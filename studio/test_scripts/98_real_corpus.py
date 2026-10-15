#!/usr/bin/env python3
"""ONE Test98 runner: local corpus cache -> current SSH profile -> benchmark/recovery.

Always recovers an existing run first. New submission is manual and never implicit.
Works with existing Studio EPCC/Cloud-V SSH sessions, without saving credentials.
"""
from __future__ import annotations
import datetime as dt,hashlib,importlib.util,json,os,re,secrets,shlex,subprocess,sys,tempfile
from pathlib import Path

RUN=re.compile(r'^test98-\d{8}T\d{6}Z-[a-f0-9]{6}$')
NEEDED=('builds98.json','machine98.json','status98.json','results98.csv',
        'summary98.json','REPORT_98.md','corpus_manifest98.json')

def q(v):return shlex.quote(str(v))
def load_helper(filename):
    p=Path(__file__).with_name(filename)
    spec=importlib.util.spec_from_file_location('helper98_'+filename.replace('.','_'),p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def list_runs(ctx,profile):
    sub='test98-epcc-runs' if profile=='EPCC' else 'test98-cloudv-runs'
    parent=ctx.ssh.base(ctx.remote_name)+'/'+sub
    with ctx.ssh.client.open_sftp() as sftp:
        try:names=sftp.listdir(parent)
        except OSError as e:
            if getattr(e,'errno',None)==2 or 'no such file' in str(e).lower():return []
            raise
    return [{'id':name,'workdir':parent+'/'+name} for name in sorted(names,reverse=True) if RUN.fullmatch(name)]

def remote_state(ctx,run):
    h=load_helper('96_epcc_8h.py')
    status=h.get_json(ctx,run['workdir']+'/status98.json')
    return status

def verified_archive(ctx,run,profile):
    import zipfile
    h=load_helper('96_epcc_8h.py')
    remote=run['workdir']+'/test98_results.zip'
    if not h.exists(ctx,remote):return None
    if profile=='EPCC':
        from rvvlab_epcc_results import sync_epcc_run
        target=sync_epcc_run(ctx.ssh,ctx.remote_name,run['id'],ctx.results_root)
        return str(target/'test98_results.zip')
    target=Path(ctx.results_root)/'TestRunner'/'test98-real-corpus'/'Cloud-V-'+run['id']
    target.mkdir(parents=True,exist_ok=True)
    temp=target/'test98_results.zip.part';dest=target/'test98_results.zip'
    with ctx.ssh.client.open_sftp() as sftp:sftp.get(remote,str(temp))
    expected=ctx.ssh.exec_text('sha256sum '+q(remote)).split()[0]
    if h.sha(temp)!=expected:temp.unlink(missing_ok=True);raise RuntimeError('Cloud-V results SHA256 mismatch')
    with zipfile.ZipFile(temp) as z:
        names=z.namelist()
        if sorted(names)!=sorted(NEEDED) or z.testzip() or sum(info.file_size for info in z.infolist())>512*1024*1024:
            raise RuntimeError('Invalid Cloud-V results ZIP')
    os.replace(temp,dest)
    with zipfile.ZipFile(dest) as z:
        for name in NEEDED:(target/name).write_bytes(z.read(name))
    (target/'SYNC_OK.txt').write_text('Verified Cloud-V Test98 SHA256: '+expected+'\n',encoding='ascii')
    return str(dest)

def inspect_or_recover(ctx,profile):
    runs=list_runs(ctx,profile)
    if not runs:return None
    run=runs[0]
    state=remote_state(ctx,run)
    packet=verified_archive(ctx,run,profile)
    if packet:
        ctx.log('Test98 already on '+profile+'; SHA256 result packet downloaded: '+packet)
        return {'state':state.get('state','unknown'),'run_id':run['id'],'packet':packet}
    ctx.log('Test98 exists on '+profile+': '+run['id']+' phase='+str(state.get('phase'))+' rows='+str(state.get('rows'))+' (no duplicate submission)')
    for name in ('studio98-build.log','studio98-cloudv.log','status98.json','slurm98-exit.json'):
        try:
            with ctx.ssh.client.open_sftp() as sftp:sftp.get(run['workdir']+'/'+name,str(ctx.output_dir/name))
        except OSError:pass
    return {'state':state.get('state','unknown'),'run_id':run['id'],'rows':state.get('rows',0),'packet':None}

def local_corpus(ctx,engine):
    manager=(engine/'tools/corpus98.py')
    if not manager.is_file():
        manager=Path(__file__).resolve().parents[2]/'tools/corpus98.py'
    if not manager.is_file():raise RuntimeError('Test98 corpus manager missing. Install VectorPath or complete Lab patch.')
    cache=engine/'.cache/test98-corpus'
    ctx.log('Preparing pinned public corpus locally (one-time HTTPS download, cached across runs).')
    p=subprocess.run([sys.executable,str(manager),'prepare','--cache',str(cache)],
                     text=True,capture_output=True,timeout=1000)
    if p.returncode:raise RuntimeError('Local corpus fetch failed (no synthetic fallback): '+p.stderr[-1700:])
    rec=json.loads(p.stdout.strip().splitlines()[-1]);corpus=Path(rec['archive'])
    if not corpus.is_file():raise RuntimeError('Corpus preparation did not create archive')
    # Revalidate independently before every deployment.
    spec=importlib.util.spec_from_file_location('corpus98_verified',manager)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.verify(corpus)
    ctx.log('Corpus: '+str(rec['files'])+' public documents, ZIP SHA256 '+rec['sha256'])
    return manager,corpus,rec['sha256'],m.CORPUS_ID

def deploy_corpus(ctx,manager,corpus,digest,identifier):
    h=load_helper('96_epcc_8h.py')
    base=ctx.ssh.base(ctx.remote_name)
    root=base+'/corpora/test98';folder=root+'/'+digest[:20]
    ctx.ssh.mkdir(base+'/corpora');ctx.ssh.mkdir(root);ctx.ssh.mkdir(folder)
    remote_zip=folder+'/'+identifier+'.zip';remote_manager=folder+'/corpus98.py'
    ctx.log('Checking reusable corpus cache on '+str(ctx.studio.active_profile)+' (no second download).')
    existing=ctx.ssh.exec_text('if test -f '+q(remote_zip)+'; then sha256sum '+q(remote_zip)+'; fi').strip()
    if not existing.startswith(digest+' '):
        h.upload(ctx,corpus,remote_zip+'.part')
        ctx.ssh.exec_text('mv -f '+q(remote_zip+'.part')+' '+q(remote_zip))
    h.upload(ctx,manager,remote_manager)
    installed=folder+'/data/'+identifier
    # Extraction is content-checked; the exact same files are reused on future runs.
    output=ctx.ssh.exec_text('python3 '+q(remote_manager)+' extract '+q(remote_zip)+' '+q(folder+'/data')).strip()
    if output.splitlines()[-1]!=installed:raise RuntimeError('Remote corpus extractor returned unexpected path: '+output[-250:])
    ctx.log('Corpus verified on remote: '+installed)
    return installed

def execute(ctx,params):
    ctx.ensure_connected()
    profile=getattr(ctx.studio,'active_profile','')
    if profile not in ('EPCC','Cloud-V'):raise RuntimeError('Select EPCC or Cloud-V profile for Test98')
    if int(params.get('seconds',0))!=3600:raise RuntimeError('Test98 duration fixed to 3600s')
    existing=inspect_or_recover(ctx,profile)
    if existing and not params.get('new_run',False):return existing
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
                raise RuntimeError('Test98 refused engine substitution: configured repo '+selected+
                    ' is incomplete. Select your complete VectorPath-RVV checkout or VLA-MethodLab\\engine.')
            ctx.log('TEST98 ENGINE PATH MIGRATION: old configured path '+selected+
                    ' is incomplete; using bundled Lab engine '+str(engine)+
                    '. Source SHA256 will be recorded. To benchmark VectorPath directly, configure its actual full checkout.')
    ctx.log('Test98 source engine ACTUALLY BENCHMARKED: '+str(engine))
    manager,archive,digest,identifier=local_corpus(ctx,engine)
    corpus_remote=deploy_corpus(ctx,manager,archive,digest,identifier)
    # The source snapshot is separate from the data and cached corpus never enters it.
    from rvvlab_backend import build_source_zip
    tag=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    rid='test98-'+tag
    with tempfile.TemporaryDirectory(prefix='test98-src-') as tmp:
        zip_src=Path(tmp)/('test98-src-'+tag+'.zip')
        manifest=build_source_zip(engine,zip_src,ctx.log)
        source_remote=ctx.ssh.deploy(zip_src,manifest,tag,ctx.remote_name,ctx.log,ctx.stop_event)
    base=ctx.ssh.base(ctx.remote_name)
    folder=base+('/test98-epcc-runs/' if profile=='EPCC' else '/test98-cloudv-runs/')+rid
    ctx.ssh.mkdir(folder.rsplit('/',1)[0]);ctx.ssh.mkdir(folder);ctx.ssh.mkdir(folder+'/tools')
    root=Path(__file__).resolve().parents[2]
    names=['test98_native.py','test98_dom.cpp','test98_epcc_build.py','test98_epcc.sbatch',
           'test98_cloudv.sh','test96_epcc_build.py']
    for name in names:
        tool=root/'tools'/name
        if not tool.is_file():raise RuntimeError('Missing Test98 tool '+name)
        h.upload(ctx,tool,folder+'/tools/'+name)
    info={'schema':1,'run_id':rid,'mode':profile,'source':source_remote,'workdir':folder,
          'corpus':corpus_remote,'corpus_zip_sha256':digest,'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ctx.output_dir/'launch98.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    if profile=='EPCC':
        lookup=load_helper('97_epcc_v5_compare.py')
        node,part,account=lookup.inspect_node(ctx,{'epcc_node':params.get('epcc_node','rvc02')})
        build_command=('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0 && python3 '+
          q(folder+'/tools/test98_epcc_build.py')+' '+q(folder+'/tools/test98_native.py')+' '+
          q(source_remote)+' '+q(folder)+' '+q(folder+'/studio98-build.log'))
        rc=ctx.ssh.exec_stream('cd '+q(folder)+' && bash -lc '+q(build_command),
                               lambda line:ctx.log('Test98 EPCC build: '+str(line)[:300]),ctx.stop_event)
        if rc:raise RuntimeError('Test98 official/fork builds failed BEFORE Slurm; see '+folder+'/studio98-build.log')
        for v in ('OFFICIAL_503','OFFICIAL_504','A2_REF','A2_G8192'):
            if not h.exists(ctx,folder+'/test98_'+v):raise RuntimeError('Missing binary '+v+'; Slurm not submitted')
        variables='TEST98_OUTPUT='+folder+',TEST98_TOOL='+folder+'/tools/test98_native.py,TEST98_CORPUS='+corpus_remote
        command='sbatch --parsable --chdir='+q(folder)+' --nodelist='+q(node)+' --partition='+q(part)
        if account:command+=' --account='+q(account)
        command+=' --export=ALL,'+variables+' '+q(folder+'/tools/test98_epcc.sbatch')
        reply=ctx.ssh.exec_text(command).strip()
        match=re.fullmatch(r'(\d+)(?:;[\w.-]+)?',reply)
        if not match:raise RuntimeError('EPCC Slurm submission failed: '+reply)
        info['job_id']=match.group(1)
        ctx.log('Test98 EPCC Slurm job '+info['job_id']+' submitted on '+node)
    else:
        check=ctx.ssh.exec_text('command -v g++ || true').strip()
        if not check:raise RuntimeError('Cloud-V g++ absent; no launch. Install native compiler or use prebuilt remote RISC-V binaries')
        if not ctx.ssh.exec_text('command -v git || true').strip():
            raise RuntimeError('Cloud-V git absent; no launch. Official baseline sources must be cloned from GitHub')
        env='TEST98_OUTPUT='+q(folder)+' TEST98_SOURCE='+q(source_remote)+' TEST98_CORPUS='+q(corpus_remote)+' TEST98_TOOL='+q(folder+'/tools/test98_native.py')
        # One detached process owns build+benchmark. Closing Studio does not cancel.
        remote='cd '+q(folder)+' && nohup env '+env+' bash '+q(folder+'/tools/test98_cloudv.sh')+' > '+q(folder+'/studio98-cloudv.log')+' 2>&1 < /dev/null & echo TEST98_PID=$!'
        reply=ctx.ssh.exec_text('bash -lc '+q(remote))
        match=re.search(r'TEST98_PID=(\d+)',reply)
        if not match:raise RuntimeError('Cloud-V launch PID not confirmed: '+reply)
        info['pid']=int(match.group(1));ctx.log('Test98 Cloud-V PID '+match.group(1)+' launched')
    (ctx.output_dir/'launch98.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    for _ in range(150):
        if ctx.stop_event.wait(30):return {'state':'monitoring_stopped',**info}
        data=remote_state(ctx,{'workdir':folder})
        if data.get('state') in ('completed','failed'):
            return inspect_or_recover(ctx,profile)
    return {'state':'monitoring_timeout',**info}
