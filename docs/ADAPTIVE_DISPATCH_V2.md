# Adaptive Workload Dispatch v2 · fixed A/B study

**Scope:** simdjson v5.0.3 RVV-VLA, focused on *low-cost* size gating and coarse workload selection. Nothing in this overlay changes the JSON parser API or parsing validity rules. It changes the Stage 1 **algorithm plan selection**, using the existing per-parse `engines::choose()` integration. Stage 2 remains unchanged. Streaming mode and explicit `FORCE_PLAN` variants retain their historical policy.

## Implementation

| Profile | Size < 4 KiB | Size >= 4 KiB | Flags on top of E14 |
| --- | --- | --- | --- |
| **A0 Original E14** | Original `tiny` / existing 4 KiB prefix | Examine up to **4,096 bytes** | `SIMDJSON_RVV_ADAPTIVE_V2_LEVEL=0` (default) |
| **A1 Size Gate** | Balanced E14 fastpath, **no classifier** | Original up to **4,096 bytes** | `SIMDJSON_RVV_ADAPTIVE_V2_LEVEL=1` |
| **A2 Quick Dispatch** | Balanced E14 fastpath, **no classifier** | Examine **512 bytes** and classify approximately | `SIMDJSON_RVV_ADAPTIVE_V2_LEVEL=2` |

The v2 selection remains a bounded *separate prefix inspection*, **not** the proposed zero-overhead fused scanning. That integration would be A3 and requires correctness-sensitive modifications to block/state transitions. It is **not implemented** in this release.

The default `SIMDJSON_RVV_ADAPTIVE_V2_LEVEL=0` leaves the existing E14 policy intact. A1 and A2 are opt-in *compile-time* experiment profiles; this is **not** runtime switching between separate compiled backend binaries. The engine configurations exposed by `plan` are all compatible with the active RVV Stage 1 dataflow. Each candidate has its own binary in the native benchmark, exactly like the previous fixed grid.

## Cost model

For any document, classifier effort is bounded by the smaller of document length and the chosen prefix limit. A1 and A2 make the small case constant-time. A2 bounds the large case to 512 bytes. **Whether this increases actual DOM speed remains to be measured.** The candidate can regress when representative JSON features occur past the first 512 bytes. It is conservative in correctness, not necessarily conservative in performance.

## Tests (sequential, approved manually)

1. Run portable dispatch unit test and microbenchmark (`python tools/test_adaptive_v2.py --microbenchmark`). The timing reported here is **only plan-selection overhead on the local development CPU**, not DOM speed.
2. Studio → Test Runner → **Adaptive Dispatch v2 — 5-minute native GCC smoke (A2)**, select manually. This builds A2 for native RVV and exercises its parser smoke harness without speed claims.
3. **Wait for smoke status and results.** If it passes, start **Adaptive Dispatch v2 — 30-minute A0/A1/A2 Stage1/Stage2/DOM A/B**. This compiles all four fixed candidates including separately built official simdjson VLS256, checks 169 valid/24 invalid JSON inputs, rotates measurement order and records small/medium/large JSON separately.
4. Stop when the budget ends, download SHA256-verified packet and analyze A0/A1/A2 by size and corpus. Do **not** launch A3 or a longer run automatically.

Remote workers use up to **2 GiB workspace**, require **4 GiB available at launch**, stop under **3 GiB free**, cap builds and record failures. The 30-minute budget includes GCC builds; short campaigns may end with few measurements if compilation/upstream fetch is slow. There is no automatic result promotion or Git push.

## What must be compared

- DOM throughput: A1/A0 and A2/A0 paired on `(phase,corpus,parse_iterations,trial)`; separately versus official `rvv_vls256`.
- Distinguish **128 B / 2,048 B / 4,095 B / 4,096 B / 8,192 B** from native **1 MiB / 4 MiB** datasets; don't extrapolate the speedup of E14 on 1-4 MiB to tiny files.
- Stage 1 vs Stage 2: measure separately using same native harness and remember they do not sum to DOM API time.
- Misclassifications as *performance signals*, not JSON validity signals. Verify full parsing and invalid JSON handling before evaluating speed.

**No server tests were started as part of this release.** The accompanying test runner scripts are manual and SHA256-pinned.
