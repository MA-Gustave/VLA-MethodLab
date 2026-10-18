#!/usr/bin/env python3
"""EPCC cross-build Test106: fail before Slurm on compiler/source error."""
import subprocess,sys
import test96_epcc_build

def main(argv):
    if len(argv)!=5:raise SystemExit('Usage: TOOL SOURCE OUTPUT LOG CANDIDATE_PACKAGE')
    tool,source,output,log,package=argv
    compiler,flags=test96_epcc_build.select_toolchain()
    cmd=[sys.executable,tool,'build','--source',source,'--output',output,
         '--candidate-package',package,'--arch','x86_64','--cxx',compiler,'--cxx-flags='+' '.join(flags)]
    with open(log,'a',encoding='utf8') as f:
        f.write('TEST106 VectorPath A2 RC native gate: official 5.0.4 / old A2 / RC stable / RC simple / RC NL4\n');f.flush()
        return subprocess.call(cmd,stdout=f,stderr=subprocess.STDOUT)
if __name__=='__main__':raise SystemExit(main(sys.argv[1:]))
