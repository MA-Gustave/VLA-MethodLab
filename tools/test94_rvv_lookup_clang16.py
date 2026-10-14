#!/usr/bin/env python3
"""Offline compile smoke for the Test 94 EPCC Clang16 RVV lookup fallback.

Local Clang 17 can compile both branches, but this is not a substitute for
Clang 16 on EPCC or a native RVV correctness/benchmark run.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
CLANG=shutil.which('clang++')
RESOURCES=subprocess.run([CLANG,'-print-resource-dir'],capture_output=True,text=True,check=True).stdout.strip() if CLANG else ''
SRC='''\
#define SIMDJSON_RVV_BASE_H
#define simdjson_really_inline inline __attribute__((always_inline))
#include "simdjson/rvv/intrinsics.h"
using namespace simdjson::rvv;
vuint8m2_t lookup2(vuint8m1_t table,vuint8m2_t indices) {
  return detail::lookup16_u8m2(table,indices);
}
vuint8m4_t lookup4(vuint8m1_t table,vuint8m4_t indices) {
  return detail::lookup16_u8m4(table,indices);
}
'''

@unittest.skipUnless(CLANG, 'Clang is not installed')
class RVVLookupCompileSmoke(unittest.TestCase):
    def compile(self,major):
        with tempfile.TemporaryDirectory(prefix='test94-rvv-lookup-') as folder:
            path=Path(folder)/'smoke.cpp';path.write_text(SRC,encoding='utf-8')
            dest=Path(folder)/'smoke.o'
            cmd=[CLANG,'--target=riscv64-unknown-linux-gnu','-march=rv64gcv','-mabi=lp64d',
                 '-std=c++17','-O3','-ffreestanding','-nostdinc','-isystem',str(Path(RESOURCES)/'include'),
                 '-I'+str(ROOT/'engine/include'),'-Wno-macro-redefined',
                 '-D__clang_major__='+str(major),'-c',str(path),'-o',str(dest)]
            result=subprocess.run(cmd,capture_output=True,text=True,check=False,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertTrue(dest.exists())
            hdr=dest.read_bytes()[:20]
            self.assertEqual(hdr[:4],b'\x7fELF')
            self.assertEqual(int.from_bytes(hdr[18:20],'little'),243,'Not a RISC-V object')
    def test_clang16_fallback(self):self.compile(16)
    def test_legacy_route_remains_available(self):self.compile(17)

if __name__=='__main__':unittest.main(verbosity=2)
