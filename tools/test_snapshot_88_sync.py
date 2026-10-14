#!/usr/bin/env python3
"""Offline tests for legacy and 8h expanded, SHA256-verified snapshots."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'orchestrator'))
from rvvlab_night import verify_zip

LEGACY=('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json')
EXTENDED=LEGACY+('corpus_manifest.json','trend_candidates.csv','prequal_pairwise.csv','TRENDS.md','coverage_by_design.csv','hypotheses_to_confirm.csv','EXPLORATION_8H.md')

def snapshot(names,*,tamper=False,extra=False):
    raw=io.BytesIO();manifest={'schema':1,'files':[]}
    with zipfile.ZipFile(raw,'w',zipfile.ZIP_DEFLATED) as z:
        for name in names:
            body=('benchmark: '+name+'\n').encode()
            entry={'name':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
            manifest['files'].append(entry)
            z.writestr(name,body+b'changed' if tamper and name==names[0] else body)
        if extra:z.writestr('unlisted.txt','should reject')
        z.writestr('MANIFEST.json',json.dumps(manifest))
    return raw.getvalue()

def must_reject(data):
    try:verify_zip(data)
    except ValueError:return
    raise AssertionError('Verifier unexpectedly accepted an invalid snapshot')

assert len(verify_zip(snapshot(LEGACY)))==7
assert len(verify_zip(snapshot(EXTENDED)))==14
must_reject(snapshot(EXTENDED+('forbidden.txt',)))
must_reject(snapshot(EXTENDED,extra=True))
must_reject(snapshot(EXTENDED,tamper=True))
print('PASS: old 7-file snapshots and 14-file Test88 snapshots; unsafe/altered data rejected.')
