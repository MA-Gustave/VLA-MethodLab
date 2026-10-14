#!/usr/bin/env python3
"""EPCC Test94 argparse regression: passing --target through --cxx-flags.

No real SSH, Slurm, C++ compile, or run is performed.
"""
import importlib.util
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import patch

HERE=Path(__file__).resolve().parent

def import_local(name):
    spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

builder=import_local('test94_epcc_build')
native=import_local('test94_native')

class TestEPCCArgPassThrough(unittest.TestCase):
    def check(self, flags):
        received={}
        with tempfile.TemporaryDirectory() as d:
            logfile=Path(d)/'build.log'
            def fake_call(cmd, **kwargs):
                self.assertEqual(cmd[1], str(HERE/'test94_native.py'))
                self.assertEqual(cmd[-1], '--cxx-flags='+shlex.join(flags))
                self.assertNotIn('--cxx-flags',cmd)
                with patch.object(native,'prepare',side_effect=lambda opts:received.update(vars(opts))):
                    self.assertEqual(native.main(cmd[2:]),0)
                return 0
            with patch.object(builder,'choose',return_value=('/fake/clang++',flags)):
                with patch.object(builder.subprocess,'call',side_effect=fake_call):
                    rc=builder.main_from_args(['source-dir','build-dir',str(HERE/'test94_native.py'),str(logfile)]) if hasattr(builder,'main_from_args') else self.invoke(builder, ['source-dir','build-dir',str(HERE/'test94_native.py'),str(logfile)])
            self.assertEqual(rc,0)
            self.assertEqual(received['cxx'],'/fake/clang++')
            self.assertEqual(shlex.split(received['cxx_flags']),flags)
            self.assertIn('Compiler:',logfile.read_text(encoding='utf-8'))
    @staticmethod
    def invoke(module, args):
        with patch.object(module.sys,'argv',[str(HERE/'test94_epcc_build.py'),*args]):
            return module.main()
    def test_llvm_target_flag(self):
        self.check(['--target=riscv64-unknown-linux-gnu'])
    def test_toolchain_option(self):
        self.check(['--target=riscv64-unknown-linux-gnu','--gcc-toolchain=/opt/riscv/toolchain'])
    def test_plain_gcc_without_target_flags(self):
        self.check([])

if __name__=='__main__':unittest.main(verbosity=2)
