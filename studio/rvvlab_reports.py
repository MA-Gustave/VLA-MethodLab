"""RVV Lab light diagnostics: plain local report directories, no nested archives.

Supports the older Manager v1.2 via collect_for_manager(); optional direct download GUI.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import tempfile
import zipfile

DEFAULT_HOST = ''
DEFAULT_PORT = 22
DEFAULT_USER = ''
HOST_FP = ''
DEFAULT_REMOTE_NAME = 'rvvlab-v5'
RUN_ID_RE = re.compile(r'^\d{8}T\d{6}Z-[0-9a-f]{6}$')
REMOTE_NAME_RE = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9._-]{0,59}$')

# Run under python3 on RVV Lab. Does not modify or delete source test artifacts.
REMOTE_COLLECT = r'''
import json, os, pathlib, re, sys, zipfile
from collections import deque

root=pathlib.Path(sys.argv[1]); out=pathlib.Path(sys.argv[2]); run_id=sys.argv[3]
if not root.is_dir(): raise SystemExit('No such run: '+str(root))
if out.exists(): raise SystemExit('Refusing to overwrite existing diagnostics archive')
out.parent.mkdir(parents=True,exist_ok=True)
prune={'builds','_deps','CMakeFiles','.git','corpus','data','src','source','sources','googletest-src','benchmark-src','_build','venv','bin','lib'}
allowed_ext={'.md','.json','.log','.txt','.csv'}
important={'summary.md','summary.json','control-summary.md','control-summary.json','doctor.json','doctor.txt','metadata.json','report.md','raw.csv','summary.csv','results.csv','lscpu.txt','cpuinfo.txt','build_plan.json'}
MAX_FILES=140; MAX_TOTAL=14*1024*1024; MAX_LOG=350*1024; MAX_NONLOG=2*1024*1024

found=[]
for folder,dirs,files in os.walk(root,followlinks=False):
  depth=len(pathlib.Path(folder).relative_to(root).parts)
  if depth>10: dirs[:]=[];continue
  dirs[:]=sorted(d for d in dirs if d not in prune and not d.startswith('.'))
  for name in sorted(files):
    p=pathlib.Path(folder)/name
    if p.is_symlink() or not p.is_file() or p.suffix.lower() not in allowed_ext:continue
    rel=p.relative_to(root)
    if any(x in ('current_git_diff.patch','ssh_config','known_hosts') for x in rel.parts):continue
    if p.suffix=='.txt' and name not in important and not (name.endswith('-error.txt') or name.endswith('-errors.txt')):continue
    if p.suffix=='.json' and ('cmake' in name.lower() or 'package' in name.lower()):continue
    if p.suffix=='.csv' and 'results' not in rel.parts and name not in important:continue
    found.append((p,rel))

# Diagnostics priority: control summaries, suite summaries, failing logs, benchmark reports.
def priority(pair):
 p,rel=pair;n=p.name.lower();parts=rel.parts
 if n=='control-summary.json':return (0,len(parts),str(rel))
 if n=='control-summary.md':return (1,len(parts),str(rel))
 if n=='summary.json':return (2,len(parts),str(rel))
 if n=='summary.md':return (3,len(parts),str(rel))
 if n in ('report.md','summary.csv','raw.csv'):return (4,len(parts),str(rel))
 if n.endswith('.log') and ('dispatch' in n or 'fail' in n or 'benchmark' in n):return (5,len(parts),str(rel))
 if n.endswith('.log'):return (6,len(parts),str(rel))
 return (7,len(parts),str(rel))
found.sort(key=priority)
chosen=[];used=0;omitted=[];error_lines=[];full_reports=[]
for p,rel in found:
 if len(chosen)>=MAX_FILES or used>=MAX_TOTAL:
  omitted.append(str(rel));continue
 max_bytes=MAX_LOG if p.suffix=='.log' else MAX_NONLOG
 size=p.stat().st_size
 if p.suffix=='.log' and size>max_bytes:
  # Keep tail, which usually contains final PASS/FAIL and actual stack trace.
  with p.open('rb') as f:
   f.seek(max(0,size-max_bytes));data=f.read(max_bytes)
  data=b'[LOG TRONQUE (dernieres 350 Ko seulement)]\n'+data
 else:
  if size>max_bytes:
   omitted.append(str(rel)+' (file too large)');continue
  data=p.read_bytes()
 if used+len(data)>MAX_TOTAL:
  omitted.append(str(rel)+' (size budget)');continue
 used+=len(data)
 raw_text=data.decode('utf-8','replace')
 if p.suffix=='.log':
  lines=raw_text.splitlines()
  signals=re.compile(r'(\bFAIL\b|\bERROR\b|fatal error|Traceback|stack smashing|SIGABRT|out of space|No space left|undefined reference|mismatch|Aborted|compilation terminated)',re.I)
  matches=[i for i,s in enumerate(lines) if signals.search(s)]
  for i in matches[-65:]:
   snippet='\n'.join(lines[max(0,i-2):min(len(lines),i+4)])
   if len(error_lines)<260:error_lines.append('['+str(rel)+':'+str(i+1)+']\n'+snippet)
 if p.name in ('summary.md','control-summary.md'):
  full_reports.append((str(rel),raw_text[:40000]))
 chosen.append((str(rel),data))

header=['# DIAGNOSTIC RVV Lab RVV — '+run_id,'','Text files only. No builds, compilers, binaries or nested archives.','',
        'Sessions:','']
for rel,txt in full_reports:
 header.append('## '+rel);header.append(txt);header.append('')
if not full_reports:header.append('No summary.md available (campaign running or incomplete).')
err=['# ERREURS ET AVERTISSEMENTS EXTRAITS','', 'Extraits des journaux (les FAIL dans des tests de configuration peuvent etre normaux).',''] + error_lines
if not error_lines:err+=['No ERROR/FAIL found in collected logs.']
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 z.writestr('00_DIAGNOSTIC.md','\n'.join(header))
 z.writestr('01_ERREURS.txt','\n\n'.join(err))
 z.writestr('02_INDEX.json',json.dumps({'run_id':run_id,'files': [rel for rel,data in chosen],
                                       'omitted':omitted,'originals':len(found),'selected':len(chosen),
                                       'size_uncompressed_bytes':used},indent=2))
 # No nested ZIP/TAR. Keep native path relative to the run under details/.
 for rel,data in chosen:z.writestr('details/'+rel,data)
print('DIAGNOSTICS_READY',out,'files',len(chosen),'bytes',out.stat().st_size)
'''


def read_env(path: Path):
    if path.is_symlink():
        raise ValueError('.env est un lien symbolique : refus')
    if not path.is_file():
        raise FileNotFoundError('Missing .env file : '+str(path))
    result={}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('export '):line=line[7:].strip()
        if '=' not in line:continue
        k,v=line.split('=',1);k=k.strip();v=v.strip()
        if k not in {'RVVLAB_HOST','RVVLAB_PORT','RVVLAB_USER','RVVLAB_PASSWORD','RVVLAB_HOST_SHA256','RVVLAB_SSH_KEY'}:continue
        if len(v)>=2 and v[0]==v[-1] and v[0] in ('"',"'"):v=v[1:-1]
        result[k]=v
    return result


def _exec(client, cmd, printer):
    stdin,stdout,stderr=client.exec_command('bash -lc '+shlex.quote(cmd),timeout=120)
    raw=stdout.read().decode('utf-8','replace')
    errors=stderr.read().decode('utf-8','replace')
    rc=stdout.channel.recv_exit_status()
    if raw:printer(raw.strip())
    if rc:
        raise RuntimeError((errors or raw or 'Remote command failed')[-1500:])
    return raw


def validate_name(value):
    if not REMOTE_NAME_RE.fullmatch(value) or value in ('.','..'):raise ValueError('Invalid remote folder')
    return value


def validate_run_id(value):
    if not RUN_ID_RE.fullmatch(value):raise ValueError('Invalid campaign ID')
    return value


def latest_run(client, name=DEFAULT_REMOTE_NAME):
    sftp=client.open_sftp()
    try:
        root=sftp.normalize('.')+'/'+validate_name(name)+'/results'
        options=[p.filename for p in sftp.listdir_attr(root) if RUN_ID_RE.fullmatch(p.filename)]
        if not options:raise RuntimeError('No campaigns found in '+root)
        return max(options)
    finally:
        sftp.close()


def collect_via_client(client, run_id, local_dir, remote_name=DEFAULT_REMOTE_NAME, printer=print):
    """Download a small zipped transfer then extract all diagnostics to a PLAIN folder.

    The temporary transfer ZIP is deleted locally after success. No full test artifacts.
    """
    run_id=validate_run_id(run_id)
    local_dir=Path(local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True,exist_ok=True)
    sftp=client.open_sftp()
    try:
        home=sftp.normalize('.').rstrip('/')
        base=home+'/'+validate_name(remote_name)
        remote_results=base+'/results/'+run_id
        report_dir=base+'/reports-lite'
        try:sftp.mkdir(report_dir)
        except IOError:
            sftp.stat(report_dir)
        remote_report=report_dir+'/lite-'+run_id+'.zip'
        # Immutable report name; reuse existing report only if caller opts-in? Regenerate by unique suffix.
        import secrets
        remote_report=report_dir+'/lite-'+run_id+'-'+secrets.token_hex(4)+'.zip'
        printer('Preparing lightweight reports on RISC-V RVV target...')
        command=('python3 -c '+shlex.quote(REMOTE_COLLECT)+' '+shlex.quote(remote_results)+' '+
                 shlex.quote(remote_report)+' '+shlex.quote(run_id))
        _exec(client,command,printer)
        stat=sftp.stat(remote_report)
        if stat.st_size>24*1024*1024:
            raise RuntimeError('Report too large (>24 Mo), stopped for safety')
        dest=local_dir/('rvvlab-'+run_id)
        if dest.exists():
            import datetime
            dest=local_dir/('rvvlab-'+run_id+'-'+datetime.datetime.now().strftime('%H%M%S'))
        dest.mkdir(parents=True,exist_ok=False)
        download_tmp=None
        try:
            with tempfile.NamedTemporaryFile(prefix='rvvlab-lite-',suffix='.zip',delete=False) as tmp:
                download_tmp=Path(tmp.name)
            printer(f'Lightweight download: {stat.st_size/1024:.0f} Ko (pas les 800 Mo)')
            sftp.get(remote_report,str(download_tmp))
            with zipfile.ZipFile(download_tmp) as z:
                members=z.infolist()
                if len(members)>180 or sum(m.file_size for m in members)>22*1024*1024:
                    raise ValueError('Report security limit exceeded')
                for member in members:
                    pure=PurePosixPath(member.filename)
                    if pure.is_absolute() or '..' in pure.parts or '\\' in member.filename or ':' in member.filename:
                        raise ValueError('Nom dangereux dans le ZIP')
                    if ((member.external_attr >> 16) & 0o170000) == 0o120000:
                        raise ValueError('Lien symbolique interdit')
                    if member.filename not in ('00_DIAGNOSTIC.md', '01_ERREURS.txt', '02_INDEX.json') and pure.parts[0] != 'details':
                        raise ValueError('Unexpected file in ZIP')
                    dst=dest.joinpath(*pure.parts)
                    if member.is_dir():dst.mkdir(parents=True,exist_ok=True);continue
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    with z.open(member) as inp, dst.open('wb') as out:
                        while True:
                            data=inp.read(1024*1024)
                            if not data:break
                            out.write(data)
            printer('Reports available: '+str(dest))
        finally:
            if download_tmp:download_tmp.unlink(missing_ok=True)
        return dest
    finally:
        # Do not fill the shared RVV Lab host with transient diagnostics archives.
        try:
            if 'remote_report' in locals():sftp.remove(remote_report)
        except OSError:pass
        sftp.close()


def collect_for_manager(session, run_id, local_dir):
    """Adapter for previous Manager v1.2's RemoteSession.collect().

    Its ssh client is already authenticated and host-key checked.
    """
    name=validate_name(session.cfg.get('remote_name') or DEFAULT_REMOTE_NAME)
    folder=collect_via_client(session.ssh,run_id,Path(local_dir),name,session.log)
    session.log('No full archive transferred. Open 00_DIAGNOSTIC.md / 01_ERREURS.txt.')
    return folder
