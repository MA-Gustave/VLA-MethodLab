#!/usr/bin/env python3
"""ONE Test100 runner: local corpus cache -> current SSH profile -> benchmark/recovery.

Always recovers an existing run first. New submission is manual and never implicit.
Works with existing Studio EPCC/Cloud-V SSH sessions, without saving credentials.
"""
from __future__ import annotations
import datetime as dt,hashlib,importlib.util,json,os,re,secrets,shlex,subprocess,sys,tempfile
from pathlib import Path

RUN=re.compile(r'^test100-\d{8}T\d{6}Z-[a-f0-9]{6}$')
NEEDED=('status100.json','REPORT_100.md')

def q(v):return shlex.quote(str(v))
def load_helper(filename):
    p=Path(__file__).with_name(filename)
    spec=importlib.util.spec_from_file_location('helper100_'+filename.replace('.','_'),p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def list_runs(ctx,profile):
    sub='test100-epcc-runs' if profile=='EPCC' else 'test100-cloudv-runs'
    parent=ctx.ssh.base(ctx.remote_name)+'/'+sub
    with ctx.ssh.client.open_sftp() as sftp:
        try:names=sftp.listdir(parent)
        except OSError as e:
            if getattr(e,'errno',None)==2 or 'no such file' in str(e).lower():return []
            raise
    return [{'id':name,'workdir':parent+'/'+name} for name in sorted(names,reverse=True) if RUN.fullmatch(name)]

def remote_state(ctx,run):
    h=load_helper('96_epcc_8h.py')
    status=h.get_json(ctx,run['workdir']+'/status100.json')
    return status

def verified_archive(ctx,run,profile):
    import zipfile
    h=load_helper('96_epcc_8h.py')
    remote=run['workdir']+'/test100_results.zip'
    if not h.exists(ctx,remote):return None
    status=remote_state(ctx,run)
    if status.get('state') not in ('completed','failed','stopped'):
        return None
    if status.get('state')=='completed' and (status.get('validated') is not True or not isinstance(status.get('rows'),int) or status['rows']<1):return None
    if profile=='EPCC':
        from rvvlab_epcc_results import sync_epcc_run
        target=sync_epcc_run(ctx.ssh,ctx.remote_name,run['id'],ctx.results_root)
        return str(target/'test100_results.zip')
    target=Path(ctx.results_root)/'TestRunner'/'test100-adaptive-public'/'Cloud-V-'+run['id']
    target.mkdir(parents=True,exist_ok=True)
    temp=target/'test100_results.zip.part';dest=target/'test100_results.zip'
    with ctx.ssh.client.open_sftp() as sftp:sftp.get(remote,str(temp))
    expected=ctx.ssh.exec_text('sha256sum '+q(remote)).split()[0]
    if h.sha(temp)!=expected:temp.unlink(missing_ok=True);raise RuntimeError('Cloud-V results SHA256 mismatch')
    with zipfile.ZipFile(temp) as z:
        names=z.namelist()
        allowed={'builds100.json','machine100.json','status100.json','results100.csv',
                 'summary100.json','REPORT_100.md','corpus_manifest100.json','inputs100.json',
                 'studio100-build.log','slurm100-exit.json','slurm100-runtime.log'}
        if (not {'status100.json','REPORT_100.md'}.issubset(names) or
            len(names)!=len(set(names)) or not set(names).issubset(allowed) or
            z.testzip() or sum(info.file_size for info in z.infolist())>512*1024*1024):
            raise RuntimeError('Invalid Cloud-V results ZIP')
    os.replace(temp,dest)
    with zipfile.ZipFile(dest) as z:
        for name in names:(target/name).write_bytes(z.read(name))
    (target/'SYNC_OK.txt').write_text('Verified Cloud-V Test100 SHA256: '+expected+'\n',encoding='ascii')
    return str(dest)

def inspect_or_recover(ctx,profile):
    runs=list_runs(ctx,profile)
    if not runs:return None
    run=runs[0]
    state=remote_state(ctx,run)
    packet=verified_archive(ctx,run,profile)
    if packet:
        ctx.log('Test100 already on '+profile+'; SHA256 result packet downloaded: '+packet)
        return {'state':state.get('state','unknown'),'run_id':run['id'],'packet':packet}
    ctx.log('Test100 exists on '+profile+': '+run['id']+' phase='+str(state.get('phase'))+' rows='+str(state.get('rows'))+' (no duplicate submission)')
    for name in ('studio100-build.log','studio100-cloudv.log','status100.json','slurm100-exit.json'):
        try:
            with ctx.ssh.client.open_sftp() as sftp:sftp.get(run['workdir']+'/'+name,str(ctx.output_dir/name))
        except OSError:pass
    return {'state':state.get('state','unknown'),'run_id':run['id'],'rows':state.get('rows',0),'packet':None}

def local_corpus(ctx,engine):
    """Test100 uses the SAME pinned archive that every other Lab test can use."""
    from rvvlab_corpus_service import LAB, MANAGER, catalog, prepare_local
    info=prepare_local(LAB,ctx.log)
    ctx.log('Shared MethodLab corpus: '+str(info['count'])+' JSON; SHA256 '+info['digest'])
    return MANAGER,Path(info['archive']),info['digest'],catalog()['id']

def deploy_corpus(ctx,manager,corpus,digest,identifier):
    from rvvlab_corpus_service import LAB,sync_remote
    info=sync_remote(ctx.ssh,ctx.remote_name,LAB,ctx.log)
    if info['digest']!=digest or info['data'].split('/')[-1]!=identifier:
        raise RuntimeError('Shared corpus ID/hash mismatch. Test100 not launched.')
    return info['data']

def execute(ctx,params):
    ctx.ensure_connected()
    profile=getattr(ctx.studio,'active_profile','')
    if profile not in ('EPCC','Cloud-V'):raise RuntimeError('Select EPCC or Cloud-V profile for Test100')
    if int(params.get('max_seconds',14400))!=14400:raise RuntimeError('Test100 safety cap is 14400 seconds')
    existing=inspect_or_recover(ctx,profile)
    if existing:
        if existing.get('state') in ('building','queued','pending','running','starting','preflight','preparing'):
            raise RuntimeError('Existing Test100 still active/uncertain on '+profile+'; refusing a duplicate')
        if not params.get('new_run',False):return existing
    # Cross-test contention prevention, not just Test100-specific locking.
    if profile=='EPCC':
        active=ctx.ssh.exec_text('squeue -h -u "$USER" -t RUNNING -o "%j|%N" || true').strip()
        if any('rvc02' in line for line in active.splitlines()):
            raise RuntimeError('Another job occupies EPCC rvc02: '+active[:300])
    else:
        active=ctx.ssh.exec_text("ps -eo args | grep -E '[p]ython[0-9.]* .*/test(9[4-9]|100)_native[.]py' || true").strip()
        if active:raise RuntimeError('Another Cloud-V benchmark process may be active: '+active[:300])
    h=load_helper('96_epcc_8h.py')
    arch=ctx.ssh.exec_text('uname -m').strip()
    if profile=='EPCC' and arch!='x86_64':raise RuntimeError('EPCC login must be x86_64')
    if profile=='Cloud-V' and arch!='riscv64':raise RuntimeError('Cloud-V must be RISC-V')
    engine=h.source(ctx) if profile=='EPCC' else load_helper('95_cloudv_8h.py').source(ctx)
    # Scientific provenance: NEVER silently substitute a stale Lab engine when
    # the operator explicitly selected a different (but incomplete) repo.
    selected=str(ctx.studio.vars['repo'].get() or '').strip()
    if selected:
        requested=Path(selected).expanduser().resolve()
        if engine.resolve() not in (requested,(requested/'engine').resolve()):
            # An earlier Lab Studio configuration used RVV-VLA-Lab\engine,
            # which may no longer exist after the VLA-MethodLab refactor.
            # Test96 already handles that migration. Allow ONLY that known
            # legacy case, and emit a loud provenance warning in the run log.
            legacy=selected.replace('\\','/').rstrip('/').lower()
            if not (legacy.endswith('/rvv-vla-lab/engine') or
                    legacy.endswith('/rvv-vla-lab')):
                raise RuntimeError('Test100 refused engine substitution: configured repo '+selected+
                    ' is incomplete. Select your complete VectorPath-RVV checkout or VLA-MethodLab\\engine.')
            ctx.log('TEST100 ENGINE PATH MIGRATION: old configured path '+selected+
                    ' is incomplete; using bundled Lab engine '+str(engine)+
                    '. Source SHA256 will be recorded. To benchmark VectorPath directly, configure its actual full checkout.')
    ctx.log('Test100 source engine ACTUALLY BENCHMARKED: '+str(engine))
    manager,archive,digest,identifier=local_corpus(ctx,engine)
    corpus_remote=deploy_corpus(ctx,manager,archive,digest,identifier)
    # The source snapshot is separate from the data and cached corpus never enters it.
    from rvvlab_backend import build_source_zip
    tag=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    rid='test100-'+tag
    with tempfile.TemporaryDirectory(prefix='test100-src-') as tmp:
        zip_src=Path(tmp)/('test100-src-'+tag+'.zip')
        manifest=build_source_zip(engine,zip_src,ctx.log)
        source_remote=ctx.ssh.deploy(zip_src,manifest,tag,ctx.remote_name,ctx.log,ctx.stop_event)
    base=ctx.ssh.base(ctx.remote_name)
    folder=base+('/test100-epcc-runs/' if profile=='EPCC' else '/test100-cloudv-runs/')+rid
    ctx.ssh.mkdir(folder.rsplit('/',1)[0]);ctx.ssh.mkdir(folder);ctx.ssh.mkdir(folder+'/tools')
    root=Path(__file__).resolve().parents[2]
    names=['test100_native.py','test100_dom.cpp','test100_epcc_build.py','test100_epcc.sbatch',
           'test100_cloudv.sh','test100_diagnostic.py','test96_epcc_build.py']
    for name in names:
        tool=root/'tools'/name
        if not tool.is_file():raise RuntimeError('Missing Test100 tool '+name)
        h.upload(ctx,tool,folder+'/tools/'+name)
    info={'schema':1,'run_id':rid,'mode':profile,'source':source_remote,'workdir':folder,
          'corpus':corpus_remote,'corpus_id':identifier,'corpus_zip_sha256':digest,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ctx.output_dir/'launch100.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    # Mandatory pinned corpus check on EPCC login / Cloud-V BEFORE compilation or Slurm.
    preflight='python3 '+q(folder+'/tools/test100_native.py')+' preflight --output '+q(folder)+' --corpus '+q(corpus_remote)
    try:
        ctx.log('TEST100 corpus preflight: '+ctx.ssh.exec_text(preflight).strip())
    except Exception as e:
        status={'state':'failed','phase':'preflight','rows':0,'validated':False,'reason':str(e)[:700]}
        ctx.ssh.exec_text('printf '+q(json.dumps(status)+'\n')+' > '+q(folder+'/status100.json'))
        ctx.ssh.exec_text('python3 '+q(folder+'/tools/test100_diagnostic.py')+' --output '+q(folder)+' --reason '+q('Corpus preflight failed'))
        raise RuntimeError('Test100 corpus preflight failed BEFORE Slurm: '+str(e)) from e
    if profile=='EPCC':
        ctx.ssh.exec_text('printf '+q('{"state":"building","phase":"cross-compile","rows":0,"validated":false}\n')+ ' > '+q(folder+'/status100.json'))
        lookup=load_helper('97_epcc_v5_compare.py')
        node,part,account=lookup.inspect_node(ctx,{'epcc_node':params.get('epcc_node','rvc02')})
        build_command=('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0 && python3 '+
          q(folder+'/tools/test100_epcc_build.py')+' '+q(folder+'/tools/test100_native.py')+' '+
          q(source_remote)+' '+q(folder)+' '+q(folder+'/studio100-build.log'))
        rc=ctx.ssh.exec_stream('cd '+q(folder)+' && bash -lc '+q(build_command),
                               lambda line:ctx.log('Test100 EPCC build: '+str(line)[:300]),ctx.stop_event)
        if rc:
            ctx.ssh.exec_text('printf '+q(json.dumps({'state':'failed','phase':'cross-compile','rows':0,'validated':False,'reason':'Cross-compilation failed; inspect studio100-build.log'})+'\n')+' > '+q(folder+'/status100.json'))
            ctx.ssh.exec_text('python3 '+q(folder+'/tools/test100_diagnostic.py')+' --output '+q(folder)+' --reason '+q('Cross-compilation failed'))
            raise RuntimeError('Test100 official/fork builds failed BEFORE Slurm; see '+folder+'/studio100-build.log')
        for v in ('OFFICIAL_504','A2_REF','A2_G7168','A2_G8192','A2_G10240'):
            if not h.exists(ctx,folder+'/test100_'+v):raise RuntimeError('Missing binary '+v+'; Slurm not submitted')
        ctx.ssh.exec_text('printf '+q('{"state":"queued","phase":"slurm","rows":0,"validated":false}\n')+ ' > '+q(folder+'/status100.json'))
        variables='TEST100_OUTPUT='+folder+',TEST100_TOOL='+folder+'/tools/test100_native.py,TEST100_CORPUS='+corpus_remote
        command='sbatch --parsable --chdir='+q(folder)+' --nodelist='+q(node)+' --partition='+q(part)
        if account:command+=' --account='+q(account)
        command+=' --export=ALL,'+variables+' '+q(folder+'/tools/test100_epcc.sbatch')
        try:reply=ctx.ssh.exec_text(command).strip()
        except Exception:
            ctx.ssh.exec_text('printf '+q(json.dumps({'state':'failed','phase':'submission','rows':0,'validated':False,'reason':'Slurm submission failed'})+'\n')+' > '+q(folder+'/status100.json'))
            raise
        match=re.fullmatch(r'(\d+)(?:;[\w.-]+)?',reply)
        if not match:
            ctx.ssh.exec_text('printf '+q(json.dumps({'state':'failed','phase':'submission','rows':0,'validated':False,'reason':'Slurm submission failed: '+reply[:100]})+'\n')+' > '+q(folder+'/status100.json'))
            raise RuntimeError('EPCC Slurm submission failed: '+reply)
        info['job_id']=match.group(1)
        ctx.log('Test100 EPCC Slurm job '+info['job_id']+' submitted on '+node)
    else:
        check=ctx.ssh.exec_text('command -v g++ || true').strip()
        if not check:raise RuntimeError('Cloud-V g++ absent; no launch. Install native compiler or use prebuilt remote RISC-V binaries')
        if not ctx.ssh.exec_text('command -v git || true').strip():
            raise RuntimeError('Cloud-V git absent; no launch. Official baseline sources must be cloned from GitHub')
        env='TEST100_OUTPUT='+q(folder)+' TEST100_SOURCE='+q(source_remote)+' TEST100_CORPUS='+q(corpus_remote)+' TEST100_TOOL='+q(folder+'/tools/test100_native.py')
        # One detached process owns build+benchmark. Closing Studio does not cancel.
        remote='cd '+q(folder)+' && nohup env '+env+' bash '+q(folder+'/tools/test100_cloudv.sh')+' > '+q(folder+'/studio100-cloudv.log')+' 2>&1 < /dev/null & echo TEST100_PID=$!'
        reply=ctx.ssh.exec_text('bash -lc '+q(remote))
        match=re.search(r'TEST100_PID=(\d+)',reply)
        if not match:raise RuntimeError('Cloud-V launch PID not confirmed: '+reply)
        info['pid']=int(match.group(1));ctx.log('Test100 Cloud-V PID '+match.group(1)+' launched')
    (ctx.output_dir/'launch100.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    for _ in range(3):
        if ctx.stop_event.wait(5):return {'state':'monitoring_stopped',**info}
        data=remote_state(ctx,{'workdir':folder})
        if data.get('state') in ('completed','failed','stopped'):
            return inspect_or_recover(ctx,profile)
    ctx.log('Test100 launched; adaptive measurement up to 4 hours. Use Tests > Refresh to monitor it.')
    return {'state':'submitted',**info}
