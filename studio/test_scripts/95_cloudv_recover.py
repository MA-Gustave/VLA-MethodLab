#!/usr/bin/env python3
"""Recover latest Test95 launch from the same Studio TestRunner results directory."""
from __future__ import annotations
import importlib.util, json
from pathlib import Path

def execute(ctx,params):
    root=ctx.output_dir.parent.parent
    candidates=sorted(root.glob('test95-cloudv-8h/*/launch95.json'),reverse=True)
    if not candidates:raise RuntimeError('No previous Test95 launch in current Studio result directory')
    import_path=Path(__file__).with_name('95_cloudv_8h.py')
    spec=importlib.util.spec_from_file_location('test95_launcher_recovery',import_path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    for candidate in candidates:
        try:
            launch=json.loads(candidate.read_text(encoding='utf8'))
            outcome=module.recover(ctx,launch)
            (ctx.output_dir/'recovered_from.txt').write_text(str(candidate)+'\n',encoding='utf8')
            return outcome
        except (OSError,ValueError):continue
    raise RuntimeError('No recoverable Test95 run found')
