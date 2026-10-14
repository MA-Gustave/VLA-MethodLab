#!/usr/bin/env python3
"""Thin SHA256-pinned launcher. All research support travels in the source snapshot."""
from pathlib import Path
import argparse,sys

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--workdir',required=True)
    p.add_argument('--hours',type=float,default=3);p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--core',type=int,default=0);p.add_argument('--max-mib',type=int,default=8)
    a=p.parse_args()
    if not 0<a.hours<=3 or a.jobs not in (1,2) or a.core<0 or a.max_mib not in (1,8,64):p.error('Invalid budget/jobs/core/max-mib')
    root=Path(a.source).resolve()/'scripts/rvv/explore91'
    if not (root/'campaign93.py').is_file():p.error('Test93 source snapshot missing')
    sys.path.insert(0,str(root))
    from campaign93 import Campaign
    c=Campaign(a.source,a.workdir,a.hours,a.jobs,a.core,a.max_mib)
    c.execute()
    print(c.status)
    return 0 if c.status['state'] in ('completed','stopped') and c.rows else 1
if __name__=='__main__':raise SystemExit(main())
