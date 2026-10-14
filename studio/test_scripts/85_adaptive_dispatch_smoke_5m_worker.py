#!/usr/bin/env python3
"""RVV Engine Library: bounded 5-minute *mechanics* smoke, not a performance campaign.

All write operations stay under --workdir. No sudo, source edits, deletion of
previous runs, CMake, network cloning or evolutionary experiment selection. Build
stderr/stdout is saved in full locally; summary is embedded in metadata.json
for the existing SHA256-verified Studio sync contract.
"""
from __future__ import annotations
import argparse
import contextlib
import csv
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import zipfile

RUN_FILES = ('status.json', 'checkpoint.json', 'map.csv', 'ranking.csv',
             'hypotheses.md', 'failures.csv', 'metadata.json')
BUDGET_SECONDS = 300
GIB = 1024 ** 3
# A single build normally requires less than the five-minute total.
PLANS = [
    ('A2_quick_dispatch', {
        'SIMDJSON_RVV_ENGINE_LIBRARY':'1',
        'SIMDJSON_RVV_FORCE_PLAN':'0',
        'SIMDJSON_RVV_ENABLE_PACKED_CONTROL':'0',
        'SIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER':'0',
        'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL':'2',
    }),
]


def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def atomic_text(path, value):
    path=Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    with temp.open('w',encoding='utf-8') as f:
        f.write(value); f.flush(); os.fsync(f.fileno())
    os.replace(temp,path)


def atomic_json(path,obj):atomic_text(path,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


def read_tail(path, limit=16000):
    if not Path(path).is_file(): return ''
    with open(path,'rb') as f:
        f.seek(0,os.SEEK_END)
        f.seek(max(0,f.tell()-limit))
        return f.read().decode('utf-8','replace')[-limit:]


def extract_errors(output, limit=25):
    errors=[]
    lines=output.splitlines()
    for index,line in enumerate(lines):
        if re.search(r'(^|\s)(fatal error:|error:|FAILED:|CMake Error)',line,re.I):
            context='\n'.join(lines[max(0,index-2):min(len(lines),index+2)])
            if context not in errors: errors.append(context[:1000])
        if len(errors)>=limit:break
    return errors


class Halt(Exception): pass
class DiskStop(Exception): pass
class Timeout(Halt):pass


def run_command(args, log_path, *, workdir, deadline, timeout, stopfile, env=None):
    """Log all compiler output with no blocked PIPE; reap process groups on timeout."""
    log_path=Path(log_path)
    start=time.monotonic(); cutoff=min(deadline,start+timeout)
    with log_path.open('wb') as log:
        proc=subprocess.Popen([str(x) for x in args],cwd=workdir,stdin=subprocess.DEVNULL,
            stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=env)
        try:
            while proc.poll() is None:
                if Path(stopfile).exists():raise Halt('Graceful STOP requested')
                if time.monotonic()>=cutoff:raise Timeout(f'Timeout at {time.monotonic()-start:.1f}s')
                free=shutil.disk_usage(workdir).free
                if free < 200*1024**2:raise DiskStop(f'Disk safety floor: {free/GIB:.2f} GiB free')
                time.sleep(.25)
        except (Halt,DiskStop):
            with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGTERM)
            try:proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(ProcessLookupError):os.killpg(proc.pid,signal.SIGKILL)
                proc.wait()
            raise
        return proc.returncode,round(time.monotonic()-start,2)


class Smoke:
    def __init__(self,source,workdir,budget,jobs,core):
        self.source=Path(source).resolve();self.root=Path(workdir).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.started=time.monotonic();self.deadline=self.started+budget
        self.stopfile=self.root/'STOP';self.jobs=jobs;self.core=core
        self.success=[];self.probes=[];self.failures=[];self.built=False
        self.metadata={'schema':1,'purpose':'Adaptive Dispatch v2 A2 native GCC smoke / 5-minute budget, NO performance ranking',
                       'source':str(self.source),'plans':PLANS,'build_log_hint':'Full build logs retained in remote run folder',
                       'budget_seconds':budget,'compiler_diagnostics':[], 'trials':[]}
        self.state={'schema':1,'state':'starting','observations':0,'current_candidate':'',
                    'started_utc':now(),'last_update':now(),'stop_reason':None,
                    'source':str(self.source),'budget_seconds':budget}

    def check(self):
        if self.stopfile.exists():raise Halt('Graceful STOP requested')
        if time.monotonic()>=self.deadline:raise Timeout('Five-minute remote execution budget reached')
        free=shutil.disk_usage(self.root).free
        self.state['disk_free_gib']=round(free/GIB,3)
        self.state['disk_free_mib']=round(free/(1024**2),1)
        self.state['disk_safety_floor_mib']=200
        self.state['disk_monitor_interval_seconds']=900
        instant=time.monotonic()
        if instant-getattr(self,'last_disk_monitor_monotonic',float('-inf'))>=900:
            self.last_disk_monitor_monotonic=instant
            self.state['disk_last_15m_check_utc']=now()
            self.metadata.setdefault('disk_monitor_15m',[]).append({'utc':now(),'free_mib':round(free/(1024**2),1)})
        if free<200*1024**2:raise DiskStop(f'Disk safety floor: {free/GIB:.2f} GiB free')

    def checkpoint(self,state=None):
        if state:self.state['state']=state
        self.state['last_update']=now()
        self.state['observations']=len(self.probes)
        with contextlib.suppress(OSError):self.state['disk_free_gib']=round(shutil.disk_usage(self.root).free/GIB,3)
        atomic_json(self.root/'status.json',self.state)
        atomic_json(self.root/'checkpoint.json',{'updated_utc':now(),'observations':len(self.probes),
                    'elapsed_seconds':round(time.monotonic()-self.started,2)})
        atomic_json(self.root/'metadata.json',self.metadata)
        with (self.root/'failures.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=('time','step','candidate','error'))
            w.writeheader();w.writerows(self.failures)
        with (self.root/'map.csv').open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=('timestamp','phase','variant','result','duration_seconds','note'))
            w.writeheader();w.writerows(self.probes)
        atomic_text(self.root/'ranking.csv','variant,metric,paired_n,geomean_ratio,mad_ratio\n')
        atomic_text(self.root/'hypotheses.md',
            '# Five-minute Adaptive Dispatch v2 A2 mechanical smoke\n\nNo performance comparison or ranking is performed.\n'
            'The goal is compile, launch, preserve GCC diagnostics, and stop within five minutes.\n')
        self.snapshot()

    def snapshot(self):
        staging=self.root/'snapshot.zip.tmp';dest=self.root/'snapshot.zip'
        manifest={'schema':1,'files':[]}
        with zipfile.ZipFile(staging,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
            for name in RUN_FILES:
                p=self.root/name
                if p.is_file():
                    body=p.read_bytes();manifest['files'].append({'name':name,'bytes':len(body),
                                                    'sha256':hashlib.sha256(body).hexdigest()})
                    z.writestr(name,body)
            z.writestr('MANIFEST.json',json.dumps(manifest,sort_keys=True))
        os.replace(staging,dest)
        atomic_text(self.root/'snapshot.sha256',hashlib.sha256(dest.read_bytes()).hexdigest()+'\n')

    def failure(self,step,tag,message):
        self.failures.append({'time':now(),'step':step,'candidate':tag,'error':str(message)[-7500:]})
        self.checkpoint()

    def validate_source(self):
        mandatory=('CMakeLists.txt','include/simdjson/simdjson_version.h','src/rvv.cpp',
          'src/rvv/stage1.h','src/rvv/engines/engine_plan.h',
          'src/rvv/engines/structural_writers.h','src/rvv/engines/workload_profile.h',
          'src/rvv/engines/stage2_bridge.h','scripts/rvv/engines/rvv_engine_smoke_probe.cpp')
        missing=[p for p in mandatory if not (self.source/p).is_file()]
        if missing:raise RuntimeError('Incomplete engine source snapshot: '+', '.join(missing))
        version=(self.source/'include/simdjson/simdjson_version.h').read_text(encoding='utf-8')
        if not re.search(r'^#define SIMDJSON_VERSION\s+"5\.0\.3"',version,re.M):
            raise RuntimeError('Source is not simdjson v5.0.3')
        # Inspect the same entry file that GCC will compile.
        head=(self.source/'src/rvv/engines/structural_writers.h').read_text(encoding='utf-8')
        self.metadata['structural_writer_sha256']=hashlib.sha256(head.encode()).hexdigest()
        if 'SIMDJSON_RVV_ADAPTIVE_V2_LEVEL' not in (
              self.source/'src/rvv/engines/engine_plan.h').read_text(encoding='utf8'):
            raise RuntimeError('Missing Adaptive Dispatch v2 in source snapshot')
        self.metadata['compiler_target']='src/simdjson.cpp and a hand-written JSON parser probe (direct native GCC, no CMake)'
        self.metadata['uname']=subprocess.check_output(['uname','-m'],text=True).strip()
        if self.metadata['uname']!='riscv64':raise RuntimeError('Native RISC-V required')
        if shutil.disk_usage(self.root).free < 200*1024**2:
            raise DiskStop('Below 200 MiB disk safety floor before build')

    def build(self, tag, defines, ordinal):
        """Compile the REAL simdjson translation unit without CMake or CPM deps.

        A hard compiler error is a useful failure, not a reason to rebuild the
        same broken library with fifteen other macro combinations.
        """
        self.state['current_candidate']=tag
        self.checkpoint('build')
        cxx=shutil.which('g++')
        if not cxx:raise RuntimeError('Native g++ is missing')
        folder=self.root/'scratch_build'
        folder.mkdir(parents=True,exist_ok=True)
        try:
            # Avoid benchmark generation, testing dependencies and Google
            # Benchmark / simdjson-data network downloads entirely.
            flags=[cxx,'-std=c++17','-O1','-g0','-pthread',
                '-mabi=lp64d','-march=rv64gcv',
                '-DSIMDJSON_IMPLEMENTATION_RVV=1',
                '-DSIMDJSON_IMPLEMENTATION_RVV_VLS=0',
                '-DSIMDJSON_IMPLEMENTATION_FALLBACK=1',
                '-I'+str(self.source/'include'),'-I'+str(self.source/'src'),
                *[f'-D{k}={v}' for k,v in sorted(defines.items())]]
            source=self.source/'src/simdjson.cpp'
            object_file=folder/'simdjson.o'
            compile_log=self.root/f'build_{tag}.log'
            remaining=self.deadline-time.monotonic()
            if remaining<35:return False
            try:
                rc,seconds=run_command([*flags,'-c',str(source),'-o',str(object_file)],
                    compile_log,workdir=folder,deadline=self.deadline,
                    timeout=min(220,max(5,remaining-20)),stopfile=self.stopfile)
            except Timeout as exc:
                self.record_log('build_timeout',tag,compile_log,124)
                self.metadata['trials'].append({'tag':tag,'phase':'build','timeout':str(exc)})
                return False
            self.metadata['trials'].append({'tag':tag,'phase':'build','rc':rc,'seconds':seconds})
            if rc!=0:
                self.record_log('build',tag,compile_log,rc)
                return False
            remaining=self.deadline-time.monotonic()
            if remaining<20:
                self.failure('budget',tag,'Compilation passed, insufficient budget to link and run probe')
                return False
            binary=folder/'rvv_engine_smoke'
            probe=self.source/'scripts/rvv/engines/rvv_engine_smoke_probe.cpp'
            link_log=self.root/f'link_{tag}.log'
            try:
                rc,seconds=run_command([*flags,str(probe),str(object_file),'-o',str(binary)],
                    link_log,workdir=folder,deadline=self.deadline,
                    timeout=min(60,max(5,remaining-15)),stopfile=self.stopfile)
            except Timeout as exc:
                self.record_log('link_timeout',tag,link_log,124)
                self.metadata['trials'].append({'tag':tag,'phase':'link','timeout':str(exc)})
                return False
            self.metadata['trials'].append({'tag':tag,'phase':'link','rc':rc,'seconds':seconds})
            if rc!=0:
                self.record_log('link',tag,link_log,rc)
                return False
            self.built=True;self.success.append(tag)
            remaining=self.deadline-time.monotonic()
            if remaining<6:
                self.failure('budget',tag,'Build passed but runtime could not start within budget')
                return False
            probe_log=self.root/f'probe_{tag}.log'
            try:
                rc,seconds=run_command(['taskset','-c',str(self.core),str(binary)],
                    probe_log,workdir=folder,deadline=self.deadline,
                    timeout=min(25,max(3,remaining-3)),stopfile=self.stopfile)
            except Timeout:
                self.record_log('probe_timeout',tag,probe_log,124)
                self.probes.append({'timestamp':now(),'phase':'smoke','variant':tag,
                      'result':'FAIL','duration_seconds':0,'note':'runtime timeout'})
                return False
            output=read_tail(probe_log,2048)
            result='PASS' if rc==0 and 'RVV_SMOKE_OK' in output else 'FAIL'
            self.probes.append({'timestamp':now(),'phase':'smoke','variant':tag,
                'result':result,'duration_seconds':seconds,
                'note':'RVV runtime parse check, not throughput; '+output[-250:]})
            if result!='PASS':self.record_log('probe',tag,probe_log,rc)
            self.checkpoint('smoke')
            return result=='PASS'
        finally:
            # All generated object files are confined to this run's scratch.
            if folder.exists():shutil.rmtree(folder)

    def record_log(self,step,tag,path,rc):
        tail=read_tail(path)
        errors=extract_errors(tail)
        self.metadata['compiler_diagnostics'].append({'tag':tag,'step':step,'returncode':rc,
            'log':Path(path).name,'errors':errors,'tail':tail[-10000:]})
        self.failure(step,tag,'returncode='+str(rc)+'; '+'\n'.join(errors or tail.splitlines()[-10:]))

    def execute(self):
        # Run-level lock matches the established 3-hour/8-hour machinery.
        import fcntl
        lock=self.root.parent/'.night_runner_global.lock'
        with lock.open('w') as f:
            fcntl.flock(f.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
            f.write(str(os.getpid()));f.flush()
            try:
                self.checkpoint('preflight')
                self.check()
                self.validate_source()
                self.metadata['compiler_version']=subprocess.check_output(['g++','--version'],text=True).splitlines()[0]
                # Prioritize the main dynamic plan; try fallbacks only if time remains.
                for index,(tag,defines) in enumerate(PLANS):
                    self.check()
                    if self.deadline-time.monotonic()<35:break
                    passed=self.build(tag,defines,index)
                    if passed:break  # mechanical success, no optimization search
                    # No compiler retry with another plan after a hard error:
                    # the same translation unit still fails. Save diagnosis.
                    if any(d['step'] in ('build','link','probe') for d in self.metadata['compiler_diagnostics']):
                        break
                if self.built and any(x['result']=='PASS' for x in self.probes):
                    self.state['state']='completed'
                    self.state['stop_reason']='Native RVV-VLA compilation and execution passed'
                elif self.built:
                    self.state['state']='failed'
                    self.state['stop_reason']='Build passed but runtime smoke failed'
                else:
                    self.state['state']='failed'
                    self.state['stop_reason']='No RVV-VLA build succeeded; inspect compiler_diagnostics in metadata.json'
            except Timeout as exc:
                self.state['state']='stopped';self.state['stop_reason']=str(exc)
            except Halt as exc:
                self.state['state']='stopped';self.state['stop_reason']=str(exc)
            except DiskStop as exc:
                self.state['state']='safety_stop';self.state['stop_reason']=str(exc)
            except Exception as exc:
                self.state['state']='failed';self.state['stop_reason']=repr(exc)[:1500]
                self.failures.append({'time':now(),'step':'fatal','candidate':self.state['current_candidate'],
                   'error':repr(exc)[:7000]})
            finally:
                self.metadata['elapsed_seconds']=round(time.monotonic()-self.started,2)
                self.checkpoint()


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument('--source',required=True)
    p.add_argument('--workdir',required=True)
    p.add_argument('--seconds',type=int,default=300)
    p.add_argument('--jobs',type=int,default=2)
    p.add_argument('--core',type=int,default=0)
    a=p.parse_args(argv)
    if not 0<a.seconds<=BUDGET_SECONDS: p.error('seconds must be between 1 and 300')
    if a.jobs not in (1,2):p.error('jobs must be 1 or 2')
    smoke=Smoke(a.source,a.workdir,a.seconds,a.jobs,a.core)
    smoke.execute()
    print(json.dumps({'state':smoke.state['state'],'observations':len(smoke.probes),
                      'stop_reason':smoke.state.get('stop_reason')},ensure_ascii=False))
    return 0 if smoke.state['state']=='completed' else 1


if __name__=='__main__':raise SystemExit(main())
