#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
    python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import paramiko' 2>/dev/null; then
    printf 'Install Paramiko in local .venv? [Y/n] '
    read answer
    case "$answer" in n|N|no|NO) exit 2;; esac
    .venv/bin/python -m pip install -r orchestrator/requirements.txt
fi
exec .venv/bin/python tools/rvvlab.py wizard
