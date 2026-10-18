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
from rvvlab_elapsed import elapsed_display

PROFILES = {'94': ('Cloud-V', 'EPCC'), '95': ('Cloud-V',), '96': ('EPCC',), '97': ('Cloud-V', 'EPCC'), '98': ('Cloud-V','EPCC'), '99': ('Cloud-V','EPCC'), '100': ('Cloud-V','EPCC'), '101': ('Cloud-V','EPCC'), '102': ('Cloud-V','EPCC'), '103': ('Cloud-V','EPCC'), '104': ('Cloud-V','EPCC')}
TEST_IDS = {'94': 'machine-compare-94-1h', '95': 'test95-cloudv-8h',
            '96': 'test96-epcc-8h', '97': 'test97-cloudv-8h',
            '97-epcc': 'test97-epcc-v5-3h', '98': 'test98-real-corpus', '99': 'test99-public-8h', '100': 'test100-adaptive-public', '101': 'test101-dispatch-validation', '102': 'test102-escape-stage', '103': 'test103-stage2-optimization','104':'test104-independent-public-validation'}


def test_id(number, profile):
    """Map a number and target to its unique manifest; never swap Test97 targets."""
    if number not in PROFILES or profile not in PROFILES[number]:
        raise ValueError('Test ' + str(number) + ' incompatible avec ' + str(profile))
    return TEST_IDS['97-epcc'] if number == '97' and profile == 'EPCC' else TEST_IDS[number]


def manifest_target(manifest_id):
    """Return the test number and target restriction of a managed manifest."""
    if manifest_id == TEST_IDS['97-epcc']:
        return '97', ('EPCC',)
    for number in ('94', '95', '96', '97', '98', '99', '100','101','102','103','104'):
        if manifest_id == TEST_IDS[number]:
            allowed = ('Cloud-V',) if number == '97' else PROFILES[number]
            return number, allowed
    return None

RUN_PATTERN = {
    '95': re.compile(r'^test95-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '96': re.compile(r'^test96-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '97': re.compile(r'^test97-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '98': re.compile(r'^test98-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '99': re.compile(r'^test99-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '100': re.compile(r'^test100-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '101': re.compile(r'^test101-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '102': re.compile(r'^test102-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '103': re.compile(r'^test103-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
    '104': re.compile(r'^test104-\d{8}T\d{6}Z-[0-9a-f]{6}$'),
}
RUN_ROOT = {'95': 'test95-runs', '96': 'test96-epcc-runs', '97': 'test97-runs', '98': 'test98-cloudv-runs', '99':'test99-cloudv-runs', '100':'test100-cloudv-runs', '101':'test101-cloudv-runs','102':'test102-cloudv-runs','103':'test103-cloudv-runs','104':'test104-cloudv-runs'}
ZIP_NAME = {'94': 'test94_results.zip', '95': 'test95_results.zip', '96': 'test96_results.zip', '97': 'test97_results.zip', '98':'test98_results.zip', '99':'test99_results.zip', '100':'test100_results.zip', '101':'test101_results.zip','102':'test102_results.zip','103':'test103_results.zip','104':'test104_results.zip'}
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
    if profile == 'EPCC' and number in ('94', '96', '97','98','99','100','101','102','103','104'):
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
                                 proof=info.get('proof','EPCC server'),
                                 started_utc=status.get('start_utc') or status.get('started_utc') or info.get('started_utc'),
                                 updated_utc=status.get('updated_utc') or status.get('last_update_utc') or info.get('last_update')))
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
                     validated=valid,proof=info.get('proof',''),
                     started_utc=info.get('started_utc') or info.get('start_utc'),
                     updated_utc=info.get('updated_utc') or info.get('last_update'))]
    if profile not in PROFILES[number]:
        raise ValueError('This test does not match the selected machine.')
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
            if number in ('98','99','100','101','102','103','104'):
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
                             validated=valid, proof='Server queried',
                             started_utc=status.get('start_utc') or status.get('started_utc'),
                             updated_utc=status.get('updated_utc') or status.get('last_update_utc'),
                             ended_utc=status.get('end_utc') or status.get('finished_utc')))
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
    if not isinstance(result,list):raise RuntimeError('Unexpected /proc response')
    return result


def _describe_local(local, runner_busy):
    if runner_busy:return '◷ Studio is preparing/uploading the test (not yet confirmed on the server)'
    if not local:return '— No remote launch detected (no identifiable local attempt)'
    if local['state']=='failed_local':return '✕ Local launch failed — no remote run confirmed'
    if local['state']=='started_local':return '⚠ Local attempt detected — no confirmed remote run'
    return '— No confirmed remote run (see last Studio attempt)'

def _label(row):
    if not row:return '— No launch found'
    return {
        'completed':'✓ Completed — ZIP ready', 'failed':'✕ Failed',
        'safety_stop':'✕ Safety stop', 'stopped':'Stopped',
        'running':'● Running', 'queued':'◷ Pending in Slurm',
        'pending':'◷ Pending', 'preparing':'◷ Preparing / compiling',
        'building':'◷ Compiling', 'build':'◷ Compiling',
        'incomplete':'⚠ Incomplete result', 'unknown':'? Status unconfirmed',
        'unconfirmed':'⚠ Remote directory exists — launch unconfirmed',
        'preparing':'◷ Preparing / compiling',
    }.get(row['state'], '◷ ' + row['state'])


class SimpleTestsPanel:
    """Three actions: Run, verify server status, download verified ZIP."""
    def __init__(self, parent, studio):
        self.parent=parent;self.studio=studio
        self.events=queue.Queue();self.busy=False;self.poll_busy=False
        self.runs={};self.remote_checked=False;self.checked_at=None
        self.remote_activity=[];self.launch_number=None;self.last_check_error=None
        self.profile=studio.active_profile
        self.notice=tk.StringVar(value='Connect SSH, then click Refresh.')
        self.status=tk.StringVar(value='—')
        self.details=tk.StringVar(value='Choose a test number.')
        self.elapsed=tk.StringVar(value='Elapsed: —')
        self.selection=tk.StringVar(value='')
        self._build()
        self.profile_changed()
        parent.after(250,self._drain)
        # Display-only one-second clock; remote status remains on the existing 60s poll.
        parent.after(1000,self._tick_elapsed)
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
        ttk.Label(title,text='Choose  →  Run  →  Monitor  →  Download',
                  style='Eyebrow.TLabel').pack(side='left',padx=(18,0),pady=(9,0))
        ttk.Label(title,text='Auto refresh: 60 s',style='Eyebrow.TLabel').pack(side='right',pady=(9,0))

        content=ttk.Frame(base,style='App.TFrame')
        content.pack(fill='both',expand=True)
        content.columnconfigure(0,weight=1,minsize=290)
        content.columnconfigure(1,weight=3,minsize=590)
        content.rowconfigure(0,weight=1)
        sidebar=ttk.Frame(content,style='Surface.TFrame',padding=16)
        sidebar.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        ttk.Label(sidebar,text='01  CHOOSE A TEST',style='PanelCaption.TLabel').pack(anchor='w',pady=(0,8))
        ttk.Label(sidebar,text='Available campaigns',style='CardTitle.TLabel').pack(anchor='w',pady=(0,10))
        cols=('test','machine','state')
        self.tree=ttk.Treeview(sidebar,columns=cols,show='headings',height=8,selectmode='browse')
        self.live_style=ttk.Style()
        self.tree.configure(style='RVVLiveSimple.Treeview')
        for key,title,width in [('test','N°',48),('machine','Machine',86),('state','Latest confirmed status',275)]:
            self.tree.heading(key,text=title)
            self.tree.column(key,width=width,anchor='w',stretch=(key=='state'))
        self.tree.tag_configure('ok',background='#DFF5E8',foreground='#10613B')
        self.tree.tag_configure('fail',background='#FDE2E2',foreground='#9B1C1C')
        self.tree.tag_configure('active',background='#FFF0B3',foreground='#785000')
        self.tree.tag_configure('warning',background='#FFF0D5',foreground='#835000')
        self.tree.pack(fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda e:(self._selected(),self._highlight_selection()))
        self.test_descr=tk.StringVar(value='Select a test pour voir son protocole.')
        ttk.Label(sidebar,textvariable=self.test_descr,style='Muted.TLabel',wraplength=260,
                  justify='left').pack(anchor='w',fill='x',pady=(12,0))

        right=ttk.Frame(content,style='App.TFrame')
        right.grid(row=0,column=1,sticky='nsew')
        card=ttk.Frame(right,style='Surface.TFrame',padding=18)
        card.pack(fill='x',pady=(0,10))
        ttk.Label(card,text='02  TEST STATUS',style='PanelCaption.TLabel').pack(anchor='w')
        self.banner=tk.Frame(card,bg=COLORS['light_blue'],padx=14,pady=12)
        self.banner.pack(fill='x',pady=(10,9))
        self.banner_label=tk.Label(self.banner,textvariable=self.status,font=('Segoe UI',14,'bold'),
                                   bg=COLORS['light_blue'],fg=COLORS['ink'],anchor='w')
        self.banner_label.pack(anchor='w',fill='x')
        self.banner_subtitle=tk.StringVar(value='Waiting for a server check.')
        self.banner_caption=tk.Label(self.banner,textvariable=self.banner_subtitle,
                    bg=COLORS['light_blue'],fg=COLORS['muted'],font=('Segoe UI',9),anchor='w')
        self.banner_caption.pack(anchor='w',pady=(4,0))
        ttk.Label(card,textvariable=self.elapsed,style='CardTitle.TLabel').pack(anchor='w',pady=(0,6))
        ttk.Label(card,textvariable=self.details,style='Muted.TLabel',wraplength=690,
                  justify='left').pack(anchor='w',pady=(0,9))
        ttk.Label(card,text='03  NEXT ACTION',style='PanelCaption.TLabel').pack(anchor='w',pady=(6,8))
        actions=ttk.Frame(card,style='Surface.TFrame')
        actions.pack(fill='x')
        self.run_button=ttk.Button(actions,text='▶  Run',command=self.run,style='Accent.TButton')
        self.run_button.pack(side='left',padx=(0,7))
        self.refresh_button=ttk.Button(actions,text='↻  Refresh',command=self.refresh)
        self.refresh_button.pack(side='left',padx=(0,7))
        self.download_button=ttk.Button(actions,text='↓  Download',command=self.download,style='Success.TButton')
        self.download_button.pack(side='left',padx=(0,7))
        self.open_button=ttk.Button(actions,text='Open',command=self.open_results)
        self.open_button.pack(side='left')
        ttk.Label(card,textvariable=self.notice,style='Muted.TLabel',wraplength=710,
                  justify='left').pack(anchor='w',pady=(12,0))

        history=ttk.Frame(right,style='Surface.TFrame',padding=(18,12))
        history.pack(fill='both',expand=True)
        ttk.Label(history,text='04  RUNS AND RESULTS',style='PanelCaption.TLabel').pack(anchor='w')
        row=ttk.Frame(history,style='Surface.TFrame')
        row.pack(fill='x',pady=(8,7))
        ttk.Label(row,text='Campagne selected',style='Muted.TLabel').pack(side='left',padx=(0,9))
        self.run_choice=ttk.Combobox(row,textvariable=self.selection,state='readonly',width=52)
        self.run_choice.pack(side='left',fill='x',expand=True)
        self.run_choice.bind('<<ComboboxSelected>>',lambda e:self._selected())
        self.history_tree=ttk.Treeview(history,columns=('run','state','elapsed','rows','zip'),
                         show='headings',height=5,selectmode='browse')
        for key,label,width in [('run','Run ID',220),('state','Status',108),('elapsed','Elapsed',146),('rows','Measurements',100),('zip','Archive',75)]:
            self.history_tree.heading(key,text=label)
            self.history_tree.column(key,width=width,anchor='w',stretch=(key=='run'))
        self.history_tree.tag_configure('active',background=COLORS['active_bg'],foreground=COLORS['active'])
        self.history_tree.tag_configure('ok',background=COLORS['ok_bg'],foreground=COLORS['ok'])
        self.history_tree.tag_configure('fail',background=COLORS['bad_bg'],foreground=COLORS['bad'])
        self.history_tree.pack(fill='both',expand=True)
        self.history_tree.bind('<<TreeviewSelect>>',self._choose_history)
        ttk.Label(history,text='A completed status requires remote validation and an available archive. '
                     'Refresh and Download do not start new computations.',style='Muted.TLabel',
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
           ('Cloud-V','94'):'Machine comparison · 1 hour',
           ('Cloud-V','95'):'Packed ablations and A2 threshold · 8 hours',
           ('Cloud-V','97'):'A2 thresholds 4–10 KiB · 8 hours',
           ('Cloud-V','98'):'18 pinned public JSON files · A2 vs official v5 · 1 hour',
           ('Cloud-V','99'):'18 public JSON files · A2 4/6/8 KiB vs official · 8 hours',
           ('EPCC','94'):'RISC-V comparison via Slurm · 1 hour',
           ('EPCC','96'):'A2 ablations and 4 KiB threshold · 8 hours',
           ('EPCC','97'):'A2 vs official simdjson v5 · 3 hours',
           ('EPCC','98'):'18 pinned public JSON files · A2 vs official v5 · 1 hour via Slurm',
           ('EPCC','99'):'18 public JSON files · A2 4/6/8 KiB vs official · 8h via Slurm',
           ('Cloud-V','102'):'Escape density / internal Stage1 + Stage2 / overnight · 6h30 cap',
           ('Cloud-V','103'):'Stage2 escape optimizations / paired RVV variants · overnight',
           ('EPCC','103'):'Stage2 escape optimizations / paired RVV variants via Slurm',
           ('Cloud-V','104'):'Independent public JSON + JSONTestSuite · verified performance / conformance',
           ('EPCC','104'):'Independent external JSON validation + Stage2 variants via Slurm',
           ('EPCC','102'):'Escape density / Stage1 + Stage2 via Slurm · overnight',
           ('Cloud-V','101'):'A2 threshold confirmation · public + derived + boundaries · 6h cap',
           ('EPCC','101'):'A2 threshold confirmation via Slurm · public + derived + boundaries',
           ('Cloud-V','100'):'Adaptive performance · official vs A2 4/7/8/10KiB · public + separate boundary stratum',
           ('EPCC','100'):'Adaptive performance via Slurm · public + boundaries · 45m min / 4h max',
        }
        self.test_descr.set('Test '+number+'  /  '+profile+'\n'+
                            descriptions.get((profile,number),'Historical campaign')+
                            '\n\nManual launch only. Duplicate-run check before Run.')
        row=self._row()
        active=bool((row and row['state'] in ACTIVE) or
               (number=='97' and profile=='Cloud-V' and self.remote_activity) or
               (self.launch_number==number and self.studio.test_runner.busy))
        failed=bool((row and row['state'] in ('failed','safety_stop','stopped')) or
                    ('Failed' in self.status.get()))
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
        if done:next_action='Results verified. Select the run and click Download.'
        elif active:next_action='Active run detected. Do not launch another; next check in 60 seconds.'
        elif self.last_check_error:next_action='Connection unavailable; last status is not reliable. Reconnect, then Refresh.'
        elif not self.studio.ssh.connected():next_action='Connect to the selected machine at the top of Studio.'
        elif not self.remote_checked:next_action='Click Refresh to verify the server status.'
        elif failed:next_action='Confirmed failure. Review the log before retrying.'
        else:next_action='No active run confirmed for this test. You can Run after verification.'
        if row and row.get('state') in ACTIVE:
            next_action += '  •  '+str(row.get('rows',0))+' measurements recorded.'
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
                     r['id'], 'Completed' if tags==('ok',) else state,
                     elapsed_display(r)[0], str(r.get('rows',0)),
                     'Ready' if r.get('packet') else '—'),tags=tags)
        chosen=self.selection.get()
        if chosen and self.history_tree.exists(chosen):
            if self.history_tree.selection()!=(chosen,):
                self.history_tree.selection_set(chosen)

    def _update_elapsed(self):
        """Render duration locally; does not probe SSH or infer liveness."""
        row=self._row()
        elapsed,source=elapsed_display(row)
        self.elapsed.set('Elapsed: '+elapsed+'  ·  '+source if row else 'Elapsed: —')
        for number, rows in self.runs.items():
            if not isinstance(rows,list):
                continue
            for run in rows:
                rid=run.get('id')
                if rid and self.history_tree.exists(rid):
                    self.history_tree.set(rid,'elapsed',elapsed_display(run)[0])

    def _tick_elapsed(self):
        try:
            if not self.parent.winfo_exists():
                return
            self._update_elapsed()
            self.parent.after(1000,self._tick_elapsed)
        except tk.TclError:
            return

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
                self.tree.insert('','end',iid=number,values=(number,self.profile,'Needs verification'))
        children=self.tree.get_children()
        if children:self.tree.selection_set(children[-1])  # 97 Cloud-V, 96 EPCC
        self.selection.set('')
        self._selected()
        self.notice.set(self.profile+' — connect via SSH, then Refresh. Other machines are excluded.')

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
            self.status.set('○ Disconnected — remote status unverified')
        elif self.poll_busy:
            self.status.set('◷ Checking remote server…')
        elif self.last_check_error:
            self.status.set('⚠ Unable to check server')
        elif row:self.status.set(_label(row))
        elif process_here:self.status.set('● Test 97: active Cloud-V process')
        elif active_here:self.status.set('◷ Test '+n+' : preparing / uploading locally')
        elif self.remote_checked:self.status.set(_describe_local(local,False))
        else:self.status.set('○ Click Refresh to check status')
        if row:
            self.details.set(f"{row['id']}  ·  {row.get('rows',0)} measurements  ·  Remote ZIP: " +
                ('yes' if row.get('packet') else 'no') + '  ·  '+row.get('proof',''))
        elif process_here:
            self.details.set('Cloud-V process: '+', '.join(str(p['pid']) for p in self.remote_activity) +
                '. Preparation or benchmark in progress. Do not run again.')
        elif active_here:
            self.details.set('Studio is still executing test launcher '+n+'. Remote directory may appear after source upload.')
        elif self.remote_checked:
            if local:
                self.details.set('Last local attempt: '+local['detail']+'  |  Log: '+local['path'])
            else:self.details.set('No Test 97 process or run directory detected on Cloud-V (check completed).' if n=='97' else
                                  'No run found on '+self.profile+'.')
        else:self.details.set('Status unconfirmed. Refresh never starts a benchmark.')
        can_download=bool(self.studio.ssh.connected() and self.remote_checked and row and
                          (row['state']=='completed' and row.get('validated') or n in ('100','101','102','103','104') and row['state'] in ('failed','stopped')) and row.get('packet'))
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
        if n in ('98','99') and row is not None:run_blocked=True
        self.run_button.configure(state='disabled' if run_blocked else 'normal')
        self._render_workspace()
        self._update_elapsed()

    def refresh(self):
        if self.poll_busy or self.busy:return
        if self.profile!=self.studio.active_profile:self.profile_changed()
        if not self.studio.ssh.connected():
            self.remote_checked=False;self._selected()
            self.notice.set('SSH disconnected: reconnect to the selected machine.');return
        self.poll_busy=True;profile=self.studio.active_profile
        self.last_check_error=None
        self._selected()
        self.notice.set('Checking server '+profile+' (read-only)…')
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
            messagebox.showwarning('SSH','Connect the selected machine before Run.');return
        if (self.busy or self.poll_busy or self.studio.test_runner.busy or
            getattr(getattr(self.studio,'corpus_library',None),'busy',False)):
            self.notice.set('A launch or status check is already in progress. Run blocked to prevent duplicates.')
            return
        self.busy=True;self._selected()
        self.notice.set('Run Test '+number+' : checking server for existing runs…')
        profile=self.profile
        remote_name=self.studio.vars['remote_name'].get().strip()
        def work():
            try:
                # Checking ALL supported tests also catches overlapping 94–99.
                data={n:_server_runs(self.studio.ssh,remote_name,n,profile)
                      for n in PROFILES if profile in PROFILES[n]}
                processes=_remote_test97_processes(self.studio.ssh) if profile=='Cloud-V' else []
                if processes:
                    raise RuntimeError('Processus Cloud-V Test97 encore actif : '+
                                       ','.join(str(p['pid']) for p in processes)+'. New launch blocked.')
                nodes=None
                if number=='94' and profile=='EPCC' and not self.studio.test_runner.epcc_nodes:
                    text=self.studio.ssh.exec_text('sinfo -h -N -o "%N|%P|%T|%f"')
                    nodes={}
                    for line in text.splitlines():
                        parts=line.split('|')
                        if len(parts)!=4 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}',parts[0]):continue
                        node,partition,state,features=parts
                        nodes[node]={'partition':partition.rstrip('*'),'state':state,'features':features}
                    if not nodes:raise RuntimeError('No Slurm nodes detected on EPCC')
                self.events.put(('preflight',(profile,number,data,nodes,None)))
            except Exception as ex:self.events.put(('preflight',(profile,number,None,None,str(ex))))
        threading.Thread(target=work,daemon=True).start()

    def _launch_after_preflight(self,number,data):
        self.busy=False
        self.runs=data;self.remote_checked=True;self.checked_at=time.monotonic()
        if any(r['state'] in ACTIVE or r['state'] in ('preparing','unconfirmed') for rows in data.values() for r in rows):
            self.notice.set('A Test 94/95/96/97/98/99 run is already active on this machine. Duplicate launch blocked.')
            messagebox.showwarning('Active run','A run is active or preparing on '+self.profile+'. No duplicate launched.')
            self._selected();return
        item=next((x for x in self.studio.test_runner.items if x['id']==test_id(number,self.profile)),None)
        if not item or not item['enabled']:
            messagebox.showerror('Test unavailable','Test manifest for '+number+' missing/disabled. Check its installation.')
            self._selected();return
        # Existing TestRunner owns launches, script SHA pinning and histories.
        if number=='94':
            self.studio.test_runner._run_test94_after_remote_check()
        elif number in ('98','99') and self.runs.get(number):
            self.notice.set('Test '+number+' already exists on '+self.profile+'. Select the run to Download; no new job submitted.')
            messagebox.showinfo('Test already exists','A test run exists on '+self.profile+'. Use Refresh / Download. No new job started.')
        elif self.studio.test_runner._approval([item]):
            self.launch_number=number
            self.studio.test_runner._run([item])
            self.notice.set('Test '+number+' : local preparation requested. The server has NOT confirmed the launch yet.')
            self.parent.after(3000,self.refresh)
        self._selected()

    def _packet_dir(self,number,runid):
        base=Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/test_id(number,self.profile)
        if number in ('98','99','100','101','102','103','104') and self.profile=='Cloud-V':
            return base/('Cloud-V-'+runid)
        return base/(('EPCC-' if self.profile=='EPCC' and number in ('94','96','97','98','99','100','101','102','103','104') else 'simple-')+runid)

    def download(self):
        row=self._row();number=self._number()
        if not row or not number or self.busy or not self.studio.ssh.connected():return
        if not (self.remote_checked and row['packet'] and ((row['state']=='completed' and row.get('validated')) or (number in ('100','101','102','103','104') and row['state'] in ('failed','stopped')))):
            messagebox.showinfo('Not finished yet','Click Refresh. Download will be enabled once completion is validated.');return
        target=self._packet_dir(number,row['id'])
        self.busy=True;self._selected()
        self.notice.set('Downloading (SHA-256) from '+self.profile+'…')
        profile=self.profile
        remote_name=self.studio.vars['remote_name'].get().strip()
        run=dict(row)
        def work():
            try:
                # Recheck the SAME remote run before copying, not the newest run.
                found=_server_runs(self.studio.ssh,remote_name,number,profile)
                match=next((r for r in found if r['id']==run['id']),None)
                if not match or not match.get('packet') or not ((match['state']=='completed' and match.get('validated')) or (number in ('100','101','102','103','104') and match['state'] in ('failed','stopped'))):
                    raise RuntimeError('The selected run is no longer confirmed as completed.')
                if number=='100' and profile=='Cloud-V':
                    # Preserve the existing Windows-safe Test100 downloader.
                    from rvvlab_test100_download import sync_cloudv_test100
                    packet=sync_cloudv_test100(
                        self.studio.ssh, remote_name, run['id'],
                        self.studio.vars['results'].get(), workdir=run['path'])
                elif number=='104' and profile=='Cloud-V':
                    from rvvlab_test104_download import sync_cloudv_test104
                    packet=sync_cloudv_test104(
                        self.studio.ssh, remote_name, run['id'],
                        self.studio.vars['results'].get(), workdir=run['path'],
                        expected_state='completed' if match['state']=='completed' else None)
                elif number=='103' and profile=='Cloud-V':
                    from rvvlab_test103_download import sync_cloudv_test103
                    packet=sync_cloudv_test103(
                        self.studio.ssh, remote_name, run['id'],
                        self.studio.vars['results'].get(), workdir=run['path'],
                        expected_state='completed' if match['state']=='completed' else None)
                elif number=='102' and profile=='Cloud-V':
                    from rvvlab_test102_download import sync_cloudv_test102
                    packet=sync_cloudv_test102(
                        self.studio.ssh, remote_name, run['id'],
                        self.studio.vars['results'].get(), workdir=run['path'],
                        expected_state='completed' if match['state']=='completed' else None)
                elif number=='101' and profile=='Cloud-V':
                    # Independent verified downloader and result directory.
                    from rvvlab_test101_download import sync_cloudv_test101
                    packet=sync_cloudv_test101(
                        self.studio.ssh, remote_name, run['id'],
                        self.studio.vars['results'].get(), workdir=run['path'])
                elif profile=='EPCC' and number in ('94','96','97','98','99','100','101','102','103','104'):
                    from rvvlab_epcc_results import sync_epcc_run
                    folder=sync_epcc_run(self.studio.ssh,remote_name,run['id'],
                                         self.studio.vars['results'].get())
                    packet=folder/ZIP_NAME[number]
                else:
                    target.mkdir(parents=True,exist_ok=True)
                    ctx=TestContext(self.studio,target,lambda x:self.events.put(('note',str(x))),
                                    threading.Event(),{'id':test_id(number,profile)})
                    ctx.ensure_connected()
                    file={'94':'94_machine_1h.py','95':'95_cloudv_8h.py','96':'96_epcc_8h.py','97':'97_cloudv_8h.py','98':'98_real_corpus.py','99':'99_public_8h.py','100':'100_adaptive_public.py', '101':'101_dispatch_validation.py','102':'102_escape_stage.py','103':'103_escape_stage.py','104':'104_escape_stage.py'}[number]
                    path=SCRIPTS_DIR/file
                    if not path.is_file():raise RuntimeError('Recovery script missing: '+str(path))
                    spec=importlib.util.spec_from_file_location('rvvlab_simple_recovery_'+number,path)
                    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                    if number=='94':
                        output=mod.recover(ctx,{'mode':profile,'id':run['id'],'workdir':run['path']})
                        packet=output.get('packet')
                    elif number in ('95','97'):packet=mod.grab(ctx,run['path'])
                    elif number in ('98','99','100','101','102','103','104'):packet=mod.verified_archive(ctx,{'id':run['id'],'workdir':run['path']},'Cloud-V')
                    else:packet=mod.download(ctx,run['path'])
                if not packet:raise RuntimeError('No ZIP archive downloaded.')
                self.events.put(('download',(profile,number,run['id'],str(packet),None)))
            except Exception as ex:self.events.put(('download',(profile,number,run['id'],None,str(ex))))
        threading.Thread(target=work,daemon=True).start()

    def open_results(self):
        number=self._number();row=self._row()
        if not number:return
        dest=self._packet_dir(number,row['id']) if row else Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/test_id(number,self.profile)
        if not dest.is_dir():
            messagebox.showinfo('Results','No local download for this run.');return
        if os.name=='nt':os.startfile(str(dest))
        else:messagebox.showinfo('Local results',str(dest))

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
                        self.notice.set('Server check failed: '+error[:320]+'. No failure or absence inferred.')
                        runner=getattr(self.studio,'test_runner',None)
                        if runner is not None and hasattr(runner,'mark_verification_unavailable'):
                            runner.mark_verification_unavailable(profile,error)
                    else:
                        self.runs=data;self.remote_checked=True;self.checked_at=time.monotonic()
                        self.remote_activity=processes or [];self.last_check_error=None
                        if profile=='Cloud-V' and self.remote_activity:
                            for r in data.get('97',[]):
                                if r['state']=='unconfirmed':
                                    r['state']='building';r['proof']='Confirmed remote /proc process'
                        for n in self.tree.get_children():
                            rows=data.get(n,[]);row=rows[0] if rows else None
                            local=_local_attempt(self.studio.vars['results'].get(),n,profile)
                            if row:label=_label(row)
                            elif n=='97' and profile=='Cloud-V' and self.remote_activity:label='🟡 Active remote process'
                            elif self.launch_number==n and self.studio.test_runner.busy:label='◷ Local preparation in progress'
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
                            # Campaign history is supplemental. A future test ID or
                            # widget failure must not stop the main Tests event queue.
                            try:
                                unified.apply_verified_campaigns(profile,data,self.remote_activity)
                                # Same 60-second scheduler, no secondary periodic poll.
                                if not unified.poll_busy and not unified.busy:
                                    unified.refresh_remote()
                            except Exception as ex:
                                if runner is not None and hasattr(runner,'_log'):
                                    runner._log('Campaign history UI error: '+repr(ex))
                                self.notice.set('History panel error (Tests status still valid): '+str(ex)[:160])
                        t=dt.datetime.now().astimezone().strftime('%H:%M:%S')
                        self.notice.set(('Cloud-V verified at '+t+': processes, runs and latest Studio log checked.') if profile=='Cloud-V' else
                                        'EPCC status and Studio logs verified at '+t+'.')
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
                            self.notice.set('No RISC-V Slurm node available; Test 94 blocked.')
                            messagebox.showerror('Slurm EPCC','No RISC-V Slurm node available.')
                            self._selected()
                            continue
                        runner.epcc_node.set('rvc02' if 'rvc02' in available else sorted(available)[0])
                    if error:
                        self.notice.set('Run blocked: cannot verify active runs: '+error[:250])
                        messagebox.showerror('Cannot verify server',error[:400])
                        self._selected()
                    else:self._launch_after_preflight(number,data)
                elif kind=='download':
                    profile,number,runid,path,error=payload
                    self.busy=False
                    if profile==self.studio.active_profile:
                        if error:self.notice.set('Download failed: '+error)
                        else:
                            self.notice.set('SHA-256 verified archive: '+path)
                            messagebox.showinfo('Download complete','Test '+number+' : archive available on your PC.\n\n'+path)
                    self._selected()
                elif kind=='note':self.notice.set(payload[:240])
        except tk.TclError:return
        self.parent.after(250,self._drain)
