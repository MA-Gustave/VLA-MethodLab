"""Regression tests for read-only elapsed duration in the main Studio workflow."""
import unittest
from datetime import datetime,timezone,timedelta
from rvvlab_elapsed import elapsed_display,run_start

UTC=timezone.utc

class ElapsedStatusTests(unittest.TestCase):
    def test_running_exact_timestamp(self):
        row={'id':'test97-20261015T190032Z-af59bc','state':'running','started_utc':'2026-10-15T20:00:00+00:00'}
        label,note=elapsed_display(row,datetime(2026,10,16,7,45,tzinfo=UTC))
        self.assertEqual(label,'11h 45m 00s')
        self.assertIn('reported start',note)

    def test_estimated_id_fallback_during_epcc_compile(self):
        row={'id':'test99-20261016T031241Z-839a48','state':'building'}
        label,note=elapsed_display(row,datetime(2026,10,16,4,12,41,tzinfo=UTC))
        self.assertEqual(label,'≈ 1h 00m 00s')
        self.assertIn('Estimated',note)

    def test_finished_freezes_at_update(self):
        row={'id':'test99-20261016T031241Z-839a48', 'state':'completed',
             'start_utc':'2026-10-16T04:00:00Z', 'updated_utc':'2026-10-16T12:00:00Z'}
        self.assertEqual(elapsed_display(row,datetime(2026,10,17,7,tzinfo=UTC))[0],'8h 00m 00s')
        self.assertEqual(elapsed_display(row,datetime(2026,10,20,7,tzinfo=UTC))[0],'8h 00m 00s')

    def test_finished_missing_end_never_keeps_running(self):
        row={'id':'test99-20261016T031241Z-839a48','state':'completed'}
        label,note=elapsed_display(row)
        self.assertEqual(label,'—');self.assertIn('no final timestamp',note)

    def test_invalid_start(self):
        self.assertEqual(elapsed_display({'id':'test99-INVALID','state':'running'})[0],'—')
        self.assertEqual(elapsed_display(None)[0],'—')
        self.assertEqual(elapsed_display({'started_utc':'junk','state':'running'})[0],'—')

    def test_day_and_clock_skew(self):
        start=datetime(2026,10,16,0,tzinfo=UTC)
        self.assertEqual(elapsed_display({'state':'running','started_utc':start},start+timedelta(days=1,hours=2,minutes=3,seconds=4))[0], '1d 02h 03m 04s')
        self.assertEqual(elapsed_display({'state':'running','started_utc':start},start-timedelta(minutes=4))[0], '—')

if __name__=='__main__':unittest.main()
