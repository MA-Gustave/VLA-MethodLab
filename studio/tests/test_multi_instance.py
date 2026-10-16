"""Non-network regression tests for dedicated Cloud-V / EPCC Studio windows."""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
import json
from pathlib import Path
import tempfile
import sys
import tkinter as tk
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))


def load_gui():
    spec = importlib.util.spec_from_loader('rvvlab_multi_test',
             SourceFileLoader('rvvlab_multi_test', str(HERE/'RVV_Lab_Studio.pyw')))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MultiInstanceTests(unittest.TestCase):
    def test_settings_first_run_migrates_read_only_and_then_isolated(self):
        gui=load_gui()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            common=base/'settings.json'
            epcc=base/'settings_epcc.json'
            old={'machine_profile':'Cloud-V','machine_epcc_env':str(base/'existing_epcc.env'),
                 'machine_epcc_results':str(base/'EPCC_results'),
                 'machine_primary_results':str(base/'CloudV_results')}
            common.write_text(json.dumps(old),encoding='utf-8')
            with mock.patch.object(gui,'TARGET','EPCC'),mock.patch.object(gui,'SETTINGS_PATH',epcc):
                self.assertEqual(gui.read_previous_settings(),old)
                self.assertFalse(epcc.exists())  # no write to common prefs or early migration
                epcc.write_text(json.dumps({'machine_profile':'EPCC','machine_epcc_env':'dedicated'}), encoding='utf-8')
                self.assertEqual(gui.read_previous_settings()['machine_epcc_env'],'dedicated')
                self.assertEqual(json.loads(common.read_text(encoding='utf-8')),old)

    def test_two_machine_locks_are_independent(self):
        from rvvlab_parallel import MachineLock
        with tempfile.TemporaryDirectory() as temp:
            with mock.patch('rvvlab_parallel.Path.home',return_value=Path(temp)):
                a,b,c=MachineLock(),MachineLock(),MachineLock()
                try:
                    self.assertTrue(a.acquire('Cloud-V'))
                    self.assertTrue(b.acquire('EPCC'))
                    self.assertFalse(c.acquire('Cloud-V'))
                finally:
                    a.release();b.release();c.release()

    def test_epcc_new_window_loads_legacy_epcc_profile(self):
        gui=load_gui()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            (base/'settings.json').write_text(json.dumps({
                'machine_profile':'Cloud-V',
                'machine_epcc_env':str(base/'my-epcc.env'),
                'machine_epcc_results':str(base/'epcc_results'),
                'machine_primary_results':str(base/'cloud_results'),
                'remote_name':'rvvlab-v5',
            }),encoding='utf8')
            with mock.patch.object(gui,'TARGET','EPCC'), mock.patch.object(gui,'SETTINGS_PATH',base/'settings_epcc.json'):
                root=tk.Tk();root.withdraw()
                try:
                    studio=gui.Studio(root)
                    self.assertEqual(studio.machine_choice.get(),'EPCC')
                    self.assertEqual(studio.vars['env_path'].get(),str(base/'my-epcc.env'))
                    self.assertEqual(studio.vars['results'].get(),str(base/'epcc_results'))
                    self.assertEqual(studio.machine_results['Cloud-V'],str(base/'cloud_results'))
                    self.assertFalse((base/'settings_epcc.json').exists())
                finally:
                    root.destroy()

    def test_launcher_has_target_and_reuses_original(self):
        root=HERE.parent
        for f,target in [('LAUNCH_STUDIO_CLOUDV.bat','Cloud-V'),('LAUNCH_STUDIO_EPCC.bat','EPCC')]:
            txt=(root/f).read_text(encoding='ascii')
            self.assertIn(f'RVVLAB_STUDIO_TARGET={target}',txt)
            self.assertIn('call "%~dp0LAUNCH_RVV_VLA_LAB.bat"',txt)
            self.assertNotIn('taskkill',txt.lower())


if __name__=='__main__':unittest.main()
