# Test 101 — Independent Performance Analysis Against Official simdjson

**Platforms:** EPCC `rvc02` (LLVM 16 cross-compiled RVV) and Cloud-V `bpf3-16G-2` (native GCC RVV)  
**Benchmark:** simdjson DOM parsing; comparison between official simdjson v5.0.4 `fallback` and experimental RVV A2 fork variants.  
**Date of measurement:** 16 October 2026 (UTC)  
**Basis:** directly recalculated from the two uploaded `results101.csv` files, with the surrounding archives, provenance metadata, and original benchmark harness reviewed.

## 1. Executive verdict

On the **18 unchanged public JSON documents**, with each document given equal weight, the best tested A2 configuration (16 KiB dispatch threshold) achieved:

| Target | Speedup vs official simdjson 5.0.4 `fallback` | More DOM throughput | Implied lower parse time at fixed bytes |
|---|---:|---:|---:|
| **EPCC** | **1.887×** | **+88.74%** | **47.02%** |
| **Cloud-V** | **1.629×** | **+62.90%** | **38.61%** |

**All 18 public files are faster** than the measured official `fallback` baseline on each machine under this benchmark. The A2 4 KiB reference already achieves 1.874× (EPCC) and 1.624× (Cloud-V); the additional increase from the 4 KiB to 16 KiB threshold is only **+0.71%** and **+0.31%**, respectively, on this stratum. Most of the headline gain therefore comes from the **different experimental RVV implementation versus official fallback**, not from threshold tuning.

**Critical qualification:** This is **not an official-RVV-vs-A2-RVV comparison** and does not prove that 16 KiB is the optimum production threshold. The official binary is built from v5.0.4 with the `fallback` backend; A2 is a modified RVV fork based on 5.0.3. Versions, source implementations and selected backends differ.

## 2. Archive and measurement integrity

| Check | EPCC | Cloud-V |
|---|---|---|
| Run ID | `test101-20261016T193203Z-0a0dc0` | `test101-20261016T193050Z-adf6c2` |
| Host architecture | `rvc02`, RISC-V 64-bit | `bpf3-16G-2`, RISC-V 64-bit |
| Build toolchain | Clang/LLVM 16, cross-compiled | native `g++` |
| Status and stop reason | `completed`, `precision_reached` | `completed`, `precision_reached` |
| Rows / complete rounds | **19,404 / 22** | **22,050 / 25** |
| Measurement elapsed | 91 min 33 s | 92 min 50 s |
| Files per round | 147 (18 original + 42 derived + 87 synthetic) | 147 (same byte hashes) |
| Binaries | 6 (official + 5 A2 variants) | 6 |
| Missing rows, duplicate `(round,document,variant)` keys | None | None |
| Invalid/zero throughput | None | None |
| Nested result archive | ZIP CRC passed; content matches outer ZIP copies | ZIP CRC passed; content matches outer ZIP copies |
| Received SHA-256 | matches `SYNC_OK.txt` | matches `SYNC_OK.txt` |

Run-result ZIP SHA-256 values:

- EPCC: `d16cac7da7b00767e813236ffc52c42c1931907bd3743b7edfeb48c7da6cda9d`
- Cloud-V: `0a87cb9e77a3d6701d06032f4d8f66829b7d13a6a7525d8658bcf5a28b254737`

Both runs use **byte-identical input metadata and SHA-256 fixture hashes**, an identical benchmark harness and source-plan/fork SHA-256 values, and the same pinned official v5.0.4 commit `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`. The upstream public corpus is pinned to `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`. Executable binary SHA-256 values differ between platforms, as expected for GCC versus Clang cross-compilation.

The independent audit regenerated all comparisons by pairing measured throughputs **within the same document and round**, computing the mean of log throughput ratios per document, then exponentiating the equal-weight mean across documents. Its results agree with the generated reports (up to displayed rounding).

## 3. Headline: original public JSON vs official simdjson

This is the primary result because these **18 corpus files are unchanged** and not selected as threshold-friendly generated cases.

| Candidate RVV A2 configuration | EPCC vs official | EPCC throughput gain | Cloud-V vs official | Cloud-V throughput gain |
|---|---:|---:|---:|---:|
| 4 KiB (`A2_REF`) | 1.874× | +87.40% | 1.624× | +62.39% |
| 8 KiB | 1.873× | +87.26% | 1.624× | +62.40% |
| 10 KiB | 1.881× | +88.13% | 1.621× | +62.09% |
| 12 KiB | 1.884× | +88.40% | 1.627× | +62.73% |
| **16 KiB** | 1.887× | +88.74% | 1.629× | +62.90% |

Interpretation: a 1.887× speedup is **88.7% more bytes parsed per unit time**, not an 88.7% reduction in time. For the same parse workload, a 1.887× throughput factor corresponds to approximately **47.0% less parsing time**. Cloud-V has approximately **38.6% less parsing time** at 1.629× throughput. Neither figure includes reading files from disk.

### What the threshold changes independently

| Threshold vs A2 4 KiB | EPCC, original JSON | Cloud-V, original JSON |
|---|---:|---:|
| 8 KiB | -0.08% | +0.00% |
| 10 KiB | +0.39% | -0.19% |
| 12 KiB | +0.53% | +0.21% |
| 16 KiB | +0.71% | +0.31% |

Only **three of the 18 public files are at or below 16 KiB** (10,075 B, 11,812 B and 15,253 B). The remaining 15 files are larger than every threshold in this comparison and are not expected to change dispatch decisions. Most of the small net effect on public originals is therefore structurally unsurprising.

## 4. Full results for the three separate workload strata

Each result is a geometric mean of paired DOM throughput ratios to official `OFFICIAL_504`. **Do not average the three rows of a variant** to manufacture a single overall score; the workload strata have intentionally different sampling distributions.

### 18 unchanged public JSON files

| RVV A2 | EPCC speedup | EPCC gain | Cloud-V speedup | Cloud-V gain |
|---|---:|---:|---:|---:|
| 4 KiB | 1.874× | +87.40% | 1.624× | +62.39% |
| 8 KiB | 1.873× | +87.26% | 1.624× | +62.40% |
| 10 KiB | 1.881× | +88.13% | 1.621× | +62.09% |
| 12 KiB | 1.884× | +88.40% | 1.627× | +62.73% |
| 16 KiB | 1.887× | +88.74% | 1.629× | +62.90% |

### 42 source-derived JSON fragments

| RVV A2 | EPCC speedup | EPCC gain | Cloud-V speedup | Cloud-V gain |
|---|---:|---:|---:|---:|
| 4 KiB | 1.862× | +86.20% | 1.560× | +56.04% |
| 8 KiB | 1.956× | +95.61% | 1.618× | +61.75% |
| 10 KiB | 1.964× | +96.41% | 1.617× | +61.66% |
| 12 KiB | 1.975× | +97.52% | 1.626× | +62.64% |
| 16 KiB | 1.992× | +99.23% | 1.635× | +63.46% |

The 42 fragments come from **14 upstream public files, exactly three fragments per source**. They are useful for studying smaller JSON structures but are **not 42 independent real-world datasets**. With three fragments per source, a source-equal geometric mean is numerically the same as the fragment-equal geometric mean here. The gains cannot be interpreted as independent holdout replication.

### 87 exact-size synthetic boundary JSON files

| RVV A2 | EPCC speedup | EPCC gain | Cloud-V speedup | Cloud-V gain |
|---|---:|---:|---:|---:|
| 4 KiB | 1.736× | +73.56% | 1.569× | +56.86% |
| 8 KiB | 1.825× | +82.47% | 1.632× | +63.20% |
| 10 KiB | 1.851× | +85.09% | 1.646× | +64.56% |
| 12 KiB | 1.873× | +87.27% | 1.666× | +66.63% |
| 16 KiB | 1.897× | +89.73% | 1.685× | +68.53% |

The synthetic stratum contains equal-sized **ASCII**, **dense** and **escaped-string** families. The overall geometric mean is sensitive to this designed equal-family weighting and is not a forecast of typical production JSON traffic.

## 5. The synthetic benchmark hides a major regression

Breakdown for **16 KiB A2 vs official fallback**, by generated content family (29 files in each family):

| Synthetic JSON family | EPCC speedup | EPCC gain | Cloud-V speedup | Cloud-V gain |
|---|---:|---:|---:|---:|
| ascii | 8.507× | +750.72% | 6.693× | +569.25% |
| dense | 1.644× | +64.41% | 1.478× | +47.82% |
| escaped | 0.488× | -51.17% | 0.484× | -51.62% |

The ASCII fixtures show exceptional speedups, dense structures show solid speedups, but **escaped-heavy JSON is approximately 51% slower by throughput than official fallback on both machines**. Thus, **58 of 87 synthetic fixtures are faster and 29 of 87 are slower** at the 16 KiB setting. A headline synthetic mean of +89.7% on EPCC or +68.5% on Cloud-V would hide this important class-dependent regression.

This is the clearest next optimization target: trace string scanning, backslashes, quote/escape masks and their interaction with RVV dispatch. The existence of the regression is measured; the exact low-level instruction-level cause has **not** been established by these archives and requires profiling.

## 6. Performance on each of the 18 original public files

File-level speedups below use the geometric mean of within-document, within-round paired throughput ratios. The last columns show the **marginal** gain of 16 KiB versus the 4 KiB A2 reference, not the total gain versus official.

| Original public JSON | Bytes | EPCC: A2 16 KiB vs official | Cloud-V: A2 16 KiB vs official | EPCC: 16 vs 4 KiB | Cloud-V: 16 vs 4 KiB |
|---|---:|---:|---:|---:|---:|
| `apache_builds.json` | 127,275 | 2.203× | 1.736× | +0.31% | -0.25% |
| `canada.json` | 2,251,051 | 1.286× | 1.358× | -0.07% | -0.08% |
| `citm_catalog.json` | 1,727,204 | 1.745× | 1.564× | -0.56% | -0.09% |
| `github_events.json` | 65,132 | 2.641× | 2.115× | -0.00% | +0.01% |
| `google_maps_api_compact_response.json` | 11,812 | 1.618× | 1.275× | +3.14% | +2.32% |
| `google_maps_api_response.json` | 26,102 | 1.690× | 1.422× | -0.03% | -0.09% |
| `gsoc-2018.json` | 3,327,831 | 4.154× | 3.146× | +0.06% | -0.10% |
| `instruments.json` | 220,346 | 1.747× | 1.475× | +0.34% | -0.24% |
| `marine_ik.json` | 2,983,466 | 1.371× | 1.256× | -0.33% | +0.21% |
| `mesh.json` | 723,597 | 1.357× | 1.361× | +0.55% | +0.14% |
| `mesh.pretty.json` | 1,577,353 | 1.485× | 1.505× | +0.04% | -0.03% |
| `numbers.json` | 150,124 | 1.314× | 1.422× | +0.04% | -0.03% |
| `twitter.json` | 631,515 | 2.380× | 1.966× | -0.11% | -0.01% |
| `twitter_api_compact_response.json` | 10,075 | 2.267× | 1.795× | +5.46% | +2.65% |
| `twitter_api_response.json` | 15,253 | 2.251× | 1.843× | +3.98% | +2.10% |
| `twitter_timeline.json` | 42,233 | 1.974× | 1.610× | +0.16% | -0.07% |
| `twitterescaped.json` | 562,408 | 1.798× | 1.439× | +0.10% | -0.33% |
| `update-center.json` | 533,178 | 2.281× | 1.805× | -0.01% | -0.38% |

The smallest public speedups still exceed 1.25× on Cloud-V and 1.28× on EPCC, while some content-specific wins are much larger. The very large `gsoc-2018.json` speedup increases the file-equal geometric mean, illustrating why the precise headline depends on how applications weight files.

### Three small unchanged public files are the most direct dispatch evidence

| File | Bytes | Marginal gain 16 KiB vs 4 KiB, EPCC | Cloud-V |
|---|---:|---:|---:|
| `twitter_api_compact_response.json` | 10,075 | +5.46% | +2.65% |
| `google_maps_api_compact_response.json` | 11,812 | +3.14% | +2.32% |
| `twitter_api_response.json` | 15,253 | +3.98% | +2.10% |

All three files show a consistent marginal gain on both machines; this is stronger evidence for a useful **small-document dispatch optimization** than the near-zero movement across the other 15 documents, which do not cross the thresholds.

## 7. Sensitivity to the benchmark weighting

The primary speedup weights each of the 18 public JSON files equally, **regardless of byte size or application frequency**. Another legitimate question is how long it would take to parse one instance of every file, giving more absolute work to larger documents. This alternative below is **a model computed from per-file median GB/s**, not a separately timed end-to-end run:

| Illustrative one-pass model (18 public files) | Official 5.0.4 fallback | A2 16 KiB | Implied speedup |
|---|---:|---:|---:|
| EPCC | 0.0767 GB/s | 0.1293 GB/s | 1.686× (+68.62%) |
| Cloud-V | 0.0883 GB/s | 0.1363 GB/s | 1.543× (+54.29%) |

This model remains positive on both machines but gives smaller headline factors than the equal-file geometric mean, especially on EPCC. Neither weighting represents an application workload without knowing its distribution of JSON sizes and formats.

### Document-selection sensitivity (illustrative resampling)

A fixed-seed bootstrap resampling **the 18 public files** (8,000 replicates) gives the following approximate 2.5%–97.5% intervals for A2 16 KiB / official geometric-mean speedup:

- EPCC: **1.66×–2.17×** (point estimate 1.887×).
- Cloud-V: **1.49×–1.81×** (point estimate 1.629×).

These are **corpus-composition sensitivity intervals**, not validated frequentist confidence intervals for an unknown population of production JSON. The 18 files were deliberately selected, not sampled at random; bootstrapping cannot fix sampling bias.

## 8. Measurement protocol and what it excludes

Review of the bundled `tools/test101_dom.cpp` and `tools/test101_native.py` establishes:

1. The benchmark selects the requested simdjson runtime implementation explicitly: `fallback` for official and `rvv` for experimental A2. The C++ program rejects an unavailable or incorrectly activated backend.
2. For every fixture, the runner compares a serialized DOM representation and a 64-bit FNV-style checksum across all six binaries **before** timing. It also checks file size and SHA-256. This is a useful cross-variant equivalence check, though not a complete formal correctness proof for all possible JSON.
3. The measured path is `simdjson::dom::parser::parse` of a **preloaded, repeatedly reused padded JSON buffer**; file I/O is outside the timer. The parser is reused. Eight parses warm it up; the reported run speed is the **median of five timed batches** of calibrated iterations.
4. Each round randomizes fixture and variant order; an A2 reference parse is measured before and after each document block to track drift. The harness attempts CPU pinning using `taskset` when available.
5. The speedups here are based on **paired measurements for the same file and round**, not on ratios of independently averaged GB/s values. The reported adaptive stopping criterion was met after 22 EPCC rounds and 25 Cloud-V rounds.
6. Official-version, fork-version and backend differences are all included in the total speedup. Neither CPU utilization, memory footprint, energy consumption, cold-cache latency, multi-thread scaling nor alternative simdjson backends are characterized by this test.

### Reliability and caution about uncertainty

- All document × round × variant groups are complete; `validated=true` and successful packaging are consistent with the raw CSVs.
- Median absolute A2 reference drift: **0.281%** EPCC and **0.252%** Cloud-V. Fractions exceeding 10%: **0.031%** EPCC and **0.544%** Cloud-V, respectively.
- The Test 101 program reports very small approximate repeated-round confidence half-widths **for the A2 threshold comparisons only**. These describe repeatability under the same fixtures and setup; they are **not confidence bounds for A2-vs-official gains**, nor do they measure across-day reproducibility or independent-document uncertainty.
- Machine-specific toolchain and memory/CPU differences preclude merging EPCC and Cloud-V throughputs into a single synthetic score. Agreement in directional effects is nevertheless encouraging.
- The adaptive stopping rule uses sequential looks at the same data; a reported 95% half-width should not automatically be treated as a multiplicity-adjusted confirmatory confidence interval.

## 9. Cross-check against independent Test 100 campaigns

The earlier Test 100 archives measured the same 18 unchanged public files with the same benchmark-harness SHA-256, official commit, and fork-source SHA-256, but only thresholds 4/7/8/10 KiB. The baseline A2 4 KiB versus official factor was:

| Platform | Test 100: A2 4 KiB vs official | Test 101: A2 4 KiB vs official |
|---|---:|---:|
| EPCC | 1.875× | 1.874× |
| Cloud-V | 1.626× | 1.624× |

The independent campaigns agree closely on the important **relative A2-vs-official performance level**. This reinforces confidence that Test 101 is not merely a Studio status-display artifact. It still does not prove application-wide speedups or erase the escaped-string regression.

## 10. Recommendations and decision

**What can be claimed:** On the 18 specified original public documents, under warm-buffer, repeated DOM parsing on the two tested RISC-V hosts, experimental A2 with RVV at 16 KiB delivers **1.887× throughput on EPCC** and **1.629× on Cloud-V** relative to the official simdjson 5.0.4 **fallback backend**. All 18 document-wise comparisons favor A2 on each host.

**What cannot be claimed:** A2 is 1.9× faster than every simdjson backend, 16 KiB is the optimal production threshold, or arbitrary real-world JSON is accelerated by the same amount. The escaped-heavy synthetic class is materially slower and remains a significant optimization concern.

Next work, in descending order of practical value:

1. **Profile escaped-string regressions** on both systems (backslash density, quote masks, escaping path, scalar/vector dispatch and performance counters), against the same official fallback and against the A2 4 KiB configuration. Preserve realistic escaped-string fixtures, not just artificial extremes.
2. **Benchmark a genuinely matched baseline**: same simdjson version/source tree where possible, same compiler/flags and equivalent backend selection. Separate “RVV implementation vs fallback” from “threshold change” and from “fork version difference.”
3. **Expand independent real JSON samples in the 4–16 KiB range**, ideally holdout files with independently licensed provenance, and track file-type and structure distributions. Retain original public, derived and synthetic strata separately.
4. **Validate 16 KiB versus 12 KiB** (and possibly 20–24 KiB) in fresh confirmatory runs, with prespecified file weights, workload targets and regression budgets. A2 16 KiB is only the best of the tested thresholds on these datasets, not a demonstrated global optimum.
5. **Report two production-relevant metrics** for representative inputs: file-equal geometric mean and a clearly defined workload-frequency/byte-weighted end-to-end throughput, including cold-cache and memory effects when relevant.

**Release recommendation:** Preserve the known working A2 path; treat the 16 KiB dispatch configuration as an **experimental candidate** for a new confirmatory test. Do not promote it solely on the basis of this study until escaped-heavy workload behavior and matched-baseline validity have been addressed.

## 11. Reproducibility notes and primary evidence

- Cloud-V upload: `studio101-cloudv.zip`, containing `results101.csv`, `summary101.json`, `status101.json`, `builds101.json`, `inputs101.json`, `machine101.json`, `corpus_manifest101.json`, `REPORT_101.md` and nested verified `test101_results.zip`.
- EPCC upload: `epcc(1).zip`, containing corresponding files and `studio101-build.log`.
- Test 101 benchmark source reviewed from `VLA-MethodLab_TEST101_EPCC_CLOUDV_DROP_ROOT_20261016.zip`: `tools/test101_dom.cpp` and `tools/test101_native.py`.
- Earlier Test 100 comparison: `test100_results.zip` (EPCC) and `test100_results(1).zip` (Cloud-V).
- Geometric-mean formula: for each document `d`, compute `r_d = exp(mean_round(log(GBps_A2(d,round)/GBps_official(d,round))))`; the reported file-equal factor is `exp(mean_document(log(r_d)))`. All observations with the same document are repeated measurements, not independent documents.
- The primary comparison uses **decimal gigabytes per second**, not GiB/s.

---

*This report is an independent audit of supplied results, not a claim to have run new experiments on either remote host.*
