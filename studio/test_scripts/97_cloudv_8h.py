#!/usr/bin/env python3
"""Studio Test97: explicit Cloud-V native 8-hour launch, SSH/SFTP and verified packet.
Closing Studio stops monitoring only. The server runner has its own 8h deadline.
"""
from __future__ import annotations
import datetime as dt, hashlib, json, re, secrets, shlex, tempfile, time, zipfile
from pathlib import Path

RUN=re.compile(r'^test97-\d{8}T\d{6}Z-[a-f0-9]{6}$')
TERMINAL={'completed','stopped','failed','safety_stop'}
def quote(x):return shlex.quote(str(x))
def file_sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def source(ctx):
    p=Path(ctx.studio.vars['repo'].get()).expanduser().resolve()
    if (p/'engine'/'src'/'simdjson.cpp').is_file():p=p/'engine'
    if not (p/'src/rvv/engines/engine_plan.h').exists():p=Path(__file__).resolve().parents[2]/'engine'
    for rel in ('src/simdjson.cpp','src/rvv/engines/engine_plan.h','scripts/rvv/explore91/support90.py','include/simdjson/simdjson_version.h'):
        if not (p/rel).is_file():raise RuntimeError('Test97 requires Lab engine snapshot: '+rel)
    if '5.0.3' not in (p/'include/simdjson/simdjson_version.h').read_text():raise RuntimeError('Test97 expects simdjson 5.0.3')
    return p
def verified_upload(ctx,path,remote):
    with ctx.ssh.client.open_sftp() as sftp:sftp.put(str(path),remote,confirm=True)
    actual=ctx.ssh.exec_text('sha256sum '+quote(remote)).strip().split()[0]
    if actual!=file_sha(path):raise RuntimeError('SSH upload SHA256 mismatch')
def exists(ctx,p):
    try:
        with ctx.ssh.client.open_sftp() as f:f.stat(p)
        return True
    except OSError:return False
def remote_status(ctx,run_dir):
    try:
        out=ctx.ssh.exec_text('if test -f '+quote(run_dir+'/status97.json')+'; then cat '+quote(run_dir+'/status97.json')+'; else echo "{}"; fi')
        return json.loads(out)
    except Exception:return {}
def grab(ctx,run_dir):
    remote=run_dir+'/test97_results.zip'
    if not exists(ctx,remote):return None
    dest=ctx.output_dir/'test97_results.zip'
    with ctx.ssh.client.open_sftp() as sftp:sftp.get(remote,str(dest))
    remote_hash=ctx.ssh.exec_text('sha256sum '+quote(remote)).split()[0]
    if file_sha(dest)!=remote_hash:
        dest.unlink(missing_ok=True)
        raise RuntimeError('Test97 packet download hash mismatch')
    with zipfile.ZipFile(dest) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('Test97 corrupt packet member '+bad)
        for name in ('builds97.json','machine97.json','status97.json','results97.csv','summary97.json','REPORT_97.md','manifest97.json'):
            if name not in z.namelist():raise RuntimeError('Missing packet member '+name)
            (ctx.output_dir/name).write_bytes(z.read(name))
    return str(dest)
def get_diagnostics(ctx,run_dir):
    try:
        with ctx.ssh.client.open_sftp() as sftp:
            for name in ('studio97-launch.log','builds97.json','status97.json'):
                try:sftp.get(run_dir+'/'+name,str(ctx.output_dir/name))
                except OSError:pass
    except Exception:pass

def wait(ctx,info):
    started=time.monotonic();run_dir=info['workdir'];last=None
    ctx.log('Test97 remote running; closing Studio does NOT stop the remote benchmark.')
    while True:
        if ctx.stop_event.wait(30):
            return {'state':'monitoring_stopped','detail':'Remote run not cancelled',**info}
        state=remote_status(ctx,run_dir);phase=state.get('phase','build');name=state.get('state','starting')
        stamp=(name,phase,state.get('rows',0))
        if stamp!=last:
            ctx.log('Cloud-V Test97: '+str(name)+' / '+str(phase)+' / '+str(state.get('rows',0))+' rows')
            last=stamp
        if name=='starting' and time.monotonic()-started>45*60:
            get_diagnostics(ctx,run_dir)
            return {'state':'build_unknown','detail':'No benchmark status after 45 minutes; review downloaded build/log, remote job may still be active',**info}
        if name=='starting' and info.get('pid'):
            alive=ctx.ssh.exec_text('kill -0 '+quote(info['pid'])+' 2>/dev/null && echo YES || true').strip().endswith('YES')
            if not alive:
                get_diagnostics(ctx,run_dir)
                raise RuntimeError('Test97 remote process ended before run status; inspect studio97-launch.log and builds97.json')
        if name in TERMINAL:
            packet=grab(ctx,run_dir)
            if packet:
                if name in ('failed','safety_stop'):
                    ctx.log('Remote stopped: '+str(state.get('reason','unknown'))+'; result packet downloaded')
                return {'state':name,'packet':packet,**info}
            raise RuntimeError('Remote terminal status but no final packet; see run dir '+run_dir)
        if time.monotonic()-started>8*3600+1800:
            return {'state':'monitoring_timeout','detail':'Check remote run via Test97 Recovery profile',**info}
def execute(ctx,params):
    ctx.ensure_connected()
    if int(params.get('seconds',0))!=28800:raise RuntimeError('Test97 fixed 28,800-second duration')
    mode=getattr(ctx.studio,'active_profile','Cloud-V')
    if mode!='Cloud-V':raise RuntimeError('Test97 Cloud-V only, not EPCC/login')
    if ctx.ssh.exec_text('uname -m').strip()!='riscv64':raise RuntimeError('Must be native RISC-V Cloud-V')
    # Refuse if Test94/95/96/97 is actively running on Cloud-V.
    # Check processes, not only status.json (which does not exist during build).
    guard = r"""import os,pathlib,json
bad=[];me=os.getpid()
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdigit() or int(p.name)==me:continue
 try:
  args=[x.decode('utf8','replace') for x in (p/'cmdline').read_bytes().split(b'\0') if x]
  if not args:continue
  if (p/'stat').read_text().rsplit(') ',1)[1][0]=='Z':continue
  exe=pathlib.Path(args[0]).name.lower()
  flag=exe.startswith(('test94_','test95_','test96_','test97_'))
  if exe.startswith(('python','pypy')):
   flag=flag or any(pathlib.Path(a).name in ('test94_native.py','test95_native.py','test96_native.py','test97_native.py') for a in args[1:])
  if flag:bad.append(p.name)
 except (OSError,ValueError,IndexError):pass
print(json.dumps(bad))"""
    overlaps=json.loads(ctx.ssh.exec_text('python3 -c '+quote(guard)).strip())
    if overlaps:raise RuntimeError('Cloud-V concurrent native benchmark detected (PIDs '+','.join(overlaps)+'). No overlapping tests allowed.')
    free=ctx.ssh.available_kib()
    if free is not None and free<650*1024:raise RuntimeError('Remote needs 650 MiB free for six builds')
    root=Path(__file__).resolve().parents[2];tool=root/'tools/test97_native.py'
    if not tool.is_file():raise RuntimeError('Install tools/test97_native.py in Lab root first')
    repo=source(ctx)
    from rvvlab_backend import build_source_zip
    runid='test97-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    source_id=runid[len('test97-'):]
    with tempfile.TemporaryDirectory(prefix='rvv-test97-') as tmp:
        archive=Path(tmp)/('engine97-'+source_id+'.zip')
        manifest=build_source_zip(repo,archive,ctx.log)
        ctx.log('Engine upload SHA256: '+manifest['zip_sha256'])
        deployed=ctx.ssh.deploy(archive,manifest,source_id,ctx.remote_name,ctx.log,ctx.stop_event)
    base=ctx.ssh.base(ctx.remote_name)
    workdir=base+'/test97-runs/'+runid;toolsdir=base+'/test97-tools'
    ctx.ssh.mkdir(toolsdir);ctx.ssh.mkdir(base+'/test97-runs');ctx.ssh.mkdir(workdir)
    remote_tool=toolsdir+'/test97_native.py'
    verified_upload(ctx,tool,remote_tool)
    info={'schema':1,'id':runid,'mode':'Cloud-V','workdir':workdir,'source':deployed,'source_sha256':manifest['zip_sha256'],'runner_sha256':file_sha(tool),'started_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    (ctx.output_dir/'launch97.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    command='python3 '+quote(remote_tool)+' all --source '+quote(deployed)+' --output '+quote(workdir)+' --seconds 28800'
    launch='cd '+quote(workdir)+' && nohup '+command+' > '+quote(workdir+'/studio97-launch.log')+' 2>&1 < /dev/null & echo TEST97_PID=$!'
    out=ctx.ssh.exec_text('bash -lc '+quote(launch))
    pid=re.search(r'TEST97_PID=(\d+)',out)
    if not pid:raise RuntimeError('Remote process PID not confirmed: '+out)
    info['pid']=int(pid.group(1))
    (ctx.output_dir/'launch97.json').write_text(json.dumps(info,indent=2)+'\n',encoding='utf8')
    ctx.log('Test97 launched on Cloud-V, remote PID '+str(info['pid']))
    return wait(ctx,info)
def recover(ctx,launch):
    ctx.ensure_connected()
    if getattr(ctx.studio,'active_profile','Cloud-V')!='Cloud-V':raise RuntimeError('Choose Cloud-V')
    if not RUN.fullmatch(str(launch.get('id',''))):raise RuntimeError('Invalid Test97 ID')
    if not str(launch.get('workdir','')).endswith('/'+launch['id']):raise RuntimeError('Invalid Test97 remote path')
    status=remote_status(ctx,launch['workdir'])
    if status.get('state') in TERMINAL:
        packet=grab(ctx,launch['workdir'])
        if not packet:raise RuntimeError('Remote finished without verified ZIP; review server log')
        return {'state':status['state'],'packet':packet,'id':launch['id'],'rows':status.get('rows')}
    ctx.log('Test97 '+launch['id']+' remote state '+str(status.get('state','unknown'))+', '+str(status.get('rows',0))+' rows')
    return {'state':status.get('state','unknown'),'id':launch['id'],'rows':status.get('rows',0)}
