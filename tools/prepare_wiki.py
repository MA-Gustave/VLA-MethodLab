#!/usr/bin/env python3
"""Publish helper: prepare self-contained GitHub Wiki sources with repo evidence URLs."""
from pathlib import Path
import argparse,re
p=argparse.ArgumentParser()
p.add_argument('--repo-url',required=True,help='e.g. https://github.com/ORG/REPO')
a=p.parse_args()
if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',a.repo_url):
 p.error('Expected https://github.com/OWNER/REPO')
r=Path(__file__).resolve().parents[1];target=r/'wiki-publish';target.mkdir(exist_ok=True)
for source in (r/'wiki').glob('*.md'):
 txt=source.read_text('utf8')
 txt=txt.replace('../results/runs/',a.repo_url+'/blob/main/results/runs/')
 (target/source.name).write_text(txt,encoding='utf8')
print('READY: publish files from',target,'in the GitHub Wiki for',a.repo_url)
