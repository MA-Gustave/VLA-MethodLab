"""Test102 Cloud-V result recovery (Windows-safe, read-only over SSH).

Separate from the benchmark/launcher: no server-side writes, no new jobs.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import posixpath
import re
import shlex
import zipfile

RUN_ID = re.compile(r'^test102-\d{8}T\d{6}Z-[0-9a-f]{6}$')
ZIP_NAME = 'test102_results.zip'
MAX_ARCHIVE = 512 * 1024 * 1024
MAX_EXTRACTED = 512 * 1024 * 1024
ALLOWED = frozenset((
    'builds102.json', 'machine102.json', 'status102.json',
    'results102.csv', 'summary102.json', 'REPORT_102.md',
    'corpus_manifest102.json', 'inputs102.json', 'studio102-build.log',
    'slurm102-exit.json', 'slurm102-runtime.log', 'studio102-cloudv.log',
))
REQUIRED = frozenset(('status102.json', 'REPORT_102.md'))


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def check_zip(path, *, expected_state=None):
    """Validate bounds, exact member names, CRC and completed-run evidence."""
    with zipfile.ZipFile(path, 'r') as z:
        items = z.infolist()
        names = [info.filename for info in items]
        if not REQUIRED.issubset(names) or len(names) != len(set(names)) or not set(names).issubset(ALLOWED):
            raise RuntimeError('Test102 archive contains missing, unexpected or repeated files')
        if sum(info.file_size for info in items) > MAX_EXTRACTED or any(
            info.is_dir() or info.file_size > MAX_EXTRACTED or info.flag_bits & 1 for info in items
        ):
            raise RuntimeError('Unsafe Test102 archive entry')
        if z.testzip() is not None:
            raise RuntimeError('Test102 archive has a corrupt ZIP member')
        status = json.loads(z.read('status102.json'))
        if not isinstance(status, dict):
            raise RuntimeError('Invalid Test102 status in archive')
        if expected_state == 'completed':
            if status.get('state') != 'completed' or status.get('validated') is not True or (
                type(status.get('rows')) is not int or status['rows'] < 1
            ):
                raise RuntimeError('Archive does not confirm a validated completed Test102')
        return names


def sync_cloudv_test102(ssh, remote_name, run_id, local_root, *, workdir=None, expected_state='completed'):
    """SFTP result ZIP using POSIX remote paths and pathlib-only local paths.

    The selected run is fixed by run_id; SHA-256 from the actual remote ZIP must
    match before anything is committed locally. No remote writes/commands except
    read-only sha256sum. Returns the verified local ZIP as pathlib.Path.
    """
    if not RUN_ID.fullmatch(str(run_id)):
        raise ValueError('Invalid Test102 run ID')
    if workdir is None:
        workdir = posixpath.join(str(ssh.base(remote_name)), 'test102-cloudv-runs', run_id)
    workdir = str(workdir).replace('\\', '/')
    if not workdir.startswith('/') or posixpath.basename(workdir) != run_id:
        raise ValueError('Invalid remote Test102 workdir')
    remote = posixpath.join(workdir, ZIP_NAME)
    target = Path(local_root).expanduser() / 'TestRunner' / 'test102-escape-stage' / ('Cloud-V-' + run_id)
    target.mkdir(parents=True, exist_ok=True)
    part = target / (ZIP_NAME + '.part')
    dest = target / ZIP_NAME
    try:
        with ssh.client.open_sftp() as sftp:
            size = sftp.stat(remote).st_size
            if not 0 < size <= MAX_ARCHIVE:
                raise RuntimeError('Cloud-V Test102 archive is empty or too large')
            sftp.get(remote, str(part))  # Paramiko requires native str for Windows destinations.
        if part.stat().st_size != size:
            raise RuntimeError('Cloud-V Test102 download truncated')
        actual = sha256(part)
        reply = ssh.exec_text('sha256sum ' + shlex.quote(remote)).strip().split()
        if not reply or not re.fullmatch(r'[0-9a-f]{64}', reply[0].lower()) or reply[0].lower() != actual:
            raise RuntimeError('Cloud-V Test102 SHA-256 mismatch')
        names = check_zip(part, expected_state=expected_state)
        os.replace(part, dest)
        with zipfile.ZipFile(dest) as z:
            for name in names:
                tmp = target / (name + '.part')
                try:
                    with z.open(name) as src, tmp.open('wb') as out:
                        for block in iter(lambda: src.read(1024 * 1024), b''):
                            out.write(block)
                    os.replace(tmp, target / name)
                finally:
                    tmp.unlink(missing_ok=True)
        marker = target / 'SYNC_OK.txt'
        tmp = target / 'SYNC_OK.txt.part'
        try:
            tmp.write_text('SHA256-verified Cloud-V Test102 archive: ' + actual + '\nrun_id: ' + run_id + '\n', encoding='utf-8')
            os.replace(tmp, marker)
        finally:
            tmp.unlink(missing_ok=True)
        return dest
    finally:
        part.unlink(missing_ok=True)
