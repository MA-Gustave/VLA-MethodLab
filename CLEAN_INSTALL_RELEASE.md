# Clean installation and final release-candidate layout

**Created 2026-10-18.** This ZIP is **a complete MethodLab repository snapshot**, not an overlay or replacement VectorPath engine.

## Wipe/reinstall — important

- On Windows, **rename or back up** the existing `VLA-MethodLab` directory first. Do not erase your only copy of `.git`, `.env`, SSH configuration, `.venv`, locally downloaded corpora or private remote logs.
- `wholeRepo.zip` was the sole authoritative input for all code and data in this package. The rebuilt archive preserves `engine/` and `studio/` sources; no further 101–107 overlays are needed.
- Extract this archive into an **empty** `VLA-MethodLab` folder. All paths are relative to the root; no extra top-level folder is present.
- If you want a working Git checkout with branches/history, first `git clone` your repository in an empty destination and then extract on top; or restore your saved `.git`. A ZIP alone has **no Git history**.
- `ZmartZnap.pyw` was **not changed**; `SNAPSHOT_INDEX.txt` was regenerated to reflect the new file layout. It cannot restore private snapshot directories absent from the uploaded ZIP.
- The cleaned package excludes obsolete direct-launch scripts and one-off overlay instructions. They are available in a **separate optional LEGACY backup ZIP**, not required to run MethodLab.

## Verification

From a terminal in the installation root:

```powershell
py -3 tools/refresh_github_manifests.py
```

The command above only previews inventory; the shipped `SHA256SUMS.txt` lists individual SHA-256 checksums of every included tree file except itself, `OVERLAY_SHA256SUMS.txt`, and `SNAPSHOT_INDEX.txt`. Confirm hashes using:

```powershell
py -3 tools/verify_release_tree.py
```

The verifier is read-only and does not access the network. Rebuild checksum manifests *only after an intentional source change* with:

```powershell
py -3 tools/refresh_github_manifests.py --write
```

## Results and native provenance

- `results/runs/`: original prior research results preserved byte-for-byte; paths not changed.
- `results/archive/test100/`: Test100 historical comparison CSV.
- `results/releases/test106/`: official final Test106 report plus per-document performance CSV.
- `results/releases/test107/`: formal local release audit report (not a new machine run).
- `logs-reports/raw-native/test101/` through `test106/`: original machine-result ZIPs, moved intact and not rewritten.
- `logs-reports/reports/`: historical Markdown analyses classified only, no second-pass standardization.
- The redundant `results.zip` / `logs-reports.zip` root bundles and exact duplicate extracted Test106 Cloud-V directory were removed after byte-level checks against their surviving originals.

## Engine and delivery status

- Historical `engine/` C++ sources remain untouched; compare them to the candidate VectorPath A2 in `release_candidates/`.
- The default recommended shipping variant is A2 / 16KiB / packed OFF, original Stage 2; `SIMPLE_RUN` and `NL4` were deliberately **not** globally promoted.
- The two native Test106 measurements are qualifying performance evidence, not proof the GitHub Actions fuzz/Valgrind workflow succeeded. The #74 CI failure remains a release blocker until its failing step is confirmed/resolved or explicitly acknowledged in release notes.

## Scope of cleanup

No arbitrary data files were pruned from the historical `results/runs` datasets and no native benchmark ZIP has been modified. The cleanup inventories all relocated and excluded files in `docs/release/REPOSITORY_CLEANUP_DECISIONS.csv`; document locations and launcher paths are explained in `README.md`.
