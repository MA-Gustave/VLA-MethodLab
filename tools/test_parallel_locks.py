#!/usr/bin/env python3
"""Offline cross-process two-target instance guard."""
import os,subprocess,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'studio'))
from rvvlab_parallel import MachineLock
with tempfile.TemporaryDirectory() as home:
    old=Path.home
    # Replace Path.home only for process-local config; subprocess gets HOME.
    Path.home=classmethod(lambda cls:Path(home))
    try:
        a=MachineLock();b=MachineLock();c=MachineLock()
        assert a.acquire('Cloud-V')
        assert not b.acquire('Cloud-V')
        assert c.acquire('EPCC')
        cmd=[sys.executable,'-c',
             'from rvvlab_parallel import MachineLock; l=MachineLock(); print(l.acquire("Cloud-V")); l.release()']
        env=os.environ.copy();env['HOME']=home;env['USERPROFILE']=home
        env['PYTHONPATH']=str(ROOT/'studio')+os.pathsep+env.get('PYTHONPATH','')
        assert subprocess.check_output(cmd,env=env,text=True).strip()=='False'
        c.release();a.release()
        assert b.acquire('Cloud-V')
        b.release()
        print('PASS: same-target second instance blocked; other target allowed; release after exit')
    finally:Path.home=old
