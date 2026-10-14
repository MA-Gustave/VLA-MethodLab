#!/usr/bin/env python3
"""Test94 one-click Studio pipeline; every remote command issued via Studio SSH.

Cloud-V: checked simdjson source deployment + detached native compile/benchmark.
EPCC: checked deployment to riscv-login, x86 cross-build, Slurm RVV-node job.
No shell commands for end users, no secret material in remote source.
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

TERMINAL={'completed','stopped','failed','safety_stop'}
RUN_NAME=re.compile(r'^test94-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$')
NODE_NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')
PARTITION_NAME=re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$')


def quote(x):return shlex.quote(str(x))
def file_sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def _source(ctx):
    p=Path(ctx.studio.vars['repo'].get()).expanduser().resolve()
    if (p/'engine'/'src'/'simdjson.cpp').is_file():p=p/'engine'
    if not (p/'src'/'rvv'/'engines'/'engine_plan.h').is_file():
        p=Path(__file__).resolve().parents[2]/'engine'
    for rel in ('CMakeLists.txt','src/simdjson.cpp','src/rvv/engines/engine_plan.h','scripts/rvv/engines/experiments.json'):
        if not (p/rel).is_file():raise RuntimeError('Test94 engine source missing: '+str(p/rel))
    return p

def _upload_checked(ctx,path,destination):
    sftp=ctx.ssh.client.open_sftp()
    try:
        sftp.put(str(path),destination,confirm=True)
    finally:sftp.close()
    expected=file_sha(path)
    got=ctx.ssh.exec_text('sha256sum '+quote(destination)).strip().split()[0]
    if got!=expected:raise RuntimeError('Remote SHA256 mismatch for '+str(path.name))
    return expected

def _exists(ssh,path):
    try:
        f=ssh.client.open_sftp()
        try:f.stat(path);return True
        finally:f.close()
    except OSError:return False

def _grab(ctx,workdir):
    local=ctx.output_dir
    remote_zip=workdir+'/test94_results.zip'
    if not _exists(ctx.ssh,remote_zip):return None
    dst=local/'test94_results.zip'
    sftp=ctx.ssh.client.open_sftp()
    try:sftp.get(remote_zip,str(dst))
    finally:sftp.close()
    expected=ctx.ssh.exec_text('sha256sum '+quote(remote_zip)).split()[0]
    if file_sha(dst)!=expected:
        dst.unlink(missing_ok=True)
        raise RuntimeError('Downloaded Test94 ZIP SHA256 mismatch')
    import zipfile
    with zipfile.ZipFile(dst) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('Test94 results ZIP corrupt: '+bad)
        for item in ('machine94.json','status94.json','results94.csv','summary94.json','REPORT_94.md'):
            if item not in z.namelist():raise RuntimeError('Test94 packet lacks '+item)
        for item in ('machine94.json','status94.json','summary94.json','REPORT_94.md'):
            (local/item).write_bytes(z.read(item))
        (local/'results94.csv').write_bytes(z.read('results94.csv'))
    ctx.log('SHA256-verified Test94 packet downloaded: '+str(dst))
    return str(dst)

def _diagnostics(ctx,workdir):
    """Try to fetch remote logs on build or Slurm failure."""
    sftp=ctx.ssh.client.open_sftp()
    try:
        for name in ('studio94-launch.log','studio94-build.log','status94.json','builds.json'):
            try:sftp.get(workdir+'/'+name,str(ctx.output_dir/name))
            except OSError:pass
    finally:sftp.close()


def _remote_status(ssh,workdir):
    try:
        raw=ssh.exec_text('if test -f '+quote(workdir+'/status94.json')+'; then cat '+quote(workdir+'/status94.json')+'; else echo "{}"; fi')
        return json.loads(raw)
    except (ValueError,RuntimeError):return {}


def _notify(ctx,mode,state,detail='',verified=False):
    # Best-effort PC-side badge and cache; must never stop a remote run.
    callback=getattr(ctx.studio,'report_test94_state',None)
    if callable(callback):
        try:callback(mode,state,detail,ctx.output_dir,verified=verified)
        except Exception:pass


def _wait(ctx,info):
    workdir=info['workdir']; mode=info['mode'];job=info.get('job_id')
    last=None;started=time.monotonic()
    ctx.log('Remote benchmark active; you can keep Studio open for auto-download.')
    ctx.log('If Studio closes, the remote run continues. Use "Recover Test94" after reconnecting.')
    while True:
        if ctx.stop_event.wait(15):
            ctx.log('Local monitoring stopped. Remote campaign was NOT cancelled.')
            _notify(ctx,mode,'monitoring_stopped','Remote run not stopped; reconnect to check',verified=False)
            return {'state':'monitoring_stopped',**info}
        status=_remote_status(ctx.ssh,workdir)
        state=status.get('state','starting')
        if mode=='EPCC' and job:
            q=ctx.ssh.exec_text('squeue -h -j '+quote(job)+' -o %T 2>/dev/null || true').strip()
            if q and state=='starting':state='Slurm '+q.splitlines()[0]
        if mode=='Cloud-V' and not _exists(ctx.ssh,workdir+'/test94_results.zip'):
            pid=str(info.get('pid') or '')
            if pid and not ctx.ssh.exec_text('kill -0 '+quote(pid)+' 2>/dev/null && echo YES || true').strip().endswith('YES') and state=='starting':
                _diagnostics(ctx,workdir)
                raise RuntimeError('Cloud-V Test94 process ended before producing results; see launch log')
        stamp=(state,status.get('phase'),status.get('rows'))
        state_text=str(state).lower()
        if state_text.startswith('slurm pending') or state_text.startswith('slurm configuring'):
            ui_state='queued'
        elif state_text.startswith('slurm running') or state_text.startswith('slurm completing'):
            ui_state='running'
        elif state_text in TERMINAL:
            ui_state='completed' if state_text=='completed' else state_text
        elif state_text=='starting':
            ui_state='build' if mode=='Cloud-V' else 'queued'
        else:ui_state='running'
        detail=(str(status.get('phase') or ('waiting for Slurm' if mode=='EPCC' else 'initializing'))+
                (' · '+str(status['rows'])+' rows' if isinstance(status.get('rows'),int) else ''))
        _notify(ctx,mode,ui_state,detail,verified=True)
        if stamp!=last:
            ctx.log(f'Test94 {mode}: {state}, phase={status.get("phase","build/queue")}, rows={status.get("rows",0)}')
            last=stamp
        packet=_grab(ctx,workdir) if (state in TERMINAL or _exists(ctx.ssh,workdir+'/test94_results.zip')) else None
        if packet:
            state=status.get('state','completed')
            if state in {'failed','safety_stop'}:
                _notify(ctx,mode,'failed',str(status.get('reason','remote failure')),verified=True)
                raise RuntimeError('Test94 remote failure: '+str(status.get('reason','see result packet')))
            _notify(ctx,mode,'completed','Result packet SHA256 verified',verified=True)
            return {'state':state,'packet':packet,**info}
        if state in TERMINAL:
            _notify(ctx,mode,'failed' if state=='failed' else 'warning',
                    'Remote '+str(state)+'; results not yet available',verified=True)
            _diagnostics(ctx,workdir)
            raise RuntimeError('Test94 finished without results archive; see logs in '+str(ctx.output_dir))
        if mode=='EPCC' and job and not q and time.monotonic()-started>75 and state=='starting':
            info_txt=ctx.ssh.exec_text('sacct -j '+quote(job)+' --format=State -n -P 2>/dev/null | head -2 || true').strip()
            if info_txt and any(word in info_txt for word in ('FAILED','CANCELLED','TIMEOUT','NODE_FAIL')):
                _diagnostics(ctx,workdir)
                raise RuntimeError('Slurm job '+job+' failed: '+info_txt)
        if time.monotonic()-started>2*3600+1800:
            ctx.log('Local monitoring timed out. Remote job remains available for Recover Test94.')
            _notify(ctx,mode,'warning','Monitoring timeout; remote run not cancelled',verified=False)
            return {'state':'monitoring_timeout',**info}


def execute(ctx,params):
    ctx.ensure_connected()
    if params.get('seconds')!=3600:raise ValueError('Test94 pinned 3600s duration changed')
    mode=getattr(ctx.studio,'active_profile','Cloud-V')
    if mode not in ('Cloud-V','EPCC'):raise RuntimeError('Unsupported target profile: '+mode)
    _notify(ctx,mode,'prepare','Preparing Test94 source and hardware preflight')
    arch=ctx.ssh.exec_text('uname -m').strip()
    if mode=='Cloud-V' and arch!='riscv64':raise RuntimeError('Cloud-V target must be native riscv64')
    if mode=='EPCC' and arch!='x86_64':ctx.log('EPCC login architecture: '+arch+'; checking Slurm crossbuild tools')
    repo=_source(ctx)
    root=Path(__file__).resolve().parents[2]
    tool=root/'tools'/'test94_native.py';batch=root/'tools'/'test94_epcc.sbatch';builder=root/'tools'/'test94_epcc_build.py'
    if not tool.is_file() or not batch.is_file() or not builder.is_file():raise RuntimeError('Missing Test94 tools in installed Lab Studio project')
    space=ctx.ssh.available_kib()
    if space is not None and space<450*1024:raise RuntimeError('Remote disk < 450 MiB; Test94 requires source+build+results')
    ctx.log('Test94 / '+mode+' — native RISC-V one-hour benchmark: A2-O3, A2-LTO, packed_plain')
    ctx.log('Studio handles remote upload, source verification, compilation, Slurm if needed, monitoring and download.')
    from rvvlab_backend import build_source_zip
    source_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    run_id='test94-'+source_id
    _notify(ctx,mode,'upload','Packaging engine and starting SSH/SFTP transfer')
    with tempfile.TemporaryDirectory(prefix='rvvlab-test94-') as tmp:
        archive=Path(tmp)/('engine94-'+source_id+'.zip')
        manifest=build_source_zip(repo,archive,ctx.log)
        ctx.log('Engine source SHA256: '+manifest['zip_sha256'])
        source=ctx.ssh.deploy(archive,manifest,source_id,ctx.remote_name,ctx.log,ctx.stop_event)
    base=ctx.ssh.base(ctx.remote_name)
    tools_remote=base+'/test94-tools';workdir=base+'/test94-runs/'+run_id
    ctx.ssh.mkdir(tools_remote);ctx.ssh.mkdir(base+'/test94-runs');ctx.ssh.mkdir(workdir)
    tool_remote=tools_remote+'/test94_native.py';batch_remote=tools_remote+'/test94_epcc.sbatch';builder_remote=tools_remote+'/test94_epcc_build.py'
    _upload_checked(ctx,tool,tool_remote);_upload_checked(ctx,batch,batch_remote)
    if mode=='EPCC':_upload_checked(ctx,builder,builder_remote)
    info={'schema':1,'id':run_id,'mode':mode,'source':source,'source_sha256':manifest['zip_sha256'],'workdir':workdir,'tool':tool_remote,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ctx.output_dir/'launch94.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    cmd='python3 '+quote(tool_remote)+' all --source '+quote(source)+' --output '+quote(workdir)+' --seconds 3600'
    if mode=='Cloud-V':
        _notify(ctx,mode,'starting','Deployed; launching native compiler')
        launch='cd '+quote(workdir)+' && nohup '+cmd+' > '+quote(workdir+'/studio94-launch.log')+' 2>&1 < /dev/null & echo TEST94_PID=$!'
        output=ctx.ssh.exec_text('bash -lc '+quote(launch))
        match=re.search(r'TEST94_PID=(\d+)',output)
        if not match:raise RuntimeError('No detached Test94 PID: '+output)
        info['pid']=int(match.group(1));ctx.log('Cloud-V Test94 started PID '+str(info['pid']))
        _notify(ctx,mode,'build','Remote PID '+str(info['pid'])+'; waiting for build status',verified=True)
    else:
        node=str(params.get('epcc_node') or '').strip()
        partition=str(params.get('epcc_partition') or '').strip()
        account=str(params.get('epcc_account') or '').strip()
        if not NODE_NAME.fullmatch(node):raise RuntimeError('Select a specific EPCC RISC-V node in Studio before Run')
        if partition and not PARTITION_NAME.fullmatch(partition):raise RuntimeError('Invalid EPCC Slurm partition')
        if account and not NODE_NAME.fullmatch(account):raise RuntimeError('Invalid Slurm account')
        lookup=ctx.ssh.exec_text('sinfo -h -N -n '+quote(node)+' -o "%N|%P|%T|%f"')
        if not any(line.split('|')[0]==node for line in lookup.splitlines()):
            raise RuntimeError('Selected EPCC node is not visible in sinfo: '+node)
        if any(line.split('|')[0]==node and line.split('|')[2].lower().startswith(('down','drain','fail','maint','unk')) for line in lookup.splitlines()):
            raise RuntimeError('Selected node '+node+' is unavailable: '+lookup)
        ctx.log('EPCC selected node: '+node+'; features/state: '+lookup.strip())
        ctx.log('Cross-compiling RVV1.0 on EPCC login node (x86), not benchmarking the login CPU.')
        _notify(ctx,mode,'build','Cross-compiling RVV 1.0 on EPCC frontend')
        # GNU 12.2 EPCC module is RV64GC only: riscv_vector.h is absent.
        # Load LLVM16 RVV1.0 + GCC12.2 C++ sysroot; verify header, vector
        # intrinsics, linker and RISC-V ELF before compiling the test itself.
        inside=('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0 && '
                'python3 '+quote(builder_remote)+' '+quote(source)+' '+quote(workdir)+' '+quote(tool_remote)+' '+quote(workdir+'/studio94-build.log'))
        build_cmd='cd '+quote(workdir)+' && bash -lc '+quote(inside)
        logs=[]
        def progress(line):
            logs.append(line)
            if len(logs)<=15 or len(logs)%30==0:ctx.log('EPCC build: '+line)
        rc=ctx.ssh.exec_stream(build_cmd,progress,ctx.stop_event)
        if rc:
            _diagnostics(ctx,workdir)
            detail=ctx.output_dir/'studio94-build.log'
            if detail.exists():
                for line in detail.read_text(encoding='utf8',errors='replace').splitlines()[-12:]:ctx.log('EPCC build details: '+line[:450])
            raise RuntimeError('EPCC cross-build failed rc='+str(rc)+': '+' '.join(logs[-8:])+'. Build details saved in studio94-build.log')
        remote_env=('TEST94_SOURCE='+quote(source)+',TEST94_OUTPUT='+quote(workdir)+',TEST94_TOOL='+quote(tool_remote))
        submit='sbatch --parsable --chdir='+quote(workdir)+' --nodelist='+quote(node)
        if partition:submit+=' --partition='+quote(partition)
        if account:submit+=' --account='+quote(account)
        submit+=' --export=ALL,'+remote_env+' '+quote(batch_remote)
        ctx.log('Submitting Slurm job through Studio...')
        output=ctx.ssh.exec_text(submit).strip();match=re.search(r'(?<!\d)(\d{2,})(?:;[^\s]+)?',output)
        if not match:raise RuntimeError('Slurm did not confirm job ID: '+output)
        info['job_id']=match.group(1);info['node']=node;info['partition']=partition;info['account']=account
        ctx.log('Slurm job submitted: '+info['job_id']+' on '+node)
        _notify(ctx,mode,'queued','Slurm job '+info['job_id']+' on '+node,verified=True)
    (ctx.output_dir/'launch94.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    return _wait(ctx,info)


def recover(ctx,launch):
    ctx.ensure_connected()
    expected=getattr(ctx.studio,'active_profile','Cloud-V')
    if launch.get('mode')!=expected:raise RuntimeError('Choose '+str(launch.get('mode'))+' profile before recovering this run')
    if not RUN_NAME.fullmatch(str(launch.get('id',''))):raise RuntimeError('Invalid saved Test94 run ID')
    if not str(launch.get('workdir','')).endswith('/'+launch['id']):raise RuntimeError('Invalid saved remote path')
    pkt=_grab(ctx,launch['workdir'])
    if pkt:
        _notify(ctx,expected,'completed','Results downloaded and SHA256 verified',verified=True)
        return {'state':'downloaded','packet':pkt}
    st=_remote_status(ctx.ssh,launch['workdir'])
    state=st.get('state','build/queued')
    _notify(ctx,expected,'running' if state=='running' else 'failed' if state=='failed' else 'starting',
            str(st.get('phase') or state)+' · '+str(st.get('rows',0))+' rows',verified=True)
    return {'state':state, 'rows':st.get('rows',0),'job_id':launch.get('job_id')}
