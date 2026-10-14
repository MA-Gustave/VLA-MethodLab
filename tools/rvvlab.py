#!/usr/bin/env python3
"""RVV-VLA Lab: auditable SSH orchestrator; no remote root access required.

Remote execution is explicit and limited to the named, bundled workers or a
user-authored custom worker path under experiments/custom/; no shell snippets
are read from remote sources. All uploaded blobs are SHA256-checked.
"""
from __future__ import annotations
import argparse
import datetime as dt
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import sys
import tempfile
import time
import zipfile

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'orchestrator'
ENGINE=ROOT/'engine'
sys.path.insert(0,str(RUNTIME))
from rvvlab_backend import StudioSSH, parse_env, discover_env_file, build_source_zip, DEFAULT_REMOTE_NAME  # noqa: E402
from rvvlab_night import remote_runs, sync, _launch_script, validate_id  # noqa: E402

PRESETS={
 'explore-91-pilot':dict(worker='91_composition_explorer_worker.py',args=['--hours','1','--jobs','2','--core','0','--max-mib','64'],minutes=60,description='Test91: native composition pilot, broad JSON, regional dispatch; partial coverage expected'),
 'explore-91-8h':dict(worker='91_composition_explorer_worker.py',args=['--hours','8','--jobs','2','--core','0','--max-mib','64'],minutes=480,description='Test91: 242 compositions plus family-derived plans, 2304 lazy corpus designs through 64MiB'),
 'diagnose-93-3h':dict(worker='93_stage1_overhead_worker.py',args=['--hours','3','--jobs','2','--core','0','--max-mib','8'],minutes=180,description='Test93: 4-way matched A2/official/packed_plain/research, Stage1 and overhead, fixed 9 policies'),
 'explore-92-8h':dict(worker='92_staged_explorer_worker.py',args=['--hours','8','--jobs','2','--core','0','--max-mib','64'],minutes=480,description='Test92: staged 242 composition screen, 48 refine, Stage1/overhead controls, fresh-seed holdout'),
 'smoke':dict(worker='82_engine_library_smoke_5m_worker.py',args=['--seconds','300','--jobs','2','--core','0'],minutes=5,description='Fast native GCC build + JSON correctness smoke'),
 'stages-60m':dict(worker='83_stage_profile_60m_worker.py',args=['--hours','1','--jobs','2','--core','0'],minutes=60,description='Focused E14/E01/sparse8/upstream Stage1 + Stage2 + DOM'),
 'matrix-3h':dict(worker='81_engine_library_3h_worker.py',args=['--hours','3','--jobs','2','--core','0'],minutes=180,description='17-plan fixed-grid DOM exploration'),
 'stages-8h':dict(worker='84_stage_profile_8h_worker.py',args=['--hours','8','--jobs','2','--core','0'],minutes=480,description='Deep four-plan paired Stage1 + Stage2 + DOM'),
 'adaptive-smoke':dict(worker='85_adaptive_dispatch_smoke_5m_worker.py',args=['--seconds','300','--jobs','2','--core','0'],minutes=5,description='Native A2 Adaptive Dispatch v2 smoke / correctness'),
 'adaptive-30m':dict(worker='86_adaptive_dispatch_30m_worker.py',args=['--hours','0.5','--jobs','2','--core','0'],minutes=30,description='Native A0/A1/A2/official Stage1 + Stage2 + DOM A/B'),
 'prequal-60m':dict(worker='87_prequal_exploration_60m_worker.py',args=['--hours','1.0','--jobs','2','--core','0'],minutes=60,description='174-scenario exploratory A0/A1/A2 qualification sweep; trends not confirmed'),
 'prequal-fixed-60m':dict(worker='89_prequal_corrected_60m_worker.py',args=['--hours','1.0','--jobs','2','--core','0'],minutes=60,description='Corrected native smoke + six-way diverse 1h pilot; 767 JSON designs precommitted'),
 'holdout-2h':dict(worker='90_holdout_validation_2h_worker.py',args=['--hours','2.0','--jobs','2','--core','0'],minutes=120,description='Test90: held-out 512B/4KiB boundaries and A2-vs-sparse8, 3 repeat priority cases'),
 'prequal-8h':dict(worker='88_prequal_exploration_8h_worker.py',args=['--hours','8.0','--jobs','2','--core','0'],minutes=480,description='767-case A0/A1/A2 + specialist RVV patterns / Stage1+Stage2+DOM exploratory'),
}
TERMINAL={'completed','stopped','failed','safety_stop'}
REMOTE_NAME=DEFAULT_REMOTE_NAME
RESULTS=ROOT/'results'/'local'
ENV=discover_env_file(ROOT)
SETUP_ENV=RUNTIME/'.env'


def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()


def setup(_args=None):
 if SETUP_ENV.exists():
  answer=input('Existing local .env file. Overwrite? [y/N] ').strip().lower()
  if answer not in ('y','yes'):return
 print('Verify the server SSH host-key SHA256 fingerprint independently before continuing.')
 host=input('Server hostname/IP: ').strip()
 port=input('SSH port [22]: ').strip() or '22'
 user=input('SSH username: ').strip()
 pin=input('Verified host key (SHA256:...): ').strip()
 key=input('Absolute SSH private-key path (blank = password prompt at run time): ').strip()
 if not re.fullmatch(r'[A-Za-z0-9.-]+',host):raise ValueError('Invalid host')
 if not re.fullmatch(r'[A-Za-z0-9_-]+',user):raise ValueError('Invalid user')
 if not port.isdigit() or not 1<=int(port)<=65535:raise ValueError('Invalid port')
 if not re.fullmatch(r'SHA256:[A-Za-z0-9+/]{43}',pin):raise ValueError('Invalid verified host key SHA256')
 # Secret-free .env; password requested in memory at connection time.
 def value(v):return v.replace('\\','/').replace('"','')
 SETUP_ENV.write_text('\n'.join([f'RVVLAB_HOST={value(host)}', f'RVVLAB_PORT={port}',f'RVVLAB_USER={value(user)}',f'RVVLAB_HOST_SHA256={pin}',f'RVVLAB_SSH_KEY={value(key)}','RVVLAB_PASSWORD=','']) ,encoding='utf8')
 try: SETUP_ENV.chmod(0o600)
 except OSError:pass
 print('Configured locally:',SETUP_ENV,'(not part of Git or source snapshots)')
 if discover_env_file(ROOT) != SETUP_ENV:
  print('Note: shared workspace .env remains preferred. Set RVVLAB_ENV_FILE to use another file.')


def connect():
 if not ENV.is_file():raise RuntimeError(f'SSH .env not found: {ENV}. Create the file or use RVVLAB_ENV_FILE.')
 env=parse_env(ENV)
 if not env['password'] and not env['key']:
  if not sys.stdin.isatty():raise RuntimeError('Interactive SSH password required. Use an SSH private key for non-interactive runs.')
  env['password']=getpass.getpass('SSH password (not saved): ')
 if not env['password'] and not env['key']:raise RuntimeError('Missing SSH authentication')
 ssh=StudioSSH();ssh.connect(env)
 return ssh


def preflight(ssh, *, min_free_mib=200):
 out=ssh.exec_text("uname -m; command -v python3; command -v g++; g++ --version | head -n 1; df -Pk ~ | tail -n 1")
 print('REMOTE PREFLIGHT\n'+out)
 lines=out.splitlines()
 if not lines or lines[0].strip()!='riscv64':raise RuntimeError('RISC-V 64-bit Linux server required (uname -m must be riscv64)')
 free=ssh.available_kib()
 if free is None:
  print('WARNING: cannot determine remote free space; native worker will enforce its 200 MiB safety stop.')
 elif free < min_free_mib*1024:
  raise RuntimeError(f'Remote disk below safety floor: {free/1024:.1f} MiB free (<{min_free_mib} MiB)')
 elif free < 512*1024:
  print(f'WARNING: only {free/1024:.1f} MiB free. Run may stop safely if disk drops below 200 MiB.')
 return {'arch':'riscv64','available_gib':round(free/1048576,2) if free is not None else None,'compiler':lines[3].strip() if len(lines)>3 else 'unknown'}


def get_profile(name):
 if name in PRESETS:return PRESETS[name]
 if not name.startswith('custom:'):raise ValueError('Unknown profile: '+name)
 key=name.split(':',1)[1]
 if not re.fullmatch('[a-z][a-z0-9_-]{1,48}',key):raise ValueError('Invalid custom profile id')
 path=ROOT/'experiments/custom'/f'{key}.json'
 if not path.is_file():raise FileNotFoundError(f'Custom manifest not found: {path}')
 doc=json.loads(path.read_text('utf8'))
 worker=doc.get('worker')
 if not isinstance(worker,str) or not re.fullmatch(r'[a-zA-Z0-9][\w-]*\.py',worker):raise ValueError('Invalid custom worker name')
 args=doc.get('args',[])
 if not isinstance(args,list) or not all(isinstance(x,str) and len(x)<256 for x in args):raise ValueError('Invalid custom argument list')
 minutes=doc.get('max_minutes',15)
 if not isinstance(minutes,int) or not 1<=minutes<=480:raise ValueError('Custom runtime budget must be 1–480 minutes')
 return dict(worker=worker,args=args,minutes=minutes,description=doc.get('description','Custom trusted Python worker'),custom=True)


def worker_path(profile):
 if profile.get('custom'):
  p=ROOT/'experiments/custom'/profile['worker']
 else:p=ROOT/'experiments/workers'/profile['worker']
 if p.is_symlink() or not p.is_file():raise FileNotFoundError('Worker not found: '+str(p))
 return p


def run(ssh,name,yes=False,wait=False):
 profile=get_profile(name)
 worker=worker_path(profile)
 print('PROFILE:',name,'—',profile['description'])
 print('WORKER:',worker.relative_to(ROOT),'SHA256',sha(worker))
 if profile.get('custom'):
  if not yes and input('Run your CUSTOM Python code on remote server? [y/N] ').strip().lower() not in ('y','yes'):
   raise RuntimeError('Custom execution was not approved')
 pre=preflight(ssh)
 existing=remote_runs(ssh,REMOTE_NAME)
 active=[e['id'] for e in existing if e.get('state') not in TERMINAL]
 if active:raise RuntimeError('Remote campaign active or in uncertain state; refusing concurrent run: '+', '.join(active))
 print('Disk free:',pre['available_gib'],'GiB; native 200 MiB safety stop, monitored during run')
 stamp=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
 sourceid=stamp+'-'+secrets.token_hex(3)
 runid='night-'+stamp+'-'+secrets.token_hex(3)
 base=ssh.base(REMOTE_NAME)
 ssh.mkdir(base+'/explorers');ssh.mkdir(base+'/night-runs')
 rundir=base+'/night-runs/'+runid
 print('Creating immutable local C++ snapshot (no credentials or build folders)...')
 with tempfile.TemporaryDirectory(prefix='rvvlab-') as tmp:
  archive=Path(tmp)/'engine-source.zip'
  manifest=build_source_zip(ENGINE,archive,lambda line:print(line))
  print('SOURCE SHA256:',manifest['zip_sha256'],'FILES:',manifest['files'])
  deployed=ssh.deploy(archive,manifest,sourceid,REMOTE_NAME,print)
 remote_worker=base+'/explorers/'+runid+'-'+worker.name
 ssh.mkdir(rundir)
 sftp=ssh.client.open_sftp()
 try:
  sftp.put(str(worker),remote_worker,confirm=True)
  if ssh.exec_text('sha256sum '+shlex.quote(remote_worker)).split()[0]!=sha(worker):
   raise RuntimeError('Remote worker SHA256 mismatch')
  details={'run_id':runid,'source_id':sourceid,'source_sha256':manifest['zip_sha256'],
           'worker_sha256':sha(worker),'profile':name,'created_utc':stamp,'manual_approval':True}
  with sftp.file(rundir+'/launcher.json','w') as f:f.write(json.dumps(details)+'\n')
 finally:sftp.close()
 launch=_launch_script(ssh,remote_worker,['--source',deployed,'--workdir',rundir,*profile['args']],rundir+'/runner-startup.log')
 if 'NIGHT_PID=' not in launch:raise RuntimeError('Detached launch was not confirmed: '+launch)
 pid=int(launch.rsplit('NIGHT_PID=',1)[1].split()[0]);details['pid']=pid
 RESULTS.mkdir(parents=True,exist_ok=True)
 (RESULTS/(runid+'.json')).write_text(json.dumps(details,indent=2)+'\n',encoding='utf8')
 print('STARTED:',name,'RUN:',runid,'PID:',pid)
 print('Detached process continues after closing this window. Use "status", "sync", or "stop".')
 if wait:watch(ssh,runid,poll=30,max_minutes=profile['minutes']+30)
 return details


def status(ssh):
 items=remote_runs(ssh,REMOTE_NAME)
 if not items: print('No runs yet.');return []
 for a in items[:40]:print(a['id'], a.get('state','?'),'observations='+str(a.get('observations','?')),'current='+str(a.get('current_candidate','?')))
 return items


def watch(ssh,runid,*,poll=30,max_minutes=510):
 validate_id(runid)
 started=time.monotonic()
 while True:
  matches=[x for x in remote_runs(ssh,REMOTE_NAME) if x['id']==runid]
  if not matches:raise RuntimeError('Remote run not visible: '+runid)
  obj=matches[0];print(obj['id'],obj.get('state'),obj.get('observations'),obj.get('current_candidate'))
  if obj.get('state') in TERMINAL:
   try:do_sync(ssh,runid)
   except Exception as e:print('Sync not ready yet:',e)
   return obj
  if time.monotonic()-started>max_minutes*60:
   print('Local watch timed out; detached remote worker remains active');return obj
  time.sleep(max(5,poll))


def do_sync(ssh,runid):
 validate_id(runid)
 folder=sync(ssh,REMOTE_NAME,runid,RESULTS)
 packet=RESULTS/(runid+'-evidence.zip')
 with zipfile.ZipFile(packet,'w',zipfile.ZIP_DEFLATED) as z:
  for p in folder.iterdir():
   if p.is_file():z.write(p,p.name)
 print('SHA256 VERIFIED EVIDENCE:',folder,'\nARCHIVE:',packet)
 return packet


def stop(ssh,runid,yes=False):
 validate_id(runid)
 matches=[r for r in remote_runs(ssh,REMOTE_NAME) if r['id']==runid]
 if not matches:raise ValueError('Run not found')
 if matches[0].get('state') in TERMINAL:
  print('Run already terminated:',matches[0].get('state'));return
 if not yes and input(f'Send graceful STOP to {runid}? [y/N] ').lower().strip() not in ('y','yes'):return
 p=ssh.base(REMOTE_NAME)+'/night-runs/'+runid+'/STOP'
 sftp=ssh.client.open_sftp()
 try:
  with sftp.file(p,'wb') as f:f.write(b'Graceful stop requested by user\n')
 finally:sftp.close()
 print('Graceful STOP requested. Wait for terminal status then sync evidence.')


def wizard():
 if not ENV.exists():setup()
 while True:
  print('\nRVV-VLA LAB — Native RISC-V research')
  keys=list(PRESETS)
  for n,key in enumerate(keys,1):
   profile=PRESETS[key]
   print(f' {n}. {key:<16} {profile["description"]} ({profile["minutes"]} min)')
  status_no=len(keys)+1
  sync_no=len(keys)+2
  studio_no=len(keys)+3
  print(f' {status_no}. Status | {sync_no}. Sync results | {studio_no}. Studio instructions | 0. Exit')
  selection=input('Select: ').strip()
  if selection=='0' or not selection:return
  if selection.isdigit() and 1<=int(selection)<=len(keys):
   name=keys[int(selection)-1]
   if input(f'Start {name} on YOUR configured server? [y/N] ').strip().lower() not in ('y','yes'):continue
   ssh=connect()
   try:run(ssh,name)
   finally:ssh.close()
  elif selection==str(status_no):
   ssh=connect()
   try:status(ssh)
   finally:ssh.close()
  elif selection==str(sync_no):
   runid=input('Run id: ').strip()
   ssh=connect()
   try:do_sync(ssh,runid)
   finally:ssh.close()
  elif selection==str(studio_no):
   print('Integrated desktop Studio: run START_STUDIO.ps1 from this Lab root.')
  else:print('Unknown selection')


def main(argv=None):
 p=argparse.ArgumentParser(description='Reproducible RVV-VLA Lab / native SSH orchestrator')
 sub=p.add_subparsers(dest='cmd')
 sub.add_parser('setup',help='Configure host, pinned host key and authentication')
 sub.add_parser('wizard',help='Interactive one-click menu')
 sub.add_parser('preflight',help='Verify target architecture/GCC/disk')
 sub.add_parser('status',help='List remote campaigns')
 runp=sub.add_parser('run',help='Launch a named native worker remotely')
 runp.add_argument('profile',help='smoke, stages-60m, matrix-3h, stages-8h, adaptive-smoke, adaptive-30m, prequal-60m, prequal-fixed-60m, holdout-2h, prequal-8h, or custom:<id>')
 runp.add_argument('--yes',action='store_true',help='Approve custom worker execution')
 runp.add_argument('--wait',action='store_true',help='Watch and sync when done')
 for cmd in ('watch','sync','stop'):
  q=sub.add_parser(cmd);q.add_argument('run_id')
  if cmd=='stop':q.add_argument('--yes',action='store_true')
 args=p.parse_args(argv)
 if args.cmd in (None,'wizard'):wizard();return 0
 if args.cmd=='setup':setup();return 0
 ssh=connect()
 try:
  if args.cmd=='preflight':preflight(ssh)
  elif args.cmd=='status':status(ssh)
  elif args.cmd=='run':run(ssh,args.profile,yes=args.yes,wait=args.wait)
  elif args.cmd=='watch':watch(ssh,args.run_id)
  elif args.cmd=='sync':do_sync(ssh,args.run_id)
  elif args.cmd=='stop':stop(ssh,args.run_id,yes=args.yes)
 finally:ssh.close()
 return 0

if __name__=='__main__':
 try:raise SystemExit(main())
 except (RuntimeError,ValueError,OSError) as e:
  print('ERROR:',e,file=sys.stderr);raise SystemExit(2)
