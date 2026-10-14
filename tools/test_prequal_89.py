#!/usr/bin/env python3
"""Offline audit of Test 89. Never touches SSH. --full builds all 767 JSON corpora."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--full',action='store_true',help='Regenerate and validate 767 JSON inputs (~180 MiB in a temporary folder)')
args=p.parse_args()
root=Path(__file__).resolve().parents[1]
worker=root/'experiments/workers/89_prequal_corrected_60m_worker.py'
spec=importlib.util.spec_from_file_location('prequal_corrected_89',worker)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert m.MAX_HOURS==1.0
assert m.BENCH_MAX_ITERATIONS==1000
assert 'count>1000' in m.BENCH_CPP
assert 'Iteration count outside 1..1000' in m.BENCH_CPP
assert m.GIB==1024**3
assert len(m.catalog())==6
assert [x[0] for x in m.catalog()]==[
 'upstream_vls256','A0_E14_original','A1_size_gate','A2_quick_dispatch',
 'E01_adaptive','sparse8_escape8_reference']
for size in (1,128,256,511,512,513,1023,1024,2047,2048,2049,4094,4095,4096,4097,4098,8192,8193,16384,65536,262144,1048576,2*1048576,4*1048576):
    iters=m.iterations_for_bytes(size)
    assert isinstance(iters,int) and 1<=iters<=1000,(size,iters)
assert m.iterations_for_bytes(256)==1000
assert m.iterations_for_bytes(1024)==768
assert m.iterations_for_bytes(4096)==512
for invalid in (0,-1,1.2,None):
    try:m.iterations_for_bytes(invalid)
    except ValueError:pass
    else:raise AssertionError('Invalid input accepted')
# A changed schedule cannot send >1000 to the subprocess.
probe=m.Campaign.__new__(m.Campaign)
probe.check=lambda:None
try:probe.measure('anchor','A0_E14_original',Path('not_used.json'),1001,0)
except RuntimeError as e:assert 'iteration' in str(e).lower()
else:raise AssertionError('measure() accepted 1001')
# Check legitimate 1000 propagates past guard; no binary provided so AttributeError is expected.
try:probe.measure('anchor','A0_E14_original',Path('not_used.json'),1000,0)
except AttributeError:pass
else:raise AssertionError('Guard was not reached')
for kind in ('ascii','escaped','utf8'):
    for size in m.EDGE_SIZES:
        data=m.exact_gate_bytes(kind,size)
        assert len(data)==size
        json.loads(data)
for kinds in [('ascii','escaped'),('numbers','utf8'),('slashstorm','unicode_escape'),('dense','numbers','utf8'),('escaped','utf8','unicode_escape')]:
    for placement in ('front','middle','back','alternating','staircase','bursts','randomized'):
        doc=m.make_combo_bytes(kinds,8192,placement)
        json.loads(doc)
        assert doc==m.make_combo_bytes(kinds,8192,placement)
manifest_name='89_prequal_corrected_60m.test.json'
a=json.loads((root/'experiments/profiles'/manifest_name).read_text())
b=json.loads((root/'studio/test_scripts'/manifest_name).read_text())
assert a==b and a['params']=={'hours':1.0,'jobs':2,'core':0,'worker_sha256':hashlib.sha256(worker.read_bytes()).hexdigest()}
assert a['script']=='89_prequal_corrected_60m.py'
assert (root/'studio/test_scripts'/worker.name).read_bytes()==worker.read_bytes()
assert (root/'studio/test_scripts'/a['script']).is_file()
assert (root/'RUN_TEST_89.bat').is_file()
assert 'prequal-fixed-60m' in (root/'tools/rvvlab.py').read_text()
from sys import path as sys_path
sys_path.insert(0,str(root/'studio'))
from rvvlab_test_runner import discover
found,errors=discover(root/'studio/test_scripts')
assert not errors,errors
assert any(x['id']==a['id'] for x in found)
# Test smoke spec generation in a disposable temp dir; does not run native C++.
with tempfile.TemporaryDirectory(prefix='rvvlab-test89-smoke-') as tmp:
    camp=m.Campaign.__new__(m.Campaign)
    camp.root=Path(tmp);camp.meta={};camp.checkpoint=lambda *a,**kw:None
    camp.make_validation_cases()
    assert len(camp.smoke_specs)==4
    assert [x[2] for x in camp.smoke_specs]==[1000,32,32,32]
    assert [x[1].stat().st_size for x in camp.smoke_specs]==[256,4095,4096,4097]
    for _,filepath,_ in camp.smoke_specs:json.loads(filepath.read_bytes())
if args.full:
    with tempfile.TemporaryDirectory(prefix='rvvlab-test89-full-') as tmp:
        camp=m.Campaign.__new__(m.Campaign)
        camp.root=Path(tmp);camp.meta={}
        camp.check=lambda **kw:None
        camp.checkpoint=lambda *a,**kw:None
        paths=camp.make_corpus()
        cases=json.loads((camp.root/'corpus_manifest.json').read_text())['scenarios']
        assert len(paths)==767==len(cases)
        assert len({x['id'] for x in cases})==767
        for item in cases:
            doc=(camp.root/item['id']).read_bytes()
            assert len(doc)==item['bytes']
            assert hashlib.sha256(doc).hexdigest()==item['sha256']
            json.loads(doc)
            if item['exact_target']:assert len(doc)==item['size_target']
print('PASS: Test 89 corrected cap + native smoke specification + six plans + Studio/CLI/worker hashes'+(' + 767-case complete corpus' if args.full else ''))
