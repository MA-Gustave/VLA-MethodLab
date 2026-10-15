"""RVV Lab Studio optional test runner (v5): 60-second watch, explicit sequential scripts.

Separation of concerns:
- Studio owns SSH, credentials, UI, reports, scheduling, and retention.
- *.test.json manifests describe trial-specific modules stored under test_scripts/.
- Each trusted Python module implements execute(ctx, params), runs ONLY after approval.
- Closing Studio does NOT kill a detached remote night runner, but pauses the queue.

This module intentionally does not read .env or create a new SSH connection.
"""
from __future__ import annotations
import collections
import csv
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import queue
import re
import shutil
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

APP_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = APP_DIR / 'test_scripts'
RUN_RE = re.compile(r'^night-\d{8}T\d{6}Z-[0-9a-f]{6}$')
TEST_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,80}$')
SOURCE_RE = re.compile(r'^\d{8}T\d{6}Z-(?:[0-9a-f]{6}|fix-[0-9a-f]{6})$')
TERMINAL = frozenset(('completed', 'stopped', 'failed', 'safety_stop'))
ACTIVE = frozenset(('starting', 'preflight', 'build', 'screen', 'confirm', 'running', 'exploring'))
MAX_SCRIPT_BYTES = 128 * 1024
MAX_MANIFEST_BYTES = 16 * 1024


def now_utc():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def sha256(path: Path) -> str:
    with path.open('rb') as f:
        h = hashlib.sha256()
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
        return h.hexdigest()


def discover(folder: Path):
    """Read-only scan; never imports/executes scripts during the refresh."""
    folder = Path(folder)
    found, errors = [], []
    if not folder.is_dir():
        return found, [f'Folder not found: {folder}']
    for manifest_path in sorted(folder.glob('*.test.json')):
        try:
            if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
                raise ValueError('Manifeste trop volumineux')
            doc = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
            if not isinstance(doc, dict) or doc.get('schema') != 1:
                raise ValueError('Expected schema: 1')
            name = doc.get('id', '')
            if not isinstance(name, str) or not TEST_RE.fullmatch(name):
                raise ValueError('Invalid test ID')
            script_name = doc.get('script', '')
            if not isinstance(script_name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.py', script_name):
                raise ValueError('Script .py sans chemin attendu')
            script_path = folder / script_name
            if script_path.is_symlink() or not script_path.is_file():
                raise ValueError('Script absent ou lien symbolique interdit')
            if script_path.stat().st_size > MAX_SCRIPT_BYTES:
                raise ValueError('Script trop volumineux')
            title = doc.get('title', name)
            if not isinstance(title, str) or len(title) > 160:
                raise ValueError('Invalid title')
            params = doc.get('params', {})
            if not isinstance(params, dict):
                raise ValueError('params must be a JSON object')
            if len(json.dumps(params)) > 8192:
                raise ValueError('params is too large')
            enabled = doc.get('enabled', False)
            if not isinstance(enabled, bool):
                raise ValueError('enabled must be boolean')
            manual_only=doc.get('manual_only',False)
            if not isinstance(manual_only,bool):raise ValueError('manual_only must be boolean')
            found.append({'id': name, 'title': title, 'enabled': enabled, 'manual_only':manual_only,
                          'params': params, 'manifest_path': manifest_path,
                          'script_path': script_path, 'manifest_sha': sha256(manifest_path),
                          'script_sha': sha256(script_path),
                          'description': str(doc.get('description', ''))[:600]})
        except (OSError, ValueError, TypeError, UnicodeError) as ex:
            errors.append(f'{manifest_path.name}: {ex}')
    ids = [d['id'] for d in found]
    duplicates = sorted({x for x in ids if ids.count(x) > 1})
    if duplicates:
        errors.append('Duplicate IDs: ' + ', '.join(duplicates))
        found = [x for x in found if x['id'] not in duplicates]
    def _newest(item):
        name=item['script_path'].stem
        match=re.match(r'^(\d+)(?:_|-|$)',name)
        return (-int(match.group(1)) if match else 0, item['id'])
    found.sort(key=_newest)
    return found, errors


def parse_csv(path: Path):
    if not path.is_file():
        return []
    with path.open('r', newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))


def analysis_report(folder: Path, run_id: str) -> str:
    """Audit stopped native v5 rows; NO assumptions about legacy baseline in ranking.csv."""
    status = json.loads((folder / 'status.json').read_text(encoding='utf-8'))
    observations = parse_csv(folder / 'map.csv')
    ranking = parse_csv(folder / 'ranking.csv')
    state = status.get('state', 'unknown')
    if state not in TERMINAL:
        raise ValueError(f'Campaign not finished: {state}')
    lines = [f'# Preliminary analysis — {run_id}', '',
             f'- Source: `{status.get("source", "unknown")}`',
             f'- Remote state: `{state}`',
             f'- Declared observations: **{status.get("observations", "unknown")}**',
             f'- map.csv rows: **{len(observations)}**',
             f'- VLEN: {status.get("vlen_bits", "unknown")} bits',
             f'- Stop reason: {status.get("stop_reason", "unknown")}',
             f'- Generated at: {now_utc()}', '']
    declared = status.get('observations')
    if isinstance(declared, int) and declared != len(observations):
        lines.append(f'**WARNING**: observations={declared}, map.csv={len(observations)} lignes.')
    versions = collections.Counter(x.get('variant', '') for x in observations)
    phases = collections.Counter(x.get('phase', '') for x in observations)
    corpora = collections.Counter(x.get('corpus', '') for x in observations)
    lines += ['## Coverage', '', f'- Variants: **{len(versions)}**; ' + ', '.join(f'`{k}` ({v})' for k,v in sorted(versions.items())),
              '- Phases: ' + ', '.join(f'`{k}` ({v})' for k,v in sorted(phases.items())),
              f'- Distinct corpora: **{len(corpora)}**', '']
    for fn in ('map.csv','ranking.csv','hypotheses.md','status.json'):
        lines.append(f'- SHA256 `{fn}`: `{sha256(folder / fn)}`' if (folder / fn).is_file() else f'- MISSING: `{fn}`')
    lines += ['', '## Ranking generated by the remote runner (reference must be verified)', '',
              '| Variant | Metric | Paired N | Geometric ratio | MAD |',
              '|---|---|---:|---:|---:|']
    for r in ranking:
        lines.append('| ' + ' | '.join([r.get('variant',''),r.get('metric',''),r.get('paired_n',''),r.get('geomean_ratio',''),r.get('mad_ratio','')]) + ' |')
    if not ranking:lines.append('No ranking available.')
    lines += ['', '## Repaired comparisons directly against upstream_vls256', '',
              'Measurements paired by phase, corpus, parse_iterations and trial number. '
              'Throughput ratio = variant / upstream_vls256. N counts observed pairs only.', '',
              '| Variant | Metric | Number of pairs | Geometric ratio |', '|---|---|---:|---:|']
    keys = ('phase','corpus','parse_iterations','trial')
    by_pair = collections.defaultdict(lambda: collections.defaultdict(list))
    for row in observations:
        by_pair[tuple(row.get(k,'') for k in keys)][row.get('variant','')].append(row)
    paired = collections.defaultdict(list)
    for key, groups in by_pair.items():
        ref = groups.get('upstream_vls256', [])
        if len(ref) != 1:
            continue
        for variant, rows in groups.items():
            if variant == 'upstream_vls256' or len(rows) != 1:
                continue
            for metric in ('dom_all_gbps','stage1_gbps','stage2_gbps'):
                try:
                    r=float(rows[0][metric])/float(ref[0][metric])
                    if r>0 and math.isfinite(r): paired[variant,metric].append(r)
                except (ValueError,KeyError,ZeroDivisionError,TypeError): pass
    for (variant,metric), ratios in sorted(paired.items()):
        gm=math.exp(sum(math.log(x) for x in ratios)/len(ratios))
        lines.append(f'| `{variant}` | `{metric}` | {len(ratios)} | {gm:.4f}× |')
    if not paired:lines.append('| No usable pairs in this early stop | — | 0 | — |')
    lines += ['', '## Limitations', '',
              '- Campaign stopped early by request; samples and variants may be unbalanced.',
              '- Remote ranking is not necessarily relative to upstream; keep those metrics separate.',
              '- Ratios use actually observed pairs, not extrapolated missing trials.',
              '- GCC global correctness and Smoke passed; full Clang/dispatch validation is not established here.',
              '- **Do not launch further tests before reviewing this report and its CSV files.**', '']
    return '\n'.join(lines)


class TestContext:
    """Small documented API passed to trusted per-test Python modules."""
    def __init__(self, studio, output_dir:Path, log, stop_event, manifest):
        self.studio=studio
        self.ssh=studio.ssh
        self.output_dir=output_dir
        self.log=log
        self.stop_event=stop_event
        self.manifest=manifest
        self.remote_name=studio.vars['remote_name'].get().strip()
        self.results_root=Path(studio.vars['results'].get()).expanduser()

    def ensure_connected(self):
        if not self.ssh.connected():raise RuntimeError('SSH disconnected')
        if self.remote_name != 'rvvlab-v5':
            raise RuntimeError('Refused: runner only permitted in rvvlab-v5')

    def sync_stopped_night(self,run_id):
        if not RUN_RE.fullmatch(str(run_id)):
            raise ValueError('Invalid run ID')
        self.ensure_connected()
        from rvvlab_night import sync
        self.log('Downloading SHA256-verified snapshot: '+run_id)
        folder=sync(self.ssh,self.remote_name,run_id,self.results_root)
        st=json.loads((folder/'status.json').read_text(encoding='utf-8'))
        if st.get('state') not in TERMINAL:
            raise RuntimeError('Run has not finished: '+str(st.get('state')))
        self.log(f'Snapshot downloaded: {folder} / {st.get("observations")} observations')
        return folder

    def create_analysis(self,run_id):
        data=self.sync_stopped_night(run_id)
        report=analysis_report(data,run_id)
        out=self.output_dir/'ANALYSIS.md'
        out.write_text(report,encoding='utf-8')
        # Entire verified source, no secrets: easy to share for review.
        import zipfile
        bundle=self.output_dir/'analysis_packet.zip'
        with zipfile.ZipFile(bundle,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('ANALYSIS.md',report)
            for name in ('status.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json'):
                path=data/name
                if path.is_file():z.write(path,arcname=name)
        self.log('Report created: '+str(out))
        self.log('Archive partageable: '+str(bundle))
        return {'analysis':str(out),'archive':str(bundle)}

    def request_night_stop(self,run_id):
        self.ensure_connected()
        if not RUN_RE.fullmatch(str(run_id)):raise ValueError('Invalid run ID')
        from rvvlab_night import stop
        stop(self.ssh,self.remote_name,run_id)
        self.log('Graceful STOP requested: '+run_id)

    def launch_night_8h(self,source_id):
        """Used by separately approved future test scripts, NOT by review script."""
        self.ensure_connected()
        if not SOURCE_RE.fullmatch(str(source_id)):raise ValueError('Invalid source ID')
        from rvvlab_night import _launch_script, remote_runs
        import shlex
        active=[r['id'] for r in remote_runs(self.ssh,self.remote_name) if r.get('state') not in TERMINAL]
        if active:raise RuntimeError('Remote exploration already running: '+', '.join(active))
        kib=self.ssh.available_kib()
        if kib is None:
            self.log('WARNING: remote disk size unavailable; remote worker will enforce 200 MiB safety guard')
        elif kib < 200*1024:
            raise RuntimeError(f'Only {kib/1024:.1f} MiB free; under 200 MiB safety floor')
        base=self.ssh.base(self.remote_name)
        source=base+'/sources/'+source_id
        script=base+'/night-runner/rvv_night_runner.py'
        local_script=APP_DIR/'night_runner'/'rvv_night_runner.py'
        if not local_script.is_file():
            raise RuntimeError('Night Runner v5 absent du Studio')
        rid=dt.datetime.now(dt.timezone.utc).strftime('night-%Y%m%dT%H%M%SZ-')+os.urandom(3).hex()
        run=base+'/night-runs/'+rid
        self.ssh.mkdir(base+'/night-runs')
        self.ssh.mkdir(base+'/night-runner')
        sftp=self.ssh.client.open_sftp()
        try:
            sftp.stat(source+'/scripts/rvv/perf/bench_native.py')
            self.ssh.mkdir(run)
            sftp.put(str(local_script),script,confirm=True)
            expected=sha256(local_script)
            actual=self.ssh.exec_text('sha256sum '+shlex.quote(script)).strip().split()[0]
            if expected!=actual:raise RuntimeError('Night runner distant SHA256 incorrect')
            response=_launch_script(self.ssh,script,
                ['--source',source,'--workdir',run,'--hours','8','--jobs','2','--core','0'],
                run+'/runner-startup.log')
            if 'NIGHT_PID=' not in response:raise RuntimeError('Launch refused: '+response)
            pid=int(response.rsplit('NIGHT_PID=',1)[1].split()[0])
            with sftp.open(run+'/launcher.json','w') as f:
                f.write(json.dumps({'run_id':rid,'source_id':source_id,'pid':pid,
                                    'worker_sha256':expected,'launcher':'rvvlab_test_runner'})+'\n')
        finally:sftp.close()
        result={'run_id':rid,'source_id':source_id,'pid':pid}
        self.log(f'8h campaign launched: {rid}, PID {pid}')
        return result

    def wait_night(self,run_id,timeout_seconds=8*3600+900):
        """60-second check; user closing Studio leaves detached remote runner intact."""
        self.ensure_connected()
        from rvvlab_night import remote_runs
        started=time.monotonic()
        while True:
            if self.stop_event.is_set():
                self.log('Studio monitoring stopped; remote campaign continues.')
                return {'state':'monitor_cancelled','run_id':run_id}
            matching=[x for x in remote_runs(self.ssh,self.remote_name) if x.get('id')==run_id]
            if matching:
                obj=matching[0]
                self.log(f'{run_id}: {obj.get("state")} / {obj.get("observations",0)} observations')
                if obj.get('state') in TERMINAL:
                    return obj
            if time.monotonic()-started>timeout_seconds:
                raise TimeoutError('Time limit reached; manual review required (no automatic kill)')
            self.stop_event.wait(60)


def run_trial(item,studio,result_root,emit,stop_event):
    """Run one previously pinned, manually approved trusted Python script."""
    manifest_path=item['manifest_path'];script_path=item['script_path']
    if sha256(manifest_path)!=item['manifest_sha'] or sha256(script_path)!=item['script_sha']:
        raise RuntimeError('Script or manifest changed since validation; refresh the queue')
    out=result_root/'TestRunner'/item['id']/(dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir(parents=True,exist_ok=True)
    (out/'manifest.json').write_text(manifest_path.read_text(encoding='utf-8-sig'),encoding='utf-8')
    (out/'script.sha256').write_text(item['script_sha']+'  '+script_path.name+'\n',encoding='ascii')
    log_path=out/'runner.log'
    def logger(line):
        stamped='['+now_utc()+'] '+str(line)
        with log_path.open('a',encoding='utf-8') as f:f.write(stamped+'\n')
        emit(stamped)
    ctx=TestContext(studio,out,logger,stop_event,item)
    ctx.ensure_connected()
    logger(f'START {item["id"]} script SHA256 {item["script_sha"]}')
    spec=importlib.util.spec_from_file_location('rvvlab_trial_'+re.sub(r'\W','_',item['id']),script_path)
    if spec is None or spec.loader is None:raise RuntimeError('Could not load script')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not callable(getattr(mod,'execute',None)):
        raise ValueError('Script must define execute(ctx, params)')
    try:
        result=mod.execute(ctx,dict(item['params']))
    except Exception as error:
        # Keep the actual failure visible to Tests simples even after Studio restarts.
        logger('FAIL: '+repr(error))
        if item['id']=='machine-compare-94-1h':
            # An SSH/monitoring failure after the detached launch does NOT
            # establish that the remote benchmark itself failed.
            launch_path=out/'launch94.json'
            launched=False
            if launch_path.exists():
                try:
                    launch=json.loads(launch_path.read_text(encoding='utf-8'))
                    launched=bool(launch.get('pid') or launch.get('job_id'))
                except (OSError,ValueError,AttributeError):pass
            # Preserve a server-confirmed failure sent by the remote observer.
            recorded=out/'status_pc94.json'
            current={}
            if recorded.exists():
                try:current=json.loads(recorded.read_text(encoding='utf-8'))
                except (OSError,ValueError):pass
            if not (current.get('verified') and current.get('state')=='failed'):
                status='warning' if launched else 'failed'
                summary=('Local monitoring interrupted; remote may still run' if launched
                         else 'Preparation failed before remote start')
                callback=getattr(studio,'report_test94_state',None)
                if callable(callback):callback(studio.active_profile,status,summary+' ('+type(error).__name__+')',out)
        raise
    (out/'result.json').write_text(json.dumps({'id':item['id'],'utc':now_utc(),
                'script_sha256':item['script_sha'],'result':result},ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    logger('PASS: '+item['id'])
    return {'folder':str(out),'result':result}




# RVVLAB_TEST_TITLES_ENGLISH_V1
ENGLISH_TEST_TITLES = {'review-v5-250': 'Review the stopped v5 campaign (250 measurements)', 'explore-v5-8h-fixed-points': 'Explore RVV v5 combinations — 8h (17 fixed points, early stop)', 'explore-v5-engines-3h': 'Explore RVV-VLA engine library — 3h (fixed plans)'}


def display_test_title(item):
    # Preserve original manifests on disk; only translate the presentation.
    return ENGLISH_TEST_TITLES.get(item['id'], item['title'])


class TestRunnerPanel:
    def __init__(self,parent,studio):
        self.parent=parent;self.studio=studio;self.events=queue.Queue();self.stop_event=threading.Event()
        self.busy=False;self.poll_busy=False;self.items=[];self.item_by_tree={}
        self.verified_campaigns={};self.verified_profile=None
        self.verified_processes=[];self.verification_error=None
        self.folder=tk.StringVar(value=str(SCRIPTS_DIR))
        self.run_id=tk.StringVar(value='night-20261009T231943Z-26725b')
        self.status=tk.StringVar(value='No automatic execution. Review the previous campaign first.')
        self.remote_status=tk.StringVar(value='Waiting for SSH connection.')
        self.history=self._read_history()
        self._build()
        self.refresh_local()
        self.parent.after(250,self._drain)
        self.parent.after(60000,self._minute)

    def _history_path(self):
        return Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/'history.json'

    def _read_history(self):
        try:
            obj=json.loads(self._history_path().read_text(encoding='utf-8'))
            return obj if isinstance(obj,dict) else {}
        except (OSError,ValueError,TypeError):return {}

    def _write_history(self):
        dest=self._history_path()
        dest.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile('w',dir=dest.parent,prefix='.history-',
                encoding='utf-8',delete=False) as f:
            temp=Path(f.name)
            json.dump(self.history,f,indent=2,ensure_ascii=False)
        os.replace(temp,dest)

    def _build(self):
        info=ttk.LabelFrame(self.parent,text='General — refresh every 60 seconds; manual launches only',padding=8)
        info.pack(fill='x')
        info.columnconfigure(1,weight=1)
        ttk.Label(info,text='Scripts folder').grid(row=0,column=0,sticky='w')
        ttk.Entry(info,textvariable=self.folder).grid(row=0,column=1,sticky='ew',padx=5)
        ttk.Button(info,text='…',width=3,command=self.browse).grid(row=0,column=2)
        ttk.Button(info,text='Refresh',command=self.refresh_local).grid(row=0,column=3,padx=5)
        ttk.Label(info,text='Campaign to monitor').grid(row=1,column=0,sticky='w',pady=4)
        ttk.Entry(info,textvariable=self.run_id).grid(row=1,column=1,sticky='ew',padx=5)
        ttk.Button(info,text='Read status',command=self.refresh_remote).grid(row=1,column=3,padx=5)
        ttk.Label(info,textvariable=self.remote_status,foreground='#555').grid(row=2,column=0,columnspan=4,sticky='w')
        ttk.Label(info,textvariable=self.status).grid(row=3,column=0,columnspan=4,sticky='w')
        # Test94 is launched from the ordinary manifest list / Test Center.
        # Keep EPCC defaults internally but no dedicated Test94 toolbar,
        # comparison button or machine settings block in Test Runner.
        self.epcc_node=tk.StringVar(value='rvc02')
        self.epcc_account=tk.StringVar(value='')
        self.epcc_node_status=tk.StringVar(value='EPCC nodes not checked yet')
        self.epcc_nodes={}
        columns=('title','script','status')
        treebox=ttk.Frame(self.parent);treebox.pack(fill='both',expand=True,pady=(8,3))
        tree=ttk.Treeview(treebox,columns=columns,show='headings',height=7,selectmode='extended')
        self.tree=tree
        self.live_style=ttk.Style()
        tree.configure(style='RVVLiveRunner.Treeview')
        self.live_style.map('RVVLiveRunner.Treeview',background=[('selected','#3470A4')],foreground=[('selected','#FFFFFF')])
        tree.bind('<<TreeviewSelect>>',lambda _e:self._highlight_selection())
        tree.tag_configure('live_active',background='#FFF0B3',foreground='#795000')
        tree.tag_configure('live_ok',background='#D9F6E4',foreground='#135C3E')
        tree.tag_configure('live_failed',background='#FDE2E2',foreground='#9B1C1C')
        tree.tag_configure('live_pending',background='#F6F0D5',foreground='#795000')
        for col,heading,width in [('title','Test',420),('script','Local script',225),('status','État distant',290)]:
            tree.heading(col,text=heading);tree.column(col,width=width,anchor='w')
        vbar=ttk.Scrollbar(treebox,orient='vertical',command=tree.yview)
        hbar=ttk.Scrollbar(treebox,orient='horizontal',command=tree.xview)
        tree.configure(yscrollcommand=vbar.set,xscrollcommand=hbar.set)
        vbar.pack(side='right',fill='y');hbar.pack(side='bottom',fill='x')
        tree.pack(side='left',fill='both',expand=True)
        btn=ttk.Frame(self.parent);btn.pack(fill='x',pady=4)
        self.single=ttk.Button(btn,text='Run selected',command=self.run_selected)
        self.single.pack(side='left',padx=3)
        self.all=ttk.Button(btn,text='Run enabled queue',command=self.run_queue)
        self.all.pack(side='left',padx=3)
        ttk.Button(btn,text='Stop local monitoring',command=self.stop_local).pack(side='left',padx=3)
        ttk.Button(btn,text='Open results',command=self.open_results).pack(side='left',padx=3)
        ttk.Label(self.parent,text='Trusted local Python scripts only. MANUAL execution; started RVV Lab campaigns run detached.',foreground='#6b7280').pack(anchor='w')
        self.log=scrolledtext.ScrolledText(self.parent,height=10,font=('Consolas',9),state='disabled')
        self.log.pack(fill='both',expand=True,pady=(5,0))

    def _log(self,text):
        self.log.configure(state='normal')
        self.log.insert('end',str(text)+'\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def browse(self):
        choice=filedialog.askdirectory(initialdir=self.folder.get(),title='Tests folder')
        if choice:self.folder.set(choice);self.refresh_local()

    def refresh_local(self):
        chosen={self.item_by_tree[i]['id'] for i in self.tree.selection() if i in self.item_by_tree}
        self.items,errors=discover(Path(self.folder.get()))
        self.history=self._read_history()
        for row in self.tree.get_children():self.tree.delete(row)
        self.item_by_tree={}
        restored=[]
        for item in self.items:
            previous=self.history.get(item['id'],{})
            done=(previous.get('script_sha256')==item['script_sha']
                    and previous.get('manifest_sha256')==item['manifest_sha']
                    and previous.get('state')=='PASS')
            state='PASS (already run)' if done else ('Ready (manual)' if item['enabled'] else 'Disabled')
            ident=self.tree.insert('','end',values=(display_test_title(item),item['script_path'].name,state))
            self.item_by_tree[ident]=item
            if item['id'] in chosen:restored.append(ident)
        if restored:self.tree.selection_set(restored)
        if errors:self._log('ERRORS: '+' | '.join(errors))
        self._render_verified_campaigns()
        self.status.set(f'{len(self.items)} test(s) found; {len(errors)} error(s). No automatic start.')

    def clear_verified_campaigns(self):
        self.verified_campaigns={};self.verified_profile=None
        self.verified_processes=[];self.verification_error=None
        self._render_verified_campaigns()

    def mark_verification_unavailable(self,profile,error):
        if self.studio.active_profile != profile:return
        self.verification_error=str(error)
        self._render_verified_campaigns()

    def apply_verified_campaigns(self,profile,data,processes):
        '''UI thread only: remote read was performed by Tests simples.

        A launcher result/PASS never establishes remote completion.
        '''
        if self.studio.active_profile!=profile:return
        self.verified_profile=profile
        self.verified_campaigns=data or {}
        self.verified_processes=processes or []
        self.verification_error=None
        self._render_verified_campaigns()

    def _render_verified_campaigns(self):
        from rvvlab_simple_tests import PROFILES,ACTIVE,_local_attempt,manifest_target,test_id
        profile=self.studio.active_profile
        for iid,item in list(self.item_by_tree.items()):
            if not self.tree.exists(iid):continue
            target=manifest_target(item['id'])
            if target is None:continue
            n,allowed=target
            row=None
            if profile not in allowed:
                label,tag='— Autre machine',''
            elif self.verification_error:
                label,tag='⚠ Serveur non vérifié','live_pending'
            elif self.verified_profile != profile:
                label,tag='○ En attente vérification',''
            else:
                rows=self.verified_campaigns.get(n,[])
                row=rows[0] if rows else None
                local=_local_attempt(self.studio.vars['results'].get(),n,profile)
                process=bool(n=='97' and profile=='Cloud-V' and self.verified_processes)
                if row:
                    state=str(row.get('state','')).lower()
                    if state=='completed' and row.get('validated') and row.get('packet'):
                        label,tag='🟢 Terminé — ZIP prêt','live_ok'
                    elif state in ('failed','safety_stop'):
                        label,tag='🔴 Échec distant','live_failed'
                    elif state in ACTIVE or state=='preparing' or (state=='unconfirmed' and process):
                        label,tag='🟡 '+('Compilation' if state in ('building','build','preparing','unconfirmed') else 'En cours'),'live_active'
                    elif state=='incomplete':
                        label,tag='⚠ Résultats incomplets','live_pending'
                    else:
                        label,tag='⚠ État à vérifier','live_pending'
                elif process:
                    label,tag='🟡 Processus distant actif','live_active'
                elif self.busy and getattr(self.studio,'simple_tests',None) is not None and self.studio.simple_tests.launch_number==n:
                    label,tag='🟡 Préparation Studio','live_active'
                elif local and local.get('state')=='failed_local':
                    label,tag='🔴 Échec local','live_failed'
                elif local and local.get('state')=='started_local':
                    label,tag='⚠ Aucun processus confirmé','live_pending'
                else:
                    label,tag='— Aucun lancement distant',''
            if row and row.get('rows') and tag in ('live_ok','live_active'):
                label+=f" · {row['rows']} mesures"
            self.tree.set(iid,'status',label)
            self.tree.item(iid,tags=(tag,) if tag else ())
        self._highlight_selection()

    def _highlight_selection(self):
        # Stock Treeview's blue selection would hide the yellow/green row tint.
        tags=[str(t) for iid in self.tree.selection() if self.tree.exists(iid)
              for t in self.tree.item(iid,'tags')]
        if 'live_failed' in tags:bg,fg='#F3B1B1','#781212'
        elif 'live_active' in tags:bg,fg='#FFE082','#563D00'
        elif 'live_ok' in tags:bg,fg='#B4E8C7','#0F5030'
        elif 'live_pending' in tags:bg,fg='#FBE7B2','#674A00'
        else:bg,fg='#3470A4','#FFFFFF'
        self.live_style.map('RVVLiveRunner.Treeview',background=[('selected',bg)],foreground=[('selected',fg)])
        selection=[self.item_by_tree[i] for i in self.tree.selection() if i in self.item_by_tree]
        from rvvlab_simple_tests import TEST_IDS
        managed_ids=set(TEST_IDS.values())
        selected_active=any(x['id'] in managed_ids and 'live_active' in self.tree.item(i,'tags')
                            for i,x in self.item_by_tree.items() if i in self.tree.selection())
        self.single.configure(state='disabled' if self.busy or selected_active else 'normal')

    def _minute(self):
        # ONE 60-second scheduler for both Test Runner and Tests simples.
        # No separate 45-second polling. All reads are read-only.
        self.refresh_local()
        if hasattr(self.studio,'simple_tests') and self.studio.ssh.connected():
            # Main workspace first, history inventory after it finishes. Prevent
            # two simultaneous SSH sweeps from fighting over the connection.
            self.studio.simple_tests.refresh()
        else:
            self.refresh_remote()
        self.parent.after(60000,self._minute)

    def refresh_remote(self):
        if self.poll_busy or not self.studio.ssh.connected():
            if not self.studio.ssh.connected():self.remote_status.set('SSH disconnected; local monitoring only.')
            return
        run_id=self.run_id.get().strip()
        if not run_id:return
        if not RUN_RE.fullmatch(run_id):
            self.remote_status.set('Invalid NightRuns ID');return
        self.poll_busy=True
        def worker():
            try:
                sftp=self.studio.ssh.client.open_sftp()
                try:
                    path=self.studio.ssh.base('rvvlab-v5')+'/night-runs/'+run_id+'/status.json'
                    with sftp.open(path,'r') as f:doc=json.loads(f.read().decode('utf-8'))
                finally:sftp.close()
                self.events.put(('remote',f'{run_id}: {doc.get("state")} · {doc.get("observations",0)} observations · disque {doc.get("disk_free_gib","?")} GiB'))
            except Exception as ex:self.events.put(('remote','Read error: '+str(ex)))
        threading.Thread(target=worker,daemon=True).start()

    def _approval(self,items):
        if self.busy:return False
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH Connect','Connect Studio to the server before starting.');return False
        if self.studio.job_busy or self.studio.night_busy or self.studio.storage_busy:
            messagebox.showwarning('Studio is busy','Wait for the current operation to finish.');return False
        if not items:return False
        from rvvlab_simple_tests import manifest_target
        mismatch=[x['title'] for x in items if manifest_target(x['id']) is not None and
                  self.studio.active_profile not in manifest_target(x['id'])[1]]
        if mismatch:
            messagebox.showerror('Mauvaise machine','Test(s) destinés à une autre machine : '+', '.join(mismatch))
            return False
        desc='\n'.join(f'{i+1}. {display_test_title(x)} — {x["script_path"].name} [{x["script_sha"][:12]}]' for i,x in enumerate(items))
        return messagebox.askyesno('Run trusted scripts',
            'These local Python scripts run under your Studio account with SSH access.\n'
            'Load ONLY scripts that you have reviewed and approved.\n'
            'Tests run one at a time. No other test starts automatically.\n\n'+desc)

    def set_machine_mode(self,profile):
        """No special Test94 controls: profile handled by the manifest runner."""
        if profile!='EPCC':self.epcc_nodes={}

    def detect_epcc_nodes(self):
        if self.studio.active_profile!='EPCC':
            messagebox.showinfo('EPCC nodes','Choose EPCC profile and connect SSH first.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('EPCC SSH','Connect to EPCC from Studio first.');return
        self.epcc_node_status.set('Querying Slurm nodes on EPCC login...')
        def task():
            try:
                text=self.studio.ssh.exec_text('sinfo -h -N -o "%N|%P|%T|%f"')
                nodes={}
                for line in text.splitlines():
                    cells=line.split('|')
                    if len(cells)!=4 or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}',cells[0]):continue
                    node,part,state,features=cells
                    nodes.setdefault(node,{'partition':part.rstrip('*'),'state':state,'features':features})
                if not nodes:raise RuntimeError('No Slurm nodes returned; check EPCC access or Slurm status')
                self.events.put(('nodes94',nodes))
            except Exception as ex:self.events.put(('nodes94_fail',str(ex)))
        threading.Thread(target=task,daemon=True).start()

    def run_test94(self):
        if hasattr(self.studio,'test_center'):
            self.studio.open_advanced(self.studio.center_tab)
            return self.studio.test_center.request_launch94()
        return self._run_test94_after_remote_check()

    def _run_test94_after_remote_check(self):
        item=next((x for x in self.items if x['id']=='machine-compare-94-1h'),None)
        if not item:
            self.refresh_local()
            item=next((x for x in self.items if x['id']=='machine-compare-94-1h'),None)
        if not item:
            messagebox.showerror('Test 94','Test94 manifest not installed in Test Runner folder.');return
        if self.studio.active_profile=='EPCC' and not self.epcc_nodes:
            self.detect_epcc_nodes()
            messagebox.showinfo('EPCC nodes','Vérification Slurm en cours. Le nœud RVV disponible sera choisi automatiquement. Relancez la sélection une fois la détection terminée.')
            return
        if self._approval([item]):self._run([item])

    def _test94_item(self,item):
        if item['id']!='machine-compare-94-1h':return item
        x=dict(item);x['params']=dict(item['params'])
        if self.studio.active_profile=='EPCC':
            node=self.epcc_node.get().strip()
            meta=self.epcc_nodes.get(node)
            if not meta:raise ValueError('For EPCC: click Detect nodes and choose the RISC-V compute node')
            if meta['state'].lower().startswith(('down','drain','fail','maint','unk')):
                raise ValueError('Slurm node unavailable: '+node+' ('+meta['state']+')')
            x['params'].update(epcc_node=node,epcc_partition=meta['partition'],
                               epcc_account=self.epcc_account.get().strip())
        return x

    def recover_test94(self):
        if self.busy:return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connect to the selected machine before recovering Test94.');return
        folder=Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/'machine-compare-94-1h'
        runs=sorted(folder.glob('*/launch94.json'),reverse=True)
        match=None
        for path in runs:
            try:
                doc=json.loads(path.read_text(encoding='utf8'))
                if doc.get('mode')==self.studio.active_profile:
                    match=(path,doc);break
            except (OSError,ValueError):pass
        # A verified remote packet can predate local Studio launch metadata.
        remote=getattr(self.studio,'remote94_last',None)
        from rvvlab_test_center import TEST94_ID
        if remote and TEST94_ID.fullmatch(str(remote.get('id') or '')) and remote.get('packet'):
            rid=remote['id']
            if match is None or match[1].get('id')!=rid:
                workdir=self.studio.ssh.base(self.studio.vars['remote_name'].get().strip())+'/test94-runs/'+rid
                doc={'id':rid,'mode':self.studio.active_profile,'workdir':workdir}
                file=folder/(rid+'-recovered')/'launch94.json'
                file.parent.mkdir(parents=True,exist_ok=True)
                file.write_text(json.dumps(doc,indent=2)+'\n',encoding='utf8')
                match=(file,doc)
        if match is None:
            messagebox.showinfo('Recover Test94','No saved launch or server-confirmed Test94 packet. Check the server in Centre des tests first.');return
        self.busy=True;self.single.configure(state='disabled');self.all.configure(state='disabled')
        self.status.set('Recover Test94: checking remote status and results...')
        def work():
            try:
                from types import SimpleNamespace
                from rvvlab_test_runner import TestContext
                import importlib.util
                p=SCRIPTS_DIR/'94_machine_1h.py'
                spec=importlib.util.spec_from_file_location('rvvlab_test94_recovery',p)
                mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
                dest,doc=match
                ctx=TestContext(self.studio,dest.parent,lambda line:self.events.put(('line',line)),threading.Event(),{'id':'machine-compare-94-1h'})
                result=mod.recover(ctx,doc)
                self.events.put(('line','Test94 recover: '+json.dumps(result,ensure_ascii=False)))
            except Exception as ex:self.events.put(('line','Recover Test94 ERROR: '+str(ex)))
            finally:self.events.put(('done','Test94 recovery finished.'))
        threading.Thread(target=work,daemon=True).start()

    def compare_test94(self):
        import subprocess
        paths=[]
        for mode in ('Cloud-V','EPCC'):
            results=Path(self.studio.machine_results[mode]).expanduser()/'TestRunner'/'machine-compare-94-1h'
            folders=sorted(results.glob('*/test94_results.zip'),reverse=True)
            if not folders:
                messagebox.showwarning('Compare Test94','No completed Test94 packet for '+mode+'. Run and recover both machines first.');return
            paths.append(folders[0])
        out=Path(self.studio.machine_results[self.studio.active_profile]).expanduser()/'TestRunner'/'Test94_Comparison'
        out.mkdir(parents=True,exist_ok=True)
        script=APP_DIR.parent/'tools'/'test94_native.py'
        try:
            proc=subprocess.run([os.sys.executable,str(script),'compare',*[str(p) for p in paths]],cwd=out,
                                capture_output=True,text=True,timeout=90,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if proc.returncode:raise RuntimeError(proc.stderr[-1800:])
            file=out/'TEST94_COMPARISON.md'
            self._log('Cross-machine comparison created: '+str(file))
            messagebox.showinfo('Test94 comparison','Report created:\n'+str(file))
        except Exception as ex:messagebox.showerror('Compare Test94',str(ex))

    def run_selected(self):
        selection=[self.item_by_tree[i] for i in self.tree.selection() if i in self.item_by_tree]
        selection=[i for i in selection if i['enabled']]
        if not selection:
            messagebox.showinfo('Selection','Select an enabled test in the table.');return
        # Tests 94–97 ALWAYS pass through the same remote anti-duplicate preflight
        # as Tests simples. This prevents Run selected from bypassing safety.
        from rvvlab_simple_tests import manifest_target
        managed=[x for x in selection if manifest_target(x['id']) is not None]
        if managed:
            if len(selection)!=1:
                messagebox.showwarning('Tests isolés',
                    'Lancez les Tests 94/95/96/97 un par un. Une file multiple est interdite.');return
            number,allowed=manifest_target(managed[0]['id'])
            if self.studio.active_profile not in allowed:
                messagebox.showerror('Mauvaise machine',
                    'Le Test '+number+' ne correspond pas à '+self.studio.active_profile+'.');return
            simple=getattr(self.studio,'simple_tests',None)
            if simple is None:
                messagebox.showerror('Tests simples',
                    'Le contrôle anti-doublon distant est indisponible. Lancement refusé.');return
            if simple.profile != self.studio.active_profile:simple.profile_changed()
            simple.tree.selection_set(number)
            simple._selected()
            simple.run()  # read-only server preflight BEFORE local launch
            return
        if self._approval(selection):self._run(selection)

    def run_queue(self):
        items=[i for i in self.items if i['enabled'] and not i.get('manual_only',False) and not (
            self.history.get(i['id'],{}).get('state')=='PASS'
            and self.history.get(i['id'],{}).get('script_sha256')==i['script_sha']
            and self.history.get(i['id'],{}).get('manifest_sha256')==i['manifest_sha'])]
        if not items:
            messagebox.showinfo('Empty queue','No enabled manifests.');return
        if self._approval(items):self._run(items)

    def _run(self,items):
        try:items=[self._test94_item(x) for x in items]
        except ValueError as exc:
            messagebox.showwarning('Test94 settings',str(exc));return
        self.busy=True;self.stop_event.clear()
        self.single.configure(state='disabled');self.all.configure(state='disabled')
        self.status.set(f'Manual execution: {len(items)} scripts, sequentially')
        def work():
            results_root=Path(self.studio.vars['results'].get()).expanduser()
            for item in items:
                if self.stop_event.is_set():break
                try:
                    self.events.put(('line','=== '+display_test_title(item)+' ==='))
                    result=run_trial(item,self.studio,results_root,
                        lambda line:self.events.put(('line',line)),self.stop_event)
                    self.history[item['id']]={'state':'PASS','script_sha256':item['script_sha'],
                        'manifest_sha256':item['manifest_sha'],'folder':result['folder'],
                        'finished_utc':now_utc()}
                    self._write_history()
                    self.events.put(('line','PASS '+item['id']+' => '+result['folder']))
                except Exception as ex:
                    # A failure before the remote run folder exists must be recoverable
                    # from the Tests simples status screen, without SSH Console.
                    try:
                        faildir=results_root/'TestRunner'/item['id']
                        faildir.mkdir(parents=True,exist_ok=True)
                        (faildir/'last_failure.json').write_text(json.dumps({
                            'state':'failed','utc':now_utc(),'error':repr(ex)},
                            ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                    except OSError:pass
                    self.events.put(('line','FAIL '+item['id']+': '+repr(ex)))
                    # Strict fail-stop: never start next test after failed one.
                    break
            self.events.put(('done','Queue finished or stopped; no automatic start.'))
        threading.Thread(target=work,daemon=True).start()

    def stop_local(self):
        self.stop_event.set()
        self._log('LOCAL STOP requested: remote campaigns keep running. Use Request Stop in Test Runner.')

    def open_results(self):
        p=Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'
        p.mkdir(parents=True,exist_ok=True)
        if hasattr(os,'startfile'):os.startfile(str(p))
        else:messagebox.showinfo('Results',str(p))

    def _drain(self):
        try:
            for _ in range(120):
                try:kind,data=self.events.get_nowait()
                except queue.Empty:break
                if kind=='line':self._log(data)
                elif kind=='remote':self.remote_status.set(data);self.poll_busy=False
                elif kind=='nodes94':
                    self.epcc_nodes=data
                    available=[n for n in sorted(data) if not data[n]['state'].lower().startswith(('down','drain','fail','maint','unk'))
                               and (n.startswith('rvc') or 'riscv' in data[n]['features'].lower())]
                    if self.epcc_node.get() not in available:self.epcc_node.set('rvc02' if 'rvc02' in available else (available[0] if available else ''))
                    desc='; '.join(f'{k}: {v["partition"]}, {v["state"]}, {v["features"]}' for k,v in sorted(data.items()))
                    self.epcc_node_status.set(f'{len(data)} Slurm node(s) discovered (using {self.epcc_node.get() or "none"}).')
                    self._log('EPCC Slurm nodes: '+desc)
                elif kind=='nodes94_fail':
                    self.epcc_node_status.set('EPCC node discovery failed: '+data)
                    self._log('EPCC node discovery ERROR: '+data)
                elif kind=='done':
                    self.busy=False;self.single.configure(state='normal');self.all.configure(state='normal')
                    self.status.set(data)
                    self.refresh_local()
                    if hasattr(self.studio,'test_center'):self.studio.test_center.refresh_local()
        finally:self.parent.after(250,self._drain)
