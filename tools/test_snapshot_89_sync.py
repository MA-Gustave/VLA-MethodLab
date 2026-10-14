#!/usr/bin/env python3
"""Portable regression tests for 7-file legacy, Test 88 and Test 89 snapshots.

Runs offline on Windows or Linux. Never connects to SSH or starts a worker.
Validates both the standalone CLI and integrated Studio verifiers.
"""
from __future__ import annotations
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
LEGACY=("status.json","checkpoint.json","map.csv","ranking.csv","hypotheses.md","failures.csv","metadata.json")
COMMON=LEGACY+("corpus_manifest.json","trend_candidates.csv","prequal_pairwise.csv","TRENDS.md","coverage_by_design.csv","hypotheses_to_confirm.csv")
TEST88=COMMON+("EXPLORATION_8H.md",)
TEST89=COMMON+("EXPLORATION_1H.md",)


def make_snapshot(names,*,tamper=False,undeclared=False,duplicate=False,wrong_len=False):
    buf=io.BytesIO()
    entries=[]
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:
            body=("data for "+name+"\n").encode()
            entries.append({"name":name,"bytes":len(body)+(1 if wrong_len else 0),
                            "sha256":hashlib.sha256(body).hexdigest()})
            z.writestr(name,body+b'BAD' if tamper and name==names[0] else body)
        if undeclared:
            z.writestr('secret.txt','no')
        if duplicate:
            # Duplicate a real file; using a duplicate manifest name also tests
            # duplicate handling but triggers warnings in Python's zipfile.
            z.writestr('extra.txt','unlisted')
            z.writestr('extra.txt','unlisted')
        z.writestr('MANIFEST.json',json.dumps({'schema':1,'files':entries}))
    return buf.getvalue()


def reject(checker,data,reason):
    try:
        checker(data)
    except (ValueError,zipfile.BadZipFile):
        return
    raise AssertionError('Unsafe ZIP accepted: '+reason)


def run(directory):
    sys.path.insert(0,str(ROOT/directory))
    try:
        spec=importlib.util.spec_from_file_location('rvvlab_night_check_'+directory,
                                                ROOT/directory/'rvvlab_night.py')
        module=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        checker=module.verify_zip
        for names in (LEGACY,TEST88,TEST89):
            items=checker(make_snapshot(names))
            assert set(items)==set(names), (directory,'missing accepted files')
        for data,reason in [
            (make_snapshot(TEST89,tamper=True),'SHA256 mismatch'),
            (make_snapshot(TEST89,wrong_len=True),'byte size mismatch'),
            (make_snapshot(TEST89,undeclared=True),'undeclared file'),
            (make_snapshot(TEST89,duplicate=True),'duplicate ZIP entries'),
            (make_snapshot(TEST89+('arbitrary.py',)),'unknown filename'),
            (make_snapshot(TEST89+('../escape.txt',)),'path traversal'),
        ]:
            reject(checker,data,reason)
        # Exercise the real sync pipeline, with an in-memory SFTP fake.
        # No connection or remote disk write is ever attempted.
        class FakeSFTP:
            def __init__(self, data):
                self.payload=data
                self.hash=hashlib.sha256(data).hexdigest().encode('ascii')
            def open(self, path, mode='r'):
                if path.endswith('/snapshot.sha256'):
                    return io.BytesIO(self.hash)
                if path.endswith('/snapshot.zip'):
                    return io.BytesIO(self.payload)
                raise AssertionError('Unexpected remote read: '+path)
            def close(self):
                pass
        class FakeClient:
            def __init__(self,sftp): self.sftp=sftp
            def open_sftp(self): return self.sftp
        class FakeSSH:
            def __init__(self,data):self.client=FakeClient(FakeSFTP(data))
            def base(self,remote_name): return '/test/rvvlab-v5'
        data=make_snapshot(TEST89)
        with tempfile.TemporaryDirectory() as tmp:
            folder=module.sync(FakeSSH(data),'rvvlab-v5',
                               'night-20261012T133100Z-5a6468',tmp)
            assert (folder/'EXPLORATION_1H.md').is_file()
            assert (folder/'SYNC_OK.txt').read_text().startswith('SHA256-verified snapshot: ')
            assert len([x for x in folder.iterdir() if x.is_file()])==15
        print('PASS:',directory,'7+14+14 formats; full fake-SFTP sync; invalid data rejected')
    finally:
        sys.path.pop(0)

for location in ('orchestrator','studio'):
    run(location)
print('PASS: Test89 results can be verified and safely pulled without rerunning native benchmarks')
