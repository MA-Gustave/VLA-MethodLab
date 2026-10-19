"""Test107 must be discoverable and actionable in the main Tests pane without SSH."""
from __future__ import annotations
from pathlib import Path
from unittest import mock
import importlib.util,sys,tempfile,tkinter as tk,unittest
from importlib.machinery import SourceFileLoader
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
from rvvlab_simple_tests import PROFILES,TEST_IDS,_test107_runs,_run_test107_audit

class Test107VisibleUI(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_loader('rvvlab_ui107_test',SourceFileLoader('rvvlab_ui107_test',str(BASE/'RVV_Lab_Studio.pyw')))
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        self.root=tk.Tk();self.studio=m.Studio(self.root);self.root.update_idletasks()
        self.panel=self.studio.simple_tests
    def tearDown(self):self.root.destroy()

    def test_visible_on_both_profiles_without_ssh(self):
        for profile in ('Cloud-V','EPCC'):
            self.studio.active_profile=profile;self.panel.profile_changed()
            self.assertTrue(self.panel.tree.exists('107'))
            self.panel.tree.selection_set('107');self.panel._selected()
            self.assertEqual(self.panel.tree.set('107','machine'),'LOCAL')
            self.assertEqual(str(self.panel.run_button['state']),'normal')
            self.assertEqual(str(self.panel.download_button['state']),'disabled')
            self.assertIn('No SSH',self.panel.test_descr.get())
            self.panel.refresh()
            self.assertIn('No SSH',self.panel.notice.get())

    def test_switching_to_remote_restores_remote_buttons(self):
        self.panel.tree.selection_set('107');self.panel._selected()
        self.assertIn('LOCAL',self.panel.run_button['text'])
        self.panel.tree.selection_set('106');self.panel._selected()
        self.assertNotIn('LOCAL',self.panel.run_button['text'])
        self.assertEqual(str(self.panel.run_button['state']),'disabled')

    def test_run_prompts_local_files_no_ssh(self):
        self.panel.tree.selection_set('107');self.panel._selected()
        filenames=iter(['cloudv.zip','epcc.zip'])
        with mock.patch('rvvlab_simple_tests.filedialog.askopenfilename',side_effect=lambda **_:next(filenames)), \
             mock.patch('rvvlab_simple_tests.messagebox.askyesno',side_effect=[False,True]), \
             mock.patch('rvvlab_simple_tests._run_test107_audit',return_value={'folder':'/tmp/fake','engine':'PASS','ship':'HOLD_CI_AND_RELEASE_SIGNOFF','rows':1}) as run:
            class ImmediateThread:
                def __init__(self,target,daemon):self.target=target
                def start(self):self.target()
            with mock.patch('rvvlab_simple_tests.threading.Thread',ImmediateThread):
                self.panel.run()
            self.assertEqual(run.call_args.args[:3],('cloudv.zip','epcc.zip',None))
            kind,payload=self.panel.events.get_nowait()
            self.assertEqual(kind,'local107')
            self.assertEqual(payload[0]['engine'],'PASS')

if __name__=='__main__':unittest.main()
