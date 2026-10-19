#!/usr/bin/env python3
"""Read-only SHA-256 validation of a clean MethodLab release tree."""
from pathlib import Path
import hashlib,sys
root=Path(__file__).resolve().parents[1]
manifest=root/'SHA256SUMS.txt'
if not manifest.is_file(): sys.exit('Missing SHA256SUMS.txt')
errors=[];checked=0
for idx,line in enumerate(manifest.read_text('utf-8').splitlines(),1):
 if not line.strip():continue
 try:expected,name=line.split('  ',1)
 except ValueError: errors.append(f'bad record {idx}');continue
 p=(root/name).resolve()
 if root not in p.parents or not p.is_file():errors.append('missing/unsafe: '+name);continue
 h=hashlib.sha256()
 with p.open('rb') as f:
  for part in iter(lambda:f.read(1024*1024),b''):h.update(part)
 if h.hexdigest()!=expected:errors.append('digest mismatch: '+name)
 checked+=1
print(f'SHA-256: checked {checked} entries; errors={len(errors)}')
for e in errors[:40]:print('FAIL',e)
if errors:sys.exit(1)
