#!/usr/bin/env python3
"""Thirty-minute Adaptive Dispatch v2 Stage1/Stage2 + DOM profiler with JSON correctness gates.

No CMake, CPM, benchmark framework, external experimental strategy, sudo or cleanup
outside this run. Every experiment is determined before launch; only hard-coded
conservative early abandonment is allowed. Thirty minutes include native GCC builds and all checks.
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
MAX_HOURS=0.5
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
BENCH_CPP=r'''// Standalone native split-stage benchmark for simdjson RVV-VLA.
// Measures actual internal stage1() / stage2() calls plus independent public DOM parse().
// Stage1 + Stage2 timings are NOT claimed to equal DOM timing.
#include "simdjson.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>
#include <cstdlib>
#include <cstdint>

static bool parse_ok(simdjson::dom::parser& p, const std::string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static bool parse_ok(simdjson::dom::parser& p, const simdjson::padded_string& s) {
  return p.parse(s).error() == simdjson::SUCCESS;
}
static int select_backend(const std::string &backend) {
  const auto* chosen=simdjson::get_available_implementations()[backend];
  if (!chosen || !chosen->supported_by_runtime_system()) {
    std::cerr << "Unsupported backend: " << backend << "\n";
    return 3;
  }
  simdjson::get_active_implementation()=chosen;
  if (simdjson::get_active_implementation()->name()!=backend) return 4;
  return 0;
}
static int validate_file(simdjson::dom::parser& parser, const char *path, bool expected) {
  std::ifstream in(path);
  if (!in) { std::cerr << "Missing JSONL: " << path << "\n"; return 5; }
  std::string line;
  int count=0;
  while (std::getline(in,line)) {
    // CR-LF line ending support for Windows-built input.
    if (!line.empty() && line.back()=='\r') line.pop_back();
    const bool actual=parse_ok(parser,line);
    if (actual!=expected) {
      std::cerr<< "JSON classification mismatch file=" << path
               << " line=" << count+1 << " expected=" << expected
               << " actual=" << actual << "\n";
      return 20;
    }
    ++count;
  }
  if (count<10) {std::cerr<< "Insufficient correctness coverage in " << path << "\n";return 21;}
  std::cout<<"VALIDATION "<<(expected?"valid":"invalid")<<"="<<count<<"\n";
  return 0;
}
int main(int argc,char** argv) {
  if (argc < 3) {std::cerr<<"usage: bench <rvv|rvv_vls> <validate|split> args...\n";return 2;}
  std::string backend=argv[1], mode=argv[2];
  if (int rc=select_backend(backend)) return rc;
  simdjson::dom::parser parser;
  if (mode=="validate") {
    if (argc!=5) return 2;
    int rc=validate_file(parser,argv[3],true);if (rc) return rc;
    rc=validate_file(parser,argv[4],false);if (rc) return rc;
    std::cout << "RVV_VALIDATION_OK backend=" << backend << "\n";
    return 0;
  }
  if (mode!="split" || argc!=5) return 2;
  simdjson::padded_string doc;
  if (simdjson::padded_string::load(argv[3]).get(doc)!=simdjson::SUCCESS || doc.size()==0)
    return 5;
  char* end=nullptr;
  long count=std::strtol(argv[4],&end,10);
  if (!end || *end || count<1 || count>1000) return 6;
  // Warm init is required: parser.implementation is created lazily by parse().
  if (!parse_ok(parser,doc)) {std::cerr<<"Corpus fails full DOM parse\n";return 22;}
  const uint8_t* data=reinterpret_cast<const uint8_t*>(doc.data());
  auto stage_cycle = [&]() -> int {
    auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage1 error "<<rc<<"\n";return 23;}
    rc=parser.implementation->stage2(parser.doc);
    if (rc!=simdjson::SUCCESS) {std::cerr<<"Stage2 error "<<rc<<"\n";return 24;}
    return 0;
  };
  if (int rc=stage_cycle()) return rc;
  using clock=std::chrono::steady_clock;
  double dom_rates[3],stage1_rates[3],stage2_rates[3];
  double dom_times[3],stage1_times[3],stage2_times[3];
  for (int rep=0;rep<3;rep++) {
    // Measure stages from actual implementation calls, not an inferred split.
    double ns1=0,ns2=0;
    for(long i=0;i<count;i++) {
      const auto t0=clock::now();
      auto rc=parser.implementation->stage1(data,doc.size(),simdjson::stage1_mode::regular);
      const auto t1=clock::now();
      if(rc!=simdjson::SUCCESS) return 30;
      rc=parser.implementation->stage2(parser.doc);
      const auto t2=clock::now();
      if(rc!=simdjson::SUCCESS) return 31;
      ns1+=std::chrono::duration<double>(t1-t0).count();
      ns2+=std::chrono::duration<double>(t2-t1).count();
    }
    const auto start=clock::now();
    for(long i=0;i<count;i++) {
      if(!parse_ok(parser,doc)) {std::cerr<<"Corrupt DOM parse during benchmark\n";return 32;}
    }
    const auto finish=clock::now();
    dom_times[rep]=std::chrono::duration<double>(finish-start).count();
    stage1_times[rep]=ns1;
    stage2_times[rep]=ns2;
    if (dom_times[rep]<=0||ns1<=0||ns2<=0)return 33;
    const double bytes=double(count)*double(doc.size());
    dom_rates[rep]=bytes / dom_times[rep] / 1e9;
    stage1_rates[rep]=bytes / ns1 / 1e9;
    stage2_rates[rep]=bytes / ns2 / 1e9;
  }
  std::sort(dom_rates,dom_rates+3);
  std::sort(stage1_rates,stage1_rates+3);
  std::sort(stage2_rates,stage2_rates+3);
  std::sort(dom_times,dom_times+3);
  std::sort(stage1_times,stage1_times+3);
  std::sort(stage2_times,stage2_times+3);
  std::cout.precision(12);
  std::cout<<"SPLIT_RESULT "<<dom_rates[1]<<' '<<stage1_rates[1]<<' '
           <<stage2_rates[1]<<' '<<dom_times[1]<<' '<<stage1_times[1]
           <<' '<<stage2_times[1]<<' '<<count<<' '<<doc.size()<<"\n";
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
    """Fixed A/B hypotheses. Changes only the policy, not JSON semantics."""
    common={'SIMDJSON_RVV_ENGINE_LIBRARY':'1',
            'SIMDJSON_RVV_FORCE_PLAN':'0',
            'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0',
            'SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0'}
    return [
        ('upstream_vls256',{},'rvv_vls','vls'),
        ('A0_E14_original',{**common,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'0'},'rvv','vla'),
        ('A1_size_gate',{**common,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'1'},'rvv','vla'),
        ('A2_quick_dispatch',{**common,'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2'},'rvv','vla'),
    ]

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
                    if deadline<=started+timeout:raise Deadline('30-minute budget reached')
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


def parse_split_output(text):
    match=re.search(r'^SPLIT_RESULT\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\d+)\s+(\d+)\s*$', text, re.M)
    if not match:raise ValueError('No SPLIT_RESULT from native benchmark')
    vals=[float(x) for x in match.groups()[:6]]
    if not all(math.isfinite(x) and x>0 for x in vals):raise ValueError('invalid rates or durations')
    return vals+[int(x) for x in match.groups()[6:]]


def rankings(rows):
    controls={(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial'])):r
              for r in rows if r['variant']=='upstream_vls256'}
    matched={}
    for r in rows:
        key=(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial']))
        ref=controls.get(key)
        if not ref:continue
        for col,metric in [('dom_all_gbps','dom_all'),('stage1_gbps','stage1'),('stage2_gbps','stage2')]:
            try:b=float(ref[col]);v=float(r[col])
            except (KeyError,TypeError,ValueError):continue
            if b>0 and v>0 and math.isfinite(b) and math.isfinite(v):
                matched.setdefault((r['variant'],metric),[]).append(v/b)
    result=[]
    for (label,metric),ratios in matched.items():
        med=statistics.median(ratios)
        gm=math.exp(statistics.mean(math.log(x) for x in ratios))
        result.append(dict(variant=label,metric=metric,paired_n=len(ratios),
            median_ratio=round(med,6),geomean_ratio=round(gm,6),
            mad_ratio=round(statistics.median(abs(x-med) for x in ratios),6)))
    return sorted(result,key=lambda d:(d['metric'],-d['geomean_ratio'],d['variant']))

class Campaign:
    def __init__(self,source,workdir,hours,jobs,core):
        self.source=Path(source).resolve();self.root=Path(workdir).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.started=time.time();self.deadline_mono=time.monotonic()+hours*3600
        self.stopfile=self.root/'STOP';self.jobs=jobs;self.core=core
        self.rows=[];self.failures=[];self.binaries={};self.abandoned={}
        self.meta={'schema':2,'experiment':'adaptive_v2_30m_split_stage_direct_gcc','compiler':'gcc',
          'benchmark_method':'Direct g++ -O3: independent DOM parse() timing + direct stage1()/stage2() timing; 3-repetition medians; 1e9 bytes/s',
          'metric_limits':'Internal parser stage1 and stage2 measured explicitly (warm preallocated parser); stage durations do not necessarily add to DOM public API timing; CPU wall time, no cycles',
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
        if time.monotonic()>=self.deadline_mono:raise Deadline('30-minute budget reached')
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
            text=['RVV Adaptive Dispatch v2 — A0/A1/A2 plus official reference',
              '','- Snapshot updated: '+now(),'- State: '+self.status['state'],
              '- Measurements: '+str(len(self.rows)),
              '- GCC direct compile; separate DOM, Stage1 and Stage2 wall times, each median of 3; GB=1e9 bytes.',
              '- Stage1 and Stage2 are measured from implementation methods, not derived from DOM; warm allocated parser.',
              '- Four fixed points: upstream, A0, A1, A2; no automatic generation or winner.',
              '- Fixed alternating/reversed measurement order to control thermal/cache drift.',
              '','## Paired metric ratios against official v5.0.3 VLS256','',
              '| Candidate | Metric | Geo-mean vs official VLS256 | N | MAD |','|---|---|---:|---:|---:|']
            text += [f"| {r['variant']} | {r['metric']} | {r['geomean_ratio']:.3f}x | {r['paired_n']} | {r['mad_ratio']:.3f} |" for r in ranking]
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
        header=(self.source/'src/rvv/engines/engine_plan.h').read_text(encoding='utf8')
        for marker in ('SIMDJSON_RVV_ADAPTIVE_V2_LEVEL',
                       'SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES',
                       'SIMDJSON_RVV_ADAPTIVE_V2_QUICK_BYTES'):
            if marker not in header:raise RuntimeError('Missing Adaptive Dispatch v2 marker: '+marker)
        if subprocess.check_output(['uname','-m'],text=True).strip()!='riscv64':
            raise RuntimeError('Native RISC-V required')
        if not shutil.which('g++') or not shutil.which('taskset'):
            raise RuntimeError('g++ or taskset missing')
        self.meta['compiler_version']=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
        # Preserve the original 30m campaign's authoritative native VLEN check.
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
        probe_cpp=self.root/'split_stage_bench.cpp';atomic_text(probe_cpp,BENCH_CPP)
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
        if not src:raise RuntimeError('Missing upstream for pinned VLS reference')
        scratch=self.root/'scratch_build';scratch.mkdir(exist_ok=True)
        obj=scratch/'simdjson.o';exe=scratch/'parse'
        flags=['g++',*self.flags(kind,defines),'-I'+str(src/'include'),'-I'+str(src/'src')]
        start=time.monotonic()
        try:
            for step,cmd,max_time in (
                ('compile',[*flags,'-c',str(src/'src/simdjson.cpp'),'-o',str(obj)],340),
                ('link',[*flags,str(self.root/'split_stage_bench.cpp'),str(obj),'-o',str(exe)],100)):
                self.check(building=True)
                log=self.root/f'{step}_{tag}.log'
                try:rc,_=run_logged(cmd,log,cwd=self.root,deadline=self.deadline_mono,
                    timeout=max_time,stopfile=self.stopfile,free_floor=FREE_FLOOR)
                except TimedOut as exc:
                    self.record_build_error(step,tag,log,124,str(exc));return False
                if rc:self.record_build_error(step,tag,log,rc,step+' error');return False
            log=self.root/f'correctness_{tag}.log'
            self.check()
            rc,_=run_logged(['taskset','-c',str(self.core),str(exe),engine,'validate',
                              str(self.root/'valid.jsonl'),str(self.root/'invalid.jsonl')],
                log,cwd=self.root,deadline=self.deadline_mono,timeout=90,stopfile=self.stopfile)
            if rc or f'RVV_VALIDATION_OK backend={engine}' not in read_tail(log,2500):
                self.record_build_error('correctness',tag,log,rc,'JSONL validation failed');return False
            shutil.copy2(exe,binary);binary.chmod(0o755)
            self.binaries[tag]=(str(binary),engine,defines)
            self.meta['runtime_probes'].append({'tag':tag,'result':'PASS',
                'selftest':self.meta['validation_cases'],'backend':engine})
            self.meta['builds'].append({'tag':tag,'result':'PASS','seconds':round(time.monotonic()-start,2)})
            self.checkpoint(force=True)
            return True
        finally:shutil.rmtree(scratch,ignore_errors=True)
    def record_build_error(self,step,tag,log,rc,why):
        tail=read_tail(log)
        diagnostics={'tag':tag,'step':step,'rc':rc,'why':why,'errors':extract_errors(tail),
                     'log_file':log.name,'tail':tail[-4000:]}
        self.meta['compiler_diagnostics'].append(diagnostics)
        self.meta['builds'].append({'tag':tag,'result':'FAIL','step':step,'returncode':rc})
        self.failure(step,tag,'\n'.join(diagnostics['errors']) or tail[-2000:])
    def make_validation_cases(self):
        import random
        rng=random.Random(20261010)
        val=[None,True,False,[],{},0,-1,1e-300,1e300,'',
             'hello','héllo 😺 世界', '\u0000\n\t\b', '\\',
             {'key':'😊','arr':[1,2,3], 'escaped':'a\"b\\c'},
             [True,False,None], {'emoji':'😀','text':'áçœ漢字'},
             {str(i):i for i in range(30)},
             {'nested':{'level':{'other':{'k':1}}}}]
        alphabet=['héllo','😺','世界','escape\n','ASCII','\u2028','\\','"','']
        for i in range(150):
            val.append({'round':i, 'strings':[rng.choice(alphabet) for _ in range(i%11)],
              'integers':[rng.randint(-2**53,2**53) for _ in range(i%7)],
              'object':{'ok':bool(i%2),'empty':[], 'nil':None},
              'float':round(rng.uniform(-1e8,1e8),4)})
        bad=['{', '[1,]', '{"a":}', '{"a":1,}', '[1,,2]',
             '{"x":01}', '{"x":+1}', '{"x":1e}', '{"x":1}junk',
             '[NaN]', '{"x":1 "y":2}', '"unterminated',
             '[true false]', '{"a":undefined}', '{"a":1, "b"}',
             '[}', '{"x":.5}', '{"x":1.}', '[-]', 'tru',
             '{"x":--1}', '{"x":2e+}', '{"x":+0}', '[1,2,3,]']
        valid_path=self.root/'valid.jsonl';invalid_path=self.root/'invalid.jsonl'
        atomic_text(valid_path, ''.join(json.dumps(x,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n' for x in val))
        atomic_text(invalid_path, ''.join(x+'\n' for x in bad))
        self.meta['validation_cases']={'valid':len(val),'invalid':len(bad),
            'method':'seeded Python json.dumps reference plus 24 deliberately malformed JSON documents'}
        self.checkpoint(force=True)

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
        # The legacy unicode_strings corpus is mostly ASCII JSON escapes.
        # Add real multibyte UTF-8 payloads in both size groups.
        for dirname,size_mib in [('small_corpus',1),('large_corpus',4)]:
            path=self.root/dirname/'real_utf8_strings.json'
            texts=['héllo 😺 世界','áçœ漢字','Привет мир','العَرَبِيَّة',
                   'தமிழ் தமிழ்','🧪🚀🌍','café crème','naïve fiancée']
            raw=[json.dumps({'n':i,'str':texts[i%len(texts)]*5,'ok':i%2==0},
                        ensure_ascii=False,separators=(',',':')) for i in range(256)]
            batch=','.join(raw)
            # Exactly one JSON document; data padded to about the requested size.
            repeats=max(1,int(size_mib*1024**2/(len(batch.encode('utf8'))+1)))
            body='[' + ','.join([batch]*repeats) + ']'
            atomic_text(path,body)
            sets.append(path)
        # Exact JSON byte lengths around the 4 KiB size gate. Benchmark small
        # payloads with more iterations to keep timer resolution useful.
        for length in (128, 2048, 4095, 4096, 8192):
            folder=self.root/'tiny_corpus';folder.mkdir(exist_ok=True)
            for shape in ('compact','escaped'):
                path=folder/f'{shape}_{length}.json'
                token='\\u1234' if shape=='escaped' else 'abc'
                overhead=len('{"payload":""}')
                remaining=length-overhead
                body='{"payload":"'+token*(remaining//len(token))+'a'*(remaining%len(token))+'"}'
                assert len(body.encode('utf-8'))==length
                atomic_text(path,body)
                sets.append(path)
        self.meta['raw_utf8_corpus']='Real UTF-8 multibyte input added separately from escaped Unicode corpus' 
        if len(sets)<5:raise RuntimeError('Insufficient generated corpus variety')
        self.meta['corpus_files']=[{'id':p.parent.name+'/'+p.name,'bytes':p.stat().st_size} for p in sets]
        self.checkpoint(force=True)
        return sets
    def measure(self,phase,tag,path,iters,trial):
        self.check()
        binary,engine,defines=self.binaries[tag]
        cid=path.parent.name+'/'+path.name+'@'+str(path.stat().st_size)
        log=self.root/'latest_bench.log'
        rc,_=run_logged(['taskset','-c',str(self.core),binary,engine,'split',str(path),str(iters)],
            log,cwd=self.root,deadline=self.deadline_mono,timeout=90,stopfile=self.stopfile)
        if rc:raise RuntimeError(f'split benchmark rc={rc}: '+read_tail(log,1600))
        dom,stage1,stage2,tdom,tstage1,tstage2,actual,size=parse_split_output(read_tail(log,3000))
        if actual!=iters or size!=path.stat().st_size:raise RuntimeError('Corpus/iteration mismatch')
        self.rows.append({'timestamp':now(),'phase':phase,'variant':tag,
           'defines':json.dumps(defines,sort_keys=True,separators=(',',':')),
           'corpus':cid,'bytes':size,'parse_iterations':iters,'trial':trial,
           'dom_all_gbps':dom,'stage1_gbps':stage1,'stage2_gbps':stage2,
           'all_cpb':'','stage1_cpb':'','stage2_cpb':'',
           'elapsed_seconds':tdom,'method':'native_DOM_and_direct_stage1_stage2_median3_gcc_O3'})
        path_csv=self.root/'map.csv'
        with path_csv.open('a',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow(self.rows[-1]);f.flush();os.fsync(f.fileno())
        self.checkpoint(phase)
    def early_screen(self):
        names=('dense_structurals.json','ascii_strings.json','numbers.json',
               'unicode_strings.json','escapes.json')
        candidates=[p for p in self.corpi if p.parent.name=='small_corpus' and p.name in names]
        if len(candidates)<3:raise RuntimeError('No diverse short-screen corpora')
        for p in candidates:self.measure('quick_screen','upstream_vls256',p,12,0)
        refs={r['corpus']:float(r['dom_all_gbps']) for r in self.rows
              if r['variant']=='upstream_vls256' and r['phase']=='quick_screen'}
        for tag in [s[0] for s in catalog()[1:] if s[0] in self.binaries]:
            ratios=[]
            self.status['current_candidate']=tag
            for p in candidates:
                if tag in self.abandoned:break
                try:
                    self.measure('quick_screen',tag,p,12,0)
                    row=self.rows[-1]
                    ratios.append((p.name,float(row['dom_all_gbps'])/refs[row['corpus']]))
                    if should_abandon(ratios):
                        self.abandon(tag,'3+ distinct screen corpora below 0.65x DOM');break
                except (Stopped,Safety):raise
                except TimedOut:self.abandon(tag,'90s screen timeout');break
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
        self.meta['ordering']='Fixed per-trial forward/reverse rotation of 4 variants; each corpus has paired same-trial reference'
        self.meta['stages']='Direct stage1()/stage2() measured separately from public DOM parse()'
        for trial in range(1,2001):
            iters=(12,24,48)[(trial-1)%3]
            order=(list(tags) if trial%2 else list(reversed(tags)))
            rot=(trial//2)%len(order)
            order=order[rot:]+order[:rot]
            self.status['last_measurement_order']=order
            for p in self.corpi:
                # For 128B–8KiB avoid meaningless nanosecond timings.
                local_iters=512 if p.parent.name=='tiny_corpus' else iters
                for tag in order:
                    if tag in self.abandoned:continue
                    self.check()
                    self.status['current_candidate']=tag
                    try:self.measure('explore_fixed',tag,p,local_iters,trial)
                    except (Stopped,Safety):raise
                    except TimedOut:
                        if tag=='upstream_vls256':raise RuntimeError('Reference timeout')
                        self.abandon(tag,'measure timeout')
                    except Exception as exc:
                        if tag=='upstream_vls256':raise RuntimeError('Reference failure: '+str(exc))
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
                self.make_validation_cases()
                self.status['current_candidate']='A0_E14_original'
                if not self.build(catalog()[1],None):
                    raise RuntimeError('A0 E14 baseline failed; inspect metadata.json compiler_diagnostics')
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
    p.add_argument('--hours',type=float,default=0.5)
    p.add_argument('--jobs',type=int,default=2);p.add_argument('--core',type=int,default=0)
    args=p.parse_args(argv)
    if not (0<args.hours<=MAX_HOURS):p.error('hours must be in (0,0.5]')
    if args.jobs not in (1,2):p.error('jobs must be 1 or 2')
    campaign=Campaign(args.source,args.workdir,args.hours,args.jobs,args.core)
    campaign.execute()
    print(json.dumps({'state':campaign.status['state'],'observations':len(campaign.rows),
      'reason':campaign.status['stop_reason']},ensure_ascii=False))
    return 0 if campaign.status['state'] in ('completed','stopped') else 1

if __name__=='__main__':raise SystemExit(main())
