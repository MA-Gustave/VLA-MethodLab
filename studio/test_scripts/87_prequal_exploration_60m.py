#!/usr/bin/env python3
"""RVV-VLA Lab Studio Test Runner: 60-minute Adaptive Dispatch v2 native stage profile.

Creates a NEW source snapshot from Studio's currently selected v5 checkout.
Deploys with SHA256; launches an 60-minute remote worker, checks every 60 seconds;
downloads verified results at terminal state. Never autostarts itself.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from pathlib import Path
import secrets
import shlex
import tempfile
import time
import zipfile

TERMINAL = {'completed', 'stopped', 'failed', 'safety_stop'}
UPSTREAM_REFERENCE_SHA = 'bf89ddd00ef5fcb6a7f20611ea8853d258b67249'


def _integrated_repo(repo: Path) -> None:
    if not repo.is_dir():
        raise RuntimeError('Local repository missing: '+str(repo))
    needed = (
       'CMakeLists.txt', 'scripts/rvv/server_control.py',
       'scripts/rvv/perf/bench_native.py',
       'include/simdjson/simdjson_version.h',
       'src/rvv.cpp','src/rvv/stage1.h',
       'src/rvv/engines/engine_plan.h',
       'src/rvv/engines/workload_profile.h',
       'src/rvv/engines/structural_writers.h',
       'src/rvv/engines/stage2_bridge.h',
       'scripts/rvv/engines/engine_probe.cpp',
       'scripts/rvv/engines/experiments.json',
       'include/simdjson/builtin.h',
       'include/simdjson/builtin/builder.h',
       'include/simdjson/builtin/ondemand.h',
    )
    missing=[name for name in needed if not (repo/name).is_file()]
    if missing:
        raise RuntimeError('Selected repository missing Engine Library / v5 routing files: '+', '.join(missing))
    version=(repo/'include/simdjson/simdjson_version.h').read_text(encoding='utf8')
    import re
    if not re.search(r'^#define SIMDJSON_VERSION\s+"5\.0\.3"',version,re.M):
        raise RuntimeError('Select the simdjson v5.0.3 checkout, not an older tree')
    if 'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL' not in (repo/'src/rvv/engines/engine_plan.h').read_text(encoding='utf8'):
        raise RuntimeError('Adaptive Dispatch v2 not installed in selected source')
    if 'rvv/engines/engine_plan.h' not in (repo/'src/rvv/stage1.h').read_text(encoding='utf8'):
        raise RuntimeError('Stage 1 not integrated with the new Engine Library')
    for name in ('include/simdjson/builtin.h','include/simdjson/builtin/builder.h',
                 'include/simdjson/builtin/ondemand.h'):
        if 'SIMDJSON_BUILTIN_IMPLEMENTATION_IS(rvv)' not in (repo/name).read_text(encoding='utf8'):
            raise RuntimeError('Missing v5 builtin fix: '+name)


def execute(ctx, params):
    ctx.ensure_connected()
    if ctx.stop_event.is_set(): raise RuntimeError('Studio local monitoring already stopped')
    if params.get('hours') != 1.0 or params.get('jobs') != 2 or params.get('core') != 0:
        raise ValueError('60-minute approved manifest parameters have changed')
    script_dir=Path(ctx.manifest['script_path']).parent
    worker=script_dir/'87_prequal_exploration_60m_worker.py'
    if not worker.is_file(): raise FileNotFoundError('Worker absent: '+str(worker))
    worker_sha=hashlib.sha256(worker.read_bytes()).hexdigest()
    if worker_sha != params.get('worker_sha256'):
        raise RuntimeError('Worker SHA256 differs from the approved manifest: refuse launch')
    # Explicit Studio selected path, not previous RISC-V v5 snapshot.
    repo=Path(ctx.studio.vars['repo'].get()).expanduser().resolve()
    if (repo/'engine/src/rvv/engines/engine_plan.h').is_file():
        repo=repo/'engine'
    elif not (repo/'src/rvv/engines/engine_plan.h').is_file():
        bundled=Path(ctx.manifest['script_path']).resolve().parents[2]/'engine'
        if bundled.is_dir(): repo=bundled
    _integrated_repo(repo)
    from rvvlab_backend import build_source_zip
    from rvvlab_night import _launch_script, remote_runs, sync
    active=[obj['id'] for obj in remote_runs(ctx.ssh,ctx.remote_name)
            if obj.get('state') not in TERMINAL]
    if active: raise RuntimeError('Another v5 remote run may be active: '+', '.join(active))
    # Remote workers additionally take a global exclusive lock.
    free=ctx.ssh.available_kib()
    if free is None:
        ctx.log('WARNING: unknown remote disk space; the remote worker enforces the 200 MiB safety stop.')
    elif free < 200*1024:
        raise RuntimeError(f'Remote disk below 200 MiB safety floor: {free/1024:.1f} MiB free')
    elif free < 512*1024:
        ctx.log(f'WARNING: only {free/1024:.1f} MiB free; safe stop activates below 200 MiB.')

    source_id=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    ctx.log('Preparing NEW v5.0.3 source snapshot from '+str(repo))
    with tempfile.TemporaryDirectory(prefix='rvvlab-stage8h-') as tmp:
        archive=Path(tmp)/(source_id+'.zip')
        manifest=build_source_zip(repo,archive,ctx.log)
        local_names=set()
        with zipfile.ZipFile(archive) as z:
            local_names=set(z.namelist())
            need=['src/rvv/engines/engine_plan.h',
                  'src/rvv/engines/structural_writers.h',
                  'scripts/rvv/engines/experiments.json']
            if any(x not in local_names for x in need):
                raise RuntimeError('Local ZIP does not include Engine Library files; check gitignore')
        # Source snapshot SHA256, not a presumed Git parent, pins this experiment.
        ctx.log('SHA256 source: '+manifest['zip_sha256']+' ('+str(manifest['files'])+' files)')
        remote=ctx.ssh.deploy(archive,manifest,source_id,ctx.remote_name,ctx.log,ctx.stop_event)
    ctx.log('NEW REMOTE SOURCE: '+remote)
    base=ctx.ssh.base(ctx.remote_name)
    source=base+'/sources/'+source_id
    script=base+'/explorers/87_prequal_exploration_60m_worker.py'
    run_id=dt.datetime.now(dt.timezone.utc).strftime('night-%Y%m%dT%H%M%SZ-')+secrets.token_hex(3)
    workdir=base+'/night-runs/'+run_id
    ctx.ssh.mkdir(base+'/explorers')
    ctx.ssh.mkdir(base+'/night-runs')
    ctx.ssh.mkdir(workdir)
    if ctx.stop_event.is_set():
        raise RuntimeError('Cancelled after deployment; no night run launched')
    sftp=ctx.ssh.client.open_sftp()
    try:
        sftp.stat(source+'/scripts/rvv/engines/experiments.json')
        sftp.put(str(worker),script,confirm=True)
        check=ctx.ssh.exec_text('sha256sum '+shlex.quote(script)).strip().split()[0]
        if check!=worker_sha:raise RuntimeError('Remote worker SHA256 mismatch')
        with sftp.open(workdir+'/launcher.json','w') as f:
            f.write(json.dumps({'run_id':run_id,'source_id':source_id,
                 'source_sha256':manifest['zip_sha256'],'worker_sha256':worker_sha,
                 'campaign':'adaptive_prequal_exploratory_60m','manual_approval':True})+'\n')
        launch=_launch_script(ctx.ssh,script,
                 ['--source',source,'--workdir',workdir,'--hours','1.0',
                  '--jobs','2','--core','0'],workdir+'/runner-startup.log')
    finally:sftp.close()
    if 'NIGHT_PID=' not in launch:
        raise RuntimeError('Detached process not confirmed: '+launch)
    pid=int(launch.rsplit('NIGHT_PID=',1)[1].split()[0])
    launch_meta={'run_id':run_id,'pid':pid,'source_id':source_id,'source_sha256':manifest['zip_sha256'],
                 'worker_sha256':worker_sha,'workdir':workdir}
    (ctx.output_dir/'launch.json').write_text(json.dumps(launch_meta,indent=2)+'\n',encoding='utf8')
    ctx.log('60M START: '+run_id+' PID '+str(pid))
    ctx.log('Direct GCC -O3; 4 fixed plans; 174 heterogeneous prequalification scenarios; actual internal Stage1 / Stage2 and public DOM; 30m including builds.')
    ctx.log('JSON validation: 169 valid / 24 invalid. Predeclared 174 synthetic cases and rotated paired official VLS256 controls.')
    ctx.log('You may close Studio; remote run and checkpoints remain on RISC-V.')
    previous=None
    start=time.monotonic()
    while not ctx.stop_event.wait(60):
        matching=[x for x in remote_runs(ctx.ssh,ctx.remote_name) if x['id']==run_id]
        if not matching:raise RuntimeError('Remote run not visible: '+run_id)
        obj=matching[0]; state=obj.get('state')
        if state!=previous or state in TERMINAL:
            ctx.log(f"{run_id}: {state}; observations={obj.get('observations','?')}; current={obj.get('current_candidate','?')}")
            previous=state
        if state in TERMINAL:break
        if time.monotonic()-start > 60*60+900:
            ctx.log('Monitoring timed out; remote runner unaffected, sync manually later.')
            return {**launch_meta,'monitoring':'timeout'}
    else:
        ctx.log('Local monitoring stopped; detached remote run remains in progress.')
        return {**launch_meta,'monitoring':'local_stopped'}
    ctx.log('Downloading SHA256-verified results.')
    folder=sync(ctx.ssh,ctx.remote_name,run_id,ctx.results_root)
    status=json.loads((folder/'status.json').read_text(encoding='utf8'))
    archive=ctx.output_dir/'adaptive_prequal_exploratory_60m_packet.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in ('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md',
                     'failures.csv','metadata.json','corpus_manifest.json','trend_candidates.csv','TRENDS.md'):
            p=folder/name
            if p.is_file(): z.write(p,arcname=name)
        z.writestr('launch.json',json.dumps(launch_meta,indent=2))
    ctx.log(f"DATA READY: {status.get('observations',0)} observations; state={status.get('state')}; packet={archive}")
    ctx.log('DOM + true Stage1 / Stage2 wall times. No automatic winner; inspect TRENDS.md for hypotheses, then validate in a dedicated confirmatory run.')
    if status.get('state') == 'stopped' and not status.get('observations'):
        raise RuntimeError('60m campaign stopped with zero measurements; diagnostics: '+str(archive))
    if status.get('state') in ('failed', 'safety_stop'):
        raise RuntimeError('Remote 60m campaign '+str(status.get('state'))+': '+
                           str(status.get('stop_reason'))+'; diagnostics packet: '+str(archive))
    return {**launch_meta,'state':status.get('state'),
            'observations':status.get('observations'),'archive':str(archive)}
