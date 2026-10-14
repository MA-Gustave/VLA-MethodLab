"""Read-only EPCC Test94 build/Slurm diagnostics used by both Studio views.

A directory created before sbatch is NOT a queued job. Only Slurm establishes
queued/running; compiler diagnostics establish a pre-Slurm failure. Do not
infer successful submission from the historical label ``build/queued``.
"""
from __future__ import annotations
import re

# Do not display arbitrary remote log content/credentials in the dashboard.
_COMPILE_ERROR=re.compile(r'(?im)^.{0,230}(?:fatal error:|\berror:|TEST94 EPCC TOOLCHAIN ERROR|^Traceback \(most recent call last\)).{0,260}$')
_SCRIPT=re.compile(r'(?:test94_epcc_build\.py|test94_native\.py\s+build-only|/clang\+\+|/riscv64-unknown-linux-gnu-g\+\+)')


def build_error_hint(log):
    """Return a concise compiler error only when actual diagnostic evidence exists."""
    matches=_COMPILE_ERROR.findall(str(log)[-32768:])
    if not matches:return ''
    last=matches[0].strip()
    # Omit path and unrelated lines, keeping the actual error cause.
    for marker in ('fatal error:','error:','TEST94 EPCC TOOLCHAIN ERROR'):
        k=last.find(marker)
        if k>=0:
            last=last[k:];break
    return ' '.join(last.split())[:130]


def is_live_build(ps_text,workdir):
    """A compiler command tied to this exact run is evidence of an active build.

    Do not mistake Studio's grep/ps probe itself for a compiler process.
    """
    if not isinstance(workdir,str) or not workdir:return False
    for line in str(ps_text).splitlines():
        if workdir not in line:continue
        if line.lstrip().startswith(('sh -c ','bash -c ','ps ','grep ')):continue
        if _SCRIPT.search(line):return True
    return False


def tail_sftp(sftp,path,limit=8192):
    """Bound remote log reads. Missing files are an expected pre-Slurm state."""
    try:
        size=int(sftp.stat(path).st_size)
        if size<=0:return ''
        with sftp.open(path,'rb') as f:
            if size>limit:
                try:f.seek(size-limit)
                except (OSError,AttributeError):pass
            data=f.read(limit)
        return data.decode('utf-8','replace') if isinstance(data,bytes) else str(data)
    except (OSError,ValueError,TypeError):return ''


def pre_slurm_diagnosis(sftp,workdir,ps_text='',status_state=''):
    """Classify a run without Slurm allocation, conservatively.

    A local script saying 'build/queued' is *not* a Slurm pending state.
    """
    log=tail_sftp(sftp,workdir+'/studio94-build.log') if sftp else ''
    hint=build_error_hint(log)
    if is_live_build(ps_text,workdir):
        return 'building','Compilation LLVM sur le login EPCC confirmée par processus (pas encore de job Slurm).'
    if hint:
        return 'failed','Échec compilation avant Slurm : '+hint
    if status_state in ('failed','safety_stop'):
        return 'failed','Échec indiqué dans le statut distant.'
    if sftp:
        try:
            if sftp.stat(workdir+'/builds.json').st_size>0:
                return 'unknown','Compilation probablement terminée, mais aucun job Slurm actif ou confirmé.'
        except OSError:pass
    return 'unknown','Tentative avant Slurm : aucun job actif confirmé et aucune fin de compilation prouvée.'
