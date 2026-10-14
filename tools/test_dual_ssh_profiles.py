#!/usr/bin/env python3
"""Offline dual-target/ProxyJump regression checks; never open a real SSH socket."""
from pathlib import Path
import hashlib
import importlib.util
import sys
import tempfile
import types
from unittest.mock import patch
ROOT=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_backend import parse_env,StudioSSH,PinnedHostKey

H1='SHA256:'+'A'*43
H2='SHA256:'+'B'*43

def config(root,extra=''):
    file=root/'.env.epcc'
    (root/'mock-key').write_text('not-a-real-private-key')
    file.write_text('RVVLAB_HOST=vm.internal\nRVVLAB_USER=internaluser\n'
                    'RVVLAB_HOST_SHA256='+H1+'\nRVVLAB_JUMP_HOST=gateway.epcc.ed.ac.uk\n'
                    'RVVLAB_JUMP_USER=gustave\nRVVLAB_JUMP_HOST_SHA256='+H2+'\n'
                    'RVVLAB_JUMP_ALLOW_AGENT=1\nRVVLAB_SSH_KEY='+str(root/'mock-key')+'\n'+extra)
    return file

class Transport:
    def __init__(self):self.active=True;self.keep=[];self.calls=[];self.channel=types.SimpleNamespace(close=lambda:None)
    def is_active(self):return self.active
    def set_keepalive(self,n):self.keep.append(n)
    def open_channel(self,kind,dest,origin,timeout=None):
        self.calls.append((kind,dest,origin,timeout));return self.channel
class SFTP:
    def normalize(self, _):return '/home/users/internaluser'
    def close(self):pass
class Client:
    created=[]
    def __init__(self):self.transport=Transport();self.opts=None;self.closed=False;self.policy=None;self.__class__.created.append(self)
    def set_missing_host_key_policy(self,p):self.policy=p
    def connect(self,**kw):self.opts=kw
    def get_transport(self):return self.transport
    def open_sftp(self):return SFTP()
    def close(self):self.closed=True;self.transport.active=False

with tempfile.TemporaryDirectory() as tmp:
    path=config(Path(tmp))
    cfg=parse_env(path)
    assert cfg['jump']['user']=='gustave'
    assert cfg['jump']['host']=='gateway.epcc.ed.ac.uk'
    assert cfg['jump']['allow_agent'] is True
    assert cfg['host']=='vm.internal' and cfg['user']=='internaluser'
    assert cfg['host_fingerprint']==H1 and cfg['jump']['host_fingerprint']==H2
    assert cfg['jump']['key']==''
    Client.created=[]
    with patch.dict(sys.modules,{'paramiko':types.SimpleNamespace(SSHClient=Client)}):
        c=StudioSSH();c.connect(cfg)
        assert c.connected()
        t,g=Client.created
        assert g.opts['hostname']=='gateway.epcc.ed.ac.uk' and g.opts['username']=='gustave'
        assert g.opts['allow_agent'] is True and g.opts['look_for_keys'] is False
        assert g.transport.calls==[('direct-tcpip',('vm.internal',22),('127.0.0.1',0),20)]
        assert t.opts['hostname']=='vm.internal' and t.opts['username']=='internaluser'
        assert t.opts['sock'] is g.transport.channel
        assert g.policy.expected==H2 and t.policy.expected==H1
        assert c.home=='/home/users/internaluser'
        c.close();assert g.closed and t.closed
        # Direct RISC-V legacy host continues without gateway.
        cfg2=dict(cfg);cfg2.pop('jump')
        Client.created=[]
        d=StudioSSH();d.connect(cfg2)
        assert len(Client.created)==1 and 'sock' not in Client.created[0].opts
        d.close()
    # No half-configured gateway, no unverified host keys.
    path=config(Path(tmp), 'RVVLAB_JUMP_HOST_SHA256=unverified\n')
    try:parse_env(path)
    except ValueError:pass
    else:raise AssertionError('Unpinned gateway was accepted')
    path=config(Path(tmp), 'RVVLAB_HOST_SHA256=unverified\n')
    try:parse_env(path)
    except ValueError:pass
    else:raise AssertionError('Unpinned internal VM was accepted')
    path=config(Path(tmp), 'RVVLAB_JUMP_HOST=\n')
    try:parse_env(path)
    except ValueError:pass
    else:raise AssertionError('Partial gateway settings were accepted')
    # The Studio backend intentionally uses per-target GUI settings files;
    # the CLI orchestrator retains its historical settings.json. Apart from
    # this explicit settings policy, the SSH/SFTP implementations must match.
    studio_backend=(ROOT/'studio/rvvlab_backend.py').read_text(encoding='utf8')
    cli_backend=(ROOT/'orchestrator/rvvlab_backend.py').read_text(encoding='utf8')
    assert 'settings_cloudv.json' in studio_backend and 'settings_epcc.json' in studio_backend
    assert "SETTINGS_PATH=CONFIG_DIR/'settings.json'" in cli_backend
    normalized=lambda source:'\n'.join('SETTINGS_PATH=<profile-specific GUI settings>' if line.startswith('SETTINGS_PATH=') else line
                                     for line in source.splitlines())
    assert normalized(studio_backend)==normalized(cli_backend)
    # Simulate a spoofed server key: verify fingerprint policy aborts.
    key=types.SimpleNamespace(asbytes=lambda:b'imposter')
    try:PinnedHostKey(H1).missing_host_key(None,'vm.internal',key)
    except RuntimeError as e:assert 'MISMATCH' in str(e)
    else:raise AssertionError('Wrong key accepted')
print('PASS: direct SSH, pinned gateway+VM ProxyJump, agent, tunnel lifecycle, refusals, backend parity. No real EPCC access attempted.')
