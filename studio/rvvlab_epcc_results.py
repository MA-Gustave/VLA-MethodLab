"""Read-only EPCC run discovery and explicit SHA256-checked results recovery.

Never submit a job, create a server directory, or infer success from the
existence of a timestamped run folder. Results are saved per verified run ID.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import zipfile

RUN_TYPES = {
    'test103': dict(pattern=re.compile(r'^test103-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                    directory='test103-epcc-runs', status='status103.json',
                    archive='test103_results.zip', test_id='test103-stage2-optimization',
                    required=('status103.json','REPORT_103.md'),
                    allowed=('status103.json','builds103.json','machine103.json','inputs103.json',
                             'corpus_manifest103.json','results103.csv','summary103.json','REPORT_103.md',
                             'studio103-build.log','studio103-cloudv.log','slurm103-exit.json','slurm103-runtime.log')),
    'test102': dict(pattern=re.compile(r'^test102-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                    directory='test102-epcc-runs', status='status102.json',
                    archive='test102_results.zip', test_id='test102-escape-stage',
                    required=('status102.json','REPORT_102.md'),
                    allowed=('status102.json','builds102.json','machine102.json','inputs102.json',
                             'corpus_manifest102.json','results102.csv','summary102.json','REPORT_102.md',
                             'studio102-build.log','studio102-cloudv.log','slurm102-exit.json','slurm102-runtime.log')),
    'test101': dict(pattern=re.compile(r'^test101-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test101-epcc-runs', status='status101.json',
                   archive='test101_results.zip', test_id='test101-dispatch-validation',
                   required=('status101.json','REPORT_101.md'),
                   allowed=('builds101.json','machine101.json','status101.json','results101.csv',
                            'summary101.json','REPORT_101.md','corpus_manifest101.json','inputs101.json',
                            'studio101-build.log','slurm101-exit.json','slurm101-runtime.log','studio101-cloudv.log')),
    'test100': dict(pattern=re.compile(r'^test100-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test100-epcc-runs', status='status100.json',
                   archive='test100_results.zip', test_id='test100-adaptive-public',
                   required=('status100.json','REPORT_100.md'),
                   allowed=('builds100.json','machine100.json','status100.json','results100.csv',
                            'summary100.json','REPORT_100.md','corpus_manifest100.json','inputs100.json',
                            'studio100-build.log','slurm100-exit.json','slurm100-runtime.log')),
    'test99': dict(pattern=re.compile(r'^test99-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test99-epcc-runs', status='status99.json',
                   archive='test99_results.zip', test_id='test99-public-8h',
                   required=('builds99.json','machine99.json','status99.json','results99.csv',
                             'summary99.json','REPORT_99.md','corpus_manifest99.json'),
                   allowed=('builds99.json','machine99.json','status99.json','results99.csv',
                            'summary99.json','REPORT_99.md','corpus_manifest99.json')),
    'test98': dict(pattern=re.compile(r'^test98-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test98-epcc-runs', status='status98.json',
                   archive='test98_results.zip', test_id='test98-real-corpus',
                   required=('builds98.json','machine98.json','status98.json','results98.csv',
                             'summary98.json','REPORT_98.md','corpus_manifest98.json'),
                   allowed=('builds98.json','machine98.json','status98.json','results98.csv',
                            'summary98.json','REPORT_98.md','corpus_manifest98.json')),
    'test94': dict(pattern=re.compile(r'^test94-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test94-runs', status='status94.json',
                   archive='test94_results.zip', test_id='machine-compare-94-1h',
                   required=('machine94.json','status94.json','results94.csv','summary94.json','REPORT_94.md'),
                   allowed=('builds.json','machine94.json','status94.json','results94.csv','summary94.json','REPORT_94.md')),
    'test97': dict(pattern=re.compile(r'^test97-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test97-epcc-runs', status='status97.json',
                   archive='test97_results.zip', test_id='test97-epcc-v5-3h',
                   required=('builds97.json','machine97.json','status97.json','results97.csv',
                             'summary97.json','REPORT_97.md','manifest97.json'),
                   allowed=('builds97.json','machine97.json','status97.json','results97.csv',
                            'summary97.json','REPORT_97.md','manifest97.json')),
    'test96': dict(pattern=re.compile(r'^test96-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
                   directory='test96-epcc-runs',status='status96.json',
                   archive='test96_results.zip',test_id='test96-epcc-8h',
                   required=('builds96.json','machine96.json','status96.json','results96.csv','summary96.json','REPORT_96.md','manifest96.json'),
                   allowed=('builds96.json','machine96.json','status96.json','results96.csv','summary96.json','REPORT_96.md','manifest96.json')),
}
MAX_ZIP_BYTES=512*1024*1024
MAX_EXTRACTED_BYTES=1024*1024*1024


def _read_json(sftp, path):
    try:
        with sftp.open(path, 'rb') as f:
            raw=f.read(65_537)
        if len(raw)>65_536:return {}
        obj=json.loads(raw.decode('utf-8') if isinstance(raw, bytes) else raw)
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError,UnicodeError,TypeError):return {}


def _listdir(sftp,path):
    try:return sftp.listdir(path)
    except OSError as ex:
        # Missing optional run folders are normal. Permissions and SSH errors
        # are not: propagate them rather than incorrectly claiming zero runs.
        if getattr(ex,'errno',None)==2 or 'no such file' in str(ex).lower():return []
        raise


def discover_epcc_runs(ssh, remote_name, *, limit=75):
    """Return only runs in the two known EPCC folders; no name heuristics."""
    base=ssh.base(remote_name)
    rows=[]
    with ssh.client.open_sftp() as sftp:
        for kind,cfg in RUN_TYPES.items():
            parent=base+'/'+cfg['directory']
            names=sorted((n for n in _listdir(sftp,parent) if cfg['pattern'].fullmatch(n)),reverse=True)[:limit]
            for name in names:
                path=parent+'/'+name
                status=_read_json(sftp,path+'/'+cfg['status'])
                packet=False
                try:packet=0<sftp.stat(path+'/'+cfg['archive']).st_size<=MAX_ZIP_BYTES
                except OSError:pass
                state=str(status.get('state') or '').lower()
                rows_count=status.get('rows',0)
                if not isinstance(rows_count,int) or isinstance(rows_count,bool) or rows_count<0:rows_count=0
                # A marker alone does not establish a completed experiment.
                if state=='completed' and (not packet or rows_count==0):state='unknown'
                if not state:state='unknown'
                proof=('Archive available on EPCC; status '+state if packet else
                       'No result archive; status '+state)
                rows.append({'id':name,'kind':kind,'test_id':cfg['test_id'],'state':state,
                             'rows':rows_count,'observations':rows_count,
                             'packet':packet,'proof':proof,'workdir':path,
                             'last_update':status.get('last_update_utc') or status.get('last_update'),
                             'started_utc':status.get('start_utc') or status.get('started_utc'),
                             'phase':status.get('phase') or '',
                             'reason':status.get('reason') or status.get('stop_reason') or ''})
    return sorted(rows,key=lambda x:x['id'],reverse=True)


def select_test_run(rows,kind):
    """Prefer latest available *packet*, otherwise latest attempt.

    The caller must still display the real state; an older packet does not
    make a newer failed run successful.
    """
    candidates=[row for row in rows if row['kind']==kind]
    if not candidates:return None
    return next((r for r in candidates if r['packet']),candidates[0])


def _sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def _check_zip(path, cfg):
    """Validate shape, contents and CRC before extracting any results."""
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(set(names))!=len(names) or not set(cfg['required']).issubset(names):
            raise ValueError('Incomplete archive or duplicate filenames')
        if not set(names).issubset(cfg['allowed']):
            raise ValueError('Archive contenant des fichiers inattendus')
        total=0
        for info in z.infolist():
            if info.is_dir() or info.file_size>MAX_EXTRACTED_BYTES:
                raise ValueError('Unsafe ZIP entry')
            total+=info.file_size
            if total>MAX_EXTRACTED_BYTES:raise ValueError('Extracted archive exceeds size limit')
        bad=z.testzip()
        if bad:raise ValueError('CRC ZIP invalide : '+bad)


def sync_epcc_run(ssh,remote_name,run_id,local_root):
    """Explicit EPCC result download. Never alters remote files.

    Verifies remote SHA256, optional server-side .sha256 marker, ZIP CRC,
    required files and bounded decompression. Writes SYNC_OK only at the end.
    """
    kind=next((name for name,cfg in RUN_TYPES.items() if cfg['pattern'].fullmatch(str(run_id))),None)
    if kind is None:raise ValueError('Unknown EPCC identifier : '+str(run_id))
    cfg=RUN_TYPES[kind]
    root=ssh.base(remote_name)+'/'+cfg['directory']+'/'+run_id
    remote=root+'/'+cfg['archive']
    target=Path(local_root).expanduser()/'TestRunner'/cfg['test_id']/('EPCC-'+run_id)
    target.mkdir(parents=True,exist_ok=True)
    archive=target/cfg['archive']
    part=target/(cfg['archive']+'.part')
    expected=''
    try:
        with ssh.client.open_sftp() as sftp:
            size=sftp.stat(remote).st_size
            if not 0<size<=MAX_ZIP_BYTES:raise ValueError('Archive absente, vide ou trop volumineuse')
            # The .sha256 marker is useful but optional for older campaigns.
            try:
                with sftp.open(remote.replace('.zip','.sha256'),'rb') as f:
                    content=f.read(512)
                value=(content.decode('ascii') if isinstance(content,bytes) else content).split()[0].lower()
                if re.fullmatch(r'[a-f0-9]{64}',value):expected=value
            except (OSError,UnicodeError,IndexError):pass
            sftp.get(remote,str(part))
        if part.stat().st_size!=size:raise RuntimeError('Transfert incomplet')
        got=_sha256(part)
        remote_hash=ssh.exec_text('sha256sum '+shlex.quote(remote)).strip().split()[0].lower()
        if not re.fullmatch(r'[0-9a-f]{64}',remote_hash) or remote_hash!=got:
            raise RuntimeError('EPCC SHA-256 does not match downloaded file')
        if expected and expected!=got:raise RuntimeError('Remote manifest SHA-256 mismatch')
        _check_zip(part,cfg)
        # Commit the fully verified archive first, then extract through bounded
        # per-file temp copies. Do not let ZIP paths dictate the destination.
        os.replace(part,archive)
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                tmp=target/(name+'.part')
                try:
                    with z.open(name) as src,tmp.open('wb') as dst:
                        while True:
                            chunk=src.read(1024*1024)
                            if not chunk:break
                            dst.write(chunk)
                    os.replace(tmp,target/name)
                finally:tmp.unlink(missing_ok=True)
        marker=target/'SYNC_OK.txt'
        tmp=target/'SYNC_OK.txt.part'
        tmp.write_text('SHA256-verified EPCC '+kind+' archive: '+got+'\nrun_id: '+run_id+'\n',encoding='utf8')
        os.replace(tmp,marker)
        return target
    finally:part.unlink(missing_ok=True)
