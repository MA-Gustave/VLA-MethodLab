#!/usr/bin/env python3
"""Select a VERIFIED RVV 1.0 cross C++ compiler on EPCC's x86 login node.

Check the compiler, its riscv_vector.h intrinsics and link-compatible RV64
C++ runtime BEFORE invoking the one-hour experiment. No changes to modules.
"""
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


def choose():
    candidates=[]
    # LLVM16 provides RVV 1.0; GCC12.2 module is RV64GC and misses vector headers.
    for binary in ('clang++', 'clang++-16', 'riscv64-unknown-linux-gnu-g++'):
        path=shutil.which(binary)
        if path:
            flags=['--target=riscv64-unknown-linux-gnu'] if 'clang' in binary else []
            if 'clang' in binary:
                cross=shutil.which('riscv64-unknown-linux-gnu-g++')
                if cross:
                    # Clang discovers GCC cross libraries if its root is explicit.
                    # Probe both implicit and explicit GCC toolchain paths.
                    candidates.append((path,flags))
                    gcc_root=Path(cross).resolve().parent.parent
                    candidates.append((path,flags+['--gcc-toolchain='+str(gcc_root)]))
                else:candidates.append((path,flags))
            else:candidates.append((path,flags))
    tested=[]
    # RVV 1.0 intrinsics have the __riscv_ prefix. The previous legacy
    # vsetvl_e8m1 spelling produced a FALSE NEGATIVE on LLVM 16 even though
    # riscv_vector.h existed. Keep a C++ standard-library link test as well.
    src=('#include <riscv_vector.h>\n'
         '#include <vector>\n'
         '#include <cstdint>\n'
         'int main() {\n'
         '  size_t vl = __riscv_vsetvl_e8m1(16);\n'
         '  size_t max_vl = __riscv_vsetvlmax_e8m1();\n'
         '  std::vector<int> value(1);\n'
         '  return int(vl == 0 || max_vl == 0) + value[0];\n'
         '}\n')
    with tempfile.TemporaryDirectory(prefix='test94-rvv-probe-') as temp:
        source=Path(temp)/'probe.cpp';source.write_text(src)
        output=Path(temp)/'probe'
        for compiler,extra in candidates:
            command=[compiler,*extra,'-O2','-std=c++17','-march=rv64gcv','-mabi=lp64d',str(source),'-o',str(output)]
            proc=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=40,check=False)
            tested.append((compiler,extra,proc.returncode,proc.stdout[-900:]))
            if proc.returncode==0 and output.is_file():
                # Native RISC-V ELF must be produced, not an accidentally host-native build.
                header=output.read_bytes()[:20]
                if header[:4]==b'\x7fELF' and int.from_bytes(header[18:20],'little')==243:
                    print('EPCC RVV1.0 compiler OK: '+compiler+' '+shlex.join(extra),flush=True)
                    return compiler,extra
                tested[-1]=(compiler,extra,-1,'Cross-build emitted non-RISC-V ELF')
    for compiler,extra,rc,log in tested:
        print('Probe failed: '+compiler+' '+shlex.join(extra)+' rc='+str(rc)+' '+log.replace('\n',' ')[:400],flush=True)
    raise RuntimeError('No working EPCC RVV1.0 cross C++ compiler/linker with __riscv_ intrinsics and RISC-V C++ runtime. '+
                       'Load riscv64-linux/llvm-16.0 and riscv64-linux/gnu-12.2, or ask EPCC about a vector-enabled toolchain.')


def main():
    if len(sys.argv)!=5:raise SystemExit('Usage: test94_epcc_build.py SOURCE OUT NATIVE_SCRIPT LOG')
    source,out,script,log=sys.argv[1:]
    compiler,flags=choose()
    # argparse treats a separate token starting with -- as another option.
    # Keep target flags in the same --cxx-flags=VALUE argument so Clang's
    # --target=... and --gcc-toolchain=... pass through unchanged.
    cmd=[sys.executable,script,'build-only','--source',source,'--output',out,
         '--cxx',compiler,'--cxx-flags='+shlex.join(flags)]
    print('Compiling EPCC A2, A2-LTO, packed_plain with tested RVV1.0 toolchain',flush=True)
    with open(log,'a',encoding='utf-8') as f:
        f.write('Compiler: '+compiler+' FLAGS='+shlex.join(flags)+'\n')
        f.flush()
        return subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print('TEST94 EPCC TOOLCHAIN ERROR:',e,file=sys.stderr);raise SystemExit(2)
