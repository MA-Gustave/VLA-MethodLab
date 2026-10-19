# VLA-MethodLab — VectorPath A2 release candidate integration (Test 106)

**Installation target: `C:\mycode\Simdjson\VLA-MethodLab\` (DROP ROOT).** This is the companion Lab update for the **separately shipped** VectorPath-RVV A2 release candidate dated 2026-10-18.

**Status: release validation ready; NOT approved for final shipping on actual RVV hardware.** No EPCC/Cloud-V Test 106 job has been launched by building this ZIP.

## Why the historic Lab engine is not overwritten

`engine/src/simdjson.cpp` and `engine/src/rvv/engines/engine_plan.h` in this snapshot match the SHA-256 identities used for Tests 101–105:

| File | Original pinned SHA-256 |
|---|---|
| `engine/src/simdjson.cpp` | `fdaea284a48b30ab3e912e1cd3580e920fe186a229faabba97d9b24eed095e16` |
| `engine/src/rvv/engines/engine_plan.h` | `7ebd7d2f4606c9ed9db77bcced50371e669698e5278f1afc4e5369fc5b4e7f4e` |

Updating these *in place* would invalidate past experiment source pinning and may make older Test 101–105 preflights reject the source. **This DROP ROOT does not modify `engine/`, does not rewrite results, and does not replace your separately installed VectorPath-RVV repository.**

Instead it adds a small immutable, SHA-256-pinned **five-file source overlay** at:

`release_candidates/vectorpath_a2_rc_20261018/vectorpath_rc_sources.zip`

Test 106 deploys the old MethodLab engine as it always did, creates a **separate source copy in the new run directory**, verifies each original/patched file SHA-256, applies the VectorPath RC changes to that copy, then compiles the actual variants against both source roots. The overlay exactly corresponds to the VectorPath release candidate supplied earlier. The previous source paths and singleheader are not modified by Lab.

## Test 106: short final same-machine A/B

| Binary | Compiler/backend | Source purpose |
|---|---|---|
| `OFFICIAL_504` | official simdjson v5.0.4 **fallback** | historical external reference |
| `A2_ORIGINAL` | original RVV 16KiB packed-off | **scientific reference on that machine** |
| `VP_STABLE` | updated VectorPath RVV A2 defaults | **intended shipping candidate** |
| `VP_SIMPLE` | VP_STABLE + SIMPLE_RUN | optional Stage 2 research |
| `VP_NL4` | VP_STABLE + SIMPLE_RUN + NL4 | optional Stage 2 research |

Each of these **five real RISC-V binaries** is independently compiled and SHA-256 recorded. EPCC uses its existing LLVM16 toolchain; Cloud-V uses its existing native GCC. Do not compare absolute GB/s across hardware/compiler environments as if they were fixed.

### Data and checks

- **Pinned 18 original simdjson-data JSONs**: identical bytes and order; authoritative large/public performance stratum.
- **Pinned JSONTestSuite**: all raw conformance files checked for acceptance/rejection and cross-variant DOM parity. Undefined `i_` results are checked for implementation agreement, not an unsupported universal normative verdict. Only mutually accepted `y_` documents enter their own **tiny-file** performance stratum.
- **Synthetic escape probes**: all 206 exact-size probes are checked during preflight; the measured matrix selects 24 per phase from `newline`, `mixed`, `unicode` at targets 0/10/25/50%, 8/16KiB. Confirmation uses independently seeded bytes. Never pool them with public files.
- Paired, randomized run order; before/after original A2 anchors; DOM, Stage 1 and Stage 2 timed separately; repeat rows are not independent source documents.
- A normative JSONTestSuite or cross-variant correctness disagreement **fails the native run before performance collection**, with a partial diagnostic packet when possible.

### Release decision (per machine, confirmation only)

`public_gate106.json` contains every public-document ratio and an explicit local verdict:

- `VP_STABLE / A2_ORIGINAL` geometric mean >= **0.995x** across all 18 public documents;
- no original public document below **0.980x**;
- zero normative conformance failures or cross-variant correctness disagreements;
- also review the tiny JSONTestSuite documents and the A2-vs-official external baseline.

`VP_SIMPLE` and `VP_NL4` get their own equivalent public ratios, but **no global promotion** occurs based on synthetic wins. Both Cloud-V and EPCC must meet the native gate; compiler/version/flags, hash manifests, performance CSV and relevant evidence ZIPs must be archived before shipping. A per-machine pass **does not certify final release**.

## Timing

- Exploration: **1 hour**.
- Confirmation: **1 hour**.
- Max native measurement budget: **2 hours** (the worker reserves two minutes for finalization).
- EPCC Slurm reservation: **2 hours 45 minutes**, after login-node cross-compilation. Scheduler waiting, corpus preparation, and compilation add time.

## Install and run

1. Back up or commit the current MethodLab `studio/` and `tools/`; don't replace an active local source deployment.
2. Extract this DROP ROOT into `C:\mycode\Simdjson\VLA-MethodLab\` directly, accepting updates. It contains **no `engine/` files**.
3. Keep **VectorPath-RVV itself** as the separate optimized RC repo and do not point Tests 101–105 at it. For Test 106, use the existing **pinned MethodLab `engine/`** in your Studio repo setting (or the repository root with its `engine/`).
4. Start independent Studio Cloud-V and EPCC windows. In JSON Corpus, verify both the **Performance** and **Conformance** suites (SHA-256 sync is done automatically on Run).
5. Select **Tests → 106 → Refresh → Run**, once per server. Await Cloud-V detached PID and EPCC Slurm Job ID before closing Studio. The worker continues remotely afterward.
6. When finished, **Refresh → Download**. Send both `test106_results.zip` files for a final recommendation and freeze decision.

The new test is isolated in `test106-cloudv-runs/` and `test106-epcc-runs/`. Older Test 100–105 archives and UI entries are preserved. The Studio Refresh/Download completion fix remains in place.

### Deliverables

- `builds106.json`: compiler/flags/backend/binary hashes and exact candidate overlay source manifest.
- `status106.json`: phase, rows, native correctness status, and reasons for failure.
- `conformance106.csv/json`: all JSONTestSuite checks, with unexpected results never hidden.
- `results106.csv`, `summary106.json`, `public_gate106.json`, `REPORT_106.md`.
- Atomic ZIP diagnostic or completed result, verified through remote/local SHA-256 and ZIP CRC checks.

### Limitations

Local checks validated Python/Studio integration and compiled the reconstructed source in **fallback mode on x86_64**. This does not prove that native RVV compilation, Stage2 speedups, and Slurm submission will succeed on your machines. Actual native Test 106 results must establish that.

**Shipping policy:** preserve `VP_STABLE` with original Stage 2 by default until same-hardware native gates pass on **both** machines. Avoid another open-ended tuning cycle; archive evidence, freeze, then deliver.
