# Eight-hour RVV-VLA split-stage performance profile

**simdjson v5.0.3 · RISC-V Vector (RVV-VLA) · Native GCC · 11 October 2026 (UTC)**

> **Status:** completed by time budget (`stopped`, *8-hour budget reached*), not a test failure. **6,887 recorded observations**, **four of four configurations compiled**, **four of four basic correctness gates passed**, and **zero recorded failures**. These are results on one RISC-V system under the conditions below—not a general-purpose performance guarantee.

![Paired DOM, Stage 1 and Stage 2 speedups](assets/2026-10-11-stage-profile-8h.png)

## Executive summary

The **E14 “packed disabled” RVV-VLA plan** led the four-way comparison for full DOM parsing: **1.502× geometric-mean paired throughput (+50.2%)** relative to official simdjson v5.0.3 `rvv_vls256`. Its corresponding internal **Stage 1** ratio was **1.601× (+60.1%)**, while **Stage 2** reached **1.298× (+29.8%)**. The adaptive E01 and previous sparse8/escape8 reference also beat the official baseline on this corpus suite, at approximately **1.443×** and **1.442×** in DOM.

E14 outperformed E01 by **1.041× (~4.1%)** in direct, same-trial DOM pairs (n=1,721). However, **performance depends strongly on JSON structure**: E14's isolated Stage 1 was only **0.417× the baseline on escape-heavy JSON**, despite a **1.317× DOM** ratio on that family. This is a concrete optimization target, not a reason to claim that every stage improved.

## 1. Overall measured results

| Configuration | DOM speedup | Stage 1 speedup | Stage 2 speedup | Paired observations |
|---|---:|---:|---:|---:|
| **E14 · packed disabled** | **1.502× (+50.2%)** | **1.601× (+60.1%)** | 1.298× (+29.8%) | 1,722 |
| E01 · adaptive | 1.443× (+44.3%) | 1.498× (+49.8%) | 1.294× (+29.4%) | 1,721 |
| sparse8/escape8 · historical VLA | 1.442× (+44.2%) | 1.486× (+48.6%) | **1.306× (+30.6%)** | 1,722 |
| **Official VLS256 (reference)** | **1.000×** | **1.000×** | **1.000×** | 1,722 |

*Definition:* a speedup is **candidate GB/s ÷ official VLS256 GB/s**, matched on measurement phase, corpus, iteration count and trial. The displayed aggregate is the **geometric mean over those ratios**, not the ratio of pooled absolute throughputs. Each recorded throughput is the median of three repetitions. Higher is better. GB/s uses 1,000,000,000 bytes/s.

The median paired DOM ratios are **1.376×** (E14), **1.375×** (E01) and **1.374×** (sparse8). This distinction matters: the larger geometric means are influenced by high gains on certain corpus families, especially structurally dense inputs. Repeated trials of the same inputs are **not independent applications** or statistical samples of arbitrary JSON.

## 2. What kinds of JSON benefit?

Each family combines both the small and large corpus observations; figures are geometric means of paired speedups. “Unicode escapes” is distinct from the dedicated **real UTF-8 multibyte** corpus.

| JSON family | E14 DOM | E01 DOM | sparse8 DOM | E14 Stage 1 | E14 Stage 2 |
|---|---:|---:|---:|---:|---:|
| ASCII strings | 1.166× | 1.102× | 0.970× | 1.272× | 1.022× |
| CITM catalog | 1.663× | 1.599× | 1.716× | 1.967× | 1.220× |
| Dense structurals | 2.392× | 2.414× | 2.439× | 5.649× | 1.207× |
| Escaped strings | 1.317× | 1.320× | 1.239× | 0.417× | 2.028× |
| Numbers | 1.313× | 1.280× | 1.322× | 2.330× | 0.991× |
| Real UTF-8 multibyte | 1.742× | 1.548× | 1.693× | 1.998× | 1.388× |
| Twitter | 1.732× | 1.629× | 1.705× | 1.925× | 1.449× |
| Unicode escapes | 1.071× | 1.037× | 0.977× | 0.818× | 1.323× |

**Interpretation:**

- **Dense structurals:** E14 gains **2.392× DOM** and **5.649× Stage 1** against VLS256, but its Stage 2 gain is **1.207×**. Improvements in a single stage do not translate linearly into full-parser speedup.
- **Escaped strings:** the **0.417× E14 Stage 1** ratio means Stage 1 was slower than the VLS256 reference on this family, even though E14 DOM gained **1.317×** and direct Stage 2 gained **2.028×**. Investigate the escape-scanning path and whether workload profiling or allocation effects differ between standalone calls and the public API.
- **Unicode escapes:** E14 Stage 1 was **0.818×**, while DOM was **1.071×**. Optimizations must not ignore this regression.
- **Real UTF-8 multibyte:** E14 delivered **1.742× DOM** and **1.998× Stage 1**, giving evidence beyond tests containing only `\uXXXX` escapes.
- **Relative positioning:** sparse8 was ahead of E14 on CITM and dense DOM workloads; E14 was strongest overall on this **specific equally represented corpus suite**.

## 3. Test environment and workload

| Property | Recorded setting |
|---|---|
| Machine | Native Linux `riscv64` RISC-V system (BPI-F3 test hardware) |
| RVV hardware | VLEN = **256 bits**; no virtualization/emulation detected |
| Compiler | `g++ (Bianbu 14.2.0-19ubuntu2bb3) 14.2.0` |
| Build | Direct compilation of `src/simdjson.cpp` with `-O3 -DNDEBUG -g0 -pthread -std=c++17 -mabi=lp64d`; no CMake dependency download |
| VLA target | `-march=rv64gcv` with RVV backend enabled |
| Official VLS target | `-march=rv64gcv_zvl256b -mrvv-vector-bits=zvl` |
| CPU controls | Core **0** for benchmarks; governor `performance`; orchestration on a separate available CPU |
| Reference | Official upstream simdjson **v5.0.3**, pinned commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249` |
| Source status | RVV-VLA working-tree snapshot contained **828 files** and was **dirty** relative to the recorded base commit |
| Budget | **8 h** = 28,800 seconds, including native compilation |
| Time span | **2026-10-11 02:29:50–10:29:51 UTC** |
| Progress | **107 full fixed rounds**, plus a partially recorded final round |
| Measurements | **6,887 rows**: 20 screening + 6,867 fixed-grid |
| Dataset | **16 input instances**: 8 JSON families × 2 size bands (about 1 MiB / 4 MiB, with native-size CITM and Twitter retained) |

The corpus suite covers ASCII, CITM catalog, dense structurals, escapes, numbers, Twitter, Unicode escapes and **real multibyte UTF-8**. The fixed-grid runner cycles among **12, 24 and 48 parse iterations**, rotates the candidate order forward and backward between trials, and compares each result to an official-VLS measurement in the **same trial**.

## 4. Native validation and build health

The four binaries were compiled successfully and each passed a basic JSON classification gate of **169 valid + 24 deliberately invalid documents**. The active backend was checked: `rvv` for the three VLA configurations and `rvv_vls` for the official reference.

| Configuration | Build time | Native backend | JSON validation |
|---|---:|---|---|
| `E14_packed_disabled` | 150.73 s | `rvv` | 169 valid / 24 invalid **PASS** |
| `E01_adaptive` | 154.18 s | `rvv` | 169 valid / 24 invalid **PASS** |
| `sparse8_escape8_reference` | 150.87 s | `rvv` | 169 valid / 24 invalid **PASS** |
| `upstream_vls256` | 152.98 s | `rvv_vls` | 169 valid / 24 invalid **PASS** |

The provided `failures.csv` has only a header, and the source metadata lists **no compiler diagnostics**. This establishes that no failures were **recorded by this campaign**; it is not a substitute for full JSON conformance, differential fuzzing, memory-safety testing or compiler-log archival.

## 5. Measurement boundaries and reproducibility

1. **Stage 1 and Stage 2 are genuine internal calls:** the harness times `parser.implementation->stage1()` and `stage2()` separately using an already initialized parser. Public DOM `parser.parse()` is timed independently. **Do not sum the stage durations and claim they equal DOM API time.** The benchmark measures elapsed wall-clock time, not CPU cycles.
2. **Paired trials, correlated data:** baseline and candidates share a corpus/trial; a geometric mean is calculated across repeated trials. The MAD values in `ranking.csv` describe variability of these paired ratios, **not a confidence interval**. No independent-board replication or statistical significance claim is made.
3. **Comparable, not identical machine code:** the VLA and VLS256 backends use different target-specific compile flags, as appropriate for each path. This is a comparison of configured implementations, not an isolated one-instruction change.
4. **Source provenance has a gap:** the recorded RVV-VLA checkout was dirty. The pinned upstream commit alone cannot recreate that modified source exactly. To claim bit-for-bit reproducibility of the entire run, publish the precise **828-file RVV-VLA source snapshot** (or a clean commit containing its changes) and the pinned benchmark worker.
5. **Evidence boundary:** the attached records include observations, ranking, metadata, status and an empty failure table, but **not the original remote compiler logs or generated JSON corpus bytes**. The normalized `events.jsonl` in this publication pack is **derived from these records**, not an original terminal transcript.
6. **Generalization:** numbers represent this GCC version, RVV VLEN=256 hardware, benchmark protocol and corpus selection. Additional boards, compilers, correctness workloads and representative production JSON are needed before broader claims.

## 6. Research implications

**Keep E14 as the experimental DOM throughput leader**, but retain **E01 and sparse8** as necessary comparators. The next work should target **escape-heavy and Unicode-escaped Stage 1 regressions** without sacrificing the dense-structurals or real-UTF-8 gains. Add focused differential correctness/fuzz tests at vector-length boundaries and validate on at least one additional RVV platform or compiler before proposing a new default implementation.

## 7. Data, audit and normalized event logs

The following versioned files make the headline numbers independently recalculable from the uploaded records:

| Artifact | Purpose |
|---|---|
| [observations.csv](../../results/runs/2026-10-11-stage-profile-8h/observations.csv) | **6,887 original measurement records**, including trial keys and DOM/Stage 1/Stage 2 throughput |
| [ranking.csv](../../results/runs/2026-10-11-stage-profile-8h/ranking.csv) | Original paired ranking and MAD |
| [by-family.csv](../../results/runs/2026-10-11-stage-profile-8h/by-family.csv) | Independently recomputed breakdown by corpus family |
| [events.jsonl](../../results/runs/2026-10-11-stage-profile-8h/events.jsonl) | **Derived normalized event log** (measurement, compile, correctness, campaign end) |
| [metadata.public.json](../../results/runs/2026-10-11-stage-profile-8h/metadata.public.json) | Publication-safe configuration, compiler flags and provenance |
| [status.public.json](../../results/runs/2026-10-11-stage-profile-8h/status.public.json) | Final budget, counters and stop reason |
| [failures.csv](../../results/runs/2026-10-11-stage-profile-8h/failures.csv) | Provided failure table; header-only |
| [SHA256SUMS.txt](../../results/runs/2026-10-11-stage-profile-8h/SHA256SUMS.txt) | Checksums for published evidence files |
| [verify.py](../../results/runs/2026-10-11-stage-profile-8h/verify.py) | Standard-library verification and recomputation of the paired speedups |

**Local audit command**, from the repository root:

```bash
python results/runs/2026-10-11-stage-profile-8h/verify.py
```

The original synchronized remote snapshot was marked SHA256-verified with digest `c1da38e6aa93b00ab83bae8f8b7fbf29acfc1ee783422c6d09d14081ce6f2d1b`. This is an **historical synchronization marker**: the original remote ZIP was not included in this upload, so the digest cannot be independently recomputed here. `SHA256SUMS.txt` instead verifies the actual files in this publication pack.

## Acknowledgment

We thank **Cloud-V** for generously lending a RISC-V server **free of charge** for the original measurements. This is an infrastructure acknowledgment, not an endorsement or a requirement for reproducing the experiments elsewhere.
