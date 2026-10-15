# Test 92 — Eight-Hour Adaptive RVV Composition Exploration: Performance Report

**Report date:** 13 October 2026  
**Campaign:** `night-20261013T011722Z-d61b0f`  
**Profile:** `composition-explorer-92-8h`  
**Evidence:** uploaded signed/synced campaign export (`map.csv`, `diagnostics.csv`, `status.json`, `metadata.json`, `build_provenance.json`, `composition_catalog.json`, `failures.csv`, `EXPLORATION_92.md`), plus Test Runner log.  
**Baseline:** dedicated **A2 RVV-VLA** executable (defined as **100% throughput / 0% delta**).  
**Secondary reference:** **official VLS256** executable.  
**Environment:** native RV64GC(V), hardware VLEN 256 bits, governor `performance`, pinned CPU 0, Bianbu GCC 14.2.0, native (no QEMU), parser source based on simdjson v5.0.3.

## 1. Executive summary

The Test 92 campaign successfully completed its staged screening, adaptive exploration, Stage 1 stress work, and fresh-seed holdout within the eight-hour allocation. The campaign ended in **`stopped` due to the wall-time budget**, *not* because of a native correctness failure. The Test Runner reported **PASS** after verified result retrieval.

**Key finding:** None of the experimental compositions exceeded the dedicated A2 baseline on full-DOM throughput in any of the **5,863 complete matched three-way groups**. The strongest independently evaluated composition, `P2345c07522b1`, reached **0.762× A2 (−23.77% throughput)** on 60 fresh-seed holdout JSON documents, while reaching **1.202× official VLS256 (+20.22% throughput)** on the *same* documents. Stage 1 degradation, unlike Stage 2, explains much of the observed end-to-end gap at the level of a diagnostic correlation; it has **not** been causally isolated.

**Decision:** Do **not** automatically promote a Test 92 candidate to production. The next experiment should quantify the compile-time packed-feature cost separately from the incremental experimental runtime dispatch cost and examine known region-switching designs. A focused **Test 93 (≤3 h)** is prepared for that purpose.

## 2. Execution quality and coverage

| Indicator | Measured result |
|---|---:|
| Campaign budget | 8 h / 28,800 s, including native builds |
| Research compositions in initial catalog | 242 |
| Native-valid compositions | 242 / 242 (100%) |
| Rejected compositions | 0 |
| Native reference/research builds | 3 / 3 passed (A2, official VLS256, research compositions) |
| Total measurement rows | 17,591 |
| Complete triplets: experimental / A2 / official | 5,863 |
| Incomplete triplets | 1 (2 extra measurement rows) |
| Unique materialized JSON designs | 1,808 |
| Training JSON designs | 1,748 |
| Fresh-seed holdout JSON designs | 60 |
| Holdout groups with all three results | 357 |
| Prespecified reference/validity failures (`failures.csv`) | 0 rows |
| Native production parser changed | No |

The campaign executed 242 screening groups, 96 refinement groups, 2,539 adaptive groups, 1,363 specialist groups, 677 Stage 1 focus groups, 431 dedicated overhead-control groups, 158 repeat groups, and 357 complete holdout groups. This confirms that adaptive exploration **was actually reached**, not just configured.

**Source/build comparability.** All three binaries were compiled natively at `-O3 -DNDEBUG -g0`, but with **different compile-time flags**. A2 disables packed-control/index-writer, while the research executable enables them and compiles `SIMDJSON_RVV_EXPLORATION91=1`. Consequently, the research-vs-A2 difference is **not** attributable to experimental dispatch alone. The official VLS256 binary also targets a different RVV implementation, so it is a useful secondary reference, not an A2 clone.

## 3. Throughput results relative to the A2 baseline

**Definition.** For each complete group and throughput component: `ratio = experimental_GBps / A2_GBps`. **Percentage change = (ratio − 1) × 100**. Ratios are calculated on the **same generated JSON and the same iteration count**, not as a ratio of grand-average speeds from different workloads. Unless stated otherwise, the ratios below use the **geometric mean** of these paired throughput ratios. Because the scheduler adaptively oversampled selected candidates and families, train-set aggregates are **descriptive only**, not representative production-weighted averages.

### 3.1 Six finalists — independent fresh-seed holdout

| Composition | Holdout JSON | Full DOM / A2 | Full DOM vs A2 | Full DOM vs official | Stage 1 vs A2 | Stage 2 vs A2 | DOM wins over official |
|---|---:|---:|---:|---:|---:|---:|---:|
| `P2345c07522b1` | 60 | 0.762× | **-23.77%** | +20.22% | -41.19% | +1.48% | 44/60 |
| `P6f95844a1fa9` | 60 | 0.757× | **-24.26%** | +20.00% | -42.06% | +0.93% | 44/60 |
| `Pe991d1cf900e` | 60 | 0.752× | **-24.79%** | +18.65% | -43.08% | +1.70% | 44/60 |
| `P6efa917c9c5c` | 59 | 0.750× | **-25.02%** | +17.84% | -42.94% | +0.40% | 43/59 |
| `P33b932b286a3` | 59 | 0.747× | **-25.26%** | +17.49% | -43.22% | +0.89% | 42/59 |
| `P4254a8de150e` | 59 | 0.746× | **-25.42%** | +17.30% | -43.57% | +0.72% | 43/59 |

**Primary finding:** The best measured full-DOM throughput is still about **24% below dedicated A2**. No finalist wins against A2 on any of its 59–60 measured holdout documents. The top two finalists differ by less than **0.5 percentage point of A2-normalized throughput**; this campaign does not establish a statistically durable ordering between them.

### 3.2 Aggregate holdout stage behavior (all finalists; descriptive)

| Throughput metric | Relative to A2 | Delta versus A2 |
|---|---:|---:|
| Full-DOM throughput | 0.752× | -24.75% |
| Stage 1 throughput | 0.573× | -42.68% |
| Stage 2 throughput | 1.010× | +1.02% |
| Official VLS256 full DOM throughput | 0.635× | -36.55% |

For comparison, the best final candidate's full-DOM throughput is **+20.22% versus official VLS256** on its 60 holdout documents. This is a distinct baseline: being faster than the official implementation **does not imply** being faster than A2.

## 4. Isolating the experimental overhead

The dedicated Test 92 `overhead_control` phase ran the research composition `P7042b142196b` with `policy=0` against the separately compiled A2 baseline and official VLS256, all on the same JSON per group. It recorded **431 complete triplets** across **6 unique anchor JSON designs**.

| Metric | Research `policy=0` / A2 | Relative delta |
|---|---:|---:|
| Full DOM — geometric mean | 0.689× | -31.09% |
| Stage 1 — geometric mean | 0.512× | -48.83% |
| Stage 2 — geometric mean | 1.007× | +0.72% |
| Full DOM — median paired ratio | 0.773× | -22.75% |

The large difference between the geometric mean and median reflects **substantial workload dependence**, particularly the long-strings anchor. Neither aggregate should be treated as a production population estimate.

**Interpretation and limitation:** A control policy that avoids regional switching still loses substantial throughput relative to the **dedicated** A2 build. This supports investigating the research-binary/code-generation overhead before tuning additional dynamic policies. However, the control **does not** independently isolate the instrumentation cost because the research build also changes packed compile-time flags and implementation code. Test 93 therefore adds a separately compiled packed-but-not-exploratory binary.

## 5. Regional switching and Stage 1

Trace diagnostics show:

| Policy | Diagnostic traces | Traces with active regions | Traces with ≥1 region switch |
|---|---:|---:|---:|
| 0 | 503 | 0 | 0 |
| 1 | 3702 | 0 | 0 |
| 2 | 799 | 0 | 0 |
| 3 | 356 | 292 | 268 |
| 4 | 504 | 0 | 0 |

Only **policy 3** generated nonzero regional counters in this run. All six holdout finalists use **`policy=1`, `gate=0`**, with no regional switches. Thus the best-scoring finalists are **static composition choices**, not demonstrated successes of dynamic regional switching. The absence of region switches in those finalists is expected for their policy and must not be presented as a malfunction.

The sharp drop in Stage 1 throughput is the dominant diagnostic pattern: across the holdout, Stage 1 is roughly **−42.7% throughput** relative to A2, whereas Stage 2 is around **+1.0%**. These are *independent* timed paths, **not** additive components of the public full-DOM wall time. They motivate targeted profiling rather than proving a specific root cause.

**Stress case:** On the holdout `utf8` single-family document, the leading `P2345c07522b1` candidate delivered about **0.471× A2 DOM (−52.89%)** and **0.398× A2 Stage 1 (−60.21%)**. This is **one JSON case**, not a family-wide estimate; Test 93 deliberately repeats UTF-8 and long-string stress on multiple sizes and region layouts.

## 6. Methodological constraints

1. **Warm repeated-document throughput.** The harness takes three median repeats per metric and reuses a warmed document. These numbers are not cold-cache latency or first-parse throughput.
2. **Synthetic data.** The generator repeats a 16-atom vocabulary per family. Results are not a substitute for independent real-world JSON distributions.
3. **Paired measurement, adaptive sampling.** Each complete group is fairly paired, but global training averages mix different adaptively sampled populations; separate fresh-seed holdout is preferred for candidate comparison.
4. **Shared holdout seeds.** The six finalists saw the same fresh-seed documents in shared rounds, but the last round was partial (59 versus 60 cases). Rank differences need repeated independent confirmation.
5. **No false attribution.** Different binaries use different compile-time options and code paths. `policy=0` is a probe, not a perfectly controlled no-overhead counterfactual.
6. **Regional instrumentation is not free.** Full-DOM agreement, region tracing and codegen overhead need independent evaluation before applying a candidate in production.
7. **Normal deadline shutdown.** `status.json` reads `stopped`, and the report's reason says `Test91 wall-time budget reached`: a **reused inherited label bug**, not evidence that Test 91 was run. `metadata.json` and the Test Runner log identify this campaign as Test 92. The subsequent Windows `[WinError 10054]` occurred while reading the campaign list **after** the runner logged PASS and downloaded the result packet.

## 7. Recommended Test 93 — fixed 3-hour investigation

**Research question:** How much of the full-DOM and Stage 1 gap is associated with packed compile-time options, how much is associated with the experimental runtime path (`policy=0`), and how do static and actively switching regional policies compare on the same JSON?

**Four-way matched comparisons:**
- `A2` — dedicated A2 baseline, reference **100%**.
- `official` — upstream/official VLS256, secondary baseline.
- `packed_plain` — packed-control/index-writer compile options enabled, **without** `SIMDJSON_RVV_EXPLORATION91`.
- `compositions` — experimental policy configuration; includes `policy=0`, static finalists and region-switching candidates.

**Fixed candidates:** Test 92 `policy=0` and static control, top three holdout finalists, a policy 2 and 4 plan, plus two policy 3 plans with observed switching (`Pf9f644d6d8a0`, `P638c6d2cc96b`). Four-way comparisons use the same JSON/iterations and **shuffled benchmark order**. The 3h clock includes four native builds and validation; 80% of the remaining post-build time is used for shared, repeated stress anchors and the last 20% for fresh-seed holdout. Max JSON size for this targeted run is 8 MiB, leaving 64 MiB coverage to Test 92.

**Acceptance criteria:** four successful native builds; full-DOM fallback agreement; at least one complete four-way comparison on each initially scheduled anchor; synchronized `map.csv`, `controls93.csv`, `diagnostics.csv` and `EXPLORATION_93.md`; report paired geometric means separately for training and holdout. The result must **not** automatically promote any candidate. If time expires before full anchor coverage, report partial coverage honestly rather than inferring success.

## 8. Bottom line

Test 92 successfully collected broad, correctness-checked, source-pinned evidence and showed that the staged scheduler was operational. It did **not** demonstrate a throughput improvement versus **dedicated A2**. It did show that static experimental plans can outperform the **official** reference on many holdout documents, while a major Stage 1 gap and research-binary confounding remain. The most efficient next step is **Test 93 (≤3 hours)**, not another wide eight-hour search.

---

*Calculation note:* all percentages in the holdout table are computed from per-group throughput ratios; full-DOM geometric means match the uploaded `EXPLORATION_92.md` after rounding. Counts exclude the single incomplete group. Report generated exclusively from the uploaded Test 92 result archive and runner log; no fresh native Test 93 results are claimed.
