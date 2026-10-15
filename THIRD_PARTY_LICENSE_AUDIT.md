# Third-party audit — VLA-MethodLab (preliminary)

This repository currently **includes `engine/`**, whose files are a copy of the simdjson-derived VectorPath-RVV engine. The embedded source has existing Apache-2.0, MIT and additional file-level third-party rights; nothing in MethodLab's own rights notice is intended to supersede them.

Preserve verbatim `engine/LICENSE`, `engine/LICENSE-MIT`, the files in `THIRD_PARTY_LICENSES/`, and relevant `licenses/historical-simdjson/` licences. See VectorPath's `THIRD_PARTY_LICENSE_AUDIT.md` for sampled Boost, fast_float, Dragonbox and PyTorch-origin licensing leads. The actual notices in each bundled source file remain authoritative for those third-party portions.

Do not describe the entire lab or embedded engine as exclusively owned. Audit independently the Python orchestration/UI packages, experiment workers, assets, templates and datasets for externally derived material. An exact source-diff, contributor chain of title and first-release rights record are necessary before labeling a mixed file or part of a file proprietary.
