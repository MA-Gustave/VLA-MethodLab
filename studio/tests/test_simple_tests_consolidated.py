"""Offline verification that EPCC patch and Simple Tests share the SAME run state."""
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rvvlab_simple_tests import _server_runs, SimpleTestsPanel
from test_epcc_results import FakeSSH, BASE, RUN, payload


class SimpleTestsConsolidatedTests(unittest.TestCase):
    def test_epcc96_completed_only_with_validation(self):
        files=payload()
        key=BASE+'/test96-epcc-runs/'+RUN+'/status96.json'
        files[key]=json.dumps({'state':'completed','rows':48,'validated':True}).encode()
        rows=_server_runs(FakeSSH(files),'rvvlab-v5','96','EPCC')
        self.assertEqual([x['id'] for x in rows],[RUN])
        self.assertEqual(rows[0]['state'],'completed')
        self.assertTrue(rows[0]['validated'])
        # A completed label alone must not enable the download button.
        files[key]=json.dumps({'state':'completed','rows':48,'validated':False}).encode()
        rows=_server_runs(FakeSSH(files),'rvvlab-v5','96','EPCC')
        self.assertEqual(rows[0]['state'],'incomplete')
        self.assertFalse(rows[0]['validated'])

    def test_epcc94_detects_failure_without_claiming_completion(self):
        run='test94-20261013T233735Z-728f3a'
        root=BASE+'/test94-runs/'+run
        data={root+'/status94.json':b'{"state":"failed","rows":0}',
              root+'/test94_results.zip':b'fake zip'}
        rows=_server_runs(FakeSSH(data),'rvvlab-v5','94','EPCC')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['state'],'failed')
        self.assertFalse(rows[0]['validated'])

    def test_epcc_download_directory_matches_sync_patch(self):
        o=SimpleTestsPanel.__new__(SimpleTestsPanel)
        o.profile='EPCC'
        o.studio=type('S',(),{'vars':{'results':type('V',(),{'get':lambda _:'/tmp/results'})()}})()
        self.assertEqual(o._packet_dir('96',RUN).name,'EPCC-'+RUN)
        self.assertEqual(o._packet_dir('97','test97-example').name,'EPCC-test97-example')
        self.assertEqual(o._packet_dir('94','test94-example').name,'EPCC-test94-example')
        o.profile='Cloud-V'
        self.assertEqual(o._packet_dir('95','test95-example').name,'simple-test95-example')

    def test_automatically_patched_studio_anchors(self):
        entry=Path(__file__).resolve().parents[1]/'RVV_Lab_Studio.pyw'
        text=entry.read_text(encoding='utf8')
        self.assertIn('self.simple_tests=SimpleTestsPanel',text)
        self.assertIn('self.advanced_notebook=adv',text)
        self.assertNotIn("notebook.add(self.test_runner_tab,text='Test Runner')",text)
        self.assertIn('self.simple_tests.profile_changed()',text)
        self.assertNotIn('runner.node_combo',Path(__file__).resolve().parents[1].joinpath('rvvlab_simple_tests.py').read_text())

if __name__=='__main__':unittest.main()
