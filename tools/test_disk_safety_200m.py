#!/usr/bin/env python3
"""Offline regression checks: 200 MiB disk safety floor and 900-second audit cadence.
No SSH, native toolchain, deletions, or server access required.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import tempfile
from types import ModuleType, SimpleNamespace
import sys
from unittest import mock

root=Path(__file__).resolve().parents[1]
worker=root/'experiments/workers/89_prequal_corrected_60m_worker.py'
spec=importlib.util.spec_from_file_location('rvvlab_disk89', worker)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
MIB=1024**2
assert m.FREE_FLOOR==200*MIB
assert m.BUILD_START_FLOOR==200*MIB
with tempfile.TemporaryDirectory(prefix='rvvlab-diskguard-test-') as tmp:
    base=Path(tmp)
    (base/'source').mkdir()
    campaign=m.Campaign(base/'source',base/'run',1.0,2,0)
    # The real worker's check both records the 15-min audit and enforces the floor.
    with mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=3900*MIB)):
        with mock.patch.object(m.time,'monotonic',return_value=1000.0):
            campaign.check(building=True)
            assert len(campaign.meta['disk_monitor_15m'])==1
            assert campaign.status['disk_safety_floor_mib']==200
            assert campaign.status['disk_monitor_interval_seconds']==900
        with mock.patch.object(m.time,'monotonic',return_value=1899.0):
            campaign.check()
            assert len(campaign.meta['disk_monitor_15m'])==1
        with mock.patch.object(m.time,'monotonic',return_value=1900.0):
            campaign.check()
            assert len(campaign.meta['disk_monitor_15m'])==2
    with mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=200*MIB)):
        campaign.check()
        campaign.check(building=True)
    with mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=200*MIB-1)):
        for building in (False,True):
            try:campaign.check(building=building)
            except m.Safety as err:assert 'disk' in str(err)
            else:raise AssertionError('Below 200 MiB did not trigger Safety')
    # A run that encounters insufficient disk stops safely, emits status/checkpoint
    # and retains an auditable snapshot rather than a generic 'failed' traceback.
    # The production worker uses the Linux-only fcntl module for exclusive
    # locking.  Windows runs this test only: a stub prevents the offline
    # safety-stop check from importing a Linux-only module.  The real worker
    # is UNCHANGED and still enforces fcntl locking on RISC-V Linux.
    fcntl_test_stub=ModuleType('fcntl')
    fcntl_test_stub.LOCK_EX=2
    fcntl_test_stub.LOCK_NB=4
    fcntl_test_stub.flock=lambda *args,**kwargs:None
    with mock.patch.dict(sys.modules,{'fcntl':fcntl_test_stub}):
        with mock.patch.object(campaign,'preflight',side_effect=lambda:campaign.check()):
            with mock.patch.object(m.shutil,'disk_usage',return_value=SimpleNamespace(free=199*MIB)):
                campaign.execute()
    assert campaign.status['state']=='safety_stop',campaign.status
    assert 'disk' in campaign.status['stop_reason']
    assert (campaign.root/'status.json').is_file()
    assert (campaign.root/'checkpoint.json').is_file()
    assert (campaign.root/'map.csv').is_file()

# CLI preflight must pass at 3.9 GiB and at the exact safety floor and refuse below.
spec=importlib.util.spec_from_file_location('rvvlab_cli_disk',root/'tools/rvvlab.py')
import sys
sys.path.insert(0,str(root/'orchestrator'))
cli=importlib.util.module_from_spec(spec);spec.loader.exec_module(cli)
class SSH:
    def __init__(self,kib):self.kib=kib
    def exec_text(self,command):return 'riscv64\n/usr/bin/python3\n/usr/bin/g++\ng++ (test) 14.2\n/dev/root 1 2 3 4% /\n'
    def available_kib(self):return self.kib
for free in (3900*1024,200*1024,None):
    result=cli.preflight(SSH(free))
    assert result['available_gib']==(round(free/1048576,2) if free is not None else None)
try:cli.preflight(SSH(200*1024-1))
except RuntimeError as e:assert '200' in str(e)
else:raise AssertionError('CLI accepted disk below 200 MiB')
# GUI and worker copies must agree with precommitted SHA manifests.
import hashlib,json
for i in range(81,90):
    w=next((root/'experiments/workers').glob(f'{i}_*_worker.py'))
    profile=json.loads(next((root/'experiments/profiles').glob(f'{i}_*.test.json')).read_text())
    assert hashlib.sha256(w.read_bytes()).hexdigest()==profile['params']['worker_sha256']
    assert w.read_bytes()==(root/'studio/test_scripts'/w.name).read_bytes()
    launch=next((root/'studio/test_scripts').glob(f'{i}_*.py'))
    launch=next(p for p in (root/'studio/test_scripts').glob(f'{i}_*.py') if not p.name.endswith('_worker.py'))
    text=launch.read_text()
    assert 'free < 200*1024' in text,launch
    assert '4*1024*1024' not in text,launch
print('PASS: 200 MiB guard / 15-min audits / safe-stop snapshot / CLI preflight / 9 GUI+worker SHA256 alignments')
