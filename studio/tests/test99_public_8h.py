"""Offline checks for Test99: scientific pairing, isolation, and Studio wiring."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'studio'))
sys.path.insert(0, str(ROOT/'tools'))
from rvvlab_simple_tests import PROFILES, test_id, manifest_target, _server_runs
from rvvlab_epcc_results import RUN_TYPES, select_test_run
from rvvlab_test_runner import discover
import test99_native as native

class FakeFile:
    def __init__(self,content): self.content=content
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,*args):return self.content
class FakeSftp:
    def __init__(self,files):self.files=files
    def listdir(self,p):
        return sorted({x[len(p)+1:].split('/')[0] for x in self.files if x.startswith(p+'/')})
    def open(self,p,mode='rb'):
        if p not in self.files:raise OSError(2,'No such file')
        return FakeFile(self.files[p])
    def stat(self,p):
        if p not in self.files:raise OSError(2,'No such file')
        return type('S',(),{'st_size':len(self.files[p])})()
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass
class FakeSSH:
    def __init__(self,files):self.files=files;self.client=self
    def open_sftp(self):return FakeSftp(self.files)
    def base(self,remote):return '/home/runner/rvvlab-v5'

class Test99(unittest.TestCase):
    def test_manifest_found_and_isolated(self):
        items,errors=discover(ROOT/'studio/test_scripts')
        self.assertFalse(errors,errors)
        item=next(x for x in items if x['id']=='test99-public-8h')
        self.assertEqual(item['params']['seconds'],28800)
        self.assertEqual(item['requires_shared_corpus'],'performance')
        self.assertFalse(item['params']['new_run'])
        self.assertEqual(item['params']['epcc_node'],'rvc02')
        self.assertEqual(test_id('99','Cloud-V'),'test99-public-8h')
        self.assertEqual(test_id('99','EPCC'),'test99-public-8h')
        self.assertEqual(manifest_target('test99-public-8h'),('99',('Cloud-V','EPCC')))
        self.assertEqual(PROFILES['98'],('Cloud-V','EPCC'))
        self.assertEqual(RUN_TYPES['test99']['directory'],'test99-epcc-runs')
    def test_complete_remote_requires_validated_and_zip(self):
        folder='/home/runner/rvvlab-v5/test99-cloudv-runs/test99-20261016T120000Z-abcdef'
        files={folder+'/status99.json':b'{"state":"completed","validated":true,"rows":90}'}
        self.assertEqual(_server_runs(FakeSSH(files),'remote','99','Cloud-V')[0]['state'],'incomplete')
        files[folder+'/test99_results.zip']=b'nonempty'
        self.assertEqual(_server_runs(FakeSSH(files),'remote','99','Cloud-V')[0]['state'],'completed')
        self.assertTrue(_server_runs(FakeSSH(files),'remote','99','Cloud-V')[0]['validated'])
        files[folder+'/status99.json']=b'{"state":"completed","validated":false,"rows":90}'
        self.assertEqual(_server_runs(FakeSSH(files),'remote','99','Cloud-V')[0]['state'],'incomplete')
    def test_scientific_summary_and_anchor_drift(self):
        docs=['a.json','b.json']
        throughput={'OFFICIAL_503':1.0,'OFFICIAL_504':2.0,'A2_REF':3.0,'A2_G6144':3.3,'A2_G8192':3.6}
        rows=[]
        for phase in ('measure','confirmation'):
            for i,doc in enumerate(docs):
                for variant,val in throughput.items():
                    rows.append(dict(phase=phase,round=str(i),document=doc,variant=variant,
                                     gbps=val,anchor_drift_pct='2.0',anchor_before_gbps=3.0,anchor_after_gbps=3.06))
        result=native.report(rows,{'files':[{'name':d} for d in docs]})
        self.assertEqual(result['rounds_complete'],4)
        self.assertAlmostEqual(result['comparisons']['confirmation']['A2_G6144_vs_A2_REF']['file_equal_geomean'],1.1)
        self.assertAlmostEqual(result['comparisons']['measure']['A2_G8192_vs_A2_REF']['file_equal_geomean'],1.2)
        self.assertEqual(result['anchor_drift_abs_percent']['confirmation']['over_10pct'],0)
        self.assertEqual(result['anchor_drift_abs_percent']['measure']['groups'],2)
        self.assertIn('NOT an unseen-file holdout',result['important'])
    def test_build_configuration_and_slurm(self):
        src=(ROOT/'tools/test99_native.py').read_text()
        self.assertIn("'6144' if name=='A2_G6144'",src)
        self.assertIn("'8192' if name=='A2_G8192'",src)
        self.assertIn('anchor_before_gbps',src)
        self.assertIn('28800',src)
        sb=(ROOT/'tools/test99_epcc.sbatch').read_text()
        self.assertIn('--time=08:20:00',sb)
        self.assertIn('--seconds 28800',sb)
        self.assertIn('flock -n 9',sb)
        self.assertIn('test99-exclusive.lock',(ROOT/'tools/test99_cloudv.sh').read_text())

if __name__=='__main__':unittest.main()
