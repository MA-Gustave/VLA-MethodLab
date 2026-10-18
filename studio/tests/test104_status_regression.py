"""Tests 103 and 104: completed remote state reaches both Studio views.

No SSH, Slurm, subprocess, or real remote jobs. Simulated Cloud-V and EPCC
success records and fault isolation on the Tk event-queue callback.
"""
from __future__ import annotations

import queue
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rvvlab_unified_campaigns import UnifiedCampaigns
from rvvlab_simple_tests import SimpleTestsPanel


def done(number):
    return {'id':f'test{number}-20261017T124313Z-be7f18',
            'path':f'/verified/test{number}-runs/test{number}-20261017T124313Z-be7f18',
            'state':'completed','rows':118560,'validated':True,'packet':True}


class TestCompletedStatePropagation(unittest.TestCase):
    def test_completed_103_and_104_both_profiles(self):
        for profile in ('Cloud-V', 'EPCC'):
            with self.subTest(profile=profile):
                panel=UnifiedCampaigns.__new__(UnifiedCampaigns)
                panel.studio=SimpleNamespace(active_profile=profile)
                panel.verified_by_profile={}
                panel.history_rows=[]
                rendered=[]
                panel._set_rows=lambda rows:rendered.append(rows)
                panel.apply_verified_campaigns(profile, {'103':[done('103')], '104':[done('104')]}, [])
                rows=panel.verified_by_profile[profile]
                self.assertEqual([x['test_id'] for x in rows],
                    ['test103-stage2-optimization','test104-independent-public-validation'])
                self.assertTrue(all(x['state']=='completed' and x['packet'] and x['validated'] for x in rows))
                self.assertEqual([x['observations'] for x in rows],[118560,118560])
                self.assertEqual(len(rendered),1)

    def test_104_does_not_regress_103_download_and_open_routing(self):
        path=Path(__file__).resolve().parents[1]/'rvvlab_unified_campaigns.py'
        src=path.read_text(encoding='utf-8')
        self.assertIn("'test103':'103','test104':'104'",src)
        self.assertIn("'103':'test103-stage2-optimization','104':'test104-independent-public-validation'",src)
        for method in ('def _buttons(', 'def _action(', 'def open_results('):
            self.assertIn(method,src)
        # Download, STOP protections and Open Results must use managed routing.
        self.assertEqual(src.count("'test101','test102','test103','test104'"),5)

    def test_history_crash_does_not_kill_main_status_or_250ms_queue(self):
        for profile in ('Cloud-V','EPCC'):
            with self.subTest(profile=profile):
                class BrokenHistory:
                    def apply_verified_campaigns(self,*_args):raise KeyError('new test id')
                    poll_busy=False
                    busy=False
                events=queue.Queue();events.put(('status',(profile,{'104':[done('104')]},[],None)))
                notices=[];logs=[];reschedule=[]
                runner=SimpleNamespace(apply_verified_campaigns=lambda *args:logs.append(('main',args)),
                                       _log=lambda message:logs.append(('log',message)),busy=False)
                panel=SimpleTestsPanel.__new__(SimpleTestsPanel)
                panel.events=events
                panel.studio=SimpleNamespace(active_profile=profile,test_runner=runner,
                    unified_campaigns=BrokenHistory(),vars={'results':SimpleNamespace(get=lambda:'/tmp/nonexistent')})
                panel.tree=SimpleNamespace(get_children=lambda:[])
                panel.parent=SimpleNamespace(after=lambda delay,func:reschedule.append((delay,func)))
                panel.notice=SimpleNamespace(set=notices.append)
                panel.poll_busy=True
                panel.remote_activity=[]
                panel.last_check_error='old'
                panel.runs={}
                panel.launch_number=None
                panel._selected=lambda:None
                panel._highlight_selection=lambda:None
                panel._drain()
                self.assertTrue(panel.remote_checked)
                self.assertEqual(panel.runs['104'][0]['state'],'completed')
                self.assertEqual(panel.runs['104'][0]['rows'],118560)
                self.assertFalse(panel.poll_busy)
                self.assertEqual(reschedule[0][0],250)
                self.assertTrue(any(x[0]=='main' for x in logs))
                self.assertTrue(any(x[0]=='log' and 'history' in x[1].lower() for x in logs))
                self.assertTrue(any('verified at' in notice for notice in notices))

if __name__=='__main__':unittest.main()
