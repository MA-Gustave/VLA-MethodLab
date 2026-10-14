#!/usr/bin/env python3
"""Sixty-minute exploratory Adaptive Dispatch v2 prequalification profiler with JSON correctness gates.

No CMake, CPM, benchmark framework, external experimental strategy, sudo or cleanup
outside this run. Every experiment is determined before launch; only hard-coded
conservative early abandonment is allowed. Sixty minutes include native GCC builds and all checks.
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
MAX_HOURS=1.0
WORK_CAP=2*GIB
FREE_FLOOR=200*1024**2
BUILD_START_FLOOR=FREE_FLOOR
SNAPSHOT_LIMIT=12*1024**2
RUN_FILES=('status.json','checkpoint.json','map.csv','ranking.csv','hypotheses.md','failures.csv','metadata.json','corpus_manifest.json','trend_candidates.csv','prequal_pairwise.csv','TRENDS.md')
RESULT_FIELDS=('timestamp','phase','variant','defines','corpus','bytes','parse_iterations','trial',
               'dom_all_gbps','stage1_gbps','stage2_gbps','all_cpb','stage1_cpb','stage2_cpb',
               'elapsed_seconds','method','scenario','distribution','size_target','sampling_bias')
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
                    if deadline<=started+timeout:raise Deadline('60-minute budget reached')
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

# Prequalification survey corpus: predeclared, deterministic and never optimized
# in response to early performance results. Approximately 170 JSON documents
# (512 B to 4 MiB), plus exact 4-KiB boundary documents.
EXPLORATION_SEED=20261011
BASE_SIZES=(512,2048,4095,4096,4097,8192,65536,262144,1048576)
BASE_KINDS=('ascii','numbers','dense','escaped','unicode_escape','utf8',
            'nested','whitespace','long_strings','many_keys','mixed')
SKEW_SIZES=(8192,65536,262144,1048576)
SKEW_KINDS=('escaped','utf8','dense','numbers')
SKEW_DISTRIBUTIONS=('front','middle','back')
EDGE_SIZES=(128,511,512,4095,4096,4097,8192)


def _json_atom(kind,index):
    # Consistent, valid JSON values across families. The encoded bytes of
    # escapes and raw UTF-8 are intentionally not interchangeable.
    if kind=='ascii':return {'name':'lorem_ipsum_alpha_beta_gamma'*2,'id':index%1000,'ok':True}
    if kind=='numbers':return [index,-index,0.0000001234,1.234e22,index+0.75]
    if kind=='dense':return [[0,1],[2,3],{'a':0,'b':[]},True,False,None]
    if kind=='escaped':return {'p':'back\\slash\\route\nquoted"value\t'*3,'index':index}
    if kind=='unicode_escape':return {'p':'😺😀漢字é'*9,'index':index}
    if kind=='utf8':return {'str':'中文 العربية हिन्दी 🐈 café '*4,'id':index}
    if kind=='nested':
        v={'leaf':[1,2,None,'z']}
        for _ in range(10):v={'child':v}
        return v
    if kind=='whitespace':return {'a':[0,1,2],'space':'   '*3,'b':True}
    if kind=='long_strings':return {'text':'abcdefghij'*100,'n':index}
    if kind=='many_keys':return {f'key_{i:02d}':i+index for i in range(24)}
    if kind=='mixed':return {'json':[1,'abc',None,{'a':[True,{'z':4}]}], 'utf8':'résumé 🧪','escape':'a\nb','n':index}
    raise ValueError(kind)


def make_bytes(kind,target,distribution='uniform'):
    # A trailing-padded JSON array with approximate target *byte* size.
    # Exact-size boundary probes are generated separately.
    import random
    rng=random.Random(EXPLORATION_SEED+target+sum(map(ord,kind))+sum(map(ord,distribution)))
    primary=kind
    filler='ascii' if primary!='ascii' else 'dense'
    # use a clean JSON prefix/suffix rather than truncating UTF-8/escapes
    atoms=[];count=0;total=2
    while total<target and count<200000:
        count+=1
        which=kind
        if distribution!='uniform':
            position=total/max(1,target)
            noisy=(position<.24 if distribution=='front' else
                   position>.76 if distribution=='back' else
                   .38<=position<=.63)
            which=primary if noisy else filler
        if kind=='mixed' and distribution=='uniform':
            which=BASE_KINDS[(count*7+rng.randrange(0,len(BASE_KINDS)))%len(BASE_KINDS)]
        # ensure escaped Unicode is actually escaped, not raw UTF-8
        item=json.dumps(_json_atom(which,count),ensure_ascii=(which=='unicode_escape'),
                        separators=(',',':'),allow_nan=False)
        # whitespace is deliberately inserted outside strings on some cases
        if kind=='whitespace' and count%2==0:
            item=' \n  '+item+'  '
        atoms.append(item)
        total+=len(item.encode('utf8'))+1
    return ('['+','.join(atoms)+']').encode('utf8')


def exact_gate_bytes(kind,size):
    # Length is precisely the requested number of bytes with safe JSON syntax.
    payload=('\\\\' if kind=='escaped' else 'u' if kind=='ascii' else 'é')
    head=b'{"data":"';tail=b'"}'
    base=len(head)+len(tail)
    if kind=='utf8':
        remaining=size-base
        inner=('é'*(remaining//2)+'z'*(remaining%2)).encode('utf8')
    elif kind=='escaped':
        remaining=size-base
        inner=(('\\\\'*(remaining//2))+'z'*(remaining%2)).encode('utf8')
    else:inner=b'x'*(size-base)
    result=head+inner+tail
    assert len(result)==size,(kind,size,len(result))
    json.loads(result)
    return result


def sampling_signals(data,window=512):
    # Crude BYTE proxies only. Not JSON syntax classification or engine
    # instrumentation. These diagnostics must NOT be represented as decisions
    # made by the runtime parser, or as ground truth JSON types.
    n=len(data)
    samples={}
    for name,start in [('head',0),('middle',max(0,(n-window)//2)),('tail',max(0,n-window))]:
        chunk=data[start:start+window]
        cnt=max(1,len(chunk))
        samples[name]={'n':len(chunk),'slash_density':round(chunk.count(b'\\')/cnt,5),
          'quote_density':round(chunk.count(b'"')/cnt,5),
          'struct_density':round(sum(chunk.count(bytes([c])) for c in (91,93,123,125,44,58))/cnt,5),
          'highbyte_density':round(sum(c>=128 for c in chunk)/cnt,5),
          'digit_density':round(sum(48<=c<=57 for c in chunk)/cnt,5)}
    samples['head_4096']={'n':min(4096,n),'slash_density':round(data[:4096].count(b'\\')/max(1,min(4096,n)),5),
        'highbyte_density':round(sum(c>=128 for c in data[:4096])/max(1,min(4096,n)),5)}
    return samples


def derived_trends(rows, corpus_info):
    from collections import defaultdict
    reference={(r['phase'],r['corpus'],str(r['trial'])):r for r in rows
               if r['variant']=='upstream_vls256'}
    slots=defaultdict(list)
    for r in rows:
        if r['variant']=='upstream_vls256':continue
        ref=reference.get((r['phase'],r['corpus'],str(r['trial'])))
        if ref is None:continue
        try: ratio=float(r['dom_all_gbps'])/float(ref['dom_all_gbps'])
        except (ValueError,ZeroDivisionError):continue
        if not math.isfinite(ratio) or ratio<=0:continue
        info=corpus_info.get(r['corpus'].split('@',1)[0],{})
        shape=info.get('kind','unknown');size=info.get('size_target',0)
        band=('tiny (<4KiB)' if size<4096 else 'gate (4-8KiB)' if size<=8192 else
              'medium (8-256KiB)' if size<=262144 else 'large (>=1MiB)')
        slots[(shape,band,r['variant'])].append(ratio)
    fields=('kind','size_band','variant','n','geomean_dom_vs_vls256','median_dom_vs_vls256','exploratory_only')
    output=[]
    for (shape,band,tag),vals in sorted(slots.items()):
        gm=math.exp(statistics.mean(math.log(x) for x in vals))
        output.append(dict(zip(fields,[shape,band,tag,len(vals),round(gm,6),round(statistics.median(vals),6),True])))
    return output,fields


def prequal_pairwise(rows,corpus_info):
    # Mode-to-mode comparisons are more relevant than a baseline speedup when
    # researching the incremental value of classification. Match EXACT trial,
    # corpus and iteration count. Require full positive finite measurements.
    from collections import defaultdict
    groups=defaultdict(dict)
    for r in rows:
        key=(r['phase'],r['corpus'],str(r['parse_iterations']),str(r['trial']))
        groups[key][r['variant']]=r
    pairs=(('A1_size_gate','A0_E14_original'),
           ('A2_quick_dispatch','A0_E14_original'),
           ('A2_quick_dispatch','A1_size_gate'))
    fields=('phase','corpus','trial','iterations','kind','distribution','size_target',
            'bytes','sample_spread_proxy','numerator','denominator',
            'dom_ratio','stage1_ratio','stage2_ratio','exploratory_only')
    output=[]
    for key,variants in sorted(groups.items()):
        phase,corpus,iterations,trial=key
        info=corpus_info.get(corpus.split('@',1)[0],{})
        for a,b in pairs:
            if a not in variants or b not in variants:continue
            vals=[]
            for metric in ('dom_all_gbps','stage1_gbps','stage2_gbps'):
                try:ratio=float(variants[a][metric])/float(variants[b][metric])
                except (ValueError,ZeroDivisionError,KeyError):break
                if not math.isfinite(ratio) or ratio<=0:break
                vals.append(round(ratio,7))
            if len(vals)!=3:continue
            output.append(dict(zip(fields,[phase,corpus,trial,iterations,
                info.get('kind','?'),info.get('distribution','?'),
                info.get('size_target',0),info.get('bytes',0),
                info.get('sample_spread_proxy',0),a,b,*vals,True])))
    return output,fields


class Campaign:
    def __init__(self,source,workdir,hours,jobs,core):
        self.source=Path(source).resolve();self.root=Path(workdir).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.started=time.time();self.deadline_mono=time.monotonic()+hours*3600
        self.stopfile=self.root/'STOP';self.jobs=jobs;self.core=core
        self.rows=[];self.failures=[];self.binaries={};self.abandoned={}
        self.meta={'schema':2,'experiment':'adaptive_v2_prequal_exploratory_60m','compiler':'gcc',
          'benchmark_method':'Direct g++ -O3: independent DOM parse() timing + direct stage1()/stage2() timing; 3-repetition medians; 1e9 bytes/s',
          'metric_limits':'Internal parser stage1 and stage2 measured explicitly (warm preallocated parser); stage durations do not necessarily add to DOM public API timing; CPU wall time, no cycles',
          'points':catalog(),'upstream_sha':UPSTREAM_SHA,'builds':[], 'compiler_diagnostics':[],
          'runtime_probes':[], 'code_sha256':hashlib.sha256(BENCH_CPP.encode()).hexdigest()}
        self.status={'schema':2,'state':'preflight','started_utc':now(),'last_update':now(),
          'observations':0,'source':str(self.source),'jobs':jobs,'core':core,
          'deadline_utc':dt.datetime.fromtimestamp(self.started+hours*3600,dt.timezone.utc).isoformat(),
          'budget_seconds':int(hours*3600),'fixed_round_completed':0,'point_catalog':[p[0] for p in catalog()],
          'stop_reason':None,'abandoned_points':{},'current_candidate':None}
        self.last_snap=0
    def check(self,building=False):
        if self.stopfile.exists():raise Stopped('STOP requested')
        if time.monotonic()>=self.deadline_mono:raise Deadline('60-minute budget reached')
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
            text=['Exploratory prequalification 60m — A0/A1/A2 plus official reference',
              '','- Snapshot updated: '+now(),'- State: '+self.status['state'],
              '- Measurements: '+str(len(self.rows)),
              '- GCC direct compile; separate DOM, Stage1 and Stage2 wall times, each median of 3; GB=1e9 bytes.',
              '- Stage1 and Stage2 are measured from implementation methods, not derived from DOM; warm allocated parser.',
              '- Four fixed points, predeclared varied JSON; no online optimization and no automatic winner.',
              '- Randomized corpus order and alternated/reversed candidates; exploratory results only.',
              '','## Paired metric ratios against official v5.0.3 VLS256','',
              '| Candidate | Metric | Geo-mean vs official VLS256 | N | MAD |','|---|---|---:|---:|---:|']
            text += [f"| {r['variant']} | {r['metric']} | {r['geomean_ratio']:.3f}x | {r['paired_n']} | {r['mad_ratio']:.3f} |" for r in ranking]
            atomic_text(self.root/'hypotheses.md','\n'.join(text)+'\n')
            info=getattr(self,'corpi_info',{})
            trends,fields=derived_trends(self.rows,info)
            write_csv(self.root/'trend_candidates.csv',trends,fields)
            comparisons,comparison_fields=prequal_pairwise(self.rows,info)
            write_csv(self.root/'prequal_pairwise.csv',comparisons,comparison_fields)
            review=['# Exploratory prequalification: candidate trends (NOT validated)', '',
               f'As of {now()}, {len(self.rows)} records; {len(info)} planned JSON cases.',
               '', 'These per-shape values are geometric means of matched DOM ratios against',
               'official simdjson VLS256. Repeated trials are correlated. The same corpus',
               'design drives all variants, but there is no multi-hardware replication.',
               'Subgroups with small paired n are especially noisy. These are candidates',
               'for future confirmation, not a winner, not statistically significant.',
               '', '| Family | Size band | Mode | Matched n | DOM vs VLS256 |',
               '|---|---|---|---:|---:|']
            review += [f"| {r['kind']} | {r['size_band']} | {r['variant']} | {r['n']} | {r['geomean_dom_vs_vls256']:.3f}x |" for r in trends]
            # Avoid claiming a winner. Rank only the most extreme, noisy
            # pairwise DOM observations as *follow-up candidates*.
            suggestions=[r for r in comparisons if r['numerator']=='A2_quick_dispatch'
                 and r['denominator']=='A0_E14_original']
            suggestions.sort(key=lambda r:abs(math.log(r['dom_ratio'])),reverse=True)
            review += ['','## Hypotheses to re-test (single-trial outliers; NOT validated)',
                '','The following are extreme A2/A0 DOM comparisons only, selected',
                'post hoc among many related tests. Expect selection bias and noise.',
                'Re-run each with new data, repeated fresh processes, and independent',
                'reference order. Do not publish them as achieved speedups.','',
                '| Corpus | Kind | Placement | A2/A0 DOM | Prefix-vs-rest proxy |',
                '|---|---|---|---:|---:|']
            review += [f"| `{r['corpus'].split('@')[0]}` | {r['kind']} | {r['distribution']} | {r['dom_ratio']:.3f}x | {r['sample_spread_proxy']:.4f} |"
                       for r in suggestions[:15]]
            atomic_text(self.root/'TRENDS.md','\n'.join(review)+'\n')
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
        self.check()
        # User-defined fixed cross-product, not a data-dependent curriculum.
        scenarios=[]
        for kind in BASE_KINDS:
            for n in BASE_SIZES:scenarios.append((kind,n,'uniform',False))
        for kind in SKEW_KINDS:
            for n in SKEW_SIZES:
                for placement in SKEW_DISTRIBUTIONS:scenarios.append((kind,n,placement,False))
        for kind in ('ascii','escaped','utf8'):
            for n in EDGE_SIZES:scenarios.append((kind,n,'threshold',True))
        for kind in ('dense','mixed','utf8','escaped','unicode_escape','numbers'):
            scenarios.append((kind,4*1024*1024,'uniform',False))
        self.meta['exploration_design']={
          'seed':EXPLORATION_SEED,'scenarios_precommitted':len(scenarios),
          'sizes_base_bytes':list(BASE_SIZES),'sizes_edge_exact_bytes':list(EDGE_SIZES),
          'heavy_placements':list(SKEW_DISTRIBUTIONS),
          'sampling':'read-only 512-byte head/mid/tail diagnostics; also 4KiB head comparison',
          'selection':'No online tuning, no automatic best-plan selection, no significance claims',
          'stage_timing':'native stage1/stage2 directly, DOM independently, median of 3',
          'hardware_note':'Varied JSON data and cache-size regimes on one native RVV server; not multiple hardware environments'}
        directory=self.root/'prequal_corpus';directory.mkdir(exist_ok=True)
        results=[];manifest=[]
        for index,(kind,target,placement,exact) in enumerate(scenarios):
            self.check()
            label=f'{index:03d}_{kind}_{placement}_{target}'
            p=directory/(label+'.json')
            data=(exact_gate_bytes(kind,target) if exact else make_bytes(kind,target,placement))
            # Reject malformed generated JSON BEFORE native measurements.
            json.loads(data)
            p.write_bytes(data)
            signals=sampling_signals(data)
            spread=max(v['slash_density'] for k,v in signals.items() if k in ('head','middle','tail'))-min(v['slash_density'] for k,v in signals.items() if k in ('head','middle','tail'))
            spread+=max(v['highbyte_density'] for k,v in signals.items() if k in ('head','middle','tail'))-min(v['highbyte_density'] for k,v in signals.items() if k in ('head','middle','tail'))
            item={'id':p.parent.name+'/'+p.name,'kind':kind,'distribution':placement,
                  'size_target':target,'bytes':len(data),'exact_target':exact,
                  'sha256':hashlib.sha256(data).hexdigest(),
                  'sample_spread_proxy':round(spread,5),'sample_windows':signals}
            manifest.append(item);results.append(p)
            # JSONL self validation above is Python only; native correctness gate
            # runs independently on all candidate binaries.
        self.corpi_info={r['id']:r for r in manifest}
        self.meta['corpus_files']=[{'id':r['id'],'bytes':r['bytes'],'kind':r['kind'],
                                  'distribution':r['distribution'],'sha256':r['sha256']} for r in manifest]
        atomic_json(self.root/'corpus_manifest.json',{'schema':1,'protocol':'prequal-v2-exploratory-60m',
                'seed':EXPLORATION_SEED,'scenarios':manifest})
        self.checkpoint(force=True)
        return results

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
           'elapsed_seconds':tdom,'method':'native_DOM_and_direct_stage1_stage2_median3_gcc_O3',
           'scenario':self.corpi_info[path.parent.name+'/'+path.name]['kind'],
           'distribution':self.corpi_info[path.parent.name+'/'+path.name]['distribution'],
           'size_target':self.corpi_info[path.parent.name+'/'+path.name]['size_target'],
           'sampling_bias':self.corpi_info[path.parent.name+'/'+path.name]['sample_spread_proxy']})
        path_csv=self.root/'map.csv'
        with path_csv.open('a',newline='',encoding='utf8') as f:
            w=csv.DictWriter(f,fieldnames=RESULT_FIELDS)
            if f.tell()==0:w.writeheader()
            w.writerow(self.rows[-1]);f.flush();os.fsync(f.fileno())
        self.checkpoint(phase)
    def abandon(self,tag,why):
        self.abandoned[tag]=why;self.status['abandoned_points']=self.abandoned
        self.failure('abandoned',tag,why)
    def explore(self):
        # Coverage-first randomized trial; never abandon a variant for being
        # merely slow. All designs are specified before first measurement.
        # Additional passes use the identical predeclared cases in a new order.
        import random
        tags=[tag for tag,*_ in catalog() if tag in self.binaries]
        if 'upstream_vls256' not in tags:raise RuntimeError('Official baseline unavailable')
        self.meta['ordering']='Fixed-seed randomized corpus order; rotating/reversed candidate order; shared corpus/trial control. No adaptive retuning.'
        self.meta['stages']='Direct stage1()/stage2(), independent public DOM parse()'
        for trial in range(1,1001):
            shuffled=list(self.corpi)
            random.Random(EXPLORATION_SEED+trial*313).shuffle(shuffled)
            for caseidx,path in enumerate(shuffled):
                self.check()
                n=path.stat().st_size
                iters=1024 if n<=2048 else 512 if n<=8192 else 96 if n<=65536 else 48 if n<=262144 else 24 if n<=1048576 else 12
                order=list(tags) if (caseidx+trial)%2 else list(reversed(tags))
                rot=(caseidx+trial//2)%len(order)
                order=order[rot:]+order[:rot]
                self.status['last_measurement_order']=order
                for tag in order:
                    if tag in self.abandoned:continue
                    self.status['current_candidate']=tag
                    try:self.measure('explore_fixed',tag,path,iters,trial)
                    except (Stopped,Safety):raise
                    except TimedOut:
                        if tag=='upstream_vls256':raise RuntimeError('Official baseline timed out')
                        self.abandon(tag,'90-second per-case timeout')
                    except Exception as exc:
                        if tag=='upstream_vls256':raise RuntimeError('Official baseline failed: '+str(exc))
                        self.abandon(tag,'measurement failure: '+str(exc)[-350:])
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
    p.add_argument('--hours',type=float,default=1.0)
    p.add_argument('--jobs',type=int,default=2);p.add_argument('--core',type=int,default=0)
    args=p.parse_args(argv)
    if not (0<args.hours<=MAX_HOURS):p.error('hours must be in (0,1.0]')
    if args.jobs not in (1,2):p.error('jobs must be 1 or 2')
    campaign=Campaign(args.source,args.workdir,args.hours,args.jobs,args.core)
    campaign.execute()
    print(json.dumps({'state':campaign.status['state'],'observations':len(campaign.rows),
      'reason':campaign.status['stop_reason']},ensure_ascii=False))
    return 0 if campaign.status['state'] in ('completed','stopped') else 1

if __name__=='__main__':raise SystemExit(main())
