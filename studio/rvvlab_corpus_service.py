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
MANAGER = LAB / 'tools' / 'corpus98.py'  # Legacy Test98 API, preserve default
SUITES = {'performance': MANAGER, 'conformance': LAB / 'tools' / 'corpus_jsontestsuite.py',
          'stress': LAB / 'tools' / 'corpus_rvv_stress.py'}
SUITE_LABELS = {'performance':'Performance · 18 JSON', 'conformance':'Conformance · JSONTestSuite',
                'stress':'Stress RVV · 90 JSON'}

def _check_suite(suite):
    if suite not in SUITES: raise ValueError('Unknown corpus suite: '+str(suite))
    return SUITES[suite]


def manager(suite='performance'):
    path = _check_suite(suite)
    spec = importlib.util.spec_from_file_location('rvvlab_pinned_corpus_'+suite, path)
    if spec is None or spec.loader is None:
        raise RuntimeError('Corpus manager not found: '+str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def catalog(suite='performance'):
    m = manager(suite)
    descriptions={'performance':'18 public performance JSON files (simdjson-data)',
                  'conformance':'JSONTestSuite: y_/n_/i_ parsing cases and transforms, bytes preserved',
                  'stress':'90 deterministic RVV stress JSON files, sizes 2–16 KiB'}
    return {'id':m.CORPUS_ID,'files':m.FILES,'commit':m.SOURCE_COMMIT,
            'source':m.SOURCE_URL,'description':descriptions[suite],
            'protocol':'rvvlab-corpus-v1','suite':suite}

def catalogs():
    return {suite: catalog(suite) for suite in SUITES}


def cache_dir(lab=LAB):
    return Path(lab) / '.cache' / 'corpus-library'


def archive_path(lab=LAB, suite='performance'):
    return cache_dir(lab) / (manager(suite).CORPUS_ID + '.zip')


def _sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as inp:
        for block in iter(lambda:inp.read(1024*1024), b''):h.update(block)
    return h.hexdigest()


def inspect_local(lab=LAB, suite='performance'):
    path=archive_path(lab,suite)
    out={'state':'absent','archive':str(path),'corpus_id':manager(suite).CORPUS_ID,'suite':suite}
    if not path.exists():return out
    try:
        m=manager(suite).verify(path)
        out.update(state='verified',digest=_sha(path),files=m['files'],count=len(m['files']),
                   total_bytes=sum(x['bytes'] for x in m['files']),
                   counts={label: sum(rec.get('expected')==label for rec in m['files']) for label in ('accept','reject','implementation','transform')})
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


def prepare_local(lab=LAB, log=None, suite='performance'):
    """Prepare the pinned suite, with a durable diagnostic log on every attempt.

    The log is local to the Lab cache and is not uploaded with benchmark data.
    No fake fixtures are substituted for a failed GitHub download.
    """
    cache=cache_dir(lab)
    cache.mkdir(parents=True,exist_ok=True)
    _check_suite(suite)
    diagnostic=cache/('preparation-'+suite+'.log')

    def report(message):
        message=str(message)
        stamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        with diagnostic.open('a',encoding='utf-8') as dest:
            dest.write('['+stamp+'] '+message+'\n')
        if log is not None:log(message)

    report('Preparation started: '+suite+'; cache='+str(cache))
    try:
        with _local_lock(cache):
            local=inspect_local(lab,suite)
            if local['state']=='verified':
                report('Existing archive verified; no network operation needed.')
                return local
            if local['state']=='invalid':
                raise RuntimeError('Invalid local corpus: '+str(local.get('error'))+'. Will not overwrite automatically.')
            if suite=='performance' and _reuse_legacy_archive(lab,cache):
                report('Existing Test98 archive verified and reused offline.')
            else:
                cmd=[sys.executable,str(_check_suite(suite)),'prepare','--cache',str(cache)]
                report('Starting corpus manager: '+_check_suite(suite).name)
                report('Downloading pinned revision if the cache is missing (this may take several minutes)…')
                try:
                    p=subprocess.run(cmd,capture_output=True,text=True,timeout=1800)
                except subprocess.TimeoutExpired as exc:
                    raise RuntimeError('Corpus preparation timed out after 30 minutes.') from exc
                if p.returncode:
                    output=(p.stderr or p.stdout or 'No manager output').strip()
                    report('Corpus manager failed (exit code '+str(p.returncode)+') : '+output[-4500:])
                    raise RuntimeError('Download or validation failed: '+output[-1100:])
                report('Corpus manager completed: '+(p.stdout or 'OK').strip()[-1000:])
            result=inspect_local(lab,suite)
            if result['state']!='verified':
                raise RuntimeError('Local corpus not verified: '+str(result.get('error','archive missing after preparation')))
            report('SUCCESS: '+str(result['count'])+' files verified; SHA-256='+result['digest'])
            return result
    except Exception as exc:
        report('FAILURE: '+type(exc).__name__+': '+str(exc)[:1800])
        raise RuntimeError(str(exc)[:850]+' | Log: '+str(diagnostic)) from exc


def _q(x):return shlex.quote(str(x))


def remote_paths(ssh,remote_name,digest,suite='performance'):
    cat=catalog(suite);root=ssh.base(remote_name).rstrip('/')+'/corpora/shared/'+cat['id']+'/'+digest[:20]
    return {'root':root,'archive':root+'/'+cat['id']+'.zip',
            'manager':root+'/'+_check_suite(suite).name,'data':root+'/data/'+cat['id'],
            'status':root+'/corpus-status.json'}


def _exists(sftp,path):
    try:return sftp.stat(path).st_size>0
    except OSError:return False


def remote_probe(ssh,remote_name,digest,*,deep=False,suite='performance'):
    """Never claim a corpus is installed on the basis of a status flag alone."""
    p=remote_paths(ssh,remote_name,digest,suite)
    with ssh.client.open_sftp() as sftp:
        if not _exists(sftp,p['status']):return {'state':'absent',**p}
        try:
            with sftp.open(p['status'],'r') as f:raw=f.read(16384)
            if isinstance(raw,bytes):raw=raw.decode('utf-8')
            meta=json.loads(raw)
        except (OSError,ValueError,UnicodeError,TypeError):return {'state':'invalid','reason':'Unreadable remote metadata',**p}
        if meta.get('schema')!=1 or meta.get('corpus_id')!=catalog(suite)['id'] or meta.get('sha256')!=digest or meta.get('root')!=p['data']:
            return {'state':'invalid','reason':'Remote manifest mismatch',**p}
        if not _exists(sftp,p['archive']) or not _exists(sftp,p['data']+'/manifest.json'):
            return {'state':'incomplete','reason':'ZIP or extracted files missing',**p}
    # The status was written only after a successful extraction. A subsequent
    # on-disk modification is caught by checksum here, or deep member validation.
    reported=ssh.exec_text('sha256sum '+_q(p['archive'])).strip().split()[0]
    if reported!=digest:return {'state':'invalid','reason':'Remote ZIP SHA-256 mismatch',**p}
    if deep:
        if not manager_cli_available(ssh,p):
            return {'state':'invalid','reason':'Remote verifier missing',**p}
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


def sync_remote(ssh,remote_name,lab=LAB,log=None,suite='performance'):
    """Manually install the exact pinned corpus on the active target only."""
    log=log or (lambda x:None)
    local=inspect_local(lab,suite)
    if local['state']!='verified':
        raise RuntimeError('Local corpus missing/invalid. Run Prepare / Verify JSON first.')
    digest=local['digest'];p=remote_paths(ssh,remote_name,digest,suite)
    try:
        existing=remote_probe(ssh,remote_name,digest,deep=True,suite=suite)
        if existing['state']=='verified':
            log('Already synced and verified on this server; no upload needed.')
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
        log('Uploading verified ZIP by SFTP to '+p['root']+'…')
        _upload(ssh,Path(local['archive']),p['archive'],digest)
    else:log('ZIP already present; upload skipped.')
    manager_path=_check_suite(suite)
    manager_digest=_sha(manager_path)
    with ssh.client.open_sftp() as sftp:
        has_manager=_exists(sftp,p['manager'])
    if has_manager:
        existing_mgr=ssh.exec_text('sha256sum '+_q(p['manager'])).strip().split()[0]
    else:existing_mgr=''
    if existing_mgr!=manager_digest:_upload(ssh,manager_path,p['manager'],manager_digest)
    # Full remote syntax/hash validation and immutable extraction.
    ssh.exec_text('python3 '+_q(p['manager'])+' extract '+_q(p['archive'])+' '+_q(p['root']+'/data'))
    meta={'schema':1,'corpus_id':catalog(suite)['id'],'sha256':digest,'count':local['count'],
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
    result=remote_probe(ssh,remote_name,digest,deep=True,suite=suite)
    if result['state']!='verified':raise RuntimeError('Remote corpus not validated: '+str(result))
    log('Corpus ready on server: '+p['data'])
    return result


def require_remote(ssh,remote_name,lab=LAB,suite='performance'):
    """For any future test script: confirmed installed path, no implicit upload."""
    local=inspect_local(lab,suite)
    if local['state']!='verified':raise RuntimeError('Prepare the corpus in the JSON Corpus tab.')
    info=remote_probe(ssh,remote_name,local['digest'],deep=True,suite=suite)
    if info['state']!='verified':raise RuntimeError('Sync the corpus from the JSON Corpus tab.')
    return {'path':info['data'],'corpus_id':catalog(suite)['id'],'suite':suite,
            'archive_sha256':local['digest'],'file_count':local['count']}
