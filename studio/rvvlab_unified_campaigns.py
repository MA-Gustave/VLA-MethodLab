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

TERMINAL = frozenset({'stopped', 'failed', 'completed', 'complete', 'finished',
                       'done', 'safety_stop', 'timeout', 'cancelled'})


def readable_test(row):
    """Identify Studio/CLI campaigns without guessing from timestamped run IDs."""
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
    return 'Non identifié'


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
    match=re.fullmatch(r'night-(\d{8}T\d{6})Z-[0-9a-f]{6}',str(row.get('id') or ''))
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
    if state in ('completed','complete','finished','done','stopped'):return 'Finished'
    if state=='failed':return 'Failed'
    if state in TERMINAL:return state.replace('_',' ').title()
    if state in ('starting','launch_incomplete','preflight'):return 'Starting'
    return 'Running' if state else 'Unknown'


def campaign_phase(row):
    phase=str(row.get('experiment_phase') or '').strip()
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
       'Stop reason: '+str(row.get('stop_reason') or '—'),
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
        self.sync_btn.configure(state='normal' if ready and state else 'disabled')
        self.stop_btn.configure(state='normal' if ready and state and state not in TERMINAL else 'disabled')

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
            self.runner.run_id.set(runid)
            row=self.by_id.get(runid,{})
            self.runner.remote_status.set(
                f"{readable_test(row)} · {campaign_state(row)} · {campaign_elapsed(row)} · "
                f"{row.get('observations',0)} observations · {runid} · "
                f"variant {row.get('current_candidate') or '—'} · "
                f"disk {row.get('disk_free_gib') if row.get('disk_free_gib') is not None else '—'} GiB")
        self._buttons()

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
                self.events.put(('rows',rows))
            except Exception as e:
                self.events.put(('error','Error reading campaigns: '+str(e)))
        threading.Thread(target=work,daemon=True).start()

    def _set_rows(self,rows):
        self.rows=rows
        self.by_id={r['id']:r for r in rows if r.get('id')}
        previous=self._selected_id() or self.runner.run_id.get().strip()
        self.tree.delete(*self.tree.get_children())
        rows_formatted=display_rows(rows)
        selected=None
        for row,vals in zip(rows,rows_formatted):
            runid=str(row.get('id') or '')
            if not runid:continue
            iid=self.tree.insert('','end',iid=runid,values=vals)
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
            self.runner.remote_status.set('No campaigns in the remote folder.')
        active=sum(1 for x in rows if x.get('state') not in TERMINAL)
        self.status.set(f'{len(rows)} campaigns · {active} still active')
        self._buttons()

    def _action(self,action):
        if self.busy or self.poll_busy:return
        runid=self._selected_id()
        if not runid:
            messagebox.showinfo('Campaign','Select a campaign in the table.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connecte Studio avant toute action.');return
        if action=='stop':
            if self._selected_state() in TERMINAL:
                messagebox.showinfo('Campaign','This campaign has already finished.');return
            if not messagebox.askyesno('Confirm graceful stop',
                f'Request a graceful stop for:\n\n{runid}\n\n'
                'The worker will stop at its next checkpoint. No files will be deleted.'):
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
                    path=sync_results(self.studio.ssh,remote,runid,root)
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
        p=Path(self.studio.vars['results'].get()).expanduser()/'NightRuns'
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
