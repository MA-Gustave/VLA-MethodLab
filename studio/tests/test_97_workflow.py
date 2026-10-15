"""No network used; verifies Test97 Studio routing/status/download gates."""
from __future__ import annotations
import sys,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rvvlab_simple_tests import PROFILES,TEST_IDS,RUN_PATTERN,_server_runs,ZIP_NAME,test_id,manifest_target

class FakeSFTP:
    def __init__(self,files):self.files=files
    def listdir(self,path):
        return list({k[len(path.rstrip('/')+'/'):].split('/')[0] for k in self.files if k.startswith(path.rstrip('/')+'/')})
    def open(self,path,mode='r'):
        from io import BytesIO
        if path not in self.files:raise FileNotFoundError(path)
        return BytesIO(self.files[path])
    def stat(self,path):
        if path not in self.files:raise FileNotFoundError(path)
        return type('Stat',(),{'st_size':len(self.files[path])})()
    def close(self):pass

class FakeSSH:
    def __init__(self,files):self.client=type('Client',(),{'open_sftp':lambda _,:FakeSFTP(files)})()
    def base(self,remote):return '/home/users/test/rvvlab-v5'

class Workflow97(unittest.TestCase):
    def test_visible_on_both_targets_with_distinct_manifests(self):
        self.assertEqual(PROFILES['97'],('Cloud-V','EPCC'))
        self.assertEqual(TEST_IDS['97'],'test97-cloudv-8h')
        self.assertEqual(ZIP_NAME['97'],'test97_results.zip')
    def test_only_verified_completed_allows_download(self):
        rid='test97-20261015T123456Z-abcdef'
        root='/home/users/test/rvvlab-v5/test97-runs/'+rid
        self.assertTrue(RUN_PATTERN['97'].fullmatch(rid))
        files={root+'/test97_results.zip':b'fake-packet',root+'/status97.json':json.dumps({'state':'completed','rows':70,'validated':True}).encode()}
        rows=_server_runs(FakeSSH(files),'rvvlab-v5','97','Cloud-V')
        self.assertEqual(rows[0]['state'],'completed')
        self.assertTrue(rows[0]['validated'])
        files[root+'/status97.json']=json.dumps({'state':'completed','rows':70,'validated':False}).encode()
        rows=_server_runs(FakeSSH(files),'rvvlab-v5','97','Cloud-V')
        self.assertEqual(rows[0]['state'],'incomplete')
        files[root+'/status97.json']=json.dumps({'state':'running','rows':70,'validated':True}).encode()
        rows=_server_runs(FakeSSH(files),'rvvlab-v5','97','Cloud-V')
        self.assertEqual(rows[0]['state'],'running')
    def test_epcc_manifest_never_routes_to_cloudv(self):
        self.assertEqual(test_id('97','EPCC'),'test97-epcc-v5-3h')
        self.assertEqual(test_id('97','Cloud-V'),'test97-cloudv-8h')
        self.assertEqual(manifest_target('test97-epcc-v5-3h'),('97',('EPCC',)))

if __name__=='__main__':unittest.main()
