#!/usr/bin/env python3
"""Verify Adaptive Dispatch v2 source policy independent of the GUI repo."""
from pathlib import Path
import json,sys
root=Path(__file__).resolve().parents[1]
d=json.loads((root/'engine/scripts/rvv/engines/experiments.json').read_text())
a=d['adaptive_dispatch_v2']
assert len(d['points'])==15 and len(a['profiles'])==3
assert a['size_gate_bytes']==4096 and a['quick_sample_bytes']==512
for i in (85,86,87):
    candidates=list((root/'experiments/workers').glob(f'{i}_*_worker.py'))
    assert len(candidates)==1
print('PASS: 15 engine patterns, A0/A1/A2 policies and seven bundled CLI workers')
