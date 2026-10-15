#!/usr/bin/env python3
"""Studio Test97: explicitly launched EPCC-only comparison vs official simdjson v5.

No test automatically starts, no alteration of the upstream source, no Cloud-V.
"""
from __future__ import annotations
import datetime as dt, importlib.util,json,re,secrets,shlex,tempfile,time
from pathlib import Path

RUN_RE=re.compile(r'^test97-\d{8}T\d{6}Z-[0-9a-f]{6}$')
REQUIRED=('builds97.json','machine97.json','status97.json','results97.csv',
          'summary97.json','REPORT_97.md','manifest97.json')

def helper():
    spec=importlib.util.spec_from_file_location('test97_legacy_helper',Path(__file__).with_name('96_epcc_8h.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

def q(val):return shlex.quote(str(val))

def inspect_node(ctx,params):
    node=str(params.get('epcc_node') or 'rvc02')
    ui=getattr(ctx.studio,'test_runner',None)
    if ui is not None and hasattr(ui,'epcc_node') and ui.epcc_node.get().strip():node=ui.epcc_node.get().strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',node):raise RuntimeError('Invalid Slurm node')
    name=ctx.ssh.exec_text('sinfo -h -N -n '+q(node)+' -o "%N|%P|%T"')
    matched=[line.split('|') for line in name.splitlines() if len(line.split('|'))==3 and line.split('|')[0]==node]
    if not matched:raise RuntimeError('Node not found: '+node)
    _,partition,state=matched[0]
    if state.lower().startswith(('down','drain','fail','maint','unk')):raise RuntimeError('Node unavailable: '+state)
    partition=partition.rstrip('*')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',partition):raise RuntimeError('Invalid partition')
    limits=ctx.ssh.exec_text('sinfo -h -p '+q(partition)+' -o "%l"').strip()
    for limit in limits.splitlines():
        if limit.upper() in ('INFINITE','UNLIMITED'):continue
        try:
            days=0
            if '-' in limit:d,limit=limit.split('-',1);days=int(d)
            parts=list(map(int,limit.split(':')))
            seconds=86400*days+(3600*parts[0]+60*parts[1]+parts[2] if len(parts)==3 else 60*parts[0]+parts[1] if len(parts)==2 else parts[0])
            if seconds<11400:raise RuntimeError('Slurm partition < 3h10: '+limit)
        except ValueError:ctx.log('Cannot parse Slurm time limit: '+limit)
    account=ui.epcc_account.get().strip() if ui is not None and hasattr(ui,'epcc_account') else ''
    if account and not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}',account):raise RuntimeError('Invalid account')
    return node,partition,account

def logs(ctx,workdir,job=''):
    names=['studio97-build.log','builds97.json','status97.json','slurm97-exit.json']
    if str(job).isdigit():names.extend([f'slurm97-{job}.out',f'slurm97-{job}.err'])
    try:
        with ctx.ssh.client.open_sftp() as sftp:
            for name in names:
                try:sftp.get(workdir+'/'+name,str(ctx.output_dir/name))
                except OSError:pass
    except Exception:pass

def recover(ctx,info):
    ctx.ensure_connected()
    if getattr(ctx.studio,'active_profile',None)!='EPCC':raise RuntimeError('EPCC profile required')
    rid=str(info.get('run_id') or '')
    if not RUN_RE.fullmatch(rid):raise RuntimeError('Invalid Test97 run ID')
    from rvvlab_epcc_results import discover_epcc_runs,select_test_run,sync_epcc_run
    rows=discover_epcc_runs(ctx.ssh,ctx.remote_name)
    row=next((r for r in rows if r['id']==rid),None)
    if row is None:raise RuntimeError('Test97 run not found on EPCC: '+rid)
    logs(ctx,row['workdir'],info.get('job_id',''))
    if row.get('packet'):
        folder=sync_epcc_run(ctx.ssh,ctx.remote_name,rid,ctx.results_root)
        ctx.log('Test97 official v5 comparison results SHA256 verified: '+str(folder))
        return dict(state=row['state'],run_id=rid,packet=str(folder/'test97_results.zip'))
    ctx.log('Test97 '+rid+' '+row['state']+' rows='+str(row['rows'])+'; ZIP not yet present')
    return dict(state=row['state'],run_id=rid,rows=row['rows'],packet=None)

def execute(ctx,params):
    h=helper();h.profile(ctx)
    if int(params.get('seconds',0))!=10800:raise RuntimeError('Fixed 3h Test97 budget')
    node,partition,account=inspect_node(ctx,params)
    repo=h.source(ctx)
    if ctx.ssh.available_kib() is not None and ctx.ssh.available_kib()<1400*1024:
        raise RuntimeError('Need >=1.4 GiB free for two official Git clones and compilation')
    base=Path(__file__).resolve().parents[2]
    tools={n:base/'tools'/n for n in ('test97_native.py','test97_dom.cpp','test97_epcc_build.py',
                                    'test97_epcc.sbatch','test96_native.py','test96_epcc_build.py')}
    for name,path in tools.items():
        if not path.is_file():raise RuntimeError('Missing Test97 tool '+name)
    tag=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    rid='test97-'+tag
    from rvvlab_backend import build_source_zip
    with tempfile.TemporaryDirectory(prefix='epcc97-') as tmp:
        sourcezip=Path(tmp)/('test97-source-'+tag+'.zip')
        manifest=build_source_zip(repo,sourcezip,ctx.log)
        source_remote=ctx.ssh.deploy(sourcezip,manifest,tag,ctx.remote_name,ctx.log,ctx.stop_event)
    parent=ctx.ssh.base(ctx.remote_name)+'/test97-epcc-runs'
    workdir=parent+'/'+rid
    ctx.ssh.mkdir(parent);ctx.ssh.mkdir(workdir);ctx.ssh.mkdir(workdir+'/tools')
    remote={n:workdir+'/tools/'+n for n in tools}
    for name,path in tools.items():h.upload(ctx,path,remote[name])
    info=dict(schema=1,run_id=rid,mode='EPCC',workdir=workdir,source=source_remote,node=node,
              partition=partition,account=account,source_zip_sha256=manifest['zip_sha256'],
              started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    (ctx.output_dir/'launch97.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    ctx.log('Test97 cross-building official v5.0.3 + v5.0.4 from GitHub; no Slurm job until all builds pass.')
    command=('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0 && python3 '+
             q(remote['test97_epcc_build.py'])+' '+q(source_remote)+' '+q(workdir)+' '+
             q(remote['test97_native.py'])+' '+q(workdir+'/studio97-build.log')+' '+q(workdir+'/tools'))
    def progress(line):
        ctx.log('EPCC Test97 build: '+str(line)[:300])
    rc=ctx.ssh.exec_stream('cd '+q(workdir)+' && bash -lc '+q(command),progress,ctx.stop_event)
    if rc:
        logs(ctx,workdir)
        local=ctx.output_dir/'studio97-build.log'
        detail='\n'.join(local.read_text(errors='replace').splitlines()[-10:]) if local.is_file() else ''
        raise RuntimeError('Test97 cross-build failed BEFORE Slurm (rc='+str(rc)+'): '+detail[-1000:])
    for v in ('OFFICIAL_503','OFFICIAL_504','A2_REF','A2_G8192'):
        if not h.exists(ctx,workdir+'/test97_'+v):raise RuntimeError('Missing compiled '+v+'; no Slurm job')
    env=','.join('TEST97_'+name+'='+q(value) for name,value in [
            ('SOURCE',source_remote),('OUTPUT',workdir),('TOOL',remote['test97_native.py'])])
    command=('sbatch --parsable --chdir='+q(workdir)+' --nodelist='+q(node)+' --partition='+q(partition))
    if account:command+=' --account='+q(account)
    command+=' --export=ALL,'+env+' '+q(remote['test97_epcc.sbatch'])
    reply=ctx.ssh.exec_text(command).strip()
    match=re.fullmatch(r'(\d+)(?:;[\w.-]+)?',reply)
    if not match:raise RuntimeError('Slurm rejected Test97 submission: '+reply)
    info['job_id']=match.group(1)
    (ctx.output_dir/'launch97.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    ctx.log('Test97 EPCC Slurm job '+info['job_id']+' submitted. Closing Studio does not cancel it.')
    last=None
    for _ in range(1500):
        if ctx.stop_event.wait(30):return dict(state='monitoring_stopped',**info)
        st=h.get_json(ctx,workdir+'/status97.json')
        done=h.get_json(ctx,workdir+'/slurm97-exit.json')
        stamp=(st.get('state'),st.get('phase'),st.get('rows'),done.get('return_code'))
        if stamp!=last:
            ctx.log('Test97 EPCC '+str(stamp));last=stamp
        if done:
            return recover(ctx,info)
        if st.get('state')=='failed':
            logs(ctx,workdir,info['job_id']);return recover(ctx,info)
    return dict(state='monitoring_timeout',**info)
