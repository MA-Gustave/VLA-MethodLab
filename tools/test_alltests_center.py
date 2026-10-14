#!/usr/bin/env python3
"""Test-center offline regression; no network or benchmark is started."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_test_runner import discover
from rvvlab_test_center import (local_state,merge,label,check_remote_night,inspect_remote_94)
ITEMS,_=discover(ROOT/'studio/test_scripts')
assert len(ITEMS)==15

class TestAllTests(unittest.TestCase):
    def byid(self,name):return next(i for i in ITEMS if i['id']==name)
    def test_all_15_manifests(self):
        self.assertEqual(len(ITEMS),15)
        self.assertEqual(ITEMS[0]['id'],'machine-compare-94-1h')
        self.assertEqual(len({i['id'] for i in ITEMS}),15)
    def test_local_pass_does_not_prove_benchmark_finished(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'TestRunner'/'stage1-overhead-93-3h'/'20261013T120000Z';p.mkdir(parents=True)
            (p/'result.json').write_text(json.dumps({'result':{'state':'stopped','run_id':'night-20261013T120347Z-1ad1e5'}}))
            x=local_state(self.byid('stage1-overhead-93-3h'),d)
            self.assertEqual(x['state'],'local_pass')
            self.assertEqual(x['run_id'],'night-20261013T120347Z-1ad1e5')
            self.assertNotEqual(label(x['state']),'TERMINÉ · distant')
            y=merge(x,{'state':'stopped','id':'night-20261013T120347Z-1ad1e5'})
            self.assertEqual(y['state'],'stopped')
    def test_downloaded_94_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'TestRunner'/'machine-compare-94-1h'/'20261013T205508Z';p.mkdir(parents=True)
            (p/'test94_results.zip').write_bytes(b'x')
            x=local_state(self.byid('machine-compare-94-1h'),d)
            self.assertEqual(x['state'],'downloaded')
            self.assertTrue(x['downloaded'])
            self.assertIn('SHA256',x['proof'])
    def test_remote_campaign_mapping_all_non91_tests(self):
        runs=[{'id':'night-20261013T120347Z-1ad1e5','campaign':'stage1_overhead_isolation_93','state':'stopped'},
              {'id':'night-20261013T011722Z-d61b0f','campaign':'staged_composition_exploration_92','state':'completed'},
              {'id':'night-20261013T055555Z-123abc','campaign':'engine_library_3h','state':'running'},
              {'id':'night-20261013T055556Z-123abc','campaign':'composition_exploration_91','state':'completed'}]
        with tempfile.TemporaryDirectory() as d:
            with patch('rvvlab_night.remote_runs',return_value=runs):
                mapping,_=check_remote_night(None,'rvvlab-v5',ITEMS,d)
            self.assertEqual(mapping['stage1-overhead-93-3h']['state'],'stopped')
            self.assertEqual(mapping['composition-explorer-92-8h']['state'],'completed')
            self.assertEqual(mapping['explore-v5-engines-3h']['state'],'running')
            self.assertNotIn('composition-explorer-91-8h',mapping)  # ambiguous pilot vs 8h
            self.assertNotIn('composition-explorer-91-pilot',mapping)
    def test_cloudv_94_completed_needs_packet_rows(self):
        rid='test94-20261013T205510Z-b9801f';work='/rvv/test94-runs/'+rid
        class SFTP:
            def listdir(self,path):return [rid]
            def open(self,path,mode='r'):
                import io
                return io.BytesIO(json.dumps({'state':'completed','rows':12454}).encode())
            def stat(self,path):return SimpleNamespace(st_size=1100)
            def close(self):pass
        ssh=SimpleNamespace(base=lambda n:'/rvv',client=SimpleNamespace(open_sftp=lambda:SFTP()),
                            exec_text=lambda c:'PID COMMAND\n')
        result=inspect_remote_94(ssh,'rvvlab-v5','Cloud-V')
        self.assertEqual(result['state'],'completed')
        self.assertEqual(result['rows'],12454)
        class MissingZip(SFTP):
            def stat(self,path):raise FileNotFoundError(path)
        ssh.client.open_sftp=lambda:MissingZip()
        result=inspect_remote_94(ssh,'rvvlab-v5','Cloud-V')
        self.assertEqual(result['state'],'unknown')
    def test_result_no_remote_is_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            for item in ITEMS:
                x=local_state(item,d)
                self.assertEqual(x['state'],'unknown')
                self.assertFalse(x['downloaded'])
if __name__=='__main__':unittest.main(verbosity=2)
