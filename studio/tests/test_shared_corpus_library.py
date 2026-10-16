"""Offline library protocol tests (the JSON below are TEST FIXTURES, not benchmark data)."""
import contextlib,hashlib,io,json,shlex,shutil,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch

LAB=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(LAB/'studio'))
import rvvlab_corpus_service as svc


def synthetic_zip():
    """Unit-test-only fake content, never distributed as a benchmark corpus."""
    m=svc.manager();records=[];buf=io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        for i,name in enumerate(m.FILES):
            blob=json.dumps({'fixture':i,'valid':True}).encode('utf-8')
            z.writestr('files/'+name,blob)
            records.append({'name':name,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
        z.writestr('manifest.json',json.dumps({'schema':1,'corpus_id':m.CORPUS_ID,
            'source_url':m.SOURCE_URL,'upstream_commit':m.SOURCE_COMMIT,'files':records}))
    return buf.getvalue()


class LocalSFTP:
    def __init__(self,ssh):self.ssh=ssh
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def put(self,src,dst,confirm=True):
        self.ssh.puts+=1
        target=self.ssh.resolve(dst);target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(src,target)
    def stat(self,p):return self.ssh.resolve(p).stat()
    def open(self,p,mode='r'):
        if 'w' in mode:self.ssh.resolve(p).parent.mkdir(parents=True,exist_ok=True)
        return self.ssh.resolve(p).open(mode)
    file=open


class LocalSSH:
    def __init__(self,root):
        self.root=Path(root);self.home='/home/testuser';self.puts=0;self.execs=[]
        self.client=type('Client',(),{'open_sftp':lambda unused:LocalSFTP(self)})()
    def resolve(self,path):return self.root/path.lstrip('/')
    def base(self,remote):
        if remote!='rvvlab-v5':raise ValueError('wrong remote name')
        return self.home+'/rvvlab-v5'
    def mkdir(self,path):self.resolve(path).mkdir(parents=True,exist_ok=True)
    def exec_text(self,command):
        self.execs.append(command)
        argv=shlex.split(command)
        if argv[:1]==['sha256sum']:
            target=self.resolve(argv[1]);return svc._sha(target)+'  '+argv[1]
        if argv[:2]==['mv','-f']:
            src=self.resolve(argv[2]);dst=self.resolve(argv[3]);dst.parent.mkdir(parents=True,exist_ok=True)
            src.replace(dst);return ''
        if argv[:2]==['rm','-f']:
            self.resolve(argv[2]).unlink(missing_ok=True);return ''
        if len(argv)==5 and argv[:2]==['python3',argv[1]] and argv[2]=='extract':
            with contextlib.redirect_stdout(io.StringIO()):
                svc.manager().extract(self.resolve(argv[3]),self.resolve(argv[4]))
            return argv[4]+'/'+svc.catalog()['id']
        raise AssertionError('Unexpected command: '+command)


class SharedCorpusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.lab=Path(self.temp.name)/'VLA-MethodLab';self.lab.mkdir()
        target=svc.archive_path(self.lab);target.parent.mkdir(parents=True)
        target.write_bytes(synthetic_zip())
        self.ssh=LocalSSH(Path(self.temp.name)/'server')
    def test_local_archive_has_correct_manifest(self):
        res=svc.inspect_local(self.lab)
        self.assertEqual(res['state'],'verified')
        self.assertEqual(res['count'],18)
        self.assertEqual(res['total_bytes'],sum(x['bytes'] for x in res['files']))
    def test_remote_absent_cannot_be_claimed_verified(self):
        d=svc.inspect_local(self.lab)['digest']
        self.assertEqual(svc.remote_probe(self.ssh,'rvvlab-v5',d)['state'],'absent')
        with self.assertRaisesRegex(RuntimeError,'Sync the corpus'):
            svc.require_remote(self.ssh,'rvvlab-v5',self.lab)
    def test_sync_pinned_corpus_and_reuse_without_reupload(self):
        s=svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        self.assertEqual(s['state'],'verified')
        self.assertEqual(s['count'],18)
        self.assertTrue(self.ssh.resolve(s['data']+'/files/twitter.json').is_file())
        got=svc.require_remote(self.ssh,'rvvlab-v5',self.lab)
        self.assertEqual(got['archive_sha256'],svc.inspect_local(self.lab)['digest'])
        uploaded=self.ssh.puts
        again=svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        self.assertEqual(again['state'],'verified')
        self.assertEqual(self.ssh.puts,uploaded)
    def test_tamper_remote_archive_disables_reuse(self):
        s=svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        self.ssh.resolve(s['archive']).write_bytes(b'altered')
        self.assertEqual(svc.remote_probe(self.ssh,'rvvlab-v5',s['digest'])['state'],'invalid')
        with self.assertRaisesRegex(RuntimeError,'Sync the corpus'):
            svc.require_remote(self.ssh,'rvvlab-v5',self.lab)
    def test_corrupted_extracted_json_fails_deep_validation(self):
        s=svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        self.ssh.resolve(s['data']+'/files/twitter.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'tampered'):
            svc.remote_probe(self.ssh,'rvvlab-v5',s['digest'],deep=True)
    def test_tamper_local_archive_fails_closed(self):
        svc.archive_path(self.lab).write_bytes(b'bad zip')
        self.assertEqual(svc.inspect_local(self.lab)['state'],'invalid')
        with self.assertRaisesRegex(RuntimeError,'Invalid'):
            svc.prepare_local(self.lab)
    def test_trusted_manifest_can_require_shared_corpus(self):
        from rvvlab_test_runner import discover
        root=Path(self.temp.name)/'manifest';root.mkdir()
        (root/'sample.py').write_text('def execute(ctx,params): return {}\n',encoding='utf-8')
        doc={'schema':1,'id':'sample-shared','script':'sample.py','enabled':True,
             'manual_only':True,'requires_shared_corpus':True,'params':{}}
        (root/'sample.test.json').write_text(json.dumps(doc),encoding='utf-8')
        items,errors=discover(root)
        self.assertFalse(errors)
        self.assertTrue(items[0]['requires_shared_corpus'])
        doc['requires_shared_corpus']='yes'
        (root/'sample.test.json').write_text(json.dumps(doc),encoding='utf-8')
        items,errors=discover(root)
        self.assertFalse(items)
        self.assertTrue(any('requires_shared_corpus' in x for x in errors))
    def test_no_implicit_test_is_submitted(self):
        svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        self.assertFalse(any('sbatch' in x or 'nohup' in x for x in self.ssh.execs))
    def test_reuses_pinned_legacy_download_without_network(self):
        archive=svc.archive_path(self.lab);archive.unlink()
        old=self.lab/'engine'/'.cache'/'test98-corpus'/archive.name
        old.parent.mkdir(parents=True);old.write_bytes(synthetic_zip())
        with patch.object(svc.subprocess,'run',side_effect=AssertionError('unexpected network')):
            result=svc.prepare_local(self.lab)
        self.assertEqual(result['state'],'verified')
        self.assertEqual(svc._sha(old),svc._sha(archive))
    def test_identical_data_address_used_across_separate_target_ssh(self):
        cv=svc.sync_remote(self.ssh,'rvvlab-v5',self.lab)
        epcc=LocalSSH(Path(self.temp.name)/'epcc')
        ep=svc.sync_remote(epcc,'rvvlab-v5',self.lab)
        self.assertEqual(cv['digest'],ep['digest'])
        self.assertEqual(cv['data'].split('/')[-2:],ep['data'].split('/')[-2:])

if __name__=='__main__':unittest.main()
