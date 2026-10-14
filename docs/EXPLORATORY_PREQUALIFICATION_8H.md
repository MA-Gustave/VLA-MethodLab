# Test 88 — Eight-hour expanded prequalification discovery

**Status:** Designed, corpus-generated and locally validated. **No native RVV performance numbers have been obtained for this test yet.**

## Goal

Discover falsifiable hypotheses about inexpensive JSON size gates and early
512-byte workload qualification. Go beyond the 174 examples in Test 87 by
building **767 precommitted valid JSON inputs** using a seeded corpus generator
(`20261012`) with intersecting properties and shifting workload geometry.
Avoid confusing synthetic type proxies with the actual selected runtime plan.

## Candidate binaries (10)

The pinned official simdjson v5.0.3 VLS256 control and nine RVV-VLA candidates:
A0/E14 original, A1 size gate, A2 quick 512-byte dispatcher, E01 adaptive,
sparse8/escape8, and E03 numeric / E05 escape / E06 Unicode-escape /
E07 UTF-8 forced-plan hypotheses.

Each plan compiles into a separate native binary with fixed flags. The suite
**does not claim** dynamic engine switching among these binaries, nor does it
implement A3 in-parse block refinement. A1/A2 share the E14 build policy as
controlled comparisons.

## 767 deterministic corpus scenarios

| Protocol dimension | Cases | What is varied |
|---|---:|---|
| Single family | 128 | 16 JSON families × 8 sizes, including real UTF-8, escaped Unicode, numeric exponents, punctuation in strings, slash-heavy text, booleans/null, nested arrays/objects, whitespace and sparse vs dense structural patterns |
| Pairwise mixtures | 352 | 22 contrasting pairs × 4 sizes × 4 placements (front, middle, back, alternating) |
| Triple mixtures | 144 | 12 three-way combinations × 4 sizes × 3 placements |
| Asymmetric skew | 72 | 6 signal types × 4 sizes × 3 misleading positions |
| Exact threshold edges | 51 | ASCII, escape, real UTF-8 × 17 exact sizes around 512 B, 1 KiB, 2 KiB, 4 KiB, 8 KiB and 16 KiB |
| Large stress | 20 | 10 dominant types × 2 and 4 MiB |
| **Total** | **767** | **~179 MiB** of deterministic input files |

All generated files are independently parsed with Python `json.loads`, SHA256
hashed and referenced in `corpus_manifest.json`. Byte-density proxies are
recorded on 512-byte beginning/middle/end samples and 4096-byte prefixes, to
highlight cases where a qualifier may mischaracterize later content.

## Timeline and fairness

The **480-minute cap includes preflight, official source checkout, ten GCC
compiles, correctness validation and benchmark loops**. The runner first
covers a deterministic representative *anchor set*, then attempts broad
coverage before repeating cases, with seeded case shuffling and rotating /
reversed candidate ordering. No parameter selection, curriculum steering, or
winning mode is decided from observed throughput during the campaign.

Every valid observation measures public DOM and direct internal Stage 1/Stage 2
separately, with three repetitions per timing. Candidate/reference throughput
ratios are paired on phase, corpus, iterations and trial. Small-input timing is
particularly susceptible to clock and call overhead. Repeated trials do not
constitute independent samples. The system may stop mid-sweep when its 8-hour
budget expires; incompletely paired data are excluded from aggregate ratios.

## Correctness / safety / audit

- Dedicated simdjson v5.0.3 code snapshot, runtime backend checks, seeded
  valid/invalid JSON classification, 256-bit native VLEN check and target GCC.
- CPU pinning, asynchronous SSH worker, global exclusive campaign lock,
  2 GiB run-workspace cap, 3 GiB free-space floor, graceful `STOP`, checkpoints
  and periodic cryptographic snapshot verification on result synchronization.
- Predeclared candidate flags from the engine library. A candidate that fails
  compilation or validation is recorded as a failure and never ranked as a win.
- `map.csv`, `ranking.csv`, `prequal_pairwise.csv`, `coverage_by_design.csv`,
  `hypotheses_to_confirm.csv`, `EXPLORATION_8H.md`, `corpus_manifest.json`,
  `metadata.json`, `failures.csv`, `checkpoint.json`, `status.json` and snapshot
  hashes/manifest. The GUI's final packet includes the derived files.
- No CPU-governor changes, sudo, automatic SSH login, unattended destructive
  cleanup or remote launch during installation.

**Interpretation:** the 767 inputs vary data conditions on **one** native RVV
machine, not multiple CPUs, compilers or operating systems. Synthetic data
and post-hoc extremes are hypothesis generators; any purported improvement
needs a fresh confirmatory run on held-out datasets.

## Commands

```powershell
cd "C:\mycode\Simdjson\RVV-VLA-Lab"
& .\.venv\Scripts\python.exe tools\test_prequal_88.py
& .\.venv\Scripts\python.exe tools\verify_release.py
python tools\rvvlab.py run prequal-8h --wait
python tools\rvvlab.py status
python tools\rvvlab.py sync night-YYYYMMDDTHHMMSSZ-abcdef
```

Or launch `LAUNCH_RVV_VLA_LAB.bat` and choose **Test 88** inside the integrated
Studio's Test Runner. A new run is started **only after manual approval**.
