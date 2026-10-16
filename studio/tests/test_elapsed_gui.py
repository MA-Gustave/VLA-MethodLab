import datetime as dt
import pathlib
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from rvvlab_simple_tests import SimpleTestsPanel

class FakeRunner:
    busy=False
    def clear_verified_campaigns(self):pass
class FakeSsh:
    def connected(self):return True
class FakeStudio:
    def __init__(self,tkroot,results):
        self.active_profile='Cloud-V'
        self.test_runner=FakeRunner()
        self.unified_campaigns=None
        self.ssh=FakeSsh()
        self.vars={'results':tk.StringVar(master=tkroot,value=str(results)),
                   'remote_name':tk.StringVar(master=tkroot,value='rvvlab-v5')}

class GraphicElapsed(unittest.TestCase):
    def test_main_panel_elapsed_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=tk.Tk();root.withdraw()
            try:
                frame=ttk.Frame(root);frame.pack()
                panel=SimpleTestsPanel(frame,FakeStudio(root,tmp))
                now=dt.datetime.now(dt.timezone.utc)
                start=(now-dt.timedelta(hours=2,minutes=15)).isoformat()
                r={'id':'test97-20261015T190032Z-af59bc', 'state':'running',
                   'started_utc':start,'rows':1234,'packet':False,'validated':False,'proof':'test'}
                panel.runs={'97':[r]};panel.remote_checked=True
                panel.tree.selection_set('97')
                panel._selected()
                self.assertIn('Elapsed: 2h 15m',panel.elapsed.get())
                self.assertIn('2h 15m',panel.history_tree.set(r['id'],'elapsed'))
                self.assertEqual(str(panel.run_button.cget('state')),'disabled')
                # EPCC build can give estimated elapsed from the run ID alone
                panel.profile='EPCC'; panel.studio.active_profile='EPCC'
                panel.runs={'99':[{'id':'test99-20261016T031241Z-839a48',
                                   'state':'building','rows':0,'packet':False,'validated':False}]}
                panel.tree.delete(*panel.tree.get_children())
                panel.tree.insert('','end',iid='99',values=('99','EPCC',''))
                panel.tree.selection_set('99');panel._selected()
                self.assertIn('Elapsed: ≈',panel.elapsed.get())
            finally:root.destroy()

if __name__=='__main__':unittest.main()
