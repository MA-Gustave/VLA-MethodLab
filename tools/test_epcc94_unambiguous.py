#!/usr/bin/env python3
"""Mocked EPCC regression: no live connection and no Slurm jobs submitted."""
from __future__ import annotations
import io,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
HERE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(HERE/'studio'))
from rvvlab_epcc94_diagnostics import build_error_hint,pre_slurm_diagnosis,is_live_build
from rvvlab_test_center import inspect_remote_94,merge,label
from rvvlab_target_status import remote_probe,display
RUN='test94-20261013T233735Z-728f3a'
WD='/home/gustave/rvvlab-v5/test94-runs/'+RUN
LOG="""EPCC RVV1.0 compiler OK: /usr/local/share/riscv-compiler/llvm-16.0/build/bin/clang++
/home/gustave/rvvlab-v5/sources/latest/include/simdjson/rvv/intrinsics.h:21:7: error: cannot initialize a parameter of type '__rvv_uint8m2_t'
/home/gustave/rvvlab-v5/sources/latest/include/simdjson/rvv/intrinsics.h:30:10: error: use of undeclared identifier '__riscv_vcreate_v_u8m1_u8m4'
3 errors generated.
"""

class SFTP:
    def __init__(self,log='',status=None,finished=False):self.log=log;self.status=status;self.finished=finished
    def listdir(self,path):return [RUN]
    def open(self,path,mode='rb'):
        if path.endswith('status94.json'):
            if self.status is None:raise FileNotFoundError(path)
            return io.BytesIO(json.dumps(self.status).encode())
        if path.endswith('studio94-build.log') and self.log:return io.BytesIO(self.log.encode())
        raise FileNotFoundError(path)
    def stat(self,path):
        if path.endswith('studio94-build.log') and self.log:return SimpleNamespace(st_size=len(self.log))
        if path.endswith('test94_results.zip') and self.finished:return SimpleNamespace(st_size=1024)
        raise FileNotFoundError(path)
    def close(self):pass

class SSH:
    def __init__(self,log='',status=None,squeue='',ps='',finished=False):
        self.fs=SFTP(log,status,finished);self.q=squeue;self.ps=ps;self.commands=[]
        self.client=SimpleNamespace(open_sftp=lambda:self.fs)
    def base(self,root):return '/home/gustave/rvvlab-v5'
    def exec_text(self,cmd):
        self.commands.append(cmd)
        if cmd.startswith('squeue '):return self.q
        if cmd.startswith('ps '):return self.ps
        if 'status94.json' in cmd:return json.dumps(self.fs.status or {})
        return ''

class EPCCStatuses(unittest.TestCase):
    def launch(self):return {'id':RUN,'mode':'EPCC','workdir':WD,'started_utc':'2026-10-13T23:37:35Z'}
    def test_previous_clang16_failed_no_slurm(self):
        ssh=SSH(LOG)
        r=inspect_remote_94(ssh,'rvvlab-v5','EPCC')
        self.assertEqual(r['state'],'failed',r)
        self.assertIn('compilation',r['proof'].lower())
        self.assertIn('error:',r['proof'])
        self.assertTrue(any('squeue' in x for x in ssh.commands))
        self.assertTrue(any('ps ' in x for x in ssh.commands))
        self.assertFalse(any('sbatch ' in x for x in ssh.commands))
        merged=merge({'state':'unknown','proof':'nothing','downloaded':False,'run_id':'','directory':''},r)
        self.assertEqual(merged['state'],'failed');self.assertIn('clang++',LOG)
        self.assertIn('ÉCHEC',label(merged['state']))
        badge_state,badge_detail=remote_probe(ssh,self.launch())
        self.assertEqual(badge_state,'failed')
        self.assertIn('Échec compilation',badge_detail)
    def test_current_crossbuild_is_building_not_slurm_queued(self):
        process='python3 /home/gustave/rvvlab-v5/test94-tools/test94_epcc_build.py /src '+WD+' /native /log'
        ssh=SSH('',ps=process)
        r=inspect_remote_94(ssh,'rvvlab-v5','EPCC')
        self.assertEqual(r['state'],'building')
        badge_state,_=remote_probe(ssh,self.launch())
        self.assertEqual(badge_state,'build')
    def test_job_pending_is_real_only_from_slurm(self):
        ssh=SSH('',squeue='rvvlab-test94|PENDING|'+WD+'\n')
        r=inspect_remote_94(ssh,'rvvlab-v5','EPCC')
        self.assertEqual(r['state'],'queued',r)
    def test_unknown_without_job_log_or_build_process(self):
        ssh=SSH('',status={'state':'build/queued','rows':0})
        r=inspect_remote_94(ssh,'rvvlab-v5','EPCC')
        self.assertEqual(r['state'],'unknown',r)
        self.assertIn('aucun job',r['proof'])
        self.assertEqual(remote_probe(ssh,self.launch())[0],'warning')
    def test_completed_needs_data_packet(self):
        ssh=SSH('',status={'state':'completed','rows':500},finished=True)
        self.assertEqual(inspect_remote_94(ssh,'rvvlab-v5','EPCC')['state'],'completed')
        ssh=SSH('',status={'state':'completed','rows':500},finished=False)
        self.assertEqual(inspect_remote_94(ssh,'rvvlab-v5','EPCC')['state'],'unknown')
    def test_foreign_process_does_not_create_build_state(self):
        self.assertFalse(is_live_build('python3 test94_epcc_build.py /someother/run',WD))
    def test_error_message_is_bounded(self):
        self.assertLessEqual(len(build_error_hint(LOG)),130)
        self.assertEqual(build_error_hint('compiler OK\n'),'')

if __name__=='__main__':unittest.main(verbosity=2)
