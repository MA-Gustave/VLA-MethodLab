"""Lightweight, privacy-conscious Mission Control helpers (no SSH side-effects)."""
from __future__ import annotations
import re
import datetime as dt

def fresh(record, seconds=105):
    """Only a recent, remotely verified observation can be called live."""
    if not isinstance(record,dict) or not record.get('verified'):return False
    try:
        stamp=dt.datetime.fromisoformat(str(record['updated_utc']).replace('Z','+00:00'))
        if stamp.tzinfo is None:return False
        age=(dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()
        return -15 <= age <= seconds
    except (ValueError,KeyError,TypeError,OverflowError):return False


STATES_DONE={'completed','downloaded'}
STATES_BUSY={'starting','upload','prepare','build','queued','pending','running',
             'repeat','train','holdout','monitoring_stopped'}


def next_action(machine, connected, record, confirmed_live=False, checking=False):
    if checking:return 'Checking '+machine+' remotely. No test will be started automatically.'
    if not connected:return 'Connect SSH to '+machine+', then click Check Test 94.'
    if not confirmed_live:return 'Click Check Test 94 to verify the latest remote state before deciding.'
    state=str((record or {}).get('state','unknown')).lower()
    if state in STATES_DONE:return 'Test 94 completed on '+machine+'. Recover its verified results; no rerun is needed.'
    if state in ('running','train','repeat','holdout','build','starting','upload'):
        return 'Test 94 appears active. Keep this Studio window open to monitor; do not start a duplicate.'
    if state in ('queued','pending'):return 'The EPCC job is in the queue. Wait; do not start a second job.'
    if state=='missing':return 'No remote Test 94 was found. Click Run if needed to verify again and launch manually.'
    if state=='failed':return 'The latest remote attempt failed. Review the log, then Run if needed to retry.'
    return 'Remote status is uncertain. Check again before considering a new run.'


def summary_text(machine,connected,current,other):
    """Safe clipboard text: state summary only, no machine details or secrets."""
    second='EPCC' if machine=='Cloud-V' else 'Cloud-V'
    def value(record):
        state=str((record or {}).get('state','unknown'))
        return state if re.fullmatch(r'[a-z_]{1,45}',state) else 'unknown'
    return ('RVV-VLA Lab Studio — Test 94\n'
            +machine+': '+value(current)+'; SSH '+('connected' if connected else 'disconnected')+'\n'
            +second+': '+value(other)+' (cached; not a live check)\n'
            +'A successful remote check is required before launching.\n')


def preset_command(name,profile,remote_name):
    """Only diagnostic commands, never mutate remote storage nor launch jobs."""
    if profile not in ('Cloud-V','EPCC'):raise ValueError('Unknown profile')
    if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,65}',remote_name):
        raise ValueError('Remote folder name contains unsupported characters')
    work='$HOME/'+remote_name+'/test94-runs'
    # Double quotes allow shell $HOME expansion, while folder name is validated.
    if name=='Test 94 statuses':
        return ('for f in "'+work+'"/test94-*/status94.json; do '
                '[ -f "$f" ] || continue; printf "\\n%s\\n" "$f"; '
                'head -c 1500 "$f"; printf "\\n"; done')
    if name=='Test 94 processes':
        if profile=='EPCC':return 'squeue -u "$USER" -o "%.16i %.22j %.10T %.20R"'
        return 'ps -eo pid,etime,args | grep "[t]est94_native.py"'
    if name=='System / architecture':return 'uname -m; hostname; lscpu | head -n 22'
    if name=='Disk space':return 'df -h "$HOME"'
    if name=='Slurm jobs (EPCC)':
        if profile!='EPCC':raise ValueError('Slurm jobs apply only to EPCC')
        return 'squeue -u "$USER" -o "%.16i %.22j %.10T %.20R"'
    if name=='Slurm nodes (EPCC)':
        if profile!='EPCC':raise ValueError('Slurm nodes apply only to EPCC')
        return 'sinfo -N -o "%N %P %T %f"'
    raise ValueError('Unknown diagnostic shortcut')
