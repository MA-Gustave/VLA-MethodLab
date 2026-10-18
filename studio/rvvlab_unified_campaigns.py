#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RVV Lab Studio v5: remote campaigns inside the existing Test Runner tab.

Read-only background refresh every 60 seconds (driven by TestRunnerPanel).
No process launch, mutation or destructive operation without a direct click.
The only remote write is an explicitly confirmed graceful STOP marker.
"""
from __future__ import annotations

import queue
import threading
from datetime import datetime, timezone
import re
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

from rvvlab_backend import validate_remote_name
from rvvlab_local_time import remote_utc_as_local
from rvvlab_night import remote_runs, stop as request_stop, sync as sync_results
from rvvlab_epcc_results import discover_epcc_runs, sync_epcc_run

TERMINAL = frozenset({'stopped', 'failed', 'completed', 'complete', 'finished',
                       'done', 'safety_stop', 'timeout', 'cancelled'})


def readable_test(row):
    """Identify Studio/CLI campaigns without guessing from timestamped run IDs."""
    if row.get('kind')=='test94':return 'Test 94 — EPCC (1h)'
    if row.get('kind')=='test96':return 'Test 96 — EPCC (8h)'
    if row.get('kind')=='test95':return 'Test 95 — Cloud-V (8h)'
    if row.get('kind')=='test98':return 'Test 98 — public JSON (1h)'
    if row.get('kind')=='test106':return 'Test 106 — VectorPath release candidate A/B'
    if row.get('kind')=='test105':return 'Test 105 — GCC × LLVM Stage 2 matrix'
    if row.get('kind')=='test104':return 'Test 104 — Independent public JSON & JSONTestSuite validation'
    if row.get('kind')=='test103':return 'Test 103 — Stage 2 escape decoder variants'
    if row.get('kind')=='test102':return 'Test 102 — Overnight escape-density Stage 1/2'
    if row.get('kind')=='test101':return 'Test 101 — Cross-machine A2 threshold validation'
    if row.get('kind')=='test100':return 'Test 100 — Adaptive public + boundary DOM'
    if row.get('kind')=='test99':return 'Test 99 — public JSON A2 4/6/8 KiB (8h)'
    if row.get('kind')=='test97':return ('Test 97 — EPCC officiel v5 (3h)' if row.get('test_id')=='test97-epcc-v5-3h' else 'Test 97 — Cloud-V (8h)')
    if row.get('kind')=='test94-cloudv':return 'Test 94 — Cloud-V (1h)'
    name=str(row.get('campaign') or '').lower().replace('_','').replace('-','')
    duration=row.get('budget_seconds')
    if 'test93' in name or 'stage1overheadisolation93' in name:
        return 'Test 93 — Stage1 + surcoût 3h'
    if 'test92' in name or 'compositionexploration92' in name:
        return 'Test 92 — Adaptatif 8h'
    if 'test91' in name or 'compositionexploration91' in name:
        if duration is not None:
            try:return 'Test 91 — Pilote 1h' if float(duration)<=3600 else 'Test 91 — Exploration 8h'
            except (ValueError,TypeError):pass
        return 'Test 91 — Compositions'
    if 'holdoutvalidation2h' in name:return 'Test 90 — Holdout 2h'
    if 'prequalcorrected' in name:return 'Test 89 — Pilote 1h'
    return 'Unidentified'


# RVVLAB_UI_20261013 — Compact, transparent time display; original IDs stay intact.
def parse_utc(value):
    if value is None or value == '':return None
    try:
        if isinstance(value,(int,float)):
            return datetime.fromtimestamp(value,timezone.utc)
        raw=str(value).strip()
        when=datetime.fromisoformat(raw[:-1]+'+00:00' if raw.endswith(('Z','z')) else raw)
        return when.replace(tzinfo=timezone.utc) if when.tzinfo is None else when.astimezone(timezone.utc)
    except (ValueError,OverflowError,OSError,TypeError):return None


def campaign_start(row):
    for field in ('started_utc','start_time_utc','started_at'):
        instant=parse_utc(row.get(field))
        if instant is not None:return instant,False
    # Historical night campaign identifiers encode UTC creation, not necessarily
    # the exact worker start. Mark this estimate explicitly with ≈.
    match=re.fullmatch(r'(?:night|test94|test95|test96|test97|test98|test99|test100|test101|test102|test103|test104|test105|test106)-(\d{8}T\d{6})Z-[0-9a-f]{6}',str(row.get('id') or ''))
    if match:
        try:
            stamp=datetime.strptime(match.group(1),'%Y%m%dT%H%M%S').replace(tzinfo=timezone.utc)
            return stamp,True
        except ValueError:pass
    return None,False


def date_pc(instant,estimated=False):
    return ('≈ ' if estimated else '')+remote_utc_as_local(instant.isoformat()) if instant else '—'


def campaign_elapsed(row,now=None):
    started,_=campaign_start(row)
    if started is None:return '—'
    if str(row.get('state') or '').lower() in TERMINAL:
        ended=parse_utc(row.get('last_update'))
    else:
        ended=parse_utc(now) if now is not None else datetime.now(timezone.utc)
    if ended is None:return '—'
    elapsed=max(0,int((ended-started).total_seconds()//60))
    hours,mins=divmod(elapsed,60)
    return f'{hours}h {mins:02d}m' if hours else f'{mins}m'


def campaign_state(row):
    state=str(row.get('state') or '').lower()
    if state in ('completed','complete','finished','done','stopped'):return '🟢 Completed' if row.get('validated') and row.get('packet') else 'Finished'
    if state in ('building','build','preparing','running','exploring','train','holdout'):return '🟡 '+('Compilation' if state in ('building','build','preparing') else 'En cours')
    if state in ('failed','safety_stop'):return '🔴 Failed'
    if state=='unknown':return 'Needs verification'
    if state=='building':return 'Compilation'
    if state in ('queued','pending'):return 'Pending'
    if state in TERMINAL:return state.replace('_',' ').title()
    if state in ('starting','launch_incomplete','preflight'):return 'Starting'
    return 'Running' if state else 'Unknown'


def campaign_phase(row):
    phase=str(row.get('experiment_phase') or row.get('phase') or '').strip()
    if phase:return phase
    state=str(row.get('state') or '').strip()
    return state if state.lower() not in TERMINAL else '—'


def campaign_details(row):
    began,estimated=campaign_start(row)
    budget=row.get('budget_seconds')
    try:budget=f'{float(budget)/3600:g}h' if budget is not None else '—'
    except (ValueError,TypeError):budget='—'
    return '\n'.join((
       'Test / profile: '+readable_test(row),
       'Campaign ID: '+str(row.get('id') or '—'),
       'Raw state: '+str(row.get('state') or '—'),
       'Phase: '+campaign_phase(row),
       'Started (PC): '+date_pc(began,estimated),
       'Elapsed: '+campaign_elapsed(row),
       'Last update (PC): '+date_pc(parse_utc(row.get('last_update'))),
       'Time budget: '+budget,
       'Measurements: '+str(row.get('observations') or 0),
       'Current variant: '+str(row.get('current_candidate') or '—'),
       'Current corpus: '+str(row.get('current_corpus') or '—'),
       'Free disk (GiB): '+str(row.get('disk_free_gib') if row.get('disk_free_gib') is not None else '—'),
       'Stop reason: '+str(row.get('stop_reason') or row.get('reason') or '—'),
       'EPCC result ZIP: '+('available (SHA256 verification on download)' if row.get('packet') else 'not available') if row.get('kind') else '',
       '≈ means estimated from campaign ID (exact started_utc unavailable).' if estimated else '',
    )).rstrip()


def display_rows(rows,now=None):
    """Operator columns only. The underlying campaign ID remains the tree IID."""
    out=[]
    for row in rows:
        started,estimated=campaign_start(row)
        out.append((readable_test(row),campaign_state(row),date_pc(started,estimated),
                    campaign_elapsed(row,now),campaign_phase(row),
                    row.get('observations') or 0,date_pc(parse_utc(row.get('last_update')))))
    return out

class UnifiedCampaigns:
    """Compact campaigns table inserted into a TestRunnerPanel, before its log."""
    def __init__(self, runner, studio):
        self.runner = runner
        self.studio = studio
        self.events = queue.Queue()
        self.busy = False
        self.poll_busy = False
        self.rows = []
        self.by_id = {}
        self.history_rows=[]
        self.verified_by_profile={}
        self.status = tk.StringVar(value='Connect SSH, then refresh campaigns.')
        self._build()
        # The original single-campaign default was a stopped 250-row review.
        # Let the unified view select the latest remote run instead.
        if self.runner.run_id.get().strip() == 'night-20261009T231943Z-26725b':
            self.runner.run_id.set('')
        self.runner.parent.after(250, self._drain)
        self.runner.parent.after(1400, self.refresh_remote)

    def _remote_name(self):
        return validate_remote_name(self.studio.vars['remote_name'].get().strip())

    def _build(self):
        self.frame=ttk.LabelFrame(self.runner.parent,
                                  text='RVV Lab campaigns — 60-second refresh, graceful stop, results sync',
                                  padding=6)
        # Keep the original scripts list and execution log in the same tab.
        self.frame.pack(fill='x',before=self.runner.log,pady=(4,5))
        bar=ttk.Frame(self.frame)
        bar.pack(fill='x',pady=(0,4))
        self.refresh_btn=ttk.Button(bar,text='Refresh campaigns',command=self.refresh_remote)
        self.refresh_btn.pack(side='left',padx=(0,5))
        self.sync_btn=ttk.Button(bar,text='Sync results',command=self.sync_selected)
        self.sync_btn.pack(side='left',padx=(0,5))
        self.stop_btn=ttk.Button(bar,text='Request stop',command=self.stop_selected)
        self.stop_btn.pack(side='left',padx=(0,5))
        ttk.Button(bar,text='Open results',command=self.open_results).pack(side='left')
        ttk.Button(bar,text='Details',command=self.show_details).pack(side='left',padx=(5,0))
        ttk.Label(bar,textvariable=self.status,foreground='#555').pack(side='right')
        cols=('test','state','started','elapsed','phase','n','updated')
        treebox=ttk.Frame(self.frame);treebox.pack(fill='x')
        self.tree=ttk.Treeview(treebox,columns=cols,show='headings',height=5,
                               selectmode='browse')
        self.live_style=ttk.Style()
        self.tree.configure(style='RVVLiveCampaigns.Treeview')
        for col,label,width in (
            ('test','Test / profile',225), ('state','State',85),
            ('started','Start time (PC)',218), ('elapsed','Elapsed',94),
            ('phase','Phase',125), ('n','Measurements',105),
            ('updated','Last update (PC)',218),
        ):
            self.tree.heading(col,text=label)
            self.tree.column(col,width=width,anchor='w',stretch=col=='test')
        vbar=ttk.Scrollbar(treebox,orient='vertical',command=self.tree.yview)
        hbar=ttk.Scrollbar(self.frame,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=vbar.set,xscrollcommand=hbar.set)
        vbar.pack(side='right',fill='y');self.tree.pack(side='left',fill='both',expand=True)
        hbar.pack(fill='x')
        self.tree.tag_configure('live_active',background='#FFF0B3',foreground='#785000')
        self.tree.tag_configure('live_ok',background='#DAF5E3',foreground='#115C3D')
        self.tree.tag_configure('live_failed',background='#FDE2E2',foreground='#9B1C1C')
        self.tree.bind('<<TreeviewSelect>>',self._on_selection)
        self.runner.tree.configure(height=5)
        self.runner.log.configure(height=7)
        # Keep the existing local stop button, but update its old-tab guidance.
        for widget in self.runner.single.master.winfo_children():
            if isinstance(widget,ttk.Button) and widget.cget('text')=='Stop local monitoring':
                widget.configure(command=self.stop_local)
        self._buttons()

    def _buttons(self):
        connected=self.studio.ssh.connected()
        state=self._selected_state()
        ready=connected and not self.busy
        self.refresh_btn.configure(state='normal' if ready and not self.poll_busy else 'disabled')
        selected=self.by_id.get(self._selected_id(),{})
        modern=selected.get('kind') in ('test94','test94-cloudv','test95','test96','test97','test98','test99','test100','test101','test102','test103','test104','test105','test106')
        downloadable=selected.get('state')=='completed' and selected.get('validated') and selected.get('packet')
        self.sync_btn.configure(state='normal' if ready and state and (not modern or downloadable) else 'disabled')
        self.stop_btn.configure(state='normal' if ready and state and state not in TERMINAL and selected.get('kind') not in ('test94','test96','test94-cloudv','test95','test97','test98','test99','test100','test101','test102','test103','test104','test105','test106') else 'disabled')

    def _selected_id(self):
        values=self.tree.selection()
        return str(values[0]) if values else None

    def show_details(self):
        item=self.by_id.get(self._selected_id())
        if item is None:
            messagebox.showinfo('Campaign details','Select a campaign first.');return
        messagebox.showinfo('Campaign details',campaign_details(item))

    def _selected_state(self):
        item=self.by_id.get(self._selected_id())
        return str(item.get('state') or '?') if item is not None else None

    def _on_selection(self,_event=None):
        runid=self._selected_id()
        if runid:
            row=self.by_id.get(runid,{})
            self.runner.run_id.set(runid if not row.get('kind') else '')
            self.runner.remote_status.set(
                f"{readable_test(row)} · {campaign_state(row)} · {campaign_elapsed(row)} · "
                f"{row.get('observations',0)} observations · {runid} · "
                f"variant {row.get('current_candidate') or '—'} · "
                f"disk {row.get('disk_free_gib') if row.get('disk_free_gib') is not None else '—'} GiB")
        self._buttons()
        self._highlight_selection()

    def _highlight_selection(self):
        tags=[str(tag) for iid in self.tree.selection() if self.tree.exists(iid)
              for tag in self.tree.item(iid,'tags')]
        if 'live_failed' in tags:bg,fg='#F3B1B1','#781212'
        elif 'live_active' in tags:bg,fg='#FFE082','#563D00'
        elif 'live_ok' in tags:bg,fg='#B4E8C7','#0F5030'
        else:bg,fg='#3470A4','#FFFFFF'
        self.live_style.map('RVVLiveCampaigns.Treeview',background=[('selected',bg)],foreground=[('selected',fg)])

    def refresh_remote(self):
        """Called by the existing TestRunnerPanel minute timer, never launches a job."""
        if self.poll_busy or self.busy:return
        if not self.studio.ssh.connected():
            self.status.set('SSH disconnected')
            self.runner.remote_status.set('SSH disconnected; local monitoring only.')
            self._buttons()
            return
        self.poll_busy=True
        self.status.set('Refreshing...')
        self._buttons()
        def work():
            try:
                rows=remote_runs(self.studio.ssh,self._remote_name())
                if self.studio.active_profile=='EPCC':
                    rows+=discover_epcc_runs(self.studio.ssh,self._remote_name())
                self.events.put(('rows',sorted(rows,key=lambda x:x.get('id',''),reverse=True)))
            except Exception as e:
                self.events.put(('error','Error reading campaigns: '+str(e)))
        threading.Thread(target=work,daemon=True).start()

    def clear_verified_campaigns(self):
        self.verified_by_profile={}
        self._set_rows(self.history_rows)

    def apply_verified_campaigns(self,profile,data,processes):
        '''Display the same 94/95/96/97 status already read for Tests.'''
        if self.studio.active_profile!=profile:return
        entries=[]
        for number,items in (data or {}).items():
            for item in items:
                kind='test94-cloudv' if number=='94' and profile=='Cloud-V' else 'test'+number
                entries.append({
                    'id':item['id'],'kind':kind,'campaign':'test'+number,
                    'state':item['state'],'observations':item.get('rows',0),
                    'packet':item.get('packet',False),'validated':item.get('validated',False),
                    'source_path':item.get('path',''),
                    'test_id':{'94':'machine-compare-94-1h','95':'test95-cloudv-8h',
                               '96':'test96-epcc-8h','97':('test97-epcc-v5-3h' if profile=='EPCC' else 'test97-cloudv-8h'), '98':'test98-real-corpus','99':'test99-public-8h','100':'test100-adaptive-public','101':'test101-dispatch-validation','102':'test102-escape-stage','103':'test103-stage2-optimization','104':'test104-independent-public-validation','105':'test105-cross-compiler-stage2','106':'test106-vectorpath-release-validation'}[number],
                    'started_utc':None,'phase':item['state'],
                })
        # A process may be visible before the test97-runs directory exists.
        if profile=='Cloud-V' and processes and not (data or {}).get('97'):
            entries.append({'id':'test97-process-confirmed','kind':'test97',
                            'campaign':'test97','state':'building',
                            'observations':0,'validated':False,'packet':False,
                            'phase':'processus actif','test_id':'test97-cloudv-8h'})
        self.verified_by_profile[profile]=entries
        self._set_rows(self.history_rows)

    def _set_rows(self,rows):
        # Historical NightRuns and current modern tests in ONE campaign view.
        profile=self.studio.active_profile
        known={r.get('id'):r for r in rows if r.get('id')}
        # Prefer verified SimpleTests state to a stale NightRuns/EPCC discovery row.
        for item in self.verified_by_profile.get(profile,[]):
            known[item['id']]=item
        rows=sorted(known.values(),key=lambda r:str(r.get('id') or ''),reverse=True)
        self.rows=rows
        self.by_id={r['id']:r for r in rows if r.get('id')}
        previous=self._selected_id() or self.runner.run_id.get().strip()
        self.tree.delete(*self.tree.get_children())
        rows_formatted=display_rows(rows)
        selected=None
        for row,vals in zip(rows,rows_formatted):
            runid=str(row.get('id') or '')
            if not runid:continue
            current=str(row.get('state','')).lower()
            if row.get('validated') and row.get('packet') and current=='completed':tag='live_ok'
            elif current in ('failed','safety_stop'):tag='live_failed'
            elif current in ('building','build','preparing','running','train','holdout','queued','pending','exploring'):tag='live_active'
            else:tag=''
            iid=self.tree.insert('','end',iid=runid,values=vals,tags=(tag,) if tag else ())
            if runid==previous:selected=iid
        if selected is None and rows_formatted:
            # Prefer an active run over a completed/historical one on first open.
            for iid in self.tree.get_children():
                if str(self.by_id.get(iid,{}).get('state') or '') not in TERMINAL:
                    selected=iid;break
            if selected is None:selected=self.tree.get_children()[0]
        if selected:
            self.tree.selection_set(selected)
            self.tree.see(selected)
            self._on_selection()
        else:
            self.runner.remote_status.set('No NightRuns or EPCC Test94/Test96 campaigns found.')
        active=sum(1 for x in rows if x.get('state') not in TERMINAL)
        self.status.set(f'{len(rows)} campaigns · {active} still active')
        self._buttons()
        self._highlight_selection()

    def _action(self,action):
        if self.busy or self.poll_busy:return
        runid=self._selected_id()
        if not runid:
            messagebox.showinfo('Campaign','Select a campaign in the table.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connecte Studio avant toute action.');return
        if action=='stop':
            if self.by_id.get(runid,{}).get('kind') in ('test94','test96','test94-cloudv','test95','test97','test98','test99','test100','test101','test102','test103','test104','test105','test106'):
                messagebox.showinfo('Slurm', 'EPCC runs cannot be stopped automatically here. Check the job and use Slurm tools.');return
            if self._selected_state() in TERMINAL:
                messagebox.showinfo('Campaign','This campaign has already finished.');return
            if not messagebox.askyesno('Confirm graceful stop',
                f'Request a graceful stop for:\n\n{runid}\n\n'
                'The worker will stop at its next checkpoint. No files will be deleted.'):
                return
        chosen=self.by_id.get(runid,{})
        if action=='sync' and chosen.get('kind') in ('test94','test96','test94-cloudv','test95','test97','test98','test99','test100','test101','test102','test103','test104','test105','test106'):
            if chosen.get('state')!='completed' or not chosen.get('validated') or not chosen.get('packet'):
                messagebox.showinfo('Result unavailable','The run must be completed and validated before Download.')
                return
            simple=getattr(self.studio,'simple_tests',None)
            if simple is None:
                messagebox.showerror('Tests','Use the Tests tab to download this run.')
                return
            number=re.search(r'test(\d+)',str(chosen['kind'])).group(1)
            if simple.profile!=self.studio.active_profile:simple.profile_changed()
            if not simple.remote_checked or not any(x.get('id')==runid for x in simple.runs.get(number,[])):
                simple.refresh()
                messagebox.showinfo('Verification','Server check started. Retry Sync results in a few seconds.')
                return
            simple.tree.selection_set(number)
            simple.selection.set(runid)
            simple._selected()
            simple.download()
            return
        self.busy=True
        self.status.set('Stopping...' if action=='stop' else 'Downloading...')
        self._buttons()
        def work():
            try:
                remote=self._remote_name()
                if action=='stop':
                    # Check fresh state to avoid STOP on a newly completed run.
                    matches=[x for x in remote_runs(self.studio.ssh,remote) if x.get('id')==runid]
                    if not matches:raise RuntimeError('Campaign not found on the server')
                    if matches[0].get('state') in TERMINAL:
                        self.events.put(('info',f'{runid} is already finished; STOP was not written.'))
                    else:
                        request_stop(self.studio.ssh,remote,runid)
                        self.events.put(('info',f'Graceful stop requested: {runid}'))
                else:
                    root=Path(self.studio.vars['results'].get()).expanduser()
                    entry=self.by_id.get(runid,{})
                    if entry.get('kind') in ('test94','test96','test97') and self.studio.active_profile=='EPCC':
                        if not entry.get('packet'):
                            raise RuntimeError('Aucune archive ZIP distante confirmede pour ce test (consulter les journaux).')
                        path=sync_epcc_run(self.studio.ssh,remote,runid,root)
                    else:path=sync_results(self.studio.ssh,remote,runid,root)
                    self.events.put(('info','SHA256-verified results synced: '+str(path)))
            except Exception as e:
                self.events.put(('error',f'{action} {runid}: {e}'))
            finally:
                self.events.put(('done',None))
        threading.Thread(target=work,daemon=True).start()

    def stop_local(self):
        self.runner.stop_event.set()
        self.runner._log('Local monitoring/execution stopped. To stop a remote campaign, select its row and click Request Stop.')

    def sync_selected(self):self._action('sync')
    def stop_selected(self):self._action('stop')

    def open_results(self):
        run=self.by_id.get(self._selected_id(),{})
        if run.get('kind') in ('test94','test96','test94-cloudv','test95','test97','test98','test99','test100','test101','test102','test103','test104','test105','test106'):
            n={'test94':'94','test94-cloudv':'94','test95':'95','test96':'96','test97':'97','test98':'98','test99':'99','test100':'100','test101':'101','test102':'102','test103':'103','test104':'104','test105':'105','test106':'106'}[run['kind']]
            simple=getattr(self.studio,'simple_tests',None)
            p=(simple._packet_dir(n,run['id']) if simple else
               Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/run['test_id'])
            if not p.exists():
                messagebox.showinfo('Results','This EPCC result has not been downloaded yet.');return
        else:p=Path(self.studio.vars['results'].get()).expanduser()/'NightRuns'
        p.mkdir(parents=True,exist_ok=True)
        import os
        if hasattr(os,'startfile'):os.startfile(str(p))
        else:messagebox.showinfo('Cartes locales',str(p))

    def _drain(self):
        try:
            for _ in range(80):
                try:kind,data=self.events.get_nowait()
                except queue.Empty:break
                if kind=='rows':
                    self.poll_busy=False
                    self.history_rows=data
                    self._set_rows(data)
                elif kind=='error':
                    self.poll_busy=False
                    if any(x in data for x in ('10054','EOFError','SSH session not active','Socket is closed')):
                        self.status.set('SSH interrupted — reconnect / refresh')
                        self.runner._log('CAMPAIGN: SSH connection interrupted while refreshing; previously synchronized results remain valid. Reconnect, then Refresh campaigns. '+data)
                    else:
                        self.status.set('Error (see log)')
                        self.runner._log('CAMPAIGN ERROR: '+data)
                elif kind=='info':
                    self.runner._log('CAMPAIGN: '+data)
                    self.status.set('Action completed')
                elif kind=='done':
                    self.busy=False
                    self.refresh_remote()
            self._buttons()
        finally:
            self.runner.parent.after(250,self._drain)
