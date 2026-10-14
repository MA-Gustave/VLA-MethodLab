# Provenance and registration of original additions

**Scope:** independent second-phase RVV-VLA Lab experiments and future original additions only. This document does not reopen the history of other repositories or earlier contributions.

**Archive reference:** snapshot supplied 2026-10-14. **Git history, first-publication date, earlier grants, AI-assisted copyright status, and line-level ownership were not included**. Therefore the candidate groups below are **not automatically Covered Additions**.

## Candidate groups requiring source-by-source review

| Candidate project area | Why it warrants review | Coverage status |
| --- | --- | --- |
| `experiments/` (patterns, workers, research protocols) | Lab-specific orchestration and experiments; individual artifacts may incorporate inherited ideas, templates, or prior publications | **UNVERIFIED — not registered** |
| `orchestrator/` and `studio/` | Lab-specific tools and interfaces; verify any third-party portions and earlier publication | **UNVERIFIED — not registered** |
| `tools/rvvlab.py` and additional Lab tool scripts | Independent control, evidence and validation logic, subject to file-by-file verification | **UNVERIFIED — not registered** |
| `engine/src/rvv/`, `engine/include/simdjson/rvv*`, dispatch/build integration | **Mixed-origin engine**: may combine original simdjson and Lab changes; a path alone cannot establish exclusive copyright | **UNVERIFIED — not registered** |

The independent snapshot fingerprints can be used as **forensic reference, not proof of ownership or publication timing**: [`PROVENANCE-CANDIDATES-SHA256.txt`](PROVENANCE-CANDIDATES-SHA256.txt).

## Verified Covered Additions register

**No entry has yet been verified for this snapshot.** Do not assert that its already distributed code is newly restricted merely because of this notice.

For each eligible future addition, add a record *before or at first publication* with all required fields and verify conflicts with GitHub/platform terms:

| Exact path and copyrightable lines / patch ID | Immutable commit or SHA-256 | Rights holder and human original authorship evidence | First public release and earlier grants checked | Date of explicit rights reservation | Status |
| --- | --- | --- | --- | --- | --- |
| *(None registered yet)* | — | — | — | — | — |

Permitted status for an enforceable entry: `VERIFIED — COVERED`, only after evidence supports each requirement of [`LICENSE-ORIGINAL-ADDITIONS.md`](LICENSE-ORIGINAL-ADDITIONS.md). Avoid designating prior public material as covered without specialized review. Add file-level notices to genuinely new source code before dissemination, referring to its registry record.

## Rights and history

The original simdjson copyright and third-party notices remain in force for inherited portions, including where a new implementation modifies a shared file. Independent implementations of the same ideas remain possible. Benchmark data and performance improvements alone do not establish ownership of source-code expression.
