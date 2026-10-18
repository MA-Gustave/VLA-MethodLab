"""Test105 regression checks for real compiler matrix, no RISC-V machine required."""
from __future__ import annotations
import importlib.util,json,hashlib,tempfile,zipfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[name]=module;spec.loader.exec_module(module)
    return module

class Test105(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker=load(ROOT/'tools/test105_native.py','test105_native_unittest')
        cls.down=load(ROOT/'studio/rvvlab_test105_download.py','test105_download_unittest')

    def test_variant_eight_exact_matrix(self):
        w=self.worker
        self.assertEqual(len(w.VARIANTS),8)
        self.assertEqual(len(set(w.VARIANTS)),8)
        for compiler in ('GCC','LLVM'):
            for kind in ('OFFICIAL_504','A2_G16384','A2_SIMPLE_RUN','A2_NL4'):
                self.assertIn(compiler+'_'+kind,w.VARIANTS)

    def test_cross_compiler_and_within_compiler_ratios(self):
        w=self.worker;records=[]
        ratios={'GCC_OFFICIAL_504':0.50,'GCC_A2_G16384':1.0,
                'GCC_A2_SIMPLE_RUN':1.1,'GCC_A2_NL4':1.2,
                'LLVM_OFFICIAL_504':0.60,'LLVM_A2_G16384':1.3,
                'LLVM_A2_SIMPLE_RUN':1.43,'LLVM_A2_NL4':1.56}
        for variant,v in ratios.items():
            for roundid in (1,2):
                records.append({'phase':'confirm','stratum':'public_original','document':'official.json','round':roundid,
                                'family':'public','requested_density_pct':None,'placement':'original','backslashes_per_probe':None,
                                'variant':variant,'dom_gbps':v,'stage1_gbps':v*2,'stage2_gbps':v*3})
        sm=w.calculate(records)['confirm/public_original/public']
        self.assertAlmostEqual(sm['LLVM_A2_G16384']['GCC_A2_G16384']['dom_gbps']['geomean_ratio'],1.3)
        self.assertAlmostEqual(sm['GCC_A2_SIMPLE_RUN']['GCC_A2_G16384']['dom_gbps']['geomean_ratio'],1.1)
        self.assertAlmostEqual(sm['LLVM_A2_SIMPLE_RUN']['LLVM_A2_G16384']['dom_gbps']['geomean_ratio'],1.1)
        self.assertAlmostEqual(sm['GCC_A2_G16384']['GCC_OFFICIAL_504']['dom_gbps']['geomean_ratio'],2.0)
        self.assertAlmostEqual(sm['LLVM_A2_NL4']['LLVM_A2_SIMPLE_RUN']['dom_gbps']['geomean_ratio'],1.56/1.43)

    def test_compiler_interaction_is_difference_in_differences(self):
        data={'GCC_OFFICIAL_504':1.,'GCC_A2_G16384':2.,
              'GCC_A2_SIMPLE_RUN':2.1,'GCC_A2_NL4':2.2,
              'LLVM_OFFICIAL_504':1.,'LLVM_A2_G16384':3.,
              'LLVM_A2_SIMPLE_RUN':3.6,'LLVM_A2_NL4':3.3}
        rows=[]
        for name,val in data.items():
            rows.append({'phase':'confirm','stratum':'public_original','document':'x.json','round':0,
             'family':'public','variant':name,'dom_gbps':val,'stage1_gbps':val,'stage2_gbps':val})
        result=self.worker.compiler_interaction(rows)
        interaction=result['confirm/public_original/public']['A2_SIMPLE_RUN']['dom_gbps']
        self.assertAlmostEqual(interaction['geomean_interaction_ratio'],(3.6/3.0)/(2.1/2.0))
        self.assertEqual(interaction['documents'],1)

    def test_partial_compiler_matrix_is_not_a_successful_comparison(self):
        rows=[]
        for var in self.worker.VARIANTS[:-1]:
            rows.append({'phase':'confirm','stratum':'public_original','document':'a.json','round':0,
                         'family':'public','variant':var,'dom_gbps':1,'stage1_gbps':1,'stage2_gbps':1})
        self.assertEqual(self.worker.calculate(rows),{})

    def test_conformance_raw_bytes_rejected_on_corruption(self):
        w=self.worker
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);records=[]
            for i in range(204):
                label=('y','n','i')[i%3]
                name=f'test_parsing/{label}_test_{i:03}.json'
                raw={'y':b'{}','n':b'(', 'i':b'\xff\x00'}[label]
                dst=root/'files'/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(raw)
                records.append({'name':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                'expected':{'y':'accept','n':'reject','i':'implementation'}[label]})
            (root/'manifest.json').write_text(json.dumps({'schema':1,'corpus_id':w.CONFORMANCE_ID,
                 'upstream_commit':w.CONFORMANCE_COMMIT,'files':records}))
            _,entries,valid=w.conformance_verify(root)
            self.assertEqual((len(entries),len(valid)),(204,68))
            (root/'files'/'test_parsing/n_test_001.json').write_bytes(b'!')
            with self.assertRaisesRegex(RuntimeError,'hash mismatch'):w.conformance_verify(root)

    def test_overlay_pinned_and_original_not_modified(self):
        patcher=load(ROOT/'tools/test105_stage2_patch.py','test105_patch_unittest')
        source=ROOT/'engine/src/generic/stage2/stringparsing.h'
        if not source.is_file():self.skipTest('Engine snapshot not mounted in this test run')
        original=hashlib.sha256(source.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'generic/stage2/stringparsing.h'
            info=patcher.create_overlay(source,path)
            self.assertEqual(info['source_sha256'],original)
            self.assertIn('SIMDJSON_TEST105_SIMPLE_RUN',path.read_text())
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),original)

    def test_manifest_and_both_ui_profiles(self):
        m=json.loads((ROOT/'studio/test_scripts/105_compiler_matrix.test.json').read_text())
        self.assertEqual(m['id'],'test105-cross-compiler-stage2')
        self.assertTrue(m['enabled'])
        self.assertEqual(m['script'],'105_compiler_matrix.py')
        panel=(ROOT/'studio/rvvlab_simple_tests.py').read_text()
        self.assertIn("'105': ('Cloud-V','EPCC')",panel)
        self.assertIn("'105':'105_compiler_matrix.py'",panel)
        self.assertIn('sync_cloudv_test105',panel)
        epcc=(ROOT/'studio/rvvlab_epcc_results.py').read_text()
        self.assertIn("'test105': dict(",epcc)
        hist=(ROOT/'studio/rvvlab_unified_campaigns.py').read_text()
        self.assertIn("'105':'test105-cross-compiler-stage2'",hist)

    def test_launcher_enforces_all_eight_before_slurm(self):
        script=(ROOT/'studio/test_scripts/105_compiler_matrix.py').read_text()
        self.assertIn('LLVM_A2_NL4',script)
        self.assertIn('GCC_A2_NL4',script)
        self.assertIn('TEST105_LLVM',script)
        self.assertIn('module load riscv64-linux/gnu-12.2 riscv64-linux/llvm-16.0',script)
        self.assertIn("inspect_local(LAB,'conformance')",script)
        self.assertIn("suite='conformance'",script)
        self.assertIn('102|103|104|105',script)

    def test_zip_completed_and_failed_are_distinguished(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'test105_results.zip'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('status105.json',json.dumps({'state':'completed','validated':True,'rows':8}))
                z.writestr('REPORT_105.md','done')
            self.down.check_zip(p,expected_state='completed')
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('status105.json',json.dumps({'state':'failed','rows':0,'validated':False}))
                z.writestr('REPORT_105.md','failed')
            self.down.check_zip(p,expected_state=None)
            with self.assertRaisesRegex(RuntimeError,'completed'):self.down.check_zip(p,expected_state='completed')

    def test_compiler_probe_refuses_missing_compiler(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(RuntimeError,'unavailable'):
                self.worker.probe_compiler('no-such-riscv-gxx-105',[],d,'GCC')

if __name__=='__main__':unittest.main()
