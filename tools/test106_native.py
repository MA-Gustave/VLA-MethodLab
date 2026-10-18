#!/usr/bin/env python3
"""Test 106: isolated VectorPath release validation with paired Stage1/Stage2/DOM measurements.

No optimization is promoted by this program; MethodLab engine remains original and pinned. Original public, new synthetic and
independently seeded confirmation cases are never pooled as independent documents.
"""
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,math,os,pathlib,platform,random,shlex,shutil,signal,statistics,subprocess,sys,tempfile,time,zipfile
from collections import defaultdict
from pathlib import Path

VARIANTS=('OFFICIAL_504','A2_ORIGINAL','VP_STABLE','VP_SIMPLE','VP_NL4')
EXPECTED_RC_PACKAGE_SHA='513dbf6ea2241d469ade18a354e18a77303d66ce9d6794fb8595ee59e01f0388'
EXPECTED_FORK_SHA='fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16'
EXPECTED_PLAN_SHA='7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e'
UPSTREAM_SHA='3b0b2b53aaffb46208817821dce2cd47a5e6bb2a'
CORPUS_COMMIT='4197c425e857f0ec38e89822fdd0bd9ea21f4daf'
CORPUS_ID='simdjson-data-4197c425-test98'
CONFORMANCE_COMMIT='1ef36fa01286573e846ac449e8683f8833c5b26a'
CONFORMANCE_ID='jsontestsuite-rfc8259-'+CONFORMANCE_COMMIT[:12]
PUBLIC=('apache_builds.json','canada.json','citm_catalog.json','github_events.json','google_maps_api_compact_response.json','google_maps_api_response.json','gsoc-2018.json','instruments.json','marine_ik.json','mesh.json','mesh.pretty.json','numbers.json','twitter_api_compact_response.json','twitter_api_response.json','twitterescaped.json','twitter.json','twitter_timeline.json','update-center.json')
METRICS=('dom_gbps','stage1_gbps','stage2_gbps')
FIELDS=('utc','phase','round','group','stratum','document','family','requested_density_pct','actual_density_pct','placement','backslashes_per_probe','bytes','sha256','variant','backend','iterations','dom_gbps','stage1_gbps','stage2_gbps','anchor_before_dom_gbps','anchor_after_dom_gbps','anchor_drift_pct')
FILES=('conformance106.json','conformance106.csv','conformance_manifest106.json','status106.json','builds106.json','machine106.json','inputs106.json','corpus_manifest106.json','results106.csv','summary106.json','public_gate106.json','REPORT_106.md','studio106-build.log','studio106-cloudv.log','slurm106-exit.json','slurm106-runtime.log')

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

def conformance_verify(root):
    """Validate entire *official*, pinned JSONTestSuite with no JSON rewriting.

    Valid y_ files are eligible for performance ONLY if all four C++
    implementations accept the exact same bytes with matching canonical DOM.
    n_ and i_ files are never used as performance data.
    """
    root=Path(root).resolve(); manifest=root/'manifest.json'
    if not manifest.is_file():raise RuntimeError('Missing pinned JSONTestSuite; prepare/sync Conformance suite in Studio')
    m=json.loads(manifest.read_text('utf8'))
    if m.get('corpus_id')!=CONFORMANCE_ID or m.get('upstream_commit')!=CONFORMANCE_COMMIT or m.get('schema')!=1:
        raise RuntimeError('JSONTestSuite provenance mismatch')
    records=m.get('files',[])
    if not 200<=len(records)<=2000:raise RuntimeError('Unexpected JSONTestSuite manifest count')
    accepted=[];seen=set()
    for rec in records:
        name=rec['name'];path=Path(name)
        if path.is_absolute() or '..' in path.parts or len(path.parts)!=2 or path.parts[0] not in ('test_parsing','test_transform') or name in seen or not name.endswith('.json'):
            raise RuntimeError('Unsafe / duplicate JSONTestSuite filename: '+str(name))
        seen.add(name)
        expected={'y':'accept','n':'reject','i':'implementation'}.get(path.name[:1]) if path.parts[0]=='test_parsing' else 'transform'
        if expected!=rec.get('expected'):raise RuntimeError('JSONTestSuite expected-class mismatch '+name)
        p=root/'files'/name
        if not p.is_file() or p.stat().st_size!=rec['bytes'] or sha(p)!=rec['sha256']:
            raise RuntimeError('JSONTestSuite hash mismatch '+name)
        if expected=='accept':
            accepted.append({'name':'jsonsuite/'+name,'file':p,'bytes':rec['bytes'],'sha256':rec['sha256'],
                             'stratum':'jsonsuite_valid','family':'official_y', 'requested_density_pct':None,
                             'actual_density_pct':100*p.read_bytes().count(b'\\')/max(1,rec['bytes']),
                             'placement':'official','backslashes_per_probe':None})
    if not accepted:raise RuntimeError('No official y_ JSONs in pinned suite')
    return m,records,accepted

def synthetic_build(root,phase):
    """Deterministic independent-seed stress cases; valid exact-size JSON.

    Densities reflect raw backslash bytes, NOT decoded escape frequency. The
    unicode \\uXXXX token limits maximum realizable density to ~16.7%; actual
    density, never the target, is recorded in the dataset metadata.
    """
    folder=Path(root)/('fixtures106-'+phase);folder.mkdir(parents=True,exist_ok=True)
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

def verify_candidate_package(original,package):
    original=Path(original).resolve();package=Path(package)
    if not package.is_file():raise RuntimeError('Pinned VectorPath candidate patch is missing')
    if sha(package)!=EXPECTED_RC_PACKAGE_SHA:raise RuntimeError('VectorPath release candidate archive SHA-256 mismatch')
    with zipfile.ZipFile(package) as z:
        if z.testzip():raise RuntimeError('Candidate patch failed ZIP CRC')
        meta=json.loads(z.read('manifest.json'))
        if meta.get('schema')!=1 or meta.get('base_src_simdjson_sha256')!=EXPECTED_FORK_SHA:
            raise RuntimeError('Candidate provenance mismatch')
        if set(z.namelist())!={x['path'] for x in meta['changed']}|{'manifest.json'}:
            raise RuntimeError('Unexpected candidate patch files')
        for x in meta['changed']:
            rel=Path(x['path'])
            if rel.is_absolute() or '..' in rel.parts:raise RuntimeError('Unsafe candidate path')
            if sha(original/rel)!=x['original_sha256'] or hashlib.sha256(z.read(x['path'])).hexdigest()!=x['new_sha256']:
                raise RuntimeError('VectorPath candidate base or payload hash differs: '+x['path'])
    return True

def prepare_candidate(original,output,package):
    """Create an immutable release-candidate source COPY; verify both sides.

    Never alter original MethodLab engine or touch any 100-105 source/binary.
    """
    original=Path(original).resolve();output=Path(output).resolve();package=Path(package).resolve()
    if not package.is_file():raise RuntimeError('Missing pinned VectorPath release candidate patch ZIP')
    if sha(package)!=EXPECTED_RC_PACKAGE_SHA:raise RuntimeError('Candidate package SHA-256 mismatch')
    if output.exists():raise RuntimeError('Candidate source folder already exists; use new run ID')
    with zipfile.ZipFile(package) as z:
        if z.testzip():raise RuntimeError('Candidate package CRC failure')
        manifest=json.loads(z.read('manifest.json'))
        names=set(z.namelist())
        expected={r['path'] for r in manifest['changed']}|{'manifest.json'}
        if names!=expected or manifest.get('schema')!=1:raise RuntimeError('Unexpected candidate package contents')
        if manifest.get('base_src_simdjson_sha256')!=EXPECTED_FORK_SHA:
            raise RuntimeError('Candidate was built for a different historical fork')
        for item in manifest['changed']:
            relative=Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts:raise RuntimeError('Invalid RC path')
            source=original/relative
            if not source.is_file() or sha(source)!=item['original_sha256']:
                raise RuntimeError('Candidate patch base SHA-256 mismatch: '+str(relative))
            if hashlib.sha256(z.read(item['path'])).hexdigest()!=item['new_sha256']:
                raise RuntimeError('Candidate source SHA-256 mismatch: '+str(relative))
        shutil.copytree(original/'src',output/'src',symlinks=False)
        shutil.copytree(original/'include',output/'include',symlinks=False)
        for item in manifest['changed']:
            target=output/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(z.read(item['path']))
            if sha(target)!=item['new_sha256']:raise RuntimeError('Copy verification failed: '+item['path'])
    return {'manifest':manifest,'sha256':sha(package),'source':str(output)}

def build(a):
    src=Path(a.source).resolve();out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if platform.machine()!=a.arch:raise RuntimeError('Build host arch mismatch: '+platform.machine())
    verify_source(src)
    if (out/'builds106.json').exists():raise RuntimeError('Refusing to overwrite existing Test106 builds')
    if shutil.disk_usage(out).free<750*1024**2:raise RuntimeError('Need 750 MiB free before compilation')
    package=Path(a.candidate_package).resolve()
    candidate=prepare_candidate(src,out/'vp-release-candidate-sources',package)
    official=out/'upstream-504'
    run(['git','clone','--quiet','--depth','1','--branch','v5.0.4','https://github.com/simdjson/simdjson.git',official],timeout=300)
    if run(['git','-C',official,'rev-parse','HEAD'])!=UPSTREAM_SHA:raise RuntimeError('Official simdjson v5.0.4 pinned commit mismatch')
    flags=shlex.split(a.cxx_flags)
    if a.arch=='x86_64' and not any(x.startswith('--target=riscv64') for x in flags):raise RuntimeError('EPCC requires an actual RISC-V cross target')
    base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-march=rv64gcv','-mabi=lp64d','-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
    rvv=['-DSIMDJSON_IMPLEMENTATION_RVV=1','-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0']
    old=['-DSIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2','-DSIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES=16384',
         '-DSIMDJSON_RVV_EXPLORATION91=0','-DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0',
         '-DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0','-DSIMDJSON_RVV_ENABLE_PACKED_ESCAPE=0',
         '-DSIMDJSON_RVV_ENABLE_PACKED_QUOTE=0','-DSIMDJSON_RVV_ENABLE_PACKED_SHIFT=0']
    bench=Path(__file__).with_name('test106_split.cpp')
    build_rows={}
    for v in VARIANTS:
        if shutil.disk_usage(out).free<170*1024**2:raise RuntimeError('Disk safety below 170 MiB')
        root=official if v=='OFFICIAL_504' else src if v=='A2_ORIGINAL' else out/'vp-release-candidate-sources'
        opts=[] if v=='OFFICIAL_504' else rvv+(old if v=='A2_ORIGINAL' else [])
        if v in ('VP_SIMPLE','VP_NL4'):
            opts+=['-DSIMDJSON_VECTORPATH_STAGE2_SIMPLE_RUN=1']
            if v=='VP_NL4':opts+=['-DSIMDJSON_VECTORPATH_STAGE2_NL4=1']
        cmd=[a.cxx,*flags,*base,*opts,'-I'+str(root/'include'),'-I'+str(root/'src')]
        exe=out/('test106_'+v);obj=out/(v+'.o')
        for label,args in [('compile',[*cmd,'-c',root/'src/simdjson.cpp','-o',obj]),
                           ('link',[*cmd,bench,obj,'-o',exe])]:
            log=out/('build106_'+v+'_'+label+'.log')
            with log.open('w') as logf:
                p=subprocess.run([str(x) for x in args],stdout=logf,stderr=subprocess.STDOUT,timeout=1200)
            if p.returncode:raise RuntimeError(v+' '+label+' failed: '+log.read_text(errors='replace')[-1500:])
        obj.unlink(missing_ok=True)
        header=exe.read_bytes()[:20]
        if header[:4]!=b'\x7fELF' or header[4]!=2 or int.from_bytes(header[18:20],'little')!=243:
            raise RuntimeError('Expected genuine RISC-V ELF64 binary: '+v)
        exe.chmod(0o755)
        build_rows[v]={'sha256':sha(exe),'backend':'fallback' if v=='OFFICIAL_504' else 'rvv',
                'compiler':a.cxx,'compiler_flags':flags,'compile_definitions':base+opts,
                'source':'upstream504' if v=='OFFICIAL_504' else 'pinned_old_a2' if v=='A2_ORIGINAL' else 'pinned_vectorpath_rc',
                'src_simdjson_sha256':sha(root/'src/simdjson.cpp'),
                'src_stage2_sha256':sha(root/'src/generic/stage2/stringparsing.h'),
                'engine_plan_sha256':sha(root/'src/rvv/engines/engine_plan.h') if v!='OFFICIAL_504' else None}
        print('TEST106 BUILD PASS',v,flush=True)
    save(out/'builds106.json',{'schema':1,'builds':build_rows,'candidate':candidate,
      'original_src_sha256':EXPECTED_FORK_SHA,'original_plan_sha256':EXPECTED_PLAN_SHA,
      'harness_sha256':sha(bench),'official_commit':UPSTREAM_SHA})

def calculate(rows,breakdown='family'):
    by_group=defaultdict(dict)
    for r in rows:by_group[(r['phase'],r['stratum'],r['document'],r['round'])][r['variant']]=r
    logs=defaultdict(list)
    for (phase,stratum,document,rnd),group in by_group.items():
        if set(group)!=set(VARIANTS):continue
        meta=group['A2_ORIGINAL'];family=meta['family']
        if breakdown=='density':
            if not stratum.startswith('synthetic_') or family=='crossover':continue
            family=family+'/requested_'+str(meta['requested_density_pct'])+'pct'
        elif breakdown=='crossover':
            if family!='crossover':continue
            family='crossover/count_'+str(meta['backslashes_per_probe'])+'/'+str(meta['placement'])
        key='/'.join([phase,stratum,family])
        for cand in ('A2_ORIGINAL','VP_STABLE','VP_SIMPLE','VP_NL4'):
            for ref in ('OFFICIAL_504','A2_ORIGINAL','VP_STABLE'):
                if cand==ref or cand=='A2_ORIGINAL' and ref!='OFFICIAL_504':continue
                for metric in METRICS:
                    a=float(group[cand][metric]);b=float(group[ref][metric])
                    if a>0 and b>0:logs[(key,cand,ref,metric,document)].append(math.log(a/b))
    out={};bydoc=defaultdict(dict)
    for (key,cand,ref,metric,doc),times in logs.items():bydoc[(key,cand,ref,metric)][doc]=statistics.mean(times)
    for (key,cand,ref,metric),docs in sorted(bydoc.items()):
        out.setdefault(key,{}).setdefault(cand,{}).setdefault(ref,{})[metric]={
            'geomean_ratio':math.exp(statistics.mean(docs.values())),'documents':len(docs)}
    return out

def public_release_gate(rows):
    """Per-document paired throughput evidence, never pooled with tiny JSON or stress.

    A local machine gate is not cross-machine shipment approval.
    """
    values=defaultdict(dict)
    for r in rows:
        if r.get('phase')=='confirm' and r.get('stratum')=='public_original':
            values[(r['round'],r['document'])][r['variant']]=r
    samples=defaultdict(list)
    for (_,doc),pair in values.items():
        if set(pair)!=set(VARIANTS):continue
        for cand in ('VP_STABLE','VP_SIMPLE','VP_NL4'):
            for ref in ('A2_ORIGINAL','OFFICIAL_504'):
                x=float(pair[cand]['dom_gbps']);y=float(pair[ref]['dom_gbps'])
                if x>0 and y>0:samples[(cand,ref,doc)].append(math.log(x/y))
    perdoc={};
    for (cand,ref,doc),logs in samples.items():
        perdoc.setdefault(cand,{}).setdefault(ref,{})[doc]=math.exp(statistics.mean(logs))
    verdicts={}
    for cand in ('VP_STABLE','VP_SIMPLE','VP_NL4'):
        docs=perdoc.get(cand,{}).get('A2_ORIGINAL',{})
        if len(docs)!=18:
            verdicts[cand]={'state':'insufficient_evidence','documents':len(docs)}
            continue
        gm=math.exp(statistics.mean(math.log(x) for x in docs.values()))
        worst=min(docs.values())
        verdicts[cand]={'state':'local_machine_pass' if gm>=0.995 and worst>=0.98 else 'local_machine_regression',
              'documents':len(docs),'geomean_vs_original_a2':gm,
              'worst_file_ratio':worst,
              'worst_file':min(docs,key=docs.get)}
    return {'schema':1,'criteria':{'public_geomean_min':0.995,'individual_min':0.98,'documents':18},
       'scope':'one_machine_only; any global shipping decision requires both targets and correctness',
       'variants':verdicts,'per_document_ratios':perdoc}

def package(out,status,rows):
    out=Path(out)
    summary={'schema':1,'method':'paired log throughput ratios; equal weight per input document; separate phase/stratum/machine',
             'comparisons':'VectorPath stable / original pinned A2, opt-in variants / stable A2, and all / official fallback',
             'workloads':calculate(rows),'density_sweep':calculate(rows,'density'),
             'crossover':calculate(rows,'crossover'),'row_count':len(rows)}
    gate=public_release_gate(rows)
    save(out/'public_gate106.json',gate)
    save(out/'summary106.json',summary)
    report=['# Test 106 — VectorPath Release Candidate A/B Validation', '',
      f"State: **{status.get('state')}**; rows: **{len(rows)}**; phase: **{status.get('phase')}**.", '',
      '## Official JSONTestSuite conformance', '',
      'See `conformance106.json` and `conformance106.csv` (all y_/n_/i_/transform cases; i_ unscored).',
      'Conformance failures are **not** silently accepted: `production_promotion_eligible` remains false when any expected-label or cross-variant discrepancy is detected.',
      'Failed expected labels and cross-variant differences are reported, NEVER concealed by excluding from performance.',
      'Official y_ performance results are reported separately from original public simdjson-data and synthetic probes.',
      '- Small y_ fixtures have substantial timing overhead; use primarily for correctness, not headline speedup.',
      '', '## Variant definitions','',
      '- `OFFICIAL_504`: unmodified simdjson v5.0.4, fallback backend.',
      '- `A2_ORIGINAL`: original pinned MethodLab RVV A2 16 KiB packed-off reference.',
      '- `VP_STABLE`: VectorPath shipping candidate A2 defaults 16 KiB, Stage 2 original.',
      '- `VP_SIMPLE`: experimental VectorPath SIMPLE_RUN; `VP_NL4`: NL4 burst on top.',
      '- The RC source is reconstructed from a SHA-256-verified overlay in a separate run directory; MethodLab engine is unchanged.', '',
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
    report+=['','## Same-machine public release gate (confirmation only)','',
             '| Candidate | Geomean / original A2 | Worst public file | Local machine gate |',
             '|---|---:|---:|---|']
    for cand,row in gate['variants'].items():
        report.append('| '+cand+' | '+(f"{row['geomean_vs_original_a2']:.5f}x" if 'geomean_vs_original_a2' in row else 'n/a')+' | '+(f"{row['worst_file_ratio']:.4f}x" if 'worst_file_ratio' in row else 'n/a')+' | '+row['state']+' |')
    report+=['','## Release promotion decision — NOT automatic','',
             'Use JSONTestSuite conformance, actual per-machine gains and exact binary SHA256 from builds106.json.','',
             'Investigate any original public JSON below 0.98x versus original A2; require public geometric mean >=0.995 on both machines.',
             'Do not globally enable opt-in Stage 2 paths without independent real escaped workload evidence.','',
             '## Density sweep and crossover','',
             'The exact density and crossover breakdown is in `summary106.json`; per-document public ratios and same-machine gate are in `public_gate106.json`.','',
             '## Promotion gate','',
             'No automatic promotion. Require correctness parity, independent confirmation on both machines,',
             'non-regression on public JSON, and a measurable Stage 2/DOM gain on dense escapes.','']
    (out/'REPORT_106.md').write_text('\n'.join(report),encoding='utf8')
    archive=out/'test106_results.zip';temp=out/'test106_results.zip.partial'
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
        for name in FILES:
            f=out/name
            if f.is_file() and f.stat().st_size<480_000_000:z.write(f,name)
    with zipfile.ZipFile(temp) as z:
        if z.testzip():raise RuntimeError('ZIP CRC check failed')
    os.replace(temp,archive)
    (out/'test106_results.sha256').write_text(sha(archive)+'  test106_results.zip\n')

def measure(a):
    if platform.machine()!='riscv64':raise RuntimeError('Benchmark execution requires riscv64')
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    if (out/'results106.csv').exists():raise RuntimeError('Existing results are immutable; refusing to overwrite')
    if shutil.disk_usage(out).free<150*1024**2:raise RuntimeError('Disk free space too low')
    interrupted=[False]
    signal.signal(signal.SIGTERM,lambda *_:interrupted.__setitem__(0,True))
    signal.signal(signal.SIGINT,lambda *_:interrupted.__setitem__(0,True))
    rows=[];start_wall=time.monotonic();status={'state':'preflight','phase':'native-preflight','validated':False,
       'rows':0,'groups':0,'started_utc':utc(),'machine':platform.node(),'max_seconds':a.max_seconds}
    save(out/'status106.json',status)
    try:
        manifest,public=corpus_verify(a.corpus)
        save(out/'corpus_manifest106.json',manifest)
        builds=json.loads((out/'builds106.json').read_text())['builds']
        if set(builds)!=set(VARIANTS):raise RuntimeError('Missing build metadata')
        for name in VARIANTS:
            exe=out/('test106_'+name)
            if not exe.is_file() or sha(exe)!=builds[name]['sha256']:raise RuntimeError('Binary SHA-256 mismatch '+name)
        # Different random seeds between explore and confirm, created before measurement.
        suite, suite_records, suite_accepted=conformance_verify(a.conformance)
        save(out/'conformance_manifest106.json',suite)
        synthetic={phase:[x for x in synthetic_build(out,phase)
                   if x['family'] in ('newline','mixed','unicode') and x['requested_density_pct'] in (0,10,25,50)]
                   for phase in ('explore','confirm')}
        save(out/'machine106.json',{'machine':platform.node(),'arch':platform.machine(),
            'cpu_affinity':sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else [],
            'compiler':builds['A2_ORIGINAL']['compiler'],'utc':utc()})
        aff=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else []
        prefix=['taskset','-c',str(aff[0])] if aff and shutil.which('taskset') else []
        def call(v,mode,document,iters=None):
            argv=[*prefix,out/('test106_'+v),builds[v]['backend'],mode,document]
            if iters is not None:argv.append(iters)
            return run(argv,timeout=180)
        # Evaluate EVERY official y_/n_/i_ and transform file with all variants.
        # No corruption of raw invalid UTF8; no Python JSON decoding of input.
        conf_rows=[];verified_y=[];class_counts=defaultdict(int)
        for rec in suite_records:
            src=Path(a.conformance)/'files'/rec['name']
            result={}
            for v in VARIANTS:
                argv=[*prefix,out/('test106_'+v),builds[v]['backend'],'check',src]
                proc=subprocess.run([str(z) for z in argv],capture_output=True,text=True,timeout=12)
                if proc.returncode==0 and proc.stdout.startswith('CHECK_OK '):
                    result[v]=('accept',proc.stdout.strip())
                elif proc.returncode==22:result[v]=('reject','')
                else:raise RuntimeError('Conformance checker failed '+rec['name']+' '+v+' rc='+str(proc.returncode)+' '+proc.stderr[-300:])
            expected=rec['expected'];vals=set(v[0] for v in result.values())
            parity=len({result[v] for v in VARIANTS})==1
            normative=expected in ('accept','reject')
            expectation_pass=not normative or vals=={expected}
            row={'name':rec['name'],'bytes':rec['bytes'],'sha256':rec['sha256'],'expected':expected,
                 'parity':parity,'expectation_pass':expectation_pass}
            for v in VARIANTS:row[v]=result[v][0]
            conf_rows.append(row);class_counts[expected]+=1
            if expected=='accept' and parity and expectation_pass and rec['bytes']>0:
                verified_y.append(next(x for x in suite_accepted if x['name']=='jsonsuite/'+rec['name']))
        with (out/'conformance106.csv').open('w',newline='',encoding='utf8') as c:
            columns=['name','bytes','sha256','expected','parity','expectation_pass',*VARIANTS]
            writer=csv.DictWriter(c,fieldnames=columns);writer.writeheader();writer.writerows(conf_rows)
        conformance_summary={'schema':1,'upstream_commit':CONFORMANCE_COMMIT,'class_counts':dict(class_counts),
          'checks':len(conf_rows),'expected_mismatches':sum(not r['expectation_pass'] for r in conf_rows),
          'cross_variant_disagreements':sum(not r['parity'] for r in conf_rows),
          'valid_selected_for_perf':len(verified_y),'valid_declared':len(suite_accepted),
          'promotion_eligible':all(r['parity'] and r['expectation_pass'] for r in conf_rows)}
        save(out/'conformance106.json',conformance_summary)
        if not conformance_summary['promotion_eligible']:
            raise RuntimeError('Native JSONTestSuite found expected-label or cross-variant correctness disagreements; refusing benchmarking')
        if not verified_y:raise RuntimeError('No y_ fixtures passed correctness validation')
        docs_by_phase={phase:public+verified_y+synthetic[phase] for phase in ('explore','confirm')}
        save(out/'inputs106.json',{'schema':1,'corpus_commit':CORPUS_COMMIT,'conformance_commit':CONFORMANCE_COMMIT,
             'public_count':len(public),'valid_jsonsuite_count':len(verified_y),
             'synthetic_explore_count':len(synthetic['explore']),'synthetic_confirm_count':len(synthetic['confirm']),
             'method':'official original public and verified y_ accepted files + separately labeled stress controls',
             'files':[{k:d[k] for k in ('name','bytes','sha256','stratum','family','requested_density_pct',
                                       'actual_density_pct','placement','backslashes_per_probe')}
                      for phase in ('explore','confirm') for d in docs_by_phase[phase]]})
        for phase,docs in docs_by_phase.items():
            for d in docs:
                if phase=='confirm' and d['stratum'] in ('public_original','jsonsuite_valid'):continue
                check=[call(v,'check',d['file']) for v in VARIANTS]
                if len(set(check))!=1 or not all(s.startswith('CHECK_OK ') for s in check):
                    raise RuntimeError('DOM correctness mismatch: '+d['name'])
        status.update(state='running',phase='explore',validated=True,
          conformance_disagreements=conformance_summary['cross_variant_disagreements'],
          conformance_expected_mismatches=conformance_summary['expected_mismatches'],
          production_promotion_eligible=conformance_summary['promotion_eligible'],updated_utc=utc())
        save(out/'status106.json',status)
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
            speed=parse(call('A2_ORIGINAL','split',d['file'],guess),d,guess)[0]
            seconds=d['bytes']*guess/(speed*1e9)
            want=int(guess*0.020/max(seconds,1e-7))
            iterations[(d['family'],d['bytes'])]=max(3,min(1000,want))
        deadline=start_wall+a.max_seconds;cutover=start_wall+a.explore_seconds
        round_id=0;group_id=0;last_status=time.monotonic()
        rng=random.Random(20261018)
        with (out/'results106.csv').open('w',newline='',encoding='utf8') as f:
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
                    before=parse(call('A2_ORIGINAL','split',d['file'],iters),d,iters)
                    names=list(VARIANTS);rng.shuffle(names)
                    readings={v:parse(call(v,'split',d['file'],iters),d,iters) for v in names}
                    after=parse(call('A2_ORIGINAL','split',d['file'],iters),d,iters)
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
                        save(out/'status106.json',status);last_status=time.monotonic()
                round_id+=1
                if shutil.disk_usage(out).free<80*1024**2:raise RuntimeError('Emergency disk safety stop (<80 MiB)')
            status.update(state='stopped' if interrupted[0] else 'completed',phase='finish',
              rows=len(rows),groups=group_id,rounds=round_id,validated=(len(rows)>0 and any(r['phase']=='explore' for r in rows) and any(r['phase']=='confirm' for r in rows) and conformance_summary['promotion_eligible']),
              stop_reason='signal' if interrupted[0] else 'release_validation_budget',
              elapsed_seconds=int(time.monotonic()-start_wall),updated_utc=utc())
    except Exception as e:
        status.update(state='failed',phase='finish',reason=str(e),rows=len(rows),groups=len(rows)//len(VARIANTS),updated_utc=utc())
        raise
    finally:
        save(out/'status106.json',status)
        package(out,status,rows)
    print('TEST106_DONE',status['state'],status['rows'],flush=True)

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('build','preflight','run'))
    p.add_argument('--source',default='');p.add_argument('--candidate-package',default='');p.add_argument('--conformance',default='');p.add_argument('--corpus',default='');p.add_argument('--output',required=True)
    p.add_argument('--arch',default='x86_64');p.add_argument('--cxx',default='g++');p.add_argument('--cxx-flags',default='')
    p.add_argument('--max-seconds',type=int,default=7200)
    p.add_argument('--explore-seconds',type=int,default=3600)
    a=p.parse_args(argv)
    if a.action=='build':build(a)
    elif a.action=='preflight':
        manifest,docs=corpus_verify(a.corpus)
        conf,records,valid=conformance_verify(a.conformance)
        verify_source(a.source) if a.source else None
        if not a.candidate_package:raise RuntimeError('Test106 preflight needs an independent pinned candidate package')
        verify_candidate_package(a.source,a.candidate_package)
        with tempfile.TemporaryDirectory(prefix='test106-preflight-') as tmp:
            d=synthetic_build(tmp,'explore')
            e=synthetic_build(tmp,'confirm')
            if len(d)!=206 or len(e)!=206:raise RuntimeError('Unexpected synthetic probe count: '+str((len(d),len(e))))
            if set(x['sha256'] for x in d) & set(x['sha256'] for x in e):raise RuntimeError('Confirmation reuses a synthetic fixture byte-for-byte')
        print('TEST106_PREFLIGHT_OK',len(docs),len(records),len(valid),len(d),len(e),manifest['upstream_commit'])
    else:
        if not (3600<=a.explore_seconds<a.max_seconds<=14400 and a.max_seconds-a.explore_seconds>=3600):
            p.error('Invalid release validation phase budgets')
        measure(a)
if __name__=='__main__':main()
