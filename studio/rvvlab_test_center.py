"""Test Center inventory for all manifest-defined experiments.

Zero remote writes, no benchmark execution, explicit evidence labels. Local scanning
never equates TestRunner PASS with completed/validated remote measurements.
"""
from __future__ import annotations
import datetime as dt
import json
import re
from pathlib import Path

NIGHT_ID=re.compile(r'^night-\d{8}T\d{6}Z-[a-f0-9]{6}$')
TEST94_ID=re.compile(r'^test94-\d{8}T\d{6}Z-[a-f0-9]{6}$')
RUN_IN_TEXT=re.compile(r'night-\d{8}T\d{6}Z-[a-f0-9]{6}')
TEST94_KEY='machine-compare-94-1h'
TEST96_KEY='test96-epcc-8h'
TEST97_KEY='test97-epcc-v5-3h'
TEST98_KEY='test98-real-corpus'
DONE={'completed','downloaded'}
ACTIVE={'building','starting','preflight','build','screen','confirm','running','train','repeat','holdout','queued','pending','adaptive','specialists','stage1_focus'}
BAD={'failed','safety_stop','error'}


def _json(path):
    try:
        if path.stat().st_size>2*1024*1024:return {}
        value=json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError,UnicodeError):return {}


def _dirs(path,limit=75):
    try:return sorted((p for p in path.iterdir() if p.is_dir()),reverse=True)[:limit]
    except OSError:return []


def _run_from_local(directory):
    d=_json(directory/'result.json')
    texts=[json.dumps(d,ensure_ascii=False)]
    try:
        log=directory/'runner.log'
        if log.is_file():
            with log.open('rb') as fh:
                # Capture both beginning and tail without loading a massive log.
                first=fh.read(120_000);fh.seek(max(0,log.stat().st_size-180_000));last=fh.read(180_000)
            texts.extend([first.decode('utf8','replace'),last.decode('utf8','replace')])
    except OSError:pass
    ids=RUN_IN_TEXT.findall('\n'.join(texts))
    return ids[-1] if ids else None


def local_state(item,root,history=None):
    """Status with evidence; no positive completion from PASS history alone."""
    root=Path(root).expanduser()
    identifier=item['id'];base=root/'TestRunner'/identifier
    directories=_dirs(base)
    latest=directories[0] if directories else None
    history=(history or {}).get(identifier,{})
    result={'test_id':identifier,'state':'unknown','proof':'Aucun résultat local vérifié',
            'downloaded':False,'directory':str(latest) if latest else '',
            'run_id':'','checked':'Local uniquement'}
    if latest:
        result['run_id']=_run_from_local(latest) or ''
        # EPCC archives are stored by validated remote ID, separately from
        # a local script execution. Only a completed SHA256 sync counts.
        if identifier in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY):
            run_prefix='test94-' if identifier==TEST94_KEY else 'test96-' if identifier==TEST96_KEY else 'test97-' if identifier==TEST97_KEY else 'test98-'
            for folder in directories:
                if not folder.name.startswith('EPCC-'+run_prefix):continue
                if (folder/'SYNC_OK.txt').is_file() and (folder/('test94_results.zip' if identifier==TEST94_KEY else 'test96_results.zip' if identifier==TEST96_KEY else 'test97_results.zip' if identifier==TEST97_KEY else 'test98_results.zip')).is_file():
                    result.update(state='downloaded',downloaded=True,
                                  proof='Archive EPCC vérifiée SHA256 sur PC',
                                  directory=str(folder),run_id=folder.name[5:])
                    return result

        if identifier==TEST94_KEY:
            packets=[p for p in [d/'test94_results.zip' for d in directories]
                     if p.is_file() and p.stat().st_size>0
                     and (not p.parent.name.startswith('EPCC-') or (p.parent/'SYNC_OK.txt').is_file())]
            if packets:
                chosen=packets[0]
                result.update(state='downloaded',downloaded=True,
                    proof='Archive Test 94 présente sur le PC (SHA256 à vérifier dans le journal de récupération)',
                    directory=str(chosen.parent))
                return result
            for d in directories:
                status=_json(d/'status_pc94.json')
                if status.get('verified'):
                    result.update(state=str(status.get('state') or 'unknown').lower(),proof='Dernier état distant enregistré (cache)',
                                  directory=str(d),run_id=status.get('run_id') or '')
                    return result
            if (latest/'launch94.json').exists():
                result.update(state='unknown',proof='Lancement connu, état serveur à vérifier')
                return result
        if (latest/'result.json').exists():
            result.update(state='local_pass',proof='Script terminé ; fin distante non prouvée')
        elif (latest/'runner.log').exists():
            try:
                tail=(latest/'runner.log').read_bytes()[-2000:].decode('utf8','replace')
                if 'FAIL ' in tail or 'Traceback' in tail:
                    result.update(state='failed',proof='Échec signalé dans le journal local')
                else:result.update(state='unknown',proof='Journal local, résultat final non confirmé')
            except OSError:pass
    if history.get('state')=='PASS' and result['state']=='unknown':
        result.update(state='local_pass',proof='Historique PASS local seulement')
    if identifier not in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY) and result['run_id']:
        night=root/'NightRuns'/result['run_id']
        if (night/'SYNC_OK.txt').is_file():
            result.update(state='downloaded',downloaded=True,proof='Snapshot NightRuns synchronisé et SHA256 vérifié',directory=str(night))
    return result


def check_remote_night(ssh,remote_name,items,local_results,history=None):
    """Remote read-only snapshots; never infer test ID from a generic night-runs name.

    Link by exact run IDs recorded in that test's local logs, or by explicit
    campaign token if unambiguous. No heuristic number matching of pilot/8h.
    """
    from rvvlab_night import remote_runs
    runs=remote_runs(ssh,remote_name)
    mappings={}
    campaign_ids={}
    for item in items:
        # Each trusted manifest already references a local, SHA256-pinned script.
        # Its hard-coded launcher campaign field provides a remote-to-test key.
        try:
            source=item['script_path'].read_text(encoding='utf-8')
            expr=re.search(r'''['"]campaign['"]\s*:\s*['"]([a-z0-9_]{4,80})['"]''',source)
            if expr:campaign_ids.setdefault(expr.group(1),set()).add(item['id'])
        except OSError:pass
    for item in items:
        state=local_state(item,local_results,history)
        if NIGHT_ID.fullmatch(state['run_id']):
            mappings.setdefault(state['run_id'],set()).add(item['id'])
    matched={}
    for run in runs:
        runid=str(run.get('id',''))
        if not NIGHT_ID.fullmatch(runid):continue
        ids=mappings.get(runid,set())
        campaign=str(run.get('campaign') or '')
        ids=ids or campaign_ids.get(campaign,set())
        if len(ids)!=1:continue
        item_id=next(iter(ids))
        if item_id not in matched:matched[item_id]=run
    return matched,runs


def remote_state(record):
    state=str(record.get('state') or 'unknown').lower()
    if state in DONE:return 'completed'
    if state=='building':return 'building'
    if state in ACTIVE:return 'running' if state not in ('queued','pending') else 'queued'
    if state in BAD:return 'failed'
    if state=='stopped':return 'stopped'   # Not equivalent to full completion.
    return 'unknown'


def merge(local,remote=None):
    """Remote snapshot trumps history except downloaded files remain visible."""
    merged=dict(local)
    if remote is not None:
        if local['downloaded']:
            merged['proof']=local['proof']+' · Dernier état distant : '+str(remote.get('state') or 'inconnu')
            if str(remote.get('id') or '')!=str(merged.get('run_id') or ''):
                merged['proof']+=' · Autre exécution sur EPCC : '+str(remote.get('id'))
            merged['checked']='Serveur vérifié'
            return merged
        remote_result=remote_state(remote)
        if remote_result!='unknown':
            merged['state']='downloaded' if remote_result=='completed' and local['downloaded'] else remote_result
            merged['proof']=str(remote.get('proof') or ('Serveur confirmé : '+str(remote.get('state') or '?')))
        elif not local['downloaded']:
            merged['state']='unknown'
            merged['proof']=str(remote.get('proof') or 'État serveur non confirmé : nouvelle vérification nécessaire')
        merged['run_id']=str(remote.get('id') or merged['run_id'])
        merged['checked']='Serveur vérifié'
    return merged


def label(state):
    return {'downloaded':'TÉLÉCHARGÉ','completed':'TERMINÉ · distant','running':'EN COURS',
            'queued':'EN ATTENTE','building':'COMPILATION EPCC','failed':'ÉCHEC','stopped':'ARRÊTÉ · partiel',
            'local_pass':'PASS local (à vérifier)','unknown':'À VÉRIFIER'}.get(state,'À VÉRIFIER')


def inspect_remote_94(ssh,remote_name,profile):
    """Read-only remote discovery of Test 94, including runs without local launch JSON.

    Never call completed unless the remote status explicitly indicates completed,
    there are positive measurements, and a nonempty result packet exists.
    """
    if profile not in ('Cloud-V','EPCC'):raise ValueError('Invalid machine')
    root=ssh.base(remote_name)+'/test94-runs'
    client=ssh.client.open_sftp()
    found=[]
    try:
        try:names=client.listdir(root)
        except OSError as ex:
            if getattr(ex,'errno',None)==2 or 'no such file' in str(ex).lower():return {'state':'unknown','id':'','proof':'Aucun dossier Test94 distant', 'packet':False}
            raise
        for name in sorted((x for x in names if TEST94_ID.fullmatch(x)),reverse=True)[:70]:
            path=root+'/'+name
            d={}
            try:
                with client.open(path+'/status94.json','r') as f:
                    raw=f.read(16000)
                if isinstance(raw,bytes):raw=raw.decode('utf8','replace')
                d=json.loads(raw)
                if not isinstance(d,dict):d={}
            except (ValueError,TypeError,OSError):pass
            packet=False
            try:packet=client.stat(path+'/test94_results.zip').st_size>0
            except OSError:pass
            found.append({'id':name,'state':str(d.get('state') or 'unknown').lower(),
                          'rows':d.get('rows',0),'packet':packet,'path':path})
    finally:client.close()
    if not found:return {'state':'unknown','id':'','proof':'Aucun Test94 distant trouvé','packet':False}
    from rvvlab_epcc94_diagnostics import pre_slurm_diagnosis
    active={}
    if profile=='EPCC':
        lines=ssh.exec_text('squeue -h -u "$USER" -o "%j|%T|%Z" 2>/dev/null || true').splitlines()
        for line in lines:
            vals=line.split('|',2)
            if len(vals)==3 and vals[0].strip()=='rvvlab-test94':active[vals[2].strip()]=vals[1].strip().upper()
    else:
        process=ssh.exec_text('ps -eo args 2>/dev/null || true')
        for row in found:
            if any(row['path'] in line and 'test94_native.py' in line and (' run-only ' in line or ' all ' in line)
                   for line in process.splitlines()):active[row['path']]='RUNNING'
    for row in found:
        st=active.get(row['path'],'')
        if st in ('RUNNING','COMPLETING'):
            row.update(state='running',proof='Processus / Slurm actif confirmé');return row
        if st in ('PENDING','CONFIGURING','SUSPENDED'):
            row.update(state='queued',proof='En attente Slurm confirmé');return row
    for row in found:
        if row['state']=='completed' and row['packet'] and isinstance(row['rows'],int) and row['rows']>0:
            row['proof']='État completed + mesures + archive distante';return row
    last=found[0]
    if last['state'] in ('failed','safety_stop'):
        last.update(state='failed',proof='Échec distant enregistré');return last
    if profile=='EPCC':
        # Re-open SFTP only after process/squeue inspection, not while the
        # previous handle is held (some EPCC gateways limit SFTP sessions).
        ps_text=ssh.exec_text('ps -eo args 2>/dev/null || true')
        sftp=ssh.client.open_sftp()
        try:state,proof=pre_slurm_diagnosis(sftp,last['path'],ps_text,last['state'])
        finally:sftp.close()
        last.update(state=state,proof=proof)
    else:last.update(state='unknown',proof='Ancienne tentative sans fin validée')
    return last
