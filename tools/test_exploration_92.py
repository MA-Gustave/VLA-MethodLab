#!/usr/bin/env python3
"""Portable Test92 regression, no RISC-V, SSH or compilation required."""
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sys
import tempfile
import zipfile
from collections import Counter
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'engine/scripts/rvv/explore91'))
sys.path.insert(0,str(root/'studio'))
import campaign92, design
from rvvlab_test_runner import discover
from rvvlab_unified_campaigns import readable_test, display_rows
from rvvlab_backend import list_source_files
worker=root/'experiments/workers/92_staged_explorer_worker.py'
manifest_name='92_staged_explorer_8h.test.json'
manifest=json.loads((root/'studio/test_scripts'/manifest_name).read_text())
assert manifest==json.loads((root/'experiments/profiles'/manifest_name).read_text())
assert manifest['manual_only'] and manifest['params']['hours']==8
assert manifest['params']['worker_sha256']==hashlib.sha256(worker.read_bytes()).hexdigest()
assert worker.read_bytes()==(root/'studio/test_scripts'/worker.name).read_bytes()
found,errors=discover(root/'studio/test_scripts')
assert not errors,errors
assert any(x['id']==manifest['id'] for x in found)
assert Path('scripts/rvv/explore91/campaign92.py') in list_source_files(root/'engine')
assert readable_test({'campaign':'Test92','budget_seconds':28800})=='Test 92 — Adaptatif 8h'
assert readable_test({'campaign':'Test91','budget_seconds':3600})=='Test 91 — Pilote 1h'
assert readable_test({'campaign':'Test91','budget_seconds':28800})=='Test 91 — Exploration 8h'
assert display_rows([{'id':'night-20261012T230539Z-58065e','campaign':'Test91','budget_seconds':3600}])[0][1]=='Test 91 — Pilote 1h'
points=design.catalog();assert len(points)==242

def paired(group,variant,corpus,family='utf8',phase='screen',ratio=0.8,stage1=0.6,role='explore'):
    entries=[]
    for name,dom,s1 in (('A2',1,1),('official',1,1),(variant,ratio,stage1)):
        entries.append(dict(group=group,variant=name,corpus=corpus,family=family,
                            dom_all_gbps=dom,stage1_gbps=s1,stage2_gbps=1.01,
                            phase=phase,role=role))
    return entries

rows=paired('G1',points[4]['id'],'C1')+paired('G2',points[4]['id'],'C2',ratio=.9)
stats=campaign92.paired_stats(rows)
assert stats[points[4]['id']]['cases']==2
assert .84<stats[points[4]['id']]['dom']<.86
assert points[4]['id'] in campaign92.finalists(points,rows,{})
# Holdout and incomplete triplets MUST have no influence on selection.
hold=paired('H1',points[4]['id'],'H1',role='holdout',ratio=99,stage1=99)
assert campaign92.paired_stats(rows+hold)==stats
assert campaign92.finalists(points,rows+hold,{})==campaign92.finalists(points,rows,{})
assert campaign92.paired_stats(rows+paired('bad',points[4]['id'],'C3')[:2])==stats
# Screening diverse policies, 242 points on one common anchor each.
all_rows=[]
for i,p in enumerate(points):
    all_rows+=paired('S'+str(i),p['id'],f'C{i%6}',ratio=.5+(i%18)/50,stage1=.4+(i%10)/50)
short=campaign92.shortlist(points,all_rows,{},48)
assert len(short)==48 and all(p['id'] in short for p in points[:2])
policies={p['id']:p['settings']['policy'] for p in points}
assert set(policies[v] for v in short)=={0,1,2,3,4}
assert campaign92.shortlist(points,all_rows,{short[-1]:'bad'},48)[-1]!=short[-1] or short[-1] not in campaign92.shortlist(points,all_rows,{short[-1]:'bad'},48)

with tempfile.TemporaryDirectory(prefix='test92-') as tmp:
    t=Path(tmp);c=campaign92.Campaign(root/'engine',t/'run',8,max_mib=64)
    assert c.status['campaign']=='Test92'
    assert c.REPORT_FILENAME=='EXPLORATION_92.md'
    c.checkpoint('preflight',force=True)
    assert (c.root/'EXPLORATION_92.md').exists()
    assert not (c.root/'EXPLORATION_91.md').exists()
    with zipfile.ZipFile(c.root/'snapshot.zip') as z:
        assert 'EXPLORATION_92.md' in z.namelist()
        assert 'EXPLORATION_91.md' not in z.namelist()
        from rvvlab_night import verify_zip
        assert 'EXPLORATION_92.md' in verify_zip((c.root/'snapshot.zip').read_bytes())
    # Exercise actual 8-hour scheduler against virtual monotonic time.
    d=campaign92.Campaign(root/'engine',t/'simulation',8,max_mib=64)
    clock=[0.0]
    d.deadline_mono=600
    def fake_group(point,spec,phase,trial=0):
        assert clock[0] < d.deadline_mono
        clock[0]+=.5
        d.group_no+=1
        d.schedule.append(dict(phase=phase,candidate=point['id'],corpus=spec['id'],role=spec['role']))
        ratio=.6 + ((sum(point['id'].encode())%25)/100)
        d.rows.extend(paired(f'G{d.group_no}',point['id'],spec['id'],spec['family'],phase,ratio, .55+(ratio-.6)/5,spec['role']))
    d.group=fake_group
    d.checkpoint=lambda *args,**kwargs: None
    with patch.object(campaign92.time,'monotonic',lambda:clock[0]):
        d.explore()
    counts=Counter(x['phase'] for x in d.schedule)
    assert counts['screen']==242,counts
    assert counts['refine']>=48,counts
    assert counts['overhead_control']>2,counts
    assert counts['stage1_focus']>3,counts
    assert counts['holdout']>0,counts
    assert len(d.frozen)<=6 and d.frozen
    assert all(x['role']=='holdout' for x in d.schedule if x['phase']=='holdout')
    assert all(x['role']!='holdout' for x in d.schedule if x['phase']!='holdout')
    assert all(len(set(row['corpus'] for row in d.rows if row['role']=='holdout' and row['group']==group))==1
               for group in set(row['group'] for row in d.rows if row['role']=='holdout'))
    assert d.status['screened_compositions']==242
    assert d.status['overhead_control_groups']==counts['overhead_control']
print('PASS: Test92 242 screen, 48 refine, Stage1 controls, frozen holdout, Studio, SHA256, snapshot verification. Native RVV not tested.')
