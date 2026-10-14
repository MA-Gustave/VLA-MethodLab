#!/usr/bin/env python3
"""Offline local-clock validation for Lab Studio (Windows/Linux, no SSH)."""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

LAB=Path(__file__).resolve().parents[1]
STUDIO=LAB/'studio'
sys.path.insert(0,str(STUDIO))
from rvvlab_local_time import clock_text, remote_utc_as_local, utc_offset_label


def verify():
    winter = datetime(2026, 1, 12, 14, 20, 30, tzinfo=timezone(timedelta(hours=-5)))
    summer = datetime(2026, 10, 12, 15, 4, 34, tzinfo=timezone(timedelta(hours=-4)))
    assert clock_text(winter) == 'PC  14:20:30 (UTC-05:00)   |   UTC  19:20:30'
    assert clock_text(summer) == 'PC  15:04:34 (UTC-04:00)   |   UTC  19:04:34'
    assert utc_offset_label(summer) == 'UTC-04:00'
    assert remote_utc_as_local('') == ''
    assert remote_utc_as_local(None) == ''
    assert remote_utc_as_local('not-an-iso-date') == 'not-an-iso-date'
    for value in ('2026-10-12T19:04:34+00:00', '2026-10-12T19:04:34Z'):
        timestamp=datetime(2026,10,12,19,4,34,tzinfo=timezone.utc).astimezone()
        expected=f'{timestamp:%Y-%m-%d %H:%M:%S} {utc_offset_label(timestamp)}'
        assert remote_utc_as_local(value)==expected
    naive='2026-10-12T19:04:34'
    assert remote_utc_as_local(naive)==remote_utc_as_local(naive+'Z')
    # The server's audit data must not be converted in-place.
    raw={'last_update':'2026-10-12T19:04:34+00:00'}
    _=remote_utc_as_local(raw['last_update'])
    assert raw['last_update']=='2026-10-12T19:04:34+00:00'
    # Syntax and integration checks without launching a GUI or using SSH.
    gui=(STUDIO/'RVV_Lab_Studio.pyw').read_text(encoding='utf-8')
    campaigns=(STUDIO/'rvvlab_unified_campaigns.py').read_text(encoding='utf-8')
    ast.parse(gui,filename='RVV_Lab_Studio.pyw')
    ast.parse(campaigns,filename='rvvlab_unified_campaigns.py')
    assert "self.root.after(1000,self._tick_clock)" in gui
    assert "textvariable=self.local_clock" in gui
    assert "remote_utc_as_local(x.get('last_update'))" in campaigns
    assert "Last update (PC)" in campaigns
    print('PASS: local-PC + UTC clocks, offsets, timestamp conversion and Studio integration')


if __name__=='__main__':verify()
