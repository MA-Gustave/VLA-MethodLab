# Test 104 — Independent public JSON validation (EPCC + Cloud-V)

**DROP ROOT** for `C:\mycode\Simdjson\VLA-MethodLab\`. Interface labels are in English.

## Purpose

Test 104 is a **holdout/validation campaign**, not a claim of an additional Stage 2 optimization. It uses the four compiled binaries already introduced in Test 103:

- `OFFICIAL_504`: pinned upstream simdjson 5.0.4 using **fallback**.
- `A2_G16384`: unchanged RVV A2, 16 KiB threshold; **the optimization reference**.
- `A2_SIMPLE_RUN`: experimental Stage 2 consecutive-simple-escape decoder.
- `A2_NL4`: consecutive-simple-escape decoder plus specialized runs of four `\n` pairs.

No existing engine source is modified; patches are applied to a **SHA-256-pinned compilation overlay**. The Test 103 results and the old Test Runner entries remain untouched.

## Official datasets

| Category | Provenance | How used |
|---|---|---|
| `public_original` | 18 original `simdjson-data` documents, commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf` | Main throughput and non-regression check, **not pooled** with others |
| JSONTestSuite `test_parsing/y_*.json` | `nst/JSONTestSuite`, commit `1ef36fa01286573e846ac449e8683f8833c5b26a` | Must accept; only accepted, four-way canonical-equal files enter `jsonsuite_valid` performance stratum |
| JSONTestSuite `test_parsing/n_*.json` | Same external pinned suite | Must reject; **correctness only**, never benchmark invalid JSON |
| JSONTestSuite `test_parsing/i_*.json` | Same external pinned suite | Acceptance unspecified; **unscored**, but crashes and disagreements are reported |
| JSONTestSuite `test_transform/*.json` | Same external pinned suite | Observed and recorded without inventing a normative acceptance expectation |
| `synthetic_explore` / `synthetic_confirm` | MethodLab-generated, byte-distinct seeds | Only selected stress controls (newline/mixed/Unicode, 0/10/25/50% requested raw escape density), **reported separately** |

The official JSONTestSuite archive is **not bundled** with the patch. The existing pinned corpus manager prepares and verifies it on your PC and syncs it to **each** server, with manifest and per-file SHA-256 verified again. No fabricated JSON files replace a missing public suite.

**Caution:** JSONTestSuite was designed primarily for parser **conformance**, not throughput. Its numerous tiny `y_` inputs have measurement overhead and are **not a representative production performance corpus**. The only independent larger performance corpus in this version remains the 18 public `simdjson-data` inputs. `jsonsuite_valid` results must not be marketed as a broad real-world speedup.

### Pass/fail reporting

`conformance104.csv` contains every upstream member and each binary's observed classification. `conformance104.json` includes class counts, unexpected accept/reject results, cross-binary disagreements and the number of valid y_ fixtures included in throughput. If **any** deviation exists, the campaign may finish collecting benchmark measurements, but its `production_promotion_eligible` flag is **false**. A measurement status of `completed` or `validated: true` does not override those conformance findings. The ZIP contains the full manifest; no failing input is silently discarded from the correctness report.

## Setup and launch

1. Back up `studio/` and `tools/`; close Studio when no local deployment is running. Extract this ZIP **at the Lab root**, overwriting only the included files.
2. Reopen Cloud-V Studio and EPCC Studio independently. In the **JSON Corpus** tab choose **Performance**, then **Prepare / Verify JSON** (18 public files). If already verified, do **not** download again.
3. Choose **Conformance · JSONTestSuite**, click **Prepare / Verify JSON** and wait for **Verified**; the first download requires Internet access. The version is pinned and existing verified local cache is reused. No conforming package = **no launch**.
4. Connect each SSH target. In **Tests → 104**, click **Refresh**, then **Run** once per server. The launcher syncs both verified corpus suites automatically; no separate manual remote upload is necessary.
5. Wait for EPCC **Slurm Job ID** and Cloud-V **detached PID** before disconnecting the PC. The jobs then continue on their own. Avoid concurrent CPU benchmarks on the **same** machine.
6. After completion or a documented error, use **Tests → 104 → Refresh → Download**. Inspect `conformance104.json` **before** interpreting `summary104.json` and `REPORT_104.md`.

## Time and resources

- Exploration: 4 hours (maximum), independent synthetic controls.
- Confirmation: 2 hours 30 minutes (maximum), same public documents, different synthetic seed.
- Worker maximum: **6 hours 30 minutes** excluding source upload/compilation, with retained partial results; EPCC Slurm limit **7 hours 30 minutes**.
- Native performance test: Stage 1, Stage 2 and DOM timed independently; do not add stage throughputs. Approximate per-file geometric ratios are calculated separately per phase, category and machine.
- Native correctness is checked **before** recording timing rows. Existing unknown/busy runs are not automatically replaced. Results are in `test104-cloudv-runs` or `test104-epcc-runs`.
- All CSV rows, input SHA-256, build flags, exact selected y_ fixtures, failures and independent corpus identities are preserved in SHA-256-verified result ZIPs.

## What has and has not been tested here

Local/offline verification covers pinned corpus checking, invalid-UTF-8 handling without Python parsing, synthetic controls, summary isolation, ZIP validation, new UI routing, and the Lab regression suite. The C++ checker was compiled and tested on x86_64 against normal/invalid/Unicode cases with the baseline and `SIMPLE_RUN` overlay. **No native RISC-V Test 104 compilation, Slurm submission, full pinned JSONTestSuite benchmark or actual Cloud-V/EPCC measurement was executed here.**

## When a run fails

Do **not** click Run a second time until the existing run state is verified. Refresh and download the diagnostic ZIP (status, build log, conformance output if created, Slurm errors). If a `y_` case fails the original upstream binary as well, report that specific upstream behavior separately from an optimization-induced regression.
