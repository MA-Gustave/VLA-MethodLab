"""Permanent, opt-in, shared JSON benchmark corpus for RVV-VLA MethodLab.

No remote benchmark is started here. The data is pinned, content-addressed,
validated both locally and on the target, and never bundled in engine snapshots.
Historic protocols (94-97) are unchanged until they explicitly request a corpus.
"""
from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid
import zipfile

LAB = Path(__file__).resolve().parents[1]
MANAGER = LAB / 'tools' / 'corpus98.py'


def manager():
    spec = importlib.util.spec_from_file_location('rvvlab_pinned_corpus', MANAGER)
    if spec is None or spec.loader is None:
        raise RuntimeError('Gestionnaire de corpus manquant: '+str(MANAGER))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def catalog():
    m = manager()
    return {'id':m.CORPUS_ID,'files':m.FILES,'commit':m.SOURCE_COMMIT,
            'source':m.SOURCE_URL,'description':'18 JSON publics épinglés (documents entiers)',
            'protocol':'rvvlab-corpus-v1'}


def cache_dir(lab=LAB):
    return Path(lab) / '.cache' / 'corpus-library'


def archive_path(lab=LAB):
    return cache_dir(lab) / (manager().CORPUS_ID + '.zip')


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as inp:
        for block in iter(lambda:inp.read(1024*1024), b''):h.update(block)
    return h.hexdigest()


def inspect_local(lab=LAB):
    path=archive_path(lab)
    out={'state':'absent','archive':str(path),'corpus_id':manager().CORPUS_ID}
    if not path.exists():return out
    try:
        m=manager().verify(path)
        out.update(state='verified',digest=_sha(path),files=m['files'],count=len(m['files']),
                   total_bytes=sum(x['bytes'] for x in m['files']))
    except (OSError,ValueError,KeyError,TypeError,RuntimeError,zipfile.BadZipFile) as exc:
        out.update(state='invalid',error=str(exc)[:450])
    return out


@contextmanager
def _local_lock(folder):
    """Serialize local preparation across Cloud-V and EPCC Studio processes."""
    folder.mkdir(parents=True,exist_ok=True)
    with (folder/'.prepare.lock').open('a+b') as fh:
        fh.seek(0);fh.write(b'\0');fh.flush();fh.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(fh.fileno(),msvcrt.LK_LOCK,1)
            try:yield
            finally:fh.seek(0);msvcrt.locking(fh.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(),fcntl.LOCK_EX)
            try:yield
            finally:fcntl.flock(fh.fileno(),fcntl.LOCK_UN)


def _reuse_legacy_archive(lab,cache):
    """Reuse the already-downloaded Test98 archive if it is byte-valid."""
    old=Path(lab)/'engine'/'.cache'/'test98-corpus'/(manager().CORPUS_ID+'.zip')
    dest=archive_path(lab)
    if dest.exists() or not old.is_file():return False
    manager().verify(old)
    temp=cache/(dest.name+'.migrating-'+uuid.uuid4().hex[:10])
    try:
        shutil.copyfile(old,temp)
        manager().verify(temp)
        os.replace(temp,dest)
        return True
    finally:temp.unlink(missing_ok=True)


def prepare_local(lab=LAB, log=None):
    """Fetch only pinned upstream documents; fail closed if offline. No fake corpus."""
    log=log or (lambda x:None)
    cache=cache_dir(lab)
    cache.mkdir(parents=True,exist_ok=True)
    with _local_lock(cache):
        local=inspect_local(lab)
        if local['state']=='verified':
            log('Corpus vérifié dans le cache commun ; aucun téléchargement.')
            return local
        if local['state']=='invalid':
            raise RuntimeError('Corpus local invalide : '+str(local.get('error'))+'. Ne sera pas écrasé automatiquement.')
        if _reuse_legacy_archive(lab,cache):
            log('Archive Test98 existante vérifiée et réutilisée sans Internet.')
        else:
            cmd=[sys.executable,str(MANAGER),'prepare','--cache',str(cache)]
            log('Préparation du corpus public épinglé ; cache partagé entre les tests…')
            p=subprocess.run(cmd,capture_output=True,text=True,timeout=1800)
            if p.returncode:
                raise RuntimeError('Téléchargement/validation impossible. '+(p.stderr or p.stdout)[-1800:])
        result=inspect_local(lab)
        if result['state']!='verified':raise RuntimeError('Corpus local non vérifié : '+str(result.get('error')))
        log('Corpus vérifié : '+str(result['count'])+' JSON ; '+result['digest'][:20]+'…')
        return result


def _q(x):return shlex.quote(str(x))


def remote_paths(ssh,remote_name,digest):
    cat=catalog();root=ssh.base(remote_name).rstrip('/')+'/corpora/shared/'+cat['id']+'/'+digest[:20]
    return {'root':root,'archive':root+'/'+cat['id']+'.zip',
            'manager':root+'/corpus98.py','data':root+'/data/'+cat['id'],
            'status':root+'/corpus-status.json'}


def _exists(sftp,path):
    try:return sftp.stat(path).st_size>0
    except OSError:return False


def remote_probe(ssh,remote_name,digest,*,deep=False):
    """Never claim a corpus is installed on the basis of a status flag alone."""
    p=remote_paths(ssh,remote_name,digest)
    with ssh.client.open_sftp() as sftp:
        if not _exists(sftp,p['status']):return {'state':'absent',**p}
        try:
            with sftp.open(p['status'],'r') as f:raw=f.read(16384)
            if isinstance(raw,bytes):raw=raw.decode('utf-8')
            meta=json.loads(raw)
        except (OSError,ValueError,UnicodeError,TypeError):return {'state':'invalid','reason':'Métadonnées distantes illisibles',**p}
        if meta.get('schema')!=1 or meta.get('corpus_id')!=catalog()['id'] or meta.get('sha256')!=digest or meta.get('root')!=p['data']:
            return {'state':'invalid','reason':'Manifeste distant incohérent',**p}
        if not _exists(sftp,p['archive']) or not _exists(sftp,p['data']+'/manifest.json'):
            return {'state':'incomplete','reason':'ZIP ou fichiers extraits absents',**p}
    # The status was written only after a successful extraction. A subsequent
    # on-disk modification is caught by checksum here, or deep member validation.
    reported=ssh.exec_text('sha256sum '+_q(p['archive'])).strip().split()[0]
    if reported!=digest:return {'state':'invalid','reason':'SHA-256 ZIP distant incorrect',**p}
    if deep:
        if not manager_cli_available(ssh,p):
            return {'state':'invalid','reason':'Vérificateur distant absent',**p}
        ssh.exec_text('python3 '+_q(p['manager'])+' extract '+_q(p['archive'])+' '+_q(p['root']+'/data'))
    return {'state':'verified','count':meta.get('count'),'digest':digest,**p}


def manager_cli_available(ssh,p):
    with ssh.client.open_sftp() as sftp:return _exists(sftp,p['manager'])


def _upload(ssh,source,target,digest):
    """Temporary name + SHA check before promotion, limited retry for SFTP drops."""
    candidate=target+'.partial-'+uuid.uuid4().hex[:12]
    try:
        for attempt in range(3):
            try:
                with ssh.client.open_sftp() as sftp:sftp.put(str(source),candidate,confirm=True)
                break
            except (OSError,EOFError,ConnectionError):
                if attempt==2:raise
        remote_sha=ssh.exec_text('sha256sum '+_q(candidate)).strip().split()[0]
        if remote_sha!=digest:raise RuntimeError('SFTP checksum mismatch: '+str(source))
        # Atomic rename inside a single directory. Never clobber an existing
        # validated blob with different bytes.
        ssh.exec_text('mv -f '+_q(candidate)+' '+_q(target))
    finally:
        try:ssh.exec_text('rm -f '+_q(candidate))
        except Exception:pass


def sync_remote(ssh,remote_name,lab=LAB,log=None):
    """Manually install the exact pinned corpus on the active target only."""
    log=log or (lambda x:None)
    local=inspect_local(lab)
    if local['state']!='verified':
        raise RuntimeError('Corpus local absent/invalide. Cliquez d’abord Préparer les 18 JSON.')
    digest=local['digest'];p=remote_paths(ssh,remote_name,digest)
    try:
        existing=remote_probe(ssh,remote_name,digest,deep=True)
        if existing['state']=='verified':
            log('Déjà synchronisé et vérifié sur ce serveur ; aucun transfert.')
            return existing
    except (OSError,RuntimeError):
        # Re-upload and reverify if the target has incomplete cached data.
        pass
    ssh.mkdir(p['root'])
    with ssh.client.open_sftp() as sftp:
        has_zip=_exists(sftp,p['archive'])
    if has_zip:
        present=ssh.exec_text('sha256sum '+_q(p['archive'])).strip().split()[0]
    else:present=''
    if present!=digest:
        log('Transfert SFTP du ZIP vérifié vers '+p['root']+'…')
        _upload(ssh,Path(local['archive']),p['archive'],digest)
    else:log('ZIP déjà présent, téléchargement évité.')
    manager_digest=_sha(MANAGER)
    with ssh.client.open_sftp() as sftp:
        has_manager=_exists(sftp,p['manager'])
    if has_manager:
        existing_mgr=ssh.exec_text('sha256sum '+_q(p['manager'])).strip().split()[0]
    else:existing_mgr=''
    if existing_mgr!=manager_digest:_upload(ssh,MANAGER,p['manager'],manager_digest)
    # Full remote syntax/hash validation and immutable extraction.
    ssh.exec_text('python3 '+_q(p['manager'])+' extract '+_q(p['archive'])+' '+_q(p['root']+'/data'))
    meta={'schema':1,'corpus_id':catalog()['id'],'sha256':digest,'count':local['count'],
          'root':p['data'],'verified_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    # SFTP temp+atomic rename, no extra shell packages required.
    temp=p['status']+'.partial-'+uuid.uuid4().hex[:12]
    try:
        with ssh.client.open_sftp() as sftp:
            with sftp.open(temp,'wb') as f:f.write((json.dumps(meta,sort_keys=True,indent=2)+'\n').encode('utf-8'))
        ssh.exec_text('mv -f '+_q(temp)+' '+_q(p['status']))
    finally:
        try:ssh.exec_text('rm -f '+_q(temp))
        except Exception:pass
    result=remote_probe(ssh,remote_name,digest,deep=True)
    if result['state']!='verified':raise RuntimeError('Corpus distant non validé: '+str(result))
    log('Corpus prêt sur serveur : '+p['data'])
    return result


def require_remote(ssh,remote_name,lab=LAB):
    """For any future test script: confirmed installed path, no implicit upload."""
    local=inspect_local(lab)
    if local['state']!='verified':raise RuntimeError('Préparez le corpus dans l’onglet Corpus JSON.')
    info=remote_probe(ssh,remote_name,local['digest'],deep=True)
    if info['state']!='verified':raise RuntimeError('Synchronisez le corpus dans l’onglet Corpus JSON.')
    return {'path':info['data'],'corpus_id':catalog()['id'],
            'archive_sha256':local['digest'],'file_count':local['count']}
