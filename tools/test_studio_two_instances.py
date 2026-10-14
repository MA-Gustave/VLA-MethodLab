#!/usr/bin/env python3
"""Offline tests for two simultaneous, isolated, machine-pinned Lab Studios."""
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_parallel import MachineLock, separate_results_paths

class TwoInstancesTests(unittest.TestCase):
    def test_locks_same_machine_blocked_other_machine_allowed(self):
        with tempfile.TemporaryDirectory() as folder:
            a=MachineLock(Path(folder)); b=MachineLock(Path(folder)); c=MachineLock(Path(folder))
            try:
                self.assertTrue(a.acquire('Cloud-V'))
                self.assertFalse(b.acquire('Cloud-V'))
                self.assertTrue(c.acquire('EPCC'))
                self.assertFalse(a.switch('EPCC'))
                self.assertEqual(a.profile,'Cloud-V')
            finally:a.release();b.release();c.release()
            self.assertTrue(b.acquire('Cloud-V'))
            b.release()

    def test_locks_cross_process(self):
        with tempfile.TemporaryDirectory() as folder:
            a=MachineLock(Path(folder))
            self.assertTrue(a.acquire('Cloud-V'))
            script='''from pathlib import Path
import sys
from rvvlab_parallel import MachineLock
x=MachineLock(Path(sys.argv[1]));print('OK' if x.acquire(sys.argv[2]) else 'BLOCKED');x.release()'''
            env=os.environ.copy()
            env['PYTHONPATH']=str(ROOT/'studio')+os.pathsep+env.get('PYTHONPATH','')
            try:
                r=subprocess.check_output([sys.executable,'-c',script,folder,'Cloud-V'],env=env,text=True).strip()
                self.assertEqual(r,'BLOCKED')
                r=subprocess.check_output([sys.executable,'-c',script,folder,'EPCC'],env=env,text=True).strip()
                self.assertEqual(r,'OK')
            finally:a.release()

    def test_results_paths_distinct(self):
        self.assertFalse(separate_results_paths({'Cloud-V':'~/RVV_Lab_results','EPCC':'~/RVV_Lab_results'}))
        self.assertTrue(separate_results_paths({'Cloud-V':'~/RVV_Lab_results','EPCC':'~/RVV_Lab_results/EPCC'}))

    def test_two_settings_paths_are_independent(self):
        script='from rvvlab_backend import SETTINGS_PATH;print(SETTINGS_PATH.name)'
        env=os.environ.copy();env['PYTHONPATH']=str(ROOT/'studio')+os.pathsep+env.get('PYTHONPATH','')
        actual=[]
        for name in ('Cloud-V','EPCC'):
            env['RVVLAB_STUDIO_TARGET']=name
            actual.append(subprocess.check_output([sys.executable,'-c',script],env=env,text=True).strip())
        self.assertEqual(actual,['settings_cloudv.json','settings_epcc.json'])

    def test_launcher_and_source_still_present(self):
        for name in ('CLOUDV','EPCC'):
            script=(ROOT/f'LANCER_STUDIO_{name}.pyw').read_text('utf-8')
            self.assertIn('RVVLAB_STUDIO_TARGET',script)
        self.assertTrue((ROOT/'studio/test_scripts/94_machine_1h.py').exists())
        self.assertTrue((ROOT/'engine/include/simdjson/rvv/intrinsics.h').exists())

if __name__=='__main__':unittest.main(verbosity=2)
