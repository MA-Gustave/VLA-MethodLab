#!/usr/bin/env python3
"""Studio Test96: EPCC ONLY, Clang16 cross build on login and Slurm 8h RVV job.

Uses existing pinned SSH session; no new credentials/SSH commands on Cloud-V.
No Slurm submission without successful compilation and source compatibility check.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import secrets
import shlex
import tempfile
import time
import zipfile

RUN_RE=re.compile(r'^test96-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$')
NAME_RE=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
TERMINAL={'completed','failed','safety_stop','stopped'}
REQUIRED=('builds96.json','machine96.json','status96.json','results96.csv','summary96.json','REPORT_96.md','manifest96.json')

def q(s):return shlex.quote(str(s))

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def profile(ctx):
    ctx.ensure_connected()
    if getattr(ctx.studio,'active_profile',None)!='EPCC':
        raise RuntimeError('REFUSED: Test96 is EPCC-only. Choose EPCC before starting/recovering.')
    machine=ctx.ssh.exec_text('uname -m').strip()
    if machine!='x86_64':
        raise RuntimeError('REFUSED: EPCC build/login must be x86_64; detected '+machine)

def source(ctx):
    """Choose a complete engine, recovering from a stale Studio repo path.

    Never select a partially deployed source or silently bypass the Clang16
    compatibility check. The Lab-owned engine is a deterministic last resort.
    """
    selected=str(ctx.studio.vars['repo'].get() or '').strip()
    configured=Path(selected).expanduser().resolve() if selected else None
    lab_engine=(Path(__file__).resolve().parents[2]/'engine').resolve()
    needed=('src/simdjson.cpp', 'src/rvv/engines/engine_plan.h',
            'include/simdjson/simdjson_version.h',
            'include/simdjson/rvv/intrinsics.h',
            'scripts/rvv/explore91/support90.py')
    options=[]
    if configured is not None:
        options.extend((configured/'engine', configured))
    options.append(lab_engine)
    checked=set()
    attempts=[]
    repo=None
    for candidate in options:
        candidate=candidate.resolve()
        key=str(candidate).casefold()
        if key in checked:
            continue
        checked.add(key)
        missing=[rel for rel in needed if not (candidate/rel).is_file()]
        if missing:
            attempts.append(str(candidate)+' (missing '+', '.join(missing[:2])+')')
            continue
        repo=candidate
        break
    if repo is None:
        raise RuntimeError('EPCC Test96: no complete local engine found. Configured: '+
                           (selected or '<empty>')+'. Checked: '+'; '.join(attempts)+
                           '. In Studio select the Lab engine folder (VLA-MethodLab\\engine).')
    if configured is not None and repo not in (configured, (configured/'engine').resolve()):
        ctx.log('EPCC Test96 WARNING: configured engine missing/incomplete: '+str(configured))
        ctx.log('EPCC Test96: using installed Lab engine instead: '+str(repo))
    else:
        ctx.log('EPCC Test96: engine source selected: '+str(repo))
    if '5.0.3' not in (repo/'include/simdjson/simdjson_version.h').read_text(encoding='utf8'):
        raise RuntimeError('EPCC Test96 requires simdjson 5.0.3 in '+str(repo))
    header=(repo/'include/simdjson/rvv/intrinsics.h').read_text(encoding='utf8')
    if '__clang_major__ <= 16' not in header or '__riscv_vlmul_ext_v_u8m1_u8m2' not in header:
        raise RuntimeError('PATCH_CLANG16_ABSENT in selected LOCAL engine '+str(repo)+
                           '. Install the corrected header in THIS engine before EPCC Test96.')
    return repo

def upload(ctx,local,remote):
    with ctx.ssh.client.open_sftp() as sftp:sftp.put(str(local),remote,confirm=True)
    got=ctx.ssh.exec_text('sha256sum '+q(remote)).strip().split()[0]
    if got!=sha(local):raise RuntimeError('EPCC SFTP SHA256 mismatch: '+Path(local).name)

def exists(ctx,path):
    try:
        with ctx.ssh.client.open_sftp() as f:f.stat(path)
        return True
    except OSError:return False

def get_json(ctx,path):
    try:
        txt=ctx.ssh.exec_text('if test -f '+q(path)+'; then cat '+q(path)+'; else echo "{}"; fi')
        val=json.loads(txt)
        return val if isinstance(val,dict) else {}
    except Exception:return {}

def get_logs(ctx,workdir,job_id=''):
    names=['studio96-build.log','builds96.json','status96.json','slurm96-exit.json']
    if job_id and str(job_id).isdigit():names+=['slurm96-'+job_id+'.out','slurm96-'+job_id+'.err']
    try:
        with ctx.ssh.client.open_sftp() as sftp:
            for name in names:
                try:sftp.get(workdir+'/'+name,str(ctx.output_dir/name))
                except OSError:pass
    except Exception:pass

def download(ctx,workdir):
    remote=workdir+'/test96_results.zip'
    if not exists(ctx,remote):return None
    dest=ctx.output_dir/'test96_results.zip'
    with ctx.ssh.client.open_sftp() as sftp:sftp.get(remote,str(dest))
    remotehash=ctx.ssh.exec_text('sha256sum '+q(remote)).strip().split()[0]
    if sha(dest)!=remotehash:
        dest.unlink(missing_ok=True)
        raise RuntimeError('EPCC Test96 result archive SHA256 mismatch')
    with zipfile.ZipFile(dest) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('Corrupt ZIP member '+bad)
        for name in REQUIRED:
            if name not in z.namelist():raise RuntimeError('Missing Test96 result '+name)
        for name in REQUIRED:(ctx.output_dir/name).write_bytes(z.read(name))
    ctx.log('Test96 EPCC verified results downloaded: '+str(dest))
    return str(dest)

def select_node(ctx,params):
    panel=getattr(ctx.studio,'test_runner',None)
    node=str(params.get('epcc_node') or 'rvc02').strip()
    if panel is not None and hasattr(panel,'epcc_node'):
        from_ui=panel.epcc_node.get().strip()
        if from_ui:node=from_ui
    if not NAME_RE.fullmatch(node):raise RuntimeError('Invalid EPCC Slurm node: '+node)
    account=str(params.get('epcc_account') or '').strip()
    if panel is not None and hasattr(panel,'epcc_account'):
        account=panel.epcc_account.get().strip()
    if account and not NAME_RE.fullmatch(account):raise RuntimeError('Invalid Slurm account')
    text=ctx.ssh.exec_text('sinfo -h -N -n '+q(node)+' -o "%N|%P|%T|%f"')
    choices=[line.split('|') for line in text.splitlines() if len(line.split('|'))==4 and line.split('|')[0]==node]
    if not choices:raise RuntimeError('Selected EPCC node not found in Slurm: '+node)
    _,partition,state,features=choices[0]
    if state.lower().startswith(('down','drain','fail','maint','unk')):
        raise RuntimeError('EPCC node unavailable: '+state)
    partition=partition.rstrip('*')
    if not NAME_RE.fullmatch(partition):raise RuntimeError('Invalid Slurm partition discovered: '+partition)
    # Observe, but do not guess, partition walltime limitations.
    limits=ctx.ssh.exec_text('sinfo -h -p '+q(partition)+' -o "%l" | head -n 2').strip()
    for limit in limits.splitlines():
        limit=limit.strip()
        if not limit or limit.upper() in ('INFINITE','UNLIMITED'):continue
        try:
            days=0
            if '-' in limit:
                d,limit=limit.split('-',1);days=int(d)
            parts=[int(x) for x in limit.split(':')]
            seconds=days*86400 + (parts[0]*3600+parts[1]*60+parts[2] if len(parts)==3 else parts[0]*60+parts[1] if len(parts)==2 else parts[0] if len(parts)==1 else 0)
            if seconds and seconds<29400:
                raise RuntimeError('EPCC Slurm partition '+partition+' time limit '+limit+' is shorter than 08:10:00; 8h Test96 cannot be submitted.')
        except ValueError:ctx.log('Could not parse Slurm partition time limit: '+limit)
    return node,partition,account,state,features

def wait(ctx,info):
    run=info['workdir'];job=str(info['job_id'])
    start=time.monotonic();prev=None;missing_since=None
    ctx.log('EPCC Test96 submitted to Slurm job '+job+'. Closing Studio does not cancel it.')
    while True:
        if ctx.stop_event.wait(30):
            ctx.log('Only Studio monitoring stopped. Slurm job '+job+' continues.')
            return {'state':'monitoring_stopped',**info}
        status=get_json(ctx,run+'/status96.json')
        done=get_json(ctx,run+'/slurm96-exit.json')
        try:qstate=ctx.ssh.exec_text('squeue -h -j '+q(job)+' -o %T 2>/dev/null || true').strip()
        except Exception:qstate='unknown'
        stamp=(status.get('state'),status.get('phase'),status.get('rows'),qstate,done.get('return_code'))
        if stamp!=prev:
            ctx.log('EPCC Test96 job='+job+' Slurm='+str(qstate or 'not in queue')+
                    ' benchmark='+str(status.get('state','not started'))+
                    ' phase='+str(status.get('phase','pending'))+' rows='+str(status.get('rows',0)))
            prev=stamp
        if done:
            get_logs(ctx,run,job)
            if done.get('return_code')!=0 or status.get('state') in ('failed','safety_stop','stopped'):
                packet=download(ctx,run)
                raise RuntimeError('EPCC Test96 Slurm job '+job+' failed rc='+str(done.get('return_code'))+
                                   '. Logs retrieved; '+('partial results: '+packet if packet else 'no results packet'))
            if status.get('state')=='completed':
                packet=download(ctx,run)
                if packet:return {'state':'completed','packet':packet,**info}
        if status.get('state') in ('failed','safety_stop'):
            get_logs(ctx,run,job)
            packet=download(ctx,run)
            raise RuntimeError('EPCC Test96 failed: '+str(status.get('reason','unknown'))+
                               (' (partial results: '+packet+')' if packet else ''))
        if qstate=='' and not done and status.get('state') not in TERMINAL:
            if missing_since is None:missing_since=time.monotonic()
            if time.monotonic()-missing_since>240:
                get_logs(ctx,run,job)
                return {'state':'uncertain','reason':'Slurm job absent and no exit marker; inspect downloaded Slurm logs',**info}
        else:missing_since=None
        if time.monotonic()-start>20*3600:
            return {'state':'monitoring_timeout','reason':'Check Test96 EPCC recovery (Slurm job not cancelled)',**info}

def execute(ctx,params):
    profile(ctx)
    if int(params.get('seconds',0))!=28800:raise RuntimeError('EPCC Test96 duration fixed at 28800 s')
    node,partition,account,state,features=select_node(ctx,params)
    repo=source(ctx)
    ctx.log('Test96 EPCC target='+node+', partition='+partition+', state='+state+', features='+features)
    available=ctx.ssh.available_kib()
    if available is not None and available<700*1024:
        raise RuntimeError('EPCC shared filesystem needs >=700 MiB free before cross compilation')
    root=Path(__file__).resolve().parents[2]
    tools={name:root/'tools'/name for name in ('test96_native.py','test96_epcc_build.py','test96_epcc.sbatch')}
    for name,path in tools.items():
        if not path.is_file():raise RuntimeError('Test96 installation missing tools/'+name)
    from rvvlab_backend import build_source_zip
    tag=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    runid='test96-'+tag
    ctx.log('EPCC Test96: packaging source with corrected Clang16 intrinsics.')
    with tempfile.TemporaryDirectory(prefix='rvvlab-test96-epcc-') as tmp:
        archive=Path(tmp)/('engine96-'+tag+'.zip')
        manifest=build_source_zip(repo,archive,ctx.log)
        source_remote=ctx.ssh.deploy(archive,manifest,tag,ctx.remote_name,ctx.log,ctx.stop_event)
    base=ctx.ssh.base(ctx.remote_name)
    workdir=base+'/test96-epcc-runs/'+runid
    ctx.ssh.mkdir(base+'/test96-epcc-runs')
    ctx.ssh.mkdir(workdir)
    ctx.ssh.mkdir(workdir+'/tools')
    remote={name:workdir+'/tools/'+name for name in tools}
    for name,path in tools.items():upload(ctx,path,remote[name])
    info=dict(schema=1,run_id=runid,mode='EPCC',workdir=workdir,source=source_remote,
              source_zip_sha256=manifest['zip_sha256'],node=node,partition=partition,account=account,
              native_script_sha256=sha(tools['test96_native.py']),started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    path=ctx.output_dir/'launch96.json'
    path.write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    ctx.log('EPCC Test96: compiler verification and 7 cross-builds on x86 login (no Slurm job yet).')
    inner=('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0 && '
           'python3 '+q(remote['test96_epcc_build.py'])+' '+q(source_remote)+' '+q(workdir)+' '+
           q(remote['test96_native.py'])+' '+q(workdir+'/studio96-build.log'))
    logs=[]
    def progress(line):
        logs.append(line)
        if len(logs)<15 or len(logs)%25==0:ctx.log('EPCC build: '+str(line)[:600])
    rc=ctx.ssh.exec_stream('cd '+q(workdir)+' && bash -lc '+q(inner),progress,ctx.stop_event)
    if rc:
        get_logs(ctx,workdir)
        local=ctx.output_dir/'studio96-build.log'
        tail=local.read_text(encoding='utf8',errors='replace').splitlines()[-14:] if local.exists() else []
        for line in tail:ctx.log('BUILD ERROR: '+line[:500])
        raise RuntimeError('EPCC Test96 build failed rc='+str(rc)+' BEFORE Slurm submission. Check studio96-build.log. '+str(logs[-3:]))
    check=ctx.ssh.exec_text('test -s '+q(workdir+'/test96_A2_REF')+' && grep -q ' +
                            q('__riscv_vlmul_ext_v_u8m1_u8m2')+' '+q(source_remote+'/include/simdjson/rvv/intrinsics.h')+
                            ' && echo OK || echo BAD').strip()
    if not check.endswith('OK'):raise RuntimeError('Compiled reference or Clang16 source validation failed; no Slurm submission')
    envs=','.join('TEST96_'+key+'='+q(value) for key,value in [
        ('SOURCE',source_remote),('OUTPUT',workdir),('TOOL',remote['test96_native.py'])])
    cmd='sbatch --parsable --chdir='+q(workdir)+' --nodelist='+q(node)+' --partition='+q(partition)
    if account:cmd+=' --account='+q(account)
    cmd+=' --export=ALL,'+envs+' '+q(remote['test96_epcc.sbatch'])
    out=ctx.ssh.exec_text(cmd).strip()
    m=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?',out)
    if not m:
        get_logs(ctx,workdir)
        raise RuntimeError('Slurm did not confirm Test96 job ID; server response: '+out)
    info['job_id']=m.group(1)
    path.write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    ctx.log('EPCC Test96 Slurm job submitted: '+info['job_id']+' on '+node)
    return wait(ctx,info)

def recover(ctx,info):
    profile(ctx)
    rid=info.get('run_id')
    if info.get('mode')!='EPCC' or not RUN_RE.fullmatch(str(rid)):
        raise RuntimeError('Not a valid EPCC Test96 launch')
    wd=str(info.get('workdir') or '')
    if not wd.endswith('/'+rid) or '/test96-epcc-runs/' not in wd:
        raise RuntimeError('Invalid EPCC Test96 remote path')
    job=str(info.get('job_id') or '')
    if not job.isdigit():
        get_logs(ctx,wd)
        raise RuntimeError('This Test96 attempt never confirmed a Slurm job. Review compilation logs.')
    st=get_json(ctx,wd+'/status96.json');done=get_json(ctx,wd+'/slurm96-exit.json')
    if done:
        get_logs(ctx,wd,job)
        packet=download(ctx,wd)
        if done.get('return_code')!=0 or st.get('state') in ('failed','safety_stop','stopped'):
            raise RuntimeError('Test96 Slurm failure (logs downloaded)' + ('; partial ZIP '+packet if packet else ''))
        if packet and st.get('state')=='completed':return {'state':'completed','packet':packet,**info}
    qstate=ctx.ssh.exec_text('squeue -h -j '+q(job)+' -o %T 2>/dev/null || true').strip()
    ctx.log('EPCC Test96 '+rid+' Slurm='+str(qstate or 'not in queue')+' state='+str(st.get('state','unknown'))+
            ', phase='+str(st.get('phase','-'))+', rows='+str(st.get('rows',0)))
    return {'state':st.get('state','queued' if qstate else 'unknown'),
            'job_id':job,'rows':st.get('rows',0),'slurm':qstate}
