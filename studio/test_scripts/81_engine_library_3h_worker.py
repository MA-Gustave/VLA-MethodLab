#!/usr/bin/env python3
"""Three-hour fixed-grid RVV Engine Library exploration, direct GCC / DOM-only.

No CMake, CPM, benchmark framework, external experimental strategy, sudo or cleanup
outside this run. Every experiment is determined before launch; only hard-coded
conservative early abandonment is allowed. Three hours includes compilation.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import statistics
import subprocess
import time
import zipfile

GIB=1024**3
MAX_HOURS=3.0
WORK_CAP=2*GIB
FREE_FLOOR=200*1024**2
BUILD_START_FLOOR=FREE_FLOOR
SNAPSHOT_LIMIT=12*1024**2
RUN_FILES=('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json')
RESULT_FIELDS=('timestamp','phase','variant','defines','corpus','bytes','parse_iterations','trial',
               'dom_all_gbps','stage1_gbps','stage2_gbps','all_cpb','stage1_cpb','stage2_cpb',
               'elapsed_seconds','method')
RANK_FIELDS=('variant','metric','paired_n','median_ratio','geomean_ratio','mad_ratio')
EARLY_ABORT_DOM_RATIO=.65
EARLY_ABORT_MIN_CORPORA=3
UPSTREAM_SHA='bf89ddd00ef5fcb6a7f20611ea8853d258b67249'
UPSTREAM_URL='https://github.com/simdjson/simdjson.git'

# Standalone measurement harness. Built from the exact pinned source tree with
# src/simdjson.cpp and the same flags; it does NOT pull in CMake dependencies.
# DOM throughput only. No synthetic Stage1/Stage2 numbers are produced.
BENCH_CPP=r'''#include "simdjson.h"
#include <algorithm>
#include <chrono>
#include <fstream>
#include <iostream>
#include <iterator>
#include <string>
#include <cstdlib>

using namespace simdjson;
static int select_backend(const std::string& name) {
  const implementation *chosen=get_available_implementations()[name];
  if (!chosen || !chosen->supported_by_runtime_system()) {
    std::cerr << "Unavailable RVV backend: " << name << "\n";
    return 3;
  }
  get_active_implementation()=chosen;
  if (get_active_implementation()->name()!=name) return 4;
  return 0;
}
static bool parse_ok(dom::parser& parser, const std::string& doc) {
  return parser.parse(doc).error()==SUCCESS;
}
static bool parse_ok(dom::parser& parser, const padded_string& doc) {
  return parser.parse(doc).error()==SUCCESS;
}
int main(int argc,char**argv) {
  if(argc<3) { std::cerr<<"usage: bench <rvv|rvv_vls> <selftest|bench> [json] [iters]\n";return 2; }
  const std::string backend=argv[1],mode=argv[2];
  if(int rc=select_backend(backend)) return rc;
  dom::parser parser;
  if(mode=="selftest") {
    const char* valid[]={
      R"({"number":42,"values":[1,2,3],"flag":true})",
      R"([{"text":"hello","escaped":"\\\""},{"unicode":"\u00e9"}])",
      R"({"nested":{"a":{"b":null}},"empty":[]})",
      R"({"long":"abcdefghijklmnopqrstuvwxyz","n":-123456789.125})",
      u8R"({"real_utf8":"héllo 😺 世界"})",
      R"([true,false,null,0,-9.25,1e30,"abc"])"
    };
    const char* invalid[]={R"({"truncated":)",R"([1,2,])",R"({"a":1,"b"})"};
    for(const char* p:valid) if(!parse_ok(parser,std::string(p))) {std::cerr<<"Valid JSON rejected: "<<p<<"\n";return 20;}
    for(const char* p:invalid) if(parse_ok(parser,std::string(p))) {std::cerr<<"Invalid JSON accepted: "<<p<<"\n";return 21;}
    std::cout<<"RVV_SMOKE_OK backend="<<backend<<" valid=6 invalid=3\n";
    return 0;
  }
  if(mode!="bench" || argc!=5) return 2;
  simdjson::padded_string doc;
  const simdjson::error_code load_error=simdjson::padded_string::load(argv[3]).get(doc);
  if(load_error != SUCCESS || doc.size()==0) {std::cerr<<"JSON input unavailable or empty\n";return 5;}
  char*end=nullptr;
  const long iterations=std::strtol(argv[4],&end,10);
  if(!end || *end || iterations<1 || iterations>1000) return 6;
  // Correctness is a hard gate BEFORE producing any performance rows.
  if(!parse_ok(parser,doc)) {std::cerr<<"Corpus rejected by backend: "<<argv[3]<<"\n";return 22;}
  for(int warm=0;warm<3;warm++) if(!parse_ok(parser,doc))return 23;
  double rates[3]={};double durations[3]={};
  for(int rep=0;rep<3;rep++) {
    auto start=std::chrono::steady_clock::now();
    for(long i=0;i<iterations;i++) {
      if(!parse_ok(parser,doc)) {std::cerr<<"Corrupt parse during timing\n";return 24;}
    }
    auto stop=std::chrono::steady_clock::now();
    durations[rep]=std::chrono::duration<double>(stop-start).count();
    if(durations[rep]<=0)return 25;
    rates[rep]=double(doc.size())*double(iterations)/durations[rep]/1.e9;
  }
  std::sort(rates,rates+3);
  std::sort(durations,durations+3);
  std::cout.precision(12);
  std::cout << "DOM_RESULT " << rates[1] << " " << durations[1] << " " << iterations << " " << doc.size() << "\n";
  return 0;
}
'''


def now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def atomic_text(path,data):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w',encoding='utf8') as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def atomic_json(path,data):atomic_text(path,json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+'\n')

def write_csv(path,rows,fields):
    p=Path(path);tmp=p.with_name(p.name+'.tmp')
    with tmp.open('w',newline='',encoding='utf8') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
        f.flush();os.fsync(f.fileno())
    os.replace(tmp,p)

def read_tail(path,limit=9500):
    p=Path(path)
    if not p.is_file():return ''
    with p.open('rb') as f:
        f.seek(0,os.SEEK_END);f.seek(max(0,f.tell()-limit))
        return f.read().decode('utf8','replace')[-limit:]

def extract_errors(log):
    lines=log.splitlines();results=[]
    for i,line in enumerate(lines):
        if re.search(r'(^|\s)(fatal error:|error:|FAILED:|undefined reference)',line,re.I):
            results.append('\n'.join(lines[max(i-1,0):i+2])[:850])
            if len(results)==12:break
    return results

def catalog(_unused=None):
    base=[('E00_historical',{'SIMDJSON_RVV_ENGINE_LIBRARY':'0'}),
      ('E01_adaptive',{'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':'0'})]
    for n,label in [(2,'dense'),(3,'numeric'),(4,'text'),(5,'escaped'),(6,'unicode_escape'),
                    (7,'utf8'),(8,'balanced'),(9,'mask_writer'),(10,'packed_escape'),
                    (11,'packed_quote_shift'),(12,'string_fastpath_only')]:
        base.append((f'E{n:02d}_{label}',{'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':str(n)}))
    base.extend([
      ('E13_stage2_prefetch',{'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':'0',
                             'SIMDJSON_RVV_STAGE2_PREFETCH':'1'}),
      ('E14_packed_disabled',{'SIMDJSON_RVV_ENGINE_LIBRARY':'1','SIMDJSON_RVV_FORCE_PLAN':'0',
         'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'})])
    reference={'SIMDJSON_RVV_ENGINE_LIBRARY':'0','SIMDJSON_RVV_SPARSE_INDEX_THRESHOLD':'8',
      'SIMDJSON_RVV_SPARSE_ESCAPE_THRESHOLD':'8','SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0',
      'SIMDJSON_RVV_ENABLE_PACKED_ESCAPE':'0','SIMDJSON_RVV_ENABLE_PACKED_QUOTE':'0',
      'SIMDJSON_RVV_ENABLE_PACKED_SHIFT':'0'}
    return ([('upstream_vls256',{},'rvv_vls','vls'),
             ('sparse8_escape8_reference',reference,'rvv','vla')]
            + [(tag,defines,'rvv','vla') for tag,defines in base])

def should_abandon(entries):
    distinct={name for name,ratio in entries}
    return (len(distinct)>=EARLY_ABORT_MIN_CORPORA
            and all(math.isfinite(r) and 0<r<EARLY_ABORT_DOM_RATIO for _,r in entries))

class Stopped(Exception):pass
class Deadline(Stopped):pass
class Safety(Exception):pass
class TimedOut(Exception):pass

def run_logged(command,log_path,*,cwd,deadline,stopfile,timeout,free_floor=FREE_FLOOR):
    """Never accumulate unbounded stdout in pipes. Stop the whole compiler group."""
    started=time.monotonic()
    cutoff=min(deadline,started+timeout)
    with Path(log_path).open('wb') as log:
        p=subprocess.Popen([str(x) for x in command],cwd=cwd,stdin=subprocess.DEVNULL,
           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while p.poll() is None:
                if Path(stopfile).exists():raise Stopped('STOP requested')
                if time.monotonic()>=cutoff:
                    if deadline<=started+timeout:raise Deadline('3-hour budget reached')
                    raise TimedOut(f'command exceeded {timeout:.0f}s')
                if shutil.disk_usage(cwd).free < free_floor:raise Safety('disk below 200 MiB safety floor during native command')
                time.sleep(.3)
        except (Stopped,TimedOut,Safety):
            with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGTERM)
            try:p.wait(timeout=3)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):os.killpg(p.pid,signal.SIGKILL)
                p.wait()
            raise
    return p.returncode,round(time.monotonic()-started,3)


def parse_dom_output(text):
    matches=re.findall(r'^DOM_RESULT\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s*$',text,re.M)
    if not matches:raise ValueError('No DOM_RESULT from native benchmark')
    rate,seconds,n,size=matches[-1]
    rate=float(rate);seconds=float(seconds)
    if not math.isfinite(rate) or rate<=0 or seconds<=0:raise ValueError('invalid throughput')
    return rate,seconds,int(n),int(size)


def rankings(rows):
    controls={(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial'])):r
              for r in rows if r['variant']=='upstream_vls256'}
    matched={}
    for r in rows:
        key=(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial']))
        ref=controls.get(key)
        if not ref:continue
        try: b=float(ref['dom_all_gbps']);v=float(r['dom_all_gbps'])
        except (KeyError,TypeError,ValueError):continue
        if b>0 and v>0 and math.isfinite(b) and math.isfinite(v):
            matched.setdefault(r['variant'],[]).append(v/b)
    result=[]
    for label,ratios in matched.items():
        med=statistics.median(ratios);gm=math.exp(statistics.mean(math.log(x) for x in ratios))
        result.append(dict(variant=label,metric='dom_all',paired_n=len(ratios),
            median_ratio=round(med,6),geomean_ratio=round(gm,6),
            mad_ratio=round(statistics.median(abs(x-med) for x in ratios),6)))
    return sorted(result,key=lambda d:(-d['geomean_ratio'],d['variant']))

class Campaign:
    def __init__(self,source,workdir,hours,jobs,core):
        self.source=Path(source).resolve();self.root=Path(workdir).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.started=time.time();self.deadline_mono=time.monotonic()+hours*3600
        self.stopfile=self.root/'STOP';self.jobs=jobs;self.core=core
        self.rows=[];self.failures=[];self.binaries={};self.abandoned={}
        self.meta={'schema':2,'experiment':'engine_library_3h_direct_gcc','compiler':'gcc',
          'benchmark_method':'Direct g++ -O3; standalone 3-repeat median DOM throughput, 1e9 bytes/s',
          'metric_limits':'Stage1 and Stage2 NOT MEASURED, columns blank; no old-method speed comparisons',
          'points':catalog(),'upstream_sha':UPSTREAM_SHA,'builds':[], 'compiler_diagnostics':[],
          'runtime_probes':[], 'code_sha256':hashlib.sha256(BENCH_CPP.encode()).hexdigest()}
        self.status={'schema':2,'state':'preflight','started_utc':now(),'last_update':now(),
          'observations':0,'source':str(self.source),'jobs':jobs,'core':core,
          'deadline_utc':dt.datetime.fromtimestamp(self.started+hours*3600,dt.timezone.utc).isoformat(),
          'budget_seconds':int(hours*3600),'point_catalog':[p[0] for p in catalog()],
          'stop_reason':None,'abandoned_points':{},'current_candidate':None}
        self.last_snap=0
    def check(self,building=False):
        if self.stopfile.exists():raise Stopped('STOP requested')
        if time.monotonic()>=self.deadline_mono:raise Deadline('3-hour budget reached')
        free=shutil.disk_usage(self.root).free
        self.status['disk_free_gib']=round(free/GIB,3)
        self.status['disk_free_mib']=round(free/(1024**2),1)
        self.status['disk_safety_floor_mib']=200
        self.status['disk_monitor_interval_seconds']=900
        instant=time.monotonic()
        if instant-getattr(self,'last_disk_monitor_monotonic',float('-inf'))>=900:
            self.last_disk_monitor_monotonic=instant
            self.status['disk_last_15m_check_utc']=now()
            self.meta.setdefault('disk_monitor_15m',[]).append({'utc':now(),'free_mib':round(free/(1024**2),1)})
        if free < (BUILD_START_FLOOR if building else FREE_FLOOR):
            raise Safety(f'free disk below safety floor ({free/GIB:.2f} GiB)')
        # Bounded workspace, including any temporary source files.
        total=0
        for base,dirs,files in os.walk(self.root,followlinks=False):
            dirs[:]=[d for d in dirs if not (Path(base)/d).is_symlink()]
            for file in files:
                with contextlib.suppress(OSError):total+=(Path(base)/file).stat().st_size
        if total>WORK_CAP:raise Safety('run exceeded 2 GiB work cap')
    def checkpoint(self,phase=None,force=False):
        if phase:self.status['state']=phase
        self.status['observations']=len(self.rows)
        self.status['last_update']=now()
        with contextlib.suppress(OSError):self.status['disk_free_gib']=round(shutil.disk_usage(self.root).free/GIB,3)
        atomic_json(self.root/'status.json',self.status)
        atomic_json(self.root/'checkpoint.json',{'started_epoch':self.started,
            'completed':len(self.rows),'updated_utc':now()})
        if force or time.monotonic()-self.last_snap>=240:
            write_csv(self.root/'map.csv',self.rows,RESULT_FIELDS)
            write_csv(self.root/'failures.csv',self.failures,('time','step','candidate','error'))
            ranking=rankings(self.rows)
            write_csv(self.root/'ranking.csv',ranking,RANK_FIELDS)
            self.meta['abandoned_points']=self.abandoned
            self.meta['build_coverage']={'passed':sorted(self.binaries),
                 'attempted':len(self.meta['builds']),'planned':len(catalog())}
            atomic_json(self.root/'metadata.json',self.meta)
            text=['# RVV 3h Engine Library — fixed experimental grid',
              '','- Snapshot updated: '+now(),'- State: '+self.status['state'],
              '- Measurements: '+str(len(self.rows)),
              '- GCC direct compile; DOM median of 3 repeats, 1e9 bytes per GB.',
              '- Stage1/Stage2 not measured in this method; never compare legacy Stage1/2 estimates.',
              '- All 17 points precommitted; only clear slowness can abort a point.',
              '- No automated winner or next experiment.',
              '','## Paired DOM exploratory ratios','',
              '| Candidate | Geo-mean vs official rvv_vls256 | N | MAD |','|---|---:|---:|---:|']
            text += [f"| {r['variant']} | {r['geomean_ratio']:.3f}x | {r['paired_n']} | {r['mad_ratio']:.3f} |" for r in ranking]
            atomic_text(self.root/'hypotheses.md','\n'.join(text)+'\n')
            self.snapshot()
            self.last_snap=time.monotonic()
    def snapshot(self):
        temp=self.root/'snapshot.zip.tmp';target=self.root/'snapshot.zip'
        manifest={'schema':1,'files':[]}
        with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in RUN_FILES:
                p=self.root/name
                if p.is_file():
                    blob=p.read_bytes();manifest['files'].append({'name':name,'bytes':len(blob),
                       'sha256':hashlib.sha256(blob).hexdigest()})
                    z.writestr(name,blob)
            z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
        if temp.stat().st_size>SNAPSHOT_LIMIT:
            temp.unlink();raise Safety('snapshot > 12 MiB')
        os.replace(temp,target)
        atomic_text(self.root/'snapshot.sha256',hashlib.sha256(target.read_bytes()).hexdigest()+'\n')
    def failure(self,step,tag,detail):
        self.failures.append({'time':now(),'step':step,'candidate':tag,'error':str(detail)[-4800:]})
        self.checkpoint(force=True)
    def preflight(self):
        mandatory=['src/simdjson.cpp','src/rvv/stage1.h','src/rvv/engines/engine_plan.h',
                   'src/rvv/engines/structural_writers.h','src/rvv/engines/stage2_bridge.h',
                   'scripts/rvv/engines/experiments.json','scripts/rvv/perf/bench_native.py',
                   'include/simdjson/simdjson_version.h']
        absent=[n for n in mandatory if not (self.source/n).is_file()]
        if absent:raise RuntimeError('Missing Engine Library files: '+', '.join(absent))
        version=(self.source/'include/simdjson/simdjson_version.h').read_text(encoding='utf8')
        if not re.search(r'^#define SIMDJSON_VERSION\s+"5\.0\.3"',version,re.M):
            raise RuntimeError('Source is not simdjson v5.0.3')
        installed=json.loads((self.source/'scripts/rvv/engines/experiments.json').read_text(encoding='utf8'))
        pointmap={x['id']:dict(s[2:].split('=',1) for s in x['flags']) for x in installed['points']}
        for tag,defines,*_ in catalog()[2:]:
            actual={'SIMDJSON_RVV_ENGINE_LIBRARY':'1',**pointmap.get(tag,{})}
            if actual!=defines:raise RuntimeError('The installed Engine Library catalogue differs: '+tag)
        if subprocess.check_output(['uname','-m'],text=True).strip()!='riscv64':
            raise RuntimeError('Native RISC-V required')
        if not shutil.which('g++') or not shutil.which('taskset'):
            raise RuntimeError('g++ or taskset missing')
        self.meta['compiler_version']=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
        # Preserve the original 8h campaign's authoritative native VLEN check.
        from argparse import Namespace
        module=importlib.util.spec_from_file_location('rvv_native_bench',
                    self.source/'scripts/rvv/perf/bench_native.py')
        bn=importlib.util.module_from_spec(module)
        module.loader.exec_module(bn)
        bn.REPO_ROOT=self.source
        with contextlib.redirect_stdout(io.StringIO()):
            hw=bn.preflight(Namespace(compiler='gcc',allow_emulation=False,core=self.core),self.root)
        if hw.get('hardware_vlen_bits')!=256:
            raise RuntimeError('Native RVV VLEN must be 256; found '+str(hw.get('hardware_vlen_bits')))
        self.status['vlen_bits']=256
        self.meta['hardware']=hw
        self.bn=bn
        self.meta['source_git_sha']=(self.source/'rvvlab-source-manifest.json').read_text(encoding='utf8')[:3000] if (self.source/'rvvlab-source-manifest.json').is_file() else 'no provenance manifest'
        probe_cpp=self.root/'dom_engine_bench.cpp';atomic_text(probe_cpp,BENCH_CPP)
        self.check(building=True)
        self.checkpoint('build',force=True)
    def source_upstream(self):
        self.check(building=True)
        dest=self.root/'upstream-official-v5.0.3'
        if dest.is_dir() and (dest/'.git').is_dir():
            actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
            if actual==UPSTREAM_SHA:return dest
        log=self.root/'upstream_clone.log'
        if not dest.exists():
            rc,_=run_logged(['git','clone','--depth','1','--branch','v5.0.3',
                 '--single-branch',UPSTREAM_URL,str(dest)],log,cwd=self.root,
                 deadline=self.deadline_mono,timeout=180,stopfile=self.stopfile,free_floor=FREE_FLOOR)
            if rc:raise RuntimeError('Official reference clone failed: '+read_tail(log,2500))
        actual=subprocess.check_output(['git','-C',str(dest),'rev-parse','HEAD'],text=True).strip()
        if actual!=UPSTREAM_SHA:
            raise RuntimeError(f'Official v5.0.3 SHA mismatch: {actual}; expected {UPSTREAM_SHA}')
        return dest
    def flags(self,kind,defines):
        base=['-O3','-DNDEBUG','-g0','-pthread','-std=c++17','-mabi=lp64d',
              '-DSIMDJSON_IMPLEMENTATION_FALLBACK=1']
        if kind=='vla':
            base += ['-march=rv64gcv','-DSIMDJSON_IMPLEMENTATION_RVV=1',
                     '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0']
        else:
            base += ['-march=rv64gcv_zvl256b','-mrvv-vector-bits=zvl',
                     '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=1']
        return base+[f'-D{k}={v}' for k,v in sorted(defines.items())]
    def build(self,spec,upstream):
        tag,defines,engine,kind=spec
        self.check(building=True)
        self.status['current_candidate']=tag
        self.checkpoint('build')
        binfolder=self.root/'bin';binfolder.mkdir(exist_ok=True)
        binary=binfolder/('parse-'+tag)
        if binary.is_file():self.binaries[tag]=(str(binary),engine,defines);return True
        src=self.source if kind=='vla' else upstream
        if not src:raise RuntimeError('Missing upstream for pinned vls reference')
        scratch=self.root/'scratch_build'
        scratch.mkdir(exist_ok=True)
        obj=scratch/'simdjson.o';exe=scratch/'parse'
        base=['g++',*self.flags(kind,defines),'-I'+str(src/'include'),'-I'+str(src/'src')]
        step='compile';start=time.monotonic()
        try:
            for step,cmd,max_time in (
                ('compile',[*base,'-c',str(src/'src/simdjson.cpp'),'-o',str(obj)],340),
                ('link',[*base,str(self.root/'dom_engine_bench.cpp'),str(obj),'-o',str(exe)],100)):
                self.check(building=True)
                log=self.root/f'{step}_{tag}.log'
                try:
                    rc,secs=run_logged(cmd,log,cwd=self.root,deadline=self.deadline_mono,
                        timeout=max_time,stopfile=self.stopfile,free_floor=FREE_FLOOR)
                except TimedOut as exc:
                    self.record_build_error(step,tag,log,124,str(exc));return False
                if rc:
                    self.record_build_error(step,tag,log,rc,f'{step} error');return False
            test_log=self.root/f'correctness_{tag}.log'
            self.check()
            rc,_=run_logged(['taskset','-c',str(self.core),str(exe),engine,'selftest'],
                test_log,cwd=self.root,deadline=self.deadline_mono,timeout=30,
                stopfile=self.stopfile)
            if rc or f'RVV_SMOKE_OK backend={engine}' not in read_tail(test_log,2000):
                self.record_build_error('correctness',tag,test_log,rc,'self-test failed');return False
            shutil.copy2(exe,binary);binary.chmod(0o755)
            self.binaries[tag]=(str(binary),engine,defines)
            self.meta['runtime_probes'].append({'tag':tag,'result':'PASS','selftest':'6 valid / 3 invalid',
                                                 'backend':engine})
            self.meta['builds'].append({'tag':tag,'result':'PASS','seconds':round(time.monotonic()-start,2)})
            self.checkpoint(force=True)
            return True
        finally:
            shutil.rmtree(scratch,ignore_errors=True)
    def record_build_error(self,step,tag,log,rc,why):
        tail=read_tail(log)
        diagnostics={'tag':tag,'step':step,'rc':rc,'why':why,'errors':extract_errors(tail),
                     'log_file':log.name,'tail':tail[-4000:]}
        self.meta['compiler_diagnostics'].append(diagnostics)
        self.meta['builds'].append({'tag':tag,'result':'FAIL','step':step,'returncode':rc})
        self.failure(step,tag,'\n'.join(diagnostics['errors']) or tail[-2000:])
    def make_corpus(self):
        bn=self.bn
        self.meta['corpus_generator']='Existing bench_native.generate_corpus (fixed 4MiB + 1MiB diverse families)'
        sets=[]
        for dirname,size in [('large_corpus',4),('small_corpus',1)]:
            folder=self.root/dirname
            self.check()
            with contextlib.redirect_stdout(io.StringIO()):bn.generate_corpus(folder,size)
            for p in sorted(folder.glob('*.json')):
                if p.name=='manifest.json':continue
                # These are deterministic user-predefined generated datasets.
                sets.append(p)
        if len(sets)<5:raise RuntimeError('Insufficient generated corpus variety')
        self.meta['corpus_files']=[{'id':p.parent.name+'/'+p.name,'bytes':p.stat().st_size} for p in sets]
        self.checkpoint(force=True)
        return sets
    def measure(self,phase,tag,path,iters,trial):
        self.check()
        binary,engine,defines=self.binaries[tag]
        cid=path.parent.name+'/'+path.name+'@'+str(path.stat().st_size)
        log=self.root/'latest_bench.log'  # reused; full result rows in map.csv
        rc,_=run_logged(['taskset','-c',str(self.core),binary,engine,'bench',str(path),str(iters)],
            log,cwd=self.root,deadline=self.deadline_mono,timeout=90,stopfile=self.stopfile)
        if rc:raise RuntimeError(f'benchmark rc={rc}: '+read_tail(log,800))
        rate,seconds,actual,size=parse_dom_output(read_tail(log,3000))
        if actual!=iters or size!=path.stat().st_size:raise RuntimeError('Corpus/iteration mismatch')
        self.rows.append({'timestamp':now(),'phase':phase,'variant':tag,
           'defines':json.dumps(defines,sort_keys=True,separators=(',',':')),
           'corpus':cid,'bytes':size,'parse_iterations':iters,'trial':trial,
           'dom_all_gbps':rate,'stage1_gbps':'','stage2_gbps':'',
           'all_cpb':'','stage1_cpb':'','stage2_cpb':'',
           'elapsed_seconds':seconds,'method':'native_dom_median3_direct_gcc_O3'})
        # Durable row immediately; snapshot generation is deliberately throttled.
        path=self.root/'map.csv'
        with path.open('a',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow(self.rows[-1]);f.flush();os.fsync(f.fileno())
        self.checkpoint(phase)
    def early_screen(self):
        # Spec order always pinned. Upstream measured first on each fixed corpus.
        names=('dense_structurals.json','ascii_strings.json','numbers.json',
               'unicode_strings.json','escapes.json')
        candidates=[p for p in self.corpi if p.parent.name=='small_corpus' and p.name in names]
        if len(candidates)<3:raise RuntimeError('No diverse short-screen corpora')
        for p in candidates:self.measure('quick_screen','upstream_vls256',p,20,0)
        refs={r['corpus']:float(r['dom_all_gbps']) for r in self.rows
              if r['variant']=='upstream_vls256' and r['phase']=='quick_screen'}
        for tag in [s[0] for s in catalog()[1:] if s[0] in self.binaries]:
            ratios=[]
            self.status['current_candidate']=tag
            for p in candidates:
                if tag in self.abandoned:break
                try:
                    self.measure('quick_screen',tag,p,20,0)
                    row=self.rows[-1]
                    ratios.append((p.name,float(row['dom_all_gbps'])/refs[row['corpus']]))
                    if should_abandon(ratios):
                        self.abandon(tag,'3+ distinct screen corpora below 0.65x DOM');break
                except (Stopped,Safety):raise
                except TimedOut:
                    self.abandon(tag,'90s screen timeout');break
                except Exception as exc:
                    self.abandon(tag,'screen failed: '+str(exc)[-400:]);break
        self.checkpoint('explore_fixed',force=True)
    def abandon(self,tag,why):
        self.abandoned[tag]=why;self.status['abandoned_points']=self.abandoned
        self.failure('abandoned',tag,why)
    def explore(self):
        self.early_screen()
        tags=[t for t,*_ in catalog() if t in self.binaries and t not in self.abandoned]
        if 'upstream_vls256' not in tags:raise RuntimeError('Reference missing; cannot compare')
        # Fixed trial order, same corpus + iterations for paired DOM ratios.
        for trial in range(1,2001):
            iters=(20,40,80)[(trial-1)%3]
            for p in self.corpi:
                for tag in tags:
                    if tag in self.abandoned:continue
                    self.check()
                    self.status['current_candidate']=tag
                    try:self.measure('explore_fixed',tag,p,iters,trial)
                    except (Stopped,Safety):raise
                    except TimedOut as exc:
                        if tag=='upstream_vls256':raise RuntimeError('Reference timeout') from exc
                        self.abandon(tag,'measure timeout')
                    except Exception as exc:
                        if tag=='upstream_vls256':raise RuntimeError('Reference measurement failure: '+str(exc)) from exc
                        self.abandon(tag,'measurement failure: '+str(exc)[-300:])
            self.status['fixed_round_completed']=trial
            self.checkpoint('explore_fixed',force=True)
    def execute(self):
        import fcntl
        lock=self.root.parent/'.night_runner_global.lock'
        with lock.open('w') as f:
            try:fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:raise RuntimeError('Another Night Runner is active')
            f.write(str(os.getpid()));f.flush()
            try:
                self.checkpoint('preflight',force=True)
                self.preflight()
                # Pin orchestration to a different allowed CPU than measurements.
                if hasattr(os,'sched_setaffinity'):
                    other=next((c for c in sorted(os.sched_getaffinity(0)) if c!=self.core),None)
                    if other is not None:
                        os.sched_setaffinity(0,{other})
                        self.status['orchestration_cpu']=other
                self.status['current_candidate']='E01_adaptive'
                if not self.build(catalog()[3],None):
                    raise RuntimeError('Known-good E01_adaptive failed; inspect metadata.json compiler_diagnostics')
                self.check()
                upstream=self.source_upstream()
                if not self.build(catalog()[0],upstream):
                    raise RuntimeError('Official upstream VLS256 reference failed; no valid comparison')
                for item in catalog():
                    if item[0] in self.binaries:continue
                    self.check(building=True)
                    try:self.build(item,upstream)
                    except (Stopped,Safety):raise
                    except Exception as exc:
                        self.meta['builds'].append({'tag':item[0],'result':'FAIL','step':'unexpected',
                                                    'error':str(exc)[-1200:]})
                        self.failure('unexpected_build',item[0],exc)
                self.meta['coverage']={'passed':list(self.binaries),'expected':len(catalog())}
                self.corpi=self.make_corpus()
                self.explore()
                self.status['state']='completed'
            except Stopped as exc:
                self.status['state']='stopped';self.status['stop_reason']=str(exc)
            except Safety as exc:
                self.status['state']='safety_stop';self.status['stop_reason']=str(exc)
            except Exception as exc:
                self.status['state']='failed';self.status['stop_reason']=str(exc)[-1800:]
                self.failures.append({'time':now(),'step':'fatal','candidate':self.status['current_candidate'],
                                      'error':str(exc)[-4600:]})
            finally:self.checkpoint(force=True)


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True);p.add_argument('--workdir',required=True)
    p.add_argument('--hours',type=float,default=3.0)
    p.add_argument('--jobs',type=int,default=2);p.add_argument('--core',type=int,default=0)
    args=p.parse_args(argv)
    if not (0<args.hours<=MAX_HOURS):p.error('hours must be in (0,3]')
    if args.jobs not in (1,2):p.error('jobs must be 1 or 2')
    campaign=Campaign(args.source,args.workdir,args.hours,args.jobs,args.core)
    campaign.execute()
    print(json.dumps({'state':campaign.status['state'],'observations':len(campaign.rows),
      'reason':campaign.status['stop_reason']},ensure_ascii=False))
    return 0 if campaign.status['state'] in ('completed','stopped') else 1

if __name__=='__main__':raise SystemExit(main())
