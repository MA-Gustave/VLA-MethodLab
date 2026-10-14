#!/usr/bin/env python3
"""Portable Test93 checks. Does not compile native RVV binaries."""
from collections import Counter
from pathlib import Path
from unittest.mock import patch
import hashlib
import json
import sys
import tempfile
import zipfile
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'engine/scripts/rvv/explore91'))
sys.path.insert(0,str(root/'studio'))
import campaign93
from rvvlab_test_runner import discover
from rvvlab_unified_campaigns import readable_test
from rvvlab_backend import list_source_files

worker=root/'experiments/workers/93_stage1_overhead_worker.py'
manifest_name='93_stage1_overhead_3h.test.json'
manifest=json.loads((root/'experiments/profiles'/manifest_name).read_text())
assert manifest==json.loads((root/'studio/test_scripts'/manifest_name).read_text())
assert manifest['params']['hours']==3.0 and manifest['manual_only']
assert hashlib.sha256(worker.read_bytes()).hexdigest()==manifest['params']['worker_sha256']
assert worker.read_bytes()==(root/'studio/test_scripts'/worker.name).read_bytes()
assert 'diagnose-93-3h' in (root/'tools/rvvlab.py').read_text()
found,errors=discover(root/'studio/test_scripts')
assert not errors, errors
assert any(i['id']==manifest['id'] for i in found)
assert readable_test({'campaign':'Test93','budget_seconds':10800})=='Test 93 — Stage1 + surcoût 3h'
assert Path('scripts/rvv/explore91/campaign93.py') in list_source_files(root/'engine')
assert len(campaign93.TARGETS)==9
with tempfile.TemporaryDirectory(prefix='rvv-test93-') as tmp:
    work=Path(tmp)
    try:
        campaign93.Campaign(root/'engine',work/'too_long',3.01,max_mib=8)
        raise AssertionError('Budget >3h permitted')
    except ValueError:
        pass
    c=campaign93.Campaign(root/'engine',work/'run',3,max_mib=8)
    assert c.status['campaign']=='Test93'
    assert len(c.targets)==9 and len(set(p['settings']['policy'] for p in c.targets))==5
    assert len(c._anchors())==12
    c.checkpoint('preflight',force=True)
    with zipfile.ZipFile(c.root/'snapshot.zip') as z:
        assert 'EXPLORATION_93.md' in z.namelist()
        assert 'controls93.csv' in z.namelist()
        from rvvlab_night import verify_zip
        assert 'EXPLORATION_93.md' in verify_zip((c.root/'snapshot.zip').read_bytes())
    # Exercise the real group() recording path with a fake native harness;
    # the bytes are genuinely generated, but no RISC-V code is executed.
    from unittest.mock import patch as patch_fn
    q=campaign93.Campaign(root/'engine',work/'group_path',3,max_mib=8)
    q.ensure_valid=lambda point: True
    q.checkpoint=lambda *args,**kwargs: None
    def fake_native(binary,mode,args,point):
        if mode=='trace':
            return 'TRACE 1 0 0 '+str(Path(args[0]).stat().st_size)+' 0 0 0\nDOM_AGREES\n'
        if mode=='check':
            return 'DOM_AGREES\n'
        if mode=='split':
            return 'FAKE '+binary+' '+str(args[-1])+' '+str(Path(args[0]).stat().st_size)
        raise AssertionError(mode)
    q.native=fake_native
    def fake_parse(text):
        _,tag,reps,size=text.split()
        rate={'A2':1.,'official':.6,'compositions':.8,'packed_plain':.9}[tag]
        return rate,rate*.8,1.01,0.001,0.,0.,int(reps),int(size)
    with patch_fn.object(campaign93.support,'parse_split_output',fake_parse):
        q.group(q.targets[0],q._anchors()[0],'diagnostic')
    assert len(q.rows)==3 and len(q.extra_rows)==1
    assert len(q.diagnostics)==1 and len(q.schedule)==1
    q.checkpoint=campaign93.Campaign.checkpoint.__get__(q,campaign93.Campaign)
    q.checkpoint('diagnostic',force=True)
    four=campaign93.paired_ratios(q.rows,q.extra_rows)
    assert abs(four[('explore','packed_plain')]['dom_all_gbps'][0]-.9)<1e-9
    assert abs(four[('explore',q.targets[0]['id'])]['dom_all_gbps'][0]-.8)<1e-9
    with zipfile.ZipFile(q.root/'snapshot.zip') as z:
        from rvvlab_night import verify_zip
        verified=verify_zip((q.root/'snapshot.zip').read_bytes())
        assert 'controls93.csv' in verified and q.targets[0]['id'].encode() in verified['EXPLORATION_93.md']
    # Verify group arithmetic, at least one switched regional plan, and all
    # four binaries paired on every (complete) simulated group.
    d=campaign93.Campaign(root/'engine',work/'simulation',3,max_mib=8)
    clock=[0.]
    d.deadline_mono=500
    d.build=lambda spec,upstream: True
    d.checkpoint=lambda *args,**kwargs: None
    called=[]
    def fake_group(point,spec,phase,trial=0):
        assert clock[0]<d.deadline_mono
        clock[0]+=1.8
        name=f'G{len(called)}'
        for tag,dom,st1 in [('A2',1.0,1.0),('official',.65,.8),(point['id'],.8,.55)]:
            d.rows.append(dict(group=name,role=spec['role'],phase=phase,variant=tag,
                               dom_all_gbps=dom,stage1_gbps=st1,stage2_gbps=1.,corpus=spec['id']))
        d.extra_rows.append(dict(group=name,role=spec['role'],phase=phase,
                                 variant='packed_plain',dom_all_gbps=.9,stage1_gbps=.85,
                                 stage2_gbps=1.,corpus=spec['id']))
        d.schedule.append(dict(group=name,phase=phase,role=spec['role'],
                               candidate=point['id'],corpus=spec['id']))
        called.append((phase,point['id'],spec['id'],spec['role']))
    d.group=fake_group
    with patch.object(campaign93.time,'monotonic',lambda:clock[0]):
        d.explore()
    counts=Counter(i[0] for i in called)
    assert counts['diagnostic'] >= 9
    assert counts['holdout'] >0
    assert all(x[3]=='holdout' for x in called if x[0]=='holdout')
    assert all(x[3]!='holdout' for x in called if x[0]!='holdout')
    assert d.frozen==list(campaign93.TARGETS)
    assert d.meta['coverage']['expected']==4
    ratios=campaign93.paired_ratios(d.rows,d.extra_rows)
    assert len(ratios[('explore','packed_plain')]['dom_all_gbps'])>0
    assert len(ratios[('holdout','official')]['dom_all_gbps'])>0
    # Holdout ratios cannot leak into diagnostic train subsets.
    for (role,tag) in ratios:
        if role=='explore':
            assert len(ratios[(role,tag)]['dom_all_gbps'])==sum(1 for t in called if t[3]=='explore' and (tag in ('official','packed_plain') or t[1]==tag))
    # Incomplete four-way groups do not contribute any paired ratios.
    extra_bad=[dict(group='bad',role='explore',phase='diagnostic',variant='packed_plain',dom_all_gbps=999,stage1_gbps=999,stage2_gbps=999)]
    assert campaign93.paired_ratios(d.rows,d.extra_rows+extra_bad).keys()==ratios.keys()
print('PASS: Test93 <=3h budget, 9 fixed policies, 4-build paired diagnostic, holdout isolation, Studio/CLI, SHA256, snapshot; native RISC-V untested.')
