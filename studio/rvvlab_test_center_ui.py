"""Tk all-tests control panel. All network and disk-heavy tasks run outside Tk."""
from __future__ import annotations
import json
import time
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox,ttk
from rvvlab_test_center import (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY,check_remote_night,inspect_remote_94,
                                label,local_state,merge)
from rvvlab_epcc_results import discover_epcc_runs,select_test_run,sync_epcc_run

class TestCenterPanel:
    def __init__(self,parent,studio):
        self.parent=parent;self.studio=studio
        self.search=tk.StringVar(value='');self.state_filter=tk.StringVar(value='All states')
        self.notice=tk.StringVar(value='Local statuses loaded. Connect SSH, then click Check server.')
        self.stats=tk.StringVar(value='')
        self.title=tk.StringVar(value='Select a test')
        self.summary=tk.StringVar(value='No selection')
        self.evidence=tk.StringVar(value='')
        self.actions=tk.StringVar(value='')
        self.data={};self.remote={};self.remote94=None
        self.busy=False;self.server_checked=False;self.pending94=False;self.checked_at=None
        self.messages=queue.Queue();self._create()
        self.refresh_local()
        self.parent.after(250,self._events)

    def _create(self):
        p=self.parent
        header=ttk.Frame(p);header.pack(fill='x',pady=(0,12))
        ttk.Label(header,text='Test Center',font=('Segoe UI',18,'bold')).pack(side='left')
        ttk.Label(header,text='All profiles · verifiable evidence · no automatic relaunch',
                  foreground='#687382').pack(side='left',padx=(20,0))
        top=ttk.Frame(p);top.pack(fill='x',pady=(0,9))
        ttk.Label(top,textvariable=self.stats,font=('Segoe UI',11,'bold')).pack(side='left')
        ttk.Label(top,text='Machine: '+self.studio.active_profile,foreground='#526579').pack(side='right')
        bar=ttk.Frame(p);bar.pack(fill='x',pady=(0,7))
        ttk.Label(bar,text='Search').pack(side='left')
        ttk.Entry(bar,textvariable=self.search,width=28).pack(side='left',fill='x',expand=True,padx=(7,15))
        cb=ttk.Combobox(bar,textvariable=self.state_filter,state='readonly',width=20,values=(
            'All states','Downloaded','Completed on server','Running','Failures','Needs verification'))
        cb.pack(side='left',padx=(0,7))
        ttk.Button(bar,text='Clear',command=self._clear).pack(side='left')
        controls=ttk.Frame(p);controls.pack(fill='x',pady=(0,8))
        self.refresh_button=ttk.Button(controls,text='Refresh local',command=self.refresh_local)
        self.refresh_button.pack(side='left',padx=(0,7))
        self.check_button=ttk.Button(controls,text='Check server',command=self.check_remote)
        self.check_button.pack(side='left',padx=(0,7))
        self.download_button=ttk.Button(controls,text='Download / Sync',command=self.download)
        self.download_button.pack(side='left',padx=(0,7))
        self.open_button=ttk.Button(controls,text='Open results',command=self.open_results)
        self.open_button.pack(side='left',padx=(0,7))
        self.run_button=ttk.Button(controls,text='Run selected test…',command=self.run)
        self.run_button.pack(side='right')
        cols=('number','test','state','evidence')
        frame=ttk.Frame(p);frame.pack(fill='both',expand=True)
        frame.columnconfigure(0,weight=4);frame.columnconfigure(1,weight=2)
        frame.rowconfigure(0,weight=1)
        box=ttk.Frame(frame);box.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.tree=ttk.Treeview(box,columns=cols,show='headings',height=13,selectmode='browse')
        for col,heading,width in [('number','No.',62),('test','Experiment',260),('state','Status',160),('evidence','Evidence',235)]:
            self.tree.heading(col,text=heading)
            self.tree.column(col,width=width,minwidth=42,stretch=(col!='number'),anchor='w')
        self.tree.tag_configure('done',foreground='#17774d')
        self.tree.tag_configure('active',foreground='#15599b')
        self.tree.tag_configure('bad',foreground='#ae3d3d')
        self.tree.tag_configure('unknown',foreground='#555')
        y=ttk.Scrollbar(box,orient='vertical',command=self.tree.yview)
        x=ttk.Scrollbar(box,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        y.pack(side='right',fill='y');x.pack(side='bottom',fill='x')
        self.tree.pack(side='left',fill='both',expand=True)
        self.tree.bind('<<TreeviewSelect>>',lambda _:self._details())
        self.tree.bind('<Double-1>',lambda _:self.open_results())
        pane=ttk.LabelFrame(frame,text='Selected test details',padding=13)
        pane.grid(row=0,column=1,sticky='nsew')
        ttk.Label(pane,textvariable=self.title,font=('Segoe UI',12,'bold'),wraplength=320).pack(anchor='w',pady=(3,14))
        ttk.Label(pane,textvariable=self.summary,font=('Segoe UI',11,'bold'),wraplength=300).pack(anchor='w',pady=(0,9))
        ttk.Label(pane,text='What is actually confirmed',foreground='#5b6571').pack(anchor='w',pady=(12,4))
        ttk.Label(pane,textvariable=self.evidence,wraplength=320,justify='left').pack(anchor='w')
        ttk.Separator(pane).pack(fill='x',pady=14)
        ttk.Label(pane,text='Next action',foreground='#5b6571').pack(anchor='w',pady=(2,4))
        ttk.Label(pane,textvariable=self.actions,wraplength=320,justify='left').pack(anchor='w')
        ttk.Button(pane,text='Open Test Runner and logs',
                   command=lambda:self.studio.open_advanced(self.studio.test_runner_tab)).pack(anchor='w',pady=(25,0))
        footer=ttk.Frame(p);footer.pack(fill='x',pady=(10,0))
        ttk.Label(footer,textvariable=self.notice,foreground='#40546c',wraplength=980).pack(anchor='w')
        ttk.Label(footer,text='Local PASS ≠ completed on server. Local ZIP ≠ full JSON validation.',
                  foreground='#687382').pack(anchor='w',pady=(5,0))
        self.search.trace_add('write',lambda *_:self._redraw())
        self.state_filter.trace_add('write',lambda *_:self._redraw())

    def _clear(self):self.search.set('');self.state_filter.set('All states')

    def _selection(self):
        sel=self.tree.selection()
        return sel[0] if sel else None

    def _records(self):
        return list(getattr(self.studio.test_runner,'items',[]))

    def refresh_local(self):
        results=Path(self.studio.vars['results'].get()).expanduser()
        history=self.studio.test_runner.history
        self.data={item['id']:local_state(item,results,history) for item in self._records()}
        self._redraw()

    def _effective(self,key):
        state=self.data.get(key,{'test_id':key,'state':'unknown','proof':'Sans historique','downloaded':False,'directory':'','run_id':''})
        merged=merge(state,self.remote.get(key)) if key in self.remote else dict(state)
        # Active/queued states are snapshots, never a durable live claim.
        if key in self.remote and merged['state'] in ('running','queued'):
            age=(time.monotonic()-self.checked_at) if self.checked_at is not None else 10**9
            if age>120 or not self.studio.ssh.connected():
                merged.update(state='unknown',proof='Old active status; new SSH check required')
        # A completed/partial NightRuns snapshot may have been recovered outside
        # TestRunner (old runs, different Studio versions). Honor SHA256 marker.
        if key!=TEST94_KEY and key in self.remote:
            runid=str(self.remote[key].get('id',''))
            from rvvlab_test_center import NIGHT_ID
            if NIGHT_ID.fullmatch(runid):
                path=Path(self.studio.vars['results'].get()).expanduser()/'NightRuns'/runid
                if (path/'SYNC_OK.txt').is_file():
                    merged.update(state='downloaded',downloaded=True,directory=str(path),
                        proof='Snapshot SHA256 verified sur PC'+
                        (' · campagne stopped (partielle)' if str(self.remote[key].get('state'))=='stopped' else ''))
        return merged

    def _redraw(self):
        if not hasattr(self,'tree'):return
        before=self._selection()
        search=self.search.get().casefold().strip()
        statefilter=self.state_filter.get()
        self.tree.delete(*self.tree.get_children())
        stats={'downloaded':0,'completed':0,'running':0,'queued':0,'building':0,'failed':0,'unknown':0,'local_pass':0,'stopped':0}
        for item in self._records():
            key=item['id'];state=self._effective(key)
            typ=state['state'];stats[typ]=stats.get(typ,0)+1
            name=item['title']
            if search and search not in (key+' '+name+' '+str(item['script_path'].name)).casefold():continue
            if statefilter=='Downloaded' and typ!='downloaded':continue
            if statefilter=='Completed on server' and typ!='completed':continue
            if statefilter=='Running' and typ not in ('running','queued','building'):continue
            if statefilter=='Failures' and typ not in ('failed','stopped'):continue
            if statefilter=='Needs verification' and typ not in ('unknown','local_pass'):continue
            match=__import__('re').match(r'^(\d+)',item['script_path'].stem)
            number=match.group(1) if match else '—'
            tag=('done' if typ in ('downloaded','completed') else 'active' if typ in ('running','queued','building')
                 else 'bad' if typ in ('failed','stopped') else 'unknown')
            self.tree.insert('','end',iid=key,values=(number,name,label(typ),state['proof']),tags=(tag,))
        self.stats.set(f"{len(self._records())} tests  ·  {stats['downloaded']} downloaded  ·  {stats['completed']} completed on server  ·  "
                       f"{stats['running']+stats['queued']+stats['building']} active  ·  {stats['failed']} failed")
        chosen=before if before in self.tree.get_children() else (self.tree.get_children()[0] if self.tree.get_children() else '')
        if chosen:self.tree.selection_set(chosen);self.tree.see(chosen)
        self._details()

    def _details(self):
        key=self._selection()
        if key is None:
            self.title.set('No test selected');self.summary.set('');self.evidence.set('');self.actions.set('');return
        state=self._effective(key)
        item=next((v for v in self._records() if v['id']==key),None)
        self.title.set(item['title'] if item else key)
        self.summary.set(label(state['state'])+'  ·  '+self.studio.active_profile)
        self.evidence.set(state['proof']+'\n\n'+('Last known remote check (snapshot).' if key in self.remote else 'Local data only.')+
                          ('\nDossier: '+Path(state['directory']).name if state.get('directory') else '')+
                          ('\nRun: '+state['run_id'] if state.get('run_id') else ''))
        if state['state']=='downloaded':nextstep='Results available on PC. Open to analyze.'
        elif state['state']=='completed':nextstep='Remote result confirmed. Click Download / Sync.'
        elif state['state'] in ('running','queued','building'):nextstep='Do not run again. Check again later.'
        elif state['state']=='failed':nextstep='Review the log, then retry if appropriate.'
        else:nextstep='Check server avant de conclure ou de lancer.'
        self.actions.set(nextstep)

    def check_remote(self):
        if (self.busy or self.studio.test_runner.busy or self.studio.night_busy or self.studio.storage_busy
                or self.studio.job_busy or self.studio.unified_campaigns.busy):
            self.notice.set('Operation in progress. Try again later.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connect this instance before checking tests.');return
        self.busy=True;self.notice.set('Verification in progress : NightRuns + tests EPCC 94/96/97 (lecture seule)…')
        ssh=self.studio.ssh;items=self._records();profile=self.studio.active_profile
        remote_name=self.studio.vars['remote_name'].get().strip()
        results=Path(self.studio.vars['results'].get()).expanduser()
        history=dict(self.studio.test_runner.history)
        def worker():
            try:
                mapping,runs=check_remote_night(ssh,remote_name,items,results,history)
                epcc=discover_epcc_runs(ssh,remote_name) if profile=='EPCC' else []
                try:detail94=inspect_remote_94(ssh,remote_name,profile)
                except Exception as ex:
                    detail94={'state':'unknown','id':'','packet':False,
                              'proof':'Diagnostic Test94 indisponible : '+str(ex)[:120]}
                self.messages.put(('check_ok',(mapping,runs,detail94,epcc)))
            except Exception as ex:self.messages.put(('check_error',str(ex)))
        threading.Thread(target=worker,daemon=True).start()

    def _events(self):
        try:
            while True:
                try:event,data=self.messages.get_nowait()
                except queue.Empty:break
                if event=='check_ok':
                    mapping,runs,test94,epcc=data;self.busy=False;self.server_checked=True;self.checked_at=time.monotonic()
                    self.remote=dict(mapping);self.remote94=test94
                    if test94.get('id'):
                        self.remote[TEST94_KEY]=test94
                        self.remote[TEST94_KEY]['state']=test94.get('state','unknown')
                    if self.studio.active_profile=='EPCC':
                        epcc94=select_test_run(epcc,'test94')
                        epcc96=select_test_run(epcc,'test96')
                        epcc97=select_test_run(epcc,'test97')
                        if epcc94:self.remote[TEST94_KEY]=epcc94
                        if epcc96:self.remote[TEST96_KEY]=epcc96
                        if epcc97:self.remote[TEST97_KEY]=epcc97
                        epcc98=select_test_run(epcc,'test98')
                        if epcc98:self.remote[TEST98_KEY]=epcc98
                    # Remote inventory is a temporary UI snapshot, never silently
                    # overwrite the local benchmark validation or PASS evidence.
                    self.notice.set(f'Server verification finished: {len(runs)} NightRuns campaigns, '
                                    f'{len(mapping)} linked to a test; Test 94: {test94.get("state","unknown")}; '
                                    f'{len(epcc)} EPCC runs detected.')
                    # The persistent badge and the Test Center must use the
                    # SAME freshly established EPCC evidence. A stale local
                    # 'Waiting for Slurm' must not survive an observed error.
                    if test94.get('id') and not self.studio.test_runner.busy:
                        outcome=test94.get('state','unknown')
                        badge='warning' if outcome=='unknown' else 'build' if outcome=='building' else outcome
                        self.studio.report_test94_state(self.studio.active_profile,badge,
                            test94.get('proof',''),verified=True)
                    self.refresh_local()
                    if self.pending94:
                        self.pending94=False
                        self._after_check94(test94)
                elif event=='sync_ok':
                    self.busy=False
                    self.notice.set('EPCC results downloaded and SHA-256 verified: '+data)
                    self.refresh_local()
                    if hasattr(self.studio,'unified_campaigns'):
                        self.studio.unified_campaigns.refresh_remote()
                elif event=='sync_error':
                    self.busy=False
                    self.notice.set('EPCC download rejected: '+str(data)[:220])
                    messagebox.showerror('Download EPCC',str(data))
                elif event=='check_error':
                    self.busy=False;self.pending94=False
                    self.notice.set('SSH verification failed: '+str(data)[:160]+' — previous status unconfirmed; no test launched.')
            self.parent.after(250,self._events)
        except tk.TclError:return

    def _item_and_state(self):
        key=self._selection();item=next((i for i in self._records() if i['id']==key),None)
        return (item,self._effective(key)) if item else (None,None)

    def open_results(self):
        item,state=self._item_and_state()
        if item is None:return
        target=Path(state['directory']) if state['directory'] else Path(self.studio.vars['results'].get()).expanduser()/'TestRunner'/item['id']
        if not target.exists():
            messagebox.showinfo('Results','No local results for this test. Check the server and sync.');return
        if __import__('sys').platform=='win32':__import__('os').startfile(str(target))
        else:messagebox.showinfo('Results directory',str(target))

    def download(self):
        item,state=self._item_and_state()
        if item is None:return
        if state['downloaded'] and not (self.studio.active_profile=='EPCC'
                and item['id'] in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY)
                and self.remote.get(item['id'],{}).get('packet')
                and self.remote[item['id']]['id']!=state.get('run_id')):
            self.open_results();return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connect SSH and check the server before downloading.');return
        if self.busy:
            self.notice.set('An operation is already running.');return
        # Test94, Test96 and Test97 have their own EPCC directories, not NightRuns.
        if self.studio.active_profile=='EPCC' and item['id'] in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY):
            record=self.remote.get(item['id'])
            if not record or not record.get('id'):
                messagebox.showinfo('Synchronisation EPCC',
                    'Check the server: no EPCC run associated with the selected test.');return
            if not record.get('packet'):
                messagebox.showinfo('Synchronisation EPCC',
                    'EPCC run found: '+record['id']+'\n'
                    'But no results archive exists yet. Check Slurm or build logs.');return
            runid=record['id']
            self.busy=True
            self.notice.set('Downloading EPCC (SHA-256): '+runid+'…')
            ssh=self.studio.ssh
            remote=self.studio.vars['remote_name'].get().strip()
            results=Path(self.studio.vars['results'].get()).expanduser()
            def worker():
                try:
                    folder=sync_epcc_run(ssh,remote,runid,results)
                    self.messages.put(('sync_ok',str(folder)))
                except Exception as ex:self.messages.put(('sync_error',str(ex)))
            threading.Thread(target=worker,daemon=True).start()
            return
        if item['id']==TEST94_KEY:
            if not self.remote94 or not self.remote94.get('id') or not self.remote94.get('packet'):
                messagebox.showinfo('Test94','Click Check server. No confirmed Test 94 archive is currently available.');return
            self.studio.remote94_last=dict(self.remote94)
            self.studio.open_advanced(self.studio.test_runner_tab)
            self.studio.test_runner.recover_test94();return
        run_id=state.get('run_id')
        if not run_id or item['id'] not in self.remote:
            messagebox.showinfo('Synchronisation',
                'No verified run ID for this test.\n'
                'Click Check server, then select a run. '
                'No data will be downloaded without a reliable match.')
            return
        self.notice.set('SHA-256 sync for '+run_id+'…')
        self.studio._night_run('sync',run_id)

    def request_launch94(self):
        """Always get a *fresh* remote check before allowing a 1h launch."""
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connect SSH before running Test 94.');return
        if self.busy or self.pending94:
            messagebox.showinfo('Verification','A verification is already running.');return
        self.pending94=True
        self.check_remote()
        if not self.busy:self.pending94=False

    def _after_check94(self,remote):
        state=str(remote.get('state') or 'unknown')
        if state in ('completed','running','queued','building') and (state!='completed' or remote.get('packet')):
            messagebox.showinfo('Test 94 duplicate-run guard',
                'Test 94 already '+state+' on '+self.studio.active_profile+' : no second launch.\n'
                'You can check or download the results.');return
        if state=='unknown' and remote.get('id'):
            if not messagebox.askyesno('Remote status uncertain',
                'A Test 94 attempt exists on the server, without proven completion or an active job.\n'
                'A new run might duplicate work that is not visible.\n\n'
                'Continue to launch confirmation?'):return
        self.studio.open_advanced(self.studio.test_runner_tab)
        self.studio.test_runner._run_test94_after_remote_check()

    def run(self):
        item,state=self._item_and_state()
        if item is None:return
        if not item['enabled']:
            messagebox.showwarning('Test disabled','This test manifest is disabled. Nothing will be launched.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connect SSH before running.');return
        if item['id']==TEST94_KEY:
            self.request_launch94();return
        if state['state'] in ('running','queued'):
            messagebox.showwarning('Active test','The latest check found an active job. No duplicate will be launched.');return
        if not messagebox.askyesno('Confirmation',
            'Run '+item['title']+' on '+self.studio.active_profile+' ?\n\n'
            'This operation may occupy the server for several hours. '
            'The displayed status alone cannot prove the absence of other work.'):return
        self.studio.open_advanced(self.studio.test_runner_tab)
        self.studio.test_runner._run([item])
