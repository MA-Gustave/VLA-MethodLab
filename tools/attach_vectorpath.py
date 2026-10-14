#!/usr/bin/env python3
"""Attach a separately cloned VectorPath RVV source tree to VLA MethodLab.

No network access or shell invocation. Refuses to overwrite an existing engine.
Uses a copy (not a symlink) to be portable and independent of local Git settings.
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'engine'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT.parent/'vectorpath-rvv',help='Path to extracted/cloned VectorPath RVV repository')
    args=parser.parse_args()
    source=args.source.expanduser().resolve()
    if source==ROOT.resolve() or DEST.resolve()==source:
        parser.error('source must be a separate VectorPath source directory')
    required=['CMakeLists.txt','LICENSE','LICENSE-MIT','src/rvv/stage1.h','include/simdjson.h']
    missing=[n for n in required if not (source/n).is_file()]
    if missing:parser.error('invalid VectorPath source; missing: '+', '.join(missing))
    if DEST.exists() or DEST.is_symlink():
        parser.error(f'{DEST} exists; refusing to overwrite. Rename/remove it manually only after backup.')
    # Never take local Git internals, secret .env files, caches, or symlinks.
    def excluded(directory,names):
        excluded_names={'.git','.hg','.svn','.venv','venv','__pycache__','build','dist','.env','.ssh','.aws','.kube'}
        return [n for n in names if n in excluded_names or n.startswith('.env.') or (Path(directory)/n).is_symlink()]
    try:
        shutil.copytree(source,DEST,ignore=excluded,symlinks=False)
        h=hashlib.sha256((DEST/'src/rvv/stage1.h').read_bytes()).hexdigest()
        provenance={'source_path':str(source),'stage1_sha256':h,'component':'VectorPath RVV','license_files':['LICENSE','LICENSE-MIT','LICENSE-SCOPE.md']}
        (ROOT/'ENGINE_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf8')
    except Exception:
        shutil.rmtree(DEST,ignore_errors=True)
        raise
    print(f'Attached VectorPath RVV to {DEST} (ignored by Git).')
    print('Run: python tools/verify_release.py')

if __name__=='__main__':main()
