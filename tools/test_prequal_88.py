#!/usr/bin/env python3
"""Offline Test 88 audit. --full regenerates all 767 cases (~179 MiB)."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,tempfile,sys
p=argparse.ArgumentParser();p.add_argument('--full',action='store_true');args=p.parse_args()
root=Path(__file__).resolve().parents[1]
w=root/'experiments/workers/88_prequal_exploration_8h_worker.py'
spec=importlib.util.spec_from_file_location('test88_worker',w)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert len(m.catalog())==10
assert len({x[0] for x in m.catalog()})==10
assert m.MAX_HOURS==8.0
assert sum(1 for _ in m.BASE_KINDS)==16
assert len(m.COMBINATION_PAIRS)==22
for kind in ('ascii','escaped','utf8'):
    for n in m.EDGE_SIZES:
        doc=m.exact_gate_bytes(kind,n)
        assert len(doc)==n
        json.loads(doc)
for kind_tuple in [('ascii','escaped'),('numbers','utf8'),('slashstorm','unicode_escape'),
                   ('dense','numbers','utf8'),('escaped','utf8','unicode_escape')]:
    for pos in ('front','middle','back','alternating','staircase','bursts','randomized'):
        data=m.make_combo_bytes(kind_tuple,8192,pos)
        json.loads(data)
        assert data==m.make_combo_bytes(kind_tuple,8192,pos)
assert len(m.prequal_pairwise([],{} )[0])==0
ui=root/'studio/test_scripts/88_prequal_exploration_8h.test.json'
manifest=json.loads(ui.read_text(encoding='utf8'))
assert manifest['params']['hours']==8.0
assert hashlib.sha256(w.read_bytes()).hexdigest()==manifest['params']['worker_sha256']
assert (root/'studio/test_scripts'/w.name).read_bytes()==w.read_bytes()
assert json.loads((root/'experiments/profiles'/ui.name).read_text())==manifest
if args.full:
    with tempfile.TemporaryDirectory(prefix='rvv-prequal88-') as td:
        camp=m.Campaign.__new__(m.Campaign)
        camp.root=Path(td);camp.meta={};camp.check=lambda **kw:None
        camp.checkpoint=lambda *a,**kw:None
        corpi=m.Campaign.make_corpus(camp)
        manifest=json.loads((camp.root/'corpus_manifest.json').read_text())
        assert len(corpi)==767==len(manifest['scenarios'])
        assert len({x['id'] for x in manifest['scenarios']})==767
        for x in manifest['scenarios']:
            data=(camp.root/x['id']).read_bytes()
            assert len(data)==x['bytes']
            assert hashlib.sha256(data).hexdigest()==x['sha256']
            json.loads(data)
            if x['exact_target']:assert len(data)==x['size_target']
print('PASS: Test 88, 10 native configurations, 767-case precommitted matrix, 51 thresholds, manifests/SHA256 (offline'+(' full corpus' if args.full else ' quick')+')')
