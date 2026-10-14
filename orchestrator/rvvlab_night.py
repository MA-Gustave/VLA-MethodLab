"""Night Explorer controls for RVV Lab Studio. Requires connected/pinned SSH client.

The worker is launched detached. Sync is checksum-verified, bounded, and atomic.
No deletion on the server and no nested build archives.
"""
from __future__ import annotations
import hashlib, io, json, os, pathlib, re, shlex, shutil, tempfile, time, zipfile
from rvvlab_backend import validate_remote_name

RUN_RE=re.compile(r'^night-\d{8}T\d{6}Z-[0-9a-f]{6}$')
SOURCE_RE=re.compile(r'^\d{8}T\d{6}Z-[0-9a-f]{6}$')
MAX_ZIP=32*1024*1024
WORKER=pathlib.Path(__file__).resolve().parent/'rvv_night_runner.py'


def validate_id(value):
    if not RUN_RE.fullmatch(value):raise ValueError('Invalid Night Runner ID')
    return value


def base_path(ssh,remote_name):return ssh.base(validate_remote_name(remote_name))


def available_sources(ssh,remote_name):
    path=base_path(ssh,remote_name)+'/sources'
    sftp=ssh.client.open_sftp()
    try:
        candidates=[x for x in sftp.listdir(path) if SOURCE_RE.fullmatch(x)]
        result=[]
        for name in sorted(candidates,reverse=True):
            src=path+'/'+name
            try:
                sftp.stat(src+'/scripts/rvv/perf/bench_native.py')
                sftp.stat(src+'/CMakeLists.txt')
            except IOError:continue
            result.append(name)
        return result
    finally:sftp.close()


def _launch_script(ssh,script,args,log_path):
    """Detach the Python worker with its interpreter, NOT via execve(.py).

    SFTP uploads do not preserve executable permission. The worker stays alive
    after SSH closes; a tiny startup log is kept locally on RVV Lab.
    """
    py=("import subprocess,sys,time;"
        "log=open(sys.argv[1],'ab',buffering=0);"
        "p=subprocess.Popen([sys.executable,*sys.argv[2:]],"
        "stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,"
        "start_new_session=True,close_fds=True);"
        "log.close();time.sleep(1);"
        "print('NIGHT_PID='+str(p.pid));"
        "sys.exit(0 if p.poll() is None else 8)")
    cmd='python3 -c '+shlex.quote(py)+' '+' '.join(shlex.quote(x) for x in [log_path,script,*args])
    return ssh.exec_text(cmd)


def launch(ssh,remote_name,*,runid,sourceid,jobs=2):
    validate_id(runid)
    if not SOURCE_RE.fullmatch(sourceid):raise ValueError('Invalid source ID')
    if runid in [x['id'] for x in remote_runs(ssh,remote_name)]:
        raise RuntimeError('Identifier already in use')
    if jobs not in (1,2):raise ValueError('Jobs 1 ou 2 uniquement')
    base=base_path(ssh,remote_name)
    sftp=ssh.client.open_sftp()
    try:
        home=base+'/night-runs';remote_runner=base+'/night-runner/rvv_night_runner.py'
        ssh.mkdir(home);ssh.mkdir(base+'/night-runner')
        ssh.mkdir(home+'/'+runid)
        if not WORKER.is_file():raise FileNotFoundError('Worker nocturne absent du Studio')
        sftp.put(str(WORKER),remote_runner,confirm=True)
        expected=hashlib.sha256(WORKER.read_bytes()).hexdigest()
        actual=ssh.exec_text('sha256sum '+shlex.quote(remote_runner)).strip().split()[0]
        if expected!=actual:raise RuntimeError('SHA256 worker distant incorrect')
        src=base+'/sources/'+sourceid
        run=home+'/'+runid
        out=_launch_script(ssh,remote_runner,['--source',src,'--workdir',run,'--hours','8','--jobs',str(jobs),'--core','0'],run+'/runner-startup.log')
        if 'NIGHT_PID=' not in out:raise RuntimeError('Detached launch failed: '+out)
        pid=int(out.rsplit('NIGHT_PID=',1)[1].split()[0])
        # Do not allow Studio to accidentally delete even a newly started run.
        with sftp.open(run+'/launcher.json','w') as f:
            f.write(json.dumps({'run_id':runid,'source_id':sourceid,'pid':pid,'worker_sha256':expected})+'\n')
        return {'run_id':runid,'source_id':sourceid,'pid':pid}
    finally:sftp.close()



def remote_runs(ssh,remote_name):
    home=base_path(ssh,remote_name)+'/night-runs'
    sftp=ssh.client.open_sftp()
    try:
        try:entries=sftp.listdir(home)
        except IOError:return []
        items=[]
        for name in sorted(entries,reverse=True):
            if not RUN_RE.fullmatch(name):continue
            path=home+'/'+name
            obj={'id':name,'state':'launch_incomplete'}
            try:
                with sftp.open(path+'/status.json','r') as f:
                    data=json.loads(f.read().decode('utf-8'))
                obj.update({key:data.get(key) for key in ('state','observations','current_candidate','last_update','disk_free_gib','stop_reason','campaign','budget_seconds','experiment_phase')})
            except (OSError,IOError,ValueError,TypeError):pass
            try:
                with sftp.open(path+'/launcher.json','r') as f:
                    launcher=json.loads(f.read().decode('utf-8'))
                if launcher.get('run_id') != name:raise ValueError('Launcher ID mismatch')
                if 'pid' in launcher:obj['pid']=launcher['pid']
                if not obj.get('campaign') and isinstance(launcher.get('campaign'),str):
                    obj['campaign']=launcher['campaign']
                if obj['state']=='launch_incomplete':obj['state']='starting'
            except (OSError,IOError,ValueError,KeyError):pass
            items.append(obj)
        return items
    finally:sftp.close()


def stop(ssh,remote_name,runid):
    validate_id(runid)
    base=base_path(ssh,remote_name)+'/night-runs/'+runid
    sftp=ssh.client.open_sftp()
    try:
        sftp.stat(base)
        with sftp.open(base+'/STOP','w') as f:f.write('Stop requested from Studio.\n')
    finally:sftp.close()


def verify_zip(data):
    if len(data)>MAX_ZIP:raise ValueError('Snapshot exceeds 32 MiB')
    if not zipfile.is_zipfile(io.BytesIO(data)):raise ValueError('Invalid snapshot ZIP')
    with zipfile.ZipFile(io.BytesIO(data),'r') as z:
        files=z.namelist()
        if len(files)!=len(set(files)) or 'MANIFEST.json' not in files:
            raise ValueError('Manifest missing or duplicate entries')
        manifest=json.loads(z.read('MANIFEST.json'))
        # The 8-hour and corrected 1-hour discovery workers each publish
        # 14 result files, with distinct report filenames. Keep explicit
        # allowlists and verify every size/hash; do not trust a manifest
        # to authorize arbitrary filenames.
        allow={'status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md',
               'failures.csv','metadata.json','corpus_manifest.json','trend_candidates.csv',
               'prequal_pairwise.csv','TRENDS.md','coverage_by_design.csv',
               'hypotheses_to_confirm.csv','EXPLORATION_8H.md','EXPLORATION_1H.md','VALIDATION_2H.md','composition_catalog.json','schedule.json','diagnostics.csv','EXPLORATION_91.md','EXPLORATION_92.md','EXPLORATION_93.md','controls93.csv','policy_candidates.json','build_provenance.json'}
        entries=manifest.get('files')
        if not isinstance(entries,list) or len(entries)>len(allow):
            raise ValueError('Invalid manifest file count')
        if len(files)>len(allow)+1:
            raise ValueError('Too many ZIP entries')
        extracted={}
        uncompressed=0
        for entry in entries:
            if not isinstance(entry,dict):raise ValueError('Invalid manifest entry')
            name=entry.get('name')
            if not isinstance(name,str) or name not in allow or name not in files or name in extracted:
                raise ValueError('Unexpected or duplicate file: '+str(name))
            file_info=z.getinfo(name)
            if file_info.is_dir() or file_info.file_size>MAX_ZIP:
                raise ValueError('File too large or not regular: '+name)
            uncompressed+=file_info.file_size
            if uncompressed>64*1024*1024:raise ValueError('Snapshot uncompressed budget exceeded')
            body=z.read(name)
            if not isinstance(entry.get('bytes'),int) or not isinstance(entry.get('sha256'),str):
                raise ValueError('Invalid manifest entry fields: '+name)
            if len(body)!=entry['bytes'] or hashlib.sha256(body).hexdigest()!=entry['sha256']:
                raise ValueError('Invalid SHA256: '+name)
            extracted[name]=body
        if set(files)!=(set(extracted)|{'MANIFEST.json'}):raise ValueError('Undeclared ZIP entries')
        return extracted


def sync(ssh,remote_name,runid,local_root):
    validate_id(runid)
    remote=base_path(ssh,remote_name)+'/night-runs/'+runid
    sftp=ssh.client.open_sftp()
    try:
        data=None
        for attempt in range(6):
            try:
                with sftp.open(remote+'/snapshot.sha256','r') as f:before=f.read().decode('ascii').strip()
                with sftp.open(remote+'/snapshot.zip','rb') as f:data=f.read(MAX_ZIP+1)
                with sftp.open(remote+'/snapshot.sha256','r') as f:expected=f.read().decode('ascii').strip()
                if before==expected and len(data)<=MAX_ZIP and hashlib.sha256(data).hexdigest()==expected:break
            except IOError:pass
            time.sleep(1)
        else:raise RuntimeError('Remote snapshot is missing or SHA256 does not match. Try again.')
        files=verify_zip(data)
    finally:sftp.close()
    folder=pathlib.Path(local_root).expanduser()/'NightRuns'/runid
    folder.mkdir(parents=True,exist_ok=True)
    # Copy fully validated bytes individually, never expose a partial write.
    for name,body in files.items():
        temp=folder/(name+'.tmp')
        with temp.open('wb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        os.replace(temp,folder/name)
    (folder/'SYNC_OK.txt').write_text('SHA256-verified snapshot: '+hashlib.sha256(data).hexdigest()+'\n',encoding='utf-8')
    return folder
