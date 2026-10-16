#!/usr/bin/env python3
"""EPCC cross-build Test99: fail before Slurm on compiler/source error."""
import subprocess,sys
import test96_epcc_build

def main(argv):
    if len(argv)!=4:raise SystemExit('Usage: TOOL SOURCE OUTPUT LOG')
    tool,source,output,log=argv
    compiler,flags=test96_epcc_build.select_toolchain()
    cmd=[sys.executable,tool,'build','--source',source,'--output',output,
         '--arch','x86_64','--cxx',compiler,'--cxx-flags='+' '.join(flags)]
    with open(log,'a',encoding='utf8') as f:
        f.write('TEST99 pinned official v5.0.3+5.0.4 and A2 builds\n');f.flush()
        return subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
