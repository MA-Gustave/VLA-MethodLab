"""Regression: Test 104 must be installable from a real snapshot, not just show in UI."""
import unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
STUDIO=ROOT/'studio'
if str(STUDIO) not in sys.path:sys.path.insert(0,str(STUDIO))
from rvvlab_test_runner import discover
from rvvlab_simple_tests import test_id,PROFILES
from rvvlab_epcc_results import RUN_TYPES

class Test104Recovery(unittest.TestCase):
    def test_manifest_discovered_and_ready(self):
        found,errors=discover(STUDIO/'test_scripts')
        self.assertFalse(any('104_' in e for e in errors),errors)
        target=[x for x in found if x['id']=='test104-independent-public-validation']
        self.assertEqual(len(target),1)
        self.assertTrue(target[0]['enabled'])
        self.assertTrue(target[0]['script_path'].is_file())
        self.assertEqual(target[0]['script_path'].name,'104_escape_stage.py')
        self.assertEqual(PROFILES['104'],('Cloud-V','EPCC'))
        self.assertEqual(test_id('104','Cloud-V'),target[0]['id'])
        self.assertEqual(test_id('104','EPCC'),target[0]['id'])
    def test_all_remote_launch_files_present(self):
        expected=('test104_native.py','test104_split.cpp','test104_stage2_patch.py',
          'test104_epcc_build.py','test104_epcc.sbatch','test104_cloudv.sh','test104_diagnostic.py')
        for fname in expected:self.assertTrue((ROOT/'tools'/fname).is_file(),fname)
        self.assertTrue((STUDIO/'rvvlab_test104_download.py').is_file())
    def test_epcc_results_manifest(self):
        self.assertIn('test104',RUN_TYPES)
        item=RUN_TYPES['test104']
        self.assertEqual(item['test_id'],'test104-independent-public-validation')
        self.assertEqual(item['directory'],'test104-epcc-runs')
        self.assertEqual(item['archive'],'test104_results.zip')
        self.assertIn('test103',RUN_TYPES)
if __name__=='__main__':unittest.main()
