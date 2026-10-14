#!/usr/bin/env python3
"""Test 94: 1h per-machine RVV 1.0 A2 optimisation confirmation.

Runs only on native RISC-V; EPCC frontend is cross-build ONLY.
Reference implementation is code from engine/scripts/rvv/explore91; no modification to parser.
"""
from __future__ import annotations
import argparse, csv, datetime, hashlib, json, math, os, platform, random, shlex, shutil, statistics, subprocess, sys, time, zipfile
from collections import defaultdict
from pathlib import Path

VARIANTS = {
 'A2_O3': {'defines':{'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2', 'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'}, 'extra':[]},
 'A2_LTO': {'defines':{'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2', 'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'}, 'extra':['-flto']},
 'packed_plain': {'defines':{'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2','SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'1','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'1','SIMDJSON_RVV_EXPLORATION91':'0'}, 'extra':[]},
}
FIELDNAMES=['timestamp_utc','phase','group','corpus','family','layout','bytes','json_sha256','iterations','variant','dom_all_gbps','stage1_gbps','stage2_gbps','seconds']
ANCHORS=[('ascii',65536),('dense',65536),('escaped',65536),('utf8',65536),('unicode_escape',65536),('floats',65536),('many_keys',1048576),('nested',1048576),('long_strings',1048576),('boolnull',65536),('integers',65536),('utf8',8388608),('long_strings',8388608)]
VERSION='94.1'

def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(path,obj):
    p=Path(path); tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,indent=2,sort_keys=True,default=str)+'\n',encoding='utf8');tmp.replace(p)
def run(cmd, timeout=300, env=None, cwd=None, capture=True):
    return subprocess.run([str(v) for v in cmd],cwd=cwd,env=env,check=True, text=True,stdout=subprocess.PIPE if capture else None,stderr=subprocess.STDOUT,timeout=timeout)
def getmodules(source):
    root=Path(source).resolve()/ 'scripts/rvv/explore91'
    if not (root/'support90.py').exists():raise RuntimeError('Source engine missing scripts/rvv/explore91/support90.py')
    sys.path.insert(0,str(root))
    import support90, harness, design
    return support90,harness,design

def specs():
    s={'machine':platform.node(),'arch':platform.machine(),'uname':platform.uname()._asdict(), 'time_utc':utc(),'python':sys.version.split()[0], 'slurm':{k:os.environ.get(k) for k in ('SLURM_JOB_ID','SLURM_JOB_NODELIST','SLURM_JOB_PARTITION','SLURM_CPUS_PER_TASK') if os.environ.get(k)}}
    for name,cmd in [('lscpu',['lscpu']),('mem',['free','-h']),('gcc',['g++','--version'])]:
        try:s[name]=run(cmd,timeout=10).stdout[:16000]
        except Exception as e:s[name]=f'unavailable: {e}'
    for name in ('/proc/cpuinfo','/proc/meminfo','/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor'):
        try:s[name]=Path(name).read_text(errors='replace')[:14000]
        except OSError:pass
    try:s['affinity_cpus']=sorted(os.sched_getaffinity(0))
    except AttributeError:s['affinity_cpus']=[]
    return s

def verify_source(source):
    req=['include/simdjson.h','src/simdjson.cpp','src/rvv/stage1.h','src/rvv/engines/engine_plan.h']
    missing=[x for x in req if not (Path(source)/x).is_file()]
    if missing:raise RuntimeError('Missing engine source: '+', '.join(missing))
    h=(Path(source)/'include/simdjson/simdjson_version.h').read_text(errors='replace')
    if '5.0.3' not in h:raise RuntimeError('Source is not verified simdjson 5.0.3')

def prepare(a):
    root=Path(a.output).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    src=Path(a.source).expanduser().resolve();verify_source(src)
    support,harness,_=getmodules(src)
    if shutil.disk_usage(root).free<200*1048576:raise RuntimeError('Less than 200 MiB free disk')
    harness_code=harness.source(support.BENCH_CPP)
    hpp=root/'test94_benchmark.cpp';hpp.write_text(harness_code,encoding='utf8')
    builds={};compiler=a.cxx;compiler_flags=shlex.split(getattr(a,"cxx_flags", ""))
    for name,settings in VARIANTS.items():
        flags=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-mabi=lp64d','-march=rv64gcv',
            '-DSIMDJSON_IMPLEMENTATION_FALLBACK=1','-DSIMDJSON_IMPLEMENTATION_RVV=1',
            '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0']+[f'-D{k}={v}' for k,v in sorted(settings['defines'].items())]+settings['extra']
        obj=root/(name+'.o');binary=root/('test94_'+name)
        cmd1=[compiler,*compiler_flags,*flags,'-I'+str(src/'include'),'-I'+str(src/'src'),'-c',str(src/'src/simdjson.cpp'),'-o',str(obj)]
        cmd2=[compiler,*compiler_flags,*flags,'-I'+str(src/'include'),'-I'+str(src/'src'),str(hpp),str(obj),'-o',str(binary)]
        record={'name':name,'compiler':compiler,'compiler_flags':compiler_flags,'flags':flags,'started_utc':utc(),'result':'not_built'}
        for step,cmd in [('compile',cmd1),('link',cmd2)]:
            log=root/(f'build_{name}_{step}.log')
            try:
                with log.open('w',encoding='utf8') as f:
                    p=subprocess.run([str(v) for v in cmd],cwd=root,stdout=f,stderr=subprocess.STDOUT,timeout=300,check=False)
                if p.returncode:raise RuntimeError(f'{step} failed rc={p.returncode}; {log.read_text(errors="replace")[-1500:]}')
            except Exception as e:
                record.update(result='FAIL',error=str(e),failed_step=step)
                if name=='A2_O3':write_json(root/'builds.json',dict(builds={**builds,name:record}));raise
                print('OPTIONAL VARIANT SKIPPED:',name,str(e)[-200:],flush=True)
                break
        else:
            binary.chmod(0o755);record.update(result='PASS',sha256=sha(binary),file=binary.name)
            obj.unlink(missing_ok=True)
            print('BUILT',name,record['sha256'][:16],flush=True)
        builds[name]=record
        write_json(root/'builds.json',dict(schema=1,version=VERSION,source=str(src),harness_sha256=sha(hpp),builds=builds,build_machine=specs(),timestamp_utc=utc()))
    probe_src=src/'scripts/rvv/perf/probe_vlen.cpp'
    if probe_src.exists():
        try:
            run([compiler,*compiler_flags,'-O2','-march=rv64gcv','-mabi=lp64d',probe_src,'-o',root/'test94_probe_vlen'],timeout=90)
        except Exception as e:print('Optional VLEN probe compilation unavailable:',e,flush=True)
    if not (root/'test94_A2_O3').is_file():raise RuntimeError('Mandatory A2 binary missing')
    return root

def validation_files(root):
    valid=['{}','[]','true','false','null','0','{"a":1}','[1,2,3]','{"x":"é😀"}','"quoted\\\""','{"nested":{"x":[null,false,true]}}','"\\uD83D\\uDE3A"']
    invalid=['{','[','[1,]','{"x":}','{"x":1,}','[NaN]','{"x":01}','{"x":+1}','[true false]','"unterminated','{"x":1}junk','{"a":1 "b":2}']
    (root/'valid.jsonl').write_text('\n'.join(valid)+'\n',encoding='utf8')
    (root/'invalid.jsonl').write_text('\n'.join(invalid)+'\n',encoding='utf8')

def snapshot_report(root,rows,machine,budgets):
    # Exclude partial groups; paired and per-family comparisons only.
    grp=defaultdict(dict)
    for row in rows:grp[row['group']][row['variant']]=row
    considered=[v for v in grp.values() if 'A2_O3' in v]
    d={}
    for phase in ('train','holdout'):
        d[phase]={}
        for label in ('A2_LTO','packed_plain'):
            paired=[(g['A2_O3'],g[label]) for g in considered if label in g and g[label]['phase']==phase]
            if not paired:continue
            ratios={metric:[float(c[metric])/float(b[metric]) for b,c in paired] for metric in ('dom_all_gbps','stage1_gbps','stage2_gbps')}
            d[phase][label]={'groups':len(paired), **{k+'_ratio_gm':round(math.exp(statistics.mean(map(math.log,v))),6) for k,v in ratios.items()}}
    lines=['# Test 94 — RVV one-hour machine benchmark','',f'- Machine: `{machine["machine"]}`','- Architecture: `'+machine['arch']+'`',
           '- Campaign budget: '+str(budgets['seconds'])+' seconds (native run, or build+run if `all`)','- Hardware VLEN (bits): '+str(machine.get('vlen_bits','unknown')),
           '- Rows: '+str(len(rows)),'- Finished: '+utc(),'', '## Paired throughput vs dedicated A2 -O3',
           '', '| Phase | Variant | Matched groups | DOM/A2 | Stage1/A2 | Stage2/A2 |', '|---|---|---:|---:|---:|---:|']
    for phase,labels in d.items():
        for variant,stat in labels.items():lines.append('| '+phase+' | '+variant+' | '+str(stat['groups'])+' | '+f'{stat["dom_all_gbps_ratio_gm"]:.3f}x | {stat["stage1_gbps_ratio_gm"]:.3f}x | {stat["stage2_gbps_ratio_gm"]:.3f}x |')
    lines+=['', '## Absolute DOM throughput (GB/s, geometric mean over observed corpus groups)', '', '| Phase | Variant | N | GB/s |','|---|---|---:|---:|']
    complete_groups={key for key,value in grp.items() if set(VARIANTS)==set(value)}
    for phase in ('train','holdout'):
        for variant in VARIANTS:
            values=[float(r['dom_all_gbps']) for r in rows if r['variant']==variant and r['phase']==phase and r['group'] in complete_groups]
            if values:lines.append(f'| {phase} | {variant} | {len(values)} | {math.exp(statistics.mean(map(math.log,values))):.6f} |')
    lines+=['','## Guardrails','','- A2 is the primary reference, not experimental packed/research code.',
            '- Identical corpora and iteration counts within each completed group, randomized run order.',
            '- Warm DOM throughput; Stage1 and Stage2 are independent diagnostics.',
            '- Across machines, use identical family/layout/size subsets and paired per-machine ratios, not aggregate speedup.',
            '- The fastest configuration is only provisional until the independent holdout supports it.',
            '- This benchmark does not deploy production binaries.','']
    (root/'REPORT_94.md').write_text('\n'.join(lines),encoding='utf8')
    write_json(root/'summary94.json',dict(schema=1,machine=machine,phases=d,rows=len(rows),budget=budgets))

def execute(a, budget_from_start=None):
    src=Path(a.source).expanduser().resolve();verify_source(src)
    support,_,design=getmodules(src)
    if platform.machine()!='riscv64':raise RuntimeError('REFUSED: benchmark must run on native riscv64, not EPCC x86 login')
    budget_start=budget_from_start or time.monotonic()
    deadline=budget_start+int(a.seconds)
    root=Path(a.output).expanduser().resolve();root.mkdir(parents=True,exist_ok=True)
    if (root/'results94.csv').exists() or (root/'status94.json').exists():raise RuntimeError('Output contains an earlier run; choose NEW --output')
    if shutil.disk_usage(root).free<200*1048576:raise RuntimeError('Insufficient free disk (<200 MiB)')
    builds=json.loads((root/'builds.json').read_text())['builds']
    avail=[]
    for label in VARIANTS:
        rec=builds.get(label,{})
        file=root/('test94_'+label)
        if rec.get('result')=='PASS':
            if not file.is_file() or sha(file)!=rec.get('sha256'):raise RuntimeError('SHA256 mismatch '+label)
            avail.append(label)
    if 'A2_O3' not in avail:raise RuntimeError('A2 baseline not available')
    machine=specs();machine['test94_version']=VERSION
    try:
        if (root/'test94_probe_vlen').exists():machine['vlen_bits']=int(run([root/'test94_probe_vlen'],timeout=10).stdout.strip())
    except Exception as e:machine['vlen_bits']=None;machine['vlen_probe_error']=str(e)
    if machine.get('vlen_bits') and machine['vlen_bits']<128:raise RuntimeError('VLEN <128 not appropriate for RVV 1.0 test')
    write_json(root/'machine94.json',machine)
    core=a.core
    if core is None:
        affinity=machine.get('affinity_cpus') or []
        core=affinity[0] if affinity else None
    if core is not None and machine.get('affinity_cpus') and core not in machine['affinity_cpus']:
        raise RuntimeError(f'CPU {core} not in Slurm/cgroup affinity {machine["affinity_cpus"]}')
    prefix=['taskset','-c',str(core)] if core is not None and shutil.which('taskset') else []
    def bench_cmd(label,mode,*arguments,timeout=120):
        left=deadline-time.monotonic()-1
        if left<=0:raise TimeoutError('Test94 one-hour wall-clock budget reached')
        return run([*prefix,root/('test94_'+label),'rvv',mode,*arguments],timeout=min(timeout,max(0.5,left))).stdout
    validation_files(root)
    for label in avail:
        out=bench_cmd(label,'validate',root/'valid.jsonl',root/'invalid.jsonl')
        if 'RVV_VALIDATION_OK backend=rvv' not in out:raise RuntimeError('Validation marker missing for '+label)
    specs_base=design.corpus_specs(8)
    anchors=[]
    for i,(kind,size) in enumerate(ANCHORS):
        match=next((s for s in specs_base if s['kinds']==[kind] and s['target']==size and s['layout']=='interleaved'),None)
        if not match:raise RuntimeError(f'Expected corpus unavailable: {kind} {size}')
        anchors.append(match)
    # Add region transition stress; make sure both platforms run identical data.
    region=next(s for s in specs_base if s['layout']=='regions16384' and s['target']==1048576 and len(s['kinds'])>=3 and 'utf8' in s['kinds'])
    anchors.append(region)
    cutoff=budget_start+int(a.seconds)*.80
    status={'schema':1,'campaign':'Test94','started_utc':utc(),'seconds':int(a.seconds),'phase':'correctness','machine':machine['machine'],'variants':avail,'core':core,'rows':0,'state':'running'}
    write_json(root/'status94.json',status)
    rows=[];groups=0;randomizer=random.Random(2026101394)
    with (root/'results94.csv').open('w',newline='',encoding='utf8') as csvfile:
        w=csv.DictWriter(csvfile,fieldnames=FIELDNAMES);w.writeheader();csvfile.flush()
        trial=0;previous_phase='train';phase_trial=0
        try:
            while time.monotonic()<deadline:
                phase='train' if time.monotonic()<cutoff else 'holdout'
                # Independent phase-specific trial counters make holdout bytes match
                # across machines even when their training measurement rates differ.
                if phase!=previous_phase:phase_trial=0;previous_phase=phase
                template=anchors[phase_trial%len(anchors)]
                sp=dict(template, id=f'{phase[0].upper()}{phase_trial:06d}',role=phase,
                        seed=20261013940000+phase_trial*9973+(900000000 if phase=='holdout' else 0))
                doc=root/'active_94.json'
                try:
                    info=design.generate(sp,doc,lambda:None)
                    if time.monotonic()>=deadline-15:break
                    for label in avail:
                        output=bench_cmd(label,'check',doc,timeout=60)
                        if 'DOM_AGREES' not in output:raise RuntimeError('DOM agreement failure: '+label)
                    # Keep all variant measurements under one group. Incomplete groups are reported but excluded from ratios.
                    iters=max(1,min(128,1048576//info['bytes']))
                    order=avail.copy();randomizer.shuffle(order)
                    group=f'G{groups:06d}'
                    for label in order:
                        if time.monotonic()>=deadline-5:break
                        out=bench_cmd(label,'split',doc,iters,timeout=120)
                        dom,s1,s2,sec,_,_,n,size=support.parse_split_output(out)
                        if size!=info['bytes'] or n!=iters:raise RuntimeError('Echo mismatch')
                        row=dict(timestamp_utc=utc(),phase=phase,group=group,corpus=sp['id'],family='+'.join(sp['kinds']),layout=sp['layout'],bytes=size,iterations=n,
                                 variant=label,json_sha256=info['sha256'],dom_all_gbps=dom,stage1_gbps=s1,stage2_gbps=s2,seconds=sec)
                        w.writerow(row);rows.append(row);csvfile.flush()
                    groups+=1
                    if groups%10==0 or time.monotonic()>=cutoff:
                        status.update(rows=len(rows),groups=groups,phase=phase,last_update_utc=utc());write_json(root/'status94.json',status)
                        snapshot_report(root,rows,machine,dict(seconds=a.seconds))
                finally:doc.unlink(missing_ok=True)
                trial+=1;phase_trial+=1
        except TimeoutError:
            if time.monotonic()>=deadline-3:
                status.update(state='completed',reason='Test94 one-hour wall-clock budget reached')
            else:
                status.update(state='failed',reason='Unexpected timeout before budget expired')
                raise
        except subprocess.TimeoutExpired:
            if time.monotonic()>=deadline-3:
                status.update(state='completed',reason='Test94 one-hour wall-clock budget reached during command')
            else:
                status.update(state='failed',reason='Command timeout before budget expired')
                raise
        except KeyboardInterrupt:
            status.update(state='stopped',reason='CTRL+C');raise
        except Exception as e:
            status.update(state='failed',reason=str(e));raise
        finally:
            status.update(rows=len(rows),groups=groups,phase='finish',last_update_utc=utc())
            if status['state']=='running':status['state']='completed' if time.monotonic()>=deadline-30 else 'stopped'
            write_json(root/'status94.json',status)
            snapshot_report(root,rows,machine,dict(seconds=a.seconds))
            # archive can be transferred back as a single bundle; never includes credentials or source.
            zpath=root/'test94_results.zip'
            with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
                for name in ['builds.json','machine94.json','status94.json','results94.csv','summary94.json','REPORT_94.md']:
                    if (root/name).is_file():z.write(root/name,arcname=name)
            (root/'test94_results.sha256').write_text(sha(zpath)+'  test94_results.zip\n',encoding='utf8')
    print(status,flush=True)
    return 0 if rows else 1

def compare(args):
    packs=[]
    for path in args:
        p=Path(path)
        if p.suffix=='.zip':
            with zipfile.ZipFile(p) as z:
                x=json.loads(z.read('summary94.json'));rows=list(csv.DictReader(z.read('results94.csv').decode().splitlines()))
        else:
            x=json.loads((p/'summary94.json').read_text());rows=list(csv.DictReader((p/'results94.csv').open()))
        packs.append((x,rows))
    lines=['# Test 94 — Cross-machine comparison','','**Different hardware is not normalized by raw GB/s.** Compare same JSON family/layout/size and per-machine A2 ratios.', '',
           '| Machine | Arch | VLEN | Holdout A2 LTO/A2 | Holdout Packed/A2 |', '|---|---|---:|---:|---:|']
    for x,rows in packs:
        m=x['machine'];h=x.get('phases',{}).get('holdout',{})
        def rat(label):
            v=h.get(label,{}).get('dom_all_gbps_ratio_gm');return f'{v:.3f}x' if v else '—'
        lines.append(f'| {m["machine"]} | {m["arch"]} | {m.get("vlen_bits","?")} | {rat("A2_LTO")} | {rat("packed_plain")} |')
    lines+=['','## Absolute A2 DOM throughput: only common family/layout/size groups','','| Family / layout / bytes | '+' | '.join(x['machine']['machine'] for x,_ in packs)+' |', '|---|'+'---:|'*len(packs)]
    tables=[]
    for x,rows in packs:
        by=defaultdict(list)
        for r in rows:
            if r['variant']=='A2_O3' and r['phase']=='holdout':
                key=(r['family'],r['layout'],int(r['bytes']),r['json_sha256'])
                by[key].append(float(r['dom_all_gbps']))
        tables.append({k:math.exp(statistics.mean(map(math.log,v))) for k,v in by.items()} )
    commons=set.intersection(*(set(t) for t in tables)) if tables else set()
    for k in sorted(commons):lines.append('| '+f'{k[0]} / {k[1]} / {k[2]} / {k[3][:12]}'+' | '+' | '.join(f'{tab[k]:.5f}' for tab in tables)+' |')
    output=Path('TEST94_COMPARISON.md');output.write_text('\n'.join(lines)+'\n',encoding='utf8');print('Created',output.resolve())

def main(argv=None):
    ap=argparse.ArgumentParser(description='1h RVV native A2 optimisation benchmark (Cloud-V / EPCC Slurm)')
    ap.add_argument('action',choices=['build-only','run-only','all','compare'])
    ap.add_argument('inputs',nargs='*',help='Results ZIPs for compare')
    ap.add_argument('--source',default='engine',help='Project engine directory')
    ap.add_argument('--output',default='test94_output',help='NEW run directory (or build directory for run-only)')
    ap.add_argument('--seconds',type=int,default=3600,help='Native wall-clock budget, default 3600')
    ap.add_argument('--core',type=int,default=None,help='Default first available CPU in affinity mask')
    ap.add_argument('--cxx',default='g++',help='C++ compiler (EPCC uses probed Clang RVV 1.0)')
    ap.add_argument('--cxx-flags',default='',help='Compiler target/sysroot options, parsed without a shell')
    a=ap.parse_args(argv)
    if a.action=='compare':
        if len(a.inputs)!=2:ap.error('compare requires exactly two ZIP or result directories')
        compare(a.inputs);return 0
    if not 30<=a.seconds<=3600:ap.error('seconds must be 30..3600')
    if a.action=='all' and platform.machine()!='riscv64':ap.error('all mode requires a native RISC-V node; EPCC frontend uses build-only')
    start=time.monotonic()
    if a.action in ('all','build-only'):prepare(a)
    if a.action in ('all','run-only'):return execute(a,budget_from_start=start if a.action=='all' else None)
    return 0
if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception as e:print('TEST94 ERROR:',e,file=sys.stderr);raise SystemExit(2)
