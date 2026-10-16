# RVV-VLA MethodLab — English UI + JSONTestSuite fixture fix

## Install (DROP ROOT)

1. Close both Studio instances (Cloud-V and EPCC). Remote detached jobs continue running.
2. Back up the `studio/` and `tools/corpus_jsontestsuite.py` files if you have uncommitted local edits.
3. Extract this ZIP **directly into** `C:\mycode\Simdjson\VLA-MethodLab\`, keeping the included `studio/` and `tools/` folder structure. Confirm file replacement.
4. Reopen Lab Studio. The main UI, JSON Corpus panel, its diagnostics/log window and workflow statuses now use English.
5. Open **JSON Corpus → Conformance · JSONTestSuite → Prepare / Verify JSON**.
6. If the preparation succeeds, choose **Sync to server**, then **Check server**, once for Cloud-V and again for EPCC as needed.

## Verified root cause

The earlier 48 MiB download cap was addressed by the preceding download-streaming patch (retained here). Your latest log proves the archive now reaches the fixture scanner, which rejected the upstream file `test_parsing/n_structure_trailing_#.json` because `#` was absent from the allowed basename characters. This release permits `#` in test fixture basenames. Directory traversal, backslashes, colons, non-fixture paths, unexpected classes, ZIP size caps, filename collision checks, per-file SHA-256 and byte-exact invalid JSON fixtures remain guarded.

The source file's presence at the pinned commit `1ef36fa01286573e846ac449e8683f8833c5b26a` was verified via the upstream GitHub repository. Its contents are `{"a":"b"}#{}` (the suffix deliberately makes the input invalid).

## English UI

* Primary **Tests** and **JSON Corpus** workflow buttons, labels, status banners and detailed preparation logs translated to English.
* Main Studio navigation, Cloud-V/EPCC control labels and advanced-status wording translated.
* **View log / Copy** shows the complete log; the page only shows the short result.
* Stable technical identifiers and API/JSON status values remain unchanged (`conformance`, `verified`, `completed`, `running` etc.).
* The manifest-provided names of some older experiments may remain as authored, to preserve their original protocol titles.

## Validation and limitations

* 66 local offline / GUI regression tests passed under a virtual desktop.
* Added a regression with the real upstream `#` fixture name and rejection tests for traversal/backslashes/colon.
* Verified UI startup and captured an English-interface preview.
* The complete upstream archive was **not** downloaded in this sandbox (no DNS access). Real download and sync must still be confirmed on your Windows PC and target servers.
* This ZIP does not include third-party JSON files, secrets, or changes to benchmark engines/runs.

## Troubleshooting

Use **JSON Corpus → View log / Copy → Copy all**. The persistent local log is:

`.cache/corpus-library/preparation-conformance.log`

If another error appears, paste the **last traceback** rather than rerunning repeatedly. The corpus manager writes to a temporary ZIP and promotes the prepared archive only after its validation succeeds.
