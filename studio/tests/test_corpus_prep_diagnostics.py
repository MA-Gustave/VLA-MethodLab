"""Regression for corpus UI queue and durable diagnostics, no network required."""
import io
import queue
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import rvvlab_corpus_panel as panel
import rvvlab_corpus_service as svc

class Value:
    def __init__(self):self.value=None
    def set(self,v):self.value=v

class DrainRegression(unittest.TestCase):
    def setup_fake(self):
        p=object.__new__(panel.CorpusLibraryPanel)
        p.parent=types.SimpleNamespace(calls=[],after=lambda *args:None)
        p.events=queue.Queue();p.busy=True
        p.suite=types.SimpleNamespace(get=lambda:'conformance')
        p.notice=Value();p.local=Value();p.remote=Value()
        p.per_machine={('Cloud-V','conformance'):'Non verified'}
        p.studio=types.SimpleNamespace(active_profile='Cloud-V')
        p.inspect=lambda:None
        p.parent.after=lambda *args:p.parent.calls.append(args)
        return p
    def test_empty_poll_always_rearms_without_nameerror(self):
        p=self.setup_fake();p._drain()
        self.assertEqual(len(p.parent.calls),1)
        self.assertEqual(p.parent.calls[0][0],250)
    def test_prepare_failure_surfaces_error(self):
        p=self.setup_fake()
        p.events.put(('progress','Cloud-V','conformance','Téléchargement…',None))
        p.events.put(('prepare','Cloud-V','conformance',None,'GitHub non accessible | Log: : .cache/...'))
        p._drain()
        self.assertFalse(p.busy)
        self.assertIn('GitHub non accessible',p.notice.value)
        self.assertIn('Preparation failed',p.local.value)
        self.assertEqual(len(p.parent.calls),1)
    def test_prepare_success_surfaces_and_rearms(self):
        p=self.setup_fake()
        p.events.put(('prepare','Cloud-V','conformance',{'state':'verified'},None))
        p._drain()
        self.assertFalse(p.busy)
        self.assertIn('verified',p.notice.value)
        self.assertEqual(len(p.parent.calls),1)
    def test_failed_download_writes_persistent_journal(self):
        with tempfile.TemporaryDirectory() as temp:
            lab=Path(temp)/'lab';lab.mkdir()
            bad=types.SimpleNamespace(returncode=1,stderr='URLError: unable to resolve codeload.github.com',stdout='')
            with patch.object(svc.subprocess,'run',return_value=bad):
                with self.assertRaisesRegex(RuntimeError,'Log:'):
                    svc.prepare_local(lab,suite='conformance')
            log=svc.cache_dir(lab)/'preparation-conformance.log'
            self.assertTrue(log.is_file())
            self.assertIn('URLError',log.read_text(encoding='utf8'))
            self.assertEqual(svc.inspect_local(lab,'conformance')['state'],'absent')
if __name__=='__main__':unittest.main()
