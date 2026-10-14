# Tests 91–93 — native exploration and diagnostics (v6.2)

- `explore-91-pilot`: 1h native composition pilot, same mechanisms as the broad test.
- `explore-91-8h`: 8h wide exploration, three builds, 242 plans and family-derived compositions.
- `explore-92-8h`: 8h staged screening (242 plans), 48-plan refinement, Stage 1 and runtime-overhead controls, frozen holdout. **Manual only**.
- `diagnose-93-3h`: <=3h four-way matched A2 / official / packed-without-exploration / instrumented-policy comparison. Nine prespecified plans, Stage 1 and regional diagnostics. **Manual only**.

Use Studio **Run selected**. These three profiles are excluded from **Run enabled queue**.
Read [README-TEST91.md](../README-TEST91.md) and [README-TEST92.md](../README-TEST92.md), and [README-TEST93.md](../README-TEST93.md). Older profiles below are retained.

# Curated test profiles

All four presets execute directly on your remote RISC-V Linux machine with
native GCC and write immutable run directories beneath `~/rvvlab-v5/night-runs/`.

| Preset | Worker | Budget | Purpose |
|---|---|---|---|
| `smoke` | `82_engine_library_smoke_5m_worker.py` | 5 minutes | Compiler + JSON probe |
| `stages-60m` | `83_stage_profile_60m_worker.py` | 60 minutes | 4-plan Stage1/Stage2/DOM |
| `matrix-3h` | `81_engine_library_3h_worker.py` | 3 hours | 17-plan DOM screening |
| `stages-8h` | `84_stage_profile_8h_worker.py` | 8 hours | Extended 4-plan stage profiling |

**Budget begins when the worker starts on the server.** Upload/preflight time is extra.
Remote workers checkpoint, honor a `STOP` file, and export SHA256-checkable snapshots.
The `tools/rvvlab.py` orchestrator uses the exact same workers as the Studio manifests.
It refuses a new test if an earlier run is active in its namespace.

## 87 — Exploratory Adaptive Prequalification (60 min)

`prequal-60m`: precommitted 174-case adaptive A0/A1/A2 vs official VLS256 survey,
rough 512/4096-byte head/mid/tail sampling proxies, true DOM/Stage 1/Stage 2;
**unconfirmed exploratory trends**, no auto-tuning. Full protocol:
[`docs/EXPLORATORY_PREQUALIFICATION_60M.md`](../docs/EXPLORATORY_PREQUALIFICATION_60M.md).
