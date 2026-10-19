"""Tests of Test107 fail-closed semantics; do not need SSH or native RISC-V."""
import hashlib,importlib.util,io,json,pathlib,sys,unittest,zipfile,tempfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('t107_engine',ROOT/'tools'/'test107_release_audit.py')
T=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(T)
class Test107Gate(unittest.TestCase):
    def test_wrong_arch_raises(self):
        with self.assertRaises(T.AuditError):T.require(False,'wrong arch')
    def test_source_provenance_pins(self):
        self.assertEqual(len(T.EXPECTED_RC),64)
        self.assertEqual(len(T.EXPECTED_FORK),64)
    def test_official_commit_fixed(self):
        self.assertEqual(T.EXPECTED_UPSTREAM,'3b0b2b53aaffb46208817821dce2cd47a5e6bb2a')
    def test_missing_evidence_is_error(self):
        with self.assertRaises(T.AuditError):T.audit_one(ROOT/'missing106.zip','rvc02')
    def test_duplicate_zip_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)/'duplicate.zip'
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(p,'w') as z:
                    z.writestr('same.txt','one');z.writestr('same.txt','two')
            with zipfile.ZipFile(p) as z:
                with self.assertRaises(T.AuditError):T.collect(z,str(p))
    def test_ci_remains_pending_without_proof(self):
        self.assertIn('NOT_VERIFIED',T.report({'machines':{},'engine_qualification':'PASS',
         'ship_authorization':'HOLD_CI_AND_RELEASE_SIGNOFF','ci':{'state':'NOT_VERIFIED','note':'pending'},
         'sum_rows':0,'release_candidate_sha256':T.EXPECTED_RC,'vectorpath_package':{'sha256':None,'state':'NOT_PROVIDED'}}))
if __name__=='__main__':unittest.main()
