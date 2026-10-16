# RVV-VLA Lab Studio — elapsed wall-clock time

## Install (DROP ROOT)

1. Close Cloud-V and EPCC Studio windows. This does **not** stop detached remote benchmarks or submitted Slurm jobs.
2. Back up `VLA-MethodLab/studio/`.
3. Extract this ZIP directly into `C:\mycode\Simdjson\VLA-MethodLab\` (allow the `studio/` folder to merge and replace the existing `rvvlab_simple_tests.py`).
4. Restart Studio and connect to the target machine.
5. Choose a test and click **Refresh**. The selected test displays **Elapsed**, and the **Runs and Results** table has an **Elapsed** column.

## Meaning of the elapsed counter

- Uses `start_utc` / `started_utc` reported by the server when available.
- When no server start timestamp is available (e.g. early EPCC cross-compilation), uses the UTC creation timestamp in the run ID and prefixes the elapsed value with `≈` for **estimate**.
- Shows elapsed **wall time**, not CPU consumption. The counter itself does **not** prove that a process is still alive.
- Terminal runs freeze at a server-reported end/update timestamp. If no end timestamp is available, elapsed is shown as unknown rather than increasing indefinitely.
- Counter display updates once per second locally; the existing 60-second SSH verification rate is **not increased**.
- Does not change SSH configuration, results, benchmarks, or Slurm jobs.

## Tested locally

- `python -m unittest` suite from the available Method Lab snapshot: 58 tests passed under a virtual graphical display.
- Includes a graphical test of Test 97 Cloud-V and Test 99 EPCC states.
- Real-time confirmation with the user's live Cloud-V and EPCC servers remains necessary.

## Read-only Cloud-V Test 97 process time

```bash
bash -lc 'echo "=== TEST 97 ELAPSED TIME ==="; date -u "+Server UTC: %Y-%m-%d %H:%M:%S"; ps -eo pid,etime,etimes,lstart,stat,args | grep -E "[p]ython[0-9.]* .*/test97_native[.]py" || echo "No active Test 97 Python process"; echo "=== CAMPAIGN STATUS ==="; f="$HOME/rvvlab-v5/test97-runs/test97-20261015T190032Z-af59bc/status97.json"; if [ -f "$f" ]; then python3 -m json.tool "$f"; else echo "Status file not found"; fi'
```
