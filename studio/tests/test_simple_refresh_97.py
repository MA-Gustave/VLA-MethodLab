"""Offline regression checks for status transparency and duplicate prevention."""
import json, tempfile, unittest, sys, subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rvvlab_simple_tests import (_local_attempt,_describe_local,_remote_test97_processes,
                                   SimpleTestsPanel,TEST_IDS)

class FakeSSH:
    def exec_text(self,command):
        completed=subprocess.run(command,shell=True,check=True,capture_output=True,text=True)
        return completed.stdout

class WorkflowFixTests(unittest.TestCase):
    def test_no_local_attempt_is_not_a_remote_success(self):
        with tempfile.TemporaryDirectory() as p:
            self.assertIsNone(_local_attempt(p,'97'))
            self.assertIn('Aucun lancement distant',_describe_local(None,False))

    def test_local_failed_before_remote_folder(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)/'TestRunner'/TEST_IDS['97']/'20261015T183600Z'
            root.mkdir(parents=True)
            (root/'runner.log').write_text('START test97-cloudv-8h\nFAIL: RuntimeError(\'source missing\')\n')
            state=_local_attempt(p,'97')
            self.assertEqual(state['state'],'failed_local')
            self.assertIn('source missing',state['detail'])
            self.assertIn('Échec',_describe_local(state,False))

    def test_local_launcher_still_working_no_remote_folder(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)/'TestRunner'/TEST_IDS['97']/'20261015T183600Z'
            root.mkdir(parents=True)
            (root/'runner.log').write_text('START test97-cloudv-8h\nSFTP: 10%\n')
            self.assertEqual(_local_attempt(p,'97')['state'],'started_local')
            self.assertIn('Studio prépare',_describe_local(None,True))

    def test_preflight_fails_are_saved(self):
        with tempfile.TemporaryDirectory() as p:
            root=Path(p)/'TestRunner'/TEST_IDS['97'];root.mkdir(parents=True)
            (root/'last_failure.json').write_text(json.dumps({
                'state':'failed','utc':'2099-10-15T18:36:00+00:00','error':'Permission refused'}))
            state=_local_attempt(p,'97')
            self.assertEqual(state['state'],'failed_local')
            self.assertIn('Permission refused',state['detail'])

    def test_process_probe_reports_no_false_self_match(self):
        self.assertEqual(_remote_test97_processes(FakeSSH()),[])

if __name__=='__main__':unittest.main()
