# Test 98 — Quick start (EPCC and Cloud-V)

**Purpose:** replace Test97's generated synthetic JSON inputs with **18 original documents** from the pinned `simdjson/simdjson-data` public fixture repository. This is a *real published-file* benchmark, but the fixture collection still has limitations as a representative workload; inspect per-file results.

## Installation

Apply the provided **VLA-MethodLab Test98 patch** into the Lab root (preserve existing local configs). Apply the separate **VectorPath Test98 patch** into the VectorPath repository so the shared corpus manager and documentation are versioned alongside the engine.

## First run on EPCC

1. In Studio choose the **EPCC** SSH profile and connect.
2. In **Test Runner**, choose **Test 98 — Corpus public simdjson-data : RVV vs officiel (EPCC / Cloud-V)**.
3. Click **Run selected**. Studio downloads JSON directly from the pinned `simdjson-data` Git commit locally (requires HTTPS on your PC), caches the source corpus ZIP in `engine/.cache/test98-corpus`, SFTP-copies it once to EPCC, and validates remote SHA256.
4. The fork engine source is deployed separately; upstream simdjson v5.0.3/v5.0.4 are cloned from official GitHub tags on the EPCC login node; cross-compilation must pass before submission to Slurm `rvc02`.
5. The compute node runs a **60-minute** real-file DOM benchmark, including the last 15 minutes of independent *timing repetition* (same files; **not** an independent data holdout).
6. To check progress or recover, click **the same Test 98 entry** again. Alternatively use **Centre des tests → Vérifier serveur → Télécharger / synchroniser** after completion. No second 'recovery test' exists.

## First run on Cloud-V

Choose the **Cloud-V** profile, then use the exact **same Test 98 entry**. Studio reuses the already-downloaded local ZIP and transfers the identical bytes to Cloud-V once. Cloud-V must have Python 3, Git, network access to GitHub **for the official code only**, and a native RISC-V `g++` compiler. If anything is missing, the runner fails explicitly instead of silently testing a different library.

## Results and interpretation

`test98_results.zip` contains `results98.csv`, `summary98.json`, `REPORT_98.md`, `status98.json`, `builds98.json`, `machine98.json`, and `corpus_manifest98.json`. Do **not** claim a measured gain until the real EPCC or Cloud-V results exist.

The Test98 output computes per-document paired ratios and an equally weighted geometric mean across files. The official simdjson v5.0.4 uses scalar `fallback` on the target RISC-V CPUs and the fork uses `rvv`. Differences across EPCC vs Cloud-V must be reported separately, not pooled without qualification.

**Caution:** The data is NOT packaged in the code ZIP. Here, external downloads are not available, so local validation uses synthetic *test fixtures only for the archive integrity tests*, never for Test98 measurements. First real downloading is performed by your installed Studio.

**Source selection:** In Studio, point the Repository field to the **complete current VectorPath-RVV root** (or explicitly select the bundled Lab engine if that is what you intend to benchmark). Test98 refuses silently replacing an incomplete configured engine with a different fallback snapshot.
