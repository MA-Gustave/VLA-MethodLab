"""Offline integration for immutable public JSONTestSuite and deterministic RVV fixtures."""
import hashlib,io,json,shlex,subprocess,sys,tempfile,unittest,zipfile,contextlib,shutil
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'studio'))
sys.path.insert(0,str(ROOT/'tools'))
import rvvlab_corpus_service as svc
import corpus_jsontestsuite as js
import corpus_rvv_stress as st
from test_shared_corpus_library import LocalSSH


def upstream_fixture():
    """Only a mock upstream payload. Never copied into distributed benchmark data."""
    prefix='JSONTestSuite-'+js.SOURCE_COMMIT+'/'
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w',zipfile.ZIP_DEFLATED) as z:
        for code,ct in [('y',100),('n',100),('i',25)]:
            for idx in range(ct):
                b={'y':b'{}','n':b'{','i':b'\xff'}[code]
                z.writestr(prefix+('test_parsing/n_structure_trailing_#.json' if code=='n' and idx==98 else f'test_parsing/{code}_test_{idx:03d}.json'),b)
        z.writestr(prefix+'test_transform/object.json',b'{}')
        z.writestr(prefix+'README.md',b'Unrelated')
    return data.getvalue()

class SuiteSSH(LocalSSH):
    def exec_text(self,command):
        argv=shlex.split(command)
        if len(argv)==5 and argv[0]=='python3' and argv[2]=='extract':
            manager=js if argv[1].endswith('corpus_jsontestsuite.py') else st
            with contextlib.redirect_stdout(io.StringIO()):
                manager.extract(self.resolve(argv[3]),self.resolve(argv[4]))
            return argv[4]+'/'+manager.CORPUS_ID
        return super().exec_text(command)

class CorpusMultisuiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.lab=Path(self.tmp.name)/'lab';self.lab.mkdir()
        self.server=SuiteSSH(Path(self.tmp.name)/'server')
    def add_js(self):
        with patch.object(js,'_download_pinned_archive',return_value=upstream_fixture()):
            js.prepare(svc.cache_dir(self.lab))
        result=svc.prepare_local(self.lab,suite='conformance')
        return result
    def test_suite_ids_and_corpus_98_legacy(self):
        self.assertEqual(set(svc.SUITES),{'performance','conformance','stress'})
        self.assertEqual(svc.catalog()['id'],svc.manager().CORPUS_ID)
        self.assertEqual(svc.catalog('conformance')['commit'],js.SOURCE_COMMIT)
    def test_prepare_verbatim_invalid_octets_and_classification(self):
        info=self.add_js();self.assertEqual(info['state'],'verified')
        self.assertEqual(info['count'],226)
        self.assertEqual(info['counts']['accept'],100)
        self.assertEqual(info['counts']['reject'],100)
        self.assertEqual(info['counts']['implementation'],25)
        with zipfile.ZipFile(info['archive']) as z:
            self.assertEqual(z.read('files/test_parsing/i_test_000.json'),b'\xff')
    def test_conformance_sync_reuse_and_tamper(self):
        self.add_js()
        a=svc.sync_remote(self.server,'rvvlab-v5',self.lab,suite='conformance')
        self.assertEqual(a['state'],'verified')
        self.assertTrue(self.server.resolve(a['data']+'/files/test_parsing/y_test_000.json').is_file())
        n=self.server.puts
        b=svc.sync_remote(self.server,'rvvlab-v5',self.lab,suite='conformance')
        self.assertEqual(self.server.puts,n)
        self.assertEqual(b['digest'],a['digest'])
        self.server.resolve(a['data']+'/files/test_parsing/n_test_000.json').write_bytes(b'X')
        with self.assertRaisesRegex(ValueError,'tampered'):
            svc.remote_probe(self.server,'rvvlab-v5',a['digest'],deep=True,suite='conformance')
    def test_stress_deterministic_and_exact_boundaries(self):
        a=svc.prepare_local(self.lab,suite='stress')
        self.assertEqual(a['count'],90)
        for item in a['files']:
            self.assertEqual(item['bytes'],item['target_bytes'])
        with tempfile.TemporaryDirectory() as another:
            b=svc.prepare_local(Path(another),suite='stress')
            self.assertEqual(a['digest'],b['digest'])
    def test_stress_sync_and_stable_manifest(self):
        svc.prepare_local(self.lab,suite='stress')
        a=svc.sync_remote(self.server,'rvvlab-v5',self.lab,suite='stress')
        self.assertEqual(a['count'],90)
        self.assertEqual(svc.require_remote(self.server,'rvvlab-v5',self.lab,suite='stress')['suite'],'stress')
    def test_manifest_supports_named_suite(self):
        from rvvlab_test_runner import discover
        d=self.lab/'scripts';d.mkdir()
        (d/'probe.py').write_text('def execute(ctx,params):return {}',encoding='utf8')
        doc={'schema':1,'id':'probe','script':'probe.py','manual_only':True,'enabled':True,'params':{},'requires_shared_corpus':'conformance'}
        (d/'probe.test.json').write_text(json.dumps(doc))
        got,errors=discover(d);self.assertFalse(errors);self.assertEqual(got[0]['requires_shared_corpus'],'conformance')
        doc['requires_shared_corpus']=['performance','conformance','stress'];(d/'probe.test.json').write_text(json.dumps(doc))
        got,errors=discover(d);self.assertFalse(errors);self.assertEqual(len(got[0]['requires_shared_corpus']),3)
        doc['requires_shared_corpus']='other';(d/'probe.test.json').write_text(json.dumps(doc))
        got,errors=discover(d);self.assertFalse(got);self.assertTrue(errors)
    def test_runner_distinguishes_y_n_i_and_crash(self):
        info=self.add_js()
        with tempfile.TemporaryDirectory() as extract_root:
            js.extract(info['archive'],extract_root)
            root=Path(extract_root)/js.CORPUS_ID
            import run_json_conformance as runner
            from types import SimpleNamespace
            out=self.lab/'out'
            def fake_parser(args,stdout,stderr,timeout):
                name=Path(args[-1]).name
                return SimpleNamespace(returncode=0 if name.startswith('y_') else 1)
            with patch.object(runner.subprocess,'run',side_effect=fake_parser):
                summary=runner.run(root,['fake-parser','{file}'],out)
            self.assertEqual(summary['counts']['PASS'],200)
            self.assertEqual(summary['counts']['UNSCORED'],25)
            self.assertEqual(summary['counts']['FAIL'],0)
    def test_legitimate_hash_in_filename_with_path_safety(self):
        # Verified from the pinned upstream commit: n_structure_trailing_#.json.
        name='test_parsing/n_structure_trailing_#.json'
        self.assertEqual(str(js._safe(name)),name)
        records,entries=js._fetch_records(upstream_fixture())
        self.assertEqual(entries[name],b'{')
        self.assertIn(name,{rec['name'] for rec in records})
        for bad in ('../test_parsing/n_traversal.json',
                    'test_parsing/../n_traversal.json',
                    'test_parsing/n_bad\\path.json',
                    'test_parsing/n_bad:colon.json'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                js._safe(bad)

    def test_reject_upstream_path_traversal(self):
        d=io.BytesIO()
        with zipfile.ZipFile(d,'w') as z:
            z.writestr('JSONTestSuite-'+js.SOURCE_COMMIT+'/test_parsing/../n_bad.json',b'{')
        with self.assertRaises(ValueError):js._fetch_records(d.getvalue())
    def test_no_benchmark_run_during_sync(self):
        self.add_js()
        svc.sync_remote(self.server,'rvvlab-v5',self.lab,suite='conformance')
        self.assertFalse(any(('sbatch' in s or 'nohup' in s) for s in self.server.execs))

if __name__=='__main__':unittest.main()
