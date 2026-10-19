# Test 101 — Confirm A2 dispatch thresholds (Cloud-V + EPCC)

## Install / launch

Close both Studio windows after any local launcher finishes. Back up `studio` and `tools`. Unzip the DROP ROOT archive into `C:\mycode\Simdjson\VLA-MethodLab\`, allowing the files to replace their previous versions. Open the dedicated Cloud-V and EPCC Studio windows. Select `Tests > 101`, click **Refresh**, then **Run** once on each machine. Separate machines may run independently; do not start another CPU benchmark on the **same** remote machine.

`JSON Corpus > Performance` should show the 18 pinned JSON fixtures prepared locally. The Test101 launcher synchronizes and checks the corpus itself, so it has **no premature `requires_shared_corpus` manifest gate**. If the repository path is stale, set it to the complete `engine` checkout before starting.

**Expected states:** Building / Preparing, EPCC queued (Slurm), Running (measurements increasing), Completed (ZIP ready), Failed (downloadable diagnostics). Closing the Studio window after verified detached Cloud-V launch or Slurm submission does not end the remote run. Test 101 uses separate folders and does not replace Test 100 results.

## Experimental design

- Six binaries: official v5.0.4 fallback, A2 4096, 8192, 10240, 12288, 16384.
- Data strata: 18 original public JSON (byte-identical), deterministic valid structural fragments derived from those originals (not independent real documents), 87 exact-size synthetic probes.
- Native DOM checks run across all six binaries before any benchmarking. The corpus commit and SHA-256 are checked before build or Slurm.
- Adaptive measurement minimum 60 minutes + 30-minute confirmation; maximum 6 hours measurement, EPCC Slurm wall limit 7.5 hours. It may stop early only after three sufficiently stable consecutive rounds.
- Paired geometric DOM throughput by stratum, compared to 4 KiB and 8 KiB baselines; original-source weighting for derived documents; raw per-file values preserved.
- Source and harness hashes recorded, SHA-256 results ZIP; partial results and diagnostics retained on failure.

## Remote directories

- EPCC: `$HOME/rvvlab-v5/test101-epcc-runs/test101-.../`
- Cloud-V: `$HOME/rvvlab-v5/test101-cloudv-runs/test101-.../`

The Studio **Download** button verifies the archive SHA-256. Windows paths are handled by a dedicated Test101 downloader; the Test100 downloader remains unchanged. A failed run may also have a ZIP with `status101.json`, `REPORT_101.md`, and `slurm101-runtime.log` where applicable.

## Warnings

This is a research protocol; unlike a live remote test, the DROP ROOT package can only be validated **locally** here. LLVM16 cross-compilation, native GCC build, JSON-derived fixture generation on the pinned dataset, and complete measurements still require actual server execution.

`OFFICIAL_504` uses fallback while A2 uses RVV. Do not treat that ratio as a same-backend ablation. No score pools original, derived or synthetic strata. No threshold is auto-promoted to production.
