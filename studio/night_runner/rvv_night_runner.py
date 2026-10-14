#!/usr/bin/env python3
"""RVV Lab Night Explorer v1: eight-hour capped, compact, crash-resumable screening.

Standalone server-side worker; starts from a pinned uploaded source snapshot.
No sudo, git push, background network service, or deletion outside its own workdir.
The exploratory ratios are hypotheses, not publication-quality benchmarks.
"""
from __future__ import annotations
import argparse, collections, contextlib, csv, datetime as dt, hashlib, importlib.util, io, json, math
import os, pathlib, random, shutil, signal, statistics, subprocess, sys, tempfile, threading, time, zipfile

GiB = 1024 ** 3
MiB = 1024 ** 2
MAX_HOURS = 8.0
WORK_CAP = 2 * GiB
FREE_FLOOR = 200 * 1024 * 1024
MIN_BUILD_FREE = FREE_FLOOR
MAX_SNAPSHOT = 12 * MiB
RESULT_FIELDS = ('timestamp','phase','variant','defines','corpus','bytes','parse_iterations','trial',
                 'dom_all_gbps','stage1_gbps','stage2_gbps','all_cpb','stage1_cpb','stage2_cpb')
RUN_FILES = ('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json')


def utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def atomic_write(path, text):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        f.write(text)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_json(path, obj): atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True)+'\n')


def folder_bytes(path):
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        dirs[:] = [d for d in dirs if not (pathlib.Path(root)/d).is_symlink()]
        for name in files:
            p = pathlib.Path(root)/name
            if not p.is_symlink():
                with contextlib.suppress(OSError): total += p.stat().st_size
    return total


def guarded_space(workdir, *, building=False):
    root = pathlib.Path(workdir)
    free = shutil.disk_usage(root).free
    used = folder_bytes(root)
    if free < (MIN_BUILD_FREE if building else FREE_FLOOR):
        raise SafetyStop(f'espace disque insuffisant : {free/GiB:.2f} Gio libres')
    if used > WORK_CAP:
        raise SafetyStop(f'quota Night Runner dépassé : {used/GiB:.2f} Gio / 2 Gio')
    return free, used


class SafetyStop(Exception): pass


class Stopped(Exception): pass


def run_bounded(cmd, *, cwd=None, env=None, workdir=None, deadline=None, stopfile=None, building=False):
    """Keep bounded stdout/stderr separately, monitor deadline and disk.

    In particular, benchmark/dom/parse writes a progress bar to stderr
    WITHOUT a final newline, and TSV measurement rows to stdout. Merging the
    streams prefixes the quoted TSV row with progress-bar control characters
    and makes bench_native.parse_tabbed_output reject every sample.
    """
    stdout_tail = collections.deque(maxlen=32)
    stderr_tail = collections.deque(maxlen=32)
    p = subprocess.Popen(list(map(str, cmd)), cwd=cwd, env=env, text=True, errors='replace',
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=1,
                         start_new_session=True)
    def reader(stream, tail):
        try:
            for line in stream: tail.append(line.rstrip()[:2400])
        except (OSError, ValueError): pass
    threads=[threading.Thread(target=reader,args=(p.stdout,stdout_tail),daemon=True),
             threading.Thread(target=reader,args=(p.stderr,stderr_tail),daemon=True)]
    for t in threads:t.start()
    exception = None
    try:
        while p.poll() is None:
            if stopfile and pathlib.Path(stopfile).exists():
                exception = Stopped('Arrêt demandé par l’utilisateur'); break
            if deadline and time.time() >= deadline:
                exception = Stopped('Durée maximale de huit heures atteinte'); break
            if workdir:
                try: guarded_space(workdir,building=building)
                except SafetyStop as e:
                    exception = e; break
            time.sleep(2)
        if exception:
            with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGTERM)
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError): os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            raise exception
        rc=p.wait()
        for t in threads:t.join(timeout=2)
        if rc:
            raise RuntimeError(f'Commande échouée (rc={rc}): '+ ' '.join(map(str,cmd[:5])) +
                               '\n[stdout]\n'+'\n'.join(stdout_tail)+
                               '\n[stderr]\n'+'\n'.join(stderr_tail))
        return '\n'.join(stdout_tail)
    finally:
        with contextlib.suppress(Exception):p.stdout.close()
        with contextlib.suppress(Exception):p.stderr.close()


def candidate_defs(bn):
    return [
        ('current', {}, 'rvv', 'vla'),
        ('sparse_index_8', dict(bn.VLA_VARIANTS['sparse-index']), 'rvv', 'vla'),
        ('packed_index', dict(bn.VLA_VARIANTS['packed-index']), 'rvv', 'vla'),
        ('upstream_vls256', {}, 'rvv_vls', 'vls'),
    ]


def rank_rows(rows):
    """Exploratory ratios to upstream v5.0.3 VLS256 for matched trial/corpus."""
    controls={(r['corpus'],r['parse_iterations'],r['trial']):r for r in rows if r['variant']=='upstream_vls256'}
    ratios={}
    for r in rows:
        key=(r['corpus'],r['parse_iterations'],r['trial'])
        control=controls.get(key)
        if not control:continue
        label=r['variant']
        for m in ('dom_all','stage1','stage2'):
            try:
                b=float(control[f'{m}_gbps']); v=float(r[f'{m}_gbps'])
            except (KeyError,TypeError,ValueError):continue
            if b>0 and v>0 and math.isfinite(b) and math.isfinite(v):
                ratios.setdefault((label,m),[]).append(v/b)
    summary=[]
    for (name,m), vals in sorted(ratios.items()):
        med=statistics.median(vals)
        mad=statistics.median(abs(x-med) for x in vals)
        gm=math.exp(sum(math.log(x) for x in vals)/len(vals))
        summary.append({'variant':name,'metric':m,'paired_n':len(vals),'median_ratio':round(med,5),
                        'geomean_ratio':round(gm,5),'mad_ratio':round(mad,5)})
    return sorted(summary,key=lambda a:(a['metric'], -a['geomean_ratio']))


def csv_data(path):
    if not pathlib.Path(path).exists():return []
    with open(path,newline='',encoding='utf-8') as f:return list(csv.DictReader(f))


def write_csv(path, fields, rows):
    p=pathlib.Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    temp=p.with_suffix(p.suffix+'.tmp')
    with temp.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    os.replace(temp,p)


def snapshot(run_dir):
    """Single compact ZIP, SHA manifest, atomic replacement; no builds or nested ZIPs."""
    run_dir=pathlib.Path(run_dir)
    tmp=run_dir/'snapshot.zip.tmp'; fin=run_dir/'snapshot.zip'
    manifest={'schema':1,'created_utc':utc(),'files':[]}
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in RUN_FILES:
            p=run_dir/name
            if not p.is_file():continue
            data=p.read_bytes()
            manifest['files'].append({'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
            z.writestr(name,data)
        z.writestr('MANIFEST.json',json.dumps(manifest,ensure_ascii=False,sort_keys=True))
    if tmp.stat().st_size > MAX_SNAPSHOT:
        tmp.unlink();raise SafetyStop('Rapport compact > 12 Mio : arrêt préventif')
    os.replace(tmp,fin)
    atomic_write(run_dir/'snapshot.sha256',hashlib.sha256(fin.read_bytes()).hexdigest()+'\n')


def write_hypotheses(run_dir, ranking, state):
    lines=['# Carte exploratoire RVV — hypothèses (non validées)', '',
           f"- Heure UTC : {utc()}", f"- État : {state.get('state')}",
           f"- Mesures : {state.get('observations',0)}", '- Référence : `upstream_vls256`, comparaisons appariées par corpus, itérations et essai.',
           '- Les candidats expérimentaux ne sont **pas** encore validés en correction.',
           '- Ce balayage ne mesure que DOM, Stage 1 et Stage 2 : ni minify ni UTF-8.',
           '', '| Variante | Mesure | Ratio géométrique | N | MAD |', '|---|---|---:|---:|---:|']
    for r in ranking:
        lines.append(f"| {r['variant']} | {r['metric']} | {r['geomean_ratio']:.3f}× | {r['paired_n']} | {r['mad_ratio']:.3f} |")
    lines+=['','## Pistes à confirmer','']
    best=[r for r in ranking if r['metric']=='stage1' and r['variant']!='upstream_vls256' and r['paired_n']>=2]
    best.sort(key=lambda r:r['geomean_ratio'],reverse=True)
    for r in best[:3]:
        lines.append(f"- `{r['variant']}` : Stage 1 {r['geomean_ratio']:.3f}× `upstream_vls256` (N={r['paired_n']}); à valider avec les tests natifs GCC/Clang et corpus complets.")
    if not best:lines.append('- Mesures appariées insuffisantes pour émettre une hypothèse.')
    lines+=['','Aucune victoire issue de ce balayage ne doit être considérée comme établie avant une campagne lourde indépendante.','']
    atomic_write(pathlib.Path(run_dir)/'hypotheses.md','\n'.join(lines))



class Explorer:
    def __init__(self, source, root, hours=8, jobs=2, core=0, resume=False):
        self.source=pathlib.Path(source).resolve();self.root=pathlib.Path(root).resolve()
        self.hours=min(float(hours),MAX_HOURS);self.jobs=min(max(1,int(jobs)),2);self.core=int(core)
        self.root.mkdir(parents=True,exist_ok=True)
        self.stopfile=self.root/'STOP'
        self.started=(json.loads((self.root/'checkpoint.json').read_text())['started_epoch'] if resume and (self.root/'checkpoint.json').exists() else time.time())
        self.deadline=self.started + self.hours*3600
        self.state={'state':'preflight','started_utc':dt.datetime.fromtimestamp(self.started,dt.timezone.utc).isoformat(),
                    'deadline_utc':dt.datetime.fromtimestamp(self.deadline,dt.timezone.utc).isoformat(),
                    'source':str(self.source),'jobs':self.jobs,'core':self.core,'observations':0,
                    'note':'EXPLORATION : pas de publication automatique','last_update':utc()}
        self.last_snapshot=0
        self.rows=csv_data(self.root/'map.csv')
        self.state['observations']=len(self.rows)
        self.failures=csv_data(self.root/'failures.csv')
        self.binaries={}
        self.bn=None
        self.metadata={}

    def check(self,building=False):
        if self.stopfile.exists():raise Stopped('Arrêt demandé')
        if time.time()>=self.deadline:raise Stopped('Budget 8h atteint')
        guarded_space(self.root,building=building)
        moment=time.monotonic()
        if moment-getattr(self,'last_disk_monitor_monotonic',float('-inf'))>=900:
            self.last_disk_monitor_monotonic=moment
            self.state['disk_last_15m_check_utc']=utc()
            self.state['disk_safety_floor_mib']=200
            self.state['disk_monitor_interval_seconds']=900

    def checkpoint(self,phase=None,force=False):
        if phase:self.state['state']=phase
        self.state['last_update']=utc();self.state['observations']=len(self.rows)
        self.state['disk_free_gib']=round(shutil.disk_usage(self.root).free/GiB,3)
        self.state['workspace_gib']=round(folder_bytes(self.root)/GiB,3)
        atomic_json(self.root/'status.json',self.state)
        atomic_json(self.root/'checkpoint.json',{'started_epoch':self.started,'completed':len(self.rows),'updated_utc':utc()})
        if force or time.time()-self.last_snapshot>=300:
            ranking=rank_rows(self.rows)
            write_csv(self.root/'ranking.csv',('variant','metric','paired_n','median_ratio','geomean_ratio','mad_ratio'),ranking)
            write_hypotheses(self.root,ranking,self.state)
            snapshot(self.root);self.last_snapshot=time.time()

    def fail(self,kind,label,error):
        self.failures.append({'time':utc(),'step':kind,'candidate':label,'error':str(error)[-3500:]})
        write_csv(self.root/'failures.csv',('time','step','candidate','error'),self.failures)
        self.checkpoint(force=True)

    def preflight(self):
        spec=importlib.util.spec_from_file_location('native_rvv_bench',self.source/'scripts/rvv/perf/bench_native.py')
        if not spec or not spec.loader:raise RuntimeError('bench_native.py introuvable dans le snapshot')
        bn=importlib.util.module_from_spec(spec);spec.loader.exec_module(bn)
        bn.REPO_ROOT=self.source
        self.bn=bn
        from argparse import Namespace
        args=Namespace(compiler='gcc',allow_emulation=False,core=self.core)
        with contextlib.redirect_stdout(io.StringIO()): self.metadata=bn.preflight(args,self.root)
        if self.metadata['hardware_vlen_bits']!=256:
            raise SafetyStop('VLEN !=256 : campagne VLS256 non adaptée, arrêt')
        self.state['vlen_bits']=256
        self.state['hardware']=self.metadata['uname_a']
        source_manifest=self.source/'rvvlab-source-manifest.json'
        if source_manifest.is_file():
            try:
                meta=json.loads(source_manifest.read_text(encoding='utf-8'))
                self.state['source_git']=meta.get('git')
            except (ValueError,OSError):pass
        self.checkpoint('build',True)

    def build(self,tag,defines,impl,kind,upstream):
        # Recover from an interrupted partial build before enforcing quotas.
        leftover=self.root/'scratch_build'
        if leftover.is_dir():shutil.rmtree(leftover)
        self.check(building=True)
        binroot=self.root/'bin';binroot.mkdir(exist_ok=True)
        parse=binroot/f'parse-{tag}'
        if parse.is_file() and os.access(parse,os.X_OK):
            self.binaries[tag]=(str(parse),impl,defines);return
        source=self.source if kind=='vla' else upstream
        if kind=='vls' and not upstream:raise RuntimeError('Upstream indisponible')
        build=self.root/'scratch_build'
        # Transient build is deleted between candidates; retain only the linked executable.
        if build.exists():shutil.rmtree(build)
        cc,cxx=self.bn.compiler_pair('gcc')
        flags=self.bn.build_flags('gcc',kind,256 if kind=='vls' else None,defines)
        flags_s=' '.join(flags)
        cmd=['cmake','-S',str(source),'-B',str(build),*self.bn.cmake_generator(),
             '-DSIMDJSON_DEVELOPER_MODE=ON','-DBUILD_SHARED_LIBS=OFF','-DCMAKE_BUILD_TYPE=Release',
             f'-DCMAKE_C_FLAGS={flags_s}',f'-DCMAKE_CXX_FLAGS={flags_s}']
        env=os.environ.copy();env.update({'CC':cc,'CXX':cxx})
        try:
            run_bounded(cmd,env=env,workdir=self.root,deadline=self.deadline,stopfile=self.stopfile,building=True)
            run_bounded(['cmake','--build',str(build),'--target','parse','-j',str(self.jobs)],
                        env=env,workdir=self.root,deadline=self.deadline,stopfile=self.stopfile,building=True)
            built=build/'benchmark/dom/parse'
            if not built.is_file():raise RuntimeError('Binaire parse non produit')
            shutil.copy2(built,parse);parse.chmod(0o755)
            self.binaries[tag]=(str(parse),impl,defines)
            self.state['latest_built']=tag
        finally:
            if build.is_dir():shutil.rmtree(build)
            self.checkpoint('build',force=True)

    def prepare_upstream_safe(self):
        upstream=self.root/'upstream-v5.0.3'
        bn=self.bn
        if not (upstream/'.git').exists():
            run_bounded(['git','clone','--depth','1','--single-branch','--branch','v5.0.3',
                         '--filter=blob:none',bn.UPSTREAM_URL,str(upstream)],
                        workdir=self.root,deadline=self.deadline,stopfile=self.stopfile,building=True)
        run_bounded(['git','-C',str(upstream),'fetch','--depth','1','origin',bn.UPSTREAM_SHA],
                    workdir=self.root,deadline=self.deadline,stopfile=self.stopfile,building=True)
        run_bounded(['git','-C',str(upstream),'checkout','--detach',bn.UPSTREAM_SHA],
                    workdir=self.root,deadline=self.deadline,stopfile=self.stopfile,building=True)
        actual=subprocess.check_output(['git','-C',str(upstream),'rev-parse','HEAD'],text=True).strip()
        if actual!=bn.UPSTREAM_SHA:raise RuntimeError('SHA upstream non conforme')
        return upstream

    def setup(self):
        self.preflight()
        self.check(building=True)
        specs=candidate_defs(self.bn)
        # v5 baseline is mandatory: never measure a mixed-version campaign.
        upstream=self.prepare_upstream_safe()
        for tag,defines,impl,kind in specs:
            self.check(building=True)
            self.state['current_candidate']=tag
            self.checkpoint('build')
            try:self.build(tag,defines,impl,kind,upstream)
            except (SafetyStop,Stopped):raise
            except Exception as e:
                self.fail('build',tag,e)
                if tag in ('current','upstream_vls256'):raise
        if not all(x in self.binaries for x in ('current','upstream_vls256')):
            raise RuntimeError('RVV-VLA / upstream v5.0.3 controls missing')
        corpus=self.root/'corpus'
        # Two sizes; existing 4 MiB plus small 1 MiB. Corpus is reused between rounds.
        with contextlib.redirect_stdout(io.StringIO()):self.bn.generate_corpus(corpus,4)
        small=self.root/'small_corpus'
        with contextlib.redirect_stdout(io.StringIO()):self.bn.generate_corpus(small,1)
        self.corpi=[p for p in sorted(list(corpus.glob('*.json'))+list(small.glob('*.json')))
                    if p.name!='manifest.json' and p.is_file()
                    and (p.parent==corpus or p.name not in ('twitter.json','citm_catalog.json'))]
        # Fail fast: NEVER spend hours collecting unparsable samples.
        # Validate every linked binary against the actual tab-separated output.
        if not self.corpi:
            raise RuntimeError('Corpus absent : aucune exploration ne peut commencer')
        probe=min(self.corpi,key=lambda p:p.stat().st_size)
        for tag,(parse,impl,_defines) in self.binaries.items():
            stdout=run_bounded(['taskset','-c',str(self.core),parse,'-t','-n','20',
                                '-i','20','-a',impl,str(probe)],workdir=self.root,
                               deadline=self.deadline,stopfile=self.stopfile)
            try:
                values=self.bn.parse_tabbed_output(stdout)
                if any(values[key] is None or not math.isfinite(values[key]) or values[key]<=0
                       for key in ('dom_all','stage1','stage2')):
                    raise ValueError('Débits absents, nuls ou non finis')
            except Exception as exc:
                raise RuntimeError(f'Smoke benchmark impossible pour {tag}: {exc}; '
                                   f'stdout={stdout[-600:]!r}') from exc
        self.checkpoint('screen',force=True)

    def measure(self,phase,tag,path,iters,trial):
        parse,impl,defines=self.binaries[tag]
        cmd=['taskset','-c',str(self.core),parse,'-t','-n',str(iters),'-i',str(min(20,iters)),
             '-a',impl,str(path)]
        text=run_bounded(cmd,workdir=self.root,deadline=self.deadline,stopfile=self.stopfile)
        values=self.bn.parse_tabbed_output(text)
        self.rows.append({'timestamp':utc(),'phase':phase,'variant':tag,
                          'defines':json.dumps(defines,sort_keys=True,separators=(',',':')),
                          'corpus':path.name+'@'+str(path.stat().st_size),
                          'bytes':path.stat().st_size,'parse_iterations':iters,'trial':trial,
                          'dom_all_gbps':values['dom_all'],'stage1_gbps':values['stage1'],
                          'stage2_gbps':values['stage2'],'all_cpb':values['all_cpb'],
                          'stage1_cpb':values['stage1_cpb'],'stage2_cpb':values['stage2_cpb']})
        with (self.root/'map.csv').open('a',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow({k:self.rows[-1].get(k,'') for k in RESULT_FIELDS});f.flush();os.fsync(f.fileno())
        self.checkpoint(phase)

    def explore(self):
        tags=list(self.binaries)
        files=self.corpi
        existing={(r['phase'],r['variant'],r['corpus'],str(r['parse_iterations']),str(r['trial'])) for r in self.rows}
        # screen; then ranked, paired replications. Bounded to eight hours, can finish earlier.
        plans=[]
        for trial in (1,2):
            for path in files:
                order=['upstream_vls256',*tags]
                order=list(dict.fromkeys(order))
                random.Random(f'{trial}-{path.name}').shuffle(order)
                for tag in order:plans.append(('screen',tag,path,20,trial))
        for phase,tag,path,iters,trial in plans:
            self.check()
            key=(phase,tag,path.name+'@'+str(path.stat().st_size),str(iters),str(trial))
            if key in existing:continue
            try:self.measure(phase,tag,path,iters,trial)
            except (SafetyStop,Stopped):raise
            except Exception as e:self.fail('measure',tag,e)
        if not self.rows:
            raise RuntimeError('Aucune mesure valide après le balayage : résultats inutilisables')
        # Confirm top variants plus baseline across different iteration counts; repeat until time or bounded cycles.
        ranking=rank_rows(self.rows)
        ordered=[r for r in ranking if r['metric']=='stage1' and r['variant'] not in ('upstream_vls256','current')]
        ordered.sort(key=lambda r:r['geomean_ratio'],reverse=True)
        finalists=['upstream_vls256','current']+[r['variant'] for r in ordered[:3] if r['variant'] in tags]
        finalists=list(dict.fromkeys(finalists))
        # 7 rounds max; intentionally exploratory; if all finish earlier, stop normally.
        for trial in range(3,80):
            for path in files:
                order=finalists[:]
                random.Random(f'confirm-{trial}-{path.name}').shuffle(order)
                for tag in order:
                    self.check()
                    iters=40 if trial<6 else 90
                    phase='confirm'
                    key=(phase,tag,path.name+'@'+str(path.stat().st_size),str(iters),str(trial))
                    if key in existing:continue
                    try:self.measure(phase,tag,path,iters,trial)
                    except (SafetyStop,Stopped):raise
                    except Exception as e:self.fail('measure',tag,e)
        if not self.rows:
            raise RuntimeError('Aucune mesure valide : ne pas déclarer completed')
        self.state['state']='completed'

    def execute(self):
        lock=self.root.parent/'.night_runner_global.lock'
        with lock.open('w') as f:
            import fcntl
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Campagne déjà active')
            f.write(str(os.getpid()));f.flush()
            try:
                self.checkpoint('preflight',force=True)
                self.setup()
                # Keep Python orchestration off benchmark core 0 during measurements.
                if hasattr(os,'sched_setaffinity'):
                    allowed=os.sched_getaffinity(0)
                    background=next((c for c in sorted(allowed) if c!=self.core),None)
                    if background is not None:
                        os.sched_setaffinity(0,{background})
                        self.state['orchestration_cpu']=background
                self.explore()
            except Stopped as exc:
                self.state['state']='stopped';self.state['stop_reason']=str(exc)
            except SafetyStop as exc:
                self.state['state']='safety_stop';self.state['stop_reason']=str(exc)
            except Exception as exc:
                self.state['state']='failed';self.state['stop_reason']=str(exc)[-2500:]
                self.fail('fatal','runner',exc)
            finally:self.checkpoint(force=True)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True)
    p.add_argument('--workdir',required=True)
    p.add_argument('--hours',type=float,default=8)
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--core',type=int,default=0)
    p.add_argument('--resume',action='store_true')
    args=p.parse_args(argv)
    if not 0<args.hours<=MAX_HOURS:raise SystemExit('hours must be in (0,8]')
    if not pathlib.Path(args.source).resolve().is_dir():raise SystemExit('source not found')
    version = pathlib.Path(args.source).resolve()/'include/simdjson/simdjson_version.h'
    if not version.is_file() or not __import__('re').search(r'SIMDJSON_VERSION_MAJOR\s*=\s*5\b', version.read_text()):
        raise SystemExit('v5.0.3 source snapshot required')
    explorer=Explorer(args.source,args.workdir,args.hours,args.jobs,args.core,args.resume)
    explorer.execute()
    print(json.dumps({'state':explorer.state['state'],'observations':len(explorer.rows)},ensure_ascii=False))
    return 0 if explorer.state['state'] in ('completed','stopped') else 1

if __name__=='__main__':raise SystemExit(main())
