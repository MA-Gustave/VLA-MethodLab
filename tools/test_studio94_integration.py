#!/usr/bin/env python3
"""Offline smoke tests for Studio Test94 runner: fake SSH/SFTP and Slurm."""
from __future__ import annotations
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from types import SimpleNamespace
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
import rvvlab_test_runner as runner
spec=importlib.util.spec_from_file_location('studio94',ROOT/'studio'/'test_scripts'/'94_machine_1h.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class FakeSFTP:
    def put(self,src,dst,confirm=True):
        Path(dst).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
    def get(self,src,dst):shutil.copyfile(src,dst)
    def stat(self,p):return Path(p).stat()
    def close(self):pass

class FakeSSH:
    def __init__(self,home,mode):
        self.home=str(home);self.mode=mode;self.client=SimpleNamespace(open_sftp=lambda:FakeSFTP())
        self.commands=[];self.deployed=False
    def connected(self):return True
    def base(self,name):return self.home+'/'+name
    def mkdir(self,p):Path(p).mkdir(parents=True,exist_ok=True)
    def available_kib(self):return 2*1024*1024
    def deploy(self,archive,manifest,src_id,name,cb,stop):
        target=Path(self.base(name))/'sources'/src_id
        target.mkdir(parents=True)
        with zipfile.ZipFile(archive) as z:z.extractall(target)
        self.deployed=True
        return str(target)
    @staticmethod
    def _finish(workdir):
        dst=Path(workdir);dst.mkdir(parents=True,exist_ok=True)
        st={'state':'completed','phase':'finish','rows':42}
        (dst/'status94.json').write_text(json.dumps(st))
        with zipfile.ZipFile(dst/'test94_results.zip','w') as z:
            for name,text in [('status94.json',json.dumps(st)),('machine94.json','{"machine":"fake"}'),
                              ('summary94.json','{}'),('REPORT_94.md','# Report'),('results94.csv','x,y\n')]:
                z.writestr(name,text)
    def exec_text(self,cmd):
        self.commands.append(cmd)
        if cmd=='uname -m':return 'x86_64' if self.mode=='EPCC' else 'riscv64'
        if cmd.startswith('sha256sum '):
            import shlex
            p=Path(shlex.split(cmd)[1]);return hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p)
        if cmd.startswith('sinfo '):return 'rvc99|jupiter|idle|spacemit_k1,rvv1.0'
        if cmd.startswith('sbatch '):
            import shlex
            args=shlex.split(cmd)
            output=next((s for s in args if s.startswith('--chdir=')),None)
            assert output,cmd
            self._finish(output.split('=',1)[1]);return '123456'
        if cmd.startswith('bash -lc ') and 'TEST94_PID=' in cmd:
            import shlex,re
            inner=shlex.split(cmd)[2] if len(shlex.split(cmd))>2 else shlex.split(cmd)[-1]
            # Cloud-V run directory is the first cd argument.
            m=re.search(r'cd\s+(\S+)\s+&&',inner)
            assert m,inner
            self._finish(shlex.split(m.group(1))[0]);return 'TEST94_PID=1234'
        if cmd.startswith('if test -f '):
            import shlex
            args=shlex.split(cmd)
            p=Path(args[3])
            return p.read_text() if p.exists() else '{}'
        if cmd.startswith('squeue '):return ''
        if cmd.startswith('sacct '):return 'COMPLETED'
        if cmd.startswith('kill -0 '):return 'YES'
        raise RuntimeError('Unknown fake SSH command: '+cmd)
    def exec_stream(self,cmd,log,stop=None):
        self.commands.append(cmd);log('mock cross-compile OK');return 0

class FakeStop:
    def is_set(self):return False
    def wait(self,_):return False

class TestStudio94(unittest.TestCase):
    def test_discover_and_integrity(self):
        found,errors=runner.discover(ROOT/'studio'/'test_scripts')
        self.assertFalse(errors,errors)
        selected=[d for d in found if d['id']=='machine-compare-94-1h']
        self.assertEqual(len(selected),1)
        self.assertTrue(selected[0]['manual_only'])
        self.assertEqual(selected[0]['params']['seconds'],3600)

    def run_fake(self,mode):
        with tempfile.TemporaryDirectory() as t:
            base=Path(t);ssh=FakeSSH(base/'remote',mode)
            values={'repo':SimpleNamespace(get=lambda:str(ROOT/'engine')),
                    'remote_name':SimpleNamespace(get=lambda:'rvvlab-v5'),
                    'results':SimpleNamespace(get=lambda:str(base/'results'))}
            reported=[]
            studio=SimpleNamespace(vars=values,ssh=ssh,active_profile=mode,
                report_test94_state=lambda *args,**kwargs:reported.append((args,kwargs)))
            out=base/'results'/'TestRunner'/'test94';out.mkdir(parents=True)
            logs=[]
            ctx=SimpleNamespace(studio=studio,ssh=ssh,stop_event=FakeStop(),
                 remote_name='rvvlab-v5',output_dir=out,log=logs.append,ensure_connected=lambda:True)
            params={'seconds':3600}
            if mode=='EPCC':params.update(epcc_node='rvc99',epcc_partition='jupiter',epcc_account='gustave')
            result=mod.execute(ctx,params)
            self.assertTrue(ssh.deployed)
            self.assertEqual(result['state'],'completed')
            self.assertTrue((out/'test94_results.zip').is_file())
            self.assertTrue((out/'REPORT_94.md').is_file())
            self.assertTrue((out/'launch94.json').is_file())
            self.assertTrue(reported)
            self.assertEqual(reported[-1][0][1],'completed')
            self.assertEqual(reported[-1][0][0],mode)
            self.assertEqual(mod.recover(ctx,json.loads((out/'launch94.json').read_text()))['state'],'downloaded')
            self.assertTrue(any('sha256sum ' in x for x in ssh.commands))
            if mode=='EPCC':
                self.assertTrue(any(x.startswith('sbatch ') for x in ssh.commands))
                self.assertTrue(any('test94_epcc_build.py' in x and 'llvm-16.0' in x for x in ssh.commands))
            else:self.assertFalse(any('sbatch ' in x for x in ssh.commands))

    def test_cloudv_pipeline(self):self.run_fake('Cloud-V')
    def test_epcc_pipeline(self):self.run_fake('EPCC')

    def test_newest_test_first(self):
        items,errors=runner.discover(ROOT/'studio'/'test_scripts')
        self.assertEqual(errors,[])
        self.assertEqual(items[0]['id'],'machine-compare-94-1h')
        self.assertEqual(items[1]['script_path'].stem[:2],'93')

    def test_cloudv_sftp_eof_resume(self):
        import os
        import types
        import io
        from rvvlab_backend import StudioSSH
        with tempfile.TemporaryDirectory() as d:
            home=Path(d)
            src=home/'local.bin';src.write_bytes(os.urandom(656000))
            remote=home/'remote'
            logs=[];calls={'n':0}
            class RemoteFile:
                def __init__(self,f,fail):self.f=f;self.fail=fail;self.writes=0
                def __enter__(self):return self
                def __exit__(self,*args):self.f.close()
                def set_pipelined(self,val):pass
                def seek(self,offset):self.f.seek(offset)
                def write(self,blob):
                    if self.fail and self.writes==3:raise EOFError('fake SFTP EOF mid-upload')
                    self.writes+=1;return self.f.write(blob)
            class FSFTP:
                def __init__(self):calls['n']+=1;self.fail=calls['n']==1
                def get_channel(self):return SimpleNamespace(settimeout=lambda _n:None)
                def stat(self,p):return Path(p).stat()
                def open(self,p,mode,bufsize=0):return RemoteFile(open(p,mode),self.fail)
                def remove(self,p):Path(p).unlink()
                def close(self):pass
            ssh=StudioSSH()
            ssh.client=SimpleNamespace(open_sftp=FSFTP)
            ssh.home=str(remote)
            ssh.connected=lambda:True
            ssh.mkdir=lambda folder:Path(folder).mkdir(parents=True,exist_ok=True)
            ssh.exec_stream=lambda cmd,callback,stop= None:0
            want=hashlib.sha256(src.read_bytes()).hexdigest()
            target=ssh.deploy(src,{'zip_sha256':want},'20261013T180000Z-123456','rvvlab-v5',logs.append)
            result=remote/'rvvlab-v5'/'incoming'/'20261013T180000Z-123456.zip'
            # Upload verified and incoming temporary archive removed by normal cleanup.
            self.assertEqual(target,str(remote/'rvvlab-v5'/'sources'/'20261013T180000Z-123456'))
            self.assertGreaterEqual(calls['n'],2)
            self.assertTrue(any('resume' in line for line in logs))

    def test_epcc_gateway_key_plus_totp(self):
        import base64,hashlib,socket
        from unittest.mock import patch
        from rvvlab_backend import StudioSSH
        key_bytes=b'MOCK-EPCC-SERVER-KEY'
        fp='SHA256:'+base64.b64encode(hashlib.sha256(key_bytes).digest()).decode().rstrip('=')
        class T:
            def __init__(self,sock):self.ok=False;self.last=[]
            def start_client(self,timeout=25):pass
            def get_remote_server_key(self):return SimpleNamespace(asbytes=lambda:key_bytes)
            def auth_publickey(self,user,pkey):return ['keyboard-interactive']
            def is_authenticated(self):return self.ok
            def auth_interactive(self,user,handler):
                self.last=handler('MFA','','TOTP code:',False) if False else handler('MFA','',[('TOTP code:',False)])
                self.ok=self.last==['123456']
            def set_keepalive(self,n):pass
            def close(self):pass
        class Key:
            @staticmethod
            def from_private_key_file(path,password=None):return 'PKEY'
        class Client:
            def __init__(self):self._transport=None
        fake=SimpleNamespace(Transport=T,Ed25519Key=Key,SSHClient=Client)
        entry={'host':'gateway.epcc.ed.ac.uk','port':22,'user':'gustave',
               'host_fingerprint':fp,'key':'/fake/epcc','key_passphrase':'fake', 'totp_code':'123456'}
        with patch.dict(sys.modules,{'paramiko':fake}),patch.object(socket,'create_connection',return_value=object()):
            client,key=StudioSSH._epcc_gateway_connect(entry,{'unverified_epcc_test_mode':False})
            self.assertTrue(client._transport.is_authenticated())
            self.assertEqual(key,'PKEY')
            with self.assertRaisesRegex(RuntimeError,'host key mismatch'):
                StudioSSH._epcc_gateway_connect({**entry,'host_fingerprint':'SHA256:'+'A'*43},
                                                {'unverified_epcc_test_mode':False})

if __name__=='__main__':unittest.main(verbosity=2)
