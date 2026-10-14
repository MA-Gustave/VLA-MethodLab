#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Presentational labels for Lab Studio. Original IDs and audit timestamps stay unchanged."""
from __future__ import annotations
from datetime import datetime, timezone
import re

# Only an explicit launcher.json `campaign` code identifies a run.
# Never guess its identity from the run's date or the active UI selection.
CAMPAIGNS = {
    'adaptive_dispatch_v2_smoke_5m': ('85', 'Test 85 — Vérification rapide (5 min)', 'adaptive-dispatch-v2-smoke'),
    'adaptive_dispatch_v2_30m': ('86', 'Test 86 — Comparaison adaptative (30 min)', 'adaptive-dispatch-v2-30m'),
    'adaptive_prequal_exploratory_60m': ('87', 'Test 87 — Exploration variée (1 h)', 'adaptive-prequal-exploratory-60m'),
    'adaptive_prequal_exploratory_8h': ('88', 'Test 88 — Exploration combinatoire (8 h)', 'adaptive-prequal-exploratory-8h'),
    'adaptive_prequal_corrected_1h': ('89', 'Test 89 — Préqualification (1 h)', 'adaptive-prequal-corrected-60m'),
    'adaptive_holdout_validation_2h': ('90', 'Test 90 — Validation ciblée (2 h)', 'adaptive-holdout-validation-2h'),
}
# Older manifests were not necessarily published under the IDs above;
# the label is a presentation choice, the script and digest remain pinned.
SCRIPT_NAMES = {
    '85_adaptive_dispatch_smoke_5m.py': 'Test 85 — Vérification rapide (5 min)',
    '86_adaptive_dispatch_30m.py': 'Test 86 — Comparaison adaptative (30 min)',
    '87_prequal_exploration_60m.py': 'Test 87 — Exploration variée (1 h)',
    '88_prequal_exploration_8h.py': 'Test 88 — Exploration combinatoire (8 h)',
    '89_prequal_corrected_60m.py': 'Test 89 — Préqualification (1 h)',
    '90_holdout_validation_2h.py': 'Test 90 — Validation ciblée (2 h)',
}
DURATION = {'85':'5 min','86':'30 min','87':'1 h','88':'8 h','89':'1 h','90':'2 h'}
TERMINAL = frozenset({'stopped','failed','completed','complete','finished','done','safety_stop','timeout','cancelled'})


def script_name(item):
    script = item.get('script_path')
    name = getattr(script, 'name', str(script or ''))
    return SCRIPT_NAMES.get(name, str(item.get('title') or 'Test sans titre').split(' (')[0])


def run_identity(row):
    data = CAMPAIGNS.get(str(row.get('campaign') or ''))
    if data:
        return {'number':data[0], 'name':data[1], 'test_id':data[2], 'known':True}
    return {'number':None, 'name':'Ancienne campagne — test non identifié', 'test_id':None, 'known':False}


def run_state(row):
    state = str(row.get('state') or '').lower()
    reason = str(row.get('stop_reason') or '').lower()
    if state in ('completed','complete','finished','done'):
        return 'Terminé', 'À récupérer'
    if state == 'stopped':
        if any(part in reason for part in ('budget', 'time budget', 'time limit', 'hour', 'duration')):
            return 'Terminé — durée atteinte', 'À récupérer'
        return 'Arrêté — résultats partiels', 'À récupérer'
    if state == 'failed':
        return 'Erreur — voir détails', 'Diagnostics à récupérer'
    if state == 'safety_stop':
        return 'Arrêt de sécurité', 'Résultats à récupérer'
    if state in ('timeout','cancelled'):
        return 'Arrêté', 'Résultats à récupérer'
    if state in ('build','compile','compiling'):
        return 'En cours — préparation', 'Pas encore'
    if state in ('anchor','confirm','confirm_secondary','confirm_primary','screen'):
        return 'En cours — vérification', 'Pas encore'
    if state.startswith(('explore','measure','run')) or state in ('running',):
        return 'En cours — mesures', 'Pas encore'
    if state in ('preflight','starting','launch_incomplete'):
        return 'En cours — démarrage', 'Pas encore'
    return ('En cours' if state else 'État inconnu'), 'Pas encore'


def local_update(value):
    """Return a compact local-wall-clock timestamp, or an em dash."""
    if not value: return '—'
    raw = str(value).strip()
    try:
        stamp=datetime.fromisoformat(raw[:-1]+'+00:00' if raw.endswith(('Z','z')) else raw)
        if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone().strftime('%d/%m %H:%M')
    except (ValueError, OverflowError):
        return '—'


def safe_evidence_name(row):
    info=run_identity(row)
    number=info['number'] or 'inconnu'
    runid=str(row.get('id') or '')
    match=re.match(r'^night-(\d{8})T(\d{6})Z-[0-9a-f]{6}$',runid)
    date=(match.group(1)+'_'+match.group(2)) if match else 'sans_date'
    return f'Test-{number}_Resultats_{date}.zip'
