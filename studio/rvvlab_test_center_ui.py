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
        self.search=tk.StringVar(value='');self.state_filter=tk.StringVar(value='Tous les états')
        self.notice=tk.StringVar(value='États locaux chargés. Connectez SSH puis cliquez « Vérifier serveur ».')
        self.stats=tk.StringVar(value='')
        self.title=tk.StringVar(value='Sélectionnez un test')
        self.summary=tk.StringVar(value='Aucune sélection')
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
        ttk.Label(header,text='Centre des tests',font=('Segoe UI',18,'bold')).pack(side='left')
        ttk.Label(header,text='Tous les profils · preuves vérifiables · aucune relance automatique',
                  foreground='#687382').pack(side='left',padx=(20,0))
        top=ttk.Frame(p);top.pack(fill='x',pady=(0,9))
        ttk.Label(top,textvariable=self.stats,font=('Segoe UI',11,'bold')).pack(side='left')
        ttk.Label(top,text='Machine : '+self.studio.active_profile,foreground='#526579').pack(side='right')
        bar=ttk.Frame(p);bar.pack(fill='x',pady=(0,7))
        ttk.Label(bar,text='Rechercher').pack(side='left')
        ttk.Entry(bar,textvariable=self.search,width=28).pack(side='left',fill='x',expand=True,padx=(7,15))
        cb=ttk.Combobox(bar,textvariable=self.state_filter,state='readonly',width=20,values=(
            'Tous les états','Téléchargés','Terminés serveur','En cours','Échecs','À vérifier'))
        cb.pack(side='left',padx=(0,7))
        ttk.Button(bar,text='Effacer',command=self._clear).pack(side='left')
        controls=ttk.Frame(p);controls.pack(fill='x',pady=(0,8))
        self.refresh_button=ttk.Button(controls,text='Actualiser local',command=self.refresh_local)
        self.refresh_button.pack(side='left',padx=(0,7))
        self.check_button=ttk.Button(controls,text='Vérifier le serveur',command=self.check_remote)
        self.check_button.pack(side='left',padx=(0,7))
        self.download_button=ttk.Button(controls,text='Télécharger / synchroniser',command=self.download)
        self.download_button.pack(side='left',padx=(0,7))
        self.open_button=ttk.Button(controls,text='Ouvrir les résultats',command=self.open_results)
        self.open_button.pack(side='left',padx=(0,7))
        self.run_button=ttk.Button(controls,text='Lancer le test sélectionné…',command=self.run)
        self.run_button.pack(side='right')
        cols=('number','test','state','evidence')
        frame=ttk.Frame(p);frame.pack(fill='both',expand=True)
        frame.columnconfigure(0,weight=4);frame.columnconfigure(1,weight=2)
        frame.rowconfigure(0,weight=1)
        box=ttk.Frame(frame);box.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        self.tree=ttk.Treeview(box,columns=cols,show='headings',height=13,selectmode='browse')
        for col,heading,width in [('number','N°',62),('test','Expérience',260),('state','État',160),('evidence','Preuve',235)]:
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
        pane=ttk.LabelFrame(frame,text='Détails du test sélectionné',padding=13)
        pane.grid(row=0,column=1,sticky='nsew')
        ttk.Label(pane,textvariable=self.title,font=('Segoe UI',12,'bold'),wraplength=320).pack(anchor='w',pady=(3,14))
        ttk.Label(pane,textvariable=self.summary,font=('Segoe UI',11,'bold'),wraplength=300).pack(anchor='w',pady=(0,9))
        ttk.Label(pane,text='Ce qui est réellement confirmé',foreground='#5b6571').pack(anchor='w',pady=(12,4))
        ttk.Label(pane,textvariable=self.evidence,wraplength=320,justify='left').pack(anchor='w')
        ttk.Separator(pane).pack(fill='x',pady=14)
        ttk.Label(pane,text='Prochaine action',foreground='#5b6571').pack(anchor='w',pady=(2,4))
        ttk.Label(pane,textvariable=self.actions,wraplength=320,justify='left').pack(anchor='w')
        ttk.Button(pane,text='Voir le Test Runner et ses journaux',
                   command=lambda:self.studio.notebook.select(self.studio.test_runner_tab)).pack(anchor='w',pady=(25,0))
        footer=ttk.Frame(p);footer.pack(fill='x',pady=(10,0))
        ttk.Label(footer,textvariable=self.notice,foreground='#40546c',wraplength=980).pack(anchor='w')
        ttk.Label(footer,text='PASS local ≠ terminé sur le serveur. Une archive locale ≠ validation JSON complète.',
                  foreground='#687382').pack(anchor='w',pady=(5,0))
        self.search.trace_add('write',lambda *_:self._redraw())
        self.state_filter.trace_add('write',lambda *_:self._redraw())

    def _clear(self):self.search.set('');self.state_filter.set('Tous les états')

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
                merged.update(state='unknown',proof='Ancien état actif ; nouvelle vérification SSH nécessaire')
        # A completed/partial NightRuns snapshot may have been recovered outside
        # TestRunner (old runs, different Studio versions). Honor SHA256 marker.
        if key!=TEST94_KEY and key in self.remote:
            runid=str(self.remote[key].get('id',''))
            from rvvlab_test_center import NIGHT_ID
            if NIGHT_ID.fullmatch(runid):
                path=Path(self.studio.vars['results'].get()).expanduser()/'NightRuns'/runid
                if (path/'SYNC_OK.txt').is_file():
                    merged.update(state='downloaded',downloaded=True,directory=str(path),
                        proof='Snapshot SHA256 vérifié sur PC'+
                        (' · campagne arrêtée (partielle)' if str(self.remote[key].get('state'))=='stopped' else ''))
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
            if statefilter=='Téléchargés' and typ!='downloaded':continue
            if statefilter=='Terminés serveur' and typ!='completed':continue
            if statefilter=='En cours' and typ not in ('running','queued','building'):continue
            if statefilter=='Échecs' and typ not in ('failed','stopped'):continue
            if statefilter=='À vérifier' and typ not in ('unknown','local_pass'):continue
            match=__import__('re').match(r'^(\d+)',item['script_path'].stem)
            number=match.group(1) if match else '—'
            tag=('done' if typ in ('downloaded','completed') else 'active' if typ in ('running','queued','building')
                 else 'bad' if typ in ('failed','stopped') else 'unknown')
            self.tree.insert('','end',iid=key,values=(number,name,label(typ),state['proof']),tags=(tag,))
        self.stats.set(f"{len(self._records())} tests  ·  {stats['downloaded']} téléchargés  ·  {stats['completed']} terminés distants  ·  "
                       f"{stats['running']+stats['queued']+stats['building']} actifs  ·  {stats['failed']} en échec")
        chosen=before if before in self.tree.get_children() else (self.tree.get_children()[0] if self.tree.get_children() else '')
        if chosen:self.tree.selection_set(chosen);self.tree.see(chosen)
        self._details()

    def _details(self):
        key=self._selection()
        if key is None:
            self.title.set('Aucun test sélectionné');self.summary.set('');self.evidence.set('');self.actions.set('');return
        state=self._effective(key)
        item=next((v for v in self._records() if v['id']==key),None)
        self.title.set(item['title'] if item else key)
        self.summary.set(label(state['state'])+'  ·  '+self.studio.active_profile)
        self.evidence.set(state['proof']+'\n\n'+('Dernier contrôle distant connu (instantané).' if key in self.remote else 'Information locale uniquement.')+
                          ('\nDossier: '+Path(state['directory']).name if state.get('directory') else '')+
                          ('\nRun: '+state['run_id'] if state.get('run_id') else ''))
        if state['state']=='downloaded':nextstep='Résultats présents sur PC. Ouvrir pour les analyser.'
        elif state['state']=='completed':nextstep='Résultat distant confirmé. Cliquer Télécharger / synchroniser.'
        elif state['state'] in ('running','queued','building'):nextstep='Ne pas relancer. Revérifier plus tard.'
        elif state['state']=='failed':nextstep='Consulter le journal puis relancer si nécessaire.'
        else:nextstep='Vérifier le serveur avant de conclure ou de lancer.'
        self.actions.set(nextstep)

    def check_remote(self):
        if (self.busy or self.studio.test_runner.busy or self.studio.night_busy or self.studio.storage_busy
                or self.studio.job_busy or self.studio.unified_campaigns.busy):
            self.notice.set('Une opération est en cours. Réessayez plus tard.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connectez cette instance au serveur avant de vérifier les tests.');return
        self.busy=True;self.notice.set('Vérification en cours : NightRuns + tests EPCC 94/96/97 (lecture seule)…')
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
                    self.notice.set(f'Verification serveur terminée : {len(runs)} campagnes NightRuns, '
                                    f'{len(mapping)} associées à un test; Test94 : {test94.get("state","inconnu")}; '
                                    f'{len(epcc)} exécutions EPCC détectées.')
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
                    self.notice.set('Résultats EPCC vérifiés SHA256 et téléchargés : '+data)
                    self.refresh_local()
                    if hasattr(self.studio,'unified_campaigns'):
                        self.studio.unified_campaigns.refresh_remote()
                elif event=='sync_error':
                    self.busy=False
                    self.notice.set('Téléchargement EPCC refusé : '+str(data)[:220])
                    messagebox.showerror('Téléchargement EPCC',str(data))
                elif event=='check_error':
                    self.busy=False;self.pending94=False
                    self.notice.set('Échec vérification SSH : '+str(data)[:160]+' — état précédent non confirmé. Aucun test lancé.')
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
            messagebox.showinfo('Résultats','Aucun dossier local pour ce test. Vérifiez le serveur puis synchronisez.');return
        if __import__('sys').platform=='win32':__import__('os').startfile(str(target))
        else:messagebox.showinfo('Répertoire des résultats',str(target))

    def download(self):
        item,state=self._item_and_state()
        if item is None:return
        if state['downloaded'] and not (self.studio.active_profile=='EPCC'
                and item['id'] in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY)
                and self.remote.get(item['id'],{}).get('packet')
                and self.remote[item['id']]['id']!=state.get('run_id')):
            self.open_results();return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connectez SSH puis vérifiez le serveur avant le téléchargement.');return
        if self.busy:
            self.notice.set('Une opération est déjà en cours.');return
        # Test94, Test96 and Test97 have their own EPCC directories, not NightRuns.
        if self.studio.active_profile=='EPCC' and item['id'] in (TEST94_KEY,TEST96_KEY,TEST97_KEY,TEST98_KEY):
            record=self.remote.get(item['id'])
            if not record or not record.get('id'):
                messagebox.showinfo('Synchronisation EPCC',
                    'Vérifiez le serveur : aucune exécution EPCC associée au test sélectionné.');return
            if not record.get('packet'):
                messagebox.showinfo('Synchronisation EPCC',
                    'Exécution EPCC trouvée : '+record['id']+'\n'
                    'Mais aucune archive de résultats n’existe encore. Consultez les journaux Slurm ou compilation.');return
            runid=record['id']
            self.busy=True
            self.notice.set('Téléchargement EPCC SHA256 en cours : '+runid+'…')
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
                messagebox.showinfo('Test94','Cliquez Vérifier le serveur. Aucun paquet Test94 confirmé actuellement.');return
            self.studio.remote94_last=dict(self.remote94)
            self.studio.notebook.select(self.studio.test_runner_tab)
            self.studio.test_runner.recover_test94();return
        run_id=state.get('run_id')
        if not run_id or item['id'] not in self.remote:
            messagebox.showinfo('Synchronisation',
                'Aucun identifiant de campagne vérifié pour ce test.\n'
                'Cliquez « Vérifier le serveur » puis choisissez une campagne. '
                'Aucune donnée ne sera téléchargée sans correspondance fiable.')
            return
        self.notice.set('Synchronisation SHA256 de '+run_id+'…')
        self.studio._night_run('sync',run_id)

    def request_launch94(self):
        """Always get a *fresh* remote check before allowing a 1h launch."""
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connectez SSH avant de lancer Test 94.');return
        if self.busy or self.pending94:
            messagebox.showinfo('Vérification','Une vérification est déjà en cours.');return
        self.pending94=True
        self.check_remote()
        if not self.busy:self.pending94=False

    def _after_check94(self,remote):
        state=str(remote.get('state') or 'unknown')
        if state in ('completed','running','queued','building') and (state!='completed' or remote.get('packet')):
            messagebox.showinfo('Anti-doublon Test 94',
                'Test 94 déjà '+state+' sur '+self.studio.active_profile+' : aucun second lancement.\n'
                'Vous pouvez vérifier ou récupérer les résultats.');return
        if state=='unknown' and remote.get('id'):
            if not messagebox.askyesno('État distant incertain',
                'Une tentative Test 94 existe sur le serveur, sans preuve de fin et sans job actif trouvé.\n'
                'Une nouvelle exécution pourrait dupliquer une tâche non visible.\n\n'
                'Poursuivre vers la confirmation de lancement ?'):return
        self.studio.notebook.select(self.studio.test_runner_tab)
        self.studio.test_runner._run_test94_after_remote_check()

    def run(self):
        item,state=self._item_and_state()
        if item is None:return
        if not item['enabled']:
            messagebox.showwarning('Test désactivé','Ce manifeste est désactivé. Rien ne sera lancé.');return
        if not self.studio.ssh.connected():
            messagebox.showwarning('SSH','Connectez SSH avant de lancer.');return
        if item['id']==TEST94_KEY:
            self.request_launch94();return
        if state['state'] in ('running','queued'):
            messagebox.showwarning('Test actif','La dernière vérification indique un travail actif. Pas de doublon.');return
        if not messagebox.askyesno('Confirmation',
            'Lancer '+item['title']+' sur '+self.studio.active_profile+' ?\n\n'
            'Cette action peut occuper le serveur pendant plusieurs heures. '
            'Le statut affiché ne prouve pas à lui seul l’absence d’un autre travail.'):return
        self.studio.notebook.select(self.studio.test_runner_tab)
        self.studio.test_runner._run([item])
