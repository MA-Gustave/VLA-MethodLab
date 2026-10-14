"""Regression test for deliberate EPCC-only temporary no-host-key-check mode."""
import sys,types,tempfile
from pathlib import Path
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'studio'))
from rvvlab_backend import parse_env,StudioSSH

def read(text):
 with tempfile.TemporaryDirectory() as d:
  p=Path(d)/'.env.epcc';p.write_text(text,encoding='utf-8')
  return parse_env(p)
base='RVVLAB_HOST=riscv-login.epcc.ed.ac.uk\nRVVLAB_USER=gustave\nRVVLAB_JUMP_HOST=gateway.epcc.ed.ac.uk\nRVVLAB_JUMP_USER=gustave\nRVVLAB_JUMP_ALLOW_AGENT=1\n'
valid=base+'RVVLAB_INSECURE_EPCC_TEST_MODE=1\n'
cfg=read(valid)
assert cfg['unverified_epcc_test_mode'] and cfg['jump']['host_fingerprint']=='' and cfg['host_fingerprint']==''
for invalid in [base,valid.replace('riscv-login.epcc.ed.ac.uk','machine2.cloud-v.co'),valid.replace('gateway.epcc.ed.ac.uk','evil.example.org'),valid.replace('MODE=1','MODE=on')]:
 try:read(invalid)
 except ValueError:pass
 else:raise AssertionError('Invalid/insecure configuration was accepted')
class Transport:
 def __init__(self):self.closed=False
 def is_active(self):return not self.closed
 def set_keepalive(self,n):pass
 def open_channel(self,*a,**kw):return types.SimpleNamespace(close=lambda:None)
class Client:
 instances=[]
 def __init__(self):self.policy=None;self.transport=Transport();self.__class__.instances.append(self)
 def set_missing_host_key_policy(self,p):self.policy=p
 def connect(self,**kw):pass
 def get_transport(self):return self.transport
 def open_sftp(self):return types.SimpleNamespace(normalize=lambda p:'/home/gustave',close=lambda:None)
 def close(self):self.transport.closed=True
class AutoAddPolicy:pass
with patch.dict(sys.modules,{'paramiko':types.SimpleNamespace(SSHClient=Client,AutoAddPolicy=AutoAddPolicy)}):
 s=StudioSSH();s.connect(cfg)
 assert s.connected()
 assert len(Client.instances)==2
 assert all(isinstance(c.policy,AutoAddPolicy) for c in Client.instances)
 s.close()
assert (root/'studio/rvvlab_backend.py').read_bytes()==(root/'orchestrator/rvvlab_backend.py').read_bytes()
print('PASS: EPCC temporary flag, no pinned keys for test, strict host restriction, normal-mode strict validation, simulated gateway+target, mirrored backends')
