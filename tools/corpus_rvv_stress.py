#!/usr/bin/env python3
"""Deterministic, self-generated valid JSON RVV boundary/stress fixtures.

Not a public standard; separated from standard performance and JSONTestSuite.
"""
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
import tempfile,zipfile
CORPUS_ID='rvv-stress-boundaries-v1'
SOURCE_URL='methodlab://generated/rvv-stress-boundaries-v1'
SOURCE_COMMIT='deterministic-v1'
SIZES=(2047,2048,2049,4095,4096,4097,6143,6144,6145,8191,8192,8193,16383,16384,16385)
KINDS=('ascii','dense','escaped','utf8','unicode_escape','nested')
FILES=tuple(f'{k}-{size}.json' for k in KINDS for size in SIZES)
MAX_SIZE=64*1024*1024

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as inp:
        for part in iter(lambda:inp.read(1024*1024),b''):h.update(part)
    return h.hexdigest()

def _json_bytes(kind,size):
    patterns={
        'ascii':'ABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789',
        'dense':',{}[]:"foobar":123456789,true,false,null',
        'escaped':r'\\ \n \t \\ / " abc',
        'utf8':'éèà漢字🙂 café π',
        'unicode_escape':'éà漢字 €',
        'nested':'[1,{"x":[true,false,null]},2]',
    }
    content=patterns[kind]*max(1,(size//(len(patterns[kind].encode('utf8'))*5)))
    if kind=='nested':value={'deep':[[{'v':content}]]}
    else:value=content
    obj={'value':value,'pad':''}
    def dump(x):return json.dumps(x,ensure_ascii=(kind=='unicode_escape'),separators=(',',':')).encode('utf8')
    start=dump(obj)
    if len(start)>size:raise ValueError(f'Base JSON exceeds requested size: {kind} {size}')
    obj['pad']='a'*(size-len(start))
    out=dump(obj)
    if len(out)!=size:raise ValueError('Length mismatch')
    json.loads(out)
    return out

def _write(z,name,blob):
    info=zipfile.ZipInfo(name,date_time=(1980,1,1,0,0,0))
    info.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(info,blob)

def _manifest():
    records=[]
    for k in KINDS:
        for s in SIZES:
            b=_json_bytes(k,s)
            records.append({'name':f'{k}-{s}.json','bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'expected':'accept','family':k,'target_bytes':s})
    return {'schema':1,'corpus_id':CORPUS_ID,'source_url':SOURCE_URL,'upstream_commit':SOURCE_COMMIT,
            'files':records,'selection':'Deterministic RVV boundary probes, not standardized third-party benchmark data'}

def verify(path):
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=MAX_SIZE:raise ValueError('Invalid stress ZIP')
    with zipfile.ZipFile(path) as z:
        manifest=json.loads(z.read('manifest.json'))
        expected=_manifest()
        if manifest!=expected:raise ValueError('Stress manifest differs from deterministic reference')
        names={'manifest.json'}|{'files/'+f for f in FILES}
        if set(z.namelist())!=names or len(z.namelist())!=len(names):raise ValueError('Unexpected members')
        for item in expected['files']:
            b=z.read('files/'+item['name'])
            if len(b)!=item['bytes'] or hashlib.sha256(b).hexdigest()!=item['sha256']:raise ValueError('Stress fixture checksum mismatch')
            json.loads(b)
    return manifest

def prepare(cache):
    path=Path(cache);path.mkdir(parents=True,exist_ok=True)
    final=path/(CORPUS_ID+'.zip')
    if final.exists():verify(final)
    else:
        tmp=path/(final.name+'.partial-'+os.urandom(4).hex())
        try:
            with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
                _write(z,'manifest.json',json.dumps(_manifest(),sort_keys=True,indent=2)+'\n')
                for k in KINDS:
                    for s in SIZES:_write(z,'files/'+f'{k}-{s}.json',_json_bytes(k,s))
            verify(tmp);os.replace(tmp,final)
        finally:tmp.unlink(missing_ok=True)
    print(json.dumps({'archive':str(final),'sha256':sha(final),'files':len(FILES)}))

def extract(archive,destination):
    m=verify(archive);dest=Path(destination);root=dest/CORPUS_ID
    if root.exists():
        if not (root/'manifest.json').exists() or json.loads((root/'manifest.json').read_text('utf8'))!=m:raise ValueError('Existing stress corpus differs')
        for r in m['files']:
            p=root/'files'/r['name']
            if not p.is_file() or sha(p)!=r['sha256']:raise ValueError('Tampered stress fixture: '+r['name'])
        print(str(root));return
    dest.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='stress-',dir=dest) as tmp:
        stage=Path(tmp)/CORPUS_ID;(stage/'files').mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:
            (stage/'manifest.json').write_bytes(z.read('manifest.json'))
            for name in FILES:(stage/'files'/name).write_bytes(z.read('files/'+name))
        stage.rename(root)
    print(str(root))

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='cmd',required=True)
    subs.add_parser('prepare').add_argument('--cache',required=True)
    subs.add_parser('verify').add_argument('archive')
    e=subs.add_parser('extract');e.add_argument('archive');e.add_argument('destination')
    args=p.parse_args()
    if args.cmd=='prepare':prepare(args.cache)
    elif args.cmd=='verify':print(json.dumps({'sha256':sha(args.archive),'manifest':verify(args.archive)}))
    else:extract(args.archive,args.destination)
if __name__=='__main__':main()
