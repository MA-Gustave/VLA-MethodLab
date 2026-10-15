"""Regression: Test98 routes to same managed UI without inventing server success."""
from pathlib import Path
import importlib.util, json, io, unittest, sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_simple_tests import PROFILES,test_id,manifest_target,_server_runs
from rvvlab_test_runner import discover
from test_epcc_results import FakeSSH,FakeSFTP,BASE
FakeSFTP.close=lambda self:None

class Check98Wiring(unittest.TestCase):
    def test_provides_both_profiles_same_manifest(self):
        self.assertEqual(PROFILES['98'],('Cloud-V','EPCC'))
        for p in PROFILES['98']:
            self.assertEqual(test_id('98',p),'test98-real-corpus')
        self.assertEqual(manifest_target('test98-real-corpus'),('98',('Cloud-V','EPCC')))
        items,errors=discover(ROOT/'studio/test_scripts')
        self.assertFalse(errors)
        self.assertEqual(len([x for x in items if x['id']=='test98-real-corpus']),1)

    def test_cloudv_unverified_or_no_zip_never_green(self):
        run='test98-20261015T210000Z-ab1234';folder=BASE+'/test98-cloudv-runs/'+run
        data={folder+'/status98.json':b'{"state":"completed","rows":700,"validated":true}'}
        r=_server_runs(FakeSSH(data),'rvvlab-v5','98','Cloud-V')
        self.assertEqual(len(r),1)
        self.assertEqual(r[0]['state'],'incomplete')
        self.assertFalse(r[0]['packet'])
        data[folder+'/test98_results.zip']=b'fakezip'
        r=_server_runs(FakeSSH(data),'rvvlab-v5','98','Cloud-V')
        self.assertEqual(r[0]['state'],'completed')
        self.assertTrue(r[0]['validated'])
        data[folder+'/status98.json']=b'{"state":"completed","rows":700,"validated":false}'
        r=_server_runs(FakeSSH(data),'rvvlab-v5','98','Cloud-V')
        self.assertEqual(r[0]['state'],'incomplete')

    def test_epcc_missing_validation_never_green(self):
        run='test98-20261015T210000Z-ab1234';folder=BASE+'/test98-epcc-runs/'+run
        data={folder+'/status98.json':b'{"state":"completed","rows":200}',folder+'/test98_results.zip':b'fakezip'}
        r=_server_runs(FakeSSH(data),'rvvlab-v5','98','EPCC')
        self.assertEqual(r[0]['state'],'incomplete')
        self.assertFalse(r[0]['validated'])
        data[folder+'/status98.json']=b'{"state":"completed","rows":200,"validated":true}'
        r=_server_runs(FakeSSH(data),'rvvlab-v5','98','EPCC')
        self.assertEqual(r[0]['state'],'completed')
        self.assertTrue(r[0]['validated'])

    def test_timing_loop_guard_does_not_abort_early(self):
        src=(ROOT/'tools/test98_native.py').read_text(encoding='utf-8')
        self.assertIn('if time.monotonic()>=deadline-20:break',src)
        self.assertNotIn('if deadline-time.monotonic()<deadline-20:break',src)

if __name__=='__main__':unittest.main()
