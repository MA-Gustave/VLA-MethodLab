# Test 107 — Visible in Tests / LOCAL final release audit (UI fix)

**Purpose:** Fix the Test 107 UI registration in the existing VLA-MethodLab snapshot (2026-10-18 15:47). This overlay is **DROP ROOT**: extract directly into `C:\mycode\Simdjson\VLA-MethodLab\`, **merge/replace**, then **close and restart** both Studio windows.

## Confirmed root cause

The earlier Test107 overlay installed the audit script and manifest in `studio/test_scripts/`, and the Test Runner discovered it. But the main **Tests** pane used a **hard-coded catalogue ending at 106**; it never included Test 107. Also, `run_trial()` required SSH globally, even though Test107 does not communicate with any remote machine.

This patch registers **107 as a local audit** in the **Tests** list on both Cloud-V and EPCC profiles, without presenting it as a remote benchmark.

## Workflow in the main Tests tab (no SSH required)

1. Close **all Studio windows** and extract this ZIP into the **VLA-MethodLab root** (not VectorPath).
2. Restart either Studio. Open the **Tests** tab and select **107** in the left list. Machine is shown as **LOCAL**.
3. Click **Run LOCAL audit** and select, in order:
   - **Cloud-V** Test106 completed ZIP (for example `106-cloudv.zip`)
   - **EPCC** Test106 completed ZIP (for example `106-eppc.zip`)
   - Optionally the **VectorPath-RVV A2 release candidate DROP ROOT ZIP** (recommended for source verification).
4. Confirm the operation. It reads only local ZIPs. **No SSH connection, Slurm job, compilation, network request, or new benchmark occurs.**
5. Click **Refresh** to see local history; **Export ZIP** to choose where to copy the report, or **Open** to inspect the local result directory.

Results are stored in `<configured results folder>/TestRunner/test107-formal-release-qualification/<UTC timestamp>/`:

- `TEST107_RELEASE_AUDIT.md`
- `TEST107_RELEASE_AUDIT.json`
- `test107_release_audit.zip`
- `inputs.json` (audit input paths and script digest; **not** packaged into the exported ZIP)

For invalid inputs, the same folder contains `TEST107_FAILURE.json` and **no successful ZIP**. The UI presents this as a failure instead of a completed success.

### Alternative: Advanced > Test Runner

The Test107 manifest remains accessible in **Advanced > Test Runner**. The global SSH requirement has been lifted **only** for Test107. That older entry searches already downloaded Test106 archives under the **configured results root**; for arbitrary paths, the **main Tests pane** is easier and recommended.

## Audit scope and status

Test107 validates two already completed native Test106 result archives, their integrity, provenance, binary identity, paired gains and JSONTestSuite conformance. The outcome **ENGINE PASS** means a qualifying evidence audit, **not a fresh performance measurement**. `SHIP HOLD_CI_AND_RELEASE_SIGNOFF` remains intentional until CI fuzz/Valgrind evidence and final release sign-off are handled separately. The audit never claims that the GitHub Actions #74 failure is fixed.

**Safety/compatibility:** No `engine/` or VectorPath files changed, no historical Test94–106 scripts/results overwritten, no new remote runs. The existing local Test107 auditor is included in full for repeatable installation. The package changes only Studio UI/runner integration, targeted tests and documentation.

**Local verification:** 148 Studio unit tests passed under an xvfb-backed Tk display. A direct end-to-end audit of supplied Cloud-V and EPCC Test106 ZIPs yielded 167,835 validated rows, ENGINE PASS, `SHIP HOLD_CI_AND_RELEASE_SIGNOFF`, and a verified frozen VectorPath distribution when provided.
