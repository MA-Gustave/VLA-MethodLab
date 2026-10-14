# Two repositories, two roles

- **VLA MethodLab** is the experimental method, orchestration, Studio, benchmarks and historical evidence. It contains no tracked C++ engine at `engine/`.
- **VectorPath RVV** is the separately maintained experimental C++ JSON engine, with its own upstream licences and modification history.

The two repositories are siblings. Run `python tools/attach_vectorpath.py --source ../vectorpath-rvv` once after checkout. This copies the engine into an ignored local folder needed by unchanged experiment workers and GUI scripts. Git history is independent. Do not commit or publish the attached engine as part of MethodLab.

Research reports may refer to the historic integrated layout and are intentionally not rewritten. Archived historical NOTICE/README files appear in `docs/historical-project-notices/` and are kept for context, **not** as overrides of present licensing documents.
