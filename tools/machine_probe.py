#!/usr/bin/env python3
"""Cross-machine hardware inventory + short CPU/memory/JSON benchmarks.

Python >=3.8, Linux, no pip requirements, optional C11 compiler for native tests.
No root or network access. Read-only except temp benchmark data and result files.
"""
from __future__ import annotations

import argparse
import datetime as datetime
import gc
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

VERSION = "1.0"
MIB = 1024 ** 2
GIB = 1024 ** 3

NATIVE_SOURCE = r'''#define _POSIX_C_SOURCE 200809L
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static double clock_seconds(void) {
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC, &t) != 0) return -1;
    return (double)t.tv_sec + (double)t.tv_nsec * 1e-9;
}
static volatile uint64_t result_sink = 0;
int main(int argc, char **argv) {
    if (argc < 3) return 2;
    uint64_t n = strtoull(argv[2], 0, 10);
    if (n == 0) return 3;
    double start = clock_seconds();
    if (strcmp(argv[1], "cpu") == 0) {
        uint64_t x = 0x9e3779b97f4a7c15ULL;
        for (uint64_t i = 0; i < n; i++) {
            x ^= x >> 12;
            x ^= x << 25;
            x ^= x >> 27;
            x *= UINT64_C(2685821657736338717);
        }
        result_sink = x;
    } else if (strcmp(argv[1], "memory") == 0 && argc >= 4) {
        size_t bytes = (size_t)strtoull(argv[3], 0, 10);
        if (bytes < 4096 || bytes > 268435456ULL) return 4;
        unsigned char *a = (unsigned char*)malloc(bytes);
        unsigned char *b = (unsigned char*)malloc(bytes);
        if (!a || !b) { free(a); free(b); return 5; }
        for (size_t i = 0; i < bytes; i++) { a[i] = (unsigned char)(i * 13u + 29u); b[i] = 0; }
        start = clock_seconds();
        uint64_t chk = 0;
        for (uint64_t i = 0; i < n; i++) {
            memcpy(b, a, bytes);
            unsigned char *tmp = a; a = b; b = tmp;
            chk += ((volatile unsigned char*)a)[(i * 65537u) % bytes];
        }
        result_sink = chk;
        free(a); free(b);
    } else return 6;
    double elapsed = clock_seconds() - start;
    if (!(elapsed > 0.)) return 7;
    printf("%.9f %llu\n", elapsed, (unsigned long long)result_sink);
    return 0;
}
'''


def read_text(path, limit=16384):
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")[:limit]
    except (OSError, UnicodeError):
        return ""


def run(cmd, timeout=8):
    try:
        p = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=timeout, check=False)
        if p.returncode == 0:
            return p.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError, OverflowError):
        return None


def os_release():
    raw = read_text('/etc/os-release')
    for line in raw.splitlines():
        if line.startswith('PRETTY_NAME='):
            return line.partition('=')[2].strip().strip('"')
    return platform.platform()


def proc_meminfo():
    data = {}
    for line in read_text('/proc/meminfo').splitlines():
        key, sep, val = line.partition(':')
        if sep:
            match = re.match(r'\s*(\d+)\s+kB', val)
            if match:
                data[key] = int(match.group(1)) * 1024
    return data


def cgroup_memory_limit():
    for p in ('/sys/fs/cgroup/memory.max', '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        value = read_text(p).strip()
        if value.isdigit():
            n = int(value)
            if 0 < n < 1 << 60:
                return n
    return None


def cgroup_cpu_quota():
    value = read_text('/sys/fs/cgroup/cpu.max').split()
    if len(value) == 2 and value[0].isdigit() and value[1].isdigit() and int(value[1]):
        return round(int(value[0]) / int(value[1]), 3)
    quota = read_text('/sys/fs/cgroup/cpu/cpu.cfs_quota_us').strip()
    period = read_text('/sys/fs/cgroup/cpu/cpu.cfs_period_us').strip()
    if quota.isdigit() and period.isdigit() and int(period):
        return round(int(quota) / int(period), 3)
    return None


def cpuinfo():
    contents = read_text('/proc/cpuinfo', limit=262144)
    first = contents.split('\n\n')[0]
    pairs = {}
    for line in first.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            pairs[k.strip().lower()] = v.strip()
    return pairs


def lscpu():
    output = run(['lscpu', '-J'])
    if output:
        try:
            entries = json.loads(output).get('lscpu', [])
            return {x['field'].rstrip(':').strip(): x.get('data') for x in entries if x.get('field')}
        except (KeyError, ValueError, TypeError):
            pass
    output = run(['lscpu'])
    result = {}
    for line in output.splitlines():
        if ':' in line:
            k, v = line.split(':', 1)
            result[k.strip()] = v.strip()
    return result


def caches():
    result = []
    for p in sorted(Path('/sys/devices/system/cpu/cpu0/cache').glob('index*')):
        result.append({
            'level': read_text(p / 'level').strip() or None,
            'type': read_text(p / 'type').strip() or None,
            'size': read_text(p / 'size').strip() or None,
        })
    return result


def disk_mount():
    usage = shutil.disk_usage('.')
    info = {'path': str(Path('.').resolve()),
            'total_gib': round(usage.total/GIB, 2),
            'free_gib': round(usage.free/GIB, 2)}
    fs = run(['df', '-PT', '.'])
    lines = fs.splitlines()
    if len(lines) > 1:
        chunks = lines[-1].split()
        if len(chunks) >= 7:
            info['filesystem_type'] = chunks[1]
            info['mountpoint'] = chunks[-1]
    return info


def hardware():
    info = cpuinfo()
    lc = lscpu()
    memory = proc_meminfo()
    aff = None
    try:
        aff = len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        pass
    name = (lc.get('Model name') or lc.get('Model') or info.get('model name')
            or info.get('uarch') or info.get('cpu') or 'not reported')
    isa = info.get('isa') or lc.get('ISA')
    flags = info.get('flags') or info.get('features') or ''
    allowed = ['rv64', 'rv32', 'rvv', 'avx512', 'avx2', 'sse4', 'neon', 'sve']
    features = [t for t in flags.split() if any(n in t.lower() for n in allowed)][:32]
    cpufreq = []
    for path in ('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq',
                 '/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq'):
        val = read_text(path).strip()
        if val.isdigit():
            cpufreq.append(round(int(val) / 1000, 1))
        else:
            cpufreq.append(None)
    arch = platform.machine()
    if 'riscv' in arch.lower():
        note = 'Native RISC-V architecture reported by this process.'
    elif 'riscv' in platform.node().lower() or 'riscv' in str(name).lower():
        note = 'Host appears to be a RISC-V login/front-end, but the current CPU architecture is not RISC-V.'
    else:
        note = 'Architecture is not identified as native RISC-V.'
    return {
        'hostname': platform.node(), 'architecture': arch, 'architecture_note': note,
        'kernel': platform.release(), 'operating_system': os_release(),
        'python': platform.python_version(), 'cpu_model': name,
        'cpu_logical': os.cpu_count(), 'cpu_allowed_by_affinity': aff,
        'cgroup_cpu_quota_cores': cgroup_cpu_quota(),
        'sockets': lc.get('Socket(s)'), 'cores_per_socket': lc.get('Core(s) per socket'),
        'threads_per_core': lc.get('Thread(s) per core'),
        'cpu_current_mhz': cpufreq[0], 'cpu_max_mhz': cpufreq[1],
        'cpu_governor': read_text('/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor').strip() or None,
        'isa': isa, 'riscv_vlenb': info.get('vlenb'),
        'features_selected': features, 'cpu_caches': caches(),
        'memory_total_gib': round(memory.get('MemTotal',0)/GIB,3) if memory.get('MemTotal') else None,
        'memory_available_gib': round(memory.get('MemAvailable',0)/GIB,3) if memory.get('MemAvailable') else None,
        'cgroup_memory_limit_gib': round(cgroup_memory_limit()/GIB,3) if cgroup_memory_limit() else None,
        'disk': disk_mount(),
        'compiler_candidates': {name: run([exe,'--version']).splitlines()[0] for name in ('gcc','clang','cc')
                                if (exe := shutil.which(name)) and run([exe, '--version'])},
    }


def native_run(exe, mode, n, mem_size=None):
    cmd = [str(exe), mode, str(n)]
    if mem_size is not None:
        cmd.append(str(mem_size))
    out = run(cmd, timeout=20)
    bits = out.split()
    if len(bits) != 2:
        raise RuntimeError('Native runner failed: ' + mode)
    sec = float(bits[0])
    if not math.isfinite(sec) or sec <= 0:
        raise RuntimeError('Invalid native benchmark clock')
    return sec


def calibrate_native(exe, mode, base, mem_size, target=0.35):
    n = base
    for _ in range(3):
        sec = native_run(exe, mode, n, mem_size)
        if sec >= target * .5:
            break
        n = max(n+1, min(500000000, int(n * min(20, target/max(.001,sec)))))
    return min(n,500000000)


def native_bench(directory, hw):
    compiler = next((shutil.which(x) for x in ('cc','gcc','clang') if shutil.which(x)), None)
    if not compiler:
        return {}, 'No C compiler detected; native CPU and memcpy tests unavailable.'
    source = directory/'microbench.c'
    exe = directory/'microbench'
    source.write_text(NATIVE_SOURCE, encoding='ascii')
    cmd = [compiler, '-O3', '-std=c11', '-DNDEBUG', '-D_POSIX_C_SOURCE=200809L',
           str(source), '-o', str(exe)]
    build = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=30, check=False)
    if build.returncode != 0:
        return {}, f'Native compilation failed: {build.stderr.strip()[-400:]}'
    mem_gib = hw.get('memory_available_gib') or 1
    lim = hw.get('cgroup_memory_limit_gib')
    if lim is not None:
        mem_gib = min(mem_gib, lim)
    block = 32*MIB if mem_gib >= 1 else (8*MIB if mem_gib >= .25 else 2*MIB)
    result = {}
    n = calibrate_native(exe, 'cpu', 2000000, None)
    times = [native_run(exe,'cpu',n) for _ in range(3)]
    result['native_cpu_million_iterations_per_sec'] = round(statistics.median(n / t for t in times) / 1e6, 3)
    result['native_cpu_calibrated_iterations'] = n
    n_mem = calibrate_native(exe, 'memory', 8, block)
    tmem = [native_run(exe,'memory',n_mem,block) for _ in range(3)]
    result['native_memcpy_gib_per_sec'] = round(statistics.median(n_mem * block/t/GIB for t in tmem),3)
    result['native_memcpy_block_mib'] = block // MIB
    result['native_memcpy_repetitions'] = n_mem
    result['native_compiler'] = Path(compiler).name
    return result, None


def json_bench():
    # Fixed data, utf-8, no external packages; CPU Python benchmark only.
    lines = [{'id': i, 'name': f'user_{i%1000}', 'values': [i%997,(i*19)%997,(i*7)%997],
              'valid': i%3==0, 'text': 'a short JSON string'} for i in range(15000)]
    payload = json.dumps(lines, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
    del lines
    reps = 1
    t = 0
    while True:
        start = time.perf_counter()
        for _ in range(reps):
            item = json.loads(payload)
            if len(item) != 15000:
                raise RuntimeError('JSON parser incorrect item count')
        t = time.perf_counter() - start
        if t >= .3 or reps >= 256:
            break
        reps = min(256,max(reps+1,int(reps*.35/max(.001,t))))
    samples = []
    was_enabled = gc.isenabled()
    try:
        gc.disable()
        for _ in range(3):
            start = time.perf_counter()
            for _ in range(reps):
                items = json.loads(payload)
                if len(items) != 15000:
                    raise RuntimeError('Invalid JSON parse result')
            sec = time.perf_counter() - start
            samples.append(len(payload)*reps / sec / 1e6)
    finally:
        if was_enabled:gc.enable()
    return {'python_json_mb_per_sec':round(statistics.median(samples),3),
            'python_json_payload_mib':round(len(payload)/MIB,3),
            'python_json_repetitions':reps}


def disk_bench(target_dir):
    # Optional; fsync included in write, read may hit page cache.
    chunk = bytes([x%251 for x in range(4096)])*256
    samples = []
    with tempfile.TemporaryDirectory(prefix='machine-disk-',dir=target_dir) as temp:
        path = Path(temp)/'data.bin'
        start = time.perf_counter()
        with path.open('wb') as f:
            for _ in range(32):
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
        elapsed = time.perf_counter() - start
        samples.append(32*MIB/elapsed/MIB)
        start = time.perf_counter()
        numbytes = 0
        with path.open('rb') as f:
            while True:
                data = f.read(1024*1024)
                if not data:break
                numbytes += len(data)
        elapsed2 = time.perf_counter() - start
    return {'disk_write_fsync_mib_per_sec':round(samples[0],3),
            'disk_read_cached_mib_per_sec':round(numbytes/elapsed2/MIB,3),
            'disk_bench_note':'32 MiB temporary file; read may be served by OS page cache.'}


def fmt(value, suffix=''):
    if value is None:
        return 'N/A'
    return str(value)+suffix


def format_report(report):
    h=report['hardware'];b=report['benchmarks'];notes=report['notes'];label=report['label']
    out=[f'# Machine snapshot — {label}', '',
        f'- UTC: {report["timestamp_utc"]}',
        f'- Host: `{h["hostname"]}`',
        f'- OS: {h["operating_system"]} / kernel {h["kernel"]}',
        f'- Architecture: **{h["architecture"]}** — {h["architecture_note"]}',
        f'- CPU: {h["cpu_model"]}',
        f'- Logical CPUs / affinity CPUs: {fmt(h["cpu_logical"])} / {fmt(h["cpu_allowed_by_affinity"])}',
        f'- CPU quota (cgroup cores): {fmt(h["cgroup_cpu_quota_cores"])}',
        f'- RAM total / available: {fmt(h["memory_total_gib"]," GiB")} / {fmt(h["memory_available_gib"]," GiB")}',
        f'- Cgroup memory limit: {fmt(h["cgroup_memory_limit_gib"]," GiB")}',
        f'- Disk free: {h["disk"]["free_gib"]} GiB ({h["disk"].get("filesystem_type","unknown FS")})',
        f'- CPU governor/current/max MHz: {fmt(h["cpu_governor"])} / {fmt(h["cpu_current_mhz"])} / {fmt(h["cpu_max_mhz"])}',
        f'- RISC-V ISA: {fmt(h["isa"])}',
        f'- RVV VLENB, if reported: {fmt(h["riscv_vlenb"])}',
        f'- Cache: {", ".join(str(x["level"])+str(x["type"])+" "+str(x["size"]) for x in h["cpu_caches"]) or "N/A"}',
        '', '## Quick performance', '',
        '| Metric | Result | What it measures |',
        '|---|---:|---|',
        f'| Native scalar integer loop | {fmt(b.get("native_cpu_million_iterations_per_sec")," M iterations/s")} | Single-thread scalar C integer arithmetic, not RVV |',
        f'| Native memcpy | {fmt(b.get("native_memcpy_gib_per_sec")," GiB/s")} | Single-thread libc memcpy, warm buffers; memory hierarchy effects |',
        f'| Python JSON parser | {fmt(b.get("python_json_mb_per_sec")," MB/s")} | Standard-library JSON parser; Python/runtime dependent |',
        f'| Disk write (opt-in) | {fmt(b.get("disk_write_fsync_mib_per_sec")," MiB/s")} | Sequential 32 MiB file with fsync |',
        f'| Disk read (opt-in) | {fmt(b.get("disk_read_cached_mib_per_sec")," MiB/s")} | Read often served from page cache |',
        '', '## Notes', '']
    out.extend(f'- {note}' for note in notes)
    out += ['', '## Reproducibility', '',
        f'- Probe version: {VERSION}',
        f'- Python: {h["python"]}',
        f'- Compilers found: {", ".join(h["compiler_candidates"].values()) or "none"}',
        '- Each metric uses the median of three measurements after warmup/calibration.',
        '- Values compare hardware + toolchain + runtime settings; they are NOT simdjson/RVV parser speedups.',
        '- Do not benchmark on a shared login node without site permission; run on an allocated compute node.',
        '']
    return '\n'.join(out)


def compare(a,b):
    h1,h2=a['hardware'],b['hardware']; x,y=a['benchmarks'],b['benchmarks']
    title=f'# Machine comparison — {a["label"]} vs {b["label"]}'
    out=[title,'', 'All percentages below compare **B relative to A**; positive means B achieved higher throughput.',
         '', '| Field | A: '+a['label']+' | B: '+b['label']+' | B vs A |', '|---|---:|---:|---:|']
    rows=[('Architecture','architecture',None),('CPU model','cpu_model',None),('CPU affinity','cpu_allowed_by_affinity',None),('RAM GiB','memory_total_gib',None),
          ('Native integer M iterations/s','native_cpu_million_iterations_per_sec','bench'),
          ('Native memcpy GiB/s','native_memcpy_gib_per_sec','bench'),
          ('Python JSON MB/s','python_json_mb_per_sec','bench'),
          ('Disk write fsync MiB/s','disk_write_fsync_mib_per_sec','bench')]
    for name,key,kind in rows:
        v1,v2=(x.get(key),y.get(key)) if kind=='bench' else (h1.get(key),h2.get(key))
        delta='—'
        if kind=='bench' and isinstance(v1,(int,float)) and isinstance(v2,(int,float)) and v1>0:
            delta=f'{(v2/v1-1)*100:+.1f}%'
        out.append(f'| {name} | {fmt(v1)} | {fmt(v2)} | {delta} |')
    out.extend(['','**Caution:** Different architectures, Python builds, loaded systems, cache sizes and frequency governors affect these numbers. EPCC `riscv-login` is an x86 front-end; do not describe it as a RISC-V compute node.',''])
    return '\n'.join(out)


def main():
    parser=argparse.ArgumentParser(description='Small hardware snapshot and machine benchmark; no pip packages')
    parser.add_argument('--label',default=None,help='Output label, e.g. cloud-v / epcc-login / epcc-riscv')
    parser.add_argument('--output-dir',type=Path,default=Path.cwd(),help='Where to write the JSON+Markdown')
    parser.add_argument('--specs-only',action='store_true',help='Safe inventory on a shared login node; no benchmark')
    parser.add_argument('--no-native',action='store_true',help='Skip native CPU and memcpy tests')
    parser.add_argument('--disk',action='store_true',help='Opt-in short 32 MiB temporary disk test')
    parser.add_argument('--compare',nargs=2,type=Path,metavar=('MACHINE_A_JSON','MACHINE_B_JSON'),help='Write machine comparison Markdown instead of benchmarking')
    args=parser.parse_args()
    args.output_dir.mkdir(parents=True,exist_ok=True)
    if args.compare:
        with args.compare[0].open(encoding='utf-8') as f:a=json.load(f)
        with args.compare[1].open(encoding='utf-8') as f:b=json.load(f)
        content=compare(a,b)
        path=args.output_dir/'machine_comparison.md'
        path.write_text(content,encoding='utf-8')
        print(content)
        print('SAVED',path)
        return
    label=args.label or platform.node() or 'machine'
    label_safe=re.sub('[^A-Za-z0-9_-]+','-',label)[:48] or 'machine'
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    print('Collecting hardware specs for',label,'...',flush=True)
    h=hardware();b={};notes=[]
    if not args.specs_only:
        if not args.no_native:
            with tempfile.TemporaryDirectory(prefix='rvvlab-machineprobe-') as temp:
                try:
                    result,error=native_bench(Path(temp),h)
                    b.update(result)
                    if error:notes.append(error)
                except (RuntimeError, subprocess.TimeoutExpired, OSError, ValueError) as exc:
                    notes.append('Native test failed: '+str(exc))
        print('Running Python JSON parse test...',flush=True)
        b.update(json_bench())
        if args.disk:
            if h['disk']['free_gib'] < .2:
                notes.append('Disk test skipped: < 200 MiB free.')
            else:
                b.update(disk_bench(Path.cwd()))
    else:
        notes.append('Specs-only mode: no benchmark was run.')
    notes.append('This is a compact microbenchmark; not a substitute for a native RVV-specific simdjson benchmark.')
    report={'schema':'rvvlab-machine-probe-v1','version':VERSION,'label':label,
            'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'hardware':h,'benchmarks':b,'notes':notes}
    dst=args.output_dir/f'machine_{label_safe}_{stamp}'
    report_json=dst.with_suffix('.json');report_md=dst.with_suffix('.md')
    report_json.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    report_md.write_text(format_report(report),encoding='utf-8')
    print('\n'+format_report(report))
    print('SAVED JSON',report_json)
    print('SAVED MD  ',report_md)

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrupted; temporary files are cleaned up.',file=sys.stderr)
        sys.exit(130)
