# Add your own experiments

**CLI worker:** create `experiments/custom/my_experiment.py` accepting
`--source` (remote extracted C++ root) and `--workdir` (a unique remote directory),
plus any declared profile flags. Write files only beneath `--workdir`. Emit
`status.json`, `map.csv`, `metadata.json`, etc. For standard SHA256 `sync` support,
publish `snapshot.zip` and `snapshot.sha256` with `MANIFEST.json` (format shown
in `example_probe.py`); otherwise the detached run can be inspected by SSH.

Create `experiments/custom/my_experiment.json` with a top-level `worker` basename,
`args` array of exact values and `max_minutes` (1-480). Example: `example.json`.
Then `python tools/rvvlab.py run custom:example` (the CLI explicitly prompts
before executing arbitrary custom code). Worker files are SHA256 verified remotely.

**Studio plugin:** put a trusted `99_custom.py` exposing
`execute(ctx, params)` in `studio/test_scripts/`, with `99_custom.test.json`
(`schema=1`, `id`, `script`, `title`, `enabled=true`, `params={}`). The `Refresh`
action validates the manifest without importing it. The module executes
**only after explicit Run selected** and receives the existing SSH connection.

Review and trust code before launch. No auto-install, no sudo, and never share
credentials in a test or input corpus. Keep results separate by run id.
