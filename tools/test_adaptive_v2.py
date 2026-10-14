#!/usr/bin/env python3
"""Compile portable C++ policy tests for all three variants (plus force override)."""
import argparse, subprocess, tempfile, pathlib, sys
root=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--engine',type=pathlib.Path,default=root/'engine')
p.add_argument('--compiler',default='g++');p.add_argument('--microbenchmark',action='store_true')
a=p.parse_args()
engine=a.engine.resolve()
unit=engine/'scripts/rvv/engines/test_adaptive_dispatch_v2.cpp'
probe=engine/'scripts/rvv/engines/bench_adaptive_dispatch_v2.cpp'
with tempfile.TemporaryDirectory() as d:
 for level,forced in [(0,0),(1,0),(2,0),(2,2)]:
  out=pathlib.Path(d)/f'unit_{level}_{forced}'
  cmd=[a.compiler,'-std=c++17','-O2', '-Wall','-Wextra','-Werror',
       '-I'+str(engine/'src'),f'-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL={level}',
       f'-DSIMDJSON_RVV_FORCE_PLAN={forced}',str(unit),'-o',str(out)]
  subprocess.run(cmd,check=True)
  subprocess.run([str(out)],check=True)
  print(f'PASS A{level} / forced={forced}: portable dispatch policy')
  if a.microbenchmark and not forced:
   bench=pathlib.Path(d)/f'bench_{level}'
   bench_cmd=cmd[:-3]+[str(probe),'-o',str(bench)]
   subprocess.run(bench_cmd,check=True);subprocess.run([str(bench)],check=True)
print('All portable tests passed. Native RVV parser correctness still required.')
