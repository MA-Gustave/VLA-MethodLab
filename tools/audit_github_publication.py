#!/usr/bin/env python3
"""Read-only prepublication checks for the two new GitHub repos.

No GitHub writes, git init, git add, SSH, or file modifications. Prints paths
only (never secret values). Inspect full staged commits manually before push.
"""
from __future__ import annotations
import argparse
import fnmatch
from pathlib import Path
import re
import sys

PRIVATE_NAMES=('.env','.env.*','id_ed25519*','id_rsa*','*.pem','*.ppk','*.pfx','*.p12','*.p8','*.key','*.kdbx')
SKIP_DIR={'.git','.venv','venv','__pycache__','.pytest_cache','.mypy_cache'}
PRIVATE_TEXT=re.compile(r'(?im)^(?:\s*(?:RVVLAB|CLOUDV|EPCC)_[A-Z0-9_]*(?:PASSWORD|PASSPHRASE|TOKEN|SECRET|PRIVATE_KEY)\s*=\s*[^#\s].*)|-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----')

def audit(root:Path):
    issues=[];notes=[]
    if not root.is_dir():return ['Source directory missing'],[]
    expected=[root/'engine/LICENSE',root/'engine/LICENSE-MIT',root/'engine/include',root/'studio/RVV_Lab_Studio.pyw']
    for p in expected:
        if not p.exists():issues.append('Missing required engine/Studio component: '+str(p.relative_to(root)))
    for path in root.rglob('*'):
        if not path.is_file() or path.is_symlink():continue
        rel=path.relative_to(root)
        if any(part in SKIP_DIR for part in rel.parts):continue
        is_example=path.name.lower().endswith('.env.example')
        if not is_example and any(fnmatch.fnmatch(path.name.lower(),x) for x in PRIVATE_NAMES):
            issues.append('Credential-like file name: '+rel.as_posix());continue
        if path.stat().st_size>40*1024*1024:
            notes.append('Large file; check Git/LFS and content: '+rel.as_posix())
        if path.suffix.lower() in ('.md','.txt','.json','.toml','.cfg','.ini','.yaml','.yml','.example','.py','.pyw','.ps1','.bat','.sh'):
            if path.stat().st_size>5*1024*1024:continue
            try:s=path.read_text(encoding='utf-8',errors='replace')
            except OSError:continue
            if PRIVATE_TEXT.search(s):
                # Test fixtures may dynamically construct fake passwords, but
                # should still be inspected before publication.
                destination=notes if path.name.startswith('test_') else issues
                destination.append('Sensitive-looking assignment/content: '+rel.as_posix())
    if not (root/'README-GITHUB-2026.md').is_file():notes.append('GitHub publication instructions not installed')
    if not (root/'REPOSITORY_SPLIT.md').is_file():notes.append('Repository split guide missing')
    return issues,notes

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    a=parser.parse_args()
    problems,notes=audit(a.root.resolve())
    print('READ-ONLY GitHub publication audit (no files uploaded):')
    for msg in problems:print('BLOCK:',msg)
    for msg in notes:print('REVIEW:',msg)
    print(f'{len(problems)} finding(s), {len(notes)} note(s).')
    if problems:print('Review manually before staging or pushing to public GitHub.')
    else:print('No obvious credential names/assignments detected; manual review still required.')
    sys.exit(1 if problems else 0)
