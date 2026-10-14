#!/usr/bin/env python3
"""Self-audit unified RVV-VLA Lab release (no remote access)."""
from pathlib import Path
import hashlib,json,csv,sys
root=Path(__file__).resolve().parents[1]
studio=root/'studio'
assert (root/'engine/src/rvv/engines/engine_plan.h').is_file()
assert (root/'orchestrator/rvvlab_backend.py').is_file()
assert (root/'tools/rvvlab.py').is_file()
assert (studio/'RVV_Lab_Studio.pyw').is_file()
assert (studio/'rvvlab_test_runner.py').is_file()
assert (studio/'rvvlab_storage.py').is_file()
assert (studio/'rvvlab_reports.py').is_file()
assert (root/'START_STUDIO.ps1').is_file()
d=json.loads((root/'experiments/patterns.json').read_text(encoding='utf8'))
assert len(d['points'])==15
manifests=sorted((root/'experiments/profiles').glob('*.test.json'))
assert len(manifests)==14
for mf in manifests:
    doc=json.loads(mf.read_text(encoding='utf8'))
    name=doc['script'].replace('.py','_worker.py')
    worker=root/'experiments/workers'/name
    gui_worker=studio/'test_scripts'/name
    assert worker.is_file() and gui_worker.is_file(),name
    assert worker.read_bytes()==gui_worker.read_bytes(),name
    digest=hashlib.sha256(worker.read_bytes()).hexdigest()
    assert digest==doc['params']['worker_sha256'],name
    guimf=studio/'test_scripts'/mf.name
    assert json.loads(guimf.read_text(encoding='utf8'))==doc,name
    script=studio/'test_scripts'/doc['script']
    assert script.is_file(),script
sys.path.insert(0,str(studio))
from rvvlab_backend import preferred_repo
import rvvlab_test_runner
assert preferred_repo(studio).resolve()==(root/'engine').resolve()
found,errors=rvvlab_test_runner.discover(studio/'test_scripts')
assert not errors,errors
assert len(found)>=14 and any(x['id']=='machine-compare-94-1h' for x in found)
sys.path.insert(0,str(root/'tools'))
import rvvlab
assert rvvlab.PRESETS['prequal-60m']['minutes']==60
assert rvvlab.PRESETS['prequal-8h']['minutes']==480
assert rvvlab.PRESETS['prequal-fixed-60m']['minutes']==60
assert rvvlab.PRESETS['holdout-2h']['minutes']==120
assert rvvlab.PRESETS['explore-92-8h']['minutes']==480
assert rvvlab.PRESETS['diagnose-93-3h']['minutes']==180
for run,count in [('2026-10-10-engine-library-3h',2469),('2026-10-11-stage-profile-8h',6887)]:
    file=root/'results/runs'/run/'observations.csv'
    with file.open(newline='',encoding='utf8') as stream:
        assert sum(1 for _ in csv.DictReader(stream))==count
assert not list(root.rglob('.env')),'.env must never be included in release'
assert not list(root.rglob('.git')),'embedded git directories not allowed in release'
if '--hashes' in sys.argv:
    for line in (root/'SHA256SUMS.txt').read_text('utf8').splitlines():
        expected,name=line.split('  ',1)
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,name
    print('PASS: complete release SHA256 manifest')
print('PASS: unified Lab + GUI, original 14 profiles and Studio-only Test94, aligned manifests & SHAs, no credentials')
