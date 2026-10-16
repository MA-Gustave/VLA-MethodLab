# Test 100 Cloud-V — Windows Download fix

## Symptom

Studio shows `Completed — ZIP ready`, but Download reports:

```
Download failed: unsupported operand type(s) for +: 'WindowsPath' and 'str'
```

This is a local recovery/download error; it does not change the completed remote measurements.
The screenshot alone does not pinpoint the original offending line, but it identifies a Windows path-type mismatch in the download path.

## Fix

- Routes **Tests > 100 > Download** on **Cloud-V** through a new, isolated, read-only recovery module.
- Keeps remote Linux paths as POSIX strings, and uses `pathlib.Path` joins for all local Windows destinations.
- Rechecks the **same selected run** before downloading; downloads to a `.part` file.
- Compares remote `sha256sum` against the actual bytes downloaded; validates ZIP member names, CRC, size and completed-run status before committing.
- Extracts files only after verification and writes `SYNC_OK.txt` last.
- Leaves **EPCC Download**, other test versions, corpus, source code, Test100 benchmark harness, SSH credentials, and remote jobs untouched.

## Installation — DROP ROOT

1. Back up `studio/rvvlab_simple_tests.py`.
2. Close **only** the Cloud-V Studio window. An EPCC Studio window may stay open.
3. Extract this ZIP into `C:\mycode\Simdjson\VLA-MethodLab\` (overwrite when prompted).
4. Start Cloud-V Studio again, connect, **Tests → 100 → Refresh → select existing run → Download**.
5. Do **not** click Run; the test has already completed.

Expected results folder:

```
<Studio results root>\TestRunner\test100-adaptive-public\Cloud-V-test100-20261016T144947Z-d71754\
```

## Offline verification

```
python -m unittest discover -s studio/tests -p test100_cloudv_download_fix.py -v
```

Six tests cover successful transfer, the selected remote path, SHA mismatch, an invalid archive path, an invalid completed status and the UI branch. These are offline simulations, **not** a live Windows/Cloud-V verification.

## Manual fallback

On Cloud-V SSH:

```
sha256sum ~/rvvlab-v5/test100-cloudv-runs/test100-20261016T144947Z-d71754/test100_results.zip
```

On Windows PowerShell (using existing SSH access to Cloud-V):

```
scp -P 985 gleblanc@machine2.cloud-v.co:/home/users/gleblanc/rvvlab-v5/test100-cloudv-runs/test100-20261016T144947Z-d71754/test100_results.zip "$env:USERPROFILE\Downloads\test100_cloudv_results.zip"
```

Compare with `Get-FileHash` after download.
