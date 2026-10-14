#!/usr/bin/env python3
"""Portable, offline Test 90 audit. --full rebuilds all 496 held-out JSON (no SSH)."""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--full',action='store_true',help='Create and validate every independent Test 90 JSON and simulate its primary 3x schedule')
args=p.parse_args()
worker=root/'experiments/workers/90_holdout_validation_2h_worker.py'
spec=importlib.util.spec_from_file_location('test90worker',worker)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert m.MAX_HOURS==2.0 and m.BENCH_MAX_ITERATIONS==1000
assert m.FREE_FLOOR==200*1024*1024
assert 'count>1000' in m.BENCH_CPP
assert m.RUN_FILES[-1]=='VALIDATION_2H.md'
assert 'fcntl' not in __doc__  # test intentionally does not call Linux-only execute()
tags=[v[0] for v in m.catalog()]
assert tags==['upstream_vls256','A0_E14_original','A1_size_gate',
              'A2_quick_dispatch','sparse8_escape8_reference'],tags
specs=m.holdout_specs()
counts=Counter(o['design'] for o in specs)
assert counts=={'gate512':104,'gate4096':136,'deceptive_prefix':160,'sparse_challenge':96},counts
assert len(specs)==496
assert len({tuple(sorted((k,str(v)) for k,v in x.items())) for x in specs})==496
for n in (128,255,256,511,512,513,1023,1024,2048,4095,4096,4097,65536,262144,1048576):
    it=m.iterations_for_bytes(n)
    assert 1<=it<=1000
assert m.iterations_for_bytes(256)==1000
for obj in specs if args.full else (specs[0],specs[12],specs[80],specs[104],specs[237],specs[240],specs[400],specs[-1]):
    if obj['design'].startswith('gate'):
        data=m.make_holdout_exact(obj['kinds'][0],obj['target'],obj['seed'])
        assert len(data)==obj['target']
    elif obj['design']=='deceptive_prefix':
        data=m.make_holdout_deceptive(obj['kinds'][0],obj['target'],obj['offset'],obj['seed'])
        assert len(data)==obj['target']
        assert data.index(m._atom_bytes(obj['kinds'][0],obj['seed']))==obj['offset']
    else:
        data=m.make_combo_bytes(obj['kinds'],obj['target'],obj['placement'],seed=obj['seed'])
    json.loads(data)
# Every repeated corpus gets distinct test90 seed and every file is unique by bytes.
assert (root/'studio/test_scripts'/worker.name).read_bytes()==worker.read_bytes()
file_hash=hashlib.sha256(worker.read_bytes()).hexdigest()
filename='90_holdout_validation_2h.test.json'
manifest_a=json.loads((root/'experiments/profiles'/filename).read_text(encoding='utf8'))
manifest_b=json.loads((root/'studio/test_scripts'/filename).read_text(encoding='utf8'))
assert manifest_a==manifest_b
assert manifest_a['params']=={'hours':2.0,'jobs':2,'core':0,'worker_sha256':file_hash}
assert manifest_a['script']=='90_holdout_validation_2h.py'
assert (root/'RUN_TEST_90.bat').is_file()
assert "'holdout-2h'" in (root/'tools/rvvlab.py').read_text()
sys.path.insert(0,str(root/'studio'))
from rvvlab_test_runner import discover
found,errors=discover(root/'studio/test_scripts')
assert not errors,errors
assert any(x['id']=='adaptive-holdout-validation-2h' for x in found)
from rvvlab_night import verify_zip
sys.path.insert(0,str(root/'orchestrator'))
import rvvlab_night as studio_sync
import importlib
cli_spec=importlib.util.spec_from_file_location('cli_test90_sync',root/'orchestrator/rvvlab_night.py')
cli_sync=importlib.util.module_from_spec(cli_spec);cli_spec.loader.exec_module(cli_sync)
with tempfile.TemporaryDirectory(prefix='test90-portable-') as temp:
    t=Path(temp)
    c=m.Campaign(t,t/'run',2.0,2,0)
    # Local status/report/snapshot check BEFORE a real source or corpus exists.
    c.checkpoint('preflight',force=True)
    blob=(c.root/'snapshot.zip').read_bytes()
    a=verify_zip(blob);b=cli_sync.verify_zip(blob)
    assert a is not None and b is not None
    assert (c.root/'VALIDATION_2H.md').is_file()
    if args.full:
        c.check=lambda building=False:None
        c.checkpoint=lambda *a,**kw:None
        paths=c.make_corpus()
        c.corpi=paths
        assert len(paths)==496
        hashes=[r['sha256'] for r in c.corpi_info.values()]
        assert len(set(hashes))==496,'duplicate JSON in holdout corpus'
        assert sum(c.corpi_info[k]['design'].startswith('gate') for k in c.corpi_info)==240
        out=[]
        c.binaries={tag:('dummy','','') for tag in tags}
        def fake_measure(phase,tag,path,iters,trial):
            assert 1<=iters<=1000
            out.append((phase,tag,path.name,trial))
        def bounded_check(building=False):
            if c.status.get('experiment_phase')=='confirm_secondary':raise m.Deadline('stop synthetic scheduling')
        c.measure=fake_measure
        c.check=bounded_check
        try:c.explore()
        except m.Deadline:pass
        assert len(out)==88*5*3,(len(out),len(c.meta.get('primary_case_ids',[])))
        assert len(c.meta['primary_case_ids'])==88
        assert all(p=='confirm_primary' for p,tag,n,tr in out)
        assert Counter(tr for p,tag,n,tr in out)=={0:440,1:440,2:440}
        print('PASS: 496 distinct valid holdout JSON; exact 512B/4KiB cases; 88 x 3 x 5 paired primary schedule')
print('PASS: Test 90, Studio/CLI manifest hashes, native 1..1000 contract, 200MiB guard, SHA256 snapshot schemas')
