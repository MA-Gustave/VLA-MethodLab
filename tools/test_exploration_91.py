#!/usr/bin/env python3
"""Portable offline release gate. --full checks every generator design at bounded size.
--cpp compiles the portable policy test if g++ exists. No SSH, no fcntl, no native RVV claim.
"""
from pathlib import Path
import argparse,csv,hashlib,importlib.util,json,random,shutil,subprocess,sys,tempfile,zipfile
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'engine/scripts/rvv/explore91'))
import design,campaign
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--full',action='store_true');p.add_argument('--cpp',action='store_true');args=p.parse_args()
points=design.catalog();specs=design.corpus_specs()
assert len(points)==242 and len(specs)==2304
assert len({p['wire'] for p in points})==len(points)
assert set(p['settings']['policy'] for p in points)=={0,1,2,3,4}
assert len({s['seed'] for s in specs})==len(specs)
assert all(len(p['wire'].split(','))==23 for p in points)
assert max(s['target'] for s in specs)==64*1048576
worker=root/'experiments/workers/91_composition_explorer_worker.py'
assert worker.read_bytes()==(root/'studio/test_scripts'/worker.name).read_bytes()
for suffix in ('pilot','8h'):
 name=f'91_composition_explorer_{suffix}.test.json'
 a=json.loads((root/'experiments/profiles'/name).read_text('utf8'));b=json.loads((root/'studio/test_scripts'/name).read_text('utf8'))
 assert a==b and a['enabled'] and a['manual_only']
 assert a['params']['worker_sha256']==hashlib.sha256(worker.read_bytes()).hexdigest()
sys.path.insert(0,str(root/'studio'))
from rvvlab_test_runner import discover
found,errors=discover(root/'studio/test_scripts');assert not errors,errors
assert len([f for f in found if f['id'].startswith('composition-explorer-91')])==2
syncs=[]
for folder in ('studio','orchestrator'):
 sp=importlib.util.spec_from_file_location(folder+'_sync91',root/folder/'rvvlab_night.py');m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);syncs.append(m)
with tempfile.TemporaryDirectory(prefix='rvvlab91-') as temp:
 t=Path(temp);c=campaign.Campaign(root/'engine',t/'run',1)
 c.make_validation_cases()
 for line in (c.root/'valid.jsonl').read_bytes().splitlines():json.loads(line)
 c.checkpoint('preflight',True)
 for m in syncs:
  decoded=m.verify_zip((c.root/'snapshot.zip').read_bytes());assert set(decoded)==set(campaign.FILES)
 # Full matrix of geometry/encoding designs, smaller temporary sizes; separate
 # original-size large document below. No multi-gigabyte corpus retained.
 hashes=set()
 for spec in specs if args.full else specs[::97]:
  small={**spec,'target':min(8192,spec['target'])}
  info=design.generate(small,t/'corpus.json');blob=(t/'corpus.json').read_bytes()
  json.loads(blob);assert info['sha256']==hashlib.sha256(blob).hexdigest()
  assert info['sha256'] not in hashes;hashes.add(info['sha256'])
  assert info['bytes']>=small['target'] and sum(info['family_bytes'].values())<=info['bytes']
 if args.full:
  large=next(s for s in specs if s['target']==64*1048576 and s['kinds']==['long_strings'])
  info=design.generate(large,t/'large.json');json.loads((t/'large.json').read_bytes())
  assert info['bytes']>=64*1048576
 # Exercise real triplet orchestration with a fake native executable interface.
 def native(tag,mode,items,point=None,timeout=120):
  if mode=='validate':return 'RVV_VALIDATION_OK backend=rvv'
  path=Path(items[0]);size=path.stat().st_size
  if mode=='trace':return f'TRACE 1 0 0 {size} 0 0 0\nDOM_AGREES\n'
  it=int(items[1]);rate=2 if tag=='compositions' else 1
  return f'SPLIT_RESULT {rate} {rate} {rate} .01 .01 .01 {it} {size}'
 c.native=native
 c.group(points[1],specs[0],'screen')
 c.group(points[1],specs[1],'explore')
 assert len(c.rows)==6 and len(c.diagnostics)==2
 summary=design.matched_summary(c.rows);assert summary[0]['cases']==2 and summary[0]['dom_vs_A2']==2
 # Incomplete pairs and held-out cases cannot train policy selection.
 before=design.matched_summary(c.rows)
 extra={**c.rows[0],'group':'partial','variant':points[2]['id']}
 assert design.matched_summary(c.rows+[extra])==before
 hold=[{**r,'group':'hold'+r['group'],'role':'holdout'} for r in c.rows]
 assert design.matched_summary(c.rows+hold)==before
 # Candidate correctness failure is quarantined, STOP and disk guards preserve data.
 def broken(*a,**kw):raise RuntimeError('injected DOM mismatch')
 c.native=broken;c.group(points[3],specs[2],'explore');assert points[3]['id'] in c.rejected and len(c.rows)==6
 assert not (c.root/'active_corpus.json').exists()
 (c.root/'STOP').write_text('stop')
 try:c.check();raise AssertionError('STOP ignored')
 except campaign.support.Stopped:pass
 (c.root/'STOP').unlink()
 usage=shutil.disk_usage(c.root)
 with patch.object(campaign.shutil,'disk_usage',return_value=type(usage)(usage.total,usage.used,199*1048576)):
  try:c.check();raise AssertionError('disk guard ignored')
  except campaign.support.Safety:pass
 c.status.update(state='stopped',stop_reason='portable simulation');c.checkpoint(force=True)
 for m in syncs:assert m.verify_zip((c.root/'snapshot.zip').read_bytes())
 # SHA256 and allowlist tampering remains rejected.
 with zipfile.ZipFile(c.root/'snapshot.zip') as z:entries={n:z.read(n) for n in z.namelist()}
 entries['map.csv']+=b'tampered'
 with zipfile.ZipFile(t/'bad.zip','w') as z:
  for n,data in entries.items():z.writestr(n,data)
 for m in syncs:
  try:m.verify_zip((t/'bad.zip').read_bytes());raise AssertionError('corrupt sync accepted')
  except ValueError:pass
 # Drive the actual broad scheduler with a virtual clock and synthetic native
 # results: screen, exploratory sampling, repeats and frozen holdout must occur.
 d=campaign.Campaign(root/'engine',t/'scheduler',1,max_mib=1)
 d.points=points[:4];d.byid={p['id']:p for p in d.points}
 clock=[0.0];d.deadline_mono=300.0
 def scheduled(point,spec,phase,trial=0):
  d.check();clock[0]+=1;d.group_no+=1
  d.validated.add(point['id'])
  d.schedule.append(dict(candidate=point['id'],corpus=spec['id'],phase=phase))
  for tag in ('A2','official',point['id']):
   d.rows.append(dict(group=str(d.group_no),role=spec['role'],phase=phase,variant=tag,corpus=spec['id'],family=spec['family'],dom_all_gbps=2 if tag==point['id'] else 1))
 d.group=scheduled
 d.checkpoint=lambda *a,**kw:None
 with patch.object(campaign.time,'monotonic',lambda:clock[0]):
  try:d.explore()
  except campaign.support.Deadline:pass
 phases={x['phase'] for x in d.schedule}
 assert {'screen','explore','repeat','holdout'}<=phases,phases
 assert d.frozen
 first_hold=next(i for i,r in enumerate(d.rows) if r['role']=='holdout')
 assert design.matched_summary(d.rows)==design.matched_summary(d.rows[:first_hold])
 if args.cpp:
  compiler=shutil.which('g++')
  if not compiler:raise RuntimeError('--cpp requires g++; omit it for Windows Python-only checks')
  binary=t/'policy'
  subprocess.run([compiler,'-std=c++17','-O2','-Wall','-Wextra','-Werror','-DSIMDJSON_RVV_EXPLORATION91=1','-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-I'+str(root/'engine/src'),str(root/'engine/scripts/rvv/engines/test_exploration91.cpp'),'-o',str(binary)],check=True)
  for point in points:subprocess.run([str(binary),point['wire']],check=True,stdout=subprocess.DEVNULL)
print('PASS: Test91 242 effective compositions, 2304 designs, portable generation/pairing/quarantine/stop/disk/sync, Studio hashes. Native RVV is still required.')
