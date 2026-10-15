"""Simple, read-only-first test workflow for RVV Lab Studio.

Supported remote result formats: Test 94, Test 95 Cloud-V, Test 96 EPCC, Test 97 Cloud-V / EPCC.
The existing trusted TestRunner remains the ONLY launch mechanism.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from rvvlab_test_runner import SCRIPTS_DIR, TestContext, discover

PROFILES = {'94': ('Cloud-V', 'EPCC'), '95': ('Cloud-V',), '96': ('EPCC',), '97': ('Cloud-V', 'EPCC'), '98': ('Cloud-V','EPCC')}
TEST_IDS = {'94': 'machine-compare-94-1h', '95': 'test95-cloudv-8h',
            '96': 'test96-epcc-8h', '97': 'test97-cloudv-8h',
            '97-epcc': 'test97-epcc-v5-3h', '98': 'test98-real-corpus'}


def test_id(number, profile):
    """Map a number and target to its unique manifest; never swap Test97 targets."""
    if number not in PROFILES or profile not in PROFILES[number]:
        raise ValueError('Test ' + str(number) + ' incompatible avec ' + str(profile))
    return TEST_IDS['97-epcc'] if number == '97' and profile == 'EPCC' else TEST_IDS[number]


def manifest_target(manifest_id):
    """Return the test number and target restriction of a managed manifest."""
    if manifest_id == TEST_IDS['97-epcc']:
        return '97', ('EPCC',)
    for number in ('94', '95', '96', '97', '98'):
        if manifest_id == TEST_IDS[number]:
            allowed = ('Cloud-V',) if number == '97' else PROFILES[number]
            return number, allowed
    return None

RUN_PATTERN = {
    '95': re.compile(r'^test95-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '96': re.compile(r'^test96-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '97': re.compile(r'^test97-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '98': re.compile(r'^test98-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
}
RUN_ROOT = {'95': 'test95-runs', '96': 'test96-epcc-runs', '97': 'test97-runs', '98': 'test98-cloudv-runs'}
ZIP_NAME = {'94': 'test94_results.zip', '95': 'test95_results.zip', '96': 'test96_results.zip', '97': 'test97_results.zip', '98':'test98_results.zip'}
TERMINAL = {'completed', 'failed', 'safety_stop', 'stopped'}
ACTIVE = {'starting', 'preflight', 'building', 'build', 'queued', 'pending', 'running', 'exploring', 'train', 'holdout', 'repeat', 'preparing'}


def _read_json_sftp(sftp, path):
    try:
        with sftp.open(path, 'r') as f:
            raw = f.read(65536)
        if isinstance(raw, bytes):raw = raw.decode('utf-8', 'replace')
        doc = json.loads(raw)
        return doc if isinstance(doc, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _has_file(sftp, path):
    try:
        return sftp.stat(path).st_size > 0
    except OSError:
        return False


def _server_runs(ssh, remote_name, number, profile):
    """Read-only, bounded inventory; do not assume a local Studio launch record."""
    if profile == 'EPCC' and number in ('94', '96', '97','98'):
        from rvvlab_epcc_results import discover_epcc_runs
        kind = 'test'+number
        rows = []
        data = [r for r in discover_epcc_runs(ssh,remote_name) if r['kind']==kind]
        with ssh.client.open_sftp() as sftp:
            for info in data:
                status = _read_json_sftp(sftp, info['workdir']+'/status'+number+'.json')
                state = str(info.get('state') or 'unknown').lower()
                packet = bool(info.get('packet'))
                count = info.get('rows',0)
                validated = (state == 'completed' and packet and isinstance(count,int)
                             and not isinstance(count,bool) and count > 0 and
                             (number == '94' or status.get('validated') is True))
                if state == 'completed' and not validated:state = 'incomplete'
                # An attempt still cross-compiling on the login node may have no status.
                # Block accidental duplicate runs until that initial build is old.
                if state == 'unknown' and not packet:
                    try:
                        import calendar
                        stamp=dt.datetime.strptime(info['id'][7:22],'%Y%m%dT%H%M%S')
                        age=time.time()-calendar.timegm(stamp.timetuple())
                        if -1800 < age < 3600:state='preparing'
                    except (ValueError,OverflowError):pass
                rows.append(dict(id=info['id'],path=info['workdir'],state=state,
                                 rows=count,packet=packet,validated=validated,
                                 proof=info.get('proof','Serveur EPCC')))
        return rows
    if number == '94':
        from rvvlab_test_center import inspect_remote_94
        info = inspect_remote_94(ssh,remote_name,profile)
        if not info.get('id'):return []
        state = str(info.get('state') or 'unknown').lower()
        valid = state == 'completed' and bool(info.get('packet')) and bool(info.get('rows',0))
        if state == 'completed' and not valid:state='incomplete'
        return [dict(id=info['id'],path=info['path'],state=state,
                     rows=info.get('rows',0),packet=bool(info.get('packet')),
                     validated=valid,proof=info.get('proof',''))]
    if profile not in PROFILES[number]:
        raise ValueError('Ce test ne correspond pas à la machine sélectionnée.')
    root = ssh.base(remote_name).rstrip('/') + '/' + RUN_ROOT[number]
    sftp = ssh.client.open_sftp()
    try:
        try:names = sftp.listdir(root)
        except OSError as ex:
            if getattr(ex, 'errno', None) == 2 or 'no such file' in str(ex).lower():return []
            raise
        runs=[]
        for name in sorted((n for n in names if RUN_PATTERN[number].fullmatch(n)), reverse=True)[:25]:
            path = root + '/' + name
            status = _read_json_sftp(sftp, path + '/status' + number + '.json')
            state = str(status.get('state') or '').lower()
            zipped = _has_file(sftp, path + '/' + ZIP_NAME[number])
            valid = status.get('validated') is True
            if number == '98':
                count=status.get('rows',0)
                valid=valid and type(count) is int and count>0
            if number == '96':
                exit_status = _read_json_sftp(sftp, path + '/slurm96-exit.json')
                if exit_status and exit_status.get('return_code') != 0:
                    state = 'failed'
            if not state:
                # Directory exists, but no status is NOT proof the benchmark runs.
                # A separate /proc probe can confirm a build process if present.
                state='unconfirmed' if number=='97' else 'preparing'
            if state == 'completed' and (not valid or not zipped):
                state = 'incomplete'  # completed string alone is NOT proof
            runs.append(dict(id=name, path=path, state=state,
                             rows=status.get('rows', 0), packet=zipped,
                             validated=valid, proof='Serveur interrogé'))
        return runs
    finally:sftp.close()



# A launch may fail on the PC before Cloud-V has a test97-runs folder.
# These snapshots are local, read-only and not server-completion evidence.
def _local_attempt(results_root, number, profile=None):
    root=Path(results_root).expanduser()/'TestRunner'/(test_id(number,profile) if profile else TEST_IDS[number])
    try:
        runs=sorted((x for x in root.iterdir() if x.is_dir() and (x/'runner.log').is_file()),
                    key=lambda x:(x/'runner.log').stat().st_mtime, reverse=True)
        failures=root/'last_failure.json'
        fail=json.loads(failures.read_text(encoding='utf-8')) if failures.is_file() else {}
        latest=runs[0] if runs else None
        t=(latest/'runner.log').stat().st_mtime if latest else 0
        try:failure_time=dt.datetime.fromisoformat(fail.get('utc','')).timestamp() if fail else 0
        except (ValueError,TypeError):failure_time=0
        if failure_time>t and fail.get('state')=='failed':
            return {'state':'failed_local','time':failure_time,'detail':str(fail.get('error',''))[:350],
                    'path':str(failures)}
        if not latest:return None
        content=(latest/'runner.log').read_text(encoding='utf-8',errors='replace')[-12000:]
        lines=[x.strip() for x in content.splitlines() if x.strip()]
        tail=lines[-1] if lines else 'Journal de lancement vide'
        if 'FAIL:' in content:
            state='failed_local'
            tail=next((x for x in reversed(lines) if 'FAIL:' in x),tail)
        elif (latest/'result.json').is_file():state='local_done'
        else:state='started_local'
        return {'state':state,'time':t,'detail':tail[:350],
                'path':str(latest/'runner.log')}
    except (OSError,ValueError,TypeError):return None


def _remote_test97_processes(ssh):
    """Check /proc on Cloud-V: read-only, ignores the checking process itself.

    Base64 avoids a false match against the command doing the check.
    """
    import base64
    script="""import os,pathlib,json
rows=[]
for p in pathlib.Path('/proc').iterdir():
 if not p.name.isdecimal() or int(p.name)==os.getpid():continue
 try:
  data=(p/'cmdline').read_bytes().split(b'\\0')
  argv=[x.decode('utf-8','replace') for x in data if x]
  if not argv:continue
  if (p/'stat').read_text().rsplit(') ',1)[1][0]=='Z':continue
  if any(pathlib.PurePath(x).name=='test97_native.py' for x in argv[1:]) or any('test97_A2_' in x for x in argv):
   rows.append({'pid':int(p.name),'command':pathlib.PurePath(argv[1]).name if len(argv)>1 else argv[0]})
 except (OSError,ValueError,IndexError):pass
print(json.dumps(rows[:12]))
"""
    encoded=base64.b64encode(script.encode('utf-8')).decode('ascii')
    output=ssh.exec_text('python3 -c '+repr('import base64;exec(base64.b64decode("'+encoded+'"))'))
    result=json.loads(output.strip())
    if not isinstance(result,list):raise RuntimeError('Réponse /proc inattendue')
    return result


def _describe_local(local, runner_busy):
    if runner_busy:return '◷ Studio prépare/transfère le test (pas encore confirmé sur le serveur)'
    if not local:return '— Aucun lancement distant détecté (aucune tentative locale identifiable)'
    if local['state']=='failed_local':return '✕ Échec du lancement local — aucun lancement distant confirmé'
    if local['state']=='started_local':return '⚠ Tentative locale détectée — pas de lancement distant confirmé'
    return '— Aucun lancement distant confirmé (voir dernière tentative Studio)'

def _label(row):
    if not row:return '— Aucun lancement trouvé'
    return {
        'completed':'✓ Terminé — ZIP prêt', 'failed':'✕ Échec',
        'safety_stop':'✕ Arrêt de sécurité', 'stopped':'Arrêté',
        'running':'● En cours', 'queued':'◷ En attente Slurm',
        'pending':'◷ En attente', 'preparing':'◷ Préparation / compilation',
        'building':'◷ Compilation', 'build':'◷ Compilation',
        'incomplete':'⚠ Résultat incomplet', 'unknown':'? État non confirmé',
        'unconfirmed':'⚠ Dossier distant présent — lancement non confirmé',
        'preparing':'◷ Préparation / compilation',
    }.get(row['state'], '◷ ' + row['state'])


class SimpleTestsPanel:
    """Three actions: Run, verify server status, download verified ZIP."""
    def __init__(self, parent, studio):
        self.parent=parent;self.studio=studio
        self.events=queue.Queue();self.busy=False;self.poll_busy=False
        self.runs={};self.remote_checked=False;self.checked_at=None
        self.remote_activity=[];self.launch_number=None;self.last_check_error=None
        self.profile=studio.active_profile
        self.notice=tk.StringVar(value='Connectez SSH, puis cliquez sur Actualiser.')
        self.status=tk.StringVar(value='—')
        self.details=tk.StringVar(value='Choisissez un numéro de test.')
        self.selection=tk.StringVar(value='')
        self._build()
        self.profile_changed()
        parent.after(250,self._drain)
        # The existing Test Runner 60-second timer owns automatic refresh.
        # Do NOT create a second SSH polling cadence here.

    def _build(self):
        """Primary end-to-end workflow: choose → run → confirm → download.

        No SSH or benchmark logic lives here; it is the existing trusted
        TestRunner and read-only remote inventory displayed in one place.
        """
        from rvvlab_studio_theme import COLORS
        self.colors=COLORS
        base=ttk.Frame(self.parent,style='App.TFrame')
        base.pack(fill='both',expand=True)
        title=ttk.Frame(base,style='App.TFrame')
        title.pack(fill='x',pady=(0,15))
        ttk.Label(title,text='Tests',style='Brand.TLabel').pack(side='left')
        ttk.Label(title,text='Choisir  →  Démarrer  →  Suivre  →  Télécharger',
                  style='Eyebrow.TLabel').pack(side='left',padx=(18,0),pady=(9,0))
        ttk.Label(title,text='Actualisation automatique : 60 s',style='Eyebrow.TLabel').pack(side='right',pady=(9,0))

        content=ttk.Frame(base,style='App.TFrame')
        content.pack(fill='both',expand=True)
        content.columnconfigure(0,weight=1,minsize=290)
        content.columnconfigure(1,weight=3,minsize=590)
        content.rowconfigure(0,weight=1)
        sidebar=ttk.Frame(content,style='Surface.TFrame',padding=16)
        sidebar.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        ttk.Label(sidebar,text='01  CHOISIR UN TEST',style='PanelCaption.TLabel').pack(anchor='w',pady=(0,8))
        ttk.Label(sidebar,text='Campagnes disponibles',style='CardTitle.TLabel').pack(anchor='w',pady=(0,10))
        cols=('test','machine','state')
        self.tree=ttk.Treeview(sidebar,columns=cols,show='headings',height=8,selectmode='browse')
        self.live_style=ttk.Style()
        self.tree.configure(style='RVVLiveSimple.Treeview')
        for key,title,width in [('test','N°',48),('machine','Machine',86),('state','Dernier état confirmé',275)]:
            self.tree.heading(key,text=title)
            self.tree.column(key,width=width,anchor='w',stretch=(key=='state'))
        self.tree.tag_configure('ok',background='#DFF5E8',foreground='#10613B')
        self.tree.tag_configure('fail',background='#FDE2E2',foreground='#9B1C1C')
        self.tree.tag_configure('active',background='#FFF0B3',foreground='#785000')
        self.tree.tag_configure('warning',background='#FFF0D5',foreground='#835000')
        self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda e:(self._selected(),self._highlight_selection()))
        self.test_descr=tk.StringVar(value='Sélectionne un test pour voir son protocole.')
        ttk.Label(sidebar,textvariable=self.test_descr,style='Muted.TLabel',wraplength=260,
                  justify='left').pack(anchor='w',fill='x',pady=(12,0))

        right=ttk.Frame(content,style='App.TFrame')
        right.grid(row=0,column=1,sticky='nsew')
        card=ttk.Frame(right,style='Surface.TFrame',padding=18)
        card.pack(fill='x',pady=(0,10))
        ttk.Label(card,text='02  ÉTAT DU TEST',style='PanelCaption.TLabel').pack(anchor='w')
        self.banner=tk.Frame(card,bg=COLORS['light_blue'],padx=14,pady=12)
        self.banner.pack(fill='x',pady=(10,9))
        self.banner_label=tk.Label(self.banner,textvariable=self.status,font=('Segoe UI',14,'bold'),
                                   bg=COLORS['light_blue'],fg=COLORS['ink'],anchor='w')
        self.banner_label.pack(anchor='w',fill='x')
        self.banner_subtitle=tk.StringVar(value='En attente d’une vérification sur le serveur.')
        self.banner_caption=tk.Label(self.banner,textvariable=self.banner_subtitle,
                    bg=COLORS['light_blue'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w')
        self.banner_caption.pack(anchor='w',pady=(4,0))
        ttk.Label(card,textvariable=self.details,style='Muted.TLabel',wraplength=690,
                  justify='left').pack(anchor='w',pady=(0,9))
        ttk.Label(card,text='03  ACTION SUIVANTE',style='PanelCaption.TLabel').pack(anchor='w',pady=(6,8))
        actions=ttk.Frame(card,style='Surface.TFrame')
        actions.pack(fill='x')
        self.run_button=ttk.Button(actions,text='▶  Démarrer',command=self.run,style='Accent.TButton')
        self.run_button.pack(side='left',padx=(0,7))
        self.refresh_button=ttk.Button(actions,text='↻  Actualiser',command=self.refresh)
        self.refresh_button.pack(side='left',padx=(0,7))
        self.download_button=ttk.Button(actions,text='↓  Télécharger',command=self.download,style='Success.TButton')
        self.download_button.pack(side='left',padx=(0,7))
        self.open_button=ttk.Button(actions,text='Ouvrir',command=self.open_results)
        self.open_button.pack(side='left')
        ttk.Label(card,textvariable=self.notice,style='Muted.TLabel',wraplength=710,
                  justify='left').pack(anchor='w',pady=(12,0))

        history=ttk.Frame(right,style='Surface.TFrame',padding=(18,12))
        history.pack(fill='both',expand=True)
        ttk.Label(history,text='04  EXÉCUTIONS ET RÉSULTATS',style='PanelCaption.TLabel').pack(anchor='w')
        row=ttk.Frame(history,style='Surface.TFrame')
        row.pack(fill='x',pady=(8,7))
        ttk.Label(row,text='Campagne sélectionnée',style='Muted.TLabel').pack(side='left',padx=(0,9))
        self.run_choice=ttk.Combobox(row,textvariable=self.selection,state='readonly',width=52)
        self.run_choice.pack(side='left',fill='x',expand=True)
        self.run_choice.bind('<<ComboboxSelected>>',lambda e:self._selected())
        self.history_tree=ttk.Treeview(history,columns=('run','state','rows','zip'),
                         show='headings',height=5,selectmode='browse')
        for key,label,width in [('run','ID de campagne',260),('state','État',145),('rows','Mesures',100),('zip','Archive',80)]:
            self.history_tree.heading(key,text=label)
            self.history_tree.column(key,width=width,anchor='w',stretch=(key=='run'))
        self.history_tree.tag_configure('active',background=COLORS['active_bg'],foreground=COLORS['active'])
        self.history_tree.tag_configure('ok',background=COLORS['ok_bg'],foreground=COLORS['ok'])
        self.history_tree.tag_configure('fail',background=COLORS['bad_bg'],foreground=COLORS['bad'])
        self.history_tree.pack(fill='both',expand=True)
        self.history_tree.bind('<<TreeviewSelect>>',self._choose_history)
        ttk.Label(history,text='Le statut « Terminé » exige une validation distante et une archive disponible. '
                     'Actualiser et Télécharger ne lancent aucun calcul.',style='Muted.TLabel',
                  wraplength=710,justify='left').pack(anchor='w',pady=(8,0))
        self._history_drawn=None

    def _choose_history(self, _event=None):
        selected=self.history_tree.selection()
        if not selected:return
        number=self._number()
        if not number:return
        chosen=selected[0]
        if any(r.get('id')==chosen for r in self.runs.get(number,[])):
            self.selection.set(chosen)
            self._selected()

    def _render_workspace(self):
        """Presentation only. Never guess completion from an old local PASS."""
        number=self._number()
        if not number:return
        profile=self.profile
        descriptions={
           ('Cloud-V','94'):'Comparaison machine · 1 heure',
           ('Cloud-V','95'):'Ablations packed et seuil A2 · 8 heures',
           ('Cloud-V','97'):'Seuils A2 de 4 à 10 Kio · 8 heures',
           ('Cloud-V','98'):'18 JSON publics immuables · A2 et officiel v5 · 1 heure',
           ('EPCC','94'):'Comparaison RISC-V sous Slurm · 1 heure',
           ('EPCC','96'):'Ablations A2 et seuil 4 Kio · 8 heures',
           ('EPCC','97'):'A2 versus simdjson officiel v5 · 3 heures',
           ('EPCC','98'):'18 JSON publics immuables · A2 et officiel v5 · 1 heure Slurm',
        }
        self.test_descr.set('Test '+number+'  /  '+profile+'\n'+
                            descriptions.get((profile,number),'Campagne historique')+
                            '\n\nLancement manuel uniquement. Contrôle anti-doublon avant Run.')
        row=self._row()
        active=bool((row and row['state'] in ACTIVE) or
               (number=='97' and profile=='Cloud-V' and self.remote_activity) or
               (self.launch_number==number and self.studio.test_runner.busy))
        failed=bool((row and row['state'] in ('failed','safety_stop','stopped')) or
                    ('Échec' in self.status.get()))
        done=bool(self.remote_checked and row and row['state']=='completed' and
                  row.get('packet') and row.get('validated'))
        if not self.studio.ssh.connected() or self.last_check_error or not self.remote_checked:
            palette=('unknown','#EDF1F6','#546477')
        elif done:palette=('done',self.colors['ok_bg'],self.colors['ok'])
        elif failed:palette=('failed',self.colors['bad_bg'],self.colors['bad'])
        elif active:palette=('active',self.colors['active_bg'],self.colors['active'])
        else:palette=('idle',self.colors['light_blue'],self.colors['ink'])
        kind,bg,fg=palette
        self.banner.configure(bg=bg)
        self.banner_label.configure(bg=bg,fg=fg)
        self.banner_caption.configure(bg=bg,fg=fg)
        if done:next_action='Résultats validés. Sélectionne la campagne puis clique Télécharger.'
        elif active:next_action='Campagne détectée. Ne relance pas Run ; vérification dans 60 secondes.'
        elif self.last_check_error:next_action='Connexion indisponible : dernier état non fiable. Reconnecter puis Actualiser.'
        elif not self.studio.ssh.connected():next_action='Connecte la machine choisie en haut de Studio.'
        elif not self.remote_checked:next_action='Clique Actualiser pour vérifier l’état du serveur.'
        elif failed:next_action='Échec confirmé. Consulte le journal avant une nouvelle tentative.'
        else:next_action='Aucun test actif confirmé pour cette sélection. Tu peux démarrer après contrôle.'
        if row and row.get('state') in ACTIVE:
            next_action += '  •  '+str(row.get('rows',0))+' mesures enregistrées.'
        self.banner_subtitle.set(next_action)
        # Show only runs for the selected test; never mistake an older completed
        # run for evidence that a newer active attempt has finished.
        rows=self.runs.get(number,[])
        signature=(profile,number,tuple((r['id'],r['state'],r.get('rows'),r.get('packet')) for r in rows))
        if signature!=self._history_drawn:
            self._history_drawn=signature
            self.history_tree.delete(*self.history_tree.get_children())
            for r in rows:
                state=str(r.get('state','unknown'))
                tags=('ok',) if state=='completed' and r.get('validated') and r.get('packet') else (
                     ('fail',) if state in ('failed','safety_stop') else ('active',) if state in ACTIVE else ())
                self.history_tree.insert('','end',iid=r['id'],values=(
                     r['id'], 'Terminé' if tags==('ok',) else state,
                     str(r.get('rows',0)), 'Prêt' if r.get('packet') else '—'),tags=tags)
        chosen=self.selection.get()
        if chosen and self.history_tree.exists(chosen):
            if self.history_tree.selection()!=(chosen,):
                self.history_tree.selection_set(chosen)

    def _highlight_selection(self):
        names=[str(t) for iid in self.tree.selection() if self.tree.exists(iid)
               for t in self.tree.item(iid,'tags')]
        if 'fail' in names:bg,fg='#F3B1B1','#781212'
        elif 'active' in names:bg,fg='#FFE082','#563D00'
        elif 'ok' in names:bg,fg='#B4E8C7','#0F5030'
        elif 'warning' in names:bg,fg='#FBE7B2','#674A00'
        else:bg,fg='#3470A4','#FFFFFF'
        self.live_style.map('RVVLiveSimple.Treeview',background=[('selected',bg)],foreground=[('selected',fg)])

    def _number(self):
        sel=self.tree.selection()
        return sel[0] if sel else None

    def _row(self):
        number=self._number()
        if not number:return None
        runs=self.runs.get(number,[])
        return next((r for r in runs if r['id']==self.selection.get()),runs[0] if runs else None)

    def profile_changed(self):
        """Always discard another target's verified status and run selection."""
        self.profile=self.studio.active_profile
        self.remote_checked=False;self.checked_at=None;self.runs={};self.remote_activity=[]
        self.launch_number=None;self.last_check_error=None
        runner=getattr(self.studio,'test_runner',None)
        if runner is not None and hasattr(runner,'clear_verified_campaigns'):
            runner.clear_verified_campaigns()
        unified=getattr(self.studio,'unified_campaigns',None)
        if unified is not None and hasattr(unified,'clear_verified_campaigns'):
            unified.clear_verified_campaigns()
        self.tree.delete(*self.tree.get_children())
        for number,allowed in PROFILES.items():
            if self.profile in allowed:
                self.tree.insert('','end',iid=number,values=(number,self.profile,'À vérifier'))
        children=self.tree.get_children()
        if children:self.tree.selection_set(children[-1])  # 97 Cloud-V, 96 EPCC
        self.selection.set('')
        self._selected()
        self.notice.set(self.profile+' — connectez SSH puis Actualiser. Les autres machines sont exclues.')

    def _selected(self):
        n=self._number()
        rows=self.runs.get(n,[]) if n else []
        choices=[r['id'] for r in rows]
        previous=self.selection.get()
        if tuple(map(str,self.run_choice['values'])) != tuple(choices):
            self.run_choice['values']=choices
        desired=previous if previous in choices else (choices[0] if choices else '')
        if previous != desired:self.selection.set(desired)
        row=self._row()
        local=_local_attempt(self.studio.vars['results'].get(),n,self.profile) if n else None
        active_here=bool(self.launch_number==n and self.studio.test_runner.busy)
        process_here=bool(n=='97' and self.profile=='Cloud-V' and self.remote_activity)
        if not self.studio.ssh.connected():
            self.status.set('○ Déconnecté — état distant non vérifié')
        elif self.poll_busy:
            self.status.set('◷ Vérification distante en cours…')
        elif self.last_check_error:
            self.status.set('⚠ Impossible de vérifier le serveur')
        elif row:self.status.set(_label(row))
        elif process_here:self.status.set('● Test 97 : processus actif sur Cloud-V')
        elif active_here:self.status.set('◷ Test '+n+' : préparation/transfert local en cours')
        elif self.remote_checked:self.status.set(_describe_local(local,False))
        else:self.status.set('○ Cliquez sur Actualiser état')
        if row:
            self.details.set(f"{row['id']}  ·  {row.get('rows',0)} mesures  ·  ZIP distant: " +
                ('oui' if row.get('packet') else 'non') + '  ·  '+row.get('proof',''))
        elif process_here:
            self.details.set('Processus Cloud-V : '+', '.join(str(p['pid']) for p in self.remote_activity) +
                '. Préparation ou benchmark en cours. Ne relancez pas Run.')
        elif active_here:
            self.details.set('Studio exécute encore le lanceur du test '+n+'. Le dossier distant peut apparaître après le transfert des sources.')
        elif self.remote_checked:
            if local:
                self.details.set('Dernier essai local : '+local['detail']+'  |  Journal : '+local['path'])
            else:self.details.set('Aucun processus Test97 et aucun dossier de campagne repéré sur Cloud-V (vérification terminée).' if n=='97' else
                                  'Aucune campagne trouvée sur '+self.profile+'.')
        else:self.details.set('État à vérifier. Actualiser ne lance jamais de benchmark.')
        can_download=bool(self.studio.ssh.connected() and self.remote_checked and row and
                          row['state']=='completed' and row.get('packet') and row.get('validated'))
        self.download_button.configure(state='normal' if can_download and not self.busy else 'disabled')
        run_blocked=(not self.studio.ssh.connected() or self.busy or self.poll_busy or self.studio.test_runner.busy or
                     self.last_check_error is not None or process_here or
                     (row is not None and row['state'] in ACTIVE))
        # A different test running on the same machine also blocks Run.
        other_active=any(r.get('state') in ACTIVE or r.get('state')=='unconfirmed'
                         for runs in self.runs.values() for r in runs)
        if self.remote_checked and other_active:run_blocked=True
        # Test98's manifest deliberately reuses an existing run instead of
        # starting another. Make that rule obvious in the primary workflow.
        if n=='98' and row is not None:run_blocked=True
        self.run_button.configure(state='disabled' if run_blocked else 'normal')
        self._render_workspace()

    def refresh(self):
        if self.poll_busy or self.busy:return
        if self.profile!=self.studio.active_profile:self.profile_changed()
        if not self.studio.ssh.connected():
            self.remote_checked=False;self._selected()
            self.notice.set('SSH déconnecté : reconnectez la machine choisie.');return
        self.poll_busy=True;profile=self.studio.active_profile
        self.last_check_error=None
        self._selected()
        self.notice.set('Vérification du serveur '+profile+' (lecture seule)…')
        remote_name=self.studio.vars['remote_name'].get().strip()
        def work():
            try:
                data={num:_server_runs(self.studio.ssh,remote_name,num,profile)
                      for num in PROFILES if profile in PROFILES[num]}
                processes=_remote_test97_processes(self.studio.ssh) if profile=='Cloud-V' else []
                self.events.put(('status',(profile,data,processes,None)))
            except Exception as ex:self.events.put(('status',(profile,None,None,str(ex))))
        threading.Thread(target=work,daemon=True).start()

    def _periodic(self):
        """Compatibility shim. The sole 60-second Test Runner clock owns polling."""
        return

    def run(self):
        """One click: verify remote state first, then ask launch confirmation."""
        number=self._number()
        if not number:return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connectez la machine sélectionnée avant Run.');return
        if (self.busy or self.poll_busy or self.studio.test_runner.busy):
            self.notice.set('Une opération de lancement ou de vérification est en cours. Run refusé pour éviter un doublon.')
            return
        self.busy=True;self._selected()
        self.notice.set('Run Test '+number+' : vérification anti-doublon sur le serveur…')
        profile=self.profile
        remote_name=self.studio.vars['remote_name'].get().strip()
        def work():
            try:
                # Checking ALL supported tests also catches overlapping 94/95/96/97.
                data={n:_server_runs(self.studio.ssh,remote_name,n,profile)
                      for n in PROFILES if profile in PROFILES[n]}
                processes=_remote_test97_processes(self.studio.ssh) if profile=='Cloud-V' else []
                if processes:
                    raise RuntimeError('Processus Cloud-V Test97 encore actif : '+
                                       ','.join(str(p['pid']) for p in processes)+'. Lancement refusé.')
                nodes=None
                if number=='94' and profile=='EPCC' and not self.studio.test_runner.epcc_nodes:
                    text=self.studio.ssh.exec_text('sinfo -h -N -o "%N|%P|%T|%f"')
                    nodes={}
                    for line in text.splitlines():
                        parts=line.split('|')
                        if len(parts)!=4 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}',parts[0]):continue
                        node,partition,state,features=parts
                        nodes[node]={'partition':partition.rstrip('*'),'state':state,'features':features}
                    if not nodes:raise RuntimeError('Aucun noeud Slurm détecté sur EPCC')
                self.events.put(('preflight',(profile,number,data,nodes,None)))
            except Exception as ex:self.events.put(('preflight',(profile,number,None,None,str(ex))))
        threading.Thread(target=work,daemon=True).start()

    def _launch_after_preflight(self,number,data):
        self.busy=False
        self.runs=data;self.remote_checked=True;self.checked_at=time.monotonic()
        if any(r['state'] in ACTIVE or r['state'] in ('preparing','unconfirmed') for rows in data.values() for r in rows):
            self.notice.set('Un test 94/95/96/97/98 est déjà actif sur cette machine. Nouveau lancement refusé.')
            messagebox.showwarning('Campagne active','Une campagne est en cours ou en préparation sur '+self.profile+'. Aucun doublon lancé.')
            self._selected();return
        item=next((x for x in self.studio.test_runner.items if x['id']==test_id(number,self.profile)),None)
        if not item or not item['enabled']:
            messagebox.showerror('Test indisponible','Manifeste du Test '+number+' absent/désactivé. Vérifiez son installation.')
            self._selected();return
        # Existing TestRunner owns launches, script SHA pinning and histories.
        if number=='94':
            self.studio.test_runner._run_test94_after_remote_check()
        elif number=='98' and self.runs.get('98'):
            self.notice.set('Test 98 existe déjà sur '+self.profile+'. Sélectionne la campagne pour Télécharger ; aucun nouveau job soumis.')
            messagebox.showinfo('Test 98 déjà présent','Une campagne 98 existe sur '+self.profile+'. Utilise Actualiser / Télécharger. Aucun nouveau job démarré.')
        elif self.studio.test_runner._approval([item]):
            self.launch_number=number
            self.studio.test_runner._run([item])
            self.notice.set('Test '+number+' : préparation locale demandée. Le serveur n’a PAS encore confirmé le lancement.')
            self.parent.after(3000,self.refresh)
        self._selected()

    def _packet_dir(self,number,runid):
        base=Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/test_id(number,self.profile)
        if number=='98' and self.profile=='Cloud-V':
            return base/('Cloud-V-'+runid)
        return base/(('EPCC-' if self.profile=='EPCC' and number in ('94','96','97','98') else 'simple-')+runid)

    def download(self):
        row=self._row();number=self._number()
        if not row or not number or self.busy or not self.studio.ssh.connected():return
        if not (self.remote_checked and row['state']=='completed' and row['packet'] and row.get('validated')):
            messagebox.showinfo('Pas encore terminé','Cliquez Actualiser état. Download sera activé à la fin validée.');return
        target=self._packet_dir(number,row['id'])
        self.busy=True;self._selected()
        self.notice.set('Téléchargement SHA-256 depuis '+self.profile+'…')
        profile=self.profile
        remote_name=self.studio.vars['remote_name'].get().strip()
        run=dict(row)
        def work():
            try:
                # Recheck the SAME remote run before copying, not the newest run.
                found=_server_runs(self.studio.ssh,remote_name,number,profile)
                match=next((r for r in found if r['id']==run['id']),None)
                if not match or match['state']!='completed' or not match.get('packet') or not match.get('validated'):
                    raise RuntimeError('La campagne choisie n’est plus confirmée comme terminée.')
                if profile=='EPCC' and number in ('94','96','97','98'):
                    from rvvlab_epcc_results import sync_epcc_run
                    folder=sync_epcc_run(self.studio.ssh,remote_name,run['id'],
                                         self.studio.vars['results'].get())
                    packet=folder/ZIP_NAME[number]
                else:
                    target.mkdir(parents=True,exist_ok=True)
                    ctx=TestContext(self.studio,target,lambda x:self.events.put(('note',str(x))),
                                    threading.Event(),{'id':test_id(number,profile)})
                    ctx.ensure_connected()
                    file={'94':'94_machine_1h.py','95':'95_cloudv_8h.py','96':'96_epcc_8h.py','97':'97_cloudv_8h.py','98':'98_real_corpus.py'}[number]
                    path=SCRIPTS_DIR/file
                    if not path.is_file():raise RuntimeError('Script de récupération absent : '+str(path))
                    spec=importlib.util.spec_from_file_location('rvvlab_simple_recovery_'+number,path)
                    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                    if number=='94':
                        output=mod.recover(ctx,{'mode':profile,'id':run['id'],'workdir':run['path']})
                        packet=output.get('packet')
                    elif number in ('95','97'):packet=mod.grab(ctx,run['path'])
                    elif number=='98':packet=mod.verified_archive(ctx,{'id':run['id'],'workdir':run['path']},'Cloud-V')
                    else:packet=mod.download(ctx,run['path'])
                if not packet:raise RuntimeError('Aucune archive ZIP récupérée.')
                self.events.put(('download',(profile,number,run['id'],str(packet),None)))
            except Exception as ex:self.events.put(('download',(profile,number,run['id'],None,str(ex))))
        threading.Thread(target=work,daemon=True).start()

    def open_results(self):
        number=self._number();row=self._row()
        if not number:return
        dest=self._packet_dir(number,row['id']) if row else Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/test_id(number,self.profile)
        if not dest.is_dir():
            messagebox.showinfo('Résultats','Aucun téléchargement local pour cette campagne.');return
        if os.name=='nt':os.startfile(str(dest))
        else:messagebox.showinfo('Résultats locaux',str(dest))

    def _drain(self):
        try:
            while True:
                try:kind,payload=self.events.get_nowait()
                except queue.Empty:break
                if kind=='status':
                    profile,data,processes,error=payload
                    self.poll_busy=False
                    if profile!=self.studio.active_profile:continue
                    if error:
                        self.remote_checked=False;self.last_check_error=error
                        self.notice.set('Vérification serveur échouée : '+error[:320]+'. Aucun état négatif conclu.')
                        runner=getattr(self.studio,'test_runner',None)
                        if runner is not None and hasattr(runner,'mark_verification_unavailable'):
                            runner.mark_verification_unavailable(profile,error)
                    else:
                        self.runs=data;self.remote_checked=True;self.checked_at=time.monotonic()
                        self.remote_activity=processes or [];self.last_check_error=None
                        if profile=='Cloud-V' and self.remote_activity:
                            for r in data.get('97',[]):
                                if r['state']=='unconfirmed':
                                    r['state']='building';r['proof']='Processus distant /proc confirmé'
                        for n in self.tree.get_children():
                            rows=data.get(n,[]);row=rows[0] if rows else None
                            local=_local_attempt(self.studio.vars['results'].get(),n,profile)
                            if row:label=_label(row)
                            elif n=='97' and profile=='Cloud-V' and self.remote_activity:label='🟡 Processus distant actif'
                            elif self.launch_number==n and self.studio.test_runner.busy:label='◷ Préparation locale en cours'
                            else:label=_describe_local(local,False)
                            self.tree.set(n,'state',label)
                            self.tree.item(n,tags=('ok' if row and row['state']=='completed' and row.get('validated') and row.get('packet') else
                                'fail' if row and row['state'] in ('failed','safety_stop') else
                                'warning' if label.startswith(('⚠','✕')) else
                                'active' if (row and row['state'] in ACTIVE) or
                                             (n=='97' and profile=='Cloud-V' and self.remote_activity) or
                                             (n==self.launch_number and self.studio.test_runner.busy)
                                    else '',))
                        # The same remote snapshot feeds the script list and campaigns list.
                        # It must never convert a local launcher PASS into a green completion.
                        runner=getattr(self.studio,'test_runner',None)
                        if runner is not None and hasattr(runner,'apply_verified_campaigns'):
                            runner.apply_verified_campaigns(profile,data,self.remote_activity)
                        unified=getattr(self.studio,'unified_campaigns',None)
                        if unified is not None and hasattr(unified,'apply_verified_campaigns'):
                            unified.apply_verified_campaigns(profile,data,self.remote_activity)
                            # Second, sequential read: specialized historic/NightRuns
                            # inventory. Same 60-second scheduler, no extra timer.
                            if not unified.poll_busy and not unified.busy:
                                unified.refresh_remote()
                        t=dt.datetime.now().astimezone().strftime('%H:%M:%S')
                        self.notice.set(('Cloud-V vérifié à '+t+' : processus, campagnes distantes et dernier journal Studio consultés.') if profile=='Cloud-V' else
                                        'État EPCC et journaux Studio vérifiés à '+t+'.')
                    self._selected()
                    self._highlight_selection()
                elif kind=='preflight':
                    profile,number,data,nodes,error=payload
                    self.busy=False
                    if profile!=self.studio.active_profile:continue
                    if nodes:
                        runner=self.studio.test_runner
                        runner.epcc_nodes=nodes
                        available=[n for n,v in nodes.items()
                                   if v['partition'].lower().startswith('riscv') and
                                   not v['state'].lower().startswith(('down','drain','fail','maint','unk'))]
                        if not available:
                            self.notice.set('Aucun nœud RISC-V Slurm disponible; Test94 refusé.')
                            messagebox.showerror('Slurm EPCC','Aucun nœud RISC-V Slurm disponible.')
                            self._selected()
                            continue
                        runner.epcc_node.set('rvc02' if 'rvc02' in available else sorted(available)[0])
                    if error:
                        self.notice.set('Run refusé : impossible de vérifier les campagnes : '+error[:250])
                        messagebox.showerror('Contrôle serveur impossible',error[:400])
                        self._selected()
                    else:self._launch_after_preflight(number,data)
                elif kind=='download':
                    profile,number,runid,path,error=payload
                    self.busy=False
                    if profile==self.studio.active_profile:
                        if error:self.notice.set('Download impossible : '+error)
                        else:
                            self.notice.set('Archive SHA-256 vérifiée : '+path)
                            messagebox.showinfo('Téléchargement terminé','Test '+number+' : archive disponible sur ton PC.\n\n'+path)
                    self._selected()
                elif kind=='note':self.notice.set(payload[:240])
        except tk.TclError:return
        self.parent.after(250,self._drain)
