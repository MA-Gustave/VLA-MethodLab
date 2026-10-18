#!/usr/bin/env python3
"""Two distinct EPCC compilers, GCC12 and LLVM16, before Slurm admission."""
import shutil,subprocess,sys,os
from pathlib import Path
import test96_epcc_build

def main(argv):
    if len(argv)!=4:raise SystemExit('Usage: TOOL SOURCE OUTPUT LOG')
    tool,source,output,log=argv
    clang,llvmflags=test96_epcc_build.select_toolchain()
    gcc=next((p for x in ('riscv64-unknown-linux-gnu-g++','riscv64-linux-gnu-g++') if (p:=shutil.which(x))),None)
    if not gcc:raise RuntimeError('EPCC GCC RISC-V cross-compiler is missing after loading riscv64-linux/gnu-12.2; Test105 cannot compare GCC/LLVM')
    command=[sys.executable,tool,'build','--source',source,'--output',output,'--arch','x86_64',
             '--gcc',gcc,'--llvm',clang,'--llvm-flags='+' '.join(llvmflags)]
    with open(log,'a',encoding='utf8') as f:
        f.write('Test105 EPCC: strict GCC vs LLVM complete eight-way matrix\n');f.flush()
        return subprocess.call(command,stdout=f,stderr=subprocess.STDOUT)
if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print('TEST105 EPCC BUILD FAILED: '+str(exc),file=sys.stderr)
        raise SystemExit(2)
