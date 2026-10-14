# Test 88: recover run, no rerun

Observed launch: `night-20261012T031326Z-43b730`. Remote status was `failed`, `observations=0`; the Studio's sync then rejected a 14-file manifest with `Too many files in manifest`. **The first error is the worker failure; the second is a Lab sync allowlist bug.** Fixing sync does not fix the worker.

## Install

Extract this ZIP into the existing **RVV-VLA-Lab repository root**, overwriting only the listed files. Both `orchestrator/rvvlab_night.py` and `studio/rvvlab_night.py` are patched to accept the versioned 14-file discovery snapshot (while verifying hashes and rejecting unknown file names). The 32 MiB limit now matches the worker. The existing `.env` at `C:\mycode\Simdjson\.env` is read, never modified.

## Pull

Double-click `PULL_TEST_88.bat`, or run:

```powershell
cd 'C:\mycode\Simdjson\RVV-VLA-Lab'
.\PULL_TEST_88.bat
```

First verify the patch locally with `python tools/test_snapshot_88_sync.py`. The script connects via pinned Paramiko SSH, obtains SHA256-verified snapshot if possible, and **also copies diagnostic logs** from the exact remote run directory. It never starts a test, deletes remote files, or performs a server-side update.

Upload `results/local/night-20261012T031326Z-43b730-diagnostics.zip` to ChatGPT so we can identify the original `stop_reason` and inspect the upstream and native GCC log tails. This is private diagnostic evidence: **do not commit it to a public repository without redacting personal server paths.**

Alternative after installing patch: `python tools/rvvlab.py sync night-20261012T031326Z-43b730`, which downloads the SHA256-verified result snapshot but does **not** retrieve the native compiler/benchmark diagnostic logs.

If the pull cannot connect, use the integrated SSH Console and run:

```bash
RUN="$HOME/rvvlab-v5/night-runs/night-20261012T031326Z-43b730"
cat "$RUN/status.json"
cat "$RUN/failures.csv"
tail -n 80 "$RUN/runner-startup.log"
for x in "$RUN"/compile_*.log "$RUN"/link_*.log "$RUN"/correctness_*.log "$RUN"/upstream_clone.log "$RUN"/latest_bench.log; do
  test -f "$x" && { echo "===== $x ====="; tail -n 50 "$x"; }
done
```

Do not rerun before investigating the failed official baseline and correctness gates. No test results can be claimed from this run.
