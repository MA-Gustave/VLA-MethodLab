"""Regression: larger pinned source ZIP may be read safely, without RAM spikes."""
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
import corpus_jsontestsuite as js


class FakeResponse:
    def __init__(self, n, headers=None):
        self.left=n
        self.headers=headers or {}
        self.closed=False
    def __enter__(self):return self
    def __exit__(self,*_):self.closed=True
    def read(self,n):
        size=min(n,self.left)
        self.left-=size
        return b'Q'*size


class StreamingTests(unittest.TestCase):
    def test_accepts_source_archive_larger_than_old_48_mib_limit(self):
        resp=FakeResponse(49*1024*1024)
        with patch.object(js.urllib.request,'urlopen',return_value=resp):
            archive=js._download_pinned_archive()
        try:
            self.assertEqual(archive.read(6),b'QQQQQQ')
            archive.seek(0,2)
            self.assertEqual(archive.tell(),49*1024*1024)
            self.assertTrue(resp.closed)
            self.assertEqual(js.MAX_DOWNLOAD,256*1024*1024)
            self.assertTrue(archive._rolled)  # Spooled to disk above 8 MiB.
        finally:archive.close()
    def test_cap_stops_stream_with_size_message(self):
        resp=FakeResponse(9*1024)
        with patch.object(js,'MAX_DOWNLOAD',8*1024):
            with patch.object(js.urllib.request,'urlopen',return_value=resp):
                with self.assertRaisesRegex(ValueError,'safety cap 8192'):
                    js._download_pinned_archive()
        self.assertTrue(resp.closed)
    def test_oversize_content_length_refused_without_reading(self):
        resp=FakeResponse(50,headers={'Content-Length':str(js.MAX_DOWNLOAD+1)})
        with patch.object(js.urllib.request,'urlopen',return_value=resp):
            with self.assertRaisesRegex(ValueError,'announced'):
                js._download_pinned_archive()
        self.assertEqual(resp.left,50)
    def test_empty_download_has_specific_error(self):
        with patch.object(js.urllib.request,'urlopen',return_value=FakeResponse(0)):
            with self.assertRaisesRegex(ValueError,'empty'):
                js._download_pinned_archive()
    def test_fails_closed_when_network_errors(self):
        with patch.object(js.urllib.request,'urlopen',side_effect=OSError('network failed')):
            with self.assertRaisesRegex(OSError,'network failed'):
                js._download_pinned_archive()

if __name__=='__main__':unittest.main()
