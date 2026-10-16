"""Test101 offline checks; no SSH, Slurm, compiler or benchmark is started."""
import importlib.util, hashlib, json, pathlib, subprocess, sys, tempfile, unittest, zipfile
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('test101_native',ROOT/'tools/test101_native.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)

class Offline101(unittest.TestCase):
    def test_manifest_and_two_targets(self):
        m=json.loads((ROOT/'studio/test_scripts/101_dispatch_validation.test.json').read_text())
        self.assertEqual(m['script'],'101_dispatch_validation.py')
        self.assertEqual(m['id'],'test101-dispatch-validation')
        self.assertNotIn('requires_shared_corpus',m)
        self.assertEqual(m['params']['max_seconds'],21600)
        self.assertEqual(native.CORPUS_COMMIT,'4197c425e857f0ec38e89822fdd0bd9ea21f4daf')
        self.assertEqual(set(native.VARIANTS),{'OFFICIAL_504','A2_REF','A2_G8192','A2_G10240','A2_G12288','A2_G16384'})

    def test_public_corpus_strict_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);(root/'files').mkdir()
            entries=[]
            for name in native.EXPECTED_DOCS:
                p=root/'files'/name;p.write_bytes(b'{"v":1}')
                entries.append(dict(name=name,bytes=p.stat().st_size,sha256=native.sha(p)))
            m=dict(upstream_commit=native.CORPUS_COMMIT,corpus_id=native.CORPUS_ID,files=entries)
            native.save(root/'manifest.json',m)
            self.assertEqual(len(native.corpus_verify(root)[1]),18)
            m['upstream_commit']=m['upstream_commit'].replace('e89822','e89922')
            native.save(root/'manifest.json',m)
            with self.assertRaisesRegex(RuntimeError,'provenance mismatch'):native.corpus_verify(root)

    def test_derived_structures_and_boundary_fixture_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp);docs=[]
            for name in native.EXPECTED_DOCS:
                obj={'source':name,'elements':[{'i':i,'description':str(i)*30,'name':name} for i in range(100)]}
                p=root/name;p.write_text(json.dumps(obj),encoding='utf8')
                docs.append(dict(name=name,file=p,sha256=native.sha(p)))
            derived=native.derived_build(root,docs)
            synthetic=native.synthetic_build(root)
            self.assertGreaterEqual(len(derived),6)
            self.assertEqual(len(synthetic),87)
            for x in synthetic+derived:
                self.assertEqual(x['bytes'],x['file'].stat().st_size)
                self.assertEqual(x['sha256'],native.sha(x['file']))
                json.loads(x['file'].read_bytes())
            self.assertTrue(all(x['derived_from'] in native.EXPECTED_DOCS for x in derived))

    def test_three_strata_and_direct_eight_kib_reference(self):
        rows=[]
        for stratum in ('public_original','public_derived','synthetic_boundary'):
            for rnd in range(8):
                for var,v in [('OFFICIAL_504',0.4),('A2_REF',1),('A2_G8192',1.05),('A2_G10240',1.1),('A2_G12288',1.2),('A2_G16384',1.3)]:
                    rows.append(dict(stratum=stratum,round=rnd,document='sample',variant=var,gbps=v,
                                     anchor_before_gbps=1,anchor_after_gbps=1))
        ans=native.summary(rows,baseline='A2_G8192')
        self.assertAlmostEqual(ans['comparisons']['public_original']['A2_G10240']['file_equal_geomean'],1.1/1.05)
        self.assertEqual(set(ans['comparisons']),{'public_original','public_derived','synthetic_boundary'})
        conf=native.round_confidence(rows,8)
        self.assertEqual(len(conf),12)

    def test_failed_and_partial_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            status={'state':'failed','rows':0,'reason':'probe failed'}
            native.save(root/'status101.json',status)
            native.package(root,status,[],None)
            with zipfile.ZipFile(root/'test101_results.zip') as z:
                self.assertIsNone(z.testzip())
                self.assertIn('status101.json',z.namelist())
                self.assertIn('probe failed',z.read('REPORT_101.md').decode())
            self.assertEqual(native.sha(root/'test101_results.zip'),(root/'test101_results.sha256').read_text().split()[0])

    def test_cloudv_download_zip_guard_and_epcc_registration(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('test101_download',ROOT/'studio/rvvlab_test101_download.py')
        d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
        spec2=importlib.util.spec_from_file_location('epcc_results',ROOT/'studio/rvvlab_epcc_results.py')
        e=importlib.util.module_from_spec(spec2);spec2.loader.exec_module(e)
        self.assertEqual(e.RUN_TYPES['test101']['test_id'],'test101-dispatch-validation')
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'test101_results.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('status101.json',json.dumps({'state':'completed','validated':True,'rows':100}))
                z.writestr('REPORT_101.md','# confirmed')
            self.assertIsNone(zipfile.ZipFile(p).testzip())
            self.assertIn('status101.json',d.check_zip(p,expected_state='completed'))
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('status101.json',json.dumps({'state':'completed','validated':True,'rows':100}))
                z.writestr('REPORT_101.md','# confirmed')
                z.writestr('../bad.txt','bad')
            with self.assertRaisesRegex(RuntimeError,'unexpected'):
                d.check_zip(p,expected_state='completed')

    def test_slurm_and_cloud_bash_are_valid(self):
        for name in ('test101_cloudv.sh','test101_epcc.sbatch'):
            result=subprocess.run(['bash','-n',str(ROOT/'tools'/name)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr.decode())

if __name__=='__main__':unittest.main()
