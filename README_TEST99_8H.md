# Test 99 — 8-hour public JSON performance campaign

## Install (DROP ROOT)

1. Close both Studio instances.
2. Back up `VLA-MethodLab/studio` and `VLA-MethodLab/tools` if you have custom changes.
3. Extract this ZIP **inside the root of** `C:\mycode\Simdjson\VLA-MethodLab\`. Preserve the `studio/` and `tools/` directories.
4. Start Studio, select **Cloud-V** or **EPCC**, connect via the matching SSH profile.
5. Open **JSON Corpus → Performance**, click **Prepare / Verify JSON**, then **Sync to server** and **Check server** (unless already verified).
6. Open **Tests → Test 99**. Click **Refresh**, then **Run**. Do **not** click Run again while the server is preparing, running or pending.
7. Later click **Refresh**, wait for **Completed — ZIP ready**, then **Download**. The Studio UI checks the remote completion, rows, validation and ZIP before enabling Download. Remote runs continue when Studio closes.

Do not start Test 99 while another RVV benchmark is running on the same CPU/node. Only one Test 99 run per profile is allowed through the default launcher; re-runs require an explicit new-run workflow, not repeated clicks.

## Scientific protocol

- **Corpus:** same 18 public, SHA256-checked JSON files from the existing shared *Performance* corpus (pinned simdjson-data commit `4197c425e857f0ec38e89822fdd0bd9ea21f4daf`). JSONTestSuite's 340 conformance files are **not** included in the performance calculations.
- **Five C++ binaries:** official simdjson 5.0.3 and 5.0.4 (`fallback` on RISC-V), A2 4096/6144/8192-byte threshold (`rvv`, packed off), all `-O3` under the same machine toolchain.
- **Time:** 28,800 seconds / 8 h of native measurements **after compilation**. First ~6 h exploration, last ~2 h *confirmation* on the **same files**. Confirmation is not a true independent-document holdout. Compilation and upload add extra time.
- **EPCC:** cross-compile on the x86_64 login server using the existing LLVM 16 toolchain; then submit one Slurm job on `rvc02` in the `riscv` partition, requesting **08:20:00** wall time to allow a modest margin. Scheduler limits, queue time and module availability have not been verified here.
- **Cloud-V:** compile natively and run in a detached process protected by `flock`; one shared lock prevents two Test99 processes from running concurrently.
- **Correctness:** parse/canonical DOM check of all variants on each JSON document before timing. Measurements refuse a mismatched baseline.
- **Noise mitigation:** shuffle document order and variant order per round; record A2 reference speed before and after each document's group. Report per-document geometric means then equal-weight files. Record relative reference drift; do not mistake multiple measurements of the same file for independent examples.
- **Disk safety:** builds require ~700 MiB free; in-run safety limit 150 MiB. No automatic deletions of old results.

## Expected remote artifacts

Cloud-V: `~/rvvlab-v5/test99-cloudv-runs/test99-<timestamp>-<suffix>/`

EPCC: `~/rvvlab-v5/test99-epcc-runs/test99-<timestamp>-<suffix>/`

Each completed run publishes `status99.json` (`state=completed`, `validated=true`, positive `rows`), `test99_results.zip` and `test99_results.sha256`. The ZIP contains exactly:

- `builds99.json`
- `machine99.json`
- `status99.json`
- `results99.csv`
- `summary99.json`
- `REPORT_99.md`
- `corpus_manifest99.json`

Local downloads are stored under Studio's configured results directory, within `TestRunner/test99-public-8h/` and a machine/run-specific folder. EPCC and Cloud-V recovery verify remote SHA-256 and ZIP integrity.

## Interpretation and limitations

Official releases use `fallback`, while the fork's A2 uses `rvv`. The resulting ratio measures end-to-end difference on a RISC-V host, *not* a matched-backend microarchitectural advantage. CPU performance can drift over 8 hours. The corpus contains only 18 fixed published files; equal-weight aggregation avoids overweighting large JSON files, but does not imply production representativeness. Compare confirmation results and per-file details before recommending a new default threshold.

## Safety and rollout

Only Test99 tools and the Studio modules required to register/status/download Test99 are in this patch. Existing Tests 94–98, the engine, SSH credentials, and corpus cache are not included or overwritten. Tested locally using simulated statuses and offline regression. Native builds and Slurm wall-time acceptance must be validated on the real target machines.
