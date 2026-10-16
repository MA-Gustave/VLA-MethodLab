"""Offline integrity tests for Test100 (no SSH, Slurm, or benchmark execution)."""
import hashlib, importlib.util, json, pathlib, tempfile, unittest, zipfile

HERE=pathlib.Path(__file__).resolve().parents[2]
SPEC=importlib.util.spec_from_file_location('test100_native',HERE/'tools/test100_native.py')
MOD=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)

class AdaptiveTest100(unittest.TestCase):
    def test_pin_matches_existing_lab_corpus(self):
        # Keep this exact revision from tools/corpus98.py; Test99 used e89922 (wrong).
        self.assertEqual(MOD.CORPUS_COMMIT,'4197c425e857f0ec38e89822fdd0bd9ea21f4daf')
        self.assertEqual(MOD.CORPUS_ID,'simdjson-data-4197c425-test98')

    def test_complete_immutable_18_file_fixture_check(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);(p/'files').mkdir()
            records=[]
            for name in MOD.EXPECTED_DOCS:
                dest=p/'files'/name;dest.write_bytes(b'{"a":1}')
                records.append(dict(name=name,bytes=dest.stat().st_size,sha256=MOD.sha(dest)))
            man={'upstream_commit':MOD.CORPUS_COMMIT,'corpus_id':MOD.CORPUS_ID,'files':records}
            MOD.save(p/'manifest.json',man)
            self.assertEqual(len(MOD.corpus_verify(p)[1]),18)
            man['upstream_commit']=MOD.CORPUS_COMMIT.replace('e89822','e89922')
            MOD.save(p/'manifest.json',man)
            with self.assertRaisesRegex(RuntimeError,'provenance mismatch'):MOD.corpus_verify(p)

    def test_synthetic_exact_sizes_and_validity(self):
        with tempfile.TemporaryDirectory() as d:
            docs=MOD.synthetic_build(d)
            self.assertEqual(len(docs),57)
            for record in docs:
                self.assertEqual(record['bytes'],record['file'].stat().st_size)
                self.assertEqual(record['sha256'],MOD.sha(record['file']))
                json.loads(record['file'].read_bytes())
            self.assertEqual(len({d['sha256'] for d in docs}),len(docs))

    def test_failed_zero_measurements_publish_diagnostics(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d);status={'state':'failed','reason':'probe failed','rows':0}
            MOD.save(p/'status100.json',status);MOD.package(p,status,[],None)
            with zipfile.ZipFile(p/'test100_results.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertIn('status100.json',z.namelist())
                self.assertIn('REPORT_100.md',z.namelist())
                self.assertIn('probe failed',z.read('REPORT_100.md').decode())
            self.assertEqual(MOD.sha(p/'test100_results.zip'),(p/'test100_results.sha256').read_text().split()[0])

    def test_diagnostic_helper_packages_failed_build(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)
            import subprocess,sys
            tool=HERE/'tools/test100_diagnostic.py'
            subprocess.run([sys.executable,str(tool),'--output',str(p),'--reason','preflight mismatch'],check=True,capture_output=True)
            with zipfile.ZipFile(p/'test100_results.zip') as z:
                self.assertEqual(json.loads(z.read('status100.json'))['state'],'failed')
                self.assertIn('preflight mismatch',z.read('REPORT_100.md').decode())

    def test_runner_manifest_consistency(self):
        meta=json.loads((HERE/'studio/test_scripts/100_adaptive_public.test.json').read_text())
        self.assertEqual(meta['id'],'test100-adaptive-public')
        self.assertEqual(meta['script'],'100_adaptive_public.py')
        self.assertNotIn('requires_shared_corpus',meta)  # Runner safely synchronizes corpus itself
        self.assertTrue(meta['params']['new_run'])

    def test_round_uncertainty_unavailable_if_insufficient(self):
        self.assertEqual(MOD.round_confidence([],0),{})

    def test_three_strata_not_pooled(self):
        rows=[]
        for workload,ratio in [('public_original',1.1),('synthetic_boundary',2.0)]:
            for name,speed in [('A2_REF',1.0),('A2_G8192',ratio)]:
                rows.append(dict(stratum=workload,round=0,document='a',variant=name,gbps=speed))
        x=MOD.summary(rows)
        self.assertAlmostEqual(x['comparisons']['public_original']['A2_G8192']['file_equal_geomean_vs_A2'],1.1)
        self.assertAlmostEqual(x['comparisons']['synthetic_boundary']['A2_G8192']['file_equal_geomean_vs_A2'],2.0)

if __name__=='__main__':unittest.main()
