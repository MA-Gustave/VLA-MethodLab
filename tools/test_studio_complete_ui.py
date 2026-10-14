#!/usr/bin/env python3
"""Regression test against Studio UI 10131514, read-only data / no remote SSH."""
from __future__ import annotations
import io
import json
from datetime import datetime,timezone
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_unified_campaigns import campaign_start,campaign_elapsed,campaign_details,display_rows,campaign_phase,campaign_state
from rvvlab_night import remote_runs
from rvvlab_test_runner import discover

RID90='night-20261012T172225Z-1942f9'
RID93='night-20261013T120347Z-1ad1e5'

class RemoteFile(io.BytesIO):pass
class MockSftp:
    def __init__(self,store):self.store=store
    def listdir(self,path):return [RID93,RID90]
    def open(self,path,mode='r'):
        key=tuple(path.rsplit('/',2)[-2:]);content=self.store.get(key)
        if content is None:raise OSError(path)
        return RemoteFile(json.dumps(content).encode())
    def close(self):pass
class MockSSH:
    def __init__(self,store):self.client=type('Client',(),{'open_sftp':lambda s:MockSftp(store)})()
    def base(self,_):return '/remote'

class Tests(unittest.TestCase):
    def setUp(self):
        data={
            (RID93,'status.json'):{'state':'repeat','observations':4411,'campaign':'Test93',
                'started_utc':'2026-10-13T12:03:50Z','last_update':'2026-10-13T13:14:32Z',
                'experiment_phase':'repeat','current_candidate':'P6f9a','budget_seconds':10800,
                'disk_free_gib':25.348},
            (RID93,'launcher.json'):{'run_id':RID93,'campaign':'Test93'},
            (RID90,'status.json'):{'state':'stopped','observations':8402,'last_update':'2026-10-12T19:22:25Z',
                'campaign':'adaptive_holdout_validation_2h'},
            (RID90,'launcher.json'):{'run_id':RID90,'campaign':'adaptive_holdout_validation_2h'},
        }
        self.rows=remote_runs(MockSSH(data),'rvvlab-v5')
    def test_campaign_times(self):
        now=datetime(2026,10,13,13,15,1,tzinfo=timezone.utc)
        values=display_rows(self.rows,now=now)
        self.assertEqual(len(values[0]),7)
        self.assertTrue(values[0][0].startswith('Test 93'))
        self.assertEqual(values[0][1],'Running')
        self.assertIn('2026-10-13',values[0][2])
        self.assertEqual(values[0][3],'1h 11m')
        self.assertEqual(values[0][4],'repeat')
        self.assertEqual(values[0][5],4411)
        self.assertNotIn(RID93,repr(values[0]))
        self.assertEqual(values[1][1],'Finished')
        self.assertTrue(values[1][2].startswith('≈ '))
        self.assertEqual(values[1][3],'2h 00m')
        self.assertIn('≈ means estimated',campaign_details(self.rows[1]))
        self.assertIn(RID93,campaign_details(self.rows[0]))
        self.assertIn('P6f9a',campaign_details(self.rows[0]))
        self.assertEqual(campaign_elapsed({'state':'failed','id':'bad'}),'—')
        self.assertEqual(campaign_phase({'state':'done'}),'—')
        self.assertEqual(campaign_state({'state':'failed'}),'Failed')
    def test_runner_discovery(self):
        found,errors=discover(ROOT/'studio'/'test_scripts')
        self.assertFalse(errors)
        self.assertGreaterEqual(len(found),15)
        self.assertEqual(found[0]['id'],'machine-compare-94-1h')
    def test_no_hash_removed_from_security(self):
        source=(ROOT/'studio/rvvlab_test_runner.py').read_text()
        self.assertIn('if sha256(manifest_path)!=item',source)
        self.assertNotIn("columns=('title','script','sha','status')",source)
        self.assertNotIn("'SHA256 (prefix)'",source)
        self.assertIn("iid=runid",(ROOT/'studio/rvvlab_unified_campaigns.py').read_text())

if __name__=='__main__':unittest.main(verbosity=2)
