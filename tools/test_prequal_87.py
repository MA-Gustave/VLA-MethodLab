#!/usr/bin/env python3
"""Offline corpus and sampling correctness tests; native RVV throughput NOT tested."""
from pathlib import Path
import hashlib,importlib.util,json,tempfile
worker=Path(__file__).resolve().parents[1]/'experiments/workers/87_prequal_exploration_60m_worker.py'
spec=importlib.util.spec_from_file_location('rvvlab_survey87',worker)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with tempfile.TemporaryDirectory(prefix='rvvlab-87-') as tmp:
    campaign=module.Campaign.__new__(module.Campaign)
    campaign.root=Path(tmp);campaign.meta={};campaign.check=lambda **kw:None
    campaign.checkpoint=lambda *args,**kw:None
    corpi=module.Campaign.make_corpus(campaign)
    assert len(corpi)==174
    manifest=json.loads((campaign.root/'corpus_manifest.json').read_text(encoding='utf8'))
    assert len(manifest['scenarios'])==174
    assert len({r['id'] for r in manifest['scenarios']})==174
    for item in manifest['scenarios']:
        path=campaign.root/item['id']
        data=path.read_bytes()
        assert len(data)==item['bytes'] and hashlib.sha256(data).hexdigest()==item['sha256']
        json.loads(data)
        if item['exact_target']:
            assert len(data)==item['size_target']
    assert sum(1 for x in manifest['scenarios'] if x['exact_target'])==21
    for pos,key in (('front','head'),('middle','middle'),('back','tail')):
        p=next(x for x in manifest['scenarios'] if x['kind']=='escaped'
              and x['size_target']==262144 and x['distribution']==pos)
        assert p['sample_windows'][key]['slash_density']>.02,(pos,p)
    print('PASS: 174 deterministic parseable cases, 21 exact thresholds, front/mid/back sampling contrasts')
