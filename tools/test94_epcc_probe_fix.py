#!/usr/bin/env python3
"""Local regression for the RVV1.0 compiler selection on EPCC.

Does not contact EPCC or submit benchmarks. Mocks a working LLVM compiler,
checks actual probe text and RISC-V ELF guard, and a negative link case.
"""
from pathlib import Path
import importlib.util
from unittest.mock import patch
import tempfile
import types
import unittest

HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('test94_epcc_build',HERE/'test94_epcc_build.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)

class TestRVVToolchainProbe(unittest.TestCase):
    def test_standard_rvv_v1_names_and_elf_guard(self):
        def run(cmd,**kwargs):
            src=Path(cmd[-3]).read_text()
            self.assertIn('__riscv_vsetvl_e8m1(16)',src)
            self.assertIn('__riscv_vsetvlmax_e8m1()',src)
            self.assertNotIn('n=vsetvl_e8m1',src)
            Path(cmd[-1]).write_bytes(b'\x7fELF'+b'\x00'*14+(243).to_bytes(2,'little')+b'\x00'*40)
            return types.SimpleNamespace(returncode=0,stdout='')
        with patch.object(b.shutil,'which',side_effect=lambda x:'/fake/clang++' if x=='clang++' else None), patch.object(b.subprocess,'run',side_effect=run):
            c,flags=b.choose()
        self.assertEqual(c,'/fake/clang++')
        self.assertEqual(flags,['--target=riscv64-unknown-linux-gnu'])

    def test_reject_host_x86_elf(self):
        def run(cmd,**kwargs):
            Path(cmd[-1]).write_bytes(b'\x7fELF'+b'\x00'*14+(62).to_bytes(2,'little')+b'\x00'*40)
            return types.SimpleNamespace(returncode=0,stdout='')
        with patch.object(b.shutil,'which',side_effect=lambda x:'/fake/clang++' if x=='clang++' else None), patch.object(b.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(RuntimeError,'No working EPCC RVV1.0'):
                b.choose()

    def test_preserves_link_failures(self):
        def run(cmd,**kwargs):
            return types.SimpleNamespace(returncode=1,stdout='ld: cannot find libstdc++ for riscv64')
        with patch.object(b.shutil,'which',side_effect=lambda x:'/fake/clang++' if x=='clang++' else None), patch.object(b.subprocess,'run',side_effect=run):
            with self.assertRaisesRegex(RuntimeError,'No working EPCC RVV1.0'):
                b.choose()

if __name__=='__main__':unittest.main(verbosity=2)
