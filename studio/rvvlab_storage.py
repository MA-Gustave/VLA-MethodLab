"""Safe RVV Lab run inventory, complete diagnostic-text sync, and opt-in cleanup.

No SSH credentials here; the caller supplies an authenticated pinned-key client.
No remote deletion before a locally verified sync, explicit UI confirmation, and
remote protection of the newest session. Never removes files outside
~/rvvlab-v5/{results,sources}/<validated run_id>.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shlex
import shutil
import tempfile
import zipfile
from rvvlab_reports import _exec, validate_run_id, validate_name

# Server script is data-only and returns JSON; no sudo or modification.
REMOTE_INVENTORY = r'''
import json,os,pathlib,re,shutil,sys
name=sys.argv[1]
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,59}',name) or name in ('.','..'):raise SystemExit('Bad remote root name')
home=pathlib.Path.home().resolve();base=home/name
if base.is_symlink():raise SystemExit('Remote root is a symlink')
results=base/'results';sources=base/'sources'
pattern=re.compile(r'^\d{8}T\d{6}Z-[0-9a-f]{6}$')
if not results.is_dir() or results.is_symlink():raise SystemExit('Results directory missing or symlinked')

def size(root):
 if not root.exists() or root.is_symlink():return 0
 total=0
 for p,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=[d for d in dirs if not (pathlib.Path(p)/d).is_symlink()]
  for f in files:
   q=pathlib.Path(p)/f
   if not q.is_symlink():
    try:total+=q.stat().st_size
    except OSError:pass
 return total
runs=[]
for p in sorted(results.iterdir(),reverse=True):
 if not pattern.fullmatch(p.name) or p.is_symlink() or not p.is_dir():continue
 runs.append({'id':p.name,'results_bytes':size(p),'sources_bytes':size(sources/p.name)})
disk=shutil.disk_usage(home)
print(json.dumps({'disk_total':disk.total,'disk_used':disk.used,'disk_free':disk.free,
 'runs':runs,'home':str(home)}))
'''

# Every eligible diagnostic text file is preserved IN FULL (no truncation).
# Compilation directories, dependency caches and nested binaries never enter the sync.
REMOTE_EXPORT = r'''
import hashlib,json,os,pathlib,re,sys,zipfile
name,run_id,out_name=sys.argv[1:4]
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,59}',name) or name in ('.','..'):raise SystemExit('Invalid remote name')
if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{6}',run_id):raise SystemExit('Invalid run ID')
home=pathlib.Path.home().resolve();base=home/name
root=base/'results'/run_id
out=base/'reports-lite'/out_name
if base.is_symlink() or (base/'results').is_symlink() or root.is_symlink() or not root.is_dir():raise SystemExit('Unsafe or missing run')
if out.is_symlink() or out.exists() or out.parent.is_symlink():raise SystemExit('Unsafe output path')
if not out_name.startswith('sync-'+run_id+'-') or not out_name.endswith('.zip') or '/' in out_name:raise SystemExit('Invalid output name')
out.parent.mkdir(parents=True,exist_ok=True)
prune={'builds','_deps','CMakeFiles','.git','corpus','data','src','sources','source','googletest-src','benchmark-src','_build','venv','bin','lib','node_modules','_CPack_Packages','Testing'}
exts={'.md','.json','.log','.txt','.csv','.tsv','.yaml','.yml'}
MAX_FILES=1600; MAX_SINGLE=32*1024*1024; MAX_TOTAL=150*1024*1024
selected=[];total=0
for folder,dirs,files in os.walk(root,followlinks=False):
 relfolder=pathlib.Path(folder).relative_to(root)
 if len(relfolder.parts)>12:raise SystemExit('Directory depth limit exceeded; refusing incomplete archive')
 dirs[:]=sorted(d for d in dirs if d not in prune and not d.startswith('.') and not (pathlib.Path(folder)/d).is_symlink())
 for filename in sorted(files):
  path=pathlib.Path(folder)/filename
  if path.is_symlink() or not path.is_file() or path.suffix.lower() not in exts:continue
  rel=path.relative_to(root)
  if any(x in ('current_git_diff.patch','known_hosts','ssh_config') for x in rel.parts):continue
  if filename.lower().startswith(('.env','id_rsa','id_ed25519')):continue
  n=path.stat().st_size
  if n>MAX_SINGLE:raise SystemExit('Text file too large to safely sync: '+str(rel))
  total+=n
  if total>MAX_TOTAL or len(selected)>=MAX_FILES:raise SystemExit('Run has too many logs; refusing incomplete sync')
  selected.append((path,rel))
if not selected:raise SystemExit('No diagnostic text files; refusing empty sync')
manifest={'version':1,'run_id':run_id,'files':[],'text_bytes':total,'excluded_builds_and_binaries':True}
try:
 with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=False) as z:
  for path,rel in selected:
   before=path.stat()
   sha=hashlib.sha256()
   with path.open('rb') as fp:
    while True:
     data=fp.read(1024*1024)
     if not data:break
     sha.update(data)
   after=path.stat()
   if before.st_size!=after.st_size or before.st_mtime_ns!=after.st_mtime_ns:raise SystemExit('Log changed during sync; retry later: '+str(rel))
   z.write(path,'details/'+rel.as_posix())
   manifest['files'].append({'name':rel.as_posix(),'bytes':before.st_size,'sha256':sha.hexdigest()})
  z.writestr('SYNC_MANIFEST.json',json.dumps(manifest,indent=2))
 if out.stat().st_size>110*1024*1024:raise SystemExit('Compressed diagnostics exceed safety limit')
 h=hashlib.sha256()
 with out.open('rb') as inp:
  for chunk in iter(lambda:inp.read(1024*1024),b''):h.update(chunk)
 print(json.dumps({'zip_sha256':h.hexdigest(),'size_bytes':out.stat().st_size,'files':len(selected),'text_bytes':total}))
except BaseException:
 try:out.unlink(missing_ok=True)
 except OSError:pass
 raise
'''

# Destructive stage: exact validated paths, newest session guarded,
# and running process detection. Selection and consent already checked on UI.
REMOTE_PURGE = r'''
import json,os,pathlib,re,shutil,sys
name,run_id=sys.argv[1:3]
if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,59}',name) or name in ('.','..'):raise SystemExit('Invalid remote root')
if not re.fullmatch(r'\d{8}T\d{6}Z-[0-9a-f]{6}',run_id):raise SystemExit('Invalid run ID')
home=pathlib.Path.home().resolve();base=home/name
results=base/'results';sources=base/'sources';run=results/run_id;src=sources/run_id
if base.is_symlink() or results.is_symlink() or sources.is_symlink() or run.is_symlink() or src.is_symlink():raise SystemExit('Symlink refused')
if not run.is_dir():raise SystemExit('Results not found')
pattern=re.compile(r'\d{8}T\d{6}Z-[0-9a-f]{6}')
allruns=sorted((p.name for p in results.iterdir() if p.is_dir() and not p.is_symlink() and pattern.fullmatch(p.name)),reverse=True)
if run_id in allruns[:1]:raise SystemExit('Refus: newest campaign is protected')
# Do not purge while native tests for this campaign are running.
for pid in os.listdir('/proc'):
 if not pid.isdigit() or int(pid) in (os.getpid(),os.getppid()):continue
 try:cmd=(pathlib.Path('/proc')/pid/'cmdline').read_bytes().replace(b'\0',b' ').decode('utf-8','replace')
 except (OSError,PermissionError):continue
 if run_id in cmd and any(marker in cmd for marker in ('server_control.py','native_suite.py','bench_native.py','run_tests.py','rvv_night_runner.py','cmake','ninja','ctest','/benchmark/')):
  raise SystemExit('A process may still be running for this campaign; purge refused')
if src.exists() and not src.is_dir():raise SystemExit('Source is not a directory')
# Path must stay immediately under expected parents (never follow symlinks).
if run.parent!=results or src.parent!=sources:raise SystemExit('Unexpected parent')
shutil.rmtree(run)
if src.is_dir():shutil.rmtree(src)
print(json.dumps({'deleted_run':run_id,'results_removed':True,'sources_removed':not src.exists()}))
'''


def _remote_exec(client, script, argv, printer=lambda _: None):
    return _exec(client, 'python3 -c '+shlex.quote(script)+' '+' '.join(shlex.quote(a) for a in argv), printer)


def inventory(client, remote_name):
    obj=json.loads(_remote_exec(client,REMOTE_INVENTORY,[validate_name(remote_name)]))
    if not isinstance(obj.get('runs'),list):raise RuntimeError('Malformed remote inventory')
    return obj


def archive_folder(local_root,run_id):
    validate_run_id(run_id)
    return Path(local_root).expanduser().resolve()/'Archives_serveur'/('rvvlab-'+run_id)


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as inp:
        for chunk in iter(lambda:inp.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def verify_local(folder,run_id):
    """Fail closed: verify every restored text file, no superficial marker check."""
    folder=Path(folder)
    try:
        marker=json.loads((folder/'SYNC_OK.json').read_text(encoding='utf-8'))
        manifest=json.loads((folder/'SYNC_MANIFEST.json').read_text(encoding='utf-8'))
        if marker.get('run_id')!=run_id or manifest.get('run_id')!=run_id:return False
        if _sha(folder/'SYNC_MANIFEST.json')!=marker.get('manifest_sha256'):return False
        files=manifest['files']
        if not files or len(files)>1600:return False
        names=set()
        for f in files:
            n=f['name'];p=PurePosixPath(n)
            if not n or n in names or p.is_absolute() or '..' in p.parts or '\\' in n or ':' in n:return False
            names.add(n)
            path=folder/'details'/Path(*p.parts)
            if path.is_symlink() or not path.is_file() or path.stat().st_size!=f['bytes'] or _sha(path)!=f['sha256']:return False
        return True
    except (OSError,ValueError,TypeError,KeyError,OverflowError):return False


def _extract_verified(zippath,stage,run_id):
    with zipfile.ZipFile(zippath) as z:
        infos=z.infolist()
        if len(infos)>1601 or z.testzip() is not None:raise RuntimeError('Corrupt text archive')
        names={i.filename for i in infos}
        if 'SYNC_MANIFEST.json' not in names:raise RuntimeError('Manifest absent')
        raw=z.read('SYNC_MANIFEST.json')
        manifest=json.loads(raw)
        if manifest.get('run_id')!=run_id:raise RuntimeError('Wrong campaign inside archive')
        listed={'details/'+f['name'] for f in manifest['files']}
        if names!=listed|{'SYNC_MANIFEST.json'}:raise RuntimeError('Contenu inattendu ou rapport manquant')
        if manifest.get('text_bytes',0)>150*1024*1024:raise RuntimeError('Archive exceeds size limit')
        stage.mkdir(parents=True,exist_ok=False)
        for info in infos:
            p=PurePosixPath(info.filename)
            if p.is_absolute() or '..' in p.parts or '\\' in info.filename or ':' in info.filename:
                raise RuntimeError('Unsafe path in archive')
            if ((info.external_attr>>16)&0o170000)==0o120000:raise RuntimeError('Symlink dans archive')
            if info.is_dir():raise RuntimeError('Unexpected directory entry')
            if info.file_size>32*1024*1024:raise RuntimeError('Fichier texte trop volumineux')
            dest=stage.joinpath(*p.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as inp,dest.open('wb') as out:
                shutil.copyfileobj(inp,out,1024*1024)
    marker={'run_id':run_id,'manifest_sha256':_sha(stage/'SYNC_MANIFEST.json'),'files':len(manifest['files'])}
    (stage/'SYNC_OK.json').write_text(json.dumps(marker,indent=2),encoding='utf-8')
    if not verify_local(stage,run_id):raise RuntimeError('Local SHA256: at least one file failed verification')
    return marker


def sync_run(client,run_id,local_root,remote_name,printer=print):
    run_id=validate_run_id(run_id);remote_name=validate_name(remote_name)
    folder=archive_folder(local_root,run_id)
    if folder.exists():
        if verify_local(folder,run_id):
            printer('Archive already synced and verified: '+str(folder))
            return folder
        raise RuntimeError('Local archive exists but is not verified: '+str(folder)+'; refusing overwrite')
    folder.parent.mkdir(parents=True,exist_ok=True)
    sftp=client.open_sftp()
    remote_file=None
    temp_file=None
    stage=None
    try:
        home=sftp.normalize('.').rstrip('/')
        remote_file=home+'/'+remote_name+'/reports-lite/sync-'+run_id+'-'+secrets.token_hex(6)+'.zip'
        printer('Compressing text logs and reports on RVV Lab (excluding builds)...')
        response=_remote_exec(client,REMOTE_EXPORT,[remote_name,run_id,remote_file.rsplit('/',1)[-1]],printer)
        remote_meta=json.loads(response)
        if not 0<remote_meta['size_bytes']<=110*1024*1024:raise RuntimeError('Archive distante trop volumineuse')
        with tempfile.NamedTemporaryFile(prefix='rvvlab-sync-',suffix='.zip',delete=False) as fp:temp_file=Path(fp.name)
        printer(f'Compressed download: {remote_meta["size_bytes"]/1024/1024:.2f} Mio (journaux complets)')
        sftp.get(remote_file,str(temp_file))
        if temp_file.stat().st_size!=remote_meta['size_bytes'] or _sha(temp_file)!=remote_meta['zip_sha256']:
            raise RuntimeError('SSH transfer SHA256 mismatch: deletion forbidden')
        stage=folder.parent/(folder.name+'.tmp-'+secrets.token_hex(4))
        mark=_extract_verified(temp_file,stage,run_id)
        stage.rename(folder)
        printer(f'SHA256 sync and verification complete: {mark["files"]} files.\n{folder}')
        return folder
    finally:
        if temp_file:temp_file.unlink(missing_ok=True)
        if stage and stage.exists():shutil.rmtree(stage,ignore_errors=True)
        if remote_file:
            try:sftp.remove(remote_file)
            except OSError:pass
        sftp.close()


def purge_run(client,run_id,local_root,remote_name,printer=print):
    """Only called AFTER typed UI confirmation; does not auto-purge ever."""
    validate_run_id(run_id)
    folder=archive_folder(local_root,run_id)
    if not verify_local(folder,run_id):
        raise RuntimeError('Deletion refused: Windows archive missing or invalid SHA256')
    info=json.loads(_remote_exec(client,REMOTE_PURGE,[validate_name(remote_name),run_id],printer))
    if info.get('deleted_run')!=run_id:raise RuntimeError('Unexpected deletion response')
    printer('Purge completed: '+run_id+' (sources + results), local archive preserved')
    return info
