"""One Studio process per dedicated target. Locks released by OS on crash."""
import os,sys
from pathlib import Path
TARGET=os.environ.get('RVVLAB_STUDIO_TARGET','')
if TARGET not in ('','Cloud-V','EPCC'):raise ValueError('Unknown fixed machine')

class MachineLock:
    def __init__(self):self.handle=None;self.machine=None
    def acquire(self,machine):
        if machine not in ('Cloud-V','EPCC'):raise ValueError('Unknown machine')
        directory=Path.home()/'.rvvlab_lab_v3';directory.mkdir(parents=True,exist_ok=True)
        f=(directory/('lock-cloudv.dat' if machine=='Cloud-V' else 'lock-epcc.dat')).open('a+b',buffering=0)
        try:
            if sys.platform=='win32':
                import msvcrt
                f.seek(0);f.write(b'0');f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            f.close();return False
        self.handle=f;self.machine=machine
        return True
    def release(self):
        if self.handle is None:return
        try:
            if sys.platform=='win32':
                import msvcrt
                self.handle.seek(0);msvcrt.locking(self.handle.fileno(),msvcrt.LK_UNLCK,1)
            else:
                import fcntl
                fcntl.flock(self.handle.fileno(),fcntl.LOCK_UN)
        finally:self.handle.close();self.handle=None
