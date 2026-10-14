#!/usr/bin/env python3
"""Offline regression: persistent per-machine Test94 badge, source validation, no remote writes."""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_target_status import display, latest_run, remote_probe, write_status

RUN='test94-20261013T205510Z-b9801f'

class TargetStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.results=self.root/'cloudv'/'TestRunner'/'machine-compare-94-1h'/'20261013T205508Z'
        self.results.mkdir(parents=True)
        self.launch={'id':RUN,'mode':'Cloud-V','workdir':'/home/test/rvvlab-v5/test94-runs/'+RUN,
                     'pid':172873,'started_utc':'2026-10-13T20:56:35+00:00'}
        (self.results/'launch94.json').write_text(json.dumps(self.launch))

    def test_first_launch_uncertain(self):
        item=latest_run(self.root/'cloudv')
        self.assertEqual(item['launch']['id'],RUN)
        self.assertIsNone(item['cached'])

    def test_record_and_timestamp(self):
        status=write_status(self.results,'Cloud-V','running','train · 100 rows',True,RUN)
        self.assertEqual(latest_run(self.root/'cloudv')['cached']['run_id'],RUN)
        text,kind=display(status,connected=True)
        self.assertIn('Running',text);self.assertNotIn('Last:',text);self.assertEqual(kind,'active')
        text,_=display(status,connected=False)
        self.assertIn('Last: Running',text)
        write_status(self.results,'Cloud-V','completed','Result SHA256 verified',True)
        result=latest_run(self.root/'cloudv')['cached']
        self.assertEqual(display(result,True)[1],'ok')
        self.assertEqual(display(result,False)[1],'idle')

    def test_failed_and_stale_warning(self):
        rec=write_status(self.results,'Cloud-V','failed','build error',True)
        self.assertEqual(display(rec,False)[1],'error')
        self.assertIn('Last: Failed',display(rec,False)[0])
        rec=write_status(self.results,'Cloud-V','monitoring_stopped','Remote continues',False)
        self.assertIn('Monitoring off',display(rec,False)[0])

    def test_remote_probe_completed(self):
        client=Mock();client.exec_text.return_value=json.dumps({'state':'completed','phase':'finish','rows':87})
        self.assertEqual(remote_probe(client,self.launch),('completed','87 rows'))
        command=client.exec_text.call_args.args[0]
        self.assertIn('status94.json',command);self.assertNotIn('rm -',command)

    def test_remote_probe_pending_epcc(self):
        client=Mock();client.exec_text.side_effect=['{}','PENDING']
        run={**self.launch,'mode':'EPCC','job_id':'284322'}
        self.assertEqual(remote_probe(client,run),('queued','Slurm pending'))
        self.assertEqual(client.exec_text.call_count,2)
        self.assertIn('284322',client.exec_text.call_args.args[0])

    def test_remote_probe_running_epcc(self):
        client=Mock();client.exec_text.side_effect=['{}','RUNNING']
        run={**self.launch,'mode':'EPCC','job_id':'284322'}
        self.assertEqual(remote_probe(client,run),('running','Slurm running'))

    def test_remote_missing_not_success(self):
        client=Mock();client.exec_text.return_value='{}'
        self.assertEqual(remote_probe(client,self.launch),('starting','Awaiting remote status'))

    def test_invalid_path_rejected_without_ssh(self):
        client=Mock()
        with self.assertRaises(ValueError):remote_probe(client,{**self.launch,'workdir':'/tmp/evil;id'})
        client.exec_text.assert_not_called()

    def test_invalid_or_unrelated_local_cache(self):
        (self.results/'launch94.json').write_text('not json')
        self.assertIsNone(latest_run(self.root/'cloudv'))
        with self.assertRaises(ValueError):write_status(self.results,'EPCC-wrong','running')

if __name__=='__main__':unittest.main(verbosity=2)
