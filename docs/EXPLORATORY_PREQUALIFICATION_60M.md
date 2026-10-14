# Adaptive Prequalification v2 — one-hour exploratory protocol (Test 87)

**Status: designed and locally corpus-tested; no native RISC-V campaign has run.**

The intent is to discover counterexamples and follow-up hypotheses about the
low-overhead size gate and 512-byte qualification, **not** to optimize the
qualifier to this dataset or establish statistically robust speedups.

## Engine configurations

- **Official:** pinned simdjson 5.0.3 `rvv_vls256`, commit `bf89ddd00ef5fcb6a7f20611ea8853d258b67249`.
- **A0:** E14 original classifier (up to 4096 bytes).
- **A1:** bypass classifier for inputs smaller than 4096 bytes.
- **A2:** A1 + up-to-512-byte quick qualification on larger inputs.

These are **separately compiled GCC binaries**, not one binary dynamically
switching implementations. A3 adaptive per-block refinement is not implemented.

## Synthetic, precommitted workload design

**174 JSON documents**, deterministically generated from seed `20261011`:

| Segment | Cases | Sizes / diversity |
|---|---:|---|
| 11 base kinds × 9 sizes | 99 | ASCII, numbers, dense structural, escaped, Unicode escape, genuine UTF-8, nested depth, whitespace, long strings, many keys, mixed; nominal 512 B–1 MiB |
| 4 kinds × 4 sizes × 3 placements | 48 | Escape / UTF-8 / dense / numeric bursts at document head, middle, or tail; 8 KiB–1 MiB |
| 3 kinds × 7 exact size gates | 21 | 128, 511, 512, 4095, 4096, 4097, 8192 bytes; ASCII, escapes, raw UTF-8 |
| 6 large cases | 6 | 4 MiB, representative high-stress kinds |

All files are syntactically checked using Python's strict `json.loads` and
hashed independently before measurement. Actual bytes (not nominal target)
are recorded in `corpus_manifest.json`.

**Diagnostic sampling:** independently record 512-byte head/middle/tail
windows and a 4-KiB prefix. Count rough byte-density proxies (escapes, quotes,
structural bytes, non-ASCII bytes and numerals) to identify situations where a
cheap prefix may mischaracterize a document. These are **offline data labels**,
not observed parser classification decisions or a separate hot-path prepass.
Character counts do not distinguish syntax from characters inside strings.

## Measurement controls

- Total cap **60 minutes**, including preflight, official-reference checkout,
  four native GCC builds, correctness gate and samples. The campaign can stop
  with a partial (but SHA256-synchronized) dataset when the cap is reached.
- Native Linux riscv64, VLEN256, no emulation, pinned CPU for benchmark;
  orchestration on a different CPU when available. No governor changes.
- Direct internal `stage1` and `stage2` wall times are measured separately;
  public DOM parsing is measured independently. Each throughput observation is
  a **median of 3** repetitions; not an estimated instruction count.
- The four variants are measured with the **same JSON, trial and iteration
  count**, and their order rotates/reverses; document order changes every trial
  using a precommitted PRNG seed.
- Initial pass prioritizes broad scenario coverage. Later passes replicate
  **without learning from measured performance**; no winner is auto-selected.
- The run continues on the RISC-V server after the local Studio window closes.
  Checkpoint, STOP, sync, disk safety and SHA256 snapshot handling are retained.
- Source snapshots omit credentials; release does not include a `.env`.

## Outputs and interpretation

`map.csv`, `ranking.csv`, `trend_candidates.csv`, `TRENDS.md`,
`prequal_pairwise.csv`, `corpus_manifest.json`, `metadata.json`, `checkpoint.json`, `status.json`,
`failures.csv`, `hypotheses.md`, `snapshot.zip`, `snapshot.sha256`.

The `prequal_pairwise.csv` file directly compares **A1/A0, A2/A0 and A2/A1**
on the same document/trial/iterations across DOM, Stage 1 and Stage 2.
`TRENDS.md` provides unvalidated, post-hoc outlier hypotheses.

Paired geometric speedups must be considered **exploratory**. Tiny JSON timings
may be dominated by timer/function overhead. Multiple related input samples and
trials are correlated. “Environment variability” here means workload layout,
size and cache regimes **on one hardware host**; it does not simulate another
RISC-V board, compiler, operating system or governor. No claims of statistical
significance or hardware generality are warranted.

**Follow-up:** identify top surprises or regressions from `TRENDS.md`, freeze
the hypothesis and threshold in a *separate*, longer confirmatory campaign with
held-out real JSON corpora and fresh baselines.

## Launch

From Lab root:

```powershell
python tools/rvvlab.py setup                 # once, credentials remain local
python tools/rvvlab.py preflight
python tools/rvvlab.py run prequal-60m --wait
python tools/rvvlab.py status
python tools/rvvlab.py sync night-YYYYMMDDTHHMMSSZ-abcdef
```

Or: `START_STUDIO.ps1` → **RVV Tests** → select **Test 87** → launch.
No test is started by merely installing Lab. Do not publish SSH host paths.
