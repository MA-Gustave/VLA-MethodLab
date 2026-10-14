"""Safe, low-traffic status of Test94 for the two Studio SSH target profiles.

This is an *observer*, not an automatic remote job launcher. Cache updates are
best-effort and always distinguish a server-confirmed state from a local hint.
"""
from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
import re
import shlex

PROFILES=('Cloud-V','EPCC')
TERMINAL={'completed','failed','stopped','safety_stop'}
RUN_ID=re.compile(r'^test94-\d{8}T\d{6}Z-[a-f0-9]{6}$')


def _utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def _is_valid_run(launch):
    run=str(launch.get('id') or '')
    wd=str(launch.get('workdir') or '')
    return bool(RUN_ID.fullmatch(run) and wd.startswith('/') and wd.endswith('/'+run))


def latest_run(results_root):
    """Read only the most recent Test94 launch and associated locally cached state."""
    folder=Path(results_root).expanduser()/'TestRunner'/'machine-compare-94-1h'
    # Capped to guard against excessive directory scans on large results folders.
    try:
        dirs=sorted((p for p in folder.iterdir() if p.is_dir()),reverse=True)[:50]
    except OSError:
        return None
    for directory in dirs:
        try:
            launch=json.loads((directory/'launch94.json').read_text(encoding='utf-8'))
            if not isinstance(launch,dict) or not _is_valid_run(launch):continue
            cached_file=directory/'status_pc94.json'
            cached=json.loads(cached_file.read_text(encoding='utf-8')) if cached_file.exists() else None
            if not isinstance(cached,dict):cached=None
            return {'launch':launch,'cached':cached,'folder':directory}
        except (OSError,ValueError,TypeError):continue
    return None


def write_status(folder, profile, state, detail='', verified=False, run_id=None):
    """Store a limited, non-secret status for reuse after Studio restarts."""
    if profile not in PROFILES:raise ValueError('Unknown profile')
    directory=Path(folder)
    directory.mkdir(parents=True,exist_ok=True)
    record={'profile':profile,'state':str(state)[:48].lower(),
            'detail':str(detail).replace('\r',' ').replace('\n',' ')[:180],
            'updated_utc':_utc(),'verified':bool(verified)}
    if run_id and RUN_ID.fullmatch(str(run_id)):record['run_id']=run_id
    target=directory/'status_pc94.json'
    temporary=directory/'status_pc94.json.tmp'
    temporary.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(target)
    return record


def display(record, connected=False):
    """Return text + semantic presentation from a cached state."""
    if not record:
        return '— No Test 94', 'idle'
    state=str(record.get('state') or 'unknown').lower()
    detail=str(record.get('detail') or '').strip()
    verified=bool(record.get('verified'))
    mapping={'upload':'Uploading','prepare':'Preparing','build':'Building','building':'Building',
             'starting':'Starting','queued':'Queued','pending':'Queued',
             'running':'Running','repeat':'Running','train':'Running',
             'holdout':'Running','completed':'Completed', 'downloaded':'Completed',
             'failed':'Failed','stopped':'Stopped','warning':'Warning',
             'unknown':'Unknown','monitoring_stopped':'Monitoring off',
             'monitoring_timeout':'Monitor timed out'}
    label=mapping.get(state,state.replace('_',' ').title())
    kind='ok' if state in {'completed','downloaded'} else 'error' if state=='failed' else 'warning' if state in {'warning','stopped','monitoring_timeout'} else 'active' if state in {'upload','prepare','build','building','starting','queued','pending','running','train','holdout','repeat','monitoring_stopped'} else 'idle'
    try:
        stamp=dt.datetime.fromisoformat(str(record.get('updated_utc','')).replace('Z','+00:00'))
        tm=stamp.astimezone().strftime('%H:%M')
    except ValueError:
        tm='?'
    # A disconnected session cannot assert that its remote process is still running.
    live=connected and verified
    prefix='' if live else 'Last: '
    summary=prefix+label
    if detail:summary+=' · '+detail[:42]
    summary+=' · '+tm
    if not live and kind=='ok':kind='idle'  # cached success is not newly verified
    return summary,kind


def remote_probe(ssh,launch):
    """Ask the *currently connected* machine for one status snapshot.

    Never reaches the other machine, never downloads large files, never issues
    a stop request, and never assumes an SSH PID means the job is alive.
    """
    if not _is_valid_run(launch):raise ValueError('Invalid saved Test94 remote path')
    workdir=launch['workdir'];profile=launch.get('mode')
    if profile not in PROFILES:raise ValueError('Unknown Test94 profile')
    safe=shlex.quote(workdir)
    command=('if test -s '+shlex.quote(workdir+'/status94.json')+'; then cat '+shlex.quote(workdir+'/status94.json')+
             '; elif test -f '+shlex.quote(workdir+'/test94_results.zip')+'; then echo \'{"state":"completed"}\';'
             ' else echo \'{}\'; fi')
    raw=ssh.exec_text(command)
    status=json.loads(raw.strip() or '{}')
    if not isinstance(status,dict):raise ValueError('Invalid remote status')
    state=str(status.get('state','')).lower().strip()
    phase=str(status.get('phase') or '').strip()
    rows=status.get('rows')
    if state in TERMINAL:
        text=(phase+' · ' if phase and phase!='finish' else '')+ (str(rows)+' rows' if isinstance(rows,int) else 'remote confirmed')
        return state,text.strip(' ·')
    if profile=='Cloud-V' and state in ('running','repeat','build','train','holdout'):
        text=(phase+' · ' if phase else '')+(str(rows)+' rows' if isinstance(rows,int) else 'active')
        return 'running',text.strip(' ·')
    if profile=='EPCC':
        job_id=str(launch.get('job_id') or '')
        if not job_id.isdigit():
            # No Slurm job ID: the old label 'build/queued' is not evidence
            # of an actual queue entry. Check compiler log and the process
            # list before asserting live work.
            from rvvlab_epcc94_diagnostics import pre_slurm_diagnosis
            ps_text=ssh.exec_text('ps -eo args 2>/dev/null || true')
            sftp=ssh.client.open_sftp() if getattr(getattr(ssh,'client',None),'open_sftp',None) else None
            try:result,detail=pre_slurm_diagnosis(sftp,workdir,ps_text,state)
            finally:
                if sftp:sftp.close()
            return ('build' if result=='building' else 'failed' if result=='failed' else 'warning',detail)
        out=ssh.exec_text('squeue -h -j '+shlex.quote(job_id)+' -o %T 2>/dev/null || true').strip()
        s=out.splitlines()[0].strip().upper() if out else ''
        if s in ('RUNNING','COMPLETING'):return 'running','Slurm '+s.lower()
        if s in ('PENDING','CONFIGURING','SUSPENDED'):return 'queued','Slurm '+s.lower()
        if s in ('FAILED','CANCELLED','TIMEOUT','NODE_FAIL'):return 'failed','Slurm '+s.lower()
        # The Slurm job may have completed before status94.json materialized.
        return 'warning','Job not in queue; verify results'
    # No reliable remote progress yet; a PID alone is not proof of execution.
    return 'starting','Awaiting remote status'
