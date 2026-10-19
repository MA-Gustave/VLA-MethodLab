# Test 102 — Quantified A2 RVV Speedups Against Official simdjson 5.0.4

**Independent audit of the uploaded EPCC and Cloud-V overnight result archives — October 17, 2026.**

## Scope and baseline

- Official baseline: **simdjson v5.0.4**, pinned Git commit `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`, compiled for the **fallback** backend.
- Our candidates: experimental **RVV A2** at 4 KiB (`A2_REF`) or 16 KiB (`A2_G16384`), packed variants disabled.
- Performance metric: throughput in GB/s. A **1.50x** throughput ratio corresponds to **+50%** speed versus the named comparator.
- Aggregation: pair candidate/reference measurements from the same document and round; geometric-mean repeated ratios within each document, then geometric-mean equally across documents. EPCC and Cloud-V remain separate.
- **Stage 1 and Stage 2 are separately timed internal entry points.** Their throughputs cannot be added and are not automatically percentages of total DOM latency.

## Archive and run checks

| Check | EPCC | Cloud-V |
|---|---:|---:|
| Measurement rows | 83,562 | 101,682 |
| Complete 3-variant comparison groups | 27,854 | 33,894 |
| Benchmark wall time | 6 h 28 min | 6 h 28 min |
| Stop reason | `overnight_budget` | `overnight_budget` |
| Finished state | `completed` | `completed` |
| Correctness flag | `validated: true` | `validated: true` |
| Unique public JSON inputs | 18 | 18 |
| Synthetic probes per phase | 206 | 206 |

Both archives pass ZIP integrity checks and their SHA-256s agree with `SYNC_OK.txt`. The two uploaded inputs manifests are byte-identical, as are the public corpus manifests. The same fork, harness, and plan SHA-256 identifiers appear in both build manifests; machine compilers differ (EPCC LLVM16; Cloud-V GCC). All 185,244 records have positive, finite measured throughputs, and the 3-variant comparison groups are complete and nonduplicated.

## Main result: unchanged public JSON (confirmation phase)

| Benchmark endpoint / candidate | EPCC vs official | EPCC gain | Cloud-V vs official | Cloud-V gain |
|---|---:|---:|---:|---:|
| A2_REF — dom | 1.8798x | +87.98% | 1.6018x | +60.18% |
| A2_REF — stage1 | 2.4754x | +147.54% | 2.0220x | +102.20% |
| A2_REF — stage2 | 1.4664x | +46.64% | 1.2824x | +28.24% |
| A2_G16384 — dom | 1.8924x | +89.24% | 1.6074x | +60.74% |
| A2_G16384 — stage1 | 2.5053x | +150.53% | 2.0369x | +103.69% |
| A2_G16384 — stage2 | 1.4674x | +46.74% | 1.2834x | +28.34% |

All 18 public documents favor A2_G16384 on both machines in the confirmation run. The gain is consistent with the Test 100 and Test 101 findings but is a **RVV-vs-fallback** comparison; it is not the gain attributable to changing the A2 threshold.

### Marginal effect of the 16 KiB dispatch threshold

| Metric | EPCC: A2_16K / A2_4K | Cloud-V: A2_16K / A2_4K |
|---|---:|---:|
| dom | 1.0067x (+0.67%) | 1.0035x (+0.35%) |
| stage1 | 1.0121x (+1.21%) | 1.0074x (+0.74%) |
| stage2 | 1.0007x (+0.07%) | 1.0008x (+0.08%) |

## Performance loss as escape density increases

The following **mixed-family synthetic probes** deliberately vary requested raw-backslash density and use independent confirmation seed inputs. Their actual raw-backslash density closely matches the requested level. This controlled stress sweep must **not** be averaged into a representative real-world workload score.

| Requested raw `\` density | EPCC DOM | Cloud-V DOM | EPCC Stage 2 | Cloud-V Stage 2 |
|---:|---:|---:|---:|---:|
| 0% | 8.123x | 6.249x | 10.569x | 9.252x |
| 1% | 6.341x | 4.981x | 7.291x | 5.973x |
| 3% | 4.555x | 3.646x | 4.575x | 3.589x |
| 6% | 3.139x | 2.548x | 2.699x | 2.139x |
| 10% | 2.197x | 1.777x | 1.721x | 1.371x |
| 15% | 1.624x | 1.299x | 1.175x | 0.956x |
| 25% | 1.171x | 0.990x | 0.733x | 0.640x |
| 50% | 0.463x | 0.431x | 0.228x | 0.218x |

- On the mixed family at **50% raw backslashes**, DOM drops to **0.463x** (EPCC) and **0.431x** (Cloud-V), i.e. roughly **−54%** and **−57%** throughput versus official fallback.
- **Stage 1 still wins at 50%**: approximately 1.60x EPCC and 1.33x Cloud-V.
- **Stage 2 collapses at 50%**: approximately 0.228x EPCC and 0.218x Cloud-V (roughly 4.4–4.6 times slower). This is strong evidence to prioritize escaped-string decoding in subsequent profiling, but independently timed stage ratios alone do not prove how much of DOM time Stage 2 consumes.
- Around **25% requested density**, Cloud-V mixed-family DOM is approximately parity with official; EPCC still shows an advantage. The crossover is workload- and machine-dependent.
- **Important density caveat:** requested and actual density differ for some escape encodings. For example, `slash` (`\\`) uses roughly twice as many raw backslashes as its requested percentage; `unicode` is capped near 16.6% due to `\uXXXX` encoding. Compare actual density before pooling families.

## Synthetic-family comparison (confirmation)

Each family is reported separately. The 126 crossover probes are overrepresented if one computes a single all-synthetic geometric mean.

| Family | Files/phase | EPCC A2_16K / official DOM | Cloud-V A2_16K / official DOM |
|---|---:|---:|---:|
| crossover | 126 | 7.830x | 6.092x |
| mixed | 16 | 2.479x | 2.027x |
| newline | 16 | 2.475x | 2.027x |
| quote | 16 | 2.520x | 2.039x |
| slash | 16 | 2.364x | 1.902x |
| unicode | 16 | 2.636x | 2.157x |

## Public-document results (DOM, confirmation, A2_16K / official)

| Public source file | EPCC ratio | Cloud-V ratio |
|---|---:|---:|
| `apache_builds.json` | 2.210x | 1.719x |
| `canada.json` | 1.290x | 1.326x |
| `citm_catalog.json` | 1.765x | 1.544x |
| `github_events.json` | 2.653x | 2.079x |
| `google_maps_api_compact_response.json` | 1.613x | 1.252x |
| `google_maps_api_response.json` | 1.696x | 1.407x |
| `gsoc-2018.json` | 4.136x | 3.080x |
| `instruments.json` | 1.754x | 1.457x |
| `marine_ik.json` | 1.385x | 1.258x |
| `mesh.json` | 1.353x | 1.353x |
| `mesh.pretty.json` | 1.488x | 1.488x |
| `numbers.json` | 1.313x | 1.404x |
| `twitter.json` | 2.369x | 1.943x |
| `twitter_api_compact_response.json` | 2.284x | 1.766x |
| `twitter_api_response.json` | 2.273x | 1.831x |
| `twitter_timeline.json` | 1.974x | 1.577x |
| `twitterescaped.json` | 1.809x | 1.423x |
| `update-center.json` | 2.277x | 1.768x |

## Interpretation and next experiment

1. The RVV A2 implementation provides a **large and replicable public-corpus speedup** versus the specified official fallback binary on both tested RISC-V machines.
2. The **threshold adjustment itself** is small on the original public documents (+0.67% EPCC / +0.35% Cloud-V for 16 KiB versus 4 KiB). Avoid crediting the entire 60–90% speedup to threshold selection.
3. The sweep isolates a **pronounced dense-escape failure mode in Stage 2**. Treat high-backslash synthetic workloads as stress probes, not representative input prevalence. Validate with additional real documents rich in escaping.
4. Investigate Stage 2 escape decode loops, vector/string boundary behavior, and data-dependent allocations/branches before globally changing the sparse/dense Stage 1 dispatch. Profile real CPU cycles and correctness, and confirm against untouched holdouts.
5. Sequential rounds on repeated documents quantify stability under those conditions; they are not independent real-world documents. These data cannot establish universal speedup or a hardware performance ceiling.
6. Differences between EPCC and Cloud-V reflect both hardware and compiler/runtime environment; no cross-machine ratio of absolute GB/s should be construed as an isolated CPU effect.

## Provenance

- EPCC original uploaded archive: `102epcc.zip`; result SHA-256 `83a5ccf64eb7204f05f930403e43525334562400f78d831779db5a943a0ec076`. 
- Cloud-V original uploaded archive: `102-cloudv.zip`; result SHA-256 `0ba1bc0b331991d464a69dd2cc23c379764a56e87364d8da3302a595fa70310d`.
- Engine fork SHA-256 (from both build manifests): `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16`.
- Measurement harness SHA-256: `2ef88a44e63e9d6790d03768940a58f42e08edb06c6a7be622267b37ba181a25`.
- Both run reports mark `validated: true`; this audit independently checked measurement completeness and archive integrity, not a fresh execution on live RISC-V hardware.
