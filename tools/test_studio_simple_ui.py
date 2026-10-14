#!/usr/bin/env python3
"""Legacy UI smoke adapted to the current Studio: immutable IDs + compact view.

The old `make_share_zip` presentation helper no longer exists. This test
validates the active source code and SHA-verified night sync design instead.
"""
from __future__ import annotations
from pathlib import Path
import io,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'studio'))
from rvvlab_friendly import CAMPAIGNS,run_identity,run_state,local_update,safe_evidence_name
from rvvlab_unified_campaigns import display_rows,campaign_start,campaign_details
from rvvlab_night import remote_runs
RID90='night-20261012T172225Z-1942f9'
RID89='night-20261012T133100Z-5a6468'

class MockSftp:
    def __init__(self,data):self.data=data
    def listdir(self,path):return [RID90,RID89]
    def open(self,path,mode='r'):
        item=self.data.get(tuple(path.rsplit('/',2)[-2:]))
        if item is None:raise OSError('missing')
        return io.BytesIO(json.dumps(item).encode())
    def close(self):pass
class MockSSH:
    def __init__(self,data):self.client=type('Client',(),{'open_sftp':lambda s:MockSftp(data)})()
    def base(self,remote):return '/remote'

def verify():
    assert CAMPAIGNS['adaptive_holdout_validation_2h'][0]=='90'
    data={
      (RID90,'status.json'):{'state':'stopped','stop_reason':'2-hour budget reached','observations':7808,
                              'last_update':'2026-10-12T19:22:25Z','campaign':'adaptive_holdout_validation_2h'},
      (RID90,'launcher.json'):{'run_id':RID90,'campaign':'adaptive_holdout_validation_2h'},
      (RID89,'status.json'):{'state':'failed','observations':0},
      (RID89,'launcher.json'):{'run_id':'night-WRONG','campaign':'adaptive_prequal_corrected_1h'},
    }
    rows=remote_runs(MockSSH(data),'rvvlab-v5')
    assert len(rows)==2
    assert rows[0]['campaign']=='adaptive_holdout_validation_2h'
    assert not rows[1].get('campaign')
    assert run_identity(rows[0])['number']=='90'
    assert run_state(rows[0])[0]=='Terminé — durée atteinte'
    assert '90' in safe_evidence_name(rows[0])
    assert local_update('bad')=='—'
    vals=display_rows(rows)
    assert vals[0][0].startswith('Test 90') and vals[0][1]=='Finished'
    assert vals[0][2].startswith('≈ ')
    assert vals[0][5]==7808
    assert RID90 not in repr(vals[0])
    assert RID90 in campaign_details(rows[0])
    print('PASS: legacy launcher mapping, compact Studio display, full details, start-time fallback')

if __name__=='__main__':verify()
