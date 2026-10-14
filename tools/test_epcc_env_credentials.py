#!/usr/bin/env python3
"""EPCC .env credential fields: parsed, passed to Studio, no prompting except MFA.

This offline test never connects to a machine, reads a private key, or writes a secret.
"""
from __future__ import annotations
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_backend import parse_env
spec=importlib.util.spec_from_loader('studio_env_test',SourceFileLoader('studio_env_test',str(ROOT/'studio'/'RVV_Lab_Studio.pyw')))
app=importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)

class Value:
    def __init__(self,val):self.val=val
    def get(self):return self.val
    def set(self,v):self.val=v

class ThreadFake:
    started=[]
    def __init__(self, target=None,args=(),daemon=True):self.target,self.args=target,args
    def start(self):self.started.append(self)

def exercise(passphrase, password, expect_prompts):
    with tempfile.TemporaryDirectory() as d:
        f=Path(d)/'.env.epcc'
        f.write_text('''RVVLAB_HOST=riscv-login.epcc.ed.ac.uk
RVVLAB_USER=gustave
RVVLAB_HOST_SHA256=SHA256:'''+'A'*43+'''
RVVLAB_JUMP_HOST=gateway.epcc.ed.ac.uk
RVVLAB_JUMP_USER=gustave
RVVLAB_JUMP_HOST_SHA256=SHA256:'''+'B'*43+'''
RVVLAB_JUMP_KEY=//fake/key
RVVLAB_JUMP_KEY_PASSPHRASE='''+passphrase+'''
RVVLAB_PASSWORD='''+password+'''
''',encoding='utf-8')
        parsed=parse_env(f)
        assert parsed['jump']['key_passphrase']==passphrase
        assert parsed['password']==password
        prompt=[]
        def ask(title,*args,**kwargs):
            prompt.append(title)
            return '876543' if title=='EPCC MFA' else 'prompt-keyphrase'
        class PasswordRequiredException(Exception):pass
        class SSHException(Exception):pass
        def load_key(path,password=None):
            if not password:
                raise PasswordRequiredException('needs unlock')
            return 'pkey-object'
        import types
        fake_paramiko=types.ModuleType('paramiko')
        fake_paramiko.PasswordRequiredException=PasswordRequiredException
        fake_paramiko.SSHException=SSHException
        fake_paramiko.Ed25519Key=SimpleNamespace(from_private_key_file=load_key)
        status=Value('')
        fake=SimpleNamespace(
           vars={'env_path':Value(str(f))}, machine_choice=Value('EPCC'),
           active_profile='EPCC', connecting=False, ssh=SimpleNamespace(connected=lambda:False),
           status=status, root=None, connect_btn=SimpleNamespace(configure=lambda **kwargs:None),
           _save_settings=lambda:None, _connect_worker=lambda cfg:None)
        ThreadFake.started=[]
        with patch.object(app.simpledialog,'askstring',side_effect=ask), \
             patch.object(app.threading,'Thread',ThreadFake), \
             patch.dict(sys.modules,{'paramiko':fake_paramiko}):
            app.Studio.connect(fake)
        assert prompt==expect_prompts,(prompt,expect_prompts)
        assert len(ThreadFake.started)==1
        cfg=ThreadFake.started[0].args[0]
        assert cfg['password']==password
        assert cfg['jump']['key_passphrase']==(passphrase or 'prompt-keyphrase')
        assert cfg['jump']['totp_code']=='876543'

exercise('dummy-key-secret','dummy-internal-secret',['EPCC MFA'])
exercise('','dummy-internal-secret',['EPCC private key','EPCC MFA'])
print('PASS: .env passphrase + internal password are reused without prompts; blank key passphrase prompts; MFA still requested')
