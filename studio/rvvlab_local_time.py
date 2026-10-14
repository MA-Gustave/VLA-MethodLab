#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local-PC clock and display-only conversion of remote UTC timestamps.

The remote status.json, logs, run IDs and evidence remain in UTC.  Calling
``astimezone()`` without an argument uses the OS (Windows) timezone, including
its daylight-saving offset for the date being displayed. No network access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


def utc_offset_label(when: datetime) -> str:
    """Return an explicit UTC offset so clocks stay understandable across DST."""
    offset = when.utcoffset() or timedelta(0)
    seconds = round(offset.total_seconds())
    sign = '+' if seconds >= 0 else '-'
    minutes = abs(seconds) // 60
    return f'UTC{sign}{minutes // 60:02d}:{minutes % 60:02d}'


def clock_text(local_now: datetime | None = None) -> str:
    """Live header text, from the PC timezone, alongside reference UTC."""
    if local_now is None:
        local_now = datetime.now().astimezone()
    elif local_now.tzinfo is None:
        # Treat explicitly supplied wall-clock input as OS local time.
        local_now = local_now.astimezone()
    utc_now = local_now.astimezone(timezone.utc)
    return (f'PC  {local_now:%H:%M:%S} ({utc_offset_label(local_now)})'
            f'   |   UTC  {utc_now:%H:%M:%S}')


def remote_utc_as_local(value: str | None) -> str:
    """Display the server's ISO8601 UTC time in the PC timezone.

    Malformed/missing timestamps are left unchanged. This function never
    changes the underlying status or evidence and never guesses server time.
    """
    if value is None:
        return ''
    raw = str(value).strip()
    if not raw:
        return ''
    try:
        timestamp = datetime.fromisoformat(raw[:-1] + '+00:00' if raw.endswith(('Z','z')) else raw)
        if timestamp.tzinfo is None:
            # Lab v5 uses UTC even where an older record omitted the suffix.
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        local = timestamp.astimezone()
        return f'{local:%Y-%m-%d %H:%M:%S} {utc_offset_label(local)}'
    except (ValueError, OverflowError):
        return raw
