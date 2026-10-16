"""Elapsed wall-clock presentation for remotely verified RVV Lab campaigns.

No SSH calls or writes are performed here. A run ID timestamp marks creation,
not necessarily benchmark start, so it is always labelled an estimate.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

FINISHED = frozenset(('completed', 'complete', 'finished', 'failed',
                      'safety_stop', 'stopped', 'incomplete', 'done'))
_ID_STAMP = re.compile(r'^(?:test\d+|night)-(\d{8}T\d{6})Z-[0-9a-f]{6}$')


def parse_utc(value):
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        instant = value
    else:
        try:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return datetime.fromtimestamp(value, tz=timezone.utc)
            value = str(value).strip()
            instant = datetime.fromisoformat(value[:-1] + '+00:00' if value.endswith(('Z', 'z')) else value)
        except (OverflowError, TypeError, ValueError, OSError):
            return None
    return (instant.replace(tzinfo=timezone.utc) if instant.tzinfo is None
            else instant.astimezone(timezone.utc))


def run_start(row):
    """Return (time, estimated). Prefer worker-reported start over run ID."""
    for key in ('start_utc', 'started_utc', 'start_time_utc', 'started_at'):
        instant = parse_utc(row.get(key))
        if instant is not None:
            return instant, False
    match = _ID_STAMP.fullmatch(str(row.get('id', '')))
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc), True
        except ValueError:
            pass
    return None, False


def _formatted(seconds):
    seconds = max(0, int(seconds))
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    return (f'{days}d {hours:02d}h {minutes:02d}m {seconds:02d}s' if days else
            f'{hours}h {minutes:02d}m {seconds:02d}s')


def elapsed_display(row, now=None):
    """Return (display, explanation), using the current clock only for nonterminal runs."""
    if not row:
        return '—', 'No campaign selected'
    start, estimated = run_start(row)
    if start is None:
        return '—', 'Start time unavailable'
    terminal = str(row.get('state') or '').lower() in FINISHED
    if terminal:
        stop = None
        for key in ('end_utc', 'ended_utc', 'finished_utc', 'completed_utc',
                    'updated_utc', 'last_update_utc', 'last_update'):
            stop = parse_utc(row.get(key))
            if stop is not None:
                break
        if stop is None:
            return '—', 'Finished, but no final timestamp was reported'
    else:
        stop = parse_utc(now) if now is not None else datetime.now(timezone.utc)
    seconds = (stop - start).total_seconds()
    if seconds < -60:
        return '—', 'Server and PC clocks disagree'
    label = ('≈ ' if estimated else '') + _formatted(seconds)
    note = ('Estimated since campaign ID time' if estimated else 'Since reported start time')
    return label, note + (' (finished)' if terminal else ' (wall clock; not CPU time)')
