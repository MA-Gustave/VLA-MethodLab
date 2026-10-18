# Test 103 — Independent Performance Analysis

**EPCC + Cloud-V | 17 October 2026 | Official simdjson baseline and incremental Stage 2 optimization**

## Executive conclusion

Test 103 delivers **major genuine speedups on dense-escape synthetic JSON**, but **does not show a reliable universal gain on the 18 unchanged public JSON inputs**. The primary production reference is unchanged experimental RVV A2 at a 16 KiB threshold; official simdjson 5.0.4 `fallback` is a second reference, not an RVV-to-RVV baseline. Both campaigns completed, and all archived CSV measurement groups were audited for completeness and positive throughputs.

## Runs and verification

| Item | EPCC | Cloud-V |
|---|---:|---:|
| Measurements | 101,536 | 118,560 |
| Complete groups (4 variants) | 25,384 | 29,640 |
| Completed rounds | 114 | 133 |
| Status | `completed`, `validated: true` | `completed`, `validated: true` |
| Worker elapsed | 6 h 28 min | 6 h 28 min |
| Confirmed public inputs | 18 | 18 |

The archives have valid CRCs and their inner result ZIPs match the outer result CSV, status and summary. Input manifests and pinned public-corpus manifests are byte-identical across machines. Both build manifests agree on source, harness, stage2 patch, dispatch-plan and official commit hashes. All **220,096 rows** are complete four-variant groups with positive finite DOM, Stage 1 and Stage 2 throughput.

## Speedup versus official simdjson 5.0.4 fallback: public original JSON

Equal-weight geometric mean across 18 unchanged original public documents, using repeated paired observations within documents. Phase **confirm** only.

| Variant | EPCC DOM | EPCC throughput gain | Cloud-V DOM | Cloud-V throughput gain |
|---|---:|---:|---:|---:|
| Unmodified A2 16 KiB | 1.893× | +89.27% | 1.595× | +59.47% |
| SIMPLE_RUN | 1.899× | +89.89% | 1.589× | +58.92% |
| NL4 | 1.899× | +89.90% | 1.585× | +58.48% |

The official baseline uses **fallback**, not an official RVV implementation. These ~1.6–1.9× ratios measure the combined changes in backend/fork, not the incremental Test 103 code changes.

### Incremental speedup over unchanged A2 (primary optimization result)

| Candidate | EPCC DOM | EPCC Stage 2 | Cloud-V DOM | Cloud-V Stage 2 |
|---|---:|---:|---:|---:|
| SIMPLE_RUN | +0.33% | +0.56% | -0.35% | -0.89% |
| NL4 | +0.33% | +0.69% | -0.62% | -1.36% |

On EPCC, both variants show small public-JSON gains. On Cloud-V, both show small public-JSON regressions. Stage 1 is unchanged in principle; minor measured Stage 1 deltas between binaries should not be interpreted as an intended algorithmic Stage 1 improvement.

## Incremental DOM speedups across synthetic families

These are intentionally generated workload strata, **not independent realistic JSON samples**. Each family receives its own geometric average over input fixtures; exploration and confirmation are kept separate.

| Family | EPCC SIMPLE_RUN | EPCC NL4 | Cloud-V SIMPLE_RUN | Cloud-V NL4 |
|---|---:|---:|---:|---:|
| newline | +18.43% | +21.27% | +15.46% | +14.96% |
| mixed | +18.27% | +17.61% | +16.34% | +13.89% |
| quote | +18.01% | +17.11% | +15.33% | +12.19% |
| slash | +18.40% | +17.59% | +16.25% | +14.15% |
| unicode | +0.54% | -0.11% | -0.45% | -2.30% |
| crossover | +2.48% | +1.82% | +1.78% | +1.34% |

NL4 wins specifically for repeated `\n` on EPCC, but SIMPLE_RUN is generally better on mixed, quote and slash cases. Unicode improvements are not established; Cloud-V NL4 regresses on the unicode synthetic family.

## Pathological maximum-density probes: relative to A2 and official

The following use requested **50% raw backslash density** with exact actual median density shown. `slash` inputs encode a repeated `\\` sequence and therefore have nearly 100% actual raw backslash density. `unicode` escape tokens cap actual density near 16.6%.

| Machine | Family | Actual backslashes | Unmodified A2 / official DOM | SIMPLE_RUN / A2 DOM | NL4 / A2 DOM | SIMPLE_RUN / official DOM | NL4 / official DOM |
|---|---|---:|---:|---:|---:|---:|---:|
| EPCC | newline | 49.9% | 0.471× | 3.083× | 4.027× | 1.453× | 1.898× |
| EPCC | mixed | 49.9% | 0.462× | 3.199× | 3.193× | 1.478× | 1.476× |
| EPCC | quote | 49.9% | 0.486× | 2.991× | 2.985× | 1.454× | 1.451× |
| EPCC | slash | 99.7% | 0.462× | 3.189× | 3.182× | 1.473× | 1.470× |
| EPCC | unicode | 16.6% | 1.426× | 0.994× | 1.001× | 1.418× | 1.428× |
| Cloud-V | newline | 49.9% | 0.439× | 2.721× | 3.443× | 1.194× | 1.511× |
| Cloud-V | mixed | 49.9% | 0.431× | 2.848× | 2.990× | 1.228× | 1.289× |
| Cloud-V | quote | 49.9% | 0.447× | 2.673× | 2.799× | 1.194× | 1.250× |
| Cloud-V | slash | 99.7% | 0.431× | 2.848× | 2.990× | 1.229× | 1.290× |
| Cloud-V | unicode | 16.6% | 1.194× | 1.000× | 0.952× | 1.194× | 1.137× |

At 50% raw escapes on the mixed family, the unchanged A2 is ~0.462× official on EPCC and ~0.431× on Cloud-V. SIMPLE_RUN converts this to approximately 1.48× and 1.23× official respectively, although these are only **two synthetic fixtures per family/density** repeated across rounds. The repeated newline family shows additional specialized NL4 advantages, while the unicode-only scenario does not.

## Public JSON by-document incremental DOM ratios

Candidate / A2 original. Above 1.000× = faster; below 1.000× = slower.

| Public JSON | EPCC SIMPLE_RUN | EPCC NL4 | Cloud-V SIMPLE_RUN | Cloud-V NL4 |
|---|---:|---:|---:|---:|
| `apache_builds.json` | 1.003× | 1.005× | 0.991× | 0.989× |
| `canada.json` | 0.998× | 0.996× | 0.998× | 1.010× |
| `citm_catalog.json` | 1.002× | 1.003× | 0.991× | 0.998× |
| `github_events.json` | 1.013× | 1.011× | 0.998× | 0.993× |
| `google_maps_api_compact_response.json` | 1.000× | 1.000× | 0.986× | 0.983× |
| `google_maps_api_response.json` | 1.003× | 1.001× | 0.989× | 0.987× |
| `gsoc-2018.json` | 1.014× | 1.013× | 1.008× | 1.002× |
| `instruments.json` | 1.000× | 0.999× | 0.990× | 0.998× |
| `marine_ik.json` | 0.996× | 1.000× | 1.013× | 1.008× |
| `mesh.json` | 0.998× | 0.998× | 1.014× | 1.009× |
| `mesh.pretty.json` | 0.997× | 1.000× | 1.004× | 1.000× |
| `numbers.json` | 1.004× | 1.005× | 1.004× | 0.997× |
| `twitter.json` | 1.005× | 1.003× | 0.995× | 0.992× |
| `twitter_api_compact_response.json` | 1.001× | 1.001× | 0.983× | 0.979× |
| `twitter_api_response.json` | 1.004× | 1.001× | 0.990× | 0.984× |
| `twitter_timeline.json` | 1.012× | 1.014× | 0.996× | 0.990× |
| `twitterescaped.json` | 1.002× | 1.001× | 1.002× | 0.984× |
| `update-center.json` | 1.008× | 1.008× | 0.989× | 0.985× |

## Decision and next steps

1. **Do not enable SIMPLE_RUN or NL4 unconditionally in the production parser.** Cloud-V experiences small but repeatable average public-JSON regressions, and some individual documents regress by up to ~2.1% with NL4. This fails a zero-regression policy.
2. **Treat the Stage 2 work as a real optimization discovery.** High escape density yields +100–300% DOM on pathological cases, repeatedly reproduced across both machines, with substantial Stage 2 speedup. This validates the Test 102 diagnosis.
3. **A next version should isolate a low-overhead density-aware decoder dispatch** or an eligibility gate that activates the run decoder only when a consecutive escape run is actually encountered. Evaluate dynamic detection overhead, the length of runs, and effects on original public documents, UTF-8 and Unicode escape handling.
4. **Correctness validation must be expanded** beyond the native pinned preflight: JSONTestSuite negative/Unicode cases, overlong strings and truncated escapes, invalid sequences and boundary placements. Completion and `validated: true` are evidence of the campaign checks only, not formal proof of all JSON edge cases.
5. **Confirm fresh holdout results** and additional independent real-world escaped-heavy JSON before promotion. The EPCC and Cloud-V runs use the same source and fixtures but different toolchains and hardware; preserve platform-specific results.

## Provenance

- EPCC result ZIP SHA-256: `fd8f67674b3881181b2b8397f4bcef07b95eff7dee2472c4b947d84abf70f3dd`.
- Cloud-V result ZIP SHA-256: `daa2406112ad1d67bd432ef5e079dc64b6403edcc39309c28cf963f5561c4b1e`.
- Raw archives: `test103_results (2).zip` (EPCC) and `103-cloudv.zip` (Cloud-V).
- The independent analysis checks nested result integrity, per-variant comparison-group completeness, finite positive measurements and matching source/input metadata. Speedups are recomputed from `results103.csv`, not copied from `REPORT_103.md`.

---
*Performance conclusions apply to the exact tested RISC-V hosts, compiler/toolchains, pinned public corpus and stated synthetic input distributions. No new remote experiment was executed for this report.*
