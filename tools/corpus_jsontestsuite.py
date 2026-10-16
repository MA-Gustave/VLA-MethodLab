#!/usr/bin/env python3
"""Immutable, byte-exact RFC 8259 JSONTestSuite corpus for MethodLab.

Do not parse upstream files with json.loads: intentionally invalid JSON and
invalid UTF-8 are the POINT of this test suite. Prefix classes: y,n,i.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import urllib.request
import zipfile

SOURCE_URL = 'https://github.com/nst/JSONTestSuite'
SOURCE_COMMIT = '1ef36fa01286573e846ac449e8683f8833c5b26a'
CORPUS_ID = 'jsontestsuite-rfc8259-'+SOURCE_COMMIT[:12]
FILES = ()  # Variable upstream collection; archive manifest enumerates exact contents.
MAX_DOWNLOAD = 256*1024*1024  # Upstream GitHub snapshot includes many parser binaries; only JSON files are retained.
DOWNLOAD_SPOOL_MEMORY = 8*1024*1024
MAX_ZIP = 48*1024*1024
MAX_TOTAL = 32*1024*1024
MAX_FILE = 2*1024*1024
MANIFEST_MAX = 1*1024*1024

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def _dumps(data):
    return (json.dumps(data,sort_keys=True,ensure_ascii=False,indent=2)+'\n').encode('utf-8')

def _safe(name):
    p=PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or len(p.parts)!=2:
        raise ValueError('Unsafe corpus member path: '+name)
    if p.parts[0] not in ('test_parsing','test_transform') or not re.fullmatch(r'[A-Za-z0-9_+.,#-]+\.json',p.parts[1]):
        raise ValueError('Unexpected fixture path: '+name)
    if p.parts[0]=='test_parsing' and not p.parts[1].startswith(('y_','n_','i_')):
        raise ValueError('Fixture missing y/n/i class: '+name)
    return p

def _label(name):
    if name.startswith('test_transform/'):return 'transform'
    return {'y':'accept','n':'reject','i':'implementation'}[PurePosixPath(name).name[0]]

def _members(manifest):
    if not isinstance(manifest,dict) or manifest.get('schema')!=1 or manifest.get('corpus_id')!=CORPUS_ID or manifest.get('source_url')!=SOURCE_URL or manifest.get('upstream_commit')!=SOURCE_COMMIT:
        raise ValueError('Corpus provenance mismatch')
    files=manifest.get('files')
    if not isinstance(files,list) or len(files)<200 or len(files)>2000:raise ValueError('Unexpected JSONTestSuite selection size')
    names=[];total=0;counts={'accept':0,'reject':0,'implementation':0,'transform':0}
    for rec in files:
        if not isinstance(rec,dict) or set(('name','bytes','sha256','expected'))-rec.keys():raise ValueError('Malformed member manifest')
        name=rec['name'];_safe(name)
        if rec['expected']!=_label(name):raise ValueError('Wrong class: '+name)
        size=rec['bytes'];hashval=rec['sha256']
        if not isinstance(size,int) or isinstance(size,bool) or size<0 or size>MAX_FILE:raise ValueError('Size cap exceeded')
        if not isinstance(hashval,str) or not re.fullmatch(r'[a-f0-9]{64}',hashval):raise ValueError('Invalid hash')
        names.append(name);counts[rec['expected']]+=1;total+=size
        if total>MAX_TOTAL:raise ValueError('Total corpus size cap exceeded')
    if names!=sorted(set(names)) or min(counts['accept'],counts['reject'],counts['implementation'])==0:
        raise ValueError('Missing classes, unsorted/duplicate members')
    return files,counts

def verify(archive):
    p=Path(archive)
    if not p.is_file() or not 0<p.stat().st_size<=MAX_ZIP:raise ValueError('Archive missing/oversize')
    with zipfile.ZipFile(p) as z:
        if z.getinfo('manifest.json').file_size>MANIFEST_MAX:raise ValueError('Oversize manifest')
        m=json.loads(z.read('manifest.json'))
        recs,counts=_members(m)
        expect={'manifest.json'}|{'files/'+r['name'] for r in recs}
        if len(z.namelist())!=len(expect) or set(z.namelist())!=expect:raise ValueError('Unexpected ZIP entries')
        for rec in recs:
            name='files/'+rec['name'];info=z.getinfo(name)
            if info.file_size!=rec['bytes']:raise ValueError('Member declared size mismatch: '+name)
            blob=z.read(name)
            if hashlib.sha256(blob).hexdigest()!=rec['sha256']:raise ValueError('Member SHA mismatch: '+name)
        if z.testzip():raise ValueError('Corrupted ZIP CRC')
    return m

def _download_pinned_archive():
    """Bounded streaming download. Large upstream ZIP never lives fully in RAM.

    GitHub's *whole-repository* archive contains parsers, results and binaries
    not needed by Method Lab. The previous 48 MiB download limit rejected the
    real pinned snapshot before _fetch_records could select the JSON fixtures.
    """
    url='https://codeload.github.com/nst/JSONTestSuite/zip/'+SOURCE_COMMIT
    req=urllib.request.Request(url,headers={'User-Agent':'VLA-MethodLab-Corpus/2.1','Accept':'application/zip'})
    tmp=tempfile.SpooledTemporaryFile(max_size=DOWNLOAD_SPOOL_MEMORY,mode='w+b')
    total=0
    try:
        with urllib.request.urlopen(req,timeout=90) as response:
            announced=response.headers.get('Content-Length')
            if announced:
                try: announced_bytes=int(announced)
                except ValueError: announced_bytes=None
                if announced_bytes is not None and announced_bytes>MAX_DOWNLOAD:
                    raise ValueError(f'Upstream ZIP announced {announced_bytes} bytes; security cap {MAX_DOWNLOAD} bytes')
            while True:
                chunk=response.read(1024*1024)
                if not chunk:break
                total+=len(chunk)
                if total>MAX_DOWNLOAD:
                    raise ValueError(f'Upstream ZIP exceeds safety cap {MAX_DOWNLOAD} bytes (read {total})')
                tmp.write(chunk)
        if total==0:raise ValueError('Upstream ZIP download is empty')
        tmp.seek(0)
        return tmp
    except Exception:
        tmp.close()
        raise

def _fetch_records(data):
    prefix='JSONTestSuite-'+SOURCE_COMMIT+'/'
    entries={};total=0
    # Accept byte buffers in offline tests, and file-like streams in production.
    source=io.BytesIO(data) if isinstance(data,(bytes,bytearray)) else data
    with zipfile.ZipFile(source) as z:
        for info in z.infolist():
            if info.is_dir():continue
            if not info.filename.startswith(prefix):raise ValueError('Unexpected upstream archive prefix')
            relative=info.filename[len(prefix):]
            if not (relative.startswith('test_parsing/') or relative.startswith('test_transform/')):continue
            if not relative.endswith('.json'):continue
            _safe(relative)
            if info.file_size>MAX_FILE:raise ValueError('Oversize upstream fixture')
            if relative in entries:raise ValueError('Duplicate fixture')
            content=z.read(info)
            total+=len(content)
            if total>MAX_TOTAL:raise ValueError('Total upstream size cap exceeded')
            entries[relative]=content
    records=[{'name':name,'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest(),'expected':_label(name)} for name,content in sorted(entries.items())]
    _members({'schema':1,'corpus_id':CORPUS_ID,'upstream_commit':SOURCE_COMMIT,'source_url':SOURCE_URL,'files':records})
    return records,entries

def _write(z,name,blob):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(info,blob)

def prepare(cache):
    cache=Path(cache).resolve();cache.mkdir(parents=True,exist_ok=True)
    target=cache/(CORPUS_ID+'.zip')
    if target.exists():
        meta=verify(target)
        print(json.dumps({'archive':str(target),'count':len(meta['files']),'sha256':sha(target),'cached':True}));return
    upstream=_download_pinned_archive()
    try:
        records,entries=_fetch_records(upstream)
    finally:
        if hasattr(upstream,'close'):upstream.close()
    manifest={'schema':1,'corpus_id':CORPUS_ID,'source_url':SOURCE_URL,'upstream_commit':SOURCE_COMMIT,'files':records,
              'selection':'Exact upstream test_parsing and test_transform *.json; invalid UTF8 preserved, expected labels only from prefixes',
              'license_notice':'Original project: nst/JSONTestSuite. Upstream license and attribution apply.'}
    tmp=cache/(target.name+'.partial-'+os.urandom(4).hex())
    try:
        with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            _write(z,'manifest.json',_dumps(manifest))
            for rec in records:_write(z,'files/'+rec['name'],entries[rec['name']])
        verify(tmp)
        os.replace(tmp,target)
    finally:tmp.unlink(missing_ok=True)
    print(json.dumps({'archive':str(target),'count':len(records),'sha256':sha(target),'cached':False}))

def extract(archive,destination):
    manifest=verify(archive)
    target=Path(destination).resolve();root=target/CORPUS_ID
    if root.exists():
        file=root/'manifest.json'
        if not file.is_file() or json.loads(file.read_text('utf-8'))!=manifest:raise ValueError('Existing corpus manifest mismatch')
        for rec in manifest['files']:
            p=root/'files'/rec['name']
            if not p.is_file() or p.stat().st_size!=rec['bytes'] or sha(p)!=rec['sha256']:
                raise ValueError('Installed corpus tampered with: '+str(p))
        print(str(root));return
    target.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='jsonsuite-',dir=target) as tmp:
        staging=Path(tmp)/CORPUS_ID
        with zipfile.ZipFile(archive) as z:
            for rec in manifest['files']:
                out=staging/'files'/rec['name'];out.parent.mkdir(parents=True,exist_ok=True)
                out.write_bytes(z.read('files/'+rec['name']))
            (staging/'manifest.json').write_bytes(z.read('manifest.json'))
        staging.rename(root)
    print(str(root))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='action',required=True)
    sub.add_parser('prepare').add_argument('--cache',required=True)
    sub.add_parser('verify').add_argument('archive')
    e=sub.add_parser('extract');e.add_argument('archive');e.add_argument('destination')
    a=p.parse_args()
    if a.action=='prepare':prepare(a.cache)
    elif a.action=='verify':print(json.dumps({'manifest':verify(a.archive),'sha256':sha(a.archive)}))
    else:extract(a.archive,a.destination)
if __name__=='__main__':main()
