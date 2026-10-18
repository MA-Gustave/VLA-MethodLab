"""Offline Test 104 corpus-provenance, download, summary and routing tests."""
import hashlib,importlib.util,json,zipfile,tempfile,unittest,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
class Test104(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker=load(ROOT/'tools/test104_native.py','test104_native')
        cls.down=load(ROOT/'studio/rvvlab_test104_download.py','test104_download')
    def test_pinned_official_suite_full_classes_raw_bytes(self):
        w=self.worker
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);records=[]
            for i in range(204):
                label=('y','n','i')[i%3]
                name=f'test_parsing/{label}_example_{i:03}.json'
                raw={'y':b'{"key":"value"}','n':b'{"key":}','i':b'\xff\x00'}[label]
                p=root/'files'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
                records.append({'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                'expected':{'y':'accept','n':'reject','i':'implementation'}[label]})
            m={'schema':1,'corpus_id':w.CONFORMANCE_ID,'upstream_commit':w.CONFORMANCE_COMMIT,'files':records}
            (root/'manifest.json').write_text(json.dumps(m))
            man,got,accepted=w.conformance_verify(root)
            self.assertEqual(len(got),204);self.assertEqual(len(accepted),68)
            self.assertEqual((root/'files'/'test_parsing/i_example_002.json').read_bytes(),b'\xff\x00')
            (root/'files'/'test_parsing/y_example_000.json').write_bytes(b'\x00')
            with self.assertRaisesRegex(RuntimeError,'hash mismatch'):w.conformance_verify(root)
            m['upstream_commit']='bad';(root/'manifest.json').write_text(json.dumps(m))
            with self.assertRaisesRegex(RuntimeError,'provenance mismatch'):w.conformance_verify(root)
    def test_jsonsuite_excluded_from_synthetic_summary(self):
        w=self.worker
        rows=[]
        for name,dom in (('OFFICIAL_504',1.),('A2_G16384',1.5),('A2_SIMPLE_RUN',1.7),('A2_NL4',1.4)):
            rows.append({'phase':'confirm','stratum':'jsonsuite_valid','document':'jsonsuite/test_parsing/y_a.json','round':1,'family':'official_y','variant':name,
             'dom_gbps':dom,'stage1_gbps':dom,'stage2_gbps':dom})
        got=w.calculate(rows)
        self.assertIn('confirm/jsonsuite_valid/official_y',got)
        self.assertAlmostEqual(got['confirm/jsonsuite_valid/official_y']['A2_SIMPLE_RUN']['A2_G16384']['dom_gbps']['geomean_ratio'],1.7/1.5)
    def test_download_error_and_success_filelist(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'test104_results.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('status104.json',json.dumps({'state':'completed','validated':True,'rows':40}))
                z.writestr('REPORT_104.md','Done')
                z.writestr('conformance104.json','{}')
            self.down.check_zip(p,expected_state='completed')
            with zipfile.ZipFile(p,'a') as z:z.writestr('../x','bad')
            with self.assertRaisesRegex(RuntimeError,'unexpected'):self.down.check_zip(p)
    def test_studio_103_and_104_coexist(self):
        s=(ROOT/'studio/rvvlab_simple_tests.py').read_text()
        self.assertIn("'103': ('Cloud-V','EPCC')",s)
        self.assertIn("'104': ('Cloud-V','EPCC')",s)
        self.assertIn("'104':'104_escape_stage.py'",s)
        e=(ROOT/'studio/rvvlab_epcc_results.py').read_text()
        self.assertIn("'test104': dict(",e)
        self.assertIn("'test103': dict(",e)
    def test_launcher_reuses_public_manager_only_verified_suite(self):
        s=(ROOT/'studio/test_scripts/104_escape_stage.py').read_text()
        self.assertIn("inspect_local(LAB,'conformance')",s)
        self.assertIn("suite='conformance'",s)
        self.assertIn("TEST104_CONFORMANCE",s)
        m=json.loads((ROOT/'studio/test_scripts/104_escape_stage.test.json').read_text())
        self.assertEqual(m['id'],'test104-independent-public-validation')
if __name__=='__main__':unittest.main()
