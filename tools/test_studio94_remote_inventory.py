#!/usr/bin/env python3
"""Read-only remote Test94 inventory and duplicate launch guard regression tests."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
import rvvlab_target_status as status
RID1='test94-20261013T205510Z-b9801f'
RID2='test94-20261013T233735Z-728f3a'

class LocalSFTP:
    def listdir(self,path):return os.listdir(path)
    def open(self,path,mode='r'):return open(path,mode,encoding='utf8')
    def stat(self,path):return os.stat(path)
    def close(self):pass
class Remote:
    def __init__(self,base,profile,queue='',processes=''):
        self.folder=Path(base);self.profile=profile
        self.queue=queue;self.processes=processes;self.commands=[]
        self.client=SimpleNamespace(open_sftp=lambda:LocalSFTP())
    def base(self,remote):return str(self.folder/remote)
    def exec_text(self,cmd):
        self.commands.append(cmd)
        if cmd.startswith('squeue'):return self.queue
        if cmd.startswith('ps '):return self.processes
        raise AssertionError('Unapproved command '+cmd)

def make_run(base,rid,state=None,rows=0,archive=False):
    d=base/'rvvlab-v5'/'test94-runs'/rid;d.mkdir(parents=True,exist_ok=True)
    if state:(d/'status94.json').write_text(json.dumps({'state':state,'rows':rows,'phase':'train'}))
    if archive:(d/'test94_results.zip').write_bytes(b'fake: only existence checked')
    return d

class TestRemoteInventory(unittest.TestCase):
    def test_never_run_no_remote_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            ssh=Remote(tmp,'Cloud-V')
            val=status.remote_inventory(ssh,'Cloud-V')
            self.assertEqual(val['state'],'missing');self.assertEqual(ssh.commands,[])

    def test_completed_persisted_result_on_server_no_local_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_run(Path(tmp),RID1,'completed',100,archive=True)
            ssh=Remote(tmp,'Cloud-V')
            val=status.remote_inventory(ssh,'Cloud-V')
            self.assertEqual(val['state'],'completed')
            self.assertEqual(val['run_id'],RID1)
            self.assertFalse(any('rm ' in s or 'sbatch' in s for s in ssh.commands))

    def test_running_cloudv_process_is_not_confused_with_stale_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=make_run(Path(tmp),RID1,'running',40)
            active=Remote(tmp,'Cloud-V',processes='python3 /home/test94_native.py all --output '+str(d)+' --seconds 3600')
            dead=Remote(tmp,'Cloud-V')
            self.assertEqual(status.remote_inventory(active,'Cloud-V')['state'],'running')
            self.assertEqual(status.remote_inventory(dead,'Cloud-V')['state'],'warning')

    def test_queued_slurm_job_and_prior_failed_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=make_run(Path(tmp),RID2)
            queue='rvvlab-test94|PENDING|'+str(d)+'\n'
            self.assertEqual(status.remote_inventory(Remote(tmp,'EPCC',queue=queue),'EPCC')['state'],'queued')
            self.assertEqual(status.remote_inventory(Remote(tmp,'EPCC'),'EPCC')['state'],'warning')

    def test_previous_completed_does_not_get_hidden_by_new_failed_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_run(Path(tmp),RID1,'completed',300,archive=True)
            make_run(Path(tmp),RID2,'failed')
            v=status.remote_inventory(Remote(tmp,'Cloud-V'),'Cloud-V')
            self.assertEqual(v['state'],'completed')
            self.assertIn('older than latest attempt',v['detail'])

    def test_failed_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_run(Path(tmp),RID2,'failed')
            self.assertEqual(status.remote_inventory(Remote(tmp,'EPCC'),'EPCC')['state'],'failed')

    def test_live_slurm_beats_old_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_run(Path(tmp),RID1,'completed',300,archive=True)
            d=make_run(Path(tmp),RID2)
            q='rvvlab-test94|RUNNING|'+str(d)+'\n'
            self.assertEqual(status.remote_inventory(Remote(tmp,'EPCC',queue=q),'EPCC')['state'],'running')

    def test_cache_keeps_source_target_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'CloudV';b=Path(tmp)/'EPCC'
            status.write_inventory(a,'Cloud-V',{'state':'completed','detail':'100 rows'})
            status.write_inventory(b,'EPCC',{'state':'missing','detail':'none'})
            self.assertEqual(status.cached_inventory(a)['state'],'completed')
            self.assertEqual(status.cached_inventory(b)['state'],'missing')

if __name__=='__main__':unittest.main(verbosity=2)
