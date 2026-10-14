# Experimental methodology and claims

## What is measured

- **Smoke (5 min):** native GCC/g++ build, executable probe, several valid/invalid JSON cases. No performance claims.
- **3h fixed grid:** 15 fixed `E00–E14` engine plans plus the `sparse8_escape8_reference` and official `upstream_vls256` reference. GCC `-O3`; paired DOM throughput in decimal GB/s. Each run compiles its own flags (no CMake/CPM benchmark dependencies).
- **60m/8h targeted:** four fixed variants (E14, E01, sparse8, official). Actual internal Stage 1 + Stage 2 and public DOM are measured independently; they are not derived by subtraction. Internal APIs are version-sensitive.
- **Correctness:** 3h uses a basic 6-valid/3-invalid gate. Stage profiling uses 169 valid and 24 invalid documents, including raw multibyte UTF-8. Neither gate is a substitute for full conformance, fuzzing and differential tape validation.

## Comparison rules

Geometric-mean throughput ratio per matched record. Pair by `(phase, corpus_id, parse_iterations, trial)`. Reference is separately compiled official `rvv_vls256` at v5.0.3 upstream commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249`. Values from different benchmark harnesses are **not directly interchangeable**. Timing conditions: original BPI-F3 / riscv64, RVV 1.0 VLEN=256, GCC 14.2.0, core 0, three-run median.

## Explicit limitations of the 2026-10-10 3h study

- Seven synthetic families; CITM and Twitter small/large workloads can contain duplicated content.
- Fixed order may introduce thermal/frequency/cache drift; the targeted stage profiles rotate order.
- No Stage 1/2 measurements in the original 3h data; those fields are blank.
- Historical results do not establish raw UTF-8 coverage or full semantic correctness.
- A dirty working-tree snapshot was transferred; an upstream SHA is not a complete hash of modified source content.
- No automatic winner selection; individual-family regressions matter.

## Reproducing on your hardware

`python tools/rvvlab.py preflight` → `python tools/rvvlab.py run smoke --wait` → choose a longer profile. Record CPU, VLEN, kernel/compiler, source zip hash, worker hash, run status, raw `map.csv`, paired `ranking.csv`, and failure diagnostics; preserve `SYNC_OK.txt` from SHA256 verified sync. Consult README for the full invocation.
