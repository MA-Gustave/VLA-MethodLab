# Test 97: RVV-A2 vs. upstream simdjson v5 on EPCC RISC-V

**Run date:** 2026-10-15 (UTC)  
**Run ID:** `test97-20261015T163613Z-0a5b6c`  
**Platform:** EPCC `rvc02`, RISC-V 64-bit / Spacemit X60  
**Status:** Completed; correctness validation passed  
**Scope:** Full DOM parsing throughput using the public simdjson API

## Executive summary

On the synthetic JSON workload used by Test 97, the experimental RVV-A2 parser with an **8,192-byte activation threshold** delivered a **1.4716x geometric-mean throughput ratio (+47.16%)** relative to **unmodified upstream simdjson v5.0.4**, built with its **`fallback` backend** on the same EPCC RISC-V compute node. This result comes from **891 independent-seed holdout groups** with four paired implementations per group.

The existing RVV-A2 configuration (4,096-byte threshold) delivered **1.4458x (+44.58%)** over the same upstream baseline. Increasing the threshold to 8,192 bytes yielded an **additional 1.0179x (+1.79%)** relative to that RVV-A2 configuration.

**Interpretation:** The **+47.16%** figure is a measured advantage of the RVV-enabled experimental fork **over the official scalar `fallback` implementation on this particular benchmark mix and machine**. It is **not** an isolated algorithmic improvement over an upstream RVV implementation, nor a claim of a 47% gain on all real-world JSON files.

## Variants compared

| Variant | Source | Selected backend | Adaptive V2 minimum input size |
|---|---|---|---:|
| `OFFICIAL_503` | Upstream simdjson tag `v5.0.3` | `fallback` | N/A |
| `OFFICIAL_504` | Upstream simdjson tag `v5.0.4` | `fallback` | N/A |
| `A2_REF` | Experimental laboratory fork | `rvv` | 4,096 bytes |
| `A2_G8192` | Same experimental fork | `rvv` | 8,192 bytes |

For both RVV-A2 builds, the Test 97 configuration disabled the experimental packed control/index/escape/quote/shift paths. The two RVV builds differ in `SIMDJSON_RVV_ADAPTIVE_V2_MIN_BYTES` (4,096 vs. 8,192). The official sources were checked out at pinned release tags and were not patched for this test.

## Primary results: independent holdout

The metric is the **geometric mean of paired per-document DOM throughput ratios**. A ratio above `1.0x` means greater throughput than the comparison implementation.

| Comparison | Complete pairs | Throughput ratio | Relative throughput change |
|---|---:|---:|---:|
| Upstream v5.0.4 vs. itself | 891 | 1.0000x | Baseline |
| Upstream v5.0.3 vs. v5.0.4 | 891 | 0.9997x | -0.03% |
| `A2_REF` vs. upstream v5.0.4 | 891 | **1.4458x** | **+44.58%** |
| `A2_G8192` vs. upstream v5.0.4 | 891 | **1.4716x** | **+47.16%** |
| `A2_G8192` vs. `A2_REF` | 891 | **1.0179x** | **+1.79%** |

### Results by workload scenario (holdout)

| Scenario | Paired groups | `A2_REF` / upstream v5.0.4 | `A2_G8192` / upstream v5.0.4 |
|---|---:|---:|---:|
| `anchor` | 208 | 2.1000x | 2.1000x |
| `boundary` | 667 | 1.2663x | 1.2967x |
| `region_mix` | 16 | 2.8318x | 2.8289x |
| **All scenarios (geometric mean)** | **891** | **1.4458x** | **1.4716x** |

The `boundary` scenario accounts for **667 of 891 holdout groups (74.9%)**. The all-scenario geometric mean is therefore specific to this test's workload distribution; it is not a workload-weighted prediction for general deployments.

### Results by JSON family (holdout)

The following figures were recomputed from the raw `results97.csv` by pairing each `A2_G8192` observation with its `OFFICIAL_504` observation for the same holdout group and taking the geometric mean of the ratios.

| Synthetic JSON family | Paired groups | Throughput ratio | Change vs. upstream v5.0.4 |
|---|---:|---:|---:|
| Long strings | 32 | 5.777x | +477.70% |
| UTF-8 | 32 | 5.037x | +403.75% |
| ASCII | 188 | 1.691x | +69.14% |
| Booleans / null | 16 | 1.664x | +66.45% |
| Dense | 181 | 1.510x | +51.02% |
| Integers | 16 | 1.409x | +40.92% |
| Nested | 16 | 1.367x | +36.69% |
| Many keys | 16 | 1.367x | +36.67% |
| Floats | 16 | 1.304x | +30.44% |
| Mixed UTF-8 / whitespace / ASCII / integers / Unicode escapes | 16 | 2.829x | +182.89% |
| Unicode escapes | 181 | 1.181x | +18.07% |
| **Escaped strings** | **181** | **0.938x** | **-6.24%** |

**Regression to investigate:** The experimental RVV configuration is **6.24% slower in throughput on the synthetic `escaped` family** than upstream v5.0.4 `fallback`. Strong results in UTF-8 and long-string families should not obscure this regression. Family-level results, especially those with 16 or 32 groups, require further replication.

## Training/measurement phase consistency

| Comparison | Train (2,725 groups) | Holdout (891 groups) |
|---|---:|---:|
| `A2_REF` / upstream v5.0.4 | 1.4348x | 1.4458x |
| `A2_G8192` / upstream v5.0.4 | 1.4610x | 1.4716x |
| `A2_G8192` / `A2_REF` | 1.0183x | 1.0179x |
| Upstream v5.0.4 / v5.0.3 | 1.0000x | 1.0003x |

The close train/holdout ratios are encouraging **within this generated-workload design**. They do not replace independent trials on different days, additional devices, or real-world corpora.

## Experimental setup and methodology

- **Hardware:** EPCC RISC-V compute node `rvc02`, Spacemit X60, 8 logical CPUs, Linux `riscv64`. The run selected CPU 0 with `taskset` when available; `machine97.json` records the machine's initial allowed affinity `[0, 1]` and a `performance` scaling governor.
- **Compilation:** EPCC LLVM/Clang 16 RISC-V cross-compiler, targeting `riscv64-unknown-linux-gnu`; common optimization options include `-O3`, `-DNDEBUG`, `-std=c++17`, `-march=rv64gcv`, and `-mabi=lp64d`. Each implementation was compiled into its own RISC-V ELF64 benchmark binary from the corresponding sources.
- **API:** The same `tools/test97_dom.cpp` benchmark harness and public `simdjson::dom::parser` API were used for all variants. The benchmark measures whole-document DOM parsing, not a sum of separate Stage 1/Stage 2 results.
- **Validation:** All variants first passed a set of valid/invalid JSON cases. Every generated document was checked for successful parsing and matching serialized DOM output across the four variants before timing.
- **Pairing:** Every group used the **same generated JSON document** for all four variants. Execution order was randomized within each group to reduce fixed-order bias.
- **Timing:** Each benchmark invocation included eight warm-up parses and five measured repetitions; the **median** of those five throughput measurements was retained. The iteration count was bounded by the document size.
- **Duration:** 10,800 seconds (3 hours) total, reserving the final 2,700 seconds (45 minutes) for the holdout phase. Holdout documents used a separate seed offset.
- **Data:** 14,464 throughput observations = **3,616 complete groups x 4 variants**; 2,725 groups in `train` and 891 in `holdout`. No groups or variant measurements are missing in the supplied CSV.
- **Input design:** Synthetic ASCII, dense, escaped, Unicode-escape, UTF-8, numerical, nested, many-key, long-string and mixed documents, with deliberately over-represented exact-size boundary cases around adaptive thresholds. Exact-size boundary documents include an ASCII padding field, which matters when interpreting family labels.

For each group, the speedup is `throughput(candidate) / throughput(reference)`. Reported aggregate speedups use:

```text
geometric_mean_speedup = exp(mean(log(throughput_candidate / throughput_reference)))
throughput_change_percent = 100 * (geometric_mean_speedup - 1)
```

The geometric-mean ratios are **descriptive**, not confidence intervals or a claim of statistical significance.

## Traceability and integrity

| Item | Recorded value |
|---|---|
| Run ID | `test97-20261015T163613Z-0a5b6c` |
| Measurement window | 2026-10-15 16:37:52 to 19:37:45 UTC |
| Final state | `completed`, `validated: true` |
| Upstream v5.0.3 commit | `bf89ddd00ef5fcb6a7f20611ea8853d258b67249` |
| Upstream v5.0.4 commit | `3b0b2b53aaffb46208817821dce2cd47a5e6bb2a` |
| Common benchmark harness SHA-256 | `919783a593ca675aff11ab8ac57b12f0012cddc1d484d1425bbe086f8da46d89` |
| Fork source (`src/simdjson.cpp`) SHA-256 | `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16` |
| Fork engine plan SHA-256 | `7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e` |
| Result archive SHA-256 | `88fc10391c785e05318ef37c8c710c9b1dd41514bf623a64d79cabfba0b4d548` |

The downloaded `test97_results.zip` hash matches `SYNC_OK(5).txt`. All seven files inside the archive match the separately supplied copies byte for byte. `builds97.json` records a successful build for every variant and the exact compiler options and binary hashes.

**Additional observation:** The two upstream tags have different source commit IDs but yielded the **same recorded SHA-256 for their benchmark binaries** under this build configuration. Their measured throughput was correspondingly near-identical; this does not establish that the releases are identical in other configurations.

Primary artifacts: `test97_results.zip` (containing `results97.csv`, `summary97.json`, `status97.json`, `builds97.json`, `machine97.json`, `manifest97.json`, and the generated `REPORT_97.md`). The source-side test harness and runner are `tools/test97_dom.cpp`, `tools/test97_native.py`, and `tools/test97_epcc.sbatch`.

## Limitations

1. **Backend asymmetry:** Official simdjson was measured using the published **scalar `fallback`** implementation. The fork used its RVV backend. The observed advantage includes vectorization and implementation differences; it does not demonstrate a 47% improvement over an official upstream RVV path.
2. **Synthetic, unbalanced input distribution:** Boundary-focused cases dominate the aggregate. Exact-size samples include artificial ASCII padding. Results should not be generalized to typical production documents or workloads without a representative corpus.
3. **Single run and hardware configuration:** One EPCC node, one three-hour session, one compiler toolchain and one selected CPU. No cross-day variance, uncertainty interval, energy analysis or cross-device measurements are provided.
4. **Correctness scope:** The checks performed are useful but are not a proof of full JSON specification compliance across all inputs.
5. **No automatic promotion:** The benchmark identifies candidate performance characteristics; it does not by itself justify adopting a threshold globally or merging the fork into upstream simdjson.

## Suggested follow-up

- Repeat the experiment on a **real-world JSON corpus**, preserving identical files and paired comparisons for all variants.
- Investigate the **escaped-string regression** with targeted profiling and correctness stress tests.
- Re-run on separate days and, when available, additional RISC-V machines; report uncertainty intervals over appropriately independent units.
- Evaluate thresholds by workload family and file size, rather than selecting the global threshold only from an aggregate dominated by synthetic boundary documents.
- Retain provenance hashes, raw paired results, and exact compiler/backend configurations with future benchmark reports.

## Conclusion

**Test 97 establishes a 1.4716x (+47.16%) geometric-mean DOM throughput advantage for the experimental RVV-A2 threshold-8192 build over official simdjson v5.0.4 `fallback` on the defined EPCC RISC-V synthetic benchmark.** The higher threshold adds **1.0179x (+1.79%)** over the fork's threshold-4096 configuration. These are reproducible, auditable observations within the recorded test setup, **not a universal performance claim**.
