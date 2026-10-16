"""Desktop UI regression tests. Requires a display (Tk on Windows or xvfb-run)."""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys,tkinter as tk,unittest
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))

class WorkspaceRefonteTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_loader('rvvlab_refonte_test',
             SourceFileLoader('rvvlab_refonte_test',str(BASE/'RVV_Lab_Studio.pyw')))
        mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
        self.root=tk.Tk()
        self.app=mod.Studio(self.root)
        self.root.update_idletasks()
        self.panel=self.app.simple_tests

    def tearDown(self):
        self.root.destroy()

    def _ready(self, number, rows):
        class FakeSSH:
            def connected(self):return True
        self.app.ssh=FakeSSH()
        self.panel.remote_checked=True
        self.panel.last_check_error=None
        self.panel.runs={number:rows}
        self.panel.tree.selection_set(number)
        self.panel._selected()

    def test_two_spaces_and_historical_navigation(self):
        self.assertEqual(len(self.app.notebook.tabs()),3)
        self.assertIn('JSON Corpus', self.app.notebook.tab(self.app.corpus_tab,'text'))
        self.assertEqual(len(self.app.advanced_notebook.tabs()),8)
        self.app.open_advanced(self.app.test_runner_tab)
        self.assertEqual(self.app.advanced_notebook.select(),str(self.app.test_runner_tab))

    def test_target_specific_test97(self):
        self.assertEqual(set(self.panel.tree.get_children()),{'94','95','97','98'})
        self.app.active_profile='EPCC';self.panel.profile_changed()
        self.assertEqual(set(self.panel.tree.get_children()),{'94','96','97','98'})
        self.panel.tree.selection_set('97');self.panel._selected()
        self.assertIn('3 hours',self.panel.test_descr.get())

    def test_active_blocks_run_and_has_amber_state(self):
        self._ready('97',[dict(id='test97-20261015T120000Z-abc123',state='building',
                         rows=121,packet=False,validated=False,proof='processus confirmé')])
        self.assertEqual(self.panel.banner.cget('bg'),'#FFF2CF')
        self.assertEqual(str(self.panel.run_button['state']),'disabled')
        self.assertEqual(str(self.panel.download_button['state']),'disabled')

    def test_done_needs_packet_and_validation(self):
        run=dict(id='test97-20261015T120000Z-abc123',state='completed',
                 rows=1600,packet=False,validated=True,proof='test')
        self._ready('97',[run])
        self.assertNotEqual(self.panel.banner.cget('bg'),'#E4F7EB')
        self.assertEqual(str(self.panel.download_button['state']),'disabled')
        run['packet']=True
        self.panel._selected()
        self.assertEqual(self.panel.banner.cget('bg'),'#E4F7EB')
        self.assertEqual(str(self.panel.download_button['state']),'normal')

    def test_old_completed_run_cannot_enable_second_launch_during_active_run(self):
        old=dict(id='test97-20261015T100000Z-abc123',state='completed',
                 rows=1500,packet=True,validated=True)
        new=dict(id='test97-20261015T120000Z-def456',state='building',
                 rows=51,packet=False,validated=False)
        self._ready('97',[new,old])
        self.panel.selection.set(old['id']);self.panel._selected()
        self.assertEqual(str(self.panel.run_button['state']),'disabled')
        self.assertEqual(str(self.panel.download_button['state']),'normal')

if __name__=='__main__':unittest.main()
