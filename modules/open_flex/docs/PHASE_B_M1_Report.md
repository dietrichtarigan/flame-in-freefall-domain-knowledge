# Phase B — Milestone M1 Report: Scientific Integrity

Date: 15 November 2026. Deliverable: `dist/open_flex_lab.html` (single file, 4.77 MB, works offline and from `file://`). The original prototype is untouched in `prototype/original/`.

## Objective
Remove or correct everything in the prototype that presented generated, invented or unsupported content as evidence; replace the presets with the NASA Table IX record.

## Files
| Path | Role |
|---|---|
| `app/src/body.html`, `app/src/styles.css`, `app/src/js/*.js` | Modular application source. `styles.css` and `js/30_scene_build.js` are verbatim carry-overs (checked byte-for-byte for the scene code). |
| `data/extracted/table_ix.csv`, `appendix_b_figures.csv` | Table IX (276 rows) and Appendix B figure index (276 figures), extracted from the TP. |
| `data/registry/{sources,claims,discrepancies,test_annotations}.json` | 16 sources, 34 atomic claims, 12 discrepancies, per-test annotations. |
| `data/MANIFEST.json` | SHA-256, origin and method for every data file. |
| `vendor/` + `VENDOR.json` | three.js r128, OrbitControls, Plotly 2.27.0 from npm, with hashes. |
| `tools/build_app.py`, `tools/canonical_json.py`, `tools/extract_*.py` | Build, independent hash recomputation, extraction. |
| `tests/browser/test_m1_browser.py`, `tests/unit/test_extractors.py` | Acceptance tests. |

## Scientific changes and justification
| Change | Basis |
|---|---|
| Synthetic replay, FSR plot, fit/RMSE on synthetic points: removed. Time-series panel now says "Time series unavailable" and points to the exact Appendix B figure and page, with the TP's own caption quoted. | OF-01, OF-15, OF-18 |
| 8 invented/incorrect presets → all 276 Table IX tests, values exactly as printed, with page locators. Literature cases (Dietrich figs, Williams "Test 0035") shown only as *candidate* mappings on Table IX tests. | OF-02, OF-03, OF-04 |
| Explore/OOD modes, the k̄ correlation, LOI shifts, extinction and cool-flame rules: removed; Explore shown disabled with the reason. | OF-14, OF-16, OF-21, OF-22 |
| Seeded forum posts and the Commons tab: removed. Badge policy kept as text. | OF-06 |
| Sobol chart and Monte Carlo interval: removed; a "Removed and why / condition to restore" table replaces them. | OF-07, OF-08 |
| "CV threshold" measurement readout: removed. Diagnostic view now draws the FOV with the printed D₀ to scale, no flame (no flame data). | OF-09 |
| SHA-256: Web Crypto only; reports "unavailable" otherwise. Hash covers the canonical JSON of the test record. UUIDs from a cryptographic RNG only. | OF-10 |
| Export renamed "JSON manifest (not an RO-Crate)"; carries the physical test record, raw + parsed values, computed composition sum, flags, discrepancies, claims. No model state exists to mislabel. | OF-11, OF-12 |
| Radial profile: dimensionless shapes, title "CONCEPTUAL ILLUSTRATION — NOT SOLVER OUTPUT"; mechanism selector removed; equations table marked not implemented, energy equation corrected to state the species-enthalpy-diffusion and Σhᵢω̇ᵢ terms. | OF-13, audit F2 |
| Procedure timeline re-sequenced to TP §2.3 (recording starts before deployment; purge step added; t = 0 at igniter ON). | OF-24, N9 |
| Needle contamination, early-shutter (001–009), approximate cells and source discrepancies shown per test. | N1, N8, N10 |
| Component information: every line carries claim IDs or "interpretive"; unsupported prototype statements moved to an "unverified" line. | OF-23 |
| Libraries vendored and inlined; explicit "3D library unavailable" / "plot library unavailable" messages. | OF-27 |
| No user-supplied text is inserted as HTML; registry text is escaped. | OF-26 |

## Tests performed (all run in this session)
`python3 -m pytest -q tests` → **14 passed** (headless Chrome 'google-chrome' via Playwright; every network request blocked).

| Test | Result |
|---|---|
| Page loads offline; THREE and Plotly present; no page or console errors; WebGL active (SwiftShader) | pass |
| 20 removed strings absent from the DOM (fake posts, "RO-Crate 1.3", "SOURCE-TRACEABLE REPLAY", "PHYSICS_SIMULATION", invented dates…); no D², FSR, Sobol, MC plot elements; no Commons tab | pass |
| FLEX–023 and FLEX–035 record table equals Table IX CSV, field by field | pass |
| All 276 tests in the selector; each one loads and renders its own record | pass |
| SHA-256("abc") = ba7816bf…; record hash is 64 hex | pass |
| With `crypto.subtle` removed: hash function returns null, header says "unavailable", no errors | pass |
| Export: `is_ro_crate: false`; values match CSV; composition sum computed; record hash recomputed independently in Python (`tools/canonical_json.py`) → MATCH | pass |
| Stage order follows TP §2.3 | pass |
| Component card tracks the current stage (bug found by screenshot review, fixed) | pass |
| Every CLM-/DSC- ID visible in the UI resolves in the registries | pass |
| Build without vendored libraries: explicit unavailable messages, no errors | pass |
| Extractors re-run from the PDF reproduce the committed CSVs exactly; key cells (FLEX–023, FLEX–114 "0", FLEX–227 "~6", FLEX–063 "0") | pass |
| Build run twice → identical bytes (deterministic); data manifest hashes recomputed independently | pass |

Visual review: screenshots of all four tabs in `docs/screens/`.

## Remaining limitations
- Table IX rows were checked by eye against the page image only for FLEX–023, –035 and page 24; the rest rely on the text layer (all 276 rows parsed with exactly 15 fields).
- Visual design is the old dark theme; accessibility is improved only partly (ARIA tab roles, reduced-motion autoplay off, escaped text). Full redesign is M5.
- Fiber/no-fiber is not shown (not in Table IX; parse of Tables III–VII planned for M2).
- JSON Schemas for the record types are not written yet (M2).
- The 3D model is still the original conceptual geometry; only two camera frusta; no click-picking (M5).

## Known unresolved issues
- Dietrich 2014 figure mappings, LOI values and drift speeds remain unverified (full paper not available).
- The per-test text data files the TP refers to were not supplied; replay waits for digitization (M3) or those files.
