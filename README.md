> **RIGHTS NOTICE — INDEPENDENT LAB, MIXED ORIGIN, PROSPECTIVE UPSTREAM EXCLUSION**  
> This repository **includes `engine/`**, a simdjson-derived engine under its applicable existing upstream and third-party licences. Neither the lab nor the engine is made wholly proprietary by this notice. For future or otherwise verified, independently controlled and individually registered original additions, **no licence is granted for incorporation into official simdjson without separate signed authorization**. Previous Apache/MIT and other grants cannot be revoked. See [LICENSE](LICENSE), [scope](LICENSE-SCOPE.md), [register](PROVENANCE-ADDITIONS.md), [upstream exclusion](UPSTREAM-EXCLUSION.md).

# VLA-MethodLab — Studio, orchestration et expériences RVV

Dépôt : https://github.com/MA-Gustave/VLA-MethodLab

**Installation directe :** décompresser le ZIP **VLA-MethodLab_DROP_ROOT_OVERWRITE.zip**
à la racine de `VLA-MethodLab`. Ne pas créer un dossier supplémentaire.
Le fichier `LICENSE` **est inclus** dans cette distribution ; il présente les droits mixtes applicables. Les licences des composants hérités conservent leur portée et ne sont pas remplacées.

Ce dossier est **autonome** et contient une **copie compatible** du moteur
sous `engine/`, pour que Lab Studio fonctionne dès l'extraction.
Le dépôt de référence du moteur est
[VectorPath-RVV](https://github.com/MA-Gustave/VectorPath-RVV).

Pour ouvrir les deux fenêtres sous Windows : double-cliquer
`LANCER_STUDIO_CLOUDV.pyw` et `LANCER_STUDIO_EPCC.pyw`. Aucun sous-module,
aucune commande Git et aucun lien symbolique ne sont nécessaires pour utiliser
le logiciel. Les fichiers `.env` secrets restent hors dépôt.

**Important :** les deux dépôts contiennent initialement une copie du moteur.
Lors d'une modification ultérieure du moteur, reporter les mêmes sources dans
`engine/` ici, pour conserver des essais reproductibles. Les ZIP de cette
livraison sont alignés sur le même code moteur.

Les sources dérivées de simdjson conservent leurs notices Apache-2.0 / MIT dans
`engine/LICENSE`, `engine/LICENSE-MIT` et `THIRD_PARTY_LICENSES/`.
La licence propre à chaque nouveau dépôt est distincte des licences tierces.

---

> **Test 93 — Stage1/overhead isolation (3h max):** see [README-TEST93.md](README-TEST93.md) and the [English Test 92 performance report](docs/results/2026-10-13-test92-performance-report.md). Test 93 is manual-only and does not replace Tests 91/92.

**Nouveau : [Test 92 — exploration progressive 8h, Stage 1 et coût expérimental](README-TEST92.md).** Le Test 91 reste disponible.

# RVV-VLA Lab v6.2 — Test 93 Stage1 overhead diagnostics (experimental)

**New: [Test 91 — installation and protocol](README-TEST91.md).** Full integrated repository, 242 research configurations, regional adaptation, 2,304 lazy JSON designs through 64 MiB. Start the 1h pilot in Studio, then the 8h exploration. New native RVV validation is pending; no new speedup is claimed.

**Independent RISC-V RVV-VLA research fork of simdjson v5.0.3.** A native C++ parser,
15 specialized engine plans, Adaptive Dispatch v2 (A0/A1/A2), an SSH CLI orchestrator,
custom-worker framework, benchmark evidence, and reproducible research documentation.

**One self-contained Studio installation:** Lab includes a matching engine
snapshot under `engine/`, the CLI, GUI, all Test Runner profiles, workers,
reports, evidence and documentation. VectorPath-RVV is maintained as a separate
engine repository; these installation ZIPs deliberately avoid Git submodules.
The former standalone RVV-VLA-Studio repository is **obsolete**; do not use or maintain
it. Launch the integrated GUI with `START_STUDIO.ps1`. Neither Lab distribution
nor Studio contains a preconfigured SSH account or private `.env`.

> Not an official simdjson release. Optimizations are tested on RISC-V RVV VLEN=256.
> An upstream Git SHA does not reconstruct the *dirty* historical source checkout.

## Research results

| Native GCC study | Observations | E14 DOM throughput vs official VLS256 |
|---|---:|---:|
| [3 h, 17 engine configurations](results/runs/2026-10-10-engine-library-3h/analysis.md) | 2,469 | **1.473×** |
| [8 h, split Stage1/Stage2/DOM](docs/results/2026-10-11-stage-profile-8h.md) | 6,887 | **1.502×** |

The 8-hour E14 Stage 1 result was **1.601×**, Stage 2 **1.298×** independently;
these are paired geometric means, not claims of universal speedup. Verify using:

```bash
python tools/check_publication.py
python results/runs/2026-10-11-stage-profile-8h/verify.py
```

## Quick start — Windows PowerShell 7

Extract into `C:\mycode\Simdjson\RVV-VLA-Lab` or any other writable folder:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass -File .\START_HERE.ps1
```

The launcher creates an isolated Python environment and asks before installing
Paramiko. Configuration is interactive, **no preset server or auto-login**.
The target must run Linux `riscv64` with RVV, native GCC/G++ and at least 200 MiB free space (graceful stop below this floor).
Verify its SSH host-key fingerprint via a trusted out-of-band channel first.

```bash
python tools/rvvlab.py setup
python tools/rvvlab.py preflight
python tools/rvvlab.py run smoke --wait
python tools/rvvlab.py run stages-60m
python tools/rvvlab.py run matrix-3h
python tools/rvvlab.py run stages-8h
python tools/rvvlab.py run adaptive-smoke --wait
python tools/rvvlab.py run adaptive-30m
python tools/rvvlab.py run prequal-60m    # Exploratory 1h, manually started
python tools/rvvlab.py run custom:example  # Explicit confirmation required
python tools/rvvlab.py status
python tools/rvvlab.py sync night-YYYYMMDDTHHMMSSZ-abcdef
```

All campaigns are manually started. The control plane preserves detached remote
workers, verifies uploaded source/worker SHA256 and supports graceful stop/sync.
Source snapshots automatically exclude `.env`, `.git`, keys, build caches and logs.
The remote server is yours; we don't provision it or install its toolchain.

## Complete repository contents

- [`engine/`](engine/): full modified simdjson source, Stage 1/Stage 2, RVV.
- [`experiments/patterns.json`](experiments/patterns.json): **15 E00–E14** engine hypotheses.
- [`experiments/workers/`](experiments/workers/): **seven** complete native remote workers (81–87).
- [`experiments/profiles/`](experiments/profiles/): manifests and SHA256 pins mirrored with Studio.
- [`experiments/custom/`](experiments/custom/): user-defined Python workers.
- [`orchestrator/`](orchestrator/): SSH runtime; local `.env` created by `setup`, shared with integrated Studio.
- [`studio/`](studio/): complete integrated Tkinter GUI, Test Runner 81–87, SSH console and reports.
- [`tools/`](tools/): CLI, artifact verification, Adaptive v2 C++ portable test runner.
- [`results/runs/`](results/runs/): normalized 3-hour and 8-hour evidence and SHA256 verifier.
- [`docs/`](docs/): GitHub Pages dashboard, methodology, Adaptive Dispatch v2 documentation.
- [`wiki/`](wiki/): GitHub Wiki manuscripts for separate Wiki git repository.

## Adaptive Dispatch v2

A0 = original E14, A1 = no classifier for inputs below 4 KiB, A2 = A1 plus
512-byte bounded sampling for larger documents. Three variants are **compile-time
A/B test profiles**, not a runtime switch between separately compiled binaries.
Experimental fused regional refinement is implemented for Test 91 only; its native validation is pending. A2 has historical Test 89/90 measurements; see
[`docs/ADAPTIVE_DISPATCH_V2.md`](docs/ADAPTIVE_DISPATCH_V2.md).

```bash
python tools/test_adaptive_v2.py
python tools/verify_adaptive_v2.py
python tools/verify_release.py
```

## Integrated desktop Studio (no second repository)

Run `START_STUDIO.ps1` from Lab root. The GUI automatically selects
`engine/`, shares the CLI SSH configuration at `orchestrator/.env`, and
provides console, Test Runner, reports, storage and campaign synchronization.
`studio/test_scripts/` contains all seven manually invoked campaigns (81–87).
Historical Studio code and the standalone Studio Git repository are obsolete.

### One-hour exploratory prequalification campaign (87)

`prequal-60m` compares **A0/A1/A2 and official VLS256** on deterministic,
varied JSON across 128 B–4 MiB: boundary sizes, ASCII, numbers, escaped Unicode,
real UTF-8, structurals, deep nesting, sparse whitespace, heterogeneous objects,
and front-/back-loaded mixed data. It uses bounded samples at the beginning,
middle and end for **post-hoc diagnostics only**, not training on the test set.
It is a 60-minute **exploration including compilation**, not confirmatory evidence.
Remote native hardware and a clean source snapshot are required; no run has been
performed when you download this release.

`python tools/rvvlab.py run prequal-60m --wait` or GUI Test Runner → 87.
See [protocol](docs/EXPLORATORY_PREQUALIFICATION_60M.md).

## Credit and reproducibility

[Benchmark methodology](docs/METHODOLOGY.md) · [Research roadmap](wiki/Research-Roadmap.md) ·
[Pattern library](experiments/PATTERN_LIBRARY.md) · [Acknowledgements](ACKNOWLEDGEMENTS.md).
The original server was generously made available **free of charge by Cloud-V**.
Upstream simdjson copyrights and licenses are retained in `engine/`.

## Test 98 public benchmark corpus

See [Test98 EPCC/Cloud-V quickstart](README-TEST98-QUICKSTART.md) for immutable `simdjson-data` corpus acquisition, SHA256-verified SSH deployment and reproducible official-v5-vs-RVV benchmarks. No external corpus files are committed.
