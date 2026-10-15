#!/usr/bin/env python3
"""Cross-build Test97 (published GitHub upstream source on EPCC login only)."""
from pathlib import Path
import subprocess,sys
import test96_epcc_build

def main(args):
    if len(args)!=5:raise SystemExit('Usage: BUILDSCRIPT FORK OUT NATIVE_SCRIPT BUILD_LOG TOOL_DIR')
    source,output,native,log,tools=args
    compiler,flags=test96_epcc_build.select_toolchain()
    root=Path(output)/'upstream-sources';root.mkdir(exist_ok=True)
    with Path(log).open('a',encoding='utf8') as f:
        f.write('Official upstream repository: https://github.com/simdjson/simdjson.git\n')
        f.flush()
        for version,name in [('v5.0.3','OFFICIAL_503'),('v5.0.4','OFFICIAL_504')]:
            target=root/name
            # A failed/no-network clone is a hard failure. NEVER use the local fork as baseline.
            print('Cloning OFFICIAL '+version+' (requires EPCC HTTPS/GitHub access)',flush=True)
            cmd=['git','clone','--quiet','--depth','1','--branch',version,'https://github.com/simdjson/simdjson.git',str(target)]
            result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=240)
            if result.returncode:raise RuntimeError('Could not clone official '+version+' from GitHub; no Slurm job submitted')
        cmd=[sys.executable,native,'build-only','--source',source,'--upstream',str(root),'--output',output,
             '--cxx',compiler,'--cxx-flags='+ ' '.join(flags)]
        result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=3600)
        if result.returncode:raise RuntimeError('Test97 build failure; see '+log)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main(sys.argv[1:]))
    except Exception as ex:
        print('TEST97 BUILD FAILED:',ex,file=sys.stderr)
        raise SystemExit(2)
