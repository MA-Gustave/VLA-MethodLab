#!/usr/bin/env python3
"""Regenerate source-tree SHA256 manifests for a self-contained Lab tree.

Dry-run by default. --write updates only SHA256SUMS.txt,
OVERLAY_SHA256SUMS.txt, and SNAPSHOT_INDEX.txt in the Lab root. Does not read,
add, commit, push or modify Git data. Refuses unexpected credential files.
"""
from __future__ import annotations
import argparse
import fnmatch
import hashlib
from pathlib import Path
import sys

SKIP_PARTS={'.git','.venv','venv','__pycache__','.pytest_cache','.cache','.idea','.vscode'}
EXCLUDE_NAMES={'SHA256SUMS.txt','OVERLAY_SHA256SUMS.txt','SNAPSHOT_INDEX.txt'}
SECRET_GLOBS={'.env','.env.*','id_ed25519*','id_rsa*','*.pem','*.key','*.pfx','*.ppk','*.p12'}


def inventory(root:Path):
    paths=[];suspects=[]
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root)
        if any(part in SKIP_PARTS for part in rel.parts):continue
        if path.name in EXCLUDE_NAMES or path.name.endswith('.pyc'):continue
        name=path.name.lower()
        if name.endswith('.env.example'):paths.append(path);continue
        if any(fnmatch.fnmatch(name,pattern) for pattern in SECRET_GLOBS):
            suspects.append(rel.as_posix());continue
        paths.append(path)
    return sorted(paths,key=lambda p:p.relative_to(root).as_posix()),suspects


def prepare(root:Path):
    paths,credentials=inventory(root)
    if credentials:raise ValueError('Refusing to prepare public hashes while credential-like files are present: '+', '.join(credentials[:15]))
    index=('RVV-VLA Lab — GitHub MethodLab self-contained tree\n'
            'Files indexed (excluding SHA256 manifests and this file): '+str(len(paths))+'\n\n'
           +'\n'.join(p.relative_to(root).as_posix() for p in paths)+'\n')
    index_hash=hashlib.sha256(index.encode('utf-8')).hexdigest()
    hashes=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in paths)
    hashes+=index_hash+'  SNAPSHOT_INDEX.txt\n'
    return paths,index,hashes


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--write',action='store_true')
    args=parser.parse_args()
    root=args.root.resolve()
    if not (root/'engine/include').is_dir():
        parser.error('engine/ is missing. Extract the complete VLA-MethodLab ZIP first.')
    paths,index,hashes=prepare(root)
    print('Manifest candidate:',len(paths),'source files including engine/')
    if not args.write:
        print('DRY RUN — no files changed. Use --write after publication review.')
        return 0
    for name,content in [('SNAPSHOT_INDEX.txt',index),('SHA256SUMS.txt',hashes),('OVERLAY_SHA256SUMS.txt',hashes)]:
        (root/name).write_text(content,encoding='utf-8')
        print('Updated',name)
    return 0


if __name__=='__main__':sys.exit(main())
