#!/usr/bin/env python3
"""Verify this release's file digests and paired 8h speedup statistics.

Usage: python verify.py
No third-party Python modules are required.
"""
import csv, hashlib, math, pathlib, statistics, json, sys
base=pathlib.Path(__file__).resolve().parent
rows={}
for line in (base/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
    if not line.strip(): continue
    expected,name=line.split('  ',1)
    got=hashlib.sha256((base/name).read_bytes()).hexdigest()
    if got!=expected:raise RuntimeError('SHA256 mismatch: '+name)
    print('SHA256 OK',name)
source=list(csv.DictReader((base/'observations.csv').open(encoding='utf-8',newline='')))
assert len(source)==6887, 'Incorrect observation count'
assert not list(csv.DictReader((base/'failures.csv').open(encoding='utf-8',newline=''))), 'Unexpected failures'
key=lambda r:(r['phase'],r['corpus'],r['parse_iterations'],r['trial'])
refs={key(r):r for r in source if r['variant']=='upstream_vls256'}
assert len(refs)==1722
measures={'dom_all':'dom_all_gbps','stage1':'stage1_gbps','stage2':'stage2_gbps'}
ratios={}
for r in source:
    ref=refs.get(key(r))
    if ref is None:continue
    for name,col in measures.items():
        x=float(r[col])/float(ref[col]);assert x>0 and math.isfinite(x)
        ratios.setdefault((r['variant'],name),[]).append(x)
for r in csv.DictReader((base/'ranking.csv').open(encoding='utf-8',newline='')):
    vals=ratios[(r['variant'],r['metric'])]
    calculated=math.exp(statistics.mean(math.log(x) for x in vals))
    median=statistics.median(vals)
    if len(vals)!=int(r['paired_n']) or abs(calculated-float(r['geomean_ratio']))>1e-6 or abs(median-float(r['median_ratio']))>1e-6:
        raise RuntimeError('Ranking mismatch '+r['variant']+'/'+r['metric'])
    print('RECOMPUTED',r['variant'],r['metric'],f'{calculated:.6f}x', 'n='+str(len(vals)))
for r in source:
    assert r['variant'] in {'upstream_vls256','E14_packed_disabled','E01_adaptive','sparse8_escape8_reference'}
events=sum(1 for _ in (base/'events.jsonl').open(encoding='utf-8'))
assert events==6896,(events,'events count')
print('PASS: 6887 observations; 6896 normalized events; 4 variants; 0 recorded failures; all ratios verified.')
