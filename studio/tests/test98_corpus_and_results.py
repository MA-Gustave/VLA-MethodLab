"""Offline unit tests using invented unit-test JSON, NOT benchmark data."""
import hashlib,io,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from importlib.util import spec_from_file_location,module_from_spec
ROOT=Path(__file__).resolve().parents[2]
spec=spec_from_file_location('corpus98',ROOT/'tools/corpus98.py')
corpus=module_from_spec(spec);spec.loader.exec_module(corpus)
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_epcc_results import RUN_TYPES,discover_epcc_runs,sync_epcc_run
from rvvlab_test_center import local_state
from test_epcc_results import FakeSSH,BASE

def fixture_zip(bad=False):
    files=[];b=io.BytesIO()
    with zipfile.ZipFile(b,'w',zipfile.ZIP_DEFLATED) as z:
        for name in corpus.FILES:
            data=b'{"test":1}'
            files.append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),
                          'source_path':'jsonexamples/'+name})
            z.writestr('files/'+name,b'{"test":2}' if bad and name==corpus.FILES[0] else data)
        z.writestr('manifest.json',json.dumps({'schema':1,'corpus_id':corpus.CORPUS_ID,
            'source_url':corpus.SOURCE_URL,'upstream_commit':corpus.SOURCE_COMMIT,'files':files}))
    return b.getvalue()

class Test98Offline(unittest.TestCase):
    def test_verify_extract_cache_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)/'data.zip';archive.write_bytes(fixture_zip())
            self.assertEqual(len(corpus.verify(archive)['files']),len(corpus.FILES))
            corpus.extract(archive,Path(td)/'cache')
            corpus.extract(archive,Path(td)/'cache')
            self.assertTrue((Path(td)/'cache'/corpus.CORPUS_ID/'files/twitter.json').exists())
    def test_reject_tampered_member(self):
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)/'bad.zip';archive.write_bytes(fixture_zip(True))
            with self.assertRaisesRegex(ValueError,'hash mismatch'):corpus.verify(archive)
    def test_reject_extra_path(self):
        with tempfile.TemporaryDirectory() as td:
            archive=Path(td)/'bad.zip';archive.write_bytes(fixture_zip())
            with zipfile.ZipFile(archive,'a') as z:z.writestr('../extraneous','bad')
            with self.assertRaisesRegex(ValueError,'Unexpected corpus archive entries'):corpus.verify(archive)
    def test_local_download_uses_pinned_urls_and_cache(self):
        from unittest.mock import patch
        visited=[]
        def fake_download(request,timeout):
            url=request.full_url
            self.assertIn(corpus.SOURCE_COMMIT,url)
            visited.append(url)
            return io.BytesIO(b'{"published_fixture_test":true}')
        with tempfile.TemporaryDirectory() as td:
            with patch.object(corpus.urllib.request,'urlopen',side_effect=fake_download):
                corpus.prepare(Path(td)/'cache')
                corpus.prepare(Path(td)/'cache')
            self.assertEqual(len(visited),len(corpus.FILES))
            self.assertEqual(len(corpus.verify(Path(td)/'cache'/(corpus.CORPUS_ID+'.zip'))['files']),len(corpus.FILES))

    def test_network_failure_cannot_create_fake_corpus(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            with patch.object(corpus.urllib.request,'urlopen',side_effect=OSError('offline')):
                with self.assertRaisesRegex(OSError,'offline'):
                    corpus.prepare(Path(td)/'cache')
            self.assertFalse((Path(td)/'cache'/(corpus.CORPUS_ID+'.zip')).exists())

    def test_epcc_test98_campaign_sync(self):
        run='test98-20261015T200000Z-abc123';cfg=RUN_TYPES['test98'];root=BASE+'/test98-epcc-runs/'+run
        b=io.BytesIO()
        with zipfile.ZipFile(b,'w') as z:
            for n in cfg['required']:z.writestr(n,b'{}' if n.endswith('json') else b'rows')
        packet=b.getvalue();data={root+'/status98.json':b'{"state":"completed","rows":12}',
            root+'/test98_results.zip':packet,
            root+'/test98_results.sha256':(hashlib.sha256(packet).hexdigest()+'  test98_results.zip\n').encode()}
        ssh=FakeSSH(data)
        self.assertEqual(discover_epcc_runs(ssh,'rvvlab-v5')[0]['kind'],'test98')
        with tempfile.TemporaryDirectory() as td:
            directory=sync_epcc_run(ssh,'rvvlab-v5',run,td)
            self.assertTrue((directory/'SYNC_OK.txt').is_file())
            self.assertEqual(local_state({'id':'test98-real-corpus'},td)['state'],'downloaded')

if __name__=='__main__':unittest.main()
