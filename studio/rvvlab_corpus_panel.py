"""Single shared corpus library screen; deliberately no independent SSH session."""
from __future__ import annotations
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox,ttk

from rvvlab_corpus_service import (LAB,catalog,SUITE_LABELS,inspect_local,prepare_local,
                                   remote_probe,require_remote,sync_remote,cache_dir)

class CorpusLibraryPanel:
    def __init__(self,parent,studio):
        self.parent=parent;self.studio=studio
        self.busy=False
        self.local_info={'state':'absent'}
        self.events=queue.Queue()
        self.suite=tk.StringVar(value='performance')
        self.per_machine={(machine,suite):'Not checked' for machine in ('Cloud-V','EPCC') for suite in SUITE_LABELS}
        self.local=tk.StringVar(value='Local verification required')
        self.remote=tk.StringVar(value='Connect to a machine, then click Check server')
        self.notice=tk.StringVar(value='The shared corpus is optional for historical tests; historical measurements remain unchanged.')
        self.availability=tk.StringVar(value='Checking SSH availability…')
        self._journal_window=None
        self._journal_text=None
        self._journal_suite=None
        self._journal_status=None
        self._journal_errors={}
        self._last_displayed_log=None
        self._auto_open_logs=True
        self._build()
        self.profile_changed()
        parent.after(250,self._drain)
        parent.after(1100,self._refresh_controls)

    def _build(self):
        panel=ttk.Frame(self.parent,style='Surface.TFrame',padding=20)
        panel.pack(fill='both',expand=True,padx=7,pady=7)
        ttk.Label(panel,text='Shared JSON library',style='Section.TLabel').pack(anchor='w',pady=(0,8))
        chooser=ttk.Frame(panel,style='Surface.TFrame');chooser.pack(fill='x',pady=(0,10))
        ttk.Label(chooser,text='Category:',style='Muted.TLabel').pack(side='left',padx=(0,10))
        self.selector=ttk.Combobox(chooser,state='readonly',width=37,values=list(SUITE_LABELS.values()))
        self.selector.current(0);self.selector.pack(side='left')
        self.selector.bind('<<ComboboxSelected>>',self._change_suite)
        self.info=tk.StringVar()
        self.source_info=tk.StringVar()
        ttk.Label(panel,textvariable=self.info,style='Muted.TLabel').pack(anchor='w')
        ttk.Label(panel,textvariable=self.source_info,style='Muted.TLabel').pack(anchor='w',pady=(2,12))
        state=ttk.Frame(panel,style='Surface.TFrame');state.pack(fill='x',pady=6)
        ttk.Label(state,text='PC:',width=11).grid(row=0,column=0,sticky='w',pady=4)
        ttk.Label(state,textvariable=self.local).grid(row=0,column=1,sticky='w')
        ttk.Label(state,text='Server:',width=11).grid(row=1,column=0,sticky='w',pady=4)
        ttk.Label(state,textvariable=self.remote).grid(row=1,column=1,sticky='w')
        bar=ttk.Frame(panel,style='Surface.TFrame');bar.pack(fill='x',pady=(10,12))
        self.prepare_btn=ttk.Button(bar,text='1. Prepare / Verify JSON',command=self.prepare)
        self.prepare_btn.pack(side='left',padx=(0,8))
        self.sync_btn=ttk.Button(bar,text='2. Sync to server',command=self.sync)
        self.sync_btn.pack(side='left',padx=(0,8))
        self.check_btn=ttk.Button(bar,text='Check server',command=self.check)
        self.check_btn.pack(side='left',padx=(0,8))
        ttk.Button(bar,text='Open cache',command=self.open_folder).pack(side='left',padx=(0,8))
        ttk.Button(bar,text='View log / Copy',command=self.open_diagnostic).pack(side='left')
        ttk.Label(panel,textvariable=self.availability,style='Muted.TLabel',wraplength=950).pack(anchor='w',pady=(0,6))
        ttk.Label(panel,text='Selected corpus files — size, SHA-256 and expected outcome',style='CardTitle.TLabel').pack(anchor='w',pady=(7,8))
        tablebox=ttk.Frame(panel,style='Surface.TFrame');tablebox.pack(fill='both',expand=True)
        self.table=ttk.Treeview(tablebox,columns=('name','class','bytes','hash'),show='headings',height=13)
        for col,title,width in [('name','File',300),('class','Expected',120),('bytes','Size',120),('hash','SHA-256',410)]:
            self.table.heading(col,text=title)
            self.table.column(col,width=width,minwidth=80,anchor='w')
        scroll=ttk.Scrollbar(tablebox,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        ttk.Label(panel,textvariable=self.notice,style='Muted.TLabel',wraplength=900).pack(anchor='w',pady=(12,0))

    def _change_suite(self,event=None):
        if self.busy:
            self.selector.set(SUITE_LABELS[self.suite.get()]);return
        label=self.selector.get()
        suite=next((k for k,v in SUITE_LABELS.items() if v==label),'performance')
        self.suite.set(suite)
        self.profile_changed()

    def profile_changed(self):
        p=self.studio.active_profile
        self.remote.set(p+' : '+self.per_machine[p,self.suite.get()])
        self._update_buttons()
        self.inspect()

    def inspect(self):
        suite=self.suite.get(); c=catalog(suite)
        self.info.set(c['description']+' · '+c['id'])
        self.source_info.set('Source: '+c['source']+' · Revision '+c['commit'][:12])
        data=inspect_local(LAB,suite)
        self.local_info=data
        if data['state']=='verified':
            classes=data.get('counts',{})
            labels=(' · y:'+str(classes['accept'])+' n:'+str(classes['reject'])+' i:'+str(classes['implementation']) if suite=='conformance' else '')
            self.local.set('Verified · '+str(data['count'])+' files'+labels+' · '+format(data['total_bytes']/1048576,'.1f')+' MiB · SHA '+data['digest'][:16])
        elif data['state']=='invalid':self.local.set('Invalid: '+data.get('error',''))
        else:self.local.set('Missing — prepare once (Internet required)')
        for id in self.table.get_children():self.table.delete(id)
        for row in data.get('files',[]):
            self.table.insert('', 'end',values=(row['name'],row.get('expected','JSON'),str(row['bytes'])+' bytes',row['sha256']))
        if not data.get('files'):
            for name in catalog(suite)['files']:self.table.insert('','end',values=(name,'—','—','—'))
        self._update_buttons()

    def _remote_blocker(self):
        """Explain why remote actions must wait. No SSH operation is issued here."""
        if not self.studio.ssh.connected():
            return 'SSH disconnected: connect to the selected machine.'
        if getattr(self.studio,'connecting',False):
            return 'SSH connection in progress; please wait.'
        if self.busy:
            return 'Corpus operation in progress; please wait.'
        runner=getattr(self.studio,'test_runner',None)
        simple=getattr(self.studio,'simple_tests',None)
        if ((runner is not None and getattr(runner,'busy',False)) or
            (simple is not None and getattr(simple,'busy',False))):
            return 'A test runner is using SSH; sync is temporarily paused.'
        if ((runner is not None and getattr(runner,'poll_busy',False)) or
            (simple is not None and getattr(simple,'poll_busy',False))):
            return 'Automatic test status check in progress; buttons will re-enable when it finishes.'
        return ''

    def _update_buttons(self):
        ready=self.local_info.get('state')=='verified'
        blocker=self._remote_blocker()
        canremote=ready and not blocker
        self.selector.configure(state='disabled' if self.busy else 'readonly')
        self.prepare_btn.configure(state='disabled' if self.busy else 'normal')
        self.sync_btn.configure(state='normal' if canremote else 'disabled')
        self.check_btn.configure(state='normal' if canremote else 'disabled')
        if not ready:
            reason=('Invalid local corpus: repair the cache before syncing.'
                    if self.local_info.get('state')=='invalid' else
                    'Prepare the corpus on this PC before syncing.')
            self.availability.set(reason)
        elif blocker:
            self.availability.set(blocker)
        else:
            self.availability.set(self.studio.active_profile+
                ' connected · local corpus verified · Sync and Check server available.')

    def _refresh_controls(self):
        """Refresh control state after other panels complete their SSH polls.

        This is UI-only: does not open another SSH channel or change the
        existing 60-second remote polling cadence.
        """
        try:
            self._update_buttons()
        finally:
            self.parent.after(1100,self._refresh_controls)

    def _work(self,which,fn):
        if self.busy:return
        self.busy=True;self._update_buttons()
        p=self.studio.active_profile; suite=self.suite.get()
        def run():
            try:res=fn(suite);self.events.put((which,p,suite,res,None))
            except Exception as e:self.events.put((which,p,suite,None,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def prepare(self):
        self.notice.set('Preparing: verifying the cache and downloading if needed…')
        self.local.set('Preparing — do not start a second download')
        def task(suite):
            return prepare_local(
                LAB, suite=suite,
                log=lambda msg: self.events.put(('progress', self.studio.active_profile, suite, msg, None))
            )
        self._work('prepare',task)

    def sync(self):
        if not self.studio.ssh.connected():return
        name=self.studio.vars['remote_name'].get().strip()
        p=self.studio.active_profile
        self.notice.set('Syncing '+p+' and verifying ZIP…')
        self._work('sync',lambda suite:sync_remote(self.studio.ssh,name,LAB,suite=suite))

    def check(self):
        if not self.studio.ssh.connected():return
        name=self.studio.vars['remote_name'].get().strip()
        self.notice.set('Checking remote server (read-only)…')
        def task(suite):
            v=inspect_local(LAB,suite)
            if v['state']!='verified':return {'state':'unavailable'}
            return remote_probe(self.studio.ssh,name,v['digest'],deep=True,suite=suite)
        self._work('check',task)

    def _diagnostic_path(self,suite):
        return cache_dir(LAB)/('preparation-'+suite+'.log')

    def _diagnostic_text(self,suite):
        """Use the durable log, not a truncated error embedded in a Tk label."""
        path=self._diagnostic_path(suite)
        if path.is_file():
            try:
                with path.open('rb') as stream:
                    # Keep UI responsive even for a pathological log file.
                    size=path.stat().st_size
                    if size>8*1024*1024:
                        stream.seek(-8*1024*1024,os.SEEK_END)
                    content=stream.read().decode('utf-8',errors='replace')
                if size>8*1024*1024:
                    content='[Showing the last 8 MiB only; full log is on disk]\n'+content
                return content or 'Empty log: '+str(path)
            except OSError as exc:
                return 'Unable to read log: '+str(exc)+'\n'+str(path)
        last=getattr(self,'_journal_errors',{}).get(suite)
        if last:
            return ('Persistent log missing. Last reported error:\n\n'+last+
                    '\n\nExpected path: '+str(path))
        return 'No preparation attempt recorded for this corpus.\n\nExpected path: '+str(path)

    def _refresh_diagnostic(self):
        win=getattr(self,'_journal_window',None)
        if win is None or not win.winfo_exists():return
        suite=self._journal_suite
        content=self._diagnostic_text(suite)
        if content==getattr(self,'_last_displayed_log',None):return
        self._last_displayed_log=content
        widget=self._journal_text
        widget.configure(state='normal')
        widget.delete('1.0','end')
        widget.insert('1.0',content)
        widget.configure(state='disabled')
        widget.see('end')
        self._journal_status.set('Log: '+str(self._diagnostic_path(suite)))

    def _copy_diagnostic(self):
        win=getattr(self,'_journal_window',None)
        if win is None or not win.winfo_exists():return
        content=self._journal_text.get('1.0','end-1c')
        try:
            win.clipboard_clear()
            win.clipboard_append(content)
            win.update_idletasks()
            self._journal_status.set('Copied to clipboard · '+str(len(content))+' characters')
        except tk.TclError as exc:
            self._journal_status.set('Copy failed: '+str(exc))

    def _close_diagnostic(self):
        win=getattr(self,'_journal_window',None)
        if win is not None and win.winfo_exists():win.destroy()
        self._journal_window=None
        self._journal_text=None
        self._journal_suite=None
        self._last_displayed_log=None

    def _poll_diagnostic(self):
        win=getattr(self,'_journal_window',None)
        if win is None or not win.winfo_exists():return
        self._refresh_diagnostic()
        win.after(1500,self._poll_diagnostic)

    def open_diagnostic(self):
        """Open a dedicated, resizable, scrollable log with a one-click copy."""
        suite=self.suite.get()
        win=getattr(self,'_journal_window',None)
        if win is not None and win.winfo_exists():
            self._journal_suite=suite
            self._last_displayed_log=None
            win.title('Preparation log — '+SUITE_LABELS[suite])
            self._refresh_diagnostic()
            win.deiconify();win.lift()
            return
        win=tk.Toplevel(self.parent)
        self._journal_window=win
        self._journal_suite=suite
        self._last_displayed_log=None
        win.title('Preparation log — '+SUITE_LABELS[suite])
        win.geometry('940x570')
        win.minsize(520,290)
        win.transient(self.parent.winfo_toplevel())
        win.protocol('WM_DELETE_WINDOW',self._close_diagnostic)
        win.bind('<Escape>',lambda event:self._close_diagnostic())
        body=ttk.Frame(win,padding=12);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Preparation log — '+SUITE_LABELS[suite],font=tkfont.Font(size=12,weight='bold')).pack(anchor='w',pady=(0,6))
        area=ttk.Frame(body);area.pack(fill='both',expand=True)
        output=tk.Text(area,wrap='none',font=('Consolas',10),undo=False,relief='sunken',borderwidth=1)
        self._journal_text=output
        y=ttk.Scrollbar(area,orient='vertical',command=output.yview)
        x=ttk.Scrollbar(area,orient='horizontal',command=output.xview)
        output.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        area.rowconfigure(0,weight=1);area.columnconfigure(0,weight=1)
        output.grid(row=0,column=0,sticky='nsew')
        y.grid(row=0,column=1,sticky='ns')
        x.grid(row=1,column=0,sticky='ew')
        buttons=ttk.Frame(body);buttons.pack(fill='x',pady=(9,4))
        ttk.Button(buttons,text='Copy all',command=self._copy_diagnostic).pack(side='left',padx=(0,8))
        ttk.Button(buttons,text='Refresh',command=self._refresh_diagnostic).pack(side='left')
        ttk.Button(buttons,text='Close',command=self._close_diagnostic).pack(side='right')
        self._journal_status=tk.StringVar(value='')
        ttk.Label(body,textvariable=self._journal_status,wraplength=850).pack(anchor='w',pady=(3,0))
        self._refresh_diagnostic()
        win.after(1500,self._poll_diagnostic)

    def open_folder(self):
        folder=cache_dir(LAB);folder.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':os.startfile(str(folder))
        else:messagebox.showinfo('Local JSON cache',str(folder))

    def _drain(self):
        """Consume worker events on the Tk main thread; always rearm only once.

        Previously a stray `parent.after(...)` raised NameError on the first
        call and permanently stopped processing completed downloads/errors.
        """
        try:
            while True:
                which,p,suite,data,error=self.events.get_nowait()
                if which=='progress':
                    if suite==self.suite.get():
                        self.notice.set('Preparation: '+str(data)[:950])
                    continue
                self.busy=False
                if error:
                    if which=='prepare':
                        getattr(self,'_journal_errors',{}).__setitem__(suite,str(error))
                        brief=str(error).splitlines()[0].split(' | Log:')[0].split(' | Journal :')[0].strip()
                        if 'Traceback' in brief or len(brief)>105:
                            brief='see full diagnostic'
                        self.notice.set('Preparation failed: '+brief+' — click “View log / Copy”.')
                        self.local.set('Preparation failed — see log')
                    else:
                        self.notice.set('Remote check failed — '+str(error)[:180])
                        self.per_machine[p,suite]='Check failed'
                elif which=='prepare':
                    self.notice.set('Corpus '+suite+' verified on this PC; sync is available.')
                else:
                    status=data.get('state','unknown')
                    if status=='verified':
                        self.per_machine[p,suite]='✓ '+str(data.get('count','?'))+' verified files · '+data['data']
                        self.notice.set('Corpus available for tests that require it: '+data['data'])
                    elif status=='absent':
                        self.per_machine[p,suite]='Missing (sync required)'
                        self.notice.set('This server does not have the selected corpus yet.')
                    else:
                        self.per_machine[p,suite]='Incomplete/invalid: '+str(data.get('reason',status))
                        self.notice.set('Sync again to repair the remote cache.')
                self.inspect()
                if error and which=='prepare':
                    self.local.set('Preparation failed — see log')
                    if getattr(self,'_auto_open_logs',False):
                        self.open_diagnostic()
                elif which=='prepare':
                    if getattr(self,'_journal_window',None) is not None:
                        self._refresh_diagnostic()
                self.remote.set(self.studio.active_profile+' : '+self.per_machine[self.studio.active_profile,self.suite.get()])
        except queue.Empty:
            pass
        except Exception as exc:
            self.busy=False
            try:self.notice.set('Internal corpus status error: '+repr(exc))
            except Exception:pass
        finally:
            self.parent.after(250,self._drain)
