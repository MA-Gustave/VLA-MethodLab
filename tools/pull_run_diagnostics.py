#!/usr/bin/env python3
"""Read-only recovery of a finished RVV-Lab run, preserving diagnostics.

Does not start a campaign, change files on the server, or copy credentials.
Only connects to configured/pinned SSH host. ZIP stays in ignored results/local.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'orchestrator'))
from rvvlab_backend import StudioSSH, parse_env, discover_env_file, DEFAULT_REMOTE_NAME
from rvvlab_night import validate_id, sync

DEFAULT_RUN='night-20261012T031326Z-43b730'
MAX_LOG_BYTES=256*1024
MAX_DIAGNOSTICS=10*1024*1024
EXACT={'status.json','checkpoint.json','failures.csv','metadata.json',
       'runner-startup.log','latest_bench.log','upstream_clone.log','launcher.json',
       'hypotheses.md','EXPLORATION_8H.md','TRENDS.md'}
PATTERN=re.compile(r'^(?:compile|link|correctness)_[A-Za-z0-9_\-]{1,96}\.log$')


def allowed(name):
    return name in EXACT or bool(PATTERN.fullmatch(name))


def pull_diagnostics(ssh,runid,dest):
    remote=ssh.base(DEFAULT_REMOTE_NAME)+'/night-runs/'+runid
    sftp=ssh.client.open_sftp()
    entries=[]
    diagnostics=dest/'diagnostics'
    diagnostics.mkdir(parents=True,exist_ok=True)
    total=0
    try:
        for item in sorted(sftp.listdir_attr(remote),key=lambda x:x.filename):
            name=item.filename
            if not allowed(name):continue
            if not stat.S_ISREG(item.st_mode):continue
            if total >= MAX_DIAGNOSTICS:break
            # Download the last 256 KiB of each possibly large log; bounded SSH traffic.
            offset=max(0,item.st_size-MAX_LOG_BYTES)
            with sftp.file(remote+'/'+name,'rb') as f:
                f.seek(offset)
                data=f.read(min(MAX_LOG_BYTES,MAX_DIAGNOSTICS-total))
            total+=len(data)
            p=diagnostics/name
            p.write_bytes(data)
            entries.append({'name':name,'bytes':len(data),
                            'source_bytes':item.st_size,'tail_from_offset':offset,
                            'sha256':hashlib.sha256(data).hexdigest()})
            print('DIAGNOSTIC:',name,f'{len(data):,} bytes',
                  f'(tail at byte {offset:,})' if offset else '')
    finally:
        sftp.close()
    (diagnostics/'DOWNLOAD_MANIFEST.json').write_text(
        json.dumps({'schema':'rvv-lab-recovery.v1','run_id':runid,
                    'read_only':True,'files':entries},indent=2)+'\n',encoding='utf-8')
    return diagnostics


def main():
    p=argparse.ArgumentParser(description='Read-only pull for RVV-VLA Lab run diagnostics and verified snapshot.')
    p.add_argument('run_id',nargs='?',default=DEFAULT_RUN)
    args=p.parse_args()
    runid=validate_id(args.run_id)
    env_path=discover_env_file(ROOT)
    if not env_path.is_file():p.error('SSH .env not found; expected external parent .env or RVVLAB_ENV_FILE')
    conf=parse_env(env_path)
    if not conf.get('key') and not conf.get('password'):
        if not sys.stdin.isatty():p.error('Interactive SSH authentication required')
        conf['password']=getpass.getpass('SSH password (not stored): ')
    ssh=StudioSSH()
    output=ROOT/'results'/'local'/runid
    output.mkdir(parents=True,exist_ok=True)
    try:
        print('Connecting to the pinned SSH host; remote access is read only.')
        ssh.connect(conf)
        # The main sync is SHA256 protected. If it fails, still recover logs.
        sync_error=None
        try:
            synced=sync(ssh,DEFAULT_REMOTE_NAME,runid,ROOT/'results'/'local')
            print('VERIFIED SNAPSHOT:',synced)
        except Exception as exc:
            sync_error=f'{type(exc).__name__}: {exc}'
            print('Snapshot could not be verified; fetching raw diagnostics instead:',sync_error)
        logs=pull_diagnostics(ssh,runid,output)
    finally:
        ssh.close()
    status_file=(output/'status.json') if (output/'status.json').is_file() else (output/'diagnostics/status.json')
    if status_file.is_file():
        try:
            st=json.loads(status_file.read_text(encoding='utf-8'))
            print('RUN STATE:',st.get('state'))
            print('OBSERVATIONS:',st.get('observations'))
            print('STOP REASON:',st.get('stop_reason'))
        except (OSError,ValueError) as exc:print('Could not parse status.json:',exc)
    target=ROOT/'results'/'local'/(runid+'-diagnostics.zip')
    # Include verified result files plus raw diagnostics; not the 767 JSON corpus files.
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for x in sorted(output.rglob('*')):
            if x.is_file() and not x.is_symlink():
                rel=x.relative_to(output).as_posix()
                if rel.startswith('diagnostics/') or x.name in {
                    'SYNC_OK.txt','status.json','checkpoint.json','map.csv','ranking.csv',
                    'hypotheses.md','failures.csv','metadata.json','corpus_manifest.json',
                    'trend_candidates.csv','prequal_pairwise.csv','TRENDS.md',
                    'coverage_by_design.csv','hypotheses_to_confirm.csv','EXPLORATION_8H.md'}:
                    z.write(x,rel)
        z.writestr('RECOVERY_NOTE.txt',
            'Remote read-only recovery of '+runid+'\n'+
            ('Main snapshot verification error: '+sync_error+'\n' if sync_error else
             'Main snapshot verified with remote SHA256.\n')+
            'Diagnostics log files may contain machine paths; review before public release.\n')
    if zipfile.ZipFile(target).testzip():raise RuntimeError('ZIP integrity error')
    print('\nUPLOAD THIS ZIP TO CHAT (do not commit without reviewing paths):\n'+str(target))
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (OSError,ValueError,RuntimeError) as exc:
        print('ERROR:',exc,file=sys.stderr)
        raise SystemExit(2)
