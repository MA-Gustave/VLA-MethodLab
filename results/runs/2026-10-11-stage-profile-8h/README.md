# 2026-10-11 · Eight-hour split-stage RVV-VLA experiment

[Read the public report](../../../docs/results/2026-10-11-stage-profile-8h.md)

This directory holds a publication-safe, source-derived evidence set. `observations.csv`, `ranking.csv` and `failures.csv` are copies of the uploaded run records. `events.jsonl`, `by-family.csv` and `metadata.public.json` were created from those records and are explicitly **derived**, not original terminal logs. Individual server paths, account names and hostnames were removed from metadata.

The 8h campaign stopped normally when its time budget expired. The VLA source was **dirty**, and the source snapshot was **not** included with these records. See the report for the reproducibility boundary.

Run `python verify.py` in this directory to hash-check the provided evidence and recompute the ranking from measurement rows.
