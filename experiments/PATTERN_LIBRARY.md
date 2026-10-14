# RVV-VLA engine-pattern library

Test 91 adds [242 explicit compositions](compositions91.json), using the same native plan and writer primitives. The canonical generator is `engine/scripts/rvv/explore91/design.py`. See [the experimental protocol](../README-TEST91.md). E00–E14 below remain the historical fixed controls.

The 15 fixed engine plans below are present **in source** in
[`engine/src/rvv/engines/`](../engine/src/rvv/engines/). They were attempted
in the 2026-10-10 native RISC-V study. The build selection flags in the linked
JSON are the implementation contract, not informal labels.

> **Important:** A successful compiler smoke is not full JSON conformance.
> The performance data were gathered on one VLEN=256 machine; retest on your own hardware.

| Plan | Compiler flags | Research hypothesis |
|---|---|---|
| `E00_historical` | `-DSIMDJSON_RVV_ENGINE_LIBRARY=0` | Full v5 RVV-VLA historical baseline |
| `E01_adaptive` | `-DSIMDJSON_RVV_ENGINE_LIBRARY=1 -DSIMDJSON_RVV_FORCE_PLAN=0` | Bounded document classifier + engine composition |
| `E02_dense` | `-DSIMDJSON_RVV_FORCE_PLAN=2` | Favor compressed vectors earlier on dense documents |
| `E03_numeric` | `-DSIMDJSON_RVV_FORCE_PLAN=3` | Sparse writer 8 and low-escape path on numeric inputs |
| `E04_text` | `-DSIMDJSON_RVV_FORCE_PLAN=4` | Fast-path whole interior-string blocks |
| `E05_escaped` | `-DSIMDJSON_RVV_FORCE_PLAN=5` | Sparse escape threshold 8 and no packed quote/shift |
| `E06_unicode_escape` | `-DSIMDJSON_RVV_FORCE_PLAN=6` | ASCII Unicode-escape strings need sparse backslash handling |
| `E07_utf8` | `-DSIMDJSON_RVV_FORCE_PLAN=7` | Literal UTF-8 differs from escaped Unicode corpus |
| `E08_balanced` | `-DSIMDJSON_RVV_FORCE_PLAN=8` | Compare common plan without classifier overhead |
| `E09_mask_writer` | `-DSIMDJSON_RVV_FORCE_PLAN=9` | Word-mask writer for medium-density blocks |
| `E10_packed_escape` | `-DSIMDJSON_RVV_FORCE_PLAN=10` | Check cost of packed escape on escaped strings |
| `E11_packed_quote_shift` | `-DSIMDJSON_RVV_FORCE_PLAN=11` | Retest combined packed quote/shift as negative control |
| `E12_string_fastpath_only` | `-DSIMDJSON_RVV_FORCE_PLAN=12` | Isolate new fast path without other policy changes |
| `E13_stage2_prefetch` | `-DSIMDJSON_RVV_FORCE_PLAN=0 -DSIMDJSON_RVV_STAGE2_PREFETCH=1` | Hint Stage2 before generic tape-builder parse; experimental |
| `E14_packed_disabled` | `-DSIMDJSON_RVV_FORCE_PLAN=0 -DSIMDJSON_RVV_ENABLE_PACKED_CONTROL=0 -DSIMDJSON_RVV_ENABLE_PACKED_INDEX_WRITER=0` | Confirm packed-control penalty in newly composed paths |

## Relevant implementations

- `engine_plan.h` — plan selection and policy.
- `workload_profile.h` — bounded workload classification.
- `structural_writers.h` — sparse and mask-based structural writers.
- `stage2_bridge.h` — integration point for Stage 2 experimentation.
- `src/rvv/stage1.h` — active Stage 1 glue and dispatch.
- `src/rvv/string_scanner.h` and `utf8_validation.h` — string/UTF-8 paths.

## Experimental controls

`E00_historical` is a historical *internal* plan, not the official upstream implementation.
The official control is separately compiled `upstream_vls256`. Our `sparse8_escape8`
control also runs as a separate build. Do not conflate the three.
