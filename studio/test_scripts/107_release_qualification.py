#!/usr/bin/env python3
"""Trusted local Test107 release evidence audit (never schedules a remote benchmark).

May be invoked from Test Runner without SSH; the primary Tests tab also
exposes Test107 as a fully local audit. No remote request is performed.
"""
from __future__ import annotations
import importlib.util, pathlib

def _choose(results_root,profile,explicit):
    if explicit:return pathlib.Path(explicit).expanduser()
    base=pathlib.Path(results_root).expanduser()/'TestRunner'/'test106-vectorpath-release-validation'
    choices=[]
    if base.is_dir():
        for x in base.rglob('test106_results.zip'):
            parts=[p.name.lower() for p in x.parents]
            if profile=='Cloud-V' and not any('cloud-v' in n or 'cloudv' in n for n in parts):continue
            if profile=='EPCC' and not any('epcc' in n for n in parts):continue
            if x.is_file() and x.stat().st_size>0:choices.append(x)
    if not choices:
        raise RuntimeError('Test107 requires a locally downloaded Test106 '+profile+' ZIP. '
         'Use Tests > 106 > Download on both machines first, or set the archive path in the Test107 manifest.')
    return max(choices,key=lambda p:p.stat().st_mtime)

def execute(ctx,params):
    root=pathlib.Path(__file__).resolve().parents[2]
    tool=root/'tools'/'test107_release_audit.py'
    if not tool.is_file():raise RuntimeError('Test107 audit engine missing: '+str(tool))
    spec=importlib.util.spec_from_file_location('test107_release_audit_local',str(tool))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    cv=_choose(ctx.results_root,'Cloud-V',str(params.get('cloudv_archive','')).strip())
    ep=_choose(ctx.results_root,'EPCC',str(params.get('epcc_archive','')).strip())
    dist=str(params.get('vectorpath_archive','')).strip() or None
    ci=str(params.get('ci_run_json','')).strip() or None
    ctx.log('Test107 LOCAL evidence only; NO remote compilation or benchmark')
    ctx.log('Cloud-V Test106: '+str(cv))
    ctx.log('EPCC Test106: '+str(ep))
    if not dist:ctx.log('VectorPath distribution ZIP absent from manifest; artifact sign-off stays pending')
    result=mod.audit_pair(cv,ep,dist,ci)
    (ctx.output_dir/'TEST107_RELEASE_AUDIT.md').write_text(mod.report(result),encoding='utf8')
    import json,zipfile
    (ctx.output_dir/'TEST107_RELEASE_AUDIT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf8')
    with zipfile.ZipFile(ctx.output_dir/'test107_release_audit.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
        for filename in ('TEST107_RELEASE_AUDIT.md','TEST107_RELEASE_AUDIT.json'):
            z.write(ctx.output_dir/filename,arcname=filename)
    ctx.log('ENGINE: '+result['engine_qualification']+'; SHIP: '+result['ship_authorization'])
    ctx.log('Report: '+str(ctx.output_dir/'TEST107_RELEASE_AUDIT.md'))
    return {'state':'completed','engine_qualification':result['engine_qualification'],
            'ship_authorization':result['ship_authorization'],
            'report':str(ctx.output_dir/'TEST107_RELEASE_AUDIT.md'),
            'archive':str(ctx.output_dir/'test107_release_audit.zip')}
