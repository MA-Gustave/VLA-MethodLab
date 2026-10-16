"""Corpus log dialog: run with xvfb-run on Linux or a Windows desktop."""
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
import tkinter as tk
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rvvlab_corpus_panel as panel_module

class CorpusLogWindowTests(unittest.TestCase):
    def setUp(self):
        try:self.root=tk.Tk()
        except tk.TclError:self.skipTest('No graphical display available')
        self.root.withdraw()
        self.temp=tempfile.TemporaryDirectory()
        self.fake_lab=Path(self.temp.name)
        (self.fake_lab/'.cache'/'corpus-library').mkdir(parents=True)
        self.mocklab=patch.object(panel_module,'LAB',self.fake_lab)
        self.mocklab.start()
        studio=types.SimpleNamespace(active_profile='Cloud-V',ssh=types.SimpleNamespace(connected=lambda:False),connecting=False)
        self.p=panel_module.CorpusLibraryPanel(self.root,studio)
        self.p.suite.set('conformance')
        self.p.selector.set(panel_module.SUITE_LABELS['conformance'])
        self.p.profile_changed()

    def tearDown(self):
        if hasattr(self,'p'):self.p._close_diagnostic()
        if hasattr(self,'root'):self.root.destroy()
        if hasattr(self,'mocklab'):self.mocklab.stop()
        if hasattr(self,'temp'):self.temp.cleanup()

    def test_dialog_displays_complete_error_and_copy(self):
        logfile=self.p._diagnostic_path('conformance')
        full="[UTC] Traceback (most recent call last):\n File x.py, line 175\n urllib.error.URLError: test offline\n"
        logfile.write_text(full,encoding='utf8')
        self.p.open_diagnostic()
        self.assertTrue(self.p._journal_window.winfo_exists())
        self.assertEqual(self.p._journal_text.get('1.0','end-1c'),full)
        self.p._copy_diagnostic()
        self.assertEqual(self.root.clipboard_get(),full)
        self.assertIn('Copied',self.p._journal_status.get())
        self.p._close_diagnostic()

    def test_error_is_short_in_panel_and_opens_log(self):
        self.p.events.put(('prepare','Cloud-V','conformance',None,
            'Téléchargement impossible : Traceback (most recent call last)\nVERY LONG LINE'))
        self.p._drain()
        self.assertIn('failed',self.p.local.get())
        self.assertNotIn('Traceback',self.p.local.get())
        self.assertNotIn('Traceback',self.p.notice.get())
        self.assertTrue(self.p._journal_window.winfo_exists())
        self.assertIn('VERY LONG LINE',self.p._journal_text.get('1.0','end-1c'))

    def test_log_refreshes_after_file_changes(self):
        f=self.p._diagnostic_path('conformance')
        f.write_text('one',encoding='utf8')
        self.p.open_diagnostic()
        f.write_text('one\ntwo',encoding='utf8')
        self.p._refresh_diagnostic()
        self.assertEqual(self.p._journal_text.get('1.0','end-1c'),'one\ntwo')

if __name__=='__main__':unittest.main()
