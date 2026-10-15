"""Offline regression tests: EPCC runs in a separate folder from NightRuns."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rvvlab_epcc_results import RUN_TYPES, discover_epcc_runs, sync_epcc_run
from rvvlab_test_center import local_state

BASE='/home/gustave/rvvlab-v5'
RUN='test96-20261015T024539Z-2b3b1d'


class FakeSFTP:
    def __init__(self,data):self.data=data
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def open(self,path,mode='r'):
        if path not in self.data:raise FileNotFoundError(2, "No such file", path)
        return io.BytesIO(self.data[path])
    def stat(self,path):
        if path not in self.data:raise FileNotFoundError(2, "No such file", path)
        return type('stat',(),{'st_size':len(self.data[path])})()
    def listdir(self,path):
        if not any(p.startswith(path+'/') for p in self.data):raise FileNotFoundError(2, "No such file", path)
        return list({p[len(path)+1:].split('/')[0] for p in self.data if p.startswith(path+'/')})
    def get(self,remote,local):
        Path(local).write_bytes(self.data[remote])


class FakeSSH:
    def __init__(self,data):self.client=type('client',(),{'open_sftp':lambda _:FakeSFTP(data)})();self.data=data
    def base(self,remote):
        assert remote=='rvvlab-v5'
        return BASE
    def exec_text(self,cmd):
        for path,data in self.data.items():
            if path in cmd and path.endswith('.zip'):
                return hashlib.sha256(data).hexdigest()+'  '+path.rsplit('/',1)[-1]+'\n'
        raise AssertionError('Unexpected shell command: '+cmd)


def payload(extra=None):
    cfg=RUN_TYPES['test96']
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in cfg['required']:
            z.writestr(name,b'{"state":"completed"}' if name.endswith('.json') else b'example')
        if extra:z.writestr(extra,b'bad')
    archive=buf.getvalue()
    root=BASE+'/test96-epcc-runs/'+RUN
    return {root+'/status96.json':json.dumps({'state':'completed','rows':48}).encode(),
            root+'/test96_results.zip':archive,
            root+'/test96_results.sha256':(hashlib.sha256(archive).hexdigest()+'  test96_results.zip\n').encode()}


class EpccResultsTests(unittest.TestCase):
    def test_remote_only_discovery_and_sync_without_launch96(self):
        ssh=FakeSSH(payload())
        runs=discover_epcc_runs(ssh,'rvvlab-v5')
        self.assertEqual(len(runs),1)
        self.assertEqual(runs[0]['id'],RUN)
        self.assertEqual(runs[0]['state'],'completed')
        self.assertTrue(runs[0]['packet'])
        with tempfile.TemporaryDirectory() as t:
            folder=sync_epcc_run(ssh,'rvvlab-v5',RUN,t)
            self.assertTrue((folder/'SYNC_OK.txt').exists())
            self.assertTrue((folder/'test96_results.zip').exists())
            self.assertTrue((folder/'REPORT_96.md').exists())
            item={'id':'test96-epcc-8h'}
            result=local_state(item,t)
            self.assertEqual(result['state'],'downloaded')
            self.assertEqual(result['run_id'],RUN)

    def test_directory_only_is_not_a_completed_run(self):
        data=payload()
        data={p:b for p,b in data.items() if not p.endswith('.zip') and not p.endswith('.sha256')}
        rows=discover_epcc_runs(FakeSSH(data),'rvvlab-v5')
        self.assertEqual(rows[0]['state'],'unknown')
        self.assertFalse(rows[0]['packet'])
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(FileNotFoundError):sync_epcc_run(FakeSSH(data),'rvvlab-v5',RUN,t)

    def test_rejects_mismatched_sha256(self):
        data=payload()
        path=BASE+'/test96-epcc-runs/'+RUN+'/test96_results.sha256'
        data[path]=('f'*64+'  test96_results.zip\n').encode()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(RuntimeError,'manifeste'):
                sync_epcc_run(FakeSSH(data),'rvvlab-v5',RUN,t)
            dest=Path(t)/'TestRunner'/'test96-epcc-8h'/('EPCC-'+RUN)
            self.assertFalse((dest/'SYNC_OK.txt').exists())

    def test_rejects_unsafe_zip_entries(self):
        data=payload('../evil.txt')
        path=BASE+'/test96-epcc-runs/'+RUN+'/test96_results.zip'
        sha=hashlib.sha256(data[path]).hexdigest()
        data[BASE+'/test96-epcc-runs/'+RUN+'/test96_results.sha256']=(sha+'  test96_results.zip\n').encode()
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'inattendus'):
                sync_epcc_run(FakeSSH(data),'rvvlab-v5',RUN,t)
            self.assertFalse((Path(t)/'evil.txt').exists())

    def test_test94_packet_can_be_recovered_without_toolbar(self):
        run='test94-20261013T233735Z-728f3a'
        cfg=RUN_TYPES['test94']
        archive=io.BytesIO()
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
            for name in cfg['required']:z.writestr(name,b'fake measurement file')
        remote=BASE+'/test94-runs/'+run
        packet=archive.getvalue()
        data={remote+'/status94.json':b'{"state":"failed","rows":7}',
              remote+'/test94_results.zip':packet,
              remote+'/test94_results.sha256':(hashlib.sha256(packet).hexdigest()+'  test94_results.zip\n').encode()}
        ssh=FakeSSH(data)
        rows=discover_epcc_runs(ssh,'rvvlab-v5')
        self.assertEqual(rows[0]['state'],'failed')
        with tempfile.TemporaryDirectory() as t:
            folder=sync_epcc_run(ssh,'rvvlab-v5',run,t)
            self.assertTrue((folder/'SYNC_OK.txt').exists())
            state=local_state({'id':'machine-compare-94-1h'},t)
            self.assertEqual(state['state'],'downloaded')
            self.assertEqual(state['run_id'],run)

    def test_test97_official_baseline_campaign_and_verified_sync(self):
        run='test97-20261015T130000Z-21cdef'
        cfg=RUN_TYPES['test97']
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
            for name in cfg['required']:
                z.writestr(name,b'{"state":"completed"}' if name.endswith('.json') else b'example')
        packet=buf.getvalue()
        root=BASE+'/test97-epcc-runs/'+run
        data={root+'/status97.json':b'{"state":"completed","rows":4500}',
              root+'/test97_results.zip':packet,
              root+'/test97_results.sha256':(hashlib.sha256(packet).hexdigest()+'  test97_results.zip\n').encode()}
        rows=discover_epcc_runs(FakeSSH(data),'rvvlab-v5')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['kind'],'test97')
        self.assertEqual(rows[0]['state'],'completed')
        with tempfile.TemporaryDirectory() as t:
            folder=sync_epcc_run(FakeSSH(data),'rvvlab-v5',run,t)
            self.assertTrue((folder/'REPORT_97.md').is_file())
            self.assertTrue((folder/'SYNC_OK.txt').is_file())
            state=local_state({'id':'test97-epcc-v5-3h'},t)
            self.assertEqual(state['state'],'downloaded')

    def test_rejects_unrecognized_remote_id(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaisesRegex(ValueError,'inconnu'):
                sync_epcc_run(FakeSSH({}),'rvvlab-v5','not-a-run',t)


if __name__=='__main__':unittest.main()
