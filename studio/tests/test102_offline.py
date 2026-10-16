"""Offline Test102 checks; no SSH, Slurm, or RISC-V hardware required."""
import importlib.util,json,tempfile,hashlib,unittest,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

class Test102Offline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker=load(ROOT/'tools/test102_native.py','t102worker')
        cls.download=load(ROOT/'studio/rvvlab_test102_download.py','t102download')

    def test_fresh_synthetic_and_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=self.worker.synthetic_build(tmp,'explore')
            b=self.worker.synthetic_build(tmp,'confirm')
            self.assertEqual(len(a),206);self.assertEqual(len(b),206)
            self.assertFalse({x['sha256'] for x in a} & {x['sha256'] for x in b})
            for r in a+b:
                self.assertEqual(r['bytes'],r['file'].stat().st_size)
                json.loads(r['file'].read_bytes())
            e=[x for x in a if x['name'].endswith('cross-8192-08-early.json')][0]
            nine=[x for x in a if x['name'].endswith('cross-8192-09-early.json')][0]
            self.assertEqual((e['backslashes_per_probe'],nine['backslashes_per_probe']),(8,9))
            self.assertEqual((e['bytes'],nine['bytes']),(8192,8192))

    def test_pinned_corpus_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'files').mkdir()
            files=[]
            for name in self.worker.PUBLIC:
                data=b'{"p":"hello"}'
                (d/'files'/name).write_bytes(data)
                files.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            m={'upstream_commit':self.worker.CORPUS_COMMIT,'corpus_id':self.worker.CORPUS_ID,'files':files}
            (d/'manifest.json').write_text(json.dumps(m))
            self.assertEqual(len(self.worker.corpus_verify(d)[1]),18)
            (d/'files'/files[0]['name']).write_bytes(b'bad')
            with self.assertRaisesRegex(RuntimeError,'mismatch'):
                self.worker.corpus_verify(d)

    def test_failure_packet_is_not_success(self):
        tool=load(ROOT/'tools/test102_diagnostic.py','t102diagnostic')
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'status102.json').write_text('{"state":"building","rows":0}')
            old=sys.argv;sys.argv=['test102_diagnostic','--output',str(d),'--reason','controlled failure']
            try:tool.main()
            finally:sys.argv=old
            z=d/'test102_results.zip'
            self.assertTrue(z.exists())
            with zipfile.ZipFile(z) as archive:
                self.assertEqual(json.loads(archive.read('status102.json'))['state'],'failed')
            self.download.check_zip(z)
            with self.assertRaisesRegex(RuntimeError,'completed'):
                self.download.check_zip(z,expected_state='completed')

    def test_summary_stage_isolation(self):
        rows=[]
        for v,dom,s1,s2 in (('A2_REF',1,2,3),('A2_G16384',2,4,1.5),('OFFICIAL_504',.5,1,1)):
            rows.append({'phase':'explore','stratum':'synthetic_explore','document':'demo','round':0,
                         'family':'newline','variant':v,'dom_gbps':dom,'stage1_gbps':s1,'stage2_gbps':s2})
        summary=self.worker.calculate(rows)
        m=summary['explore/synthetic_explore/newline']['A2_REF']
        self.assertAlmostEqual(m['dom_gbps']['geomean_ratio_A2_16K_over_comparator'],2)
        self.assertAlmostEqual(m['stage2_gbps']['geomean_ratio_A2_16K_over_comparator'],.5)

    def test_studio_routing(self):
        # The Studio integration is tracked by manifest and simple-runner ID.
        manifest=json.loads((ROOT/'studio/test_scripts/102_escape_stage.test.json').read_text())
        self.assertEqual(manifest['id'],'test102-escape-stage')
        self.assertEqual(manifest['params']['max_seconds'],23400)
        s=(ROOT/'studio/rvvlab_simple_tests.py').read_text()
        self.assertIn("'102': ('Cloud-V','EPCC')",s)
        self.assertIn('rvvlab_test102_download',s)

if __name__=='__main__':unittest.main()
