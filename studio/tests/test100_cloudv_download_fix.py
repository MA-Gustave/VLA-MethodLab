"""Offline SSH simulation for Test100 Cloud-V Windows result download."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import zipfile

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('rvvlab_test100_download', BASE/'rvvlab_test100_download.py')
download = importlib.util.module_from_spec(spec)
spec.loader.exec_module(download)
RUN = 'test100-20261016T144947Z-d71754'
REMOTE = '/home/users/gleblanc/rvvlab-v5/test100-cloudv-runs/'+RUN


def example_zip(dest):
    status={'state':'completed','validated':True,'rows':14625}
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('status100.json',json.dumps(status))
        z.writestr('REPORT_100.md','# Test 100\n')
        z.writestr('results100.csv','variant,throughput\nA2_REF,123.4\n')
    return hashlib.sha256(dest.read_bytes()).hexdigest()


class SFTP:
    def __init__(self, remote_file):self.remote_file=remote_file;self.paths=[]
    def __enter__(self):return self
    def __exit__(self,*a):return False
    def stat(self,remote):
        self.paths.append(remote)
        assert isinstance(remote,str)
        assert remote == REMOTE+'/test100_results.zip'
        class Stat:pass
        st=Stat();st.st_size=self.remote_file.stat().st_size
        return st
    def get(self,remote,local):
        assert isinstance(remote,str) and isinstance(local,str)
        self.paths.append(remote)
        shutil.copyfile(self.remote_file,local)


class SSH:
    def __init__(self,archive, *, remote_sha=None):
        self.remote_file=archive
        self.digest=remote_sha or hashlib.sha256(archive.read_bytes()).hexdigest()
        self.sftp=SFTP(archive)
        self.client=self
        self.commands=[]
    def open_sftp(self):return self.sftp
    def exec_text(self,cmd):
        self.commands.append(cmd)
        assert cmd.startswith('sha256sum ')
        return self.digest+'  '+REMOTE+'/test100_results.zip\n'
    def base(self,name):return '/home/users/gleblanc/'+name


class TestCloudvDownload(unittest.TestCase):
    def test_verified_download_and_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.zip';digest=example_zip(source)
            ssh=SSH(source)
            got=download.sync_cloudv_test100(ssh,'rvvlab-v5',RUN,Path(tmp)/'local',workdir=Path(REMOTE))
            self.assertTrue(got.is_file())
            self.assertEqual(download.sha256(got),digest)
            self.assertIn('SHA256-verified Cloud-V', (got.parent/'SYNC_OK.txt').read_text())
            self.assertEqual(json.loads((got.parent/'status100.json').read_text())['rows'],14625)
            self.assertEqual(len(ssh.commands),1)
            self.assertEqual(ssh.sftp.paths,[REMOTE+'/test100_results.zip']*2)

    def test_sha_failure_does_not_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.zip';example_zip(source)
            ssh=SSH(source,remote_sha='0'*64)
            with self.assertRaisesRegex(RuntimeError,'SHA-256 mismatch'):
                download.sync_cloudv_test100(ssh,'rvvlab-v5',RUN,Path(tmp)/'local',workdir=Path(REMOTE))
            folder=Path(tmp)/'local'/'TestRunner'/'test100-adaptive-public'/('Cloud-V-'+RUN)
            self.assertFalse((folder/'SYNC_OK.txt').exists())
            self.assertFalse((folder/'test100_results.zip').exists())
            self.assertFalse((folder/'test100_results.zip.part').exists())

    def test_archive_path_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.zip'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('status100.json',json.dumps({'state':'completed','validated':True,'rows':1}))
                z.writestr('REPORT_100.md','ok')
                z.writestr('../escape.txt','BAD')
            with self.assertRaisesRegex(RuntimeError,'unexpected'):
                download.sync_cloudv_test100(SSH(source),'rvvlab-v5',RUN,Path(tmp)/'local',workdir=REMOTE)
            self.assertFalse((Path(tmp)/'escape.txt').exists())

    def test_invalid_completed_status_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'source.zip'
            with zipfile.ZipFile(source,'w') as z:
                z.writestr('status100.json',json.dumps({'state':'failed','validated':False,'rows':0}))
                z.writestr('REPORT_100.md','failed')
            with self.assertRaisesRegex(RuntimeError,'validated completed'):
                download.sync_cloudv_test100(SSH(source),'rvvlab-v5',RUN,Path(tmp)/'local',workdir=REMOTE)

    def test_run_id_rejected(self):
        with self.assertRaises(ValueError):
            download.sync_cloudv_test100(None,'rvvlab-v5','../oops','C:/Temp')

    def test_ui_routes_cloudv_test100_without_testcontext(self):
        text=(BASE/'rvvlab_simple_tests.py').read_text(encoding='utf-8')
        self.assertIn("if number=='100' and profile=='Cloud-V':",text)
        self.assertIn('packet=sync_cloudv_test100(',text)


if __name__=='__main__':unittest.main()
