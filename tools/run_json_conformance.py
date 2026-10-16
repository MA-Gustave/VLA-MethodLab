#!/usr/bin/env python3
"""Run JSONTestSuite conformance using an external parser-validator executable.

Exit-code contract: 0=accepted, 1=rejected, >1=crash/operational error.
Invocations are not shell-interpreted. The i_ fixtures are NOT scored.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,subprocess,sys
from pathlib import Path

def _sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run(corpus,command,out,timeout=5,include_transform=False):
    root=Path(corpus).resolve();manifest_path=root/'manifest.json'
    from importlib.util import spec_from_file_location,module_from_spec
    manager=root.parent.parent.parent/'corpus_jsontestsuite.py'
    # No external dependency: validate manifest and every extracted file in place.
    manifest=json.loads(manifest_path.read_text('utf-8'))
    if manifest.get('corpus_id','').startswith('jsontestsuite-rfc8259-') is False:
        raise ValueError('Not a JSONTestSuite corpus')
    rows=[];counts={'PASS':0,'FAIL':0,'UNSCORED':0,'CRASH':0,'TIMEOUT':0}
    for rec in manifest['files']:
        name=rec['name'];expected=rec['expected']
        if expected=='transform' and not include_transform:continue
        path=(root/'files'/name).resolve()
        if not path.is_relative_to((root/'files').resolve()):raise ValueError('Unexpected manifest path')
        if not path.is_file() or path.stat().st_size!=rec['bytes'] or _sha(path)!=rec['sha256']:
            raise ValueError('Fixture checksum mismatch: '+name)
        args=[arg.replace('{file}',str(path)) for arg in command]
        if not any('{file}' in item for item in command):args.append(str(path))
        try:
            p=subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=timeout)
            if p.returncode==0:actual='accept'
            elif p.returncode==1:actual='reject'
            else:actual='crash'
        except subprocess.TimeoutExpired:actual='timeout'
        if actual=='crash':result='CRASH'
        elif actual=='timeout':result='TIMEOUT'
        elif expected in ('implementation','transform'):result='UNSCORED'
        else:result='PASS' if actual==expected else 'FAIL'
        counts[result]+=1
        rows.append({'fixture':name,'expected':expected,'actual':actual,'result':result})
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    with (out/'conformance_results.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=['fixture','expected','actual','result']);writer.writeheader();writer.writerows(rows)
    summary={'schema':1,'suite':manifest['corpus_id'],'upstream_commit':manifest['upstream_commit'],
             'timestamp_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
             'counts':counts,'scored':counts['PASS']+counts['FAIL']+counts['CRASH']+counts['TIMEOUT'],
             'command':command,'timeout_seconds':timeout,'fixtures':len(rows),
             'note':'i_ = non normative; n_ must reject; y_ must accept; crashes/timeouts never pass.'}
    (out/'conformance_summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    return summary

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--corpus',required=True,help='Extracted JSONTestSuite directory containing manifest.json')
    p.add_argument('--output',required=True)
    p.add_argument('--timeout',type=float,default=5.0)
    p.add_argument('--include-transform',action='store_true')
    p.add_argument('command',nargs=argparse.REMAINDER,help='Parser command after --; use {file} to pass filename')
    a=p.parse_args()
    cmd=a.command[1:] if a.command[:1]==['--'] else a.command
    if not cmd or not (0.05<=a.timeout<=60):p.error('Valid --timeout and parser command are required')
    summary=run(a.corpus,cmd,a.output,a.timeout,a.include_transform)
    sys.exit(1 if summary['counts']['FAIL'] or summary['counts']['CRASH'] or summary['counts']['TIMEOUT'] else 0)
if __name__=='__main__':main()
