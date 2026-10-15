#!/usr/bin/env python3
"""EPCC x86 cross-compile Test96 with a verified Clang16 RVV1.0 C++ toolchain.

Requires module environment supplied by the launcher. No changes to any module
or source files. All seven binaries must build and must be RISC-V ELF64.
"""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile


def select_toolchain():
    clang=shutil.which('clang++')
    if not clang:
        raise RuntimeError('No clang++ in PATH after loading riscv64-linux/llvm-16.0')
    candidates=[['--target=riscv64-unknown-linux-gnu']]
    cross=shutil.which('riscv64-unknown-linux-gnu-g++')
    if cross:
        gccroot=str(Path(cross).resolve().parent.parent)
        candidates.append(['--target=riscv64-unknown-linux-gnu','--gcc-toolchain='+gccroot])
    source='''#include <riscv_vector.h>
#include <vector>
#include <cstdint>
int main() {
  size_t v = __riscv_vsetvl_e8m1(16);
  vuint8m1_t tbl = __riscv_vmv_v_x_u8m1(7, v);
  vuint8m2_t idx2 = __riscv_vlmul_ext_v_u8m1_u8m2(tbl);
  vuint8m4_t idx4 = __riscv_vlmul_ext_v_u8m1_u8m4(tbl);
  auto a = __riscv_vrgather_vv_u8m2(idx2, idx2, __riscv_vsetvlmax_e8m2());
  auto b = __riscv_vrgather_vv_u8m4(idx4, idx4, __riscv_vsetvlmax_e8m4());
  std::vector<int> vec(1);
  (void)a; (void)b; return vec[0];
}
'''
    with tempfile.TemporaryDirectory(prefix='epcc-t96-probe-') as tmp:
        src=Path(tmp)/'probe.cpp';src.write_text(source)
        dest=Path(tmp)/'probe'
        for extra in candidates:
            cmd=[clang,*extra,'-O2','-march=rv64gcv','-mabi=lp64d','-std=c++17',str(src),'-o',str(dest)]
            try:p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=90)
            except subprocess.TimeoutExpired:
                print('Probe timeout '+shlex.join(extra),flush=True);continue
            if p.returncode==0 and dest.is_file():
                hdr=dest.read_bytes()[:20]
                if len(hdr)>=20 and hdr[:4]==b'\x7fELF' and hdr[4]==2 and int.from_bytes(hdr[18:20],'little')==243:
                    print('EPCC LLVM16 cross-toolchain OK '+clang+' '+shlex.join(extra),flush=True)
                    return clang,extra
            print('Probe FAILED '+shlex.join(extra)+' rc='+str(p.returncode)+' '+p.stdout[-1300:].replace('\n',' '),flush=True)
    raise RuntimeError('EPCC LLVM16 Clang RVV1.0+C++ link probe failed. Do not submit Slurm job.')


def main(argv):
    if len(argv)!=4:raise SystemExit('Usage: test96_epcc_build.py SOURCE OUTPUT NATIVE_SCRIPT BUILD_LOG')
    src,out,script,log=argv
    if not Path(src,'include/simdjson/rvv/intrinsics.h').is_file():raise RuntimeError('No RVV header in deployed source')
    head=Path(src,'include/simdjson/rvv/intrinsics.h').read_text(encoding='utf8')
    if '__clang_major__ <= 16' not in head or '__riscv_vlmul_ext_v_u8m1_u8m2' not in head:
        raise RuntimeError('PATCH_CLANG16_ABSENT in deployed EPCC source: install patched engine locally, then redeploy')
    clang,extra=select_toolchain()
    cmd=[sys.executable,script,'build-only','--source',src,'--output',out,'--cxx',clang,'--cxx-flags='+shlex.join(extra)]
    print('EPCC Test96: cross-compiling seven RVV1.0 variants (may take time)',flush=True)
    with open(log,'a',encoding='utf8') as f:
        f.write('Compiler: '+clang+' FLAGS='+shlex.join(extra)+'\n')
        f.flush()
        return subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)

if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except Exception as e:
        print('TEST96 EPCC BUILD FAILED: '+str(e),file=sys.stderr)
        raise SystemExit(2)
