"""Offline pre-release checks: no network, no remote SSH, no Slurm actions."""
from pathlib import Path
import json,sys,tempfile,unittest,hashlib,importlib.util,zipfile

ROOT=Path(__file__).resolve().parents[2]
TOOLS=ROOT/'tools'
def mod(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o);return o
class Test106Release(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker=mod('test106_native',TOOLS/'test106_native.py')
        cls.package=ROOT/'release_candidates/vectorpath_a2_rc_20261018/vectorpath_rc_sources.zip'
    def test_release_overlay_and_immutable_old_engine(self):
        old=ROOT/'engine'
        self.worker.verify_source(old)
        self.assertTrue(self.worker.verify_candidate_package(old,self.package))
        fingerprint=self.worker.sha(old/'src/rvv/engines/engine_plan.h')
        with tempfile.TemporaryDirectory() as folder:
            candidate=Path(folder)/'candidate'
            info=self.worker.prepare_candidate(old,candidate,self.package)
            self.assertEqual(info['manifest']['schema'],1)
            self.assertNotEqual(self.worker.sha(candidate/'src/rvv/engines/engine_plan.h'),fingerprint)
            self.assertEqual(self.worker.sha(old/'src/rvv/engines/engine_plan.h'),fingerprint)
            self.assertIn('#define SIMDJSON_RVV_ADAPTIVE_V2_LEVEL 2',(candidate/'src/rvv/engines/engine_plan.h').read_text())
    def test_refuse_modified_legacy_base(self):
        with tempfile.TemporaryDirectory() as folder:
            orig=ROOT/'engine';p=Path(folder)/'changed';(p/'src/rvv/engines').mkdir(parents=True)
            (p/'src/rvv/engines/engine_plan.h').write_text('altered')
            with self.assertRaisesRegex((RuntimeError,FileNotFoundError),'mismatch|No such file'):
                self.worker.verify_candidate_package(p,self.package)
    def test_paired_summary_returns_expected_five_variants(self):
        data=[]
        for name,dom,s1,s2 in [('OFFICIAL_504',1,1,1),('A2_ORIGINAL',2,2,2),('VP_STABLE',2,2,2),('VP_SIMPLE',2.2,2,3),('VP_NL4',2.5,2,4)]:
            data.append(dict(phase='confirm',stratum='public_original',document='demo',round_=0,
                family='public',variant=name,dom_gbps=dom,stage1_gbps=s1,stage2_gbps=s2))
            data[-1]['round']=data[-1].pop('round_')
        summary=self.worker.calculate(data)
        comp=summary['confirm/public_original/public']
        self.assertAlmostEqual(comp['VP_STABLE']['A2_ORIGINAL']['dom_gbps']['geomean_ratio'],1)
        self.assertAlmostEqual(comp['VP_SIMPLE']['A2_ORIGINAL']['dom_gbps']['geomean_ratio'],1.1)
        self.assertAlmostEqual(comp['VP_NL4']['VP_STABLE']['stage2_gbps']['geomean_ratio'],2)
        self.assertAlmostEqual(comp['VP_STABLE']['OFFICIAL_504']['dom_gbps']['geomean_ratio'],2)
    def test_studio_manifest_and_remote_result_paths(self):
        manifest=json.loads((ROOT/'studio/test_scripts/106_vectorpath_release.test.json').read_text())
        self.assertEqual(manifest['id'],'test106-vectorpath-release-validation')
        self.assertEqual(manifest['params']['max_seconds'],7200)
        for part in ('rvvlab_simple_tests.py','rvvlab_epcc_results.py','rvvlab_unified_campaigns.py'):
            self.assertIn('106',(ROOT/'studio'/part).read_text())
        self.assertIn("'VP_STABLE'",(ROOT/'tools/test106_native.py').read_text())
        self.assertIn('candidate-package',(ROOT/'studio/test_scripts/106_vectorpath_release.py').read_text())
    def test_failure_archive_not_success(self):
        import zipfile
        diagnostic=mod('test106_diagnostic',TOOLS/'test106_diagnostic.py')
        download=mod('rvvlab_test106_download',ROOT/'studio/rvvlab_test106_download.py')
        with tempfile.TemporaryDirectory() as tmp:
            prev=sys.argv
            sys.argv=['diagnostic','--output',tmp,'--reason','test failure']
            try:diagnostic.main()
            finally:sys.argv=prev
            archive=Path(tmp)/'test106_results.zip'
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(json.loads(z.read('status106.json'))['state'],'failed')
            download.check_zip(archive,expected_state=None)
            with self.assertRaisesRegex(RuntimeError,'completed'):
                download.check_zip(archive,expected_state='completed')
if __name__=='__main__':unittest.main()
