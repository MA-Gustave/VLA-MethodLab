# Test 104 — Studio status and download routing hotfix

**Target:** Cloud-V and EPCC Studio windows. **No server or benchmark files changed.**

## What was found

Inspection of `znapshot_VLA-MethodLab_10171822.zip` and of the original `VLA-MethodLab_TEST104_INDEPENDENT_JSON_VALIDATION_EPCC_CLOUDV_DROP_ROOT_20261017.zip` found a partially carried-forward fix:

- The Test 103/104 `test_id` lookup in `rvvlab_unified_campaigns.py` was present in the Test 104 package, addressing the earlier Test 103 `KeyError` for that particular mapping.
- However, **Test 103 and Test 104 were absent from four managed-run action lists and from the `Open Results` number mapping**, so **Sync results**, **Open results** and stop-guard buttons were not consistently routed to the per-test tools and local result directories.
- The Test 104 package **did not include the `SimpleTestsPanel._drain` fault isolation** that had been added in the previous Test 103 Studio status hotfix. A non-Tk error in the supplementary campaign view could still halt the main Tests status event pump, leaving a previously displayed `Preparing` or `Running` state frozen even after the remote run has finished.

This hotfix patches both Python files together to fix the Test 103 regression and support Test 104. It neither starts, stops nor reruns experiments.

## Installation order

1. Close both Studio windows after local transfers are idle.
2. First install the **Test 104 original DROP ROOT** if it is not already installed.
3. Extract the **Test 104 Studio status hotfix ZIP** directly into `C:\mycode\Simdjson\VLA-MethodLab\`, accepting replacement of two Python files in `studio/` and addition of one test in `studio/tests/`.
4. Reopen Studio Cloud-V and EPCC, reconnect, then select **Tests -> 103 or 104 -> Refresh**. Only a server-verified `state=completed` with `validated=true`, positive row count and a present ZIP becomes **Completed — ZIP ready**. Click **Download** when enabled.
5. Do **not** relaunch a completed server campaign; the hotfix affects the Windows UI only.

## Validation

- Synthetic remote responses for completed Test 103 and Test 104 runs on **both** Cloud-V and EPCC: pass.
- Forced `KeyError` from the auxiliary campaign-history panel: the primary Tests status still updates, error is logged, and the **250-ms event queue reschedules normally**.
- Download/Open/Stop management mapping includes Test 103 and Test 104.
- **121 offline/Studio regression tests pass (1 skipped)** under virtual display, against a Lab snapshot merged with Test 104 and this hotfix.
- No direct interrogation of live remote hosts was conducted as part of this verification.

The display may still show `Preparing` if a remote status is genuinely missing or SSH verification fails. This patch prevents the confirmed UI-specific hang; it does not fabricate remote completion.
