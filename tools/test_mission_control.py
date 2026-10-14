#!/usr/bin/env python3
"""Offline dashboard / command-safety checks. Never opens SSH."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'studio'))
from rvvlab_dashboard import fresh,next_action,preset_command,summary_text

class MissionControlTests(unittest.TestCase):
    def record(self,state='running',age=0,verified=True):
        return {'state':state,'updated_utc':(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(), 'verified':verified}
    def test_freshness(self):
        self.assertTrue(fresh(self.record(age=50)))
        self.assertFalse(fresh(self.record(age=500)))
        self.assertFalse(fresh(self.record(verified=False)))
        self.assertFalse(fresh({'state':'running','verified':True,'updated_utc':'BAD'}))
    def test_guidance(self):
        self.assertIn('Connect SSH',next_action('Cloud-V',False,None))
        self.assertIn('verify',next_action('EPCC',True,self.record(),False))
        self.assertIn('completed',next_action('Cloud-V',True,self.record('completed'),True))
        self.assertIn('do not start',next_action('Cloud-V',True,self.record('running'),True))
        self.assertIn('Wait',next_action('EPCC',True,self.record('queued'),True))
        self.assertIn('No remote',next_action('EPCC',True,self.record('missing'),True))
        self.assertIn('failed',next_action('Cloud-V',True,self.record('failed'),True))
        self.assertIn('Checking',next_action('EPCC',True,None,False,True))
    def test_read_only_diagnostics(self):
        names=['Test 94 statuses','Test 94 processes','System / architecture','Disk space']
        names+=['Slurm jobs (EPCC)','Slurm nodes (EPCC)']
        for name in names:
            command=preset_command(name,'EPCC','rvvlab-v5')
            for forbidden in ['sbatch','scancel','srun ','rm -','sudo ','kill ','chmod ','export ','eval ','curl ','wget ']:
                self.assertNotIn(forbidden,command)
        with self.assertRaises(ValueError):preset_command('Slurm nodes (EPCC)','Cloud-V','rvvlab-v5')
        with self.assertRaises(ValueError):preset_command('Test 94 statuses','EPCC','repo; rm -rf ~')
    def test_safe_clipboard_no_details(self):
        private={'state':'running','detail':'PASSWORD=NEVERLOG','host':'secret.example.com'}
        text=summary_text('EPCC',True,private,private)
        self.assertNotIn('PASSWORD',text)
        self.assertNotIn('secret.example.com',text)
        self.assertIn('Cloud-V',text)
if __name__=='__main__':unittest.main(verbosity=2)
