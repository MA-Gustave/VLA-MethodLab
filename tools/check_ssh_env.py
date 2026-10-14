#!/usr/bin/env python3
"""Check external .env discovery and shape, without exposing secrets or connecting."""
from pathlib import Path
import sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'orchestrator'))
from rvvlab_backend import discover_env_file, parse_env
p=discover_env_file(root)
print('Config file:',p)
if not p.is_file():
    print('MISSING: configure an external .env or run setup.')
    raise SystemExit(2)
try:
    obj=parse_env(p)
except (OSError, ValueError) as exc:
    # The parser's messages do not print credentials or key material.
    print('INVALID:',exc)
    raise SystemExit(1)
print('VALID: SSH variables recognized; pinned host key present.')
print('SSH authentication method:', 'key' if obj['key'] else 'password' if obj['password'] else 'prompt at Connect')
print('No network connection was attempted.')
