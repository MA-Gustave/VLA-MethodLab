# Test 104 — Independent Public JSON Benchmark vs simdjson 5.0.4

**EPCC and Cloud-V: paired, document-equal geometric throughput audit**

## Summary

The public 18-file simdjson-data performance corpus shows a **large unchanged RVV A2 advantage** versus the official 5.0.4 **fallback** backend, but neither Stage 2 experiment is a globally superior replacement for A2 on both machines. The 95 JSONTestSuite `y_` cases are exceptionally tiny (2–110 bytes, median 8 bytes): the official fallback is faster on most. Dense-escape synthetic stress is dramatically accelerated by the Stage 2 variants, but this does not establish prevalence on real workloads.

## Identity, method and validation

- **Official:** simdjson 5.0.4 fallback, commit `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`.
- **Our original A2:** fork source SHA-256 `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16`, RVV implementation, adaptive threshold 16 KiB.
- **Experimental Stage 2:** `A2_SIMPLE_RUN` (batched adjacent simple escapes) and `A2_NL4` (same plus 4-pair newline burst). The deployed original A2 checkout is not modified.
- **Aggregation:** candidate/reference measured in the same 4-variant comparison group. First average log-throughput ratios over repeated rounds for *each document*, then geometric-mean over documents. EPCC and Cloud-V remain separate; exploration and confirmation never pooled.
- All four variants are reported on the same input bytes on both machines, with identical `inputs104.json`, public corpus manifest, and JSONTestSuite manifest SHA-256.
- No cross-variant conformance disagreements or labelled-expectation mismatches reported on either machine.

| Audit | EPCC | Cloud-V |
|---|---:|---:|
| Raw measurement rows | 230,376 | 282,884 |
| Fully paired 4-variant groups | 57,594 | 70,721 |
| Public performance JSON documents | 18 | 18 |
| Standard JSONTestSuite valid files | 95 | 95 |
| Independent synthetic confirm probes | 24 | 24 |
| Standard JSONTestSuite conformance cases | 340 | 340 |
| Run state | `completed` | `completed` |
| Run stop reason | `overnight_budget` | `overnight_budget` |
| Expected-label / inter-variant disagreements | 0 / 0 | 0 / 0 |

All inner and outer ZIP archives passed CRC checks; each inner archive SHA-256 matches its `SYNC_OK.txt` proof. No missing or duplicated variants in any paired group. All DOM, Stage 1 and Stage 2 throughput entries are finite and positive.

## 1. 18 larger public JSON documents — candidate / official fallback

| Candidate | EPCC DOM | Cloud-V DOM | EPCC Stage 1 | Cloud-V Stage 1 | EPCC Stage 2 | Cloud-V Stage 2 |
|---|---:|---:|---:|---:|---:|---:|
| `A2_G16384` | 1.8944× | 1.5945× | 2.5042× | 2.0379× | 1.4694× | 1.2656× |
| `A2_SIMPLE_RUN` | 1.9004× | 1.5897× | 2.5062× | 2.0360× | 1.4774× | 1.2553× |
| `A2_NL4` | 1.9000× | 1.5837× | 2.5036× | 2.0335× | 1.4797× | 1.2488× |

All 18 public documents favor original A2 over the official fallback in full DOM throughput, on each machine.

### Incremental effect of Stage 2 patches on the 18 public JSON documents

| Candidate / unchanged A2 | EPCC DOM | Cloud-V DOM | EPCC Stage 2 | Cloud-V Stage 2 |
|---|---:|---:|---:|---:|
| `A2_SIMPLE_RUN` | 1.0032× | 0.9970× | 1.0055× | 0.9918× |
| `A2_NL4` | 1.0030× | 0.9932× | 1.0070× | 0.9867× |

The positive approximately +0.3% incremental DOM change on EPCC is not replicated on Cloud-V (approximately −0.3% to −0.7%). In this workload mix, enabling either patch globally would expose small negative public-file regressions on Cloud-V.

## 2. Standard JSONTestSuite valid files — candidate / official fallback

The 95 valid `y_` files range from 2 to 110 bytes; their median size is **8 bytes** and their mean is 12.5 bytes. This micro-document case is **not** a general real-world throughput proxy.

| Candidate | EPCC DOM | Cloud-V DOM | EPCC Stage 1 | Cloud-V Stage 1 | EPCC Stage 2 | Cloud-V Stage 2 |
|---|---:|---:|---:|---:|---:|---:|
| `A2_G16384` | 0.8501× | 0.6591× | 0.8501× | 0.6576× | 0.9158× | 0.9134× |
| `A2_SIMPLE_RUN` | 0.8472× | 0.6648× | 0.8497× | 0.6488× | 0.9285× | 0.9108× |
| `A2_NL4` | 0.8475× | 0.6573× | 0.8496× | 0.6561× | 0.9286× | 0.9138× |

- Original A2 DOM is 0.8501× official (−14.99%) on EPCC and 0.6591× official (−34.09%) on Cloud-V.
- EPCC: original A2 beats fallback in only 7/95 micro-documents. Cloud-V: original A2 wins in only 2/95.
- Stage 1 is also slower on these tiny inputs; startup, parsing overhead, dispatch and timer granularity plausibly dominate. These measurements cannot attribute an exact cause without a targeted microbenchmark.

## 3. Standard JSONTestSuite conformance

| Declared classification | Cases |
|---|---:|
| Valid (accept, `y_`) | 95 |
| Invalid (reject, `n_`) | 188 |
| Implementation-dependent (`i_`) | 35 |
| Transformation/auxiliary fixtures | 22 |
| **Total** | **340** |

Reported cross-variant disagreements: **0** on both systems; expected-label mismatches: **0**. For implementation-defined `i_` inputs the result only asserts consistency, not a universal JSON validity verdict. The reported `production_promotion_eligible: true` is a **conformance check**, not permission to promote a performance optimization automatically.

## 4. Independent synthetic confirmation: dense escapes

Only three synthetic families were measured by Test 104 (8 documents per family for each phase), i.e., **24 distinct synthetic confirmation documents** per machine. A ratio above 1 is faster; synthetic rows are **not pooled** with either public corpus.

| Family | Candidate | EPCC vs original A2 DOM | Cloud-V vs original A2 DOM | EPCC vs official DOM | Cloud-V vs official DOM |
|---|---|---:|---:|---:|---:|
| mixed | `A2_SIMPLE_RUN` | 1.390× | 1.342× | 2.451× | 1.976× |
| mixed | `A2_NL4` | 1.381× | 1.330× | 2.435× | 1.959× |
| newline | `A2_SIMPLE_RUN` | 1.382× | 1.320× | 2.447× | 1.950× |
| newline | `A2_NL4` | 1.463× | 1.366× | 2.591× | 2.017× |
| unicode | `A2_SIMPLE_RUN` | 1.000× | 0.997× | 2.318× | 1.894× |
| unicode | `A2_NL4` | 0.998× | 0.971× | 2.314× | 1.844× |

### Extreme mixed-escape density: approximately 50% raw backslashes

| Machine | Original A2 / official | SIMPLE_RUN / official | NL4 / official |
|---|---:|---:|---:|
| EPCC | 0.462× | 1.478× | 1.476× |
| Cloud-V | 0.430× | 1.218× | 1.279× |

The 50% mixed-escape case is a **pathological controlled input**, two exact-size documents per density point, not an observation of a real production distribution. In contrast, `\uXXXX` Unicode encoding physically cannot reach 50% raw backslashes because each token contains multiple bytes; always use recorded **actual**, not nominal, density.

## 5. Per-public-document DOM ratios — confirmation

| JSON file | EPCC A2 / official | EPCC SIMPLE_RUN / A2 | EPCC NL4 / A2 | Cloud-V A2 / official | Cloud-V SIMPLE_RUN / A2 | Cloud-V NL4 / A2 |
|---|---:|---:|---:|---:|---:|---:|
| `apache_builds.json` | 2.207× | 1.004× | 1.006× | 1.717× | 0.992× | 0.990× |
| `canada.json` | 1.288× | 0.997× | 0.997× | 1.330× | 0.995× | 1.007× |
| `citm_catalog.json` | 1.761× | 1.004× | 1.000× | 1.515× | 0.993× | 0.997× |
| `github_events.json` | 2.655× | 1.012× | 1.011× | 2.078× | 0.997× | 0.992× |
| `google_maps_api_compact_response.json` | 1.615× | 0.999× | 0.999× | 1.253× | 0.987× | 0.983× |
| `google_maps_api_response.json` | 1.692× | 1.003× | 1.000× | 1.410× | 0.988× | 0.986× |
| `gsoc-2018.json` | 4.160× | 1.012× | 1.007× | 3.090× | 1.010× | 1.003× |
| `instruments.json` | 1.758× | 0.999× | 0.998× | 1.449× | 0.991× | 0.996× |
| `marine_ik.json` | 1.389× | 0.999× | 1.004× | 1.260× | 1.011× | 1.004× |
| `mesh.json` | 1.358× | 1.000× | 1.004× | 1.352× | 1.015× | 1.007× |
| `mesh.pretty.json` | 1.491× | 0.998× | 0.999× | 1.492× | 1.006× | 1.000× |
| `numbers.json` | 1.322× | 1.006× | 1.003× | 1.407× | 1.005× | 0.996× |
| `twitter.json` | 2.368× | 1.005× | 1.006× | 1.871× | 0.993× | 0.992× |
| `twitter_api_compact_response.json` | 2.281× | 1.002× | 1.001× | 1.768× | 0.984× | 0.983× |
| `twitter_api_response.json` | 2.266× | 1.002× | 1.002× | 1.829× | 0.990× | 0.985× |
| `twitter_timeline.json` | 1.973× | 1.011× | 1.012× | 1.572× | 0.999× | 0.990× |
| `twitterescaped.json` | 1.806× | 1.000× | 1.000× | 1.385× | 1.001× | 0.982× |
| `update-center.json` | 2.294× | 1.003× | 1.004× | 1.657× | 0.989× | 0.985× |

## Verdict and engineering decision

1. **The 18 larger public files:** A2 remains +89.44% EPCC and +59.45% Cloud-V over official 5.0.4 fallback. The Stage 2 patches add negligible net public-file speed and cause small Cloud-V regressions.
2. **The 95 public JSONTestSuite micro-documents:** fallback is faster than A2 on most files, particularly Cloud-V. Do not conflate extremely small JSON inputs with large-file throughput.
3. **Conformance:** all 340 official cases have consistent results across all four variants on both machines, with zero expectation mismatches.
4. **Dense synthetic escapes:** both Stage 2 variants provide very large improvements compared with original A2; `NL4` is most beneficial on homogeneous newline runs while `SIMPLE_RUN` can be stronger on mixed escapes.
5. **No unconditional engine promotion.** First evaluate a cheap gated decoder on richer independent *real-world* escaped strings, and benchmark tiny-JSON dispatch overhead independently. Preserve the unchanged A2 variant for A/B checks.

## Artifact provenance

- Uploaded archives: `104_epcc.zip` and `104-cloudv.zip`, ZIP CRC verified.
- Both archives contain nested `test104_results.zip` whose SHA-256 matches the declared remote `SYNC_OK.txt` and whose core files hash-identically to outer ZIP files.
- Official commit: `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a`.
- Pinned conformance upstream commit: `1ef36fa01286573e846ac449e8683f8833c5b26a`.
- This report is based on actual benchmark CSVs and JSON manifests, with stage figures independently recomputed from paired raw rows rather than merely copied from report summaries.
