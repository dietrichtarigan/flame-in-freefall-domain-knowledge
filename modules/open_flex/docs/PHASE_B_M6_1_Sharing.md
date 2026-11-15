# Phase B M6.1: sharing a simulation run so others can check it

Status: implemented and tested (see the test files at the end). Applies to the D²-law educational baseline only.

## What you can do

1. In the app, open Physics & Results, choose a test, switch to **Explore with a model**, and change inputs.
2. Open **Share this run, or check someone else's**. Save the run file (`OpenFLEX_run_SIM-….json`) or copy the post text.
3. Post it in a forum. The app can open the GitHub new-discussion page when a repository is configured
   (`data/registry/share_config.json`, field `github_repo`, currently `null`, so the button is hidden).
4. A reader pastes the run JSON (or the whole post) or loads the file in the same panel and presses **Check**.
   The same check runs without a browser: `python3 -m openflex check-run run.json`.
5. After a successful check, **Load these inputs into Explore** restores the form so the reader can change one thing and compare.

## What "reproduced" means, and does not mean

| Word | Meaning here | Does not mean |
|---|---|---|
| **Reproduced** | The documented model, run again from the file's inputs, gives the file's numbers (relative tolerance 1e-6) and its run id. | That the model agrees with FLEX, or that the inputs are sensible. |
| **Compared** | The file shows the model's K next to the printed K of the seeding test (Table IX) when the inputs are those of the test (D₀ may differ). | Validation. No metric or acceptance criterion has been agreed. |
| **Reviewed** | People discuss it in the forum. | Anything automatic. |

A shared run is a `NUMERICAL_SIMULATION` with a `SIM-…` id. It is never a FLEX test and never called validated.

## Check results

| Status | Meaning |
|---|---|
| REPRODUCED | Every check passed (F1–F9). |
| NOT_REPRODUCED | Same model, but a result, id, modified-input list, comparison or hash differs. The file was edited or made by faulty software. |
| CANNOT_CHECK | Different model version, property table or implementation (or SHA-256 is unavailable in the browser context). Results may legitimately differ. |
| INVALID | Not a usable file: wrong format, over 200 kB, unknown fields, inputs out of range, a non-SIM id, or an unknown seeding test. |

Checks: F1 format and fields; F2 labels and SIM id; F3 inputs in range and seeding test exists; F4 same model, table and
implementation; F9 content hash; F5 modified-input list; F6 run id; F7 outputs; F8 printed-value comparison.

## What is in a run file

Inputs, outputs (8 significant figures), model name and version, property-table and implementation hashes, the seeding test id,
the list of modified inputs, the printed-value comparison, the app build id, and a content hash. **No name, e-mail, path,
time or date.** Format: `schemas/shared_run.schema.json`. Reference code: `openflex/share.py` (Python) and
`app/src/js/62_share.js` (browser). The tests check each against files made by the other.

## Limits to be aware of

- The content hash detects accidental edits only. Anyone can edit a file and recompute it. The real check is re-running the model (F6, F7).
- A reproduction confirms the file against this code. If the code has a mistake, both sides share it; that is what the code
  verification (24 checks) and, later, validation against data are for.
- The GitHub new-discussion page cannot, to our knowledge, be pre-filled from a link (GitHub community discussion #3799 is a
  feature request), so the app copies the text and you paste it. The app makes no network request; the link opens only on click.
- The pasted post is parsed as JSON between its outermost braces. Everything read from a file is size-limited, validated and shown as text.
- Numbers outside 1e-6 to 1e-4 or above 1e16 may format differently in JavaScript and Python. Outputs are rounded to
  8 significant figures and no such inputs are accepted by the range checks, so this does not arise in practice.

## Open decisions (yours)

- The GitHub repository (`owner/repo`) and the Discussions category name (default "Shared runs").
- The repository licence and the publisher name (both still open in the RO-Crate).
- The validation metric and acceptance criteria. Until they exist the forum can reproduce and discuss, not validate.

## Tests

`tests/unit/test_m6_1_share.py` (31) and `tests/browser/test_m6_1_share_browser.py` (24), including cross-implementation round trips,
tamper cases (17 in Python, 11 in the browser), hostile strings, oversize files, privacy, the GitHub link rules and axe in both themes.
