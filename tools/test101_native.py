#!/usr/bin/env python3
"""Test 101: cross-machine confirmation with original, public-derived, and synthetic strata.

Important: public fixtures and synthetic boundaries are NEVER pooled into one ranking.
The fixed public corpus is held byte-identical across targets; generated boundary JSON
is labeled synthetic. Cross-implementation DOM equality is required before any timings.
"""
from __future__ import annotations
import argparse, signal, csv, datetime as dt, hashlib, json, math, os, pathlib, platform, random, shlex, shutil, statistics, subprocess, sys, tempfile, time, zipfile
from collections import defaultdict
from pathlib import Path

VARIANTS=('OFFICIAL_504','A2_REF','A2_G8192','A2_G10240','A2_G12288','A2_G16384')
UPSTREAM_TAG='v5.0.4'
UPSTREAM_SHA='3b0b2b53aaffb46208817821dce2cd47a5e6bb2a'
CORPUS_COMMIT='4197c425e857f0ec38e89822fdd0bd9ea21f4daf'  # from tools/corpus98.py
CORPUS_ID='simdjson-data-4197c425-test98'
EXPECTED_DOCS=('apache_builds.json','canada.json','citm_catalog.json','github_events.json',
 'google_maps_api_compact_response.json','google_maps_api_response.json','gsoc-2018.json','instruments.json',
 'marine_ik.json','mesh.json','mesh.pretty.json','numbers.json',
 'twitter_api_compact_response.json','twitter_api_response.json','twitterescaped.json','twitter.json',
 'twitter_timeline.json','update-center.json')
FIELDS=('utc','stratum','round','block','document','bytes','document_sha256','variant','backend','gbps','iterations','anchor_before_gbps','anchor_after_gbps','anchor_drift_pct')
MIN_DISK=150*1024*1024

def utc():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def save(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    t=path.with_name(path.name+'.tmp')
    t.write_text(json.dumps(data,sort_keys=True,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    os.replace(t,path)
def run(argv,timeout=360):
    p=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=timeout)
    if p.returncode:raise RuntimeError('Command failed ('+str(p.returncode)+'): '+' '.join(map(str,argv[:3]))+' '+(p.stdout+p.stderr)[-1200:])
    return p.stdout.strip()
def corpus_verify(root):
    root=Path(root).resolve();m=root/'manifest.json'
    if not m.is_file():raise RuntimeError('Missing shared Performance corpus manifest: '+str(m))
    manifest=json.loads(m.read_text(encoding='utf8'))
    if manifest.get('upstream_commit')!=CORPUS_COMMIT or manifest.get('corpus_id')!=CORPUS_ID:
        raise RuntimeError('Corpus provenance mismatch: expected '+CORPUS_COMMIT+', got '+str(manifest.get('upstream_commit')))
    entries=manifest.get('files',[])
    if not isinstance(entries,list) or tuple(r.get('name') for r in entries)!=EXPECTED_DOCS:
        raise RuntimeError('Expected the exact 18-file public Performance corpus')
    docs=[]
    for r in entries:
        n=r['name'];p=root/'files'/n
        if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
            raise RuntimeError('Missing/changed JSON corpus fixture: '+n)
        docs.append({'name':n,'file':p,'bytes':r['bytes'],'sha256':r['sha256'],'stratum':'public_original'})
    return manifest,docs

def synthetic_build(out):
    """Deterministic exact-byte sizes; not represented as independent real documents."""
    folder=Path(out)/'synthetic101';folder.mkdir(exist_ok=True)
    sizes=(3584,4095,4096,4097,5120,6143,6144,6145,7167,7168,7169,
           8191,8192,8193,9216,10239,10240,10241,11264,12287,12288,12289,
           14335,14336,14337,16383,16384,16385,20480)
    docs=[]
    for family in ('ascii','escaped','dense'):
        for n in sizes:
            if family=='ascii':
                prefix='{"p":"';suffix='"}'
                s=prefix+('A'*(n-len(prefix)-len(suffix)))+suffix
            elif family=='escaped':
                prefix='{"p":"';suffix='"}'
                k=n-len(prefix)-len(suffix)
                s=prefix+('\\n'*(k//2))+('A'*(k%2))+suffix
            else:
                count=max(1,(n-24)//3)
                suffix='"}'
                prefix='{"v":['+(','.join(['0']*count))+'],"p":"'
                while len(prefix)+len(suffix)>n:
                    count-=1
                    prefix='{"v":['+(','.join(['0']*count))+'],"p":"'
                s=prefix+('A'*(n-len(prefix)-len(suffix)))+suffix
            raw=s.encode('utf8');p=folder/(family+'-'+str(n)+'.json')
            if len(raw)!=n:raise ValueError('Unexpected JSON length')
            json.loads(raw);p.write_bytes(raw)
            docs.append({'name':'synthetic/'+p.name,'file':p,'bytes':n,'sha256':sha(p),'stratum':'synthetic_boundary'})
    return docs

def derived_build(out, public_docs):
    """Reproducible *transforms* of public files. Not independent real documents.

    Reassemble contiguous child members of existing arrays/objects; do not
    invent or edit scalar values. The fixed source SHA ties each to the pinned
    public fixture, and the exact final bytes are recorded in inputs101.json.
    """
    folder=Path(out)/'derived101';folder.mkdir(exist_ok=True)
    docs=[]; encode=lambda v:json.dumps(v,ensure_ascii=True,separators=(',',':'),allow_nan=False).encode('utf8')
    targets=(6144,10240,14336)
    for source in public_docs:
        tree=json.loads(source['file'].read_text(encoding='utf8'))
        sequences=[]
        def walk(node,depth=0):
            if depth>3 or len(sequences)>=100:return
            if isinstance(node,(dict,list)):
                if len(node)>=3:sequences.append(node)
                items=list(node.values()) if isinstance(node,dict) else node
                if depth<3 and items:
                    for idx in sorted({0,1,len(items)//4,len(items)//2,3*len(items)//4,len(items)-1}):
                        if idx<len(items):walk(items[idx],depth+1)
        walk(tree)
        candidates=[];used=set()
        for sequence in sequences[:50]:
            n=len(sequence)
            if n<3:continue
            pairs=list(sequence.items()) if isinstance(sequence,dict) else sequence
            for fraction in (0,1/3,2/3):
                start=min(n-1,int(n*fraction))
                remaining=n-start
                if remaining<1:continue
                for desired in targets:
                    def snippet(count):
                        chunk=pairs[start:start+count]
                        return dict(chunk) if isinstance(sequence,dict) else chunk
                    lo,hi=1,remaining
                    while lo<hi:
                        mid=(lo+hi)//2
                        if len(encode(snippet(mid)))<desired:lo=mid+1
                        else:hi=mid
                    for count in (lo-1,lo):
                        if count<1:continue
                        raw=encode(snippet(count));size=len(raw)
                        if not 3500<=size<=17000:continue
                        digest=hashlib.sha256(raw).hexdigest()
                        if digest==source['sha256'] or digest in used:continue
                        used.add(digest)
                        candidates.append((abs(size-desired),digest,raw))
        candidates.sort(key=lambda t:(t[0],t[1]))
        selected=[]
        for score,digest,raw in candidates:
            if any(x[1]==digest for x in selected):continue
            selected.append((score,digest,raw))
            if len(selected)==3:break
        for idx,(_,digest,raw) in enumerate(selected):
            name='public_derived/'+source['name'].removesuffix('.json')+'-fragment'+str(idx)+'.json'
            p=folder/name.rsplit('/',1)[-1];p.write_bytes(raw)
            docs.append({'name':name,'file':p,'bytes':len(raw),'sha256':digest,
                         'stratum':'public_derived','derived_from':source['name'],
                         'source_sha256':source['sha256']})
    return docs

def build(a):
    src=Path(a.source).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if platform.machine()!=a.arch:raise RuntimeError('Build host is '+platform.machine()+' not '+a.arch)
    if shutil.disk_usage(out).free < 700*1024*1024:raise RuntimeError('Need 700MiB free for compilation')
    for f in ('src/simdjson.cpp','src/rvv/engines/engine_plan.h','include/simdjson.h','include/simdjson/simdjson_version.h'):
        if not (src/f).is_file():raise RuntimeError('Missing fork source '+f)
    if '5.0.3' not in (src/'include/simdjson/simdjson_version.h').read_text(errors='replace'):
        raise RuntimeError('Unexpected fork version; expected 5.0.3')
    if (out/'builds101.json').exists():raise RuntimeError('Existing Test101 builds cannot be overwritten')
    cflags=shlex.split(a.cxx_flags)
    if a.arch=='x86_64' and not any(s.startswith('--target=riscv64') for s in cflags):
        raise RuntimeError('EPCC cross-compiler needs explicit RISC-V target')
    upstream=out/'upstream-sources'/'OFFICIAL_504';upstream.parent.mkdir(exist_ok=True)
    run(['git','clone','--quiet','--depth','1','--branch',UPSTREAM_TAG,'https://github.com/simdjson/simdjson.git',upstream],timeout=300)
    if run(['git','-C',upstream,'rev-parse','HEAD'])!=UPSTREAM_SHA:raise RuntimeError('Official source tag commit mismatch')
    base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-march=rv64gcv','-mabi=lp64d','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
    bench=Path(__file__).with_name('test101_dom.cpp');builds={}
    for name in VARIANTS:
        if shutil.disk_usage(out).free<MIN_DISK:raise RuntimeError('Disk safety cap')
        fork=name.startswith('A2_');root=src if fork else upstream
        threshold={'A2_REF':4096,'A2_G8192':8192,'A2_G10240':10240,'A2_G12288':12288,'A2_G16384':16384}.get(name)
        extra=[] if not fork else ['-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0',
          '-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_EXPLORATION91=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0','-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE=0','-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE=0',
          '-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT=0','-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES='+str(threshold)]
        cmd=[a.cxx,*cflags,*base,*extra,'-I'+str(root/'include'),'-I'+str(root/'src')]
        obj=out/(name+'.o');exe=out/('test101_'+name)
        for label,args in (('compile',[*cmd,'-c',root/'src/simdjson.cpp','-o',obj]),
                           ('link',[*cmd,bench,obj,'-o',exe])):
            log=out/('build101_'+name+'_'+label+'.log')
            with log.open('w') as f:p=subprocess.run(list(map(str,args)),stdout=f,stderr=subprocess.STDOUT,timeout=900)
            if p.returncode:raise RuntimeError(name+' build failed: '+log.read_text(errors='replace')[-1600:])
        obj.unlink(missing_ok=True)
        hdr=exe.read_bytes()[:20]
        if hdr[:4]!=b'\x7fELF' or hdr[4]!=2 or int.from_bytes(hdr[18:20],'little')!=243:
            raise RuntimeError(name+' is not a 64-bit RISC-V ELF')
        exe.chmod(0o755)
        builds[name]={'backend':'rvv' if fork else 'fallback','sha256':sha(exe),'threshold':threshold,
                      'compiler':a.cxx,'compiler_flags':cflags,'flags':base+extra,'source_commit':UPSTREAM_SHA if not fork else None}
        print('TEST101 BUILD PASS',name,flush=True)
    save(out/'builds101.json',{'schema':1,'builds':builds,'source_fork_sha256':sha(src/'src/simdjson.cpp'),
          'source_plan_sha256':sha(src/'src/rvv/engines/engine_plan.h'),'harness_sha256':sha(bench),
          'official_tag':UPSTREAM_TAG,'official_commit':UPSTREAM_SHA})

def summary(rows, baseline='A2_REF', parent_by_derived=None):
    """Equal-weight geometric ratios; public-derived fragments are not independent.

    All strata remain separate. Where supplied, public-derived data additionally
    aggregate within each source public JSON before averaging over source files.
    """
    by=defaultdict(dict)
    for r in rows:by[(r['stratum'],r['round'],r['document'])][r['variant']]=float(r['gbps'])
    comparisons={}
    for stratum in ('public_original','public_derived','synthetic_boundary'):
        variants={}
        for variant in VARIANTS:
            if variant==baseline:continue
            doc_logs=defaultdict(list);complete_rounds=set()
            for (s,rnd,doc),vals in by.items():
                if s!=stratum or baseline not in vals or variant not in vals:continue
                ref=vals[baseline];cur=vals[variant]
                if not (ref>0 and cur>0):continue
                doc_logs[doc].append(math.log(cur/ref));complete_rounds.add(rnd)
            if not doc_logs:continue
            per_doc={d:statistics.mean(v) for d,v in doc_logs.items()}
            rec={'file_equal_geomean':math.exp(statistics.mean(per_doc.values())),
                 'file_equal_geomean_vs_A2':math.exp(statistics.mean(per_doc.values())),
                 'files':len(per_doc),'blocks':len(complete_rounds),
                 'per_file':{d:{'ratio':math.exp(x),'pairs':len(doc_logs[d])} for d,x in sorted(per_doc.items())}}
            if stratum=='public_derived' and parent_by_derived:
                parents=defaultdict(list)
                for doc,value in per_doc.items():
                    if doc in parent_by_derived:parents[parent_by_derived[doc]].append(value)
                if parents:
                    rec['source_equal_geomean']=math.exp(statistics.mean(statistics.mean(v) for v in parents.values()))
                    rec['independent_original_sources']=len(parents)
            variants[variant]=rec
        comparisons[stratum]=variants
    return {'schema':1,'baseline':baseline,
            'method':'Geometric paired per-file means; never pool strata or treat timing repeats as independent documents',
            'comparisons':comparisons,'rows':len(rows)}

def round_confidence(rows,rounds):
    """Approximate 95% intervals across full repeated rounds in each stratum."""
    grouped=defaultdict(dict)
    for r in rows:
        grouped[(r['stratum'],r['round'],r['document'])][r['variant']]=r
    result={}
    for stratum,expected in [(s,len({r['document'] for r in rows if r['stratum']==s})) for s in ('public_original','public_derived','synthetic_boundary')]:
        for variant in ('A2_G8192','A2_G10240','A2_G12288','A2_G16384'):
            rounds_log=defaultdict(list)
            for (s,rnd,doc),v in grouped.items():
                if s!=stratum or variant not in v or 'A2_REF' not in v:continue
                r=v['A2_REF'];c=v[variant]
                ref=math.sqrt(float(r['anchor_before_gbps'])*float(r['anchor_after_gbps']))
                cur=float(c['gbps'])
                if ref>0 and cur>0:rounds_log[rnd].append(math.log(cur/ref))
            means=[statistics.mean(vals) for k,vals in sorted(rounds_log.items()) if len(vals)==expected]
            if len(means)>=8:
                mean=statistics.mean(means);se=statistics.stdev(means)/math.sqrt(len(means))
                result[stratum+'/'+variant]={'ratio':math.exp(mean),'rounds':len(means),
                   'half_width_pct':100*(math.exp(1.96*se)-1)}
    return result

def package(out,status,rows,manifest):
    out=Path(out)
    try:
        inputs=json.loads((out/'inputs101.json').read_text())
        parents={v['name']:v['derived_from'] for v in inputs.get('files',[]) if v.get('derived_from')}
    except (OSError,ValueError,KeyError):parents={}
    result=summary(rows,parent_by_derived=parents)
    result['comparisons_vs_A2_G8192']=summary(rows,baseline='A2_G8192',parent_by_derived=parents)['comparisons']
    drift=[abs(float(r['anchor_drift_pct'])) for r in rows if r['variant']=='A2_REF']
    result['anchor_drift']={'median_abs_pct':statistics.median(drift) if drift else None,
        'fraction_over_10pct':sum(x>10 for x in drift)/len(drift) if drift else None}
    result['round_confidence_per_stratum']=status.get('confidence',{})
    save(out/'summary101.json',result)
    lines=['# Test 101 — Adaptive public JSON + targeted dispatch boundaries','',
           f"State: **{status['state']}**; measurement rows: **{len(rows)}**.",
           f"Stop reason: {status.get('stop_reason',status.get('reason','normal/adaptive'))}.",'',
           '## Provenance and interpretation','',
           '- Public data: **18 byte-identical simdjson-data examples**, pinned '+CORPUS_COMMIT+'.',
           '- Derived data: **structural fragments reconstructed from pinned public files**, not independent real-world documents.',
           '- Synthetic data: **87 deterministic exact-size boundary fixtures**, clearly separate.',
           '- Public original, public-derived, and synthetic categories are NEVER pooled into one ranking.',
           '- Official baseline is **simdjson 5.0.4 fallback**; experimental A2 uses **RVV**.',
           '- Previous EPCC Test99 v5.0.3 and 5.0.4 compiled to identical ELF SHA-256; Test101 avoids a redundant v5.0.3 binary.',
           '- Timing repeats are not an independent-document holdout.',
           '- Interval estimates use repeated rounds, not separate JSON documents as independent timing observations.','',
           '## Paired geometric mean DOM throughput ratios versus A2_REF','',
           '| Workload (separate) | Variant | Geomean ratio | Documents |',
           '|---|---|---:|---:|']
    for workload,entries in result['comparisons'].items():
        for name,rec in entries.items():
            lines.append(f"| {workload} | {name} | {rec['file_equal_geomean_vs_A2']:.5f}× | {rec['files']} |")
    lines+=['', '## Direct comparison versus 8 KiB (A2_G8192)', '',
            '| Workload (separate) | Variant | Geomean vs 8 KiB | Documents |',
            '|---|---|---:|---:|']
    for workload,entries in result['comparisons_vs_A2_G8192'].items():
        for name,rec in entries.items():
            lines.append(f"| {workload} | {name} | {rec['file_equal_geomean']:.5f}× | {rec['files']} |")
    lines+=['', 'Values above one are faster. The source-equal geomean for derived fragments is in summary101.json.',
            '', 'Ratios above 1 indicate a faster candidate than the named reference.', '',
            '## Sequential confidence checks by separate stratum','',
            '| Candidate | Ratio | Approx. 95% half-width | Complete rounds |','|---|---:|---:|---:|']
    for name,rec in result.get('round_confidence_per_stratum',{}).items():
        lines.append(f"| {name} | {rec['ratio']:.5f}× | ±{rec['half_width_pct']:.3f}% | {rec['rounds']} |")
    lines+=['','## Run health','',
            f"- Reference before/after median absolute drift: {result['anchor_drift']['median_abs_pct']} percent.",
            f"- Reference comparisons exceeding 10% drift: {result['anchor_drift']['fraction_over_10pct']} fraction.",
            '- A candidate is not promoted automatically; examine per-document results and machine noise.','',
            'Raw rows: `results101.csv`; machine/build/provenance: JSON files in this archive.','']
    (out/'REPORT_101.md').write_text('\n'.join(lines),encoding='utf8')
    names=['builds101.json','machine101.json','status101.json','results101.csv',
           'summary101.json','REPORT_101.md','corpus_manifest101.json','inputs101.json']
    available=[n for n in names if (out/n).is_file()]
    if status.get('state') not in ('completed','failed','stopped'):return
    for log in ('studio101-build.log','slurm101-exit.json','slurm101-runtime.log','studio101-cloudv.log'):
        if (out/log).is_file():available.append(log)
    tmp=out/'test101_results.zip.partial'
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in available:z.write(out/name,name)
    with zipfile.ZipFile(tmp) as z:
        if z.testzip():raise RuntimeError('Result archive CRC error')
    os.replace(tmp,out/'test101_results.zip')
    (out/'test101_results.sha256').write_text(sha(out/'test101_results.zip')+'  test101_results.zip\n')

def inspect(a):
    man,docs=corpus_verify(a.corpus)
    status={'state':'preflight','phase':'corpus','validated':False,'rows':0,'groups':0,'started_utc':utc(),
            'corpus_id':CORPUS_ID,'machine':platform.node(),'max_seconds':a.max_seconds}
    save(Path(a.output)/'status101.json',status)
    save(Path(a.output)/'corpus_manifest101.json',man)
    return man,docs,status

def execute(a):
    if platform.machine()!='riscv64':raise RuntimeError('Benchmark must execute on RISC-V')
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(out).free<MIN_DISK:raise RuntimeError('Disk safety cap')
    if (out/'results101.csv').exists():raise RuntimeError('Existing measurements cannot be overwritten')
    interrupted=[False]
    signal.signal(signal.SIGTERM,lambda *_: interrupted.__setitem__(0,True))
    signal.signal(signal.SIGINT,lambda *_: interrupted.__setitem__(0,True))
    rows=[];man=None;status={'state':'preflight','phase':'initial','validated':False,'rows':0,'started_utc':utc(),
                              'machine':platform.node(),'max_seconds':a.max_seconds}
    save(out/'status101.json',status)
    try:
        man,docs,status=inspect(a)
        b=json.loads((out/'builds101.json').read_text())['builds']
        if set(b)!=set(VARIANTS):raise RuntimeError('Missing variant metadata')
        for name in VARIANTS:
            path=out/('test101_'+name)
            if not path.is_file() or sha(path)!=b[name]['sha256']:raise RuntimeError('Binary SHA256 mismatch '+name)
        synth=synthetic_build(out)
        derived=derived_build(out,docs)
        if len(derived)<6:raise RuntimeError('Insufficient public-derived fixtures: '+str(len(derived)))
        all_docs=docs+derived+synth
        save(out/'inputs101.json',{'source':'pinned_public_plus_generated_stress','public_count':len(docs),
          'derived_count':len(derived),'synthetic_count':len(synth),'files':[{'name':r['name'],'bytes':r['bytes'],'sha256':r['sha256'],'stratum':r['stratum'], 'derived_from':r.get('derived_from'),'source_sha256':r.get('source_sha256')} for r in all_docs]})
        save(out/'machine101.json',{'arch':platform.machine(),'hostname':platform.node(),
          'cpu_affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else [],'utc':utc()})
        prefix=['taskset','-c',str(min(os.sched_getaffinity(0)))] if hasattr(os,'sched_getaffinity') and shutil.which('taskset') else []
        def call(name,action,path,iters=None):
            cmd=[*prefix,out/('test101_'+name),b[name]['backend'],action,path]
            if iters is not None:cmd.append(iters)
            return run(cmd,timeout=240)
        for rec in all_docs:
            checks=[call(name,'check',rec['file']) for name in VARIANTS]
            if not all(x.startswith('CHECK_OK ') for x in checks) or len(set(checks))!=1:
                raise RuntimeError('DOM equivalence check failed for '+rec['name']+': '+str(checks))
        status.update(state='running',phase='measure',validated=True,rows=0,groups=0,updated_utc=utc())
        save(out/'status101.json',status)
        # Calibrate one timed sample per document to get useful inner-loop timing,
        # particularly for tiny JSON. Exe startup is outside the C++ timer.
        iters_by_doc={}
        for rec in all_docs:
            guess=max(2,min(500,2000000//rec['bytes']))
            probe=call('A2_REF','bench',rec['file'],guess).split()
            if len(probe)!=4 or probe[0]!='BENCH_OK':raise RuntimeError('Calibration output invalid: '+rec['name'])
            measured=float(probe[1]);est_sec=rec['bytes']*guess/(measured*1e9)
            want=int(math.ceil(guess*0.035/max(est_sec,0.0000001)))
            iters_by_doc[rec['name']]=max(2,min(1000,want))
        start=time.monotonic();deadline=start+a.max_seconds;blocks=0;rounds=0;stable_checks=0;last_snapshot=time.monotonic()
        rng=random.Random(20261017)
        # Substrata intentionally kept separate in analysis, not weighted 18:57.
        with (out/'results101.csv').open('w',encoding='utf8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();f.flush()
            while time.monotonic()<deadline-180 and not interrupted[0]:
                docs_order=list(all_docs);rng.shuffle(docs_order)
                round_complete=True
                for rec in docs_order:
                    if time.monotonic()>=deadline-180 or interrupted[0]:
                        round_complete=False;break
                    before=call('A2_REF','bench',rec['file'],iters_by_doc[rec['name']])
                    shuffled=list(VARIANTS);rng.shuffle(shuffled)
                    readings={}
                    iters=iters_by_doc[rec['name']]
                    for name in shuffled:readings[name]=call(name,'bench',rec['file'],iters)
                    after=call('A2_REF','bench',rec['file'],iters)
                    def gb(s):
                        t=s.split()
                        if len(t)!=4 or t[0]!='BENCH_OK' or int(t[2])!=rec['bytes'] or int(t[3])!=iters:
                            raise RuntimeError('Invalid benchmark output '+str(s))
                        v=float(t[1])
                        if not (0<v<500 and math.isfinite(v)):raise RuntimeError('Nonfinite GB/s')
                        return v
                    lo=gb(before);hi=gb(after);drift=100*(hi/lo-1)
                    block=[{'utc':utc(),'stratum':rec['stratum'],'round':rounds,'block':blocks,'document':rec['name'],
                      'bytes':rec['bytes'],'document_sha256':rec['sha256'],'variant':n,
                      'backend':b[n]['backend'],'gbps':gb(readings[n]),'iterations':iters,
                      'anchor_before_gbps':lo,'anchor_after_gbps':hi,'anchor_drift_pct':drift} for n in shuffled]
                    for row in block:w.writerow(row);rows.append(row)
                    f.flush()
                    blocks+=1
                    if blocks%10==0:
                        status.update(rows=len(rows),groups=blocks,elapsed_seconds=int(time.monotonic()-start),updated_utc=utc(),phase=status.get('phase','measure'))
                        save(out/'status101.json',status)
                    if time.monotonic()-last_snapshot>300:
                        status.update(rows=len(rows),groups=blocks,elapsed_seconds=int(time.monotonic()-start),updated_utc=utc())
                        save(out/'status101.json',status);last_snapshot=time.monotonic()
                if round_complete:rounds+=1
                elapsed=time.monotonic()-start
                if elapsed>=a.min_seconds and rounds>=8:
                    # Round-level uncertainty, not thousands of JSON documents treated
                    # as statistically independent samples.
                    status['phase']='confirmation'
                    ci=round_confidence(rows,rounds)
                    status['confidence']=ci
                    bounded=len(ci)==12 and all(v['half_width_pct']<=0.65 for v in ci.values())
                    drift=[abs(float(row['anchor_drift_pct'])) for row in rows if row['variant']=='A2_REF']
                    quiet=bool(drift and statistics.median(drift)<=2.0 and sum(v>10.0 for v in drift)/len(drift)<=0.025)
                    bounded=bounded and quiet
                    stable_checks=stable_checks+1 if bounded else 0
                    # Require 3 consecutive complete rounds with precise estimates
                    # AND at least a dedicated 20-minute confirmation period.
                    if stable_checks>=3 and elapsed>=a.min_seconds+a.confirm_seconds:break
            status.update(state='stopped' if interrupted[0] else 'completed',phase='finish',rows=len(rows),groups=blocks,
                          stop_reason='signal' if interrupted[0] else 'precision_reached' if stable_checks>=3 else 'max_budget',
                          elapsed_seconds=int(time.monotonic()-start),updated_utc=utc())
    except Exception as e:
        status.update(state='failed',phase='finish',reason=str(e),rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
        raise
    finally:
        save(out/'status101.json',status)
        package(out,status,rows,man)
    print('TEST101_DONE',status['state'],status['rows'],flush=True)

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=('build','preflight','run'))
    p.add_argument('--source',default='');p.add_argument('--output',required=True);p.add_argument('--corpus',default='')
    p.add_argument('--arch',default='x86_64');p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--min-seconds',type=int,default=3600);p.add_argument('--confirm-seconds',type=int,default=1800)
    p.add_argument('--max-seconds',type=int,default=21600)
    a=p.parse_args()
    if a.action=='build':build(a)
    elif a.action=='preflight':
        m,docs=corpus_verify(a.corpus)
        with tempfile.TemporaryDirectory(prefix='test101-preflight-') as tmp:
            derived=derived_build(tmp,docs)
            if len(derived)<6:raise RuntimeError('Preflight: fewer than six public-derived JSON fragments')
            synthetic=synthetic_build(tmp)
            if len(synthetic)!=87:raise RuntimeError('Synthetic fixture generation incomplete')
        print('PREFLIGHT_OK',m['corpus_id'],m['upstream_commit'],len(docs),len(derived),len(synthetic))
    else:
        if not (600<=a.min_seconds<=a.max_seconds<=25200 and 300<=a.confirm_seconds<a.max_seconds):p.error('Invalid adaptive timing bounds')
        execute(a)
if __name__=='__main__':main()
