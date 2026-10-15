#!/usr/bin/env python3
"""Test97 / Cloud-V: 8-hour isolated A2 threshold study.

6 gate values; A2 reference before AND after candidates in every group.
No engine source modification, no packed variants, explicit opt-in launch.
A remote lock and process checks reject colliding RVV benchmarks.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math, os, platform, random, shlex, shutil, statistics, subprocess, sys, time, zipfile
from collections import defaultdict
from pathlib import Path

VERSION='97.0'
MIN_FREE=200*1024*1024
START_FREE=650*1024*1024
DURATION=28800
HOLDOUT_SECONDS=7200
VARIANTS={
 'A2_REF':4096,
 'A2_G5120':5120,
 'A2_G6144':6144,
 'A2_G7168':7168,
 'A2_G8192':8192,
 'A2_G10240':10240,
}
MEASURED_VARIANTS=tuple(VARIANTS)+('A2_REF_POST',)
FIELDS=['timestamp_utc','phase','group','scenario','family','layout','target_bytes','bytes','json_sha256','iterations','variant','dom_all_gbps','stage1_gbps','stage2_gbps','seconds']
ANCHORS=[('ascii',65536),('dense',65536),('escaped',65536),('utf8',65536),('unicode_escape',65536),('floats',65536),('many_keys',1048576),('nested',1048576),('long_strings',1048576),('boolnull',65536),('integers',65536),('utf8',8388608),('long_strings',8388608)]
BOUNDARIES=[2047,2048,2049,3072,3584,4095,4096,4097,4608,5119,5120,5121,5632,6143,6144,6145,6656,7167,7168,7169,7680,8191,8192,8193,9216,10239,10240,10241,12288,16384]
BOUND_FAMILIES=('ascii','dense','escaped','unicode_escape')

def utc():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def write_json(p,obj):
    p=Path(p); tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8');tmp.replace(p)
def run(cmd,timeout=300):
    return subprocess.run(list(map(str,cmd)),check=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=timeout)
def modules(src):
    p=Path(src)/'scripts/rvv/explore91'
    if not (p/'support90.py').is_file():raise RuntimeError('Missing design/harness in source')
    sys.path.insert(0,str(p))
    import support90, harness, design
    return support90,harness,design

def verify_source(src):
    required=('src/simdjson.cpp','src/rvv/engines/engine_plan.h','include/simdjson.h','scripts/rvv/explore91/support90.py')
    for rel in required:
        if not (Path(src)/rel).is_file():raise RuntimeError('Engine source missing '+rel)
    if '5.0.3' not in (Path(src)/'include/simdjson/simdjson_version.h').read_text():raise RuntimeError('Expected simdjson 5.0.3')

def cases(design,src=None):
    specs=design.corpus_specs(8)
    anchors=[]
    for kind,size in ANCHORS:
        sp=next((x for x in specs if x['kinds']==[kind] and x['target']==size and x['layout']=='interleaved'),None)
        if sp is None:raise RuntimeError('Missing anchor '+kind+'/'+str(size))
        anchors.append(dict(sp,scenario='anchor',family=kind))
    region=next((x for x in specs if x['layout']=='regions16384' and x['target']==1048576 and 'utf8' in x['kinds'] and len(x['kinds'])>=3),None)
    regions=[dict(region,scenario='region_mix',family='+'.join(region['kinds']))] if region else []
    if not regions:raise RuntimeError('No mixed-region template in engine')
    boundaries=[{'id':f'B-{fam}-{size}','scenario':'boundary','family':fam,'target':size,'layout':'exact'} for fam in BOUND_FAMILIES for size in BOUNDARIES]
    fixtures=[]
    # Different real JSON files in train vs holdout. No shared fixture bytes.
    for name,phase in (('recipe_book.json','train'),('example_config.json','train'),('twitter.json','holdout'),('citm_catalog.json','holdout')):
        p=Path(src)/'jsonexamples'/name if src is not None else None
        if p is not None and p.is_file():
            b=p.read_bytes()
            try:json.loads(b)
            except ValueError:raise RuntimeError('Invalid real fixture '+name)
            fixtures.append(dict(id='R-'+name,scenario='real_json',family=name,layout='real_fixture',target=len(b),fixture=str(p),phase=phase))
    return dict(anchors=anchors,regions=regions,boundaries=boundaries,fixtures=fixtures)

def pick_case(bank,n,phase):
    # 50% exact-size boundaries, 25% mixed-size anchors, 12.5% regions,
    # 12.5% real JSON when available. A fresh holdout uses disjoint seeds.
    slot=n%8;cycle=n//8
    if slot<4:return bank['boundaries'][(4*cycle+slot)%len(bank['boundaries'])]
    if slot<6:return bank['anchors'][(2*cycle+slot-4)%len(bank['anchors'])]
    if slot==6:return bank['regions'][cycle%len(bank['regions'])]
    fixtures=[x for x in bank['fixtures'] if x['phase']==phase]
    if fixtures:return fixtures[cycle%len(fixtures)]
    return bank['anchors'][(2*cycle+3)%len(bank['anchors'])]

def exact_json(family,target,seed):
    """Exact byte length, valid JSON and family-specific repeated atoms + bounded pad string.
    Pad introduces an ASCII field; the effect is documented in the manifest.
    """
    import json as _json
    from random import Random
    rng=Random(seed)
    atoms={
      'ascii':lambda i:{'name':'alpha_beta_%s'%i,'ok':True},
      'dense':lambda i:[i,[0,1],{},[],True,False,None,{'x':[]}],
      'escaped':lambda i:{'s':'path\\x\\y\nquoted"\t'*2,'id':i},
      'unicode_escape':lambda i:{'s':'😺漢字é'*3,'id':i},
    }
    if family not in atoms:raise ValueError(family)
    # Inner field's bytes are pure UTF-8/escape JSON. Add atoms until one more
    # would leave too little space for the fixed pad object overhead.
    prefix=b'{"items":[';suffix=b'],"pad":"';ending=b'"}'
    items=[];used=len(prefix)+len(suffix)+len(ending)
    for i in range(5000):
        blob=_json.dumps(atoms[family](rng.randrange(10000)),ensure_ascii=family=='unicode_escape',separators=(',',':')).encode('utf8')
        add=len(blob)+(1 if items else 0)
        if used+add>target-48:break
        items.append(blob);used+=add
    assert items and used<=target, (family,target)
    payload=prefix+b','.join(items)+suffix+b'x'*(target-used)+ending
    assert len(payload)==target and _json.loads(payload), (len(payload),target)
    return payload

def build(args):
    if platform.machine()!='riscv64':raise RuntimeError('Native RISC-V Cloud-V only (build requires riscv64)')
    src=Path(args.source).resolve();verify_source(src)
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(out).free<START_FREE:raise RuntimeError('At least 650 MiB free required before build; 200 MiB reserved')
    other=competitor_processes()
    if other:raise RuntimeError('Concurrent native RVV benchmark prevents compilation: '+str(other[:4]))
    if (out/'builds97.json').exists():raise RuntimeError('Existing build: use run-only, not all/build-only')
    support,harness,_=modules(src)
    harnessfile=out/'test97_benchmark.cpp';harnessfile.write_text(harness.source(support.BENCH_CPP),encoding='utf8')
    header={"original_sha256":sha(src/"src/rvv/engines/engine_plan.h"),"overlay_sha256":None,"path":None}
    builds={}
    baseflags=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-mabi=lp64d','-march=rv64gcv','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1','-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0','-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_EXPLORATION91=0']
    compiler_flags=shlex.split(args.cxx_flags)
    for name,gate in VARIANTS.items():
        if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200 MiB)')
        flags=baseflags+['-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES='+str(gate),'-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0','-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0','-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE=0','-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE=0','-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT=0']
        inc=['-I'+str(src/'include'),'-I'+str(src/'src')]
        obj=out/(name+'.o');exe=out/('test97_'+name)
        rec={'result':'not_built','flags':flags,'source_header_sha256':header['original_sha256'],'uses_overlay':False,'started_utc':utc()}
        for step,cmd in [('compile',[args.cxx,*compiler_flags,*flags,*inc,'-c',src/'src/simdjson.cpp','-o',obj]),('link',[args.cxx,*compiler_flags,*flags,*inc,harnessfile,obj,'-o',exe])]:
            with (out/f'build_{name}_{step}.log').open('w',encoding='utf8') as log:
                try:p=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=480)
                except subprocess.TimeoutExpired:rec.update(result='FAIL',step=step,error='Compile timeout');break
            if p.returncode:rec.update(result='FAIL',step=step,error=(out/f'build_{name}_{step}.log').read_text(errors='replace')[-2000:]);break
        else:
            exe.chmod(0o755);rec.update(result='PASS',sha256=sha(exe),path=exe.name)
            obj.unlink(missing_ok=True)
        builds[name]=rec
        write_json(out/'builds97.json',{'schema':1,'version':VERSION,'builds':builds,'harness_sha256':sha(harnessfile),'header':header,'source':str(src),'created_utc':utc()})
        print('BUILD',name,rec['result'],rec.get('error','')[-100:],flush=True)
        if name=='A2_REF' and rec['result']!='PASS':raise RuntimeError('Mandatory A2 reference failed; stop')
    return out

def machine_info():
    m={'machine':platform.node(),'arch':platform.machine(),'time_utc':utc(),'python':sys.version,'uname':platform.uname()._asdict()}
    for name,cmd in [('gcc',['g++','--version']),('lscpu',['lscpu'])]:
        try:m[name]=run(cmd,15).stdout[:10000]
        except Exception as e:m[name]=str(e)
    try:m['affinity']=sorted(os.sched_getaffinity(0))
    except Exception:m['affinity']=[]
    for filename in ('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor','/proc/cpuinfo'):
        try:m[filename]=Path(filename).read_text(errors='replace')[:10000]
        except Exception:pass
    return m

def summary(rows,variants):
    groups=defaultdict(dict)
    for r in rows:groups[r['group']][r['variant']]=r
    out={}
    for phase in ('train','holdout'):
        out[phase]={}
        for variant in variants:
            if variant=='A2_REF':continue
            for scope in ('all','boundary','anchor','real_json','region_mix','4096-8191','other_sizes'):
                paired=[]
                for g in groups.values():
                    if not all(k in g for k in ('A2_REF','A2_REF_POST',variant)):continue
                    a,b,c=g['A2_REF'],g[variant],g['A2_REF_POST']
                    if b['phase']!=phase:continue
                    if scope=='4096-8191' and not 4096<=int(b['bytes'])<8192:continue
                    if scope=='other_sizes' and 4096<=int(b['bytes'])<8192:continue
                    if scope not in ('all','4096-8191','other_sizes') and b['scenario']!=scope:continue
                    if any(a[k]!=b[k] or c[k]!=b[k] for k in ('json_sha256','bytes','iterations','phase','group')):raise RuntimeError('Corrupted pair '+str(b['group']))
                    pairs=[]
                    for metric in ('dom_all_gbps','stage1_gbps','stage2_gbps'):
                        aa,bb,cc=[float(r[metric]) for r in (a,b,c)]
                        if not all(math.isfinite(v) and v>0 for v in (aa,bb,cc)):raise RuntimeError('Invalid throughput')
                        pairs.append(math.log(bb)-0.5*(math.log(aa)+math.log(cc)))
                    paired.append((b,pairs))
                if not paired:continue
                arr=list(zip(*(p for _,p in paired)))
                out[phase][variant+'|'+scope]={'pairs':len(paired),'DOM_vs_A2':round(math.exp(statistics.mean(arr[0])),6),'stage1_vs_A2':round(math.exp(statistics.mean(arr[1])),6),'stage2_vs_A2':round(math.exp(statistics.mean(arr[2])),6)}
    out['complete_groups']=sum(1 for g in groups.values() if set(MEASURED_VARIANTS)<=set(g))
    out['total_groups']=len(groups)
    out['incomplete_groups']=out['total_groups']-out['complete_groups']
    return out

def report(out,rows,variants,status):
    sm=summary(rows,variants)
    write_json(out/'summary97.json',dict(schema=1,version=VERSION,summary=sm,status=status))
    lines=['# Test 97 — Cloud-V 8 h : seuil de dispatch A2 isolé','','**EXPÉRIMENTAL — aucune promotion automatique.**',
       'État : `'+str(status.get('state'))+'`, phase : `'+str(status.get('phase'))+'`, lignes : '+str(len(rows)),
       'Groupes complets : '+str(sm['complete_groups'])+' ; incomplets : '+str(sm['incomplete_groups']),
       'Début : '+str(status.get('start_utc'))+' ; limite : '+str(status.get('deadline_utc')),'',
       'Comparaison géométrique appariée à la moyenne géométrique des mesures A2 avant/après.','',
       '| Phase | Variante | Scénario | Paires | DOM/A2 | Stage1/A2 | Stage2/A2 |','|---|---|---|---:|---:|---:|---:|']
    for phase in ('train','holdout'):
        for name in variants:
            if name=='A2_REF':continue
            for scope in ('all','4096-8191','other_sizes','boundary','anchor','real_json','region_mix'):
                obj=sm.get(phase,{}).get(name+'|'+scope)
                if obj:lines.append(f'| {phase} | `{name}` | {scope} | {obj["pairs"]} | {obj["DOM_vs_A2"]:.4f}× | {obj["stage1_vs_A2"]:.4f}× | {obj["stage2_vs_A2"]:.4f}× |')
    lines+=['','## Interprétation et limites','',
      '- A2 avant et après chaque séquence de variantes, afin de détecter la dérive thermique/temporelle ; candidats mélangés à chaque groupe.',
      '- Six binaires natifs GCC -O3, packed désactivé, seul le seuil change : 4096 / 5120 / 6144 / 7168 / 8192 / 10240.',
      '- Nouveaux seeds pour les documents synthétiques ; corpus réel réparti entre exploration et holdout si disponible.',
      '- Les JSON exact-size comportent un champ ASCII de remplissage ; ne pas généraliser le résultat synthétique à la production.',
      '- Groupes incomplets exclus de toute comparaison. Ratio >1 : candidat plus rapide.',
      '- Ne conclure à un gain stable que si holdout et jeux réels concordent, sans contention détectée.',
      '- Aucune optimisation intégrée au moteur automatiquement.','']
    (out/'REPORT_97.md').write_text('\n'.join(lines),encoding='utf8')
    return sm

def packet(out):
    files=['builds97.json','machine97.json','status97.json','results97.csv','summary97.json','REPORT_97.md','manifest97.json']
    temp=out/'test97_results.zip.partial';dest=out/'test97_results.zip'
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for filename in files:
            if (out/filename).exists():z.write(out/filename,arcname=filename)
    if zipfile.ZipFile(temp).testzip() is not None:raise RuntimeError('ZIP validation failure')
    temp.replace(dest)
    (out/'test97_results.sha256').write_text(sha(dest)+'  '+dest.name+'\n',encoding='ascii')

def read_rows(out):
    if not (out/'results97.csv').exists():return []
    with (out/'results97.csv').open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))

def validation(out):
    good=['{}','[]','true','false','null','0','{"a":1}','[1,2,3]','{"x":"é😀"}','"quoted\\\""','{"nested":{"x":[null,false,true]}}','"\\uD83D\\uDE3A"']
    bad=['{','[','[1,]','{"x":}','{"x":1,}','[NaN]','{"x":01}','{"x":+1}','[true false]','"unterminated','{"x":1}junk','{"a":1 "b":2}']
    (out/'valid97.jsonl').write_text('\n'.join(good)+'\n',encoding='utf8')
    (out/'invalid97.jsonl').write_text('\n'.join(bad)+'\n',encoding='utf8')

def competitor_processes():
    """Find concurrently active native experiment processes, ignoring zombies.
    /proc is used instead of pgrep to avoid matching command shells themselves.
    """
    found=[]
    me=os.getpid()
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name)==me:continue
        try:
            cmd=(p/'cmdline').read_bytes().split(b'\0')
            if not cmd or not cmd[0]:continue
            stat=(p/'stat').read_text()
            if stat.rsplit(') ',1)[1][:1]=='Z':continue
            args=[x.decode('utf8','replace') for x in cmd if x]
            executable=Path(args[0]).name.lower()
            suspect=False
            if executable.startswith(('test94_','test95_','test96_','test97_')):suspect=True
            if executable.startswith(('python','pypy')):
                suspect=any(Path(a).name in ('test94_native.py','test95_native.py','test96_native.py','test97_native.py') for a in args[1:])
            if suspect:found.append({'pid':int(p.name),'cmd':args[:4]})
        except (PermissionError,OSError,ValueError,IndexError):continue
    return found

def execute(args,start_monotonic):
    if platform.machine()!='riscv64':raise RuntimeError('REFUSED: Cloud-V native riscv64 only')
    src=Path(args.source).resolve();out=Path(args.output).resolve();verify_source(src)
    builds=json.loads((out/'builds97.json').read_text())
    avail=[k for k in VARIANTS if builds['builds'].get(k,{}).get('result')=='PASS']
    if 'A2_REF' not in avail:raise RuntimeError('Reference build missing')
    for name in avail:
        exe=out/('test97_'+name)
        if not exe.is_file() or sha(exe)!=builds['builds'][name]['sha256']:raise RuntimeError('Binary SHA mismatch '+name)
    if set(avail)!=set(VARIANTS):raise RuntimeError('Test97 requires all six variants; build issues: '+','.join(set(VARIANTS)-set(avail)))
    if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200MiB)')
    import fcntl
    # Shared lock for future native Lab campaigns. Prevents concurrent Test97
    # launches; /proc checks below also detect older Test95 launchers.
    with (out.parent/'.rvvlab_cpu0_experiment.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another Test97 process owns this run directory')
        statuspath=out/'status97.json'
        if args.resume:
            if not statuspath.exists():raise RuntimeError('Resume requested without prior status')
            status=json.loads(statuspath.read_text())
            if status.get('state')=='completed':raise RuntimeError('Already completed')
            deadline=dt.datetime.fromisoformat(status['deadline_utc']).timestamp()
            if time.time()>=deadline:raise RuntimeError('8h deadline expired; no extension allowed')
            if status.get('source_header_sha256')!=sha(src/'src/rvv/engines/engine_plan.h'):raise RuntimeError('Source changed: resume blocked')
            rows=read_rows(out)
            next_group=max([int(r['group'][1:]) for r in rows]+[-1])+1
            tr_count=sum(1 for r in rows if r['phase']=='train' and r['variant']=='A2_REF')
            ho_count=sum(1 for r in rows if r['phase']=='holdout' and r['variant']=='A2_REF')
        else:
            if statuspath.exists() or (out/'results97.csv').exists():raise RuntimeError('Existing run directory; use --resume or new directory')
            deadline=time.time()+max(0,args.seconds-(time.monotonic()-start_monotonic))
            now=dt.datetime.now(dt.timezone.utc)
            status=dict(schema=1,version=VERSION,state='running',phase='validation',start_utc=now.isoformat(),deadline_utc=dt.datetime.fromtimestamp(deadline,dt.timezone.utc).isoformat(),source_header_sha256=sha(src/'src/rvv/engines/engine_plan.h'),seconds=args.seconds,rows=0,groups=0)
            rows=[];next_group=0;tr_count=0;ho_count=0
        status.update(state='running',updated_utc=utc(),variants=avail)
        write_json(statuspath,status)
        machine=machine_info();write_json(out/'machine97.json',machine)
        core=args.core if args.core is not None else next(iter(machine.get('affinity') or []),None)
        if core is not None and machine.get('affinity') and core not in machine['affinity']:raise RuntimeError('Requested CPU unavailable')
        if core is not None and not shutil.which('taskset'):raise RuntimeError('taskset is required for pinned CPU test')
        prefix=['taskset','-c',str(core)] if core is not None else []
        status['cpu']=core
        def call(name,mode,*params,timeout=90):
            remaining=deadline-time.time()-3
            if remaining<=0:raise TimeoutError('8h deadline')
            cmd=prefix+[str(out/('test97_'+name)),'rvv',mode]+list(map(str,params))
            return run(cmd,timeout=max(.5,min(timeout,remaining))).stdout
        validation(out)
        support,_,design=modules(src)
        bank=cases(design,src)
        rng=random.Random(2026101597)
        doc=out/'active97.json'
        def update_snapshot(force=False):
            status.update(rows=len(rows),groups=next_group,updated_utc=utc())
            write_json(statuspath,status)
            if force or time.time()-update_snapshot.last_packet>600:
                # Full report over all rows is expensive; do it at 10-min snapshots.
                report(out,rows,avail,status)
                if shutil.disk_usage(out).free>=MIN_FREE:
                    packet(out);update_snapshot.last_packet=time.time()
                else:print('WARNING: <200 MiB; final ZIP snapshot skipped, raw CSV/status preserved',flush=True)
        update_snapshot.last_packet=0
        mode='a' if args.resume else 'w'
        try:
            for name in avail:
                marker=call(name,'validate',out/'valid97.jsonl',out/'invalid97.jsonl',timeout=90)
                if 'RVV_VALIDATION_OK backend=rvv' not in marker:raise RuntimeError('Validation failed '+name)
            status['validated']=True
            write_json(statuspath,status)
            if not args.resume:write_json(out/'manifest97.json',dict(schema=1,variants=VARIANTS,templates=bank,holdout_seconds=HOLDOUT_SECONDS,version=VERSION,source_header_sha256=status['source_header_sha256'],harness_sha256=builds['harness_sha256'],notes='A2 measurements before and after each group. Balanced cases. New seeds; train/holdout real fixtures disjoint. Exact JSON contains ASCII pad.'))
            with (out/'results97.csv').open(mode,newline='',encoding='utf8') as csvfile:
                writer=csv.DictWriter(csvfile,fieldnames=FIELDS)
                if mode=='w' or (out/'results97.csv').stat().st_size==0:writer.writeheader();csvfile.flush()
                while time.time()<deadline-8:
                    if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200 MiB)')
                    holdout=time.time()>=deadline-HOLDOUT_SECONDS
                    phase='holdout' if holdout else 'train'
                    n=ho_count if holdout else tr_count
                    # Rotate through all templates with distinct seeds. Mirror the
                    # case distribution between training and untouched holdout.
                    if next_group%10==0:
                        other=competitor_processes()
                        if other:raise RuntimeError('Concurrent RVV benchmark detected mid-run: '+str(other[:4]))
                    template=pick_case(bank,n,phase)
                    seed=202610159700000+10007*n+(2147483647 if holdout else 0)
                    family=template['family']
                    status['phase']=phase
                    try:
                        if template['scenario']=='real_json':
                            data=Path(template['fixture']).read_bytes()
                            doc.write_bytes(data)
                            info=dict(bytes=len(data),sha256=sha(doc))
                        elif template['scenario']=='boundary':
                            data=exact_json(family,template['target'],seed)
                            doc.write_bytes(data)
                            info=dict(bytes=len(data),sha256=sha(doc))
                        else:
                            sp=dict(template,seed=seed)
                            info=design.generate(sp,doc,lambda:None)
                        # Each binary must agree with scalar fallback for *this* JSON
                        # before any performance measurement. Fail closed.
                        for name in avail:
                            marker=call(name,'check',doc,timeout=90)
                            if 'DOM_AGREES' not in marker:raise RuntimeError('Correctness failure '+name+' '+str(template['id']))
                        size=info['bytes'];iters=max(1,min(1000, max(4194304//size, 1)))
                        group='G%07d'%next_group
                        order=[k for k in avail if k!='A2_REF'];rng.seed(seed);rng.shuffle(order)
                        order=['A2_REF']+order+['A2_REF_POST']
                        # Two A2 measurements bracket all candidates; logs used as
                        # geometric baseline, reducing smooth clock/temperature drift.
                        for position,name in enumerate(order):
                            binary='A2_REF' if name=='A2_REF_POST' else name
                            result=call(binary,'split',doc,iters,timeout=120)
                            dom,s1,s2,elapsed,_,_,reps,actual=support.parse_split_output(result)
                            if actual!=size or reps!=iters:raise RuntimeError('Benchmark echo mismatch')
                            row=dict(timestamp_utc=utc(),phase=phase,group=group,scenario=template['scenario'],family=family,layout=template['layout'],target_bytes=template['target'],bytes=size,json_sha256=info['sha256'],iterations=iters,variant=name,dom_all_gbps=dom,stage1_gbps=s1,stage2_gbps=s2,seconds=elapsed)
                            writer.writerow(row);csvfile.flush();rows.append(row)
                        next_group+=1
                        if holdout:ho_count+=1
                        else:tr_count+=1
                        if next_group%10==0:update_snapshot()
                    finally:doc.unlink(missing_ok=True)
        except (TimeoutError,subprocess.TimeoutExpired) as e:
            if time.time()<deadline-15:status.update(state='failed',reason='Unexpected early timeout: '+str(e));raise
            status.update(state='completed',reason='Eight-hour budget reached')
        except KeyboardInterrupt:
            status.update(state='stopped',reason='Operator interrupted');raise
        except Exception as e:
            status.update(state='safety_stop' if 'Disk safety stop' in str(e) else 'failed',reason=str(e));raise
        finally:
            if status['state']=='running':status['state']='completed' if time.time()>=deadline-20 else 'stopped'
            if status['state']=='completed' and ho_count < 1:status.update(state='incomplete',reason='No holdout groups were completed')
            status['phase']='finish'
            update_snapshot(force=True)
        print('TEST97_DONE',status['state'],status['rows'],flush=True)
    return 0

def main():
    p=argparse.ArgumentParser(description='Test97 8h Cloud-V native benchmark; no production changes')
    p.add_argument('action',choices=['plan','build-only','run-only','all'])
    p.add_argument('--source',default='engine');p.add_argument('--output',default='test97_output')
    p.add_argument('--seconds',type=int,default=DURATION)
    p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--core',type=int);p.add_argument('--resume',action='store_true')
    args=p.parse_args();start=time.monotonic()
    if args.action=='plan':
        src=Path(args.source).resolve();verify_source(src)
        _,_,design=modules(src)
        bank=cases(design,src)
        print(json.dumps(dict(duration_seconds=args.seconds,variant_count=len(VARIANTS),variants=VARIANTS,case_count=sum(len(v) for v in bank.values()),case_bank={k:len(v) for k,v in bank.items()},boundaries=BOUNDARIES,holdout_seconds=HOLDOUT_SECONDS),indent=2));return 0
    if not 60<=args.seconds<=DURATION: p.error('seconds must be 60..28800 (8h max)')
    if args.resume and args.action!='run-only':p.error('--resume requires run-only')
    if args.action in ('build-only','all'):build(args)
    if args.action in ('run-only','all'):return execute(args,start)
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('TEST97_ERROR',str(e),file=sys.stderr)
        raise
