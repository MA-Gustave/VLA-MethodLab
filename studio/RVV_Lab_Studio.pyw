#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""RVV-VLA Studio v5.0.3 — simdjson 5.0.3 native testing console.

Requires Python 3.10+ Tkinter and Paramiko. No embedded password and no automatic
package installs, git pushes, sudo commands, or deletion of existing test runs.
"""
from __future__ import annotations
import codecs
import datetime as dt
import json
import os
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

from rvvlab_backend import (StudioSSH, parse_env, discover_env_file, preferred_repo, build_source_zip,
                            utc_id, config_for_run, DEFAULT_REMOTE_NAME, DEFAULT_RESULTS,
                            SETTINGS_PATH, HOST_FINGERPRINT)
from rvvlab_reports import latest_run, collect_via_client, validate_run_id
from rvvlab_parallel import MachineLock, TARGET
from rvvlab_local_time import clock_text
from rvvlab_storage import inventory, sync_run, purge_run, verify_local, archive_folder
from rvvlab_night import (available_sources, launch as launch_night,
                          remote_runs as night_runs,
                          stop as stop_night, sync as sync_night)

APP_DIR=Path(__file__).resolve().parent
ENV_EXAMPLE=APP_DIR/'.env.example'
LOCAL_LITE=DEFAULT_RESULTS/'Rapports_legers'
FATAL_RE=re.compile(r'(?:\bPASS\b|\bFAIL\b|\bERROR\b|fatal error|Traceback|stack smashing|SIGABRT|\bAborted\b|No space left|undefined reference|target specific option mismatch|compilation terminated|AUTO (?:STOP|COMPLETE)|\bFINAL\b|^\s*===|^\s*Native RVV preflight|^\s*VLEN:|^\s*compiler:|^\s*governor:|WARNING|\bGB/s\b)',re.I)
CSI=re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
OSC=re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)')
ESC=re.compile(r'\x1b[@-_]')


def clean_terminal(s):
    return ESC.sub('',CSI.sub('',OSC.sub('',s))).replace('\r\n','\n').replace('\r','\n').replace('\x00','')


def open_local(path:Path):
    path=Path(path).expanduser()
    if sys.platform=='win32':os.startfile(str(path))
    else:messagebox.showinfo('Local folder',str(path))


def read_previous_settings():
    try:
        obj=json.loads(SETTINGS_PATH.read_text(encoding='utf-8'))
        return obj if isinstance(obj,dict) else {}
    except (OSError,ValueError):return {}


class Studio:
    def __init__(self,root):
        self.root=root
        root.title('RVV-VLA Lab Studio — '+(TARGET or 'Dual Machine')+' — simdjson 5.0.3')
        root.geometry('1150x790')
        root.minsize(850,620)
        self.ssh=StudioSSH()
        self.events=queue.Queue()
        self.stop_job=threading.Event()
        self.console_stop=threading.Event()
        self.console_chan=None
        self.job_busy=False
        self.storage_busy=False
        self.night_busy=False
        self.night_running=False
        self.night_rows=[]
        self.connecting=False
        self.history=[]
        self.hist_index=0
        self.latest_folder=None
        self.active_run=None
        self.last_session=None
        self.full_log=None
        self.raw_line_count=0
        self.messages_displayed=0
        settings=read_previous_settings()
        found_env = discover_env_file(APP_DIR.parent)
        # The historical workspace .env can be shared by Lab's GUI and CLI.
        # Honor an existing custom GUI choice; repair stale default paths.
        saved_env = str(settings.get('env_path') or '').strip()
        automatic_defaults = {str(APP_DIR.parent / 'orchestrator' / '.env'),
                              str(APP_DIR / '.env')}
        if (settings.get('machine_profile','Cloud-V')!='EPCC' and saved_env and
            saved_env not in automatic_defaults and Path(saved_env).expanduser().is_file()):
            found_env = Path(saved_env).expanduser()
        self.vars={}
        defaults={'env_path':str(found_env), 'repo':str(preferred_repo(APP_DIR)),
                  'results':str(DEFAULT_RESULTS),'remote_name':DEFAULT_REMOTE_NAME,
                  'jobs':'2','vls_bits':'256','core':'',
                  'gcc_cc':'','gcc_cxx':'','clang_cc':'','clang_cxx':''}
        for key,value in defaults.items():
            if key in settings and isinstance(settings[key],(str,int)):
                # Use the discovered .env when the old path has moved or was
                # only the previous auto-generated default.
                if key == 'env_path':
                    value = str(found_env)
                else:
                    value=settings[key] if key!='vls_bits' or str(settings[key])=='256' else '256'
            self.vars[key]=tk.StringVar(value=str(value))
        # Each target has separate user-owned SSH configuration and results/history.
        # Never mix local TestRunner PASS markers or downloaded snapshots.
        self.machine_envs={
            'Cloud-V': str(settings.get('machine_primary_env') or found_env),
            'EPCC': str(settings.get('machine_epcc_env') or (APP_DIR.parent.parent/'.env.epcc')),
        }
        self.machine_results={
            'Cloud-V':str(settings.get('machine_primary_results') or self.vars['results'].get()),
            'EPCC':str(settings.get('machine_epcc_results') or (DEFAULT_RESULTS/'EPCC')),
        }
        initial_machine=settings.get('machine_profile','Cloud-V')
        if initial_machine not in self.machine_envs:initial_machine='Cloud-V'
        if TARGET:initial_machine=TARGET
        if Path(self.machine_results['Cloud-V']).expanduser().resolve()==Path(self.machine_results['EPCC']).expanduser().resolve():
            self.machine_results['EPCC']=str(Path(self.machine_results['Cloud-V'])/'EPCC')
        self.machine_choice=tk.StringVar(value=initial_machine)
        self.active_profile=initial_machine
        self.vars['env_path'].set(self.machine_envs[initial_machine])
        self.vars['results'].set(self.machine_results[initial_machine])
        self.target_arch=None
        # Independent per-target Test94 indicators. Only the connected target is
        # queried; the other one shows last known status with a timestamp.
        self.target_test94_labels={key:tk.StringVar(value='— No Test 94') for key in ('Cloud-V','EPCC')}
        self.target_test94_widgets={}
        self._test94_status_records={}
        self._test94_live_profiles=set()
        self._test94_poll_busy=False
        for target in self.target_test94_labels:
            self._test94_load_cached(target)
        self.rid=tk.StringVar(value='')
        self.status=tk.StringVar(value='Disconnected — select the .env file, then click Connect.')
        self.console_status=tk.StringVar(value='Console inactive')
        self.job_status=tk.StringVar(value='Ready: RVV target (VLEN 256 campaigns available)')
        self.report_status=tk.StringVar(value='Lightweight reports: nothing to download yet')
        self.storage_status=tk.StringVar(value='Connect, then click Refresh.')
        self.local_clock=tk.StringVar(value=clock_text())
        self.night_status=tk.StringVar(value='Connect, then refresh the campaign list.')
        self.storage_rows=[]
        self._build()
        self.root.after(75,self._poll)
        self.root.after(1000,self._tick_clock)
        self.root.after(35000,self._test94_periodic)
        self.root.protocol('WM_DELETE_WINDOW',self._quit)

    def _build(self):
        shell=ttk.Frame(self.root);shell.pack(fill='both',expand=True)
        canvas=tk.Canvas(shell,highlightthickness=0,borderwidth=0)
        scrollbar=ttk.Scrollbar(shell,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        main=ttk.Frame(canvas,padding=10)
        inner=canvas.create_window((0,0),window=main,anchor='nw')
        def sync_region(_event=None):
            canvas.configure(scrollregion=canvas.bbox('all'))
        def resize_outer(event):
            canvas.itemconfigure(inner,width=event.width)
            canvas.itemconfigure(inner,height=max(event.height,main.winfo_reqheight()))
            sync_region()
        main.bind('<Configure>',sync_region)
        canvas.bind('<Configure>',resize_outer)
        self.main_canvas=canvas
        def wheel(event):
            # Do not steal wheel events from text, list, combobox or tree scrollbars.
            widget=event.widget
            while widget is not None:
                if isinstance(widget,(tk.Text,tk.Listbox,ttk.Treeview,ttk.Combobox,tk.Scrollbar,ttk.Scrollbar)):
                    return
                if widget is canvas:break
                widget=getattr(widget,'master',None)
            step=(-1 if event.delta>0 else 1) if getattr(event,'delta',0) else (-1 if event.num==4 else 1)
            canvas.yview_scroll(step*3,'units')
            return 'break'
        self.root.bind_all('<MouseWheel>',wheel,add='+')
        self.root.bind_all('<Button-4>',wheel,add='+')
        self.root.bind_all('<Button-5>',wheel,add='+')
        header=ttk.Frame(main);header.pack(fill='x')
        ttk.Label(header,text='RVV-VLA Lab Studio',font=('Segoe UI',16,'bold')).pack(side='left')
        ttk.Label(header,text='simdjson 5.0.3 · RISC-V RVV 1.0 · native profiling',foreground='#555').pack(side='left',padx=14)
        self.connect_btn=ttk.Button(header,text='SSH Connect',command=self.connect)
        self.connect_btn.pack(side='right')
        self.disconnect_btn=ttk.Button(header,text='Disconnect',command=self.disconnect,state='disabled')
        self.disconnect_btn.pack(side='right',padx=6)
        ttk.Label(header,textvariable=self.local_clock,font=('Consolas',9)).pack(side='right',padx=(0,12))
        ttk.Label(main,textvariable=self.status).pack(anchor='w',pady=(4,7))
        cfg=ttk.Frame(main);cfg.pack(fill='x',pady=(0,10))
        cfg.columnconfigure(1,weight=1)
        ttk.Label(cfg,text='Target machine:').grid(row=0,column=0,sticky='w',pady=(0,6))
        chooser=ttk.Frame(cfg);chooser.grid(row=0,column=1,columnspan=3,sticky='w',pady=(0,6))
        for name,title in (('Cloud-V','Cloud-V — direct RISC-V'),
                           ('EPCC','EPCC — via SSH gateway')):
            group=ttk.Frame(chooser);group.pack(side='left',padx=(0,22))
            ttk.Radiobutton(group,text=title,variable=self.machine_choice,value=name,
                            state=('disabled' if TARGET and name!=TARGET else 'normal'),
                            command=self.switch_machine).pack(side='left')
            marker=tk.Label(group,textvariable=self.target_test94_labels[name],anchor='w',
                            foreground='#6b7280',font=('Segoe UI',9))
            marker.pack(side='left',padx=(5,0))
            self.target_test94_widgets[name]=marker
        self._test94_draw_badges()
        ttk.Label(cfg,text='SSH profile (.env):').grid(row=1,column=0,sticky='w')
        ttk.Entry(cfg,textvariable=self.vars['env_path']).grid(row=1,column=1,sticky='ew',padx=7)
        ttk.Button(cfg,text='…',width=3,command=self.browse_env).grid(row=1,column=2)
        ttk.Button(cfg,text='Open .env',command=self.edit_env).grid(row=1,column=3,padx=5)
        ttk.Button(cfg,text='Prepare EPCC profile',command=self.prepare_epcc_env).grid(
            row=2,column=1,sticky='w',pady=(5,0))
        notebook=ttk.Notebook(main);notebook.pack(fill='both',expand=True)
        self.center_tab=ttk.Frame(notebook,padding=12)
        notebook.add(self.center_tab,text='Centre des tests')
        self.tabs=[]
        for title in ('SSH Console','RVV Tests','Reports','Server Storage','8h Exploration'):
            f=ttk.Frame(notebook,padding=10);notebook.add(f,text=title);self.tabs.append(f)
        self._console_ui(self.tabs[0]);self._tests_ui(self.tabs[1]);self._reports_ui(self.tabs[2]);self._storage_ui(self.tabs[3]);self._night_ui(self.tabs[4])
        # RVVLAB_V5_TEST_RUNNER_TAB_V1
        from rvvlab_test_runner import TestRunnerPanel
        self.test_runner_tab=ttk.Frame(notebook,padding=10)
        notebook.add(self.test_runner_tab,text='Test Runner')
        self.test_runner=TestRunnerPanel(self.test_runner_tab,self)
        from rvvlab_test_center_ui import TestCenterPanel
        self.test_center=TestCenterPanel(self.center_tab,self)
        # RVVLAB_V5_CAMPAIGN_UNIFIED_V1
        from rvvlab_unified_campaigns import UnifiedCampaigns
        self.unified_campaigns=UnifiedCampaigns(self.test_runner,self)
        # Compatibility widgets remain instantiated, but their redundant tab is hidden.
        notebook.hide(self.tabs[4])
        self.test_runner.refresh_remote=self.unified_campaigns.refresh_remote
        # RVVLAB_STUDIO_ENGLISH_V503
        self.notebook=notebook

    def _center_auto_check(self,attempt=0):
        """Auto-refresh only status, respecting concurrent SSH activity."""
        if not self.ssh.connected() or self.connecting:return
        if (self.night_busy or self.storage_busy or self.job_busy or
            self._test94_poll_busy or self.unified_campaigns.busy or
            self.test_runner.busy or self.test_center.busy):
            if attempt<5:self.root.after(4000,lambda:self._center_auto_check(attempt+1))
            return
        self.test_center.check_remote()

    def _test94_load_cached(self,profile):
        """Load durable local status for both targets without connecting via SSH."""
        from rvvlab_target_status import latest_run
        item=latest_run(self.machine_results[profile])
        if item:
            cached=item.get('cached')
            if cached:
                self._test94_status_records[profile]=cached
            else:
                self._test94_status_records[profile]={
                    'state':'starting','detail':'Remote launch recorded, not checked',
                    'updated_utc':item['launch'].get('started_utc',''),
                    'verified':False}

    def _test94_draw_badges(self):
        from rvvlab_target_status import display
        colors={'idle':'#6b7280','active':'#936100','warning':'#b45309',
                'error':'#b91c1c','ok':'#087443'}
        for profile,var in self.target_test94_labels.items():
            connected=(self.active_profile==profile and self.ssh.connected()
                       and profile in self._test94_live_profiles)
            text,kind=display(self._test94_status_records.get(profile),connected=connected)
            var.set(('● ' if kind!='idle' else '○ ')+text)
            widget=self.target_test94_widgets.get(profile)
            if widget is not None:widget.configure(foreground=colors.get(kind,'#6b7280'))

    def report_test94_state(self,profile,state,detail='',output_dir=None,verified=False):
        """Thread-safe entry point for Test94 workers; no Tk access here."""
        from rvvlab_target_status import write_status
        if profile not in self.machine_results:return
        try:
            if output_dir is not None:
                info=write_status(output_dir,profile,state,detail,verified)
            else:
                info={'profile':profile,'state':str(state),'detail':str(detail)[:180],
                      'updated_utc':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                      'verified':bool(verified)}
            self.events.put(('test94_state',info))
        except OSError as exc:
            self.events.put(('test94_status_error',str(exc)))

    def _test94_periodic(self):
        """Poll the connected target read-only, at most every 35 seconds."""
        self._test94_check_now()
        self.root.after(35000,self._test94_periodic)

    def _test94_check_now(self):
        if (self._test94_poll_busy or not self.ssh.connected() or self.connecting
                or self.test_runner.busy or self.test_runner.poll_busy
                or self.storage_busy or self.night_busy or self.job_busy
                or self.unified_campaigns.busy or self.unified_campaigns.poll_busy):
            return
        from rvvlab_target_status import latest_run
        profile=self.active_profile
        item=latest_run(self.machine_results[profile])
        if not item or item['launch'].get('mode')!=profile:return
        launch=item['launch'];folder=item['folder'];ssh=self.ssh
        self._test94_poll_busy=True
        def work():
            try:
                from rvvlab_target_status import remote_probe,write_status
                state,detail=remote_probe(ssh,launch)
                record=write_status(folder,profile,state,detail,verified=True,
                                    run_id=launch.get('id'))
                self.events.put(('test94_polled',(profile,record)))
            except Exception as exc:
                self.events.put(('test94_poll_error',(profile,type(exc).__name__)))
        threading.Thread(target=work,daemon=True).start()

    def _tick_clock(self):
        """One-second GUI-only clock; does not trigger SSH polling."""
        self.local_clock.set(clock_text())
        self.root.after(1000,self._tick_clock)

    def _text(self,parent,height=15,dark=False):
        opts=dict(height=height,wrap='word',font=('Consolas',9),state='disabled')
        if dark:opts.update(bg='#111827',fg='#e5e7eb',insertbackground='#e5e7eb')
        w=scrolledtext.ScrolledText(parent,**opts)
        return w

    def _append(self,widget,text,max_lines=3500):
        widget.configure(state='normal')
        widget.insert('end',str(text))
        if int(widget.index('end-1c').split('.')[0])>max_lines:
            widget.delete('1.0','350.0')
        widget.see('end');widget.configure(state='disabled')

    def _console_ui(self,parent):
        toolbar=ttk.Frame(parent);toolbar.pack(fill='x',pady=(0,8))
        ttk.Label(toolbar,text='Interactive RVV Lab shell (shares the Studio SSH connection)').pack(side='left')
        self.interrupt_btn=ttk.Button(toolbar,text='Ctrl+C SSH',command=self.interrupt,state='disabled');self.interrupt_btn.pack(side='right')
        ttk.Button(toolbar,text='Clear console',command=self.clear_console_output).pack(side='right',padx=(0,8))
        ttk.Button(toolbar,text='Copy console',command=self.copy_console).pack(side='right',padx=(0,8))
        ttk.Button(toolbar,text='Disk',command=lambda:self.insert_shell('df -h ~')).pack(side='right',padx=(0,8))
        ttk.Button(toolbar,text='CPU',command=lambda:self.insert_shell('lscpu | head -n 25')).pack(side='right',padx=(0,8))
        ttk.Button(toolbar,text='Save output',command=self.save_console).pack(side='right',padx=(0,8))
        self.console_out=self._text(parent,height=20,dark=True);self.console_out.pack(fill='both',expand=True)
        self.console_out.bind('<Control-c>',self.copy_console_selection)
        bottom=ttk.Frame(parent);bottom.pack(fill='x',pady=(7,0))
        ttk.Label(bottom,text='Command:').pack(side='left')
        self.shell_entry=ttk.Entry(bottom,font=('Consolas',10),state='disabled')
        self.shell_entry.pack(side='left',expand=True,fill='x',padx=7)
        self.shell_entry.bind('<Return>',self.send_shell)
        self.shell_entry.bind('<Up>',self.history_up)
        self.shell_entry.bind('<Down>',self.history_down)
        self.shell_send=ttk.Button(bottom,text='Send',command=self.send_shell,state='disabled');self.shell_send.pack(side='left')
        ttk.Label(parent,textvariable=self.console_status).pack(anchor='w',pady=(6,0))
        ttk.Label(parent,text='Ctrl+C SSH interrupts remote commands; keyboard Ctrl+C copies selection.',foreground='#666').pack(anchor='w')
        self._append(self.console_out,'Console ready. Connect to run Linux commands.\n')

    # RVVLAB_STUDIO_CONSOLE_CONTROLS_V503
    def clear_console_output(self):
        """Clear the on-screen transcript only; no SSH command or disk deletion."""
        widget = self.console_out
        widget.configure(state='normal')
        try:
            widget.delete('1.0', 'end')
        finally:
            widget.configure(state='disabled')

    def copy_console_selection(self, event=None):
        """Keyboard Ctrl+C copies highlighted text, not remote interrupt."""
        try:
            selected = self.console_out.get('sel.first', 'sel.last')
        except tk.TclError:
            return 'break'
        self.root.clipboard_clear()
        self.root.clipboard_append(selected)
        self.root.update_idletasks()
        return 'break'

    # RVVLAB_STUDIO_CONSOLE_BUTTONS_V503_ENGLISH_V2
    def copy_console(self):
        """Copy the ENTIRE local console, whether or not text is selected."""
        contents = self.console_out.get('1.0', 'end-1c')
        self.root.clipboard_clear()
        self.root.clipboard_append(contents)
        self.root.update_idletasks()

    def _field(self,frame,label,key,row,col,button=False,width=15):
        ttk.Label(frame,text=label).grid(row=row,column=col,sticky='w',padx=(0,6),pady=3)
        wrapper=ttk.Frame(frame);wrapper.grid(row=row,column=col+1,sticky='ew',padx=(0,14),pady=3)
        wrapper.columnconfigure(0,weight=1)
        ttk.Entry(wrapper,textvariable=self.vars[key],width=width).grid(row=0,column=0,sticky='ew')
        if button:
            ttk.Button(wrapper,text='…',width=3,command=lambda:self.choose_path(key)).grid(row=0,column=1,padx=4)

    def _tests_ui(self,parent):
        config=ttk.LabelFrame(parent,text='Configuration — RISC-V RVV target defaults',padding=10)
        config.pack(fill='x')
        for col in (1,3):config.columnconfigure(col,weight=1)
        self._field(config,'Local repository','repo',0,0,button=True,width=48)
        self._field(config,'Windows results','results',1,0,button=True,width=48)
        self._field(config,'Remote folder','remote_name',2,0,width=25)
        self._field(config,'Jobs','jobs',2,2,width=8)
        self._field(config,'VLS (bits)','vls_bits',3,0,width=12)
        self._field(config,'CPU core (optional)','core',3,2,width=8)
        self._field(config,'GCC C','gcc_cc',4,0)
        self._field(config,'GCC C++','gcc_cxx',4,2)
        self._field(config,'Clang C','clang_cc',5,0)
        self._field(config,'Clang C++','clang_cxx',5,2)
        ttk.Label(config,text='Recommended: VLS 256 and 2 jobs. Blank compiler fields use the remote system compilers.',foreground='#555').grid(row=6,column=0,columnspan=4,sticky='w',pady=(5,0))
        controls=ttk.Frame(parent);controls.pack(fill='x',pady=9)
        buttons=[('Diagnostics','probe'),('Push sources','push'),('Preflight','preflight'),('Smoke','smoke'),
                 ('Phase1','phase1'),('Safe AUTO','auto'),('Matrix','matrix'),('Standard','standard'),('Publication','publication')]
        self.run_buttons=[]
        for i,(label,action) in enumerate(buttons):
            b=ttk.Button(controls,text=label,command=lambda a=action:self.start_run(a));b.grid(row=i//5,column=i%5,sticky='ew',padx=3,pady=3)
            self.run_buttons.append(b)
        for i in range(5):controls.columnconfigure(i,weight=1)
        row=ttk.Frame(parent);row.pack(fill='x',pady=(2,5))
        self.stop_btn=ttk.Button(row,text='Stop command',command=self.stop_run,state='disabled');self.stop_btn.pack(side='left')
        ttk.Button(row,text='Open results folder',command=lambda:open_local(Path(self.vars['results'].get()))).pack(side='left',padx=10)
        ttk.Label(row,textvariable=self.job_status).pack(side='left',padx=8)
        self.test_out=self._text(parent,height=15);self.test_out.pack(fill='both',expand=True)
        self._append(self.test_out,'Simplified output: stages, PASS/FAIL and errors. Detailed logs remain on your PC.\n')

    def _reports_ui(self,parent):
        ttk.Label(parent,text='Download small extracted reports. No nested TAR/ZIP archives.').pack(anchor='w')
        top=ttk.Frame(parent);top.pack(fill='x',pady=9)
        ttk.Label(top,text='Session:').pack(side='left')
        ttk.Entry(top,textvariable=self.rid,width=39).pack(side='left',padx=7)
        ttk.Label(top,text='(blank = latest remote campaign)').pack(side='left')
        self.report_btn=ttk.Button(top,text='Download lightweight reports',command=self.download_reports)
        self.report_btn.pack(side='right')
        row=ttk.Frame(parent);row.pack(fill='x',pady=(1,8))
        ttk.Button(row,text='Open Windows reports',command=self.open_reports).pack(side='left')
        ttk.Button(row,text='View diagnostics',command=lambda:self.load_report('00_DIAGNOSTIC.md')).pack(side='left',padx=8)
        ttk.Button(row,text='View errors',command=lambda:self.load_report('01_ERREURS.txt')).pack(side='left')
        ttk.Label(parent,textvariable=self.report_status).pack(anchor='w',pady=(0,6))
        sash=ttk.PanedWindow(parent,orient='horizontal');sash.pack(fill='both',expand=True)
        left=ttk.Frame(sash);right=ttk.Frame(sash)
        sash.add(left,weight=1);sash.add(right,weight=3)
        ttk.Label(left,text='Recent local reports').pack(anchor='w',pady=(0,4))
        self.report_list=tk.Listbox(left,exportselection=False)
        self.report_list.pack(fill='both',expand=True)
        self.report_list.bind('<<ListboxSelect>>',self.report_selected)
        ttk.Button(left,text='Refresh',command=self.refresh_reports).pack(fill='x',pady=5)
        self.report_text=self._text(right,height=17);self.report_text.pack(fill='both',expand=True)
        self.refresh_reports()

    def _storage_ui(self,parent):
        ttk.Label(parent,text='Full text-log archives on Windows, excluding builds, binaries and nested ZIPs.',
                  font=('Segoe UI',10,'bold')).pack(anchor='w',pady=(0,5))
        ttk.Label(parent,text='Purging removes results AND sources for an old campaign. The newest campaign is protected.',
                  foreground='#555').pack(anchor='w',pady=(0,9))
        buttons=ttk.Frame(parent);buttons.pack(fill='x',pady=(0,8))
        self.storage_refresh=ttk.Button(buttons,text='Refresh / free space',command=self.storage_refresh_list)
        self.storage_refresh.pack(side='left',padx=(0,7))
        self.storage_sync=ttk.Button(buttons,text='Sync selected',command=self.storage_sync_selected)
        self.storage_sync.pack(side='left',padx=(0,7))
        self.storage_sync_all=ttk.Button(buttons,text='Sync old campaigns',command=self.storage_sync_all_old)
        self.storage_sync_all.pack(side='left',padx=(0,7))
        self.storage_purge=ttk.Button(buttons,text='Purge selected',command=self.storage_purge_selected)
        self.storage_purge.pack(side='left',padx=(0,7))
        self.storage_purge_all=ttk.Button(buttons,text='Purge archived',command=self.storage_purge_all_old)
        self.storage_purge_all.pack(side='left',padx=(0,7))
        ttk.Button(buttons,text='Open Windows archives',command=self.storage_open_local).pack(side='right')
        ttk.Label(parent,textvariable=self.storage_status).pack(anchor='w',pady=(0,8))
        cols=('run','results','sources','archived','protected')
        storage_box=ttk.Frame(parent);storage_box.pack(fill='both',expand=True)
        self.storage_tree=ttk.Treeview(storage_box,columns=cols,show='headings',selectmode='browse',height=11)
        widths=(265,125,125,120,125)
        for key,label,w in zip(cols,('Campaign','Results','Sources','Windows archives','Protection'),widths):
            self.storage_tree.heading(key,text=label)
            self.storage_tree.column(key,width=w,anchor='w' if key=='run' else 'center',stretch=key=='run')
        y=ttk.Scrollbar(storage_box,orient='vertical',command=self.storage_tree.yview)
        x=ttk.Scrollbar(storage_box,orient='horizontal',command=self.storage_tree.xview)
        self.storage_tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        y.pack(side='right',fill='y');x.pack(side='bottom',fill='x')
        self.storage_tree.pack(side='left',fill='both',expand=True)
        self.storage_output=self._text(parent,height=10)
        self.storage_output.pack(fill='both',expand=True,pady=(8,0))
        self._append(self.storage_output,
          '1. Refresh to inspect disk space and campaigns.\n'
          '2. Sync a campaign: full logs, CSV and reports, verified by SHA256.\n'
          '3. Purge ONLY an old campaign with verified backups (explicit confirmation required).\n'
          'Lightweight reports remain accessible under Reports.\n')

    def _night_ui(self,parent):
        ttk.Label(parent,text='RVV VLA exploration: 8h max · Stage 1 / Stage 2 / DOM map',
                  font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(0,7))
        ttk.Label(parent,text='Detached execution on RVV Lab. Closing Studio does not stop a remote runner.',
                  foreground='#555').pack(anchor='w')
        ttk.Label(parent,text='Maximum 2 GiB workspace; stop below 3 GiB free; compact results and checkpoints.',
                  foreground='#555').pack(anchor='w',pady=(0,10))
        buttons=ttk.Frame(parent);buttons.pack(fill='x',pady=(0,10))
        self.night_start_btn=ttk.Button(buttons,text='Start 8h',command=self.night_start)
        self.night_start_btn.pack(side='left',padx=(0,7))
        self.night_refresh_btn=ttk.Button(buttons,text='Refresh status',command=self.night_refresh)
        self.night_refresh_btn.pack(side='left',padx=(0,7))
        self.night_sync_btn=ttk.Button(buttons,text='Sync results',command=self.night_sync)
        self.night_sync_btn.pack(side='left',padx=(0,7))
        self.night_stop_btn=ttk.Button(buttons,text='Request stop',command=self.night_stop)
        self.night_stop_btn.pack(side='left',padx=(0,7))
        ttk.Button(buttons,text='Open Windows map',command=self.night_open).pack(side='right')
        ttk.Label(parent,textvariable=self.night_status).pack(anchor='w',pady=(0,7))
        keys=('id','state','observations','candidate','updated','free')
        names=('Campaign','State','Measurements','Current variant','Last update','Free (GiB)')
        widths=(263,112,83,151,177,95)
        night_box=ttk.Frame(parent);night_box.pack(fill='x',pady=(0,9))
        self.night_tree=ttk.Treeview(night_box,columns=keys,show='headings',selectmode='browse',height=7)
        for k,n,w in zip(keys,names,widths):
            self.night_tree.heading(k,text=n);self.night_tree.column(k,width=w,stretch=k in ('id','candidate'))
        y=ttk.Scrollbar(night_box,orient='vertical',command=self.night_tree.yview)
        x=ttk.Scrollbar(night_box,orient='horizontal',command=self.night_tree.xview)
        self.night_tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        y.pack(side='right',fill='y');self.night_tree.pack(side='left',fill='both',expand=True);x.pack(fill='x')
        self.night_output=self._text(parent,height=14)
        self.night_output.pack(fill='both',expand=True)
        self._append(self.night_output,
            '1. Start 8h: prepare variants and benchmark them sequentially on CPU 0.\n'
            '2. Sync results: map.csv, ranking and hypotheses; no builds or huge logs.\n'
            '3. If Studio remains open, sync periodically (every 5 minutes).\n'
            '4. If Studio is closed, checkpoints remain on RVV Lab; sync next time.\n'
            '5. Stop: finish the current scenario and save; never purge automatically.\n'
            '6. The source snapshot must come from the simdjson 5.0.3 checkout.\n')

    def _night_selected(self):
        ids=self.night_tree.selection()
        if ids:return self.night_tree.item(ids[0],'values')[0]
        if self.night_rows:return self.night_rows[0]['id']
        return None

    def _night_start_worker(self,action,remote,runid=None):
        try:
            if action=='start':
                sources=available_sources(self.ssh,remote)
                if not sources:raise RuntimeError('No source snapshot is available; run Push Sources')
                current=night_runs(self.ssh,remote)
                if any(r.get('state') in ('starting','preflight','build','screen','confirm') for r in current):
                    raise RuntimeError('An exploration appears to be running on RVV Lab')
                data=launch_night(self.ssh,remote,runid=runid,sourceid=sources[0],jobs=2)
                self.events.put(('night_line',f"Started: {data['run_id']} · source {data['source_id']} · PID {data['pid']}\n"))
                self.events.put(('night_status','Runner started in the background, independent of Studio.'))
            elif action=='stop':
                stop_night(self.ssh,remote,runid)
                self.events.put(('night_line','Stop requested for '+runid+'; gracefully stopping at the next checkpoint.\n'))
            elif action=='sync':
                folder=sync_night(self.ssh,remote,runid,self._storage_local_root())
                self.events.put(('night_line','SHA256-verified snapshot: '+str(folder)+'\n'))
                self.events.put(('night_status','Results synced: '+runid))
            elif action=='periodic':
                rows=night_runs(self.ssh,remote)
                if rows:
                    try:
                        folder=sync_night(self.ssh,remote,rows[0]['id'],self._storage_local_root())
                        self.events.put(('night_line','Periodic sync: '+str(folder)+'\n'))
                    except RuntimeError:
                        pass  # worker starting: snapshot may not exist yet
            rows=night_runs(self.ssh,remote)
            self.events.put(('night_rows',rows))
            self.events.put(('night_finished',None))
        except Exception as e:
            self.events.put(('night_line','ERROR: '+str(e)+'\n'))
            self.events.put(('night_finished','Failed: '+str(e)))

    def _night_run(self,action,runid=None,quiet=False):
        if self.night_busy or self.job_busy or self.storage_busy:
            if not quiet:messagebox.showwarning('Studio is busy','Wait for the current operation to finish.')
            return
        if not self.ssh.connected():
            if not quiet:messagebox.showwarning('SSH','Connect to RVV Lab first.')
            return
        try:remote=config_for_run(self._settings())['remote_name']
        except Exception as e:
            if not quiet:messagebox.showerror('Configuration',str(e))
            return
        self.night_busy=True
        for btn in (self.night_start_btn,self.night_refresh_btn,self.night_sync_btn,self.night_stop_btn):btn.configure(state='disabled')
        threading.Thread(target=self._night_start_worker,args=(action,remote,runid),daemon=True).start()

    def night_start(self):
        if not self.rvv_target_ready():return
        if self.night_running:
            messagebox.showwarning('Exploration en cours','An exploration is already running.');return
        free=self.ssh.available_kib() if self.ssh.connected() else None
        if free is None or free<5*1024*1024:
            messagebox.showerror('Disk','At least 5 GiB of free space is required to start an exploration.')
            return
        msg=('Start an autonomous exploration lasting up to 8 hours?\n\n'
             'GCC · VLS 256 · CPU 0 · 2 jobs maximum.\n'
             'Workspace quota: 2 GiB; stop if free disk space falls below 3 GiB.\n'
             'Temporary builds are removed after each variant.\n'
             'Data are exploratory and must be independently validated.\n\n'
             'No git push and no deletion of old campaigns.')
        if not messagebox.askyesno('CONFIRMER 8 H',msg):return
        runid='night-'+utc_id()+'-'+os.urandom(3).hex()
        self._night_run('start',runid)

    def night_refresh(self):self._night_run('refresh')
    def night_sync(self):
        rid=self._night_selected()
        if not rid:messagebox.showinfo('Exploration','Refresh campaigns, then select one.');return
        self._night_run('sync',rid)
    def night_stop(self):
        rid=self._night_selected()
        if not rid:return
        if messagebox.askyesno('Overnight run stop','Request a graceful stop for '+rid+'?\nNo remote files will be deleted.'):
            self._night_run('stop',rid)
    def night_open(self):
        path=self._storage_local_root()/'NightRuns'
        path.mkdir(parents=True,exist_ok=True)
        open_local(path)
    def _night_show_rows(self,rows):
        self.night_rows=rows
        old=self._night_selected()
        self.night_tree.delete(*self.night_tree.get_children())
        running_states=('starting','preflight','build','screen','confirm')
        self.night_running=any(x.get('state') in running_states for x in rows)
        for x in rows:
            values=(x.get('id'),x.get('state') or '?',x.get('observations') or 0,
                    x.get('current_candidate') or '',x.get('last_update') or '',
                    x.get('disk_free_gib') or '')
            item=self.night_tree.insert('','end',values=values)
            if x.get('id')==old:self.night_tree.selection_set(item)
        if rows:
            latest=rows[0]
            self.night_status.set(f"{latest.get('id')} : {latest.get('state')} — {latest.get('observations',0)} observations")
        else:self.night_status.set('No overnight exploration found.')

    def _night_periodic(self):
        try:
            if self.ssh.connected() and not (self.night_busy or self.job_busy or self.storage_busy):
                # Tiny checkpoint-only sync. If Studio/PC sleeps, resume on reconnection.
                self._night_run('periodic',quiet=True)
        finally:
            self.root.after(300000,self._night_periodic)

    @staticmethod
    def _human_bytes(n):
        n=max(0,int(n))
        for unit in ('o','Kio','Mio','Gio','Tio'):
            if n<1024 or unit=='Tio':return f'{n:.1f} {unit}' if unit!='o' else f'{n} o'
            n=n/1024

    def _storage_local_root(self):
        return Path(self.vars['results'].get()).expanduser()

    def _storage_selected(self):
        selection=self.storage_tree.selection()
        if not selection:messagebox.showinfo('Stockage','Select a campaign in the table.');return None
        return self.storage_tree.item(selection[0],'values')[0]

    def _storage_start(self,label,worker,*args):
        if self.night_running:
            messagebox.showwarning('Exploration nocturne','Wait for the night runner to finish before changing storage.');return
        if self.job_busy or self.storage_busy:
            messagebox.showwarning('Operation in progress','Another operation is in progress.');return
        if not self.ssh.connected():
            messagebox.showwarning('SSH','Connect before managing the server.');return
        try:remote=config_for_run(self._settings())['remote_name']
        except Exception as exc:messagebox.showerror('Configuration',str(exc));return
        self.storage_busy=True
        self.storage_status.set(label)
        for b in (self.storage_refresh,self.storage_sync,self.storage_sync_all,self.storage_purge,self.storage_purge_all):
            b.configure(state='disabled')
        self._enable_runs(False)
        self.stop_btn.configure(state='disabled')  # no native test is running
        threading.Thread(target=self._storage_worker,args=(worker,remote,*args),daemon=True).start()

    def storage_refresh_list(self):
        self._storage_start('Metric de l’espace serveur…','inventory')

    def storage_sync_selected(self):
        run=self._storage_selected()
        if run:self._storage_start('Full log sync for '+run+'…','sync',run)

    def storage_sync_all_old(self):
        runs=[x['id'] for x in self.storage_rows[1:]]
        if not runs:
            messagebox.showinfo('Stockage','Refresh the list or wait for an older campaign.');return
        self._storage_start('Backing up '+str(len(runs))+' older campaigns...','sync-all',runs)

    def storage_purge_selected(self):
        if self.night_running:
            messagebox.showwarning('Exploration nocturne','Purging is disabled during an active exploration.');return
        run=self._storage_selected()
        if not run:return
        protected={x['id'] for x in self.storage_rows[:1]}
        if run in protected:
            messagebox.showwarning('Protected campaign','The newest campaign cannot be deleted.');return
        folder=archive_folder(self._storage_local_root(),run)
        if not verify_local(folder,run):
            messagebox.showerror('Unverified archive',
                'First sync and verify this campaign logs locally.\nDeletion is not allowed.')
            return
        ask=(f'Text logs for {run} have been synced and verified on Windows.\n\n'
             'WARNING: this will PERMANENTLY delete folders '
             'results/<campaign> and sources/<campaign> on RVV Lab, including builds, '
             'corpora and binaries that were NOT backed up.\n\n'
             'Your local Windows log archive will remain intact.\n\n'
             f'To confirm, type exactly: {run}')
        answer=simpledialog.askstring('CONFIRMER PURGE SERVEUR',ask,parent=self.root)
        if answer!=run:
            self.storage_status.set('Purge cancelled: confirmation missing or incorrect.')
            return
        self._storage_start('Controlled purge of '+run+'…','purge',run)

    def storage_purge_all_old(self):
        if self.night_running:
            messagebox.showwarning('Exploration nocturne','Purging is disabled during an active exploration.');return
        runs=[x['id'] for x in self.storage_rows[1:]
              if verify_local(archive_folder(self._storage_local_root(),x['id']),x['id'])]
        if not runs:
            messagebox.showinfo('Stockage','No old verified and archived campaign to purge.');return
        label=f'PURGE {len(runs)}'
        names='\n'.join(runs)
        ask=(f'Permanent purge of {len(runs)} old campaigns on RVV Lab:\n\n{names}\n\n'
             'Matching results/ AND sources/ files will be deleted, '
             'including builds, corpora and binaries that were not backed up. '
             'Synced text logs will remain on Windows. '
             'The newest campaign remains protected.\n\n'
             'Type exactly: '+label)
        value=simpledialog.askstring('PURGE MULTIPLE — CONFIRMATION',ask,parent=self.root)
        if value!=label:
            self.storage_status.set('Bulk purge cancelled.');return
        self._storage_start('Purging '+str(len(runs))+' archived campaigns...','purge-all',runs)

    def storage_open_local(self):
        folder=self._storage_local_root()/'Archives_serveur';folder.mkdir(parents=True,exist_ok=True)
        open_local(folder)

    def _storage_worker(self,action,remote,run=None):
        try:
            def say(line):self.events.put(('storage_line',str(line)+'\n'))
            if action=='inventory':
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            elif action=='sync':
                folder=sync_run(self.ssh.client,run,self._storage_local_root(),remote,printer=say)
                self.events.put(('storage_line','Saved on Windows: '+str(folder)+'\n'))
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            elif action=='sync-all':
                for index,rid in enumerate(run,1):
                    say(f'[{index}/{len(run)}] Synchronisation {rid}')
                    sync_run(self.ssh.client,rid,self._storage_local_root(),remote,printer=say)
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            elif action=='purge':
                purge_run(self.ssh.client,run,self._storage_local_root(),remote,printer=say)
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            elif action=='purge-all':
                for index,rid in enumerate(run,1):
                    say(f'[{index}/{len(run)}] Purge {rid} (verified archive)')
                    purge_run(self.ssh.client,rid,self._storage_local_root(),remote,printer=say)
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            else:raise ValueError('Unknown storage action')
            self.events.put(('storage_finished','Operation completed.'))
        except Exception as exc:
            self.events.put(('storage_line','ERROR: '+str(exc)+'\n'))
            try:
                data=inventory(self.ssh.client,remote)
                data['archives_verified']={item['id']:verify_local(archive_folder(self._storage_local_root(),item['id']),item['id'])
                                           for item in data['runs']}
                self.events.put(('storage_inventory',data))
            except Exception:pass
            self.events.put(('storage_finished','Failed: '+str(exc)))

    def _storage_show_inventory(self,data):
        self.storage_rows=data['runs']
        self.storage_tree.delete(*self.storage_tree.get_children())
        for n,item in enumerate(self.storage_rows):
            run=item['id']
            saved=data.get('archives_verified',{}).get(run,False)
            self.storage_tree.insert('','end',values=(run,
                self._human_bytes(item['results_bytes']),self._human_bytes(item['sources_bytes']),
                'Verified' if saved else 'No', 'Newest' if n<1 else 'Older'))
        self._append(self.storage_output, 'Disk RVV Lab : '+self._human_bytes(data['disk_free'])+' libres / '
                     +self._human_bytes(data['disk_total'])+' au total. '
                     +str(len(self.storage_rows))+' campaigns.\n')
        self.storage_status.set(self._human_bytes(data['disk_free'])+' libres sur RVV Lab — '
                                +str(len(self.storage_rows))+' campaigns')

    def browse_env(self):
        path=filedialog.askopenfilename(title='Choose an .env file',filetypes=[('All files','*.*')])
        if path:
            self.vars['env_path'].set(path)
            self.machine_envs[self.machine_choice.get()]=path

    def prepare_epcc_env(self):
        """Creates an unprivileged local template outside the source repository."""
        dest=Path(self.machine_envs['EPCC']).expanduser()
        if dest.is_symlink():
            messagebox.showerror('EPCC configuration','Symlinked .env files are not permitted.');return
        if dest.exists():
            messagebox.showinfo('EPCC configuration',
                'The EPCC profile already exists. Edit it without replacing your SSH credentials:\n'+str(dest))
            return
        if not messagebox.askyesno('Prepare EPCC SSH profile',
            'Create an empty EPCC connection template at:\n'+str(dest)+'\n\n'
            'No passwords or keys will be inserted. You must supply the internal '
            'VM hostname, VM login, and two verified SSH host fingerprints.'):
            return
        content=("""# EPCC internal VM reached through the SSH-only gateway.
# This file should remain OUTSIDE the repository. Do not share it.
# First ask EIDF for your INTERNAL VM hostname, VM username, and SSH access.
RVVLAB_HOST=REPLACE_WITH_INTERNAL_VM_HOSTNAME
RVVLAB_PORT=22
RVVLAB_USER=REPLACE_WITH_INTERNAL_VM_USERNAME
RVVLAB_HOST_SHA256=SHA256:REPLACE_WITH_VERIFIED_INTERNAL_VM_FINGERPRINT
# VM authentication. Set an absolute key path or let Studio prompt for a password.
RVVLAB_SSH_KEY=

# Gateway account from the approval email (not the compute machine):
RVVLAB_JUMP_HOST=gateway.epcc.ed.ac.uk
RVVLAB_JUMP_PORT=22
RVVLAB_JUMP_USER=gustave
RVVLAB_JUMP_HOST_SHA256=SHA256:REPLACE_WITH_VERIFIED_GATEWAY_FINGERPRINT
# Use your gateway SSH key, or agent if configured with the public key.
RVVLAB_JUMP_KEY=
RVVLAB_JUMP_ALLOW_AGENT=1
""")
        try:
            dest.parent.mkdir(parents=True,exist_ok=True)
            with dest.open('x',encoding='utf-8') as out:out.write(content)
            self.machine_envs['EPCC']=str(dest)
            if self.machine_choice.get()=='EPCC':self.vars['env_path'].set(str(dest))
            messagebox.showinfo('EPCC profile created',
                'Template created. Fill the internal VM details and both VERIFIED SSH '
                'host key fingerprints before connecting. Gateway-only access is not a compute node.')
        except OSError as exc:
            messagebox.showerror('EPCC profile',str(exc))

    def switch_machine(self):
        """Switches the intended target; never reuses a live SSH connection."""
        target=self.machine_choice.get()
        previous=getattr(self,'active_profile','Cloud-V')
        if TARGET and target!=TARGET:
            self.machine_choice.set(TARGET)
            messagebox.showwarning('Instance dédiée', 'Cette fenêtre est réservée à '+TARGET+'. Utilisez le second lanceur.')
            return
        if target==previous:return
        if (self.connecting or self.job_busy or self.storage_busy or self.night_busy or
            self.test_runner.busy or self.test_runner.poll_busy or self._test94_poll_busy or
            self.unified_campaigns.busy or self.unified_campaigns.poll_busy):
            self.machine_choice.set(previous)
            messagebox.showwarning('Machine in use',
                'Wait for local tests, synchronization, or remote refresh to finish before switching.')
            return
        if not TARGET and getattr(self,'_machine_lock',None):
            guard=self._machine_lock
            guard.release()
            if not guard.acquire(target):
                guard.acquire(previous)
                self.machine_choice.set(previous)
                messagebox.showwarning('Machine déjà ouverte',target+' est déjà contrôlé par une autre instance.')
                return
        # Save edits made in the outgoing profile before switching.
        self.machine_envs[previous]=self.vars['env_path'].get().strip()
        self.machine_results[previous]=self.vars['results'].get().strip()
        if self.ssh.connected():self.disconnect()
        self._test94_live_profiles.discard(previous)
        self.active_profile=target
        self._test94_load_cached(target)
        self._test94_draw_badges()
        self.test_runner.epcc_nodes.clear()
        self.test_runner.node_combo['values']=[]
        self.test_runner.set_machine_mode(target)
        self.vars['env_path'].set(self.machine_envs[target])
        self.vars['results'].set(self.machine_results[target])
        self.target_arch=None
        self.unified_campaigns._set_rows([])
        self.test_runner.run_id.set('')
        self.test_runner.refresh_local()
        self.test_center.remote.clear();self.test_center.remote94=None;self.test_center.server_checked=False
        self.test_center.refresh_local()
        self.night_rows=[]
        self.status.set(f'{target} selected — click SSH Connect. Detached remote tests continue running.')
        self._save_settings()

    def choose_path(self,key):
        path=filedialog.askdirectory(title='Choose '+key,initialdir=self.vars[key].get())
        if path:self.vars[key].set(path)
    def edit_env(self):
        p=Path(self.vars['env_path'].get()).expanduser()
        if not p.is_file():
            messagebox.showwarning('.env introuvable',f'Copie .env.example en .env puis ajoute ton mot de passe.\n\n{p}')
            return
        try:open_local(p)
        except Exception as exc:messagebox.showerror('Error',str(exc))

    def _save_settings(self):
        obj={k:v.get() for k,v in self.vars.items()}
        selected=self.machine_choice.get()
        self.machine_envs[selected]=self.vars['env_path'].get().strip()
        self.machine_results[selected]=self.vars['results'].get().strip()
        obj.update(machine_profile=selected,
                   machine_primary_env=self.machine_envs['Cloud-V'],
                   machine_epcc_env=self.machine_envs['EPCC'],
                   machine_primary_results=self.machine_results['Cloud-V'],
                   machine_epcc_results=self.machine_results['EPCC'])
        SETTINGS_PATH.parent.mkdir(parents=True,exist_ok=True)
        SETTINGS_PATH.write_text(json.dumps(obj,indent=2,ensure_ascii=False),encoding='utf-8')

    def connect(self):
        if self.connecting or self.ssh.connected():return
        try:
            import paramiko  # noqa: F401
            env=parse_env(Path(self.vars['env_path'].get()))
            if self.machine_choice.get()=='EPCC' and not env.get('jump'):
                raise ValueError('EPCC profile requires JUMP_HOST and JUMP_USER; host fingerprints are required except in explicit EPCC test mode.')
            if env.get('unverified_epcc_test_mode'):
                if not messagebox.askyesno('Unverified EPCC test connection',
                    'TEST MODE: SSH host keys will NOT be verified for the gateway or internal host.\n'
                    'This exposes SSH credentials to possible server impersonation.\n'
                    'Use only temporarily for EPCC diagnostics. Continue?'):
                    self.status.set('Unverified EPCC test mode cancelled')
                    return
            if self.active_profile=='EPCC' and env.get('jump'):
                # Recognize the user's dedicated EPCC key without editing/overwriting .env.
                default_key=Path.home()/'.ssh'/'id_ed25519_epcc'
                if not env['jump'].get('key') and default_key.is_file():
                    env['jump']['key']=str(default_key)
                if not env.get('key') and default_key.is_file():
                    env['key']=str(default_key)
                if env['jump'].get('key'):
                    # A locally stored .env.epcc passphrase may unlock the key.
                    # If absent, prompt interactively. Never log secrets.
                    try:
                        import paramiko
                        paramiko.Ed25519Key.from_private_key_file(
                            env['jump']['key'], password=env['jump'].get('key_passphrase') or None)
                    except paramiko.PasswordRequiredException:
                        phrase=simpledialog.askstring('EPCC private key',
                            'Enter the passphrase for id_ed25519_epcc (not saved):',
                            show='*',parent=self.root)
                        if phrase is None:
                            self.status.set('EPCC connection cancelled');return
                        env['jump']['key_passphrase']=phrase
                    except (OSError,paramiko.SSHException,ValueError) as exc:
                        raise RuntimeError('Unable to unlock EPCC SSH key. Check the key path and '
                                           'RVVLAB_JUMP_KEY_PASSPHRASE in your local .env.epcc.') from exc
                code=simpledialog.askstring('EPCC MFA',
                    'Enter the current 6-digit EPCC TOTP code (one time per Studio SSH connection):',
                    parent=self.root)
                if code is None:
                    self.status.set('EPCC MFA cancelled');return
                if not re.fullmatch(r'\d{6}',code.strip()):
                    raise ValueError('EPCC TOTP code must contain exactly 6 digits')
                env['jump']['totp_code']=code.strip()
            if env.get('jump') and not any((env['jump']['key'],env['jump']['password'],
                                            env['jump'].get('allow_agent',False))):
                password=simpledialog.askstring('Gateway authentication',
                    'Gateway SSH password (not saved):',show='*',parent=self.root)
                if not password:
                    self.status.set('Gateway connection cancelled')
                    return
                env['jump']['password']=password
            if (self.active_profile=='EPCC' and not env['password']) or (not env['key'] and not env['password']):
                password=simpledialog.askstring('Internal VM authentication' if env.get('jump')
                    else 'SSH Authentication',
                    'Internal VM SSH password (not saved):' if env.get('jump') else
                    'SSH password (used only for this connection; never saved):',
                    show='*', parent=self.root)
                if not password:
                    self.status.set('SSH connection cancelled')
                    return
                env['password']=password
            env['profile_label']=self.active_profile
            self._save_settings()
        except ImportError:
            messagebox.showerror('Missing Paramiko','Run: python -m pip install paramiko');return
        except Exception as exc:
            messagebox.showerror('SSH Configuration',str(exc));return
        self.connecting=True;self.connect_btn.configure(state='disabled')
        self.status.set('Connecting SSH (EPCC unverified TEST MODE)...' if env.get('unverified_epcc_test_mode') else 'Connecting SSH and verifying host fingerprint...')
        threading.Thread(target=self._connect_worker,args=(env,),daemon=True).start()

    def _connect_worker(self,env):
        try:
            self.ssh.connect(env)
            # EPCC may be an x86 VM. Verify the actual target, not the gateway.
            try:self.target_arch=self.ssh.exec_text('uname -m').strip()
            except Exception:self.target_arch='unknown'
            chan=self.ssh.open_shell()
            self.console_chan=chan
            self.console_stop.clear()
            threading.Thread(target=self._console_reader,args=(chan,),daemon=True).start()
            route=f" via {env['jump']['user']}@{env['jump']['host']}" if env.get('jump') else ''
            architecture=f' · architecture: {self.target_arch}'
            if env.get('profile_label')=='EPCC' and self.target_arch!='riscv64':
                architecture+=' (Test94 runs on Slurm RISC-V compute nodes)' 
            self.events.put(('connected',f"Connected: {env['user']}@{env['host']}:{env['port']}"+route+
                             architecture+' (both host keys pinned where applicable)'))
        except Exception as exc:
            self.ssh.close()
            self.events.put(('connect_fail',str(exc)))
        finally:
            # Drop plaintext after SSH authentication, even on failed connect.
            env.pop('password',None)
            env.pop('key_passphrase',None)
            if env.get('jump'):
                for secret in ('totp_code','key_passphrase','password'):
                    env['jump'].pop(secret,None)

    def _console_reader(self,chan):
        decoder=codecs.getincrementaldecoder('utf-8')('replace')
        try:
            chan.settimeout(.35)
            while not self.console_stop.is_set():
                try:data=chan.recv(16384)
                except TimeoutError:continue
                if not data:break
                s=decoder.decode(data)
                if s:self.events.put(('console',s))
        except Exception as exc:
            if not self.console_stop.is_set():self.events.put(('console','\n[Console closed: '+str(exc)+']\n'))
        finally:self.events.put(('console_done',None))

    def disconnect(self):
        if self.job_busy or self.storage_busy or self.night_busy:
            messagebox.showwarning('Activity in progress','Wait for tests or sync to finish before disconnecting.')
            return
        self.console_stop.set()
        if self.console_chan:
            try:self.console_chan.close()
            except Exception:pass
        self.ssh.close()
        self._test94_live_profiles.discard(self.active_profile)
        self._test94_draw_badges()
        self.status.set('Disconnected')
        self.target_arch=None
        self.console_status.set('Console inactive')
        self.console_chan=None
        self._enable_console(False)
        self.connect_btn.configure(state='normal');self.disconnect_btn.configure(state='disabled')

    def _enable_console(self,on):
        state='normal' if on else 'disabled'
        self.shell_entry.configure(state=state)
        self.shell_send.configure(state=state)
        self.interrupt_btn.configure(state=state)
    def insert_shell(self,command):
        if self.console_chan is None:return
        self.shell_entry.delete(0,'end');self.shell_entry.insert(0,command);self.shell_entry.focus_set()
    def send_shell(self,event=None):
        if not self.ssh.connected() or self.console_chan is None:return 'break'
        value=self.shell_entry.get()
        try:self.console_chan.sendall((value+'\n').encode('utf-8'))
        except Exception as exc:self._append(self.console_out,'\n[Send error: '+str(exc)+']\n')
        if value.strip():self.history.append(value);self.history=self.history[-100:]
        self.hist_index=len(self.history);self.shell_entry.delete(0,'end')
        return 'break'
    def interrupt(self,event=None):
        if self.console_chan and self.ssh.connected():
            try:self.console_chan.sendall(b'\x03')
            except Exception:pass
        return 'break'
    def history_up(self,event=None):
        if self.history:
            self.hist_index=max(0,self.hist_index-1)
            self.shell_entry.delete(0,'end');self.shell_entry.insert(0,self.history[self.hist_index])
        return 'break'
    def history_down(self,event=None):
        if self.history:
            self.hist_index=min(len(self.history),self.hist_index+1)
            self.shell_entry.delete(0,'end')
            if self.hist_index<len(self.history):self.shell_entry.insert(0,self.history[self.hist_index])
        return 'break'
    def save_console(self):
        p=filedialog.asksaveasfilename(title='Enregistrer sortie console',defaultextension='.txt',filetypes=[('Texte','*.txt')])
        if p:Path(p).write_text(self.console_out.get('1.0','end'),encoding='utf-8')

    def _settings(self):
        cfg={k:self.vars[k].get().strip() for k in ('repo','results','remote_name','jobs','vls_bits','core','gcc_cc','gcc_cxx','clang_cc','clang_cxx')}
        cfg=config_for_run(cfg)
        if not cfg['results']:raise ValueError('Windows results directory is required')
        return cfg
    def rvv_target_ready(self):
        if self.active_profile=='EPCC' and self.target_arch!='riscv64':
            messagebox.showwarning('Unsupported target',
                f'EPCC target architecture: {self.target_arch or "unknown"}. '
                'Native RVV campaigns require a RISC-V riscv64 VM with RVV, '
                'an appropriate toolchain and sufficient resources. No test was started.')
            return False
        return True

    def start_run(self,action):
        if self.job_busy or self.storage_busy or self.night_busy:return
        if action!='probe' and not self.rvv_target_ready():return
        if self.night_running:
            messagebox.showwarning('Active exploration','Wait for the night runner to finish before starting another test.');return
        if not self.ssh.connected():messagebox.showwarning('SSH','Connect to SSH first.');return
        try:
            cfg=self._settings()
            if action not in ('probe',):
                if not (Path(cfg['repo'])/'scripts/rvv/server_control.py').is_file():
                    raise ValueError('Select the local simdjson-rvv-vla checkout : scripts/rvv/server_control.py absent')
            self._save_settings()
        except Exception as exc:messagebox.showerror('Configuration',str(exc));return
        self.job_busy=True;self.stop_job.clear();self.active_run=utc_id()+'-'+os.urandom(3).hex()
        self.raw_line_count=0;self.messages_displayed=0
        self.job_status.set(f'{action} — starting')
        self._append(self.test_out,f'\n=== Nouvelle campagne {self.active_run} : {action} ===\n')
        self._enable_runs(False)
        threading.Thread(target=self._run_worker,args=(action,cfg,self.active_run),daemon=True).start()
    def _enable_runs(self,on):
        for b in self.run_buttons:b.configure(state='normal' if on else 'disabled')
        self.stop_btn.configure(state='disabled' if on else 'normal')
    def stop_run(self):
        if self.job_busy:
            self.stop_job.set();self._append(self.test_out,'[Stop requested; the remote process may continue.]\n')

    def _run_worker(self,action,cfg,run_id):
        output=Path(cfg['results']).expanduser()
        output.mkdir(parents=True,exist_ok=True)
        full_log=output/f'rvvlab-log-{run_id}.txt'
        status='FAIL';rc=None;manifest=None;report=None;target=None
        began=time.monotonic()
        try:
            with full_log.open('w',encoding='utf-8',buffering=1) as logfile:
                def log(s):
                    self.raw_line_count+=1
                    logfile.write(str(s)+'\n')
                    line=str(s)
                    if FATAL_RE.search(line) or self.raw_line_count%140==0:
                        shown=(f'[activity: {self.raw_line_count} detailed lines]\n'
                               if self.raw_line_count%140==0 and not FATAL_RE.search(line) else line+'\n')
                        self.events.put(('test_line',shown))
                log('=== Session '+run_id+' / '+action+' ===')
                if action=='probe':
                    rc=self.ssh.exec_stream('uname -m; uname -a; lscpu | head -n 24; df -h ~; g++ --version | head -n 1; clang++ --version | head -n 1',log,self.stop_job)
                else:
                    avail=self.ssh.available_kib()
                    if avail is not None:
                        log(f'RVV Lab free disk space: {avail/1024/1024:.2f} GiB')
                        if avail < 2*1024*1024:raise RuntimeError('RVV Lab has less than 2 GiB free. Aborting before compilation.')
                        if avail < 5*1024*1024:log('WARNING: espace disque faible, surveiller les compilations')
                    with tempfile.TemporaryDirectory(prefix='rvvlab-studio-') as temp:
                        archive=Path(temp)/(run_id+'.zip')
                        manifest=build_source_zip(Path(cfg['repo']),archive,log)
                        log(f"Source locale : {manifest['files']} files, SHA256 {manifest['zip_sha256']}")
                        target=self.ssh.deploy(archive,manifest,run_id,cfg['remote_name'],log,self.stop_job)
                    if action=='push':rc=0
                    else:
                        rc=self.ssh.run(target,run_id,action,cfg,log,self.stop_job)
                        # Try reports EVEN on FAIL. Do not touch compilation artifacts.
                        try:
                            self.events.put(('report_status','Downloading lightweight reports automatically...'))
                            report=collect_via_client(self.ssh.client,run_id,output/'Rapports_legers',
                                                      cfg['remote_name'],printer=log)
                            self.events.put(('report_folder',str(report)))
                        except Exception as exc:
                            log('WARNING: lightweight reports unavailable: '+str(exc))
                status='PASS' if rc==0 else 'FAIL'
                log('FINAL: '+status+' (rc='+str(rc)+')')
        except Exception as exc:
            self.events.put(('test_line','ERROR: '+str(exc)+'\n'))
            status='FAIL'
            try:
                with full_log.open('a',encoding='utf-8') as fp:fp.write('ERROR: '+str(exc)+'\n')
            except OSError:pass
        finally:
            session={'id':run_id,'action':action,'status':status,'returncode':rc,
                     'created_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                     'duration_s':round(time.monotonic()-began,2),'git':(manifest or {}).get('git'),
                     'source_sha256':(manifest or {}).get('zip_sha256'),'source_path':target,
                     'run_settings':cfg,'report_dir':str(report) if report else None,
                     'detailed_log':str(full_log)}
            (output/f'rvvlab-session-{run_id}.json').write_text(json.dumps(session,indent=2,ensure_ascii=False),encoding='utf-8')
            self.events.put(('run_done',session))

    def download_reports(self):
        if self.job_busy or self.storage_busy:
            messagebox.showinfo('Campaign active','Wait for the campaign or automatic results collection to finish.');return
        if not self.ssh.connected():messagebox.showwarning('SSH','Connect to SSH first.');return
        try:remote=config_for_run(self._settings())['remote_name']
        except Exception as exc:messagebox.showerror('Configuration',str(exc));return
        run=self.rid.get().strip()
        if run:
            try:validate_run_id(run)
            except Exception as exc:messagebox.showerror('Session',str(exc));return
        self.report_btn.configure(state='disabled')
        self.report_status.set('Downloading lightweight reports...')
        threading.Thread(target=self._reports_worker,args=(remote,run),daemon=True).start()
    def _reports_worker(self,remote,run):
        try:
            if not run:run=latest_run(self.ssh.client,remote)
            folder=collect_via_client(self.ssh.client,run,Path(self.vars['results'].get())/'Rapports_legers',remote,
                                      printer=lambda x:self.events.put(('report_status',str(x))))
            self.events.put(('report_folder',str(folder)))
            self.events.put(('report_done','Lightweight reports downloaded for '+run))
        except Exception as exc:self.events.put(('report_done','Report download failed: '+str(exc)))

    def refresh_reports(self):
        base=Path(self.vars['results'].get()).expanduser()/'Rapports_legers'
        self.report_list.delete(0,'end')
        if not base.is_dir():return
        for p in sorted(base.glob('rvvlab-*'),reverse=True):
            if p.is_dir() and (p/'00_DIAGNOSTIC.md').exists():self.report_list.insert('end',p.name)
    def report_selected(self,event=None):
        sel=self.report_list.curselection()
        if not sel:return
        self.latest_folder=Path(self.vars['results'].get()).expanduser()/'Rapports_legers'/self.report_list.get(sel[0])
        self.load_report('00_DIAGNOSTIC.md')
    def load_report(self,name):
        if not self.latest_folder:
            self.refresh_reports()
            if self.report_list.size():self.latest_folder=Path(self.vars['results'].get()).expanduser()/'Rapports_legers'/self.report_list.get(0)
        if not self.latest_folder:return
        file=self.latest_folder/name
        try:txt=file.read_text(encoding='utf-8',errors='replace')
        except OSError as exc:txt=str(exc)
        self.report_text.configure(state='normal');self.report_text.delete('1.0','end')
        self.report_text.insert('end',txt);self.report_text.configure(state='disabled')
    def open_reports(self):
        folder=self.latest_folder or Path(self.vars['results'].get()).expanduser()/'Rapports_legers'
        folder.mkdir(parents=True,exist_ok=True)
        open_local(folder)

    def _poll(self):
        try:
            for _ in range(180):
                try:kind,msg=self.events.get_nowait()
                except queue.Empty:break
                if kind=='connected':
                    self.connecting=False
                    self.status.set(msg);self.console_status.set('SSH console connected')
                    self.connect_btn.configure(state='disabled');self.disconnect_btn.configure(state='normal')
                    self._enable_console(True)
                    self.shell_entry.focus_set()
                    self.root.after(1000,self.unified_campaigns.refresh_remote)
                    self._test94_live_profiles.discard(self.active_profile)
                    self._test94_draw_badges()
                    self.root.after(2400,self._test94_check_now)
                    # Read-only inventory after connection. Never auto-start a job.
                    self.root.after(6500,lambda:self._center_auto_check(0))
                elif kind=='connect_fail':
                    self.connecting=False
                    self.status.set('SSH failure: '+msg)
                    self.connect_btn.configure(state='normal')
                    self.console_status.set('Disconnected')
                elif kind=='test94_state':
                    profile=msg.get('profile')
                    if profile in self.target_test94_labels:
                        self._test94_status_records[profile]=msg
                        if msg.get('verified') and self.active_profile==profile and self.ssh.connected():
                            self._test94_live_profiles.add(profile)
                        self._test94_draw_badges()
                elif kind=='test94_polled':
                    self._test94_poll_busy=False
                    profile,record=msg
                    self._test94_status_records[profile]=record
                    if self.active_profile==profile and self.ssh.connected():
                        self._test94_live_profiles.add(profile)
                    self._test94_draw_badges()
                elif kind=='test94_poll_error':
                    self._test94_poll_busy=False
                    profile,error=msg
                    self._test94_live_profiles.discard(profile)
                    # Keep the previous result. It is now explicitly stale.
                    self._test94_draw_badges()
                elif kind=='test94_status_error':
                    pass  # A cache write failure must never stop a remote test.
                elif kind=='console':self._append(self.console_out,clean_terminal(msg))
                elif kind=='console_done':
                    if self.console_chan and not self.ssh.connected():self._enable_console(False)
                elif kind=='test_line':self._append(self.test_out,msg)
                elif kind=='run_done':
                    self.job_busy=False;self._enable_runs(True)
                    self.last_session=msg
                    self.job_status.set(f"{msg['action']} : {msg['status']} ({msg['duration_s']:.0f}s)")
                    self._append(self.test_out,f"Fin : {msg['status']} | journal complet : {msg['detailed_log']}\n")
                    self.rid.set(msg['id']);self.refresh_reports()
                elif kind=='report_status':self.report_status.set(msg)
                elif kind=='report_folder':
                    self.latest_folder=Path(msg)
                    self.report_status.set('Lightweight reports: '+msg)
                    self.refresh_reports();self.load_report('00_DIAGNOSTIC.md')
                elif kind=='report_done':
                    self.report_btn.configure(state='normal')
                    self.report_status.set(msg)
                elif kind=='night_line':self._append(self.night_output,msg)
                elif kind=='night_status':self.night_status.set(msg)
                elif kind=='night_rows':self._night_show_rows(msg)
                elif kind=='night_finished':
                    self.night_busy=False
                    if hasattr(self,'test_center'):self.test_center.refresh_local()
                    for b in (self.night_start_btn,self.night_refresh_btn,self.night_sync_btn,self.night_stop_btn):b.configure(state='normal')
                    if msg:self.night_status.set(msg)
                elif kind=='storage_line':self._append(self.storage_output,msg)
                elif kind=='storage_inventory':self._storage_show_inventory(msg)
                elif kind=='storage_finished':
                    self.storage_busy=False
                    for b in (self.storage_refresh,self.storage_sync,self.storage_sync_all,self.storage_purge,self.storage_purge_all):
                        b.configure(state='normal')
                    self._enable_runs(not self.job_busy)
                    if msg.startswith('Failed'):self.storage_status.set(msg)
        finally:
            self.root.after(75,self._poll)

    def _quit(self):
        if self.storage_busy or self.night_busy:
            messagebox.showwarning('Active synchronization',
                'Wait for sync or purge to finish before exiting.');return
        if self.job_busy and not messagebox.askyesno('Exit','A campaign is active. Closing Studio may leave a process running on RVV Lab. Exit?'):
            return
        self.stop_job.set();self.console_stop.set()
        try:self.ssh.close()
        except Exception:pass
        self.root.destroy()


def main():
    # Advisory OS lock, held for lifetime; release even if Studio exits abruptly.
    chosen=TARGET or read_previous_settings().get('machine_profile','Cloud-V')
    if chosen not in ('Cloud-V','EPCC'):chosen='Cloud-V'
    guard=MachineLock()
    if not guard.acquire(chosen):
        popup=tk.Tk();popup.withdraw()
        try:messagebox.showwarning('Lab Studio déjà ouvert',
              'Une fenêtre pilote déjà '+chosen+'. Ouvrez le lanceur de l’autre machine.')
        finally:popup.destroy()
        return
    root=None
    try:
        root=tk.Tk()
        try:
            if sys.platform=='win32':ttk.Style().theme_use('vista')
            else:ttk.Style().theme_use('clam')
        except tk.TclError:pass
        app=Studio(root)
        app._machine_lock=guard
        root.mainloop()
    finally:
        if root:
            try:root.destroy()
            except tk.TclError:pass
        guard.release()

if __name__=='__main__':main()
