#!/usr/bin/env python3
"""Offline integrity and semantic checks for the published 3h experiment. stdlib only."""
import csv
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'results'/'runs'/'2026-10-10-engine-library-3h'

def die(s): raise SystemExit('FAIL: '+s)

def main():
    m=json.loads((D/'manifest.json').read_text(encoding='utf-8'))
    for name,meta in m['files'].items():
        p=D/name
        if not p.is_file():die('missing '+name)
        b=p.read_bytes()
        if hashlib.sha256(b).hexdigest()!=meta['sha256'] or len(b)!=meta['bytes']:die('SHA mismatch '+name)
    rows=list(csv.DictReader((D/'observations.csv').open(encoding='utf-8',newline='')))
    if len(rows)!=m['measurements'] or len(rows)!=2469:die('observation count')
    if len({r['variant'] for r in rows})!=17:die('variant coverage')
    if any(r['stage1_gbps'] or r['stage2_gbps'] for r in rows):die('fabricated stage metrics')
    keys=lambda r:(r['phase'],r['corpus_id'],r['parse_iterations'],r['trial'])
    control={keys(r):float(r['dom_gbps']) for r in rows if r['variant']=='upstream_vls256'}
    with (D/'ranking.csv').open(encoding='utf-8',newline='') as f:ranking={r['variant']:r for r in csv.DictReader(f)}
    for name in ['E14_packed_disabled','E01_adaptive','sparse8_escape8_reference']:
        matched=[(float(r['dom_gbps']),control[keys(r)]) for r in rows if r['variant']==name and keys(r) in control]
        gm=math.exp(sum(math.log(a/b) for a,b in matched)/len(matched))
        claimed=float(ranking[name]['geomean_ratio'])
        if abs(gm-claimed)>0.00002:die(f'paired ratio mismatch {name}: {gm}, {claimed}')
        if len(matched)!=int(ranking[name]['paired_n']):die('pair count mismatch '+name)
    events=[json.loads(l) for l in (D/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    if len(events)!=1+17+17+2469+1:die('event count')
    if sum(e['kind']=='measurement.dom' for e in events)!=2469:die('events measurements')
    if any(e.get('schema')!='rvv-vla.event.v1' or e.get('run_id')!=m['run_id'] for e in events):die('schema/run id')
    if any(e['result']!='PASS' for e in events if e['kind'] in ('build.result','correctness.smoke')):die('pass coverage')
    for n in ['status.json','metadata.json','launch.json','.env','night_runner.zip']:
        if (D/n).exists():die('unredacted private raw packet: '+n)
    print(f'PASS: {len(rows)} measurements, 17 native modes, {len(events)} normalized events, SHA256 verified')
    print('E14 vs VLS256: {:.3f}x; E01: {:.3f}x'.format(float(ranking['E14_packed_disabled']['geomean_ratio']),float(ranking['E01_adaptive']['geomean_ratio'])))

if __name__=='__main__':main()
