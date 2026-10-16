#!/usr/bin/env python3
"""Test99: extended paired public-DOM benchmarks on immutable simdjson-data documents.

No generated fixtures in performance comparisons. Confirmationed timings of the SAME
published documents are independent executions, NOT independently held-out data.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, math, os, pathlib, platform, random, shlex, shutil, statistics, subprocess, sys, time, zipfile
from collections import defaultdict
from pathlib import Path

VARIANTS=('OFFICIAL_503','OFFICIAL_504','A2_REF','A2_G6144','A2_G8192')
UPSTREAM={'OFFICIAL_503':('v5.0.3','bf89ddd00ef5fcb6a7f20611ea8853d258b67249'),
          'OFFICIAL_504':('v5.0.4','3b0b2b53aaffb46208817821dce2cd47a5e6bb2a')}
FIELDS=('utc','phase','round','document','bytes','document_sha256','variant','backend','gbps','iterations','anchor_before_gbps','anchor_after_gbps','anchor_drift_pct')
MIN_FREE=150*1024*1024

def utc():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def write(p,obj):
    p=Path(p);tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,sort_keys=True,indent=2)+'\n',encoding='utf8');os.replace(tmp,p)
def run(argv,timeout=600):
    a=subprocess.run([str(x) for x in argv],text=True,capture_output=True,timeout=timeout)
    if a.returncode:raise RuntimeError('Exit '+str(a.returncode)+': '+' '.join(map(str,argv[:3]))+': '+a.stdout[-400:]+a.stderr[-1400:])
    return a.stdout.strip()
def check_source(src):
    for rel in ('src/simdjson.cpp','src/rvv/engines/engine_plan.h','include/simdjson.h','include/simdjson/simdjson_version.h'):
        if not (src/rel).is_file():raise RuntimeError('Missing fork source: '+rel)
    if '5.0.3' not in (src/'include/simdjson/simdjson_version.h').read_text():raise RuntimeError('Fork version mismatch: expected v5.0.3')
def build(args):
    out=Path(args.output).resolve();src=Path(args.source).resolve();upstream=out/'upstream-sources'
    if platform.machine()!=args.arch:raise RuntimeError('Wrong build architecture, expected '+args.arch)
    out.mkdir(parents=True,exist_ok=True)
    if (out/'builds99.json').exists():raise RuntimeError('Build already started in this run folder')
    if shutil.disk_usage(out).free<700*1024*1024:raise RuntimeError('Need >=700 MiB free for baseline builds')
    check_source(src)
    compiler=args.cxx
    flags=shlex.split(args.cxx_flags)
    if args.arch=='x86_64' and not any(f.startswith('--target=riscv64') for f in flags):
        raise RuntimeError('EPCC requires explicit riscv64 compiler target')
    if args.arch=='riscv64' and any(f.startswith('--target=') for f in flags):
        raise RuntimeError('Cloud-V native build cannot use cross target')
    upstream.mkdir(parents=True,exist_ok=True)
    heads={}
    for name,(tag,expected) in UPSTREAM.items():
        folder=upstream/name
        run(['git','clone','--quiet','--depth','1','--branch',tag,'https://github.com/simdjson/simdjson.git',folder],timeout=300)
        head=run(['git','-C',folder,'rev-parse','HEAD'],timeout=20)
        if head!=expected:raise RuntimeError('Pinned official upstream tag moved: '+tag+' '+head)
        if not (folder/'include/simdjson.h').is_file():raise RuntimeError('Missing official source '+name)
        heads[name]=head
    bench=Path(__file__).with_name('test99_dom.cpp')
    base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-march=rv64gcv','-mabi=lp64d','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
    builds={}
    for name in VARIANTS:
        if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety limit reached')
        fork=name.startswith('A2_');folder=src if fork else upstream/name
        extra=(['-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0',
            '-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_EXPLORATION91=0',
            '-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0','-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0',
            '-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE=0','-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE=0',
            '-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT=0',
            '-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES='+('8192' if name=='A2_G8192' else '6144' if name=='A2_G6144' else '4096')] if fork else [])
        cmd=[compiler,*flags,*base,*extra,'-I'+str(folder/'include'),'-I'+str(folder/'src')]
        obj=out/(name+'.o');exe=out/('test99_'+name)
        for label,argv in [('compile',[*cmd,'-c',folder/'src/simdjson.cpp','-o',obj]),
                           ('link',[*cmd,bench,obj,'-o',exe])]:
            log=out/('build99_'+name+'_'+label+'.log')
            with log.open('w') as f:
                p=subprocess.run(list(map(str,argv)),stdout=f,stderr=subprocess.STDOUT,timeout=900)
            if p.returncode:raise RuntimeError(name+' '+label+' failed: '+log.read_text(errors='replace')[-1800:])
        obj.unlink(missing_ok=True)
        elf=exe.read_bytes()[:20]
        if elf[:4]!=b'\x7fELF' or elf[4]!=2 or int.from_bytes(elf[18:20],'little')!=243:
            raise RuntimeError(name+' not ELF64 RISC-V')
        exe.chmod(0o755)
        builds[name]={'source_git_commit':heads.get(name),'backend':'rvv' if fork else 'fallback',
                      'sha256':sha(exe),'flags':base+extra,'compiler':compiler,'compiler_target_flags':flags}
        print('TEST99 BUILD PASS',name,flush=True)
    write(out/'builds99.json',{'schema':1,'upstream':heads,'source_fork_sha256':sha(src/'src/simdjson.cpp'),
                              'harness_sha256':sha(bench),'builds':builds})

def report(rows,corpus):
    grouped=defaultdict(dict)
    for row in rows:
        grouped[(row['phase'],row['round'],row['document'])][row['variant']]=float(row['gbps'])
    perfile=defaultdict(list);per_variant=defaultdict(lambda:defaultdict(list))
    for (phase,roundno,doc),group in grouped.items():
        if len(group)!=len(VARIANTS):continue
        for variant in ('OFFICIAL_503','A2_REF','A2_G6144','A2_G8192'):
            if group['OFFICIAL_504']>0 and group[variant]>0:
                per_variant[(phase,variant)][doc].append(math.log(group[variant]/group['OFFICIAL_504']))
        if group['A2_REF']>0:
            for name in ('A2_G6144','A2_G8192'):
                if group[name]>0:
                    per_variant[(phase,name+'_vs_A2_REF')][doc].append(math.log(group[name]/group['A2_REF']))
    drift_by_phase=defaultdict(list)
    for row in rows:
        if row['variant']=='A2_REF':
            drift_by_phase[row['phase']].append(abs(float(row['anchor_drift_pct'])))
    totals={}
    for (phase,variant),files in per_variant.items():
        per_file={doc:{'pairs':len(vals),'ratio':math.exp(statistics.mean(vals))} for doc,vals in files.items()}
        # Equally weight each original JSON file, not repeated timing rows or byte count.
        totals.setdefault(phase,{})[variant]={'per_file':per_file,
            'file_equal_geomean':math.exp(statistics.mean(statistics.mean(vals) for vals in files.values())),
            'complete_files':len(files),'paired_rounds':sum(map(len,files.values()))}
    return {'schema':1,'method':'geometric mean of paired DOM throughput ratios, first per file then equal weight across files',
            'important':'Confirmationed measurements reuse the same public files; confirmation is NOT an unseen-file holdout',
            'rounds_complete':len([1 for group in grouped.values() if len(group)==len(VARIANTS)]),
            'corpus_files':len(corpus['files']),'comparisons':totals,
            'anchor_drift_abs_percent':{phase:{'median':statistics.median(values),
                'over_10pct':sum(v>10.0 for v in values),'groups':len(values)}
                for phase,values in drift_by_phase.items()}}

def package(out,rows,status,corpus):
    summ=report(rows,corpus)
    write(out/'summary99.json',summ)
    lines=['# Test 99 — Published JSON fixture corpus (EPCC / Cloud-V)','',
      'This is a benchmark on a **pinned public simdjson-data corpus**, not generated JSON. The selected fixtures include real-world-like examples but do not certify representativeness of production traffic.','',
      'Machine: `'+str(status.get('machine','unknown'))+'`; state: `'+status['state']+'`; total rows: '+str(len(rows))+'.','',
      'Corpus commit: `'+corpus['upstream_commit']+'`; file count: '+str(len(corpus['files']))+'.','',
      'Official v5.0.4 uses **fallback** on RISC-V; fork A2 uses **rvv**. These are platform-specific relative throughputs.','',
      '| Phase | Variant | File-equal geometric mean vs official 5.0.4 | Complete files |','|---|---|---:|---:|---:|']
    for phase,values in summ['comparisons'].items():
        for v,rec in values.items():
            lines.append(f'| {phase} | {v} | {rec["file_equal_geomean"]:.4f}× | {rec["complete_files"]} |')
    lines+=['','## Per-document results (independent corpus units)','',
            '| Phase | Document | A2_REF / official 5.0.4 | A2_G6144 / official 5.0.4 | A2_G8192 / official 5.0.4 |','|---|---|---:|---:|---:|']
    for phase,values in summ['comparisons'].items():
        a=values.get('A2_REF',{}).get('per_file',{});c=values.get('A2_G6144',{}).get('per_file',{});b=values.get('A2_G8192',{}).get('per_file',{})
        for name in sorted(set(a)&set(b)&set(c)):
            lines.append(f'| {phase} | {name} | {a[name]["ratio"]:.4f}× | {c[name]["ratio"]:.4f}× | {b[name]["ratio"]:.4f}× |')
    lines+=['','## Interpretation and limitations','',
            '- Same byte-identical JSON files on both machines, identified with SHA256.',
            '- Same machine and public DOM parse API for all five variants within each host.',
            '- Randomized variant ordering per document/round; per-document paired ratios.',
            '- A2_REF anchor measured before and after each document group to expose thermal/frequency drift.',
            '- `confirmation` is a separate timing period on the same documents, not a holdout of unseen files.',
            '- No synthetic input generation in the performance measurements.',
            '- Single node per result; independent reruns recommended for variance and confidence intervals.',
            '- Last two hours are confirmation with same documents, not an independent file holdout.',
            '- Dataset is a published collection of mixed examples, **not a formal universal/representative real-world benchmark**.',
            '- Official simdjson v5 uses scalar `fallback` on these RISC-V nodes; not a same-backend algorithm-only comparison.',
            '- Raw CSV, source commits, binary hashes, corpus manifest and machine metadata are in the result ZIP.','']
    (out/'REPORT_99.md').write_text('\n'.join(lines),encoding='utf8')
    names=['builds99.json','machine99.json','status99.json','results99.csv','summary99.json','REPORT_99.md','corpus_manifest99.json']
    if not all((out/name).is_file() for name in names):return
    if status['state'] not in ('completed','failed'):return
    tmp=out/'test99_results.zip.partial'
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in names:z.write(out/name,name)
    with zipfile.ZipFile(tmp) as z:
        if z.testzip():raise RuntimeError('Results archive CRC error')
    os.replace(tmp,out/'test99_results.zip')
    (out/'test99_results.sha256').write_text(sha(out/'test99_results.zip')+'  test99_results.zip\n',encoding='ascii')

def execute(args):
    if platform.machine()!='riscv64':raise RuntimeError('Measurements must run on RISC-V node')
    src=Path(args.output).resolve();corpus=Path(args.corpus).resolve();out=src
    if (out/'status99.json').exists():raise RuntimeError('Existing run: will not relaunch or overwrite it')
    if shutil.disk_usage(out).free<MIN_FREE:raise RuntimeError('Disk safety cap')
    man=json.loads((corpus/'manifest.json').read_text())
    if man['upstream_commit']!='4197c425e857f0ec38e89922fdd0bd9ea21f4daf':raise RuntimeError('Corpus commit mismatch')
    docs=[]
    for rec in man['files']:
        file=corpus/'files'/rec['name']
        if not file.is_file() or file.stat().st_size!=rec['bytes'] or sha(file)!=rec['sha256']:
            raise RuntimeError('Missing/unverified corpus document '+rec['name'])
        docs.append((rec,file))
    if len(docs)<8:raise RuntimeError('Benchmark requires >=8 published documents')
    b=json.loads((out/'builds99.json').read_text())['builds']
    if set(b)!=set(VARIANTS):raise RuntimeError('Missing official builds or fork builds')
    for name in VARIANTS:
        file=out/('test99_'+name)
        if not file.is_file() or sha(file)!=b[name]['sha256']:raise RuntimeError('Binary mismatch '+name)
    from fcntl import flock,LOCK_EX,LOCK_NB
    with (out/'test99.lock').open('a') as lock:
        flock(lock,LOCK_EX|LOCK_NB)
        status={'state':'starting','phase':'validation','rows':0,'groups':0,'start_utc':utc(),
                'machine':platform.node(),'duration_seconds':args.seconds,'confirmation_seconds':args.confirmation_seconds,
                'corpus_id':man['corpus_id']}
        write(out/'status99.json',status)
        write(out/'machine99.json',{'architecture':platform.machine(),'hostname':platform.node(),
            'cpu_affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else [],'utc':utc(),
            'platform':platform.platform()})
        write(out/'corpus_manifest99.json',man)
        prefix=[]
        if hasattr(os,'sched_getaffinity') and shutil.which('taskset'):
            cpu=min(os.sched_getaffinity(0));prefix=['taskset','-c',str(cpu)]
        start=time.monotonic();deadline=start+args.seconds
        def call(name,action,file,iterations=None):
            cmd=[*prefix,out/('test99_'+name),b[name]['backend'],action,file]
            if iterations is not None:cmd.append(iterations)
            return run(cmd,timeout=min(140,max(20,deadline-time.monotonic())))
        rows=[];rng=random.Random(198497);round_no=0
        try:
            # PUBLIC DOM API must agree on each original document before timing.
            for rec,file in docs:
                checks=[call(v,'check',file) for v in VARIANTS]
                if not all(x.startswith('CHECK_OK ') for x in checks) or len(set(checks))!=1:
                    raise RuntimeError('Cross-implementation JSON DOM mismatch on '+rec['name']+' '+str(checks))
            status['validated']=True;status['state']='running';write(out/'status99.json',status)
            with (out/'results99.csv').open('w',encoding='utf8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();f.flush()
                while time.monotonic()<deadline-20:
                    phase='confirmation' if deadline-time.monotonic()<=args.confirmation_seconds else 'measure'
                    shuffled=list(docs);rng.shuffle(shuffled)
                    for rec,file in shuffled:
                        if time.monotonic()>=deadline-20:break
                        order=list(VARIANTS);rng.shuffle(order)
                        iterations=max(2,min(100,2_000_000//rec['bytes']))
                        def read_bench(name):
                            val=call(name,'bench',file,iterations).split()
                            if len(val)!=4 or val[0]!='BENCH_OK' or int(val[2])!=rec['bytes'] or int(val[3])!=iterations:
                                raise RuntimeError('Invalid benchmark output '+name+': '+str(val))
                            g=float(val[1])
                            if not (0<g<500 and math.isfinite(g)):
                                raise RuntimeError('Nonfinite benchmark result for '+name)
                            return g
                        before=read_bench('A2_REF')
                        readings={name:read_bench(name) for name in order}
                        after=read_bench('A2_REF')
                        drift=100.0*(after/before-1.0)
                        block=[{'utc':utc(),'phase':phase,'round':round_no,'document':rec['name'],
                                'bytes':rec['bytes'],'document_sha256':rec['sha256'],'variant':name,
                                'backend':b[name]['backend'],'gbps':readings[name],'iterations':iterations,
                                'anchor_before_gbps':before,'anchor_after_gbps':after,
                                'anchor_drift_pct':drift} for name in order]
                        for row in block:writer.writerow(row);rows.append(row)
                        f.flush()
                    round_no+=1
                    status.update(phase=phase,rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
                    write(out/'status99.json',status)
                    if round_no%3==0:package(out,rows,status,man)
            if not rows or not any(r['phase']=='confirmation' for r in rows):
                raise RuntimeError('Not enough complete measurements in confirmation period')
            status.update(state='completed',phase='finish',rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
        except Exception as exc:
            status.update(state='failed',phase='finish',reason=str(exc),rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
            raise
        finally:
            write(out/'status99.json',status)
            if (out/'results99.csv').exists():package(out,rows,status,man)
    print('TEST99_DONE',status['state'],status['rows'])

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('build','run'))
    p.add_argument('--source',default='');p.add_argument('--output',required=True)
    p.add_argument('--corpus',default='');p.add_argument('--arch',default='x86_64')
    p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--seconds',type=int,default=28800);p.add_argument('--confirmation-seconds',type=int,default=7200)
    a=p.parse_args()
    if not (1200<=a.seconds<=30000 and 120<=a.confirmation_seconds<a.seconds/2):p.error('Invalid measurement time')
    if a.action=='build':build(a)
    else:execute(a)
if __name__=='__main__':main()
