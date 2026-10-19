# RVV-VLA Lab — Two-machine hardware probe and quick performance benchmark

**Use:** native Linux on Cloud-V, EPCC compute nodes, or other Linux hosts; Python 3.8+, no `pip`, root permissions, SSH credentials or network calls. C compiler optional (`cc`, `gcc`, `clang`); the script uses a temporary working directory for a tiny native C11 benchmark and deletes the binary afterward. It does not touch ongoing Studio/Slurm jobs.

This is deliberately a **small machine inventory and microbenchmark**, **not** a simdjson or RVV-specific benchmark. It typically takes **seconds to tens of seconds**, including native compilation, when a compiler is installed.

## Run from each Linux machine

Copy `tools/machine_probe.py` to the machine, or extract the entire ZIP at the root of the existing `RVV-VLA-Lab` repo on both machines. From the repository root:

```bash
# Cloud-V RISC-V machine (run when it has spare capacity)
python3 tools/machine_probe.py --label cloud-v --output-dir ./machine_reports

# EPCC FRONT-END (x86 login): inventory ONLY, no CPU benchmarking on shared login
python3 tools/machine_probe.py --label epcc-login --specs-only --output-dir ./machine_reports

# EPCC native RISC-V compute node, inside an allocated compute session/job:
python3 tools/machine_probe.py --label epcc-riscv --output-dir ./machine_reports
```

You can also use `sh RUN_MACHINE_PROBE.sh --label cloud-v --output-dir ./machine_reports`.

**EPCC architecture warning:** `riscv-login.epcc.ed.ac.uk` is an **x86_64 login/front-end**. A performance run there does **not** measure RISC-V. First connect through `gustave@gateway.epcc.ed.ac.uk`, obtain an **allocated RISC-V compute node** through the EPCC job scheduler (according to site policy), and run the full benchmark there. This script doesn't request an allocation for you and doesn't bypass gateway MFA.

## What it collects

- Machine hostname, UTC run time, OS, kernel, native architecture, CPU model, CPU counts/affinity and cgroup quota, package/core/thread topology, governor, available clock readings, cache levels/sizes, RISC-V ISA and `vlenb` **if exposed by Linux**.
- Physical memory total/available and container/cgroup limit, working filesystem type, total and free disk space, compiler and Python versions.
- **Native CPU scalar arithmetic:** `-O3` C11 one-thread 64-bit integer dependency loop, millions of iterations per second (M iterations/s). **Not a vector/RVV score.**
- **Native memory copy:** one-thread warmed `libc memcpy` on 2–32 MiB buffers (depending on RAM limits), GiB/s. Cache effects included; not a DDR peak-bandwidth measurement.
- **Python JSON parser:** standard-library `json.loads` on the **same deterministic 1–2 MiB** generated document, throughput MB/s. This includes Python overhead and is **not equivalent to simdjson**.
- Optional **disk:** `--disk` writes/fsyncs and re-reads a temporary 32 MiB file (read may come from the OS page cache). Without `--disk`, **no disk performance test is run**.

All performance metrics use the **median of three calibrated samples**. Missing data is reported as N/A, never invented. The benchmark is single-threaded and controlled for the same workload, but compiler quality, CPU frequency, load and memory hierarchy vary; compare trends rather than treating percentages as perfect hardware equivalence.

## Outputs and automated comparison

Each run writes two **local** files:

```
machine_reports/machine_cloud-v_YYYYMMDDTHHMMSSZ.json
machine_reports/machine_cloud-v_YYYYMMDDTHHMMSSZ.md
```

Retrieve both JSON files to a common directory (e.g. your Windows workstation; you can use `scp` or SFTP). Compare **B against A**:

```powershell
python tools\machine_probe.py --compare .\machine_cloud-v_20261013T120000Z.json .\machine_epcc-riscv_20261013T123000Z.json --output-dir .
```

This produces `machine_comparison.md` including **% B vs A** for the measured CPU, memory and Python JSON metrics. `+20%` means B delivered 20% *higher throughput* for that specific test. A missing benchmark (`--specs-only`, no C compiler) is reported as unavailable.

## Optional Windows → server file transfer

Cloud-V: supply the verified Cloud-V SSH host/user/port from Studio when using `scp -P <port> ...`. EPCC after SSH authentication works and internal account access is confirmed:

```powershell
scp -o ProxyJump=gustave@gateway.epcc.ed.ac.uk .\tools\machine_probe.py gustave@riscv-login.epcc.ed.ac.uk:~/machine_probe.py
ssh -J gustave@gateway.epcc.ed.ac.uk gustave@riscv-login.epcc.ed.ac.uk
# On the EPCC front-end:
python3 ~/machine_probe.py --label epcc-login --specs-only --output-dir ~/
```

The gateway's prior `Connection closed` problem is **not solved by this benchmark**. SSH access must work before any file transfer or EPCC execution. Do not copy passwords, private keys or `.env` files into your measurement archives.

## Validation

```bash
python3 tools/test_machine_probe.py
python3 tools/machine_probe.py --label quick --specs-only
```

No Studio GUI modifications, Test 91–93 changes, remote deployment or experiment launches are included. This is a **root-drop overlay**, with only new files and no overwritten source code.
