"""Single shared corpus library screen; deliberately no independent SSH session."""
from __future__ import annotations
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import messagebox,ttk

from rvvlab_corpus_service import (LAB,catalog,inspect_local,prepare_local,
                                   remote_probe,require_remote,sync_remote)

class CorpusLibraryPanel:
    def __init__(self,parent,studio):
        self.parent=parent;self.studio=studio
        self.busy=False
        self.local_info={'state':'absent'}
        self.events=queue.Queue()
        self.per_machine={'Cloud-V':'Non vérifié','EPCC':'Non vérifié'}
        self.local=tk.StringVar(value='Vérification locale nécessaire')
        self.remote=tk.StringVar(value='Connectez la machine puis cliquez Vérifier serveur')
        self.notice=tk.StringVar(value='Corpus partagé facultatif pour les anciens tests ; pas de modification des mesures historiques.')
        self._build()
        self.profile_changed()
        parent.after(250,self._drain)

    def _build(self):
        panel=ttk.Frame(self.parent,style='Surface.TFrame',padding=20)
        panel.pack(fill='both',expand=True,padx=7,pady=7)
        ttk.Label(panel,text='Bibliothèque JSON commune',style='Section.TLabel').pack(anchor='w',pady=(0,8))
        c=catalog()
        ttk.Label(panel,text=c['description']+' · '+c['id'],style='Muted.TLabel').pack(anchor='w')
        ttk.Label(panel,text='Source : '+c['source']+' · Commit '+c['commit'][:12],style='Muted.TLabel').pack(anchor='w',pady=(2,12))
        state=ttk.Frame(panel,style='Surface.TFrame');state.pack(fill='x',pady=6)
        ttk.Label(state,text='PC :',width=11).grid(row=0,column=0,sticky='w',pady=4)
        ttk.Label(state,textvariable=self.local).grid(row=0,column=1,sticky='w')
        ttk.Label(state,text='Serveur :',width=11).grid(row=1,column=0,sticky='w',pady=4)
        ttk.Label(state,textvariable=self.remote).grid(row=1,column=1,sticky='w')
        bar=ttk.Frame(panel,style='Surface.TFrame');bar.pack(fill='x',pady=(10,12))
        self.prepare_btn=ttk.Button(bar,text='1. Préparer / vérifier les JSON',command=self.prepare)
        self.prepare_btn.pack(side='left',padx=(0,8))
        self.sync_btn=ttk.Button(bar,text='2. Synchroniser la machine',command=self.sync)
        self.sync_btn.pack(side='left',padx=(0,8))
        self.check_btn=ttk.Button(bar,text='Vérifier serveur',command=self.check)
        self.check_btn.pack(side='left',padx=(0,8))
        ttk.Button(bar,text='Ouvrir cache',command=self.open_folder).pack(side='left')
        ttk.Label(panel,text='Fichiers JSON épinglés — taille et empreinte après préparation',style='CardTitle.TLabel').pack(anchor='w',pady=(7,8))
        tablebox=ttk.Frame(panel,style='Surface.TFrame');tablebox.pack(fill='both',expand=True)
        self.table=ttk.Treeview(tablebox,columns=('name','bytes','hash'),show='headings',height=13)
        for col,title,width in [('name','Fichier',300),('bytes','Taille',120),('hash','SHA-256',470)]:
            self.table.heading(col,text=title)
            self.table.column(col,width=width,minwidth=80,anchor='w')
        scroll=ttk.Scrollbar(tablebox,orient='vertical',command=self.table.yview)
        self.table.configure(yscrollcommand=scroll.set)
        self.table.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        ttk.Label(panel,textvariable=self.notice,style='Muted.TLabel',wraplength=900).pack(anchor='w',pady=(12,0))

    def profile_changed(self):
        p=self.studio.active_profile
        self.remote.set(p+' : '+self.per_machine[p])
        self._update_buttons()
        self.inspect()

    def inspect(self):
        data=inspect_local(LAB)
        self.local_info=data
        if data['state']=='verified':
            self.local.set('Vérifié · '+str(data['count'])+' JSON · '+format(data['total_bytes']/1048576,'.1f')+' Mio · SHA '+data['digest'][:16])
        elif data['state']=='invalid':self.local.set('Invalide : '+data.get('error',''))
        else:self.local.set('Absent — préparer une fois (Internet requis)')
        for id in self.table.get_children():self.table.delete(id)
        for row in data.get('files',[]):
            self.table.insert('', 'end',values=(row['name'],str(row['bytes'])+' octets',row['sha256']))
        if not data.get('files'):
            for name in catalog()['files']:self.table.insert('','end',values=(name,'—','—'))
        self._update_buttons()

    def _update_buttons(self):
        connected=self.studio.ssh.connected()
        canremote=(connected and not self.busy and
                   not getattr(self.studio,'connecting',False) and
                   not self.studio.test_runner.busy and
                   not self.studio.test_runner.poll_busy and
                   not self.studio.simple_tests.busy and
                   not self.studio.simple_tests.poll_busy)
        self.prepare_btn.configure(state='disabled' if self.busy else 'normal')
        self.sync_btn.configure(state='normal' if canremote and self.local_info['state']=='verified' else 'disabled')
        self.check_btn.configure(state='normal' if canremote and self.local_info['state']=='verified' else 'disabled')

    def _work(self,which,fn):
        if self.busy:return
        self.busy=True;self._update_buttons()
        p=self.studio.active_profile
        def run():
            try:res=fn();self.events.put((which,p,res,None))
            except Exception as e:self.events.put((which,p,None,str(e)))
        threading.Thread(target=run,daemon=True).start()

    def prepare(self):
        self.notice.set('Préparation/validation en cours…')
        self._work('prepare',lambda:prepare_local(LAB))

    def sync(self):
        if not self.studio.ssh.connected():return
        name=self.studio.vars['remote_name'].get().strip()
        p=self.studio.active_profile
        self.notice.set('Synchronisation de '+p+' et vérification du ZIP…')
        self._work('sync',lambda:sync_remote(self.studio.ssh,name,LAB))

    def check(self):
        if not self.studio.ssh.connected():return
        name=self.studio.vars['remote_name'].get().strip()
        self.notice.set('Vérification distante, lecture seule…')
        def task():
            v=inspect_local(LAB)
            if v['state']!='verified':return {'state':'unavailable'}
            return remote_probe(self.studio.ssh,name,v['digest'],deep=True)
        self._work('check',task)

    def open_folder(self):
        from rvvlab_corpus_service import cache_dir
        folder=cache_dir(LAB);folder.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':os.startfile(str(folder))
        else:messagebox.showinfo('Cache JSON local',str(folder))

    def _drain(self):
        try:
            while True:
                which,p,data,error=self.events.get_nowait()
                self.busy=False
                if error:
                    self.notice.set('Erreur : '+error[:550])
                    if which!='prepare':self.per_machine[p]='Erreur de vérification'
                elif which=='prepare':
                    self.notice.set('ZIP local prêt ; cliquez Synchroniser sur chaque machine connectée.')
                else:
                    status=data.get('state','unknown')
                    if status=='verified':
                        self.per_machine[p]='✓ '+str(data.get('count','18'))+' JSON vérifiés · '+data['data']
                        self.notice.set('Corpus disponible pour les tests qui le demandent : '+data['data'])
                    elif status=='absent':
                        self.per_machine[p]='Absent (synchronisation requise)'
                        self.notice.set('Ce serveur ne possède pas encore ce corpus.')
                    else:
                        self.per_machine[p]='Incomplet/invalide : '+str(data.get('reason',status))
                        self.notice.set('Synchronisez à nouveau pour réparer le cache distant.')
                self.inspect()
                self.remote.set(self.studio.active_profile+' : '+self.per_machine[self.studio.active_profile])
        except queue.Empty:pass
        self.parent.after(250,self._drain)
