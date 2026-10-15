#!/usr/bin/env python3
"""Test96 / EPCC: eight-hour, native RVV, paired A2 packed-path & dispatch-gate ablation.

Source is never modified. For three candidates only, an include-directory overlay
turns on the selected packed algorithms in configure(). A2 reference is unmodified.
Runs require explicit invocation, no automatic promotion/deployment, no sudo.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math, os, platform, random, shlex, shutil, statistics, subprocess, sys, time, zipfile
from collections import defaultdict
from pathlib import Path

VERSION='96.0'
MIN_FREE=200*1024*1024
START_FREE=650*1024*1024
DURATION=28800
HOLDOUT_SECONDS=7200
VARIANTS={
 'A2_REF':  dict(c=0,w=0,e=0,q=0,s=0,gate=4096,active=False),
 'A2_CTL':  dict(c=1,w=0,e=1,q=1,s=1,gate=4096,active=True),
 'A2_IDX':  dict(c=0,w=1,e=0,q=0,s=0,gate=4096,active=True),
 'A2_BOTH': dict(c=1,w=1,e=1,q=1,s=1,gate=4096,active=True),
 'A2_ESC':  dict(c=0,w=0,e=1,q=0,s=0,gate=4096,active=True),
 'A2_G2048':dict(c=0,w=0,e=0,q=0,s=0,gate=2048,active=False),
 'A2_G8192':dict(c=0,w=0,e=0,q=0,s=0,gate=8192,active=False),
}
FIELDS=['timestamp_utc','phase','group','scenario','family','layout','target_bytes','bytes','json_sha256','iterations','variant','dom_all_gbps','stage1_gbps','stage2_gbps','seconds']
ANCHORS=[('ascii',65536),('dense',65536),('escaped',65536),('utf8',65536),('unicode_escape',65536),('floats',65536),('many_keys',1048576),('nested',1048576),('long_strings',1048576),('boolnull',65536),('integers',65536),('utf8',8388608),('long_strings',8388608)]
BOUNDARIES=[2047,2048,2049,3584,4095,4096,4097,4608,8191,8192,8193]
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

def patched_header(src,out):
    original=Path(src)/'src/rvv/engines/engine_plan.h'
    src_text=original.read_text(encoding='utf8')
    needle='  return p;\n}\n\ninline plan choose('
    if src_text.count(needle)!=1:raise RuntimeError('Engine header diverged: test96 overlay cannot be applied safely')
    patch='''#if SIMDJSON_RVV_TEST96_ACTIVE_PACKED
  // Test96 ONLY: force candidate packed subpaths on ordinary A2-selected plans.
  // Original engine chooses false here. Reference does not load this overlay.
  p.packed_writer = SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER != 0;
  p.packed_escape = SIMDJSON_RVV_ENABLE_PACKED_ESCAPE != 0;
  p.packed_quote = SIMDJSON_RVV_ENABLE_PACKED_QUOTE != 0;
  p.packed_shift = SIMDJSON_RVV_ENABLE_PACKED_SHIFT != 0;
#endif
  return p;
}

inline plan choose('''
    target=Path(out)/'overlay/rvv/engines/engine_plan.h'
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(src_text.replace(needle,patch),encoding='utf8')
    return dict(original_sha256=sha(original),overlay_sha256=sha(target),path=str(target))

def cases(design):
    specs=design.corpus_specs(8)
    anchors=[]
    for kind,size in ANCHORS:
        s=next((x for x in specs if x['kinds']==[kind] and x['target']==size and x['layout']=='interleaved'),None)
        if s is None:raise RuntimeError('Missing anchor '+kind+'/'+str(size))
        anchors.append(dict(s,scenario='anchor',family=kind))
    region=next((x for x in specs if x['layout']=='regions16384' and x['target']==1048576 and 'utf8' in x['kinds'] and len(x['kinds'])>=3),None)
    if region:anchors.append(dict(region,scenario='region_mix',family='+'.join(region['kinds'])))
    boundaries=[{'id':f'B-{fam}-{size}','scenario':'boundary','family':fam,'target':size,'layout':'exact'} for fam in BOUND_FAMILIES for size in BOUNDARIES]
    # Approximately half the cases are around boundaries, all case types repeated evenly.
    return anchors+boundaries

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
    if platform.machine()!='x86_64':raise RuntimeError('EPCC cross-build must run on x86_64 login node, not on RISC-V compute node')
    src=Path(args.source).resolve();verify_source(src)
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(out).free<START_FREE:raise RuntimeError('At least 650 MiB free required before build; 200 MiB reserved')
    if (out/'builds96.json').exists():raise RuntimeError('Existing build: use run-only, not all/build-only')
    support,harness,_=modules(src)
    harnessfile=out/'test96_benchmark.cpp';harnessfile.write_text(harness.source(support.BENCH_CPP),encoding='utf8')
    header=patched_header(src,out)
    builds={}
    baseflags=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-mabi=lp64d','-march=rv64gcv','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1','-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0','-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_EXPLORATION91=0']
    compiler_flags=shlex.split(args.cxx_flags)
    if not any(x.startswith('--target=riscv64') for x in compiler_flags):raise RuntimeError('Cross-build requires explicit --target=riscv64-unknown-linux-gnu')
    for name,sp in VARIANTS.items():
        if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200 MiB)')
        flags=baseflags+['-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES='+str(sp['gate']),'-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL='+str(sp['c']),'-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER='+str(sp['w']),'-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE='+str(sp['e']),'-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE='+str(sp['q']),'-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT='+str(sp['s'])]
        if sp['active']:flags+=['-DSIMDJSON_RVV_TEST96_ACTIVE_PACKED=1']
        inc=(['-I'+str(out/'overlay')] if sp['active'] else [])+['-I'+str(src/'include'),'-I'+str(src/'src')]
        obj=out/(name+'.o');exe=out/('test96_'+name)
        rec={'result':'not_built','flags':flags,'source_header_sha256':header['original_sha256'],'uses_overlay':sp['active'],'started_utc':utc()}
        for step,cmd in [('compile',[args.cxx,*compiler_flags,*flags,*inc,'-MD','-MF',str(out/(name+'.d')),'-c',src/'src/simdjson.cpp','-o',obj]),('link',[args.cxx,*compiler_flags,*flags,*inc,harnessfile,obj,'-o',exe])]:
            with (out/f'build_{name}_{step}.log').open('w',encoding='utf8') as log:
                try:p=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,timeout=480)
                except subprocess.TimeoutExpired:rec.update(result='FAIL',step=step,error='Compile timeout');break
            if p.returncode:rec.update(result='FAIL',step=step,error=(out/f'build_{name}_{step}.log').read_text(errors='replace')[-2000:]);break
        else:
            dep=out/(name+'.d')
            depdata=dep.read_text(errors='replace') if dep.is_file() else ''
            overlay=str(out/'overlay/rvv/engines/engine_plan.h')
            if (overlay in depdata)!=sp['active']:
                rec.update(result='FAIL',step='dependency_check',error='Wrong engine_plan.h include path; overlay activation differs from expected')
            else:
                headerbytes=exe.read_bytes()[:20]
                if not (len(headerbytes)>=20 and headerbytes[:4]==b'\x7fELF' and headerbytes[4]==2 and int.from_bytes(headerbytes[18:20],'little')==243):
                    rec.update(result='FAIL',step='elf_check',error='Compiler did not emit RISC-V ELF64 (e_machine=243)')
                else:
                    exe.chmod(0o755);rec.update(result='PASS',sha256=sha(exe),path=exe.name)
            obj.unlink(missing_ok=True)
        builds[name]=rec
        write_json(out/'builds96.json',{'schema':1,'version':VERSION,'builds':builds,'harness_sha256':sha(harnessfile),'header':header,'source':str(src),'created_utc':utc()})
        print('BUILD',name,rec['result'],rec.get('error','')[-100:],flush=True)
        if rec['result']!='PASS':raise RuntimeError('Variant '+name+' failed; stop, inspect build_'+name+'_*.log and builds96.json')
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
            for scope in ('all','anchor','boundary','region_mix'):
                paired=[(g['A2_REF'],g[variant]) for g in groups.values() if 'A2_REF' in g and variant in g and g[variant]['phase']==phase and (scope=='all' or g[variant]['scenario']==scope)]
                if not paired:continue
                arr=[math.log(float(b['dom_all_gbps'])/float(a['dom_all_gbps'])) for a,b in paired if float(a['dom_all_gbps'])>0 and float(b['dom_all_gbps'])>0]
                if not arr:continue
                out[phase][variant+'|'+scope]={'pairs':len(arr),'DOM_vs_A2':round(math.exp(statistics.mean(arr)),6),'mean_log':round(statistics.mean(arr),8)}
            for family in ('utf8','nested','boolnull','ascii','dense','escaped','unicode_escape'):
                paired=[(g['A2_REF'],g[variant]) for g in groups.values() if 'A2_REF' in g and variant in g and g[variant]['phase']==phase and g[variant]['family']==family]
                if paired:
                    arr=[math.log(float(b['dom_all_gbps'])/float(a['dom_all_gbps'])) for a,b in paired]
                    out[phase][variant+'|family:'+family]={'pairs':len(arr),'DOM_vs_A2':round(math.exp(statistics.mean(arr)),6)}
    out['complete_groups']=sum(1 for g in groups.values() if set(variants)<=set(g))
    out['total_groups']=len(groups)
    return out

def report(out,rows,variants,status):
    sm=summary(rows,variants)
    write_json(out/'summary96.json',dict(schema=1,version=VERSION,summary=sm,status=status))
    lines=['# Test 96 — 8h EPCC · ablation réelle du packed et du seuil A2','','**Résultats expérimentaux, pas d’optimisation validée automatiquement.**',
      'État : `'+str(status.get('state'))+'`, phase : `'+str(status.get('phase'))+'`, lignes : '+str(len(rows)),
      'Début : '+str(status.get('start_utc'))+' ; limite : '+str(status.get('deadline_utc')),'',
      '## Ratios DOM appariés (géométriques) vs A2_REF','', '| Phase | Variante | Scénario | Paires | DOM / A2 |','|---|---|---|---:|---:|']
    for phase in ('train','holdout'):
        for name in variants:
            if name=='A2_REF':continue
            for scope in ('all','anchor','boundary','region_mix'):
                obj=sm.get(phase,{}).get(name+'|'+scope)
                if obj:lines.append(f'| {phase} | `{name}` | {scope} | {obj["pairs"]} | {obj["DOM_vs_A2"]:.4f}× |')
    lines+=['','## Notes de méthode','',
      '- Le témoin A2_REF compile le moteur non modifié (source snapshot).',
      '- Les variantes CTL / IDX / BOTH / ESC utilisent UNIQUEMENT un header overlay non persistant pour activer effectivement leurs sous-chemins packed avec A2.',
      '- La série G2048 / G8192 modifie uniquement le seuil A2_MIN_BYTES sans overlay.',
      '- Les cas boundary ont des longueurs exactes en octets et incluent un champ pad ASCII; résultats propres à cette construction.',
      '- Validation RVV vs fallback exigée avant chaque mesure de chaque document; aucun faux débit Stage1/Stage2 additif.',
      '- Seuls les groupes appariés complets entrent dans une comparaison variante/A2. Le holdout utilise des graines distinctes.',
      '- Aucun candidat n’est promu automatiquement. Revue par famille, corrections, reproductibilité requises.','']
    (out/'REPORT_96.md').write_text('\n'.join(lines),encoding='utf8')
    return sm

def packet(out):
    files=['builds96.json','machine96.json','status96.json','results96.csv','summary96.json','REPORT_96.md','manifest96.json']
    temp=out/'test96_results.zip.partial';dest=out/'test96_results.zip'
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for filename in files:
            if (out/filename).exists():z.write(out/filename,arcname=filename)
    if zipfile.ZipFile(temp).testzip() is not None:raise RuntimeError('ZIP validation failure')
    temp.replace(dest)
    (out/'test96_results.sha256').write_text(sha(dest)+'  '+dest.name+'\n',encoding='ascii')

def read_rows(out):
    if not (out/'results96.csv').exists():return []
    with (out/'results96.csv').open(newline='',encoding='utf8') as f:return list(csv.DictReader(f))

def validation(out):
    good=['{}','[]','true','false','null','0','{"a":1}','[1,2,3]','{"x":"é😀"}','"quoted\\\""','{"nested":{"x":[null,false,true]}}','"\\uD83D\\uDE3A"']
    bad=['{','[','[1,]','{"x":}','{"x":1,}','[NaN]','{"x":01}','{"x":+1}','[true false]','"unterminated','{"x":1}junk','{"a":1 "b":2}']
    (out/'valid96.jsonl').write_text('\n'.join(good)+'\n',encoding='utf8')
    (out/'invalid96.jsonl').write_text('\n'.join(bad)+'\n',encoding='utf8')

def execute(args,start_monotonic):
    if platform.machine()!='riscv64':raise RuntimeError('REFUSED: native RVV benchmark must run on EPCC RISC-V compute node, NEVER x86 login')
    src=Path(args.source).resolve();out=Path(args.output).resolve();verify_source(src)
    builds=json.loads((out/'builds96.json').read_text())
    avail=[k for k in VARIANTS if builds['builds'].get(k,{}).get('result')=='PASS']
    if 'A2_REF' not in avail:raise RuntimeError('Reference build missing')
    for name in avail:
        exe=out/('test96_'+name)
        if not exe.is_file() or sha(exe)!=builds['builds'][name]['sha256']:raise RuntimeError('Binary SHA mismatch '+name)
    if set(avail)!=set(VARIANTS):raise RuntimeError('Test96 requires all seven variants; build issues: '+','.join(set(VARIANTS)-set(avail)))
    if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200MiB)')
    import fcntl
    with (out/'test96.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('Another Test96 process owns this run directory')
        statuspath=out/'status96.json'
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
            if statuspath.exists() or (out/'results96.csv').exists():raise RuntimeError('Existing run directory; use --resume or new directory')
            deadline=time.time()+max(0,args.seconds-(time.monotonic()-start_monotonic))
            now=dt.datetime.now(dt.timezone.utc)
            status=dict(schema=1,version=VERSION,state='running',phase='validation',start_utc=now.isoformat(),deadline_utc=dt.datetime.fromtimestamp(deadline,dt.timezone.utc).isoformat(),source_header_sha256=sha(src/'src/rvv/engines/engine_plan.h'),seconds=args.seconds,rows=0,groups=0)
            rows=[];next_group=0;tr_count=0;ho_count=0
        status.update(state='running',updated_utc=utc(),variants=avail)
        write_json(statuspath,status)
        machine=machine_info();write_json(out/'machine96.json',machine)
        core=args.core if args.core is not None else next(iter(machine.get('affinity') or []),None)
        if core is not None and machine.get('affinity') and core not in machine['affinity']:raise RuntimeError('Requested CPU unavailable')
        prefix=['taskset','-c',str(core)] if core is not None and shutil.which('taskset') else []
        status['cpu']=core
        def call(name,mode,*params,timeout=90):
            remaining=deadline-time.time()-3
            if remaining<=0:raise TimeoutError('8h deadline')
            cmd=prefix+[str(out/('test96_'+name)),'rvv',mode]+list(map(str,params))
            return run(cmd,timeout=max(.5,min(timeout,remaining))).stdout
        validation(out)
        support,_,design=modules(src)
        templates=cases(design)
        rng=random.Random(2026101496)
        doc=out/'active96.json'
        def update_snapshot(force=False):
            status.update(rows=len(rows),groups=next_group,updated_utc=utc())
            write_json(statuspath,status)
            report(out,rows,avail,status)
            if force or time.time()-update_snapshot.last_packet>600:
                if shutil.disk_usage(out).free>=MIN_FREE:
                    packet(out);update_snapshot.last_packet=time.time()
                else:print('WARNING: <200 MiB; final ZIP snapshot skipped, raw CSV/status preserved',flush=True)
        update_snapshot.last_packet=0
        mode='a' if args.resume else 'w'
        try:
            for name in avail:
                marker=call(name,'validate',out/'valid96.jsonl',out/'invalid96.jsonl',timeout=90)
                if 'RVV_VALIDATION_OK backend=rvv' not in marker:raise RuntimeError('Validation failed '+name)
            status['validated']=True
            write_json(statuspath,status)
            if not args.resume:write_json(out/'manifest96.json',dict(schema=1,variants=VARIANTS,templates=templates,holdout_seconds=HOLDOUT_SECONDS,version=VERSION,source_header_sha256=status['source_header_sha256'],harness_sha256=builds['harness_sha256'],notes='Exact boundary samples have ASCII pad string; seeds differ by phase. No runtime candidate selection.'))
            with (out/'results96.csv').open(mode,newline='',encoding='utf8') as csvfile:
                writer=csv.DictWriter(csvfile,fieldnames=FIELDS)
                if mode=='w' or (out/'results96.csv').stat().st_size==0:writer.writeheader();csvfile.flush()
                while time.time()<deadline-8:
                    if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety stop (<200 MiB)')
                    holdout=time.time()>=deadline-HOLDOUT_SECONDS
                    phase='holdout' if holdout else 'train'
                    n=ho_count if holdout else tr_count
                    # Rotate through all templates with distinct seeds. Mirror the
                    # case distribution between training and untouched holdout.
                    template=templates[n%len(templates)]
                    seed=202610149600000+9973*n+(887654321 if holdout else 0)
                    family=template['family']
                    status['phase']=phase
                    try:
                        if template['scenario']=='boundary':
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
                        order=avail[:];rng.seed(seed);rng.shuffle(order)
                        # Change relative order to limit fixed thermal/system drift.
                        for name in order:
                            result=call(name,'split',doc,iters,timeout=120)
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
            status['phase']='finish'
            update_snapshot(force=True)
        print('TEST96_DONE',status['state'],status['rows'],flush=True)
    return 0

def main():
    p=argparse.ArgumentParser(description='Test96 8h EPCC node native benchmark; no production changes')
    p.add_argument('action',choices=['plan','build-only','run-only','all'])
    p.add_argument('--source',default='engine');p.add_argument('--output',default='test96_output')
    p.add_argument('--seconds',type=int,default=DURATION)
    p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--core',type=int);p.add_argument('--resume',action='store_true')
    args=p.parse_args();start=time.monotonic()
    if args.action=='plan':
        src=Path(args.source).resolve();verify_source(src)
        _,_,design=modules(src)
        print(json.dumps(dict(duration_seconds=args.seconds,variant_count=len(VARIANTS),variants=VARIANTS,case_count=len(cases(design)),boundaries=BOUNDARIES,holdout_seconds=HOLDOUT_SECONDS),indent=2));return 0
    if not 60<=args.seconds<=DURATION: p.error('seconds must be 60..28800 (8h max)')
    if args.resume and args.action!='run-only':p.error('--resume requires run-only')
    if args.action in ('build-only','all'):build(args)
    if args.action in ('run-only','all'):return execute(args,start)
    return 0
if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:
        print('TEST96_ERROR',str(e),file=sys.stderr)
        raise
