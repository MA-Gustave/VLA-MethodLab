#!/usr/bin/env python3
"""Test 103: compiled Stage 2 optimizations with paired Stage1/Stage2/DOM measurements.

No optimization is promoted by this program. Original public, new synthetic and
independently seeded confirmation cases are never pooled as independent documents.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math,os,pathlib,platform,random,shlex,shutil,signal,statistics,subprocess,sys,tempfile,time,zipfile
from collections import defaultdict
from pathlib import Path

VARIANTS=('OFFICIAL_504','A2_G16384','A2_SIMPLE_RUN','A2_NL4')
EXPECTED_FORK_SHA='fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16'
EXPECTED_PLAN_SHA='7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e'
UPSTREAM_SHA='3b0b2b53aaffb46208817821dce2cd47a5e6bb2a'
CORPUS_COMMIT='4197c425e857f0ec38e89822fdd0bd9ea21f4daf'
CORPUS_ID='simdjson-data-4197c425-test98'
PUBLIC=('apache_builds.json','canada.json','citm_catalog.json','github_events.json','google_maps_api_compact_response.json','google_maps_api_response.json','gsoc-2018.json','instruments.json','marine_ik.json','mesh.json','mesh.pretty.json','numbers.json','twitter_api_compact_response.json','twitter_api_response.json','twitterescaped.json','twitter.json','twitter_timeline.json','update-center.json')
METRICS=('dom_gbps','stage1_gbps','stage2_gbps')
FIELDS=('utc','phase','round','group','stratum','document','family','requested_density_pct','actual_density_pct','placement','backslashes_per_probe','bytes','sha256','variant','backend','iterations','dom_gbps','stage1_gbps','stage2_gbps','anchor_before_dom_gbps','anchor_after_dom_gbps','anchor_drift_pct')
FILES=('status103.json','builds103.json','machine103.json','inputs103.json','corpus_manifest103.json','results103.csv','summary103.json','REPORT_103.md','studio103-build.log','studio103-cloudv.log','slurm103-exit.json','slurm103-runtime.log')

def utc():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def save(p,obj):
    p=Path(p);p.parent.mkdir(exist_ok=True,parents=True)
    tmp=p.with_name(p.name+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,ensure_ascii=False)+'\n',encoding='utf8');os.replace(tmp,p)
def run(cmd,timeout=360):
    p=subprocess.run([str(x) for x in cmd],capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError('Failed command ('+str(p.returncode)+') '+str(cmd[:3])+': '+(p.stdout+p.stderr)[-1400:])
    return p.stdout.strip()
def corpus_verify(root):
    root=Path(root).resolve();f=root/'manifest.json'
    if not f.is_file():raise RuntimeError('Missing shared Performance corpus manifest: '+str(f))
    m=json.loads(f.read_text())
    if m.get('upstream_commit')!=CORPUS_COMMIT or m.get('corpus_id')!=CORPUS_ID:
        raise RuntimeError('Wrong corpus commit/id: '+str(m.get('upstream_commit')))
    if tuple(x.get('name') for x in m.get('files',[]))!=PUBLIC:raise RuntimeError('Expected exactly the 18 pinned public fixtures')
    docs=[]
    for entry in m['files']:
        name=entry['name'];p=root/'files'/name
        if not p.is_file() or p.stat().st_size!=entry['bytes'] or sha(p)!=entry['sha256']:
            raise RuntimeError('Performance corpus bytes/hash mismatch: '+name)
        docs.append({'name':name,'file':p,'bytes':entry['bytes'],'sha256':entry['sha256'],
                     'stratum':'public_original','family':'public','requested_density_pct':None,
                     'actual_density_pct':100*p.read_bytes().count(b'\\')/entry['bytes'],
                     'placement':'original','backslashes_per_probe':None})
    return m,docs

def synthetic_build(root,phase):
    """Deterministic independent-seed stress cases; valid exact-size JSON.

    Densities reflect raw backslash bytes, NOT decoded escape frequency. The
    unicode \\uXXXX token limits maximum realizable density to ~16.7%; actual
    density, never the target, is recorded in the dataset metadata.
    """
    folder=Path(root)/('fixtures103-'+phase);folder.mkdir(parents=True,exist_ok=True)
    docs=[];seed=20261016 if phase=='explore' else 20261207
    fill=b'A' if phase=='explore' else b'B'
    def add(name,raw,family,desired,placement,probe=None):
        # Strictly require byte-for-byte valid JSON before adding the sample.
        json.loads(raw)
        p=folder/name;p.write_bytes(raw)
        docs.append({'name':phase+'/'+name,'file':p,'bytes':len(raw),'sha256':sha(p),
          'stratum':'synthetic_'+phase,'family':family,'requested_density_pct':desired,
          'actual_density_pct':100*raw.count(b'\\')/len(raw),'placement':placement,
          'backslashes_per_probe':probe})
    for size in (8192,16384):
        for family in ('newline','quote','slash','unicode','mixed'):
            atom={'newline':b'\\n','quote':b'\\"','slash':b'\\\\','unicode':b'\\u0041','mixed':b'\\t'}[family]
            for pct in (0,1,3,6,10,15,25,50):
                prefix=b'{"payload":"';suffix=b'","ok":true}' if phase=='explore' else b'","ok":null}'
                room=size-len(prefix)-len(suffix)
                count=min(int(size*pct/100),room//len(atom))
                # The same public algorithm but distinct independent seeds per phase.
                rng=random.Random(seed+size*31+sum(map(ord,family))*100+pct)
                atoms=[atom]*count+([fill]*(room-count*len(atom)))
                rng.shuffle(atoms)
                raw=prefix+b''.join(atoms)+suffix
                if len(raw)!=size:raise AssertionError('Invalid exact-size fixture')
                add(f'{family}-{pct:02d}pct-{size}.json',raw,family,pct,'shuffled')
    # Exact crossover: 8 vs 9 backslashes, plus prefix-vs-after-512 placement.
    for size in (4095,4096,4097,8192,16383,16384,16385):
        for count in (0,1,2,4,8,9,12,16,32):
            for placement in ('early','after512'):
                prefix=b'{"payload":"';suffix=b'","ok":true}' if phase=='explore' else b'","ok":null}'
                room=size-len(prefix)-len(suffix)
                start=8 if placement=='early' else 768
                # All escapes deliberately confined to a short region; for
                # count=32, 64 raw bytes are exactly 32 escapes (maximum).
                raw=prefix+fill*start+b'\\n'*count+fill*(room-start-2*count)+suffix
                if len(raw)!=size:raise AssertionError('Crossover length mismatch')
                add(f'cross-{size}-{count:02d}-{placement}.json',raw,'crossover',None,placement,count)
    return docs

def verify_source(src):
    src=Path(src)
    for rel in ('src/simdjson.cpp','src/rvv/engines/engine_plan.h','include/simdjson.h','include/simdjson/simdjson_version.h'):
        if not (src/rel).is_file():raise RuntimeError('Missing source: '+rel)
    if sha(src/'src/simdjson.cpp')!=EXPECTED_FORK_SHA or sha(src/'src/rvv/engines/engine_plan.h')!=EXPECTED_PLAN_SHA:
        raise RuntimeError('Source code differs from Test101 benchmarked fork; preserve provenance and use pinned snapshot')
    if '5.0.3' not in (src/'include/simdjson/simdjson_version.h').read_text(errors='replace'):
        raise RuntimeError('Expected verified 5.0.3 fork')

def build(a):
    src=Path(a.source).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if platform.machine()!=a.arch:raise RuntimeError('Build host arch mismatch: '+platform.machine())
    verify_source(src)
    if (out/'builds103.json').exists():raise RuntimeError('Do not overwrite existing Test103 builds')
    if shutil.disk_usage(out).free<750*1024**2:raise RuntimeError('Need 750 MiB free before compilation')
    flags=shlex.split(a.cxx_flags)
    if a.arch=='x86_64' and not any(x.startswith('--target=riscv64') for x in flags):raise RuntimeError('EPCC needs RISC-V cross target')
    official=out/'upstream-504';official.parent.mkdir(exist_ok=True)
    run(['git','clone','--quiet','--depth','1','--branch','v5.0.4','https://github.com/simdjson/simdjson.git',official],timeout=300)
    if run(['git','-C',official,'rev-parse','HEAD'])!=UPSTREAM_SHA:raise RuntimeError('Wrong official 5.0.4 commit')
    base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-march=rv64gcv','-mabi=lp64d','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
    bench=Path(__file__).with_name('test103_split.cpp');builds={}
    for v in VARIANTS:
        if shutil.disk_usage(out).free<170*1024**2:raise RuntimeError('Disk safety below 170 MiB')
        fork=v!='OFFICIAL_504';root=src if fork else official
        threshold=None if not fork else 16384
        extra=[] if not fork else ['-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0',
          '-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_EXPLORATION91=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0','-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE=0','-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT=0','-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES='+str(threshold)]
        overlay=out/'test103-stage2-overlay'/'generic'/'stage2'
        if v in ('A2_SIMPLE_RUN','A2_NL4'):
            from test103_stage2_patch import create_overlay
            patch_info=create_overlay(src/'src/generic/stage2/stringparsing.h',overlay/'stringparsing.h')
            extra.append('-DSIMDJSON_TEST103_SIMPLE_RUN=1')
            if v=='A2_NL4':extra.append('-DSIMDJSON_TEST103_NL4=1')
        cmd=[a.cxx,*flags,*base,*extra,'-I'+str(root/'include')]
        if v in ('A2_SIMPLE_RUN','A2_NL4'):cmd+=['-I'+str(overlay.parent.parent)]
        cmd+=['-I'+str(root/'src')]
        obj=out/(v+'.o');exe=out/('test103_'+v)
        for label,args in (('compile',[*cmd,'-c',root/'src/simdjson.cpp','-o',obj]),
                           ('link',[*cmd,bench,obj,'-o',exe])):
            log=out/('build103_'+v+'_'+label+'.log')
            with log.open('w') as stream:
                p=subprocess.run([str(x) for x in args],stdout=stream,stderr=subprocess.STDOUT,timeout=1000)
            if p.returncode:raise RuntimeError(v+' '+label+' failed: '+log.read_text(errors='replace')[-1500:])
        obj.unlink(missing_ok=True)
        header=exe.read_bytes()[:20]
        if header[:4]!=b'\x7fELF' or header[4]!=2 or int.from_bytes(header[18:20],'little')!=243:
            raise RuntimeError('Not RISC-V ELF: '+v)
        exe.chmod(0o755)
        builds[v]={'backend':'rvv' if fork else 'fallback','sha256':sha(exe),'threshold':threshold,
                   'compiler':a.cxx,'compiler_flags':flags,'flags':base+extra,'source_commit':None if fork else UPSTREAM_SHA,'stage2_patch':v in ('A2_SIMPLE_RUN','A2_NL4'), 'stage2_patch_mode':v if v in ('A2_SIMPLE_RUN','A2_NL4') else None}
        print('TEST103 BUILD PASS',v,flush=True)
    save(out/'builds103.json',{'schema':1,'builds':builds,'fork_sha256':EXPECTED_FORK_SHA,'plan_sha256':EXPECTED_PLAN_SHA,
       'stage2_patch_sha256':sha(out/'test103-stage2-overlay'/'generic'/'stage2'/'stringparsing.h'), 'harness_sha256':sha(bench),'official_tag':'v5.0.4','official_commit':UPSTREAM_SHA})

def calculate(rows, breakdown='family'):
    """Paired repeated measurements per document; benchmark phases never pooled.
    Return optimizations relative to original A2, and unchanged official fallback.
    """
    by_group=defaultdict(dict)
    for r in rows:
        by_group[(r['phase'],r['stratum'],r['document'],r['round'])][r['variant']]=r
    raw=defaultdict(list)
    for (phase,stratum,doc,rnd),group in by_group.items():
        if set(group)!=set(VARIANTS):continue
        meta=group['A2_G16384']
        family=meta['family']
        if breakdown=='density':
            if not stratum.startswith('synthetic_') or family=='crossover':continue
            family=family+'/requested_'+str(meta['requested_density_pct'])+'pct'
        elif breakdown=='crossover':
            if family!='crossover':continue
            family='crossover/count_'+str(meta['backslashes_per_probe'])+'/'+str(meta['placement'])
        key='/'.join((phase,stratum,family))
        for candidate in ('A2_SIMPLE_RUN','A2_NL4','A2_G16384'):
            for baseline in ('A2_G16384','OFFICIAL_504','A2_SIMPLE_RUN'):
                if baseline=='A2_SIMPLE_RUN' and candidate!='A2_NL4':continue
                if candidate==baseline:continue
                for metric in METRICS:
                    a=float(group[candidate][metric]);b=float(group[baseline][metric])
                    if a>0 and b>0:raw[(key,candidate,baseline,metric,doc)].append(math.log(a/b))
    aggregate=defaultdict(dict)
    for (key,candidate,baseline,metric,doc),values in raw.items():
        aggregate[(key,candidate,baseline,metric)][doc]=statistics.mean(values)
    output={}
    for (key,candidate,baseline,metric),docs in sorted(aggregate.items()):
        output.setdefault(key,{}).setdefault(candidate,{}).setdefault(baseline,{})[metric]={
          'geomean_ratio':math.exp(statistics.mean(docs.values())), 'documents':len(docs)}
    return output

def package(out,status,rows):
    out=Path(out)
    summary={'schema':1,'method':'paired log throughput ratios; equal weight per input document; separate phase/stratum/machine',
             'comparisons':'candidate / original A2, official fallback, and NL4 / SIMPLE_RUN',
             'workloads':calculate(rows),'density_sweep':calculate(rows,'density'),
             'crossover':calculate(rows,'crossover'),'row_count':len(rows)}
    save(out/'summary103.json',summary)
    report=['# Test 103 — Real Stage 2 escape-decoder optimization', '',
      f"State: **{status.get('state')}**; rows: **{len(rows)}**; phase: **{status.get('phase')}**.", '',
      '## Variant definitions','',
      '- `OFFICIAL_504`: unmodified simdjson v5.0.4, fallback backend.',
      '- `A2_G16384`: unmodified RVV A2, 16 KiB dispatch threshold.',
      '- `A2_SIMPLE_RUN`: A2 with scalar consecutive simple-escape decoding inside Stage 2.',
      '- `A2_NL4`: A2 with the same scalar run and four-pair `\\n` burst specialization.',
      '- These are **experimental compile-only overlays**. No production checkout is mutated.', '',
      '## Measurement interpretation','',
      '- Separate DOM, internal Stage 1, internal Stage 2: not additive.',
      '- Public inputs and generated synthetic stress are NEVER pooled.',
      '- Explore and confirm synthetic seeds are distinct; repeat runs are not independent source samples.',
      '- Synthetic 50% backslash stress is intentionally pathological.',
      '- Per-machine results only; no pooled EPCC/Cloud-V speedup.','',
      '## Paired geometric throughput ratios (above 1.0 is faster)','',
      '| Phase / workload | Candidate | Baseline | DOM | Stage 1 | Stage 2 |',
      '|---|---|---|---:|---:|---:|']
    for k,cands in sorted(summary['workloads'].items()):
        for cand,bases in sorted(cands.items()):
            for baseline,metrics in sorted(bases.items()):
                vals=[metrics.get(m,{}).get('geomean_ratio') for m in METRICS]
                report.append('| '+k+' | '+cand+' | '+baseline+' | '+' | '.join(f'{x:.4f}x' if x is not None else '—' for x in vals)+' |')
    report+=['','## Density sweep and crossover','',
             'The exact density and crossover breakdown is in `summary103.json`.','',
             '## Promotion gate','',
             'No automatic promotion. Require correctness parity, independent confirmation on both machines,',
             'non-regression on public JSON, and a measurable Stage 2/DOM gain on dense escapes.','']
    (out/'REPORT_103.md').write_text('\n'.join(report),encoding='utf8')
    archive=out/'test103_results.zip';temp=out/'test103_results.zip.partial'
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name in FILES:
            f=out/name
            if f.is_file() and f.stat().st_size<480_000_000:z.write(f,name)
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('ZIP CRC check failed')
    os.replace(temp,archive)
    (out/'test103_results.sha256').write_text(sha(archive)+'  test103_results.zip\n')

def measure(a):
    if platform.machine()!='riscv64':raise RuntimeError('Benchmark execution requires riscv64')
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'results103.csv').exists():raise RuntimeError('Existing results are immutable; refusing to overwrite')
    if shutil.disk_usage(out).free<150*1024**2:raise RuntimeError('Disk free space too low')
    interrupted=[False]
    signal.signal(signal.SIGTERM,lambda *_:interrupted.__setitem__(0,True))
    signal.signal(signal.SIGINT,lambda *_:interrupted.__setitem__(0,True))
    rows=[];start_wall=time.monotonic();status={'state':'preflight','phase':'native-preflight','validated':False,
       'rows':0,'groups':0,'started_utc':utc(),'machine':platform.node(),'max_seconds':a.max_seconds}
    save(out/'status103.json',status)
    try:
        manifest,public=corpus_verify(a.corpus)
        save(out/'corpus_manifest103.json',manifest)
        builds=json.loads((out/'builds103.json').read_text())['builds']
        if set(builds)!=set(VARIANTS):raise RuntimeError('Missing build metadata')
        for name in VARIANTS:
            exe=out/('test103_'+name)
            if not exe.is_file() or sha(exe)!=builds[name]['sha256']:raise RuntimeError('Binary SHA-256 mismatch '+name)
        # Different random seeds between explore and confirm, created before measurement.
        synthetic={phase:synthetic_build(out,phase) for phase in ('explore','confirm')}
        docs_by_phase={phase:public+synthetic[phase] for phase in ('explore','confirm')}
        manifest_list=[]
        for phase,docs in docs_by_phase.items():
            for d in docs:
                manifest_list.append({k:d[k] for k in ('name','bytes','sha256','stratum','family','requested_density_pct','actual_density_pct','placement','backslashes_per_probe')})
        save(out/'inputs103.json',{'schema':1,'corpus_commit':CORPUS_COMMIT,'public_count':len(public),
             'synthetic_explore_count':len(synthetic['explore']),'synthetic_confirm_count':len(synthetic['confirm']),
             'method':'fixed raw bytes and independent synthetic seeds; no reuse in confirm','files':manifest_list})
        save(out/'machine103.json',{'machine':platform.node(),'arch':platform.machine(),
            'cpu_affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else [],
            'compiler':builds['A2_G16384']['compiler'],'utc':utc()})
        aff=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else []
        prefix=['taskset','-c',str(aff[0])] if aff and shutil.which('taskset') else []
        def call(v,mode,document,iters=None):
            argv=[*prefix,out/('test103_'+v),builds[v]['backend'],mode,document]
            if iters is not None:argv.append(iters)
            return run(argv,timeout=180)
        # Native correctness must pass all generated and public files before measurements.
        for phase,docs in docs_by_phase.items():
            for d in docs:
                if phase=='confirm' and d['stratum']=='public_original':continue
                check=[call(v,'check',d['file']) for v in VARIANTS]
                if len(set(check))!=1 or not all(s.startswith('CHECK_OK ') for s in check):
                    raise RuntimeError('DOM correctness mismatch: '+d['name'])
        status.update(state='running',phase='explore',validated=True,updated_utc=utc())
        save(out/'status103.json',status)
        def parse(s,d,iters):
            z=s.split()
            if len(z)!=9 or z[0]!='SPLIT_RESULT' or int(z[-2])!=iters or int(z[-1])!=d['bytes']:
                raise RuntimeError('Split-stage output format mismatch: '+s[:220])
            m=[float(x) for x in z[1:4]]
            if not all(math.isfinite(x) and 0<x<1000 for x in m):raise RuntimeError('Invalid throughput '+s)
            return m
        iterations={}
        for d in docs_by_phase['explore']:
            guess=min(500,max(4,1000000//d['bytes']))
            speed=parse(call('A2_G16384','split',d['file'],guess),d,guess)[0]
            seconds=d['bytes']*guess/(speed*1e9)
            want=int(guess*0.020/max(seconds,1e-7))
            iterations[(d['family'],d['bytes'])]=max(3,min(1000,want))
        deadline=start_wall+a.max_seconds;cutover=start_wall+a.explore_seconds
        round_id=0;group_id=0;last_status=time.monotonic()
        rng=random.Random(20261018)
        with (out/'results103.csv').open('w',newline='',encoding='utf8') as f:
            writer=csv.DictWriter(f,fieldnames=FIELDS);writer.writeheader();f.flush()
            while time.monotonic()<deadline-120 and not interrupted[0]:
                phase='explore' if time.monotonic()<cutover else 'confirm'
                status['phase']=phase
                docs=list(docs_by_phase[phase]);rng.shuffle(docs)
                for d in docs:
                    if interrupted[0] or time.monotonic()>=deadline-120:break
                    # Avoid a round crossing phases: no confirm rows in explore.
                    if phase=='explore' and time.monotonic()>=cutover:break
                    iters=iterations.get((d['family'],d['bytes']),32)
                    before=parse(call('A2_G16384','split',d['file'],iters),d,iters)
                    names=list(VARIANTS);rng.shuffle(names)
                    readings={v:parse(call(v,'split',d['file'],iters),d,iters) for v in names}
                    after=parse(call('A2_G16384','split',d['file'],iters),d,iters)
                    drift=100*(after[0]/before[0]-1)
                    # Commit complete paired groups only; there are no partial rows.
                    block=[]
                    for v in names:
                        record={'utc':utc(),'phase':phase,'round':round_id,'group':group_id,
                         'stratum':d['stratum'],'document':d['name'],'family':d['family'],
                         'requested_density_pct':d['requested_density_pct'],'actual_density_pct':d['actual_density_pct'],
                         'placement':d['placement'],'backslashes_per_probe':d['backslashes_per_probe'],
                         'bytes':d['bytes'],'sha256':d['sha256'],'variant':v,'backend':builds[v]['backend'],
                         'iterations':iters,'anchor_before_dom_gbps':before[0],
                         'anchor_after_dom_gbps':after[0],'anchor_drift_pct':drift}
                        record.update(zip(METRICS,readings[v]));block.append(record)
                    for record in block:writer.writerow(record);rows.append(record)
                    f.flush();group_id+=1
                    if f.tell()>430_000_000:
                        raise RuntimeError('CSV 430MB safety cap; partial results preserved in failure packet')
                    if group_id%12==0 or time.monotonic()-last_status>60:
                        status.update(rows=len(rows),groups=group_id,rounds=round_id,
                            elapsed_seconds=int(time.monotonic()-start_wall),updated_utc=utc())
                        save(out/'status103.json',status);last_status=time.monotonic()
                round_id+=1
                if shutil.disk_usage(out).free<80*1024**2:raise RuntimeError('Emergency disk safety stop (<80 MiB)')
            status.update(state='stopped' if interrupted[0] else 'completed',phase='finish',
              rows=len(rows),groups=group_id,rounds=round_id,validated=len(rows)>0,
              stop_reason='signal' if interrupted[0] else 'overnight_budget',
              elapsed_seconds=int(time.monotonic()-start_wall),updated_utc=utc())
    except Exception as e:
        status.update(state='failed',phase='finish',reason=str(e),rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
        raise
    finally:
        save(out/'status103.json',status)
        package(out,status,rows)
    print('TEST103_DONE',status['state'],status['rows'],flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('build','preflight','run'))
    p.add_argument('--source',default='');p.add_argument('--corpus',default='');p.add_argument('--output',required=True)
    p.add_argument('--arch',default='x86_64');p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--max-seconds',type=int,default=23400)
    p.add_argument('--explore-seconds',type=int,default=14400)
    a=p.parse_args(argv)
    if a.action=='build':build(a)
    elif a.action=='preflight':
        manifest,docs=corpus_verify(a.corpus)
        verify_source(a.source) if a.source else None
        with tempfile.TemporaryDirectory(prefix='test103-preflight-') as tmp:
            d=synthetic_build(tmp,'explore')
            e=synthetic_build(tmp,'confirm')
            if len(d)!=206 or len(e)!=206:raise RuntimeError('Unexpected synthetic probe count: '+str((len(d),len(e))))
            if set(x['sha256'] for x in d) & set(x['sha256'] for x in e):raise RuntimeError('Confirmation reuses a synthetic fixture byte-for-byte')
        print('TEST103_PREFLIGHT_OK',len(docs),len(d),len(e),manifest['upstream_commit'])
    else:
        if not (3600<=a.explore_seconds<a.max_seconds<=25200 and a.max_seconds-a.explore_seconds>=3600):
            p.error('Invalid overnight phase budgets')
        measure(a)
if __name__=='__main__':main()
