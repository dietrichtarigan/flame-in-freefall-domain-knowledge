# Open FLEX — Phase B, Step 1: Independent Review of the Phase A Audit and Revision Plan

Prepared 15 November 2026. Status: **review and plan only — the prototype has not been modified.**
Repository checkpoint: `f90c20f` (immutable, read-only copies of all six inputs with SHA-256 manifest in `SOURCE_CHECKSUMS.sha256`).

Evidence words used below:

| Word | Meaning |
|---|---|
| **VERIFIED** | Checked by me directly against the HTML source, the NASA/TP-2015-216046 PDF (text layer and, where noted, rendered page images), or by running code. |
| **VERIFIED (abstract only)** | Checked against the published abstract of Dietrich et al. 2014 via bibliographic index records; the full paper was not reachable from this environment. |
| **UNVERIFIED** | Rests on a source I could not open. |
| **AUDIT ERROR** | The Phase A audit states something the source does not support. |
| **NEW** | Not in the Phase A audit; found in this review. |

---

## 1. Bottom line

1. **The Phase A audit is substantially correct.** I re-checked all 8 Critical and 11 High findings against the code and the NASA report. All 19 hold. Its numerical checks (Table IX values, the correlation errors in OF-14, the Sobol sum of 1.14, the pixel-pitch arithmetic in E0, the D²-law derivation in F3) reproduce exactly.
2. **The audit contains six errors or omissions**, none of which reverses a finding (Section 3). Two of them understate what the prototype got right (the 0–9 atm chamber rating and the "~40 s" recording time are both in the TP). One overstates what the TP contains (Table IX does not print H₂O or fuel-vapour fractions).
3. **I found eleven additional issues the audit missed** (Section 4). The most consequential for the platform design are:
   - **Needle contamination (TP §5.2).** Every test in the TP used fuel needles whose conformal coating dissolved/flaked into the fuel. The TP's own conclusions qualify which observables are affected (disruptive extinction of methanol "probably due to the contaminant"; burning rates and radiative extinction diameters minimally affected). Neither the prototype nor the audit mentions this. It must be a first-class caveat on every test record.
   - **Table IX is not 284 tests.** The abstract says "first 284 tests", but Table IX ends at FLEX–280 and has 276 rows; FLEX–156, –205, –213 and –228 are absent (confirmed on the rendered page image for 156; Table VIII lists 156 as conducted).
   - **Nominal vs. actual composition.** Table III gives FLEX–019…024 as 0.400/0.600 O₂/N₂; Table IX (composition reconstructed from fill, recirculation and combustion records) gives 0.34/0.66. The highest oxygen fraction anywhere in Table IX is 0.34, so the prototype's "0.10–0.40" envelope rests on nominal, not actual, values.
   - **The TP itself quantifies colour/LLUV flame size**: colour-camera flame diameters are "typically about three-fourths" of LLUV ones (TP §4.2/§5.1, p. 16). The prototype hard-codes 0.91–0.92. The audit called the coefficient unsourced (true) but missed that the source contradicts it.
   - **Appendix B plots are raster images with colour-coded markers** (e.g. Fig. 27 is a 1268 × 834 JPEG of red/blue circles on white). This makes genuine, documented digitization practical, which the audit did not establish.
4. **The core judgement stands: the prototype contains no experimental time series.** I would refine the audit's phrase "no experimental data at all": the prototype does contain correct reported scalars (pressures, the three NASA measurement estimates, the radiometer limitation, hardware facts), but every plotted curve is generated.
5. **Empirical confirmation of OF-27.** I ran the original page in headless Chrome with no network access to the CDNs. `THREE` and `Plotly` were undefined, no plot rendered, and no error was shown to the user. The 2-D fallback schematic did render. The (FNV-free) SHA-256 path ran because Chrome treats `file://` as a secure context.

---

## 2. Verification of the Critical and High findings

| ID | Sev. | Audit claim (short) | My check | Verdict |
|---|---|---|---|---|
| OF-01 | Crit | Replay synthesizes D², flame, FSR | `computePhysicsTrajectory` (L1538–1745) is the only data source; Replay only swaps in `kBarReported` (L1549–1550). No file load anywhere. | **VERIFIED** |
| OF-02 | Crit | FLEX-023 preset wrong vs Table IX | Table IX p. 20: 196F002, 10/24/09 18:29:53 GMT, heptane, 541.8 mmHg (0.7129 atm), 0.34/0.66, D₀ 3.01, ext "–", K 0.73, t_b 13.1 s, **Disruption**. Preset: K 0.68 ("illustrative"), duration 16, "Radiative / Soot-Shell". Also: preset sets **no drift** although Fig. 27 caption (p. 51) says the droplet drifted partly out of the FOV (NEW detail). | **VERIFIED** |
| OF-03 | Crit | FLEX-0035 preset invented | Table IX p. 21: 181F001, 11/27/09 13:01:24, 768.1 mmHg, 0.21/0.79, D₀ 3.85, ext 3.34, K 0.43, 8.9 s, Extinction. Table V p. 13: D₀ 3.91. Fig. 39 caption p. 63: post-extinction vaporization rate "only slightly lower" than K, then plateau with vapour cloud, "indicative of cool flame burning". Preset date 2009-07-15, D₀ 3.80, K 0.56, 24 s, 0.55 × K cool-flame rate: none supported. | **VERIFIED** |
| OF-04 | Crit | Dietrich-figure presets carry invented dates | No source gives these dates. Candidate Table IX matches (my own check, conditions + K): Fig. 3 ↔ FLEX–062 (1 atm, 0.18 O₂, D₀ 3.43, K 0.39); Fig. 4 ↔ FLEX–198 (D₀ 3.04, K 0.49) and FLEX–199 (D₀ 2.12, K 0.53), both 8/18/11. NEW: methanol Fig. 6 candidates are FLEX–204 (N₂, **1.0 atm**, D₀ 2.75, K 0.52), FLEX–110 (CO₂ 0.30, **0.71 atm**, D₀ 2.83, K 0.45), FLEX–263 (He 0.30, **0.70 atm**, D₀ 2.67, K 0.70). If those mappings hold, the prototype's 1.00 atm for the CO₂ and He cases is wrong. All mappings remain **candidates** until the Dietrich paper is read. | **VERIFIED** (mapping unconfirmed) |
| OF-05 | Crit | One badge conflates provenance and computation; generated output called "PHYSICS_SIMULATION" | L2445–2456, L2679–2700. | **VERIFIED** |
| OF-06 | Crit | Fabricated posts, incl. named NASA author | L1471–1486: "D. Dietrich (Archival Reference Note)", role NASA_REPORTED; "Independent Student Replicator (FTMD-ITB)", k̄ = 0.381 ± 0.019, dated 2026-11-15 (today). Nothing persists. | **VERIFIED** |
| OF-07 | Crit | Hard-coded Sobol bars summing to 1.14 | L2486–2488: [0.04, 0.11, 0.14, 0.27, 0.58] → Σ = 1.14. First-order indices of independent inputs cannot exceed 1 in sum. g-jitter listed though K does not depend on it. | **VERIFIED** |
| OF-08 | Crit | MC treats ±50 µm as 2σ; other σ unsourced | L2416: σ(D₀) = 0.025 mm with comment "±50 μm measurement spread". σ(X_O₂)=0.003, σ(P)=0.008 unsourced. Response function = the unsourced correlation. | **VERIFIED** |
| OF-09 | High | "CV threshold" rescales a synthetic radius, prints NASA ±50 µm | L2171, L2192–2194. TP §3.1.1–3.1.2: threshold set per test from ground tests with precision spheres; TP adds that within reasonable limits it "had little impact on the droplet size". | **VERIFIED** |
| OF-10 | High | SHA-256 falls back to 32-bit FNV ×8 | L1503–1508. Hash covers 12 UI fields only. | **VERIFIED** |
| OF-11 | High | Export attaches NASA ID to modified runs | L2760 `legacy_nasa_test_id: state.presetKey`, regardless of mode/edits; `sum_check: 1.0` literal. | **VERIFIED** |
| OF-12 | High | "RO-Crate 1.3" label, 1.1 context, not a crate | L550 / L2747. NEW context: RO-Crate 1.3 *does* exist (announced 23 Jun 2026; 1.2 is the long-term stable release, Jun 2025). So the label is not impossible, but the file has no `ro-crate-metadata.json` descriptor, no `@graph`, no root entity, and no packaged files. A validator (`roc-validator` 0.13.1 on PyPI) is installable here. | **VERIFIED** |
| OF-13 | High | Radial profile is a Gaussian; mechanism selector inert | L2359–2396; `ctrl-mechanism` value never read. Mole fraction used as mass fraction (L2377). | **VERIFIED** |
| OF-14 | High | Explore correlation unsourced, fitted to the points it is compared with | Coefficients reproduce Dietrich methanol CO₂/He values exactly (0.450, 0.699). My recomputation matches the audit for all 7 tests quoted. NEW, for balance: across all 259 Table IX rows where a comparison is possible, the median error is ≈ 0 % but the range is −55 % to +606 %, and 12 % of tests are off by more than 20 %. The correlation is not uniformly bad; it is uncalibrated, unsourced and unreliable in the tails (near-limit tests). | **VERIFIED** |
| OF-15 | High | FSR is an input constant; colour = 0.91–0.92 × LLUV | L1599–1602, L1641–1643. NEW: TP p. 16 says colour ≈ ¾ × LLUV typically, smaller still for heptane. | **VERIFIED** |
| OF-16 | High | Ignition/extinction/cool-flame rule engine unsourced | L1543–1576. Cool flame is a TP *inference* in captions (Figs. 39, 66, 201: "indicative of cool flame burning"). | **VERIFIED** |
| OF-17 | High | g-jitter modelled as constant drift velocity; data drawn after FOV exit | L1607–1612, L1668. TP p. 5 and §4.2 (p. 16): drift from deployment residual velocity and g-jitter; droplets can drift back in, producing gaps. | **VERIFIED** |
| OF-18 | High | Fit is circular; 0.012 RMSE fallback; windows differ from NASA definition | L1698–1719. TP App. A.1: K is from a linear fit "from shortly after ignition to extinction". | **VERIFIED** |
| OF-19 | High | 14 source IDs, none resolvable; locator errors | Count reproduced: S01, S02, S03, S04, S06, S07, S08, S09, S25, S26, S30, S33, S35, S39. "Sec. 3.1.2, p. 7" should be p. 8; "S01 Sec. 18.3" does not exist in the TP. Most IDs *do* resolve in the Research Guide's register (§7); none resolves inside the HTML. | **VERIFIED** |

All Medium/Low/Informational findings I spot-checked (OF-20, -21, -22, -24, -27, -31, -36, -37, -38) hold, except the parts listed in Section 3.

---

## 3. Errors and omissions in the Phase A audit

| # | Audit location | What it says | What the source says | Effect |
|---|---|---|---|---|
| A1 | C02, Gap register | "0–9 atm facility capability not located" | TP §2.1, p. 2–3: chamber "can operate at pressures of approximately 0 to 9 atm"; FLEX safety analysis reduced maximum working pressure to "approximately 3 atm". | Prototype claim CLM-001 is **VERIFIED**, not unsourced. |
| A2 | C34, G07 | "Typical ~40 s" recording not located | TP §2.3 step (5)(c)(v), p. 5: "after a preset time (typically on the order of 40 s)". FOMA overboard vent: §2.1, p. 3. | G07 resolved. |
| A3 | OF-31 | "Table IX's H₂O and fuel-vapour fractions are ignored" | App. A.1 *defines* Fiber, Notes, H₂O, heptane-vapour and methanol-vapour columns, but the **printed** Table IX contains none of them (columns: P, O₂, N₂, CO₂, He, D₀, ext. diameter, K, t_b, test end). They are presumably in the electronic files. | The fix "carry trace species for replay" is impossible from the printed TP; it needs the data files. Also: App. A.1/Table IX disagree with each other (NEW). |
| A4 | OF-16 | "FLEX–063 none" (no extinction diameter) | Table IX prints **0** (with "Completion"). The A.1 definition says "–" marks completion/disruption, yet the table uses both "0" and "–" for completion and also "0" with "Disruption" (FLEX–039, –043, –052, –093). | The data model must keep the raw cell and not interpret "0" as a measured diameter. |
| A5 | OF-24 | "TP says igniters energized after needles retract (Sec. 2.3, p. 4)" | Correct statement, wrong locator: it is §2.1 (p. 4); the sequence itself is §2.3 (p. 5). | Locator only. |
| A6 | Exec. summary | "The prototype contains no experimental data at all" | Correct for time series. Several reported scalars are right (FLEX-023 pressure and date; the three NASA estimates; radiometer limitation; hardware dimensions). | Wording; does not change the finding. |

I found no error in the audit's arithmetic.

---

## 4. Additional findings (NEW)

| ID | Severity | Finding | Locator | Consequence for the platform |
|---|---|---|---|---|
| N1 | **High** | Needle conformal coating dissolved/flaked into the fuel in the tests reported; TP lists eight assertions about which observables were affected (e.g. methanol disruptive extinction "probably due to the contaminant"; ~4 distorted methanol droplets such as FLEX–088). | TP §5.2, pp. 16–17 | Data-quality flag on every TP test; caveat on disruption outcomes; claim records for each of the 8 assertions. |
| N2 | High | Table IX has 276 rows (FLEX–001…280; missing 156, 205, 213, 228) vs abstract "first 284 tests". FLEX–156 appears in Table VIII but not Table IX (confirmed on rendered page 24). | TP p. 1; Table VIII p. 15; Table IX pp. 20–28 | Record the count discrepancy; mark these test IDs "listed in matrix, no Table IX result". |
| N3 | High | Nominal (Tables I–VIII) vs reconstructed (Table IX) composition differ, e.g. FLEX–019…024 nominal 0.400 O₂, Table IX 0.34. Max O₂ in Table IX is 0.34. | Table III p. 11; Table IX | Store both; domain checks use Table IX; slider limits not justified by 0.40. |
| N4 | Medium | Colour flame ≈ ¾ LLUV flame (typical), smaller for heptane — contradicts prototype 0.91. | TP p. 16 | Remove 0.91; quote TP statement in the diagnostics bubble as a qualitative claim. |
| N5 | Medium | FLEX–114 printed pressure "0" mmHg; Table VI gives 0.70 atm. | Table IX p. 23; Table VI p. 14 | Source anomaly record; never silently "fix". |
| N6 | Medium | HiBMs scale factor 32.5 px/mm (§3.1.1 step 6) implies 30.8 µm/px and a 31.5 mm FOV, inconsistent with 30.25 mm / 1024 px = 29.5 µm. LLUV (8.86 px/mm) and colour (6.87 px/mm) are self-consistent. Also copy errors in TP: HiBMs step 6 says "flame", LLUV/colour step 6 say "droplet"; colour §3.3.2 says "FOV for the LLUV is 93.2 mm". | TP pp. 8–9 | Extends audit OF-36. Preserve verbatim; show discrepancy. |
| N7 | Medium | TP internal inconsistencies on scope: App. A says "March 2009 through December 2010" but Table IX runs to 12/8/11; Conclusions (p. 17) and the abstract (p. 2) say D₀ "between 2 and 5 mm" but Table IX includes 1.1 mm (FLEX–069) and Table V lists 1.29 mm. Table IX D₀ range is 1.1–4.67 mm. | TP pp. 17, 19, 13, 28 | Do not quote any single "range" without its source. |
| N8 | Medium | Tests FLEX–001…009 used 1/30 s shutter with igniter/flame image distortion; after 009 it was 1/1000 s, "resulting in more accurate droplet size data". | TP §5.1 (p. 16) | Data-quality flag on 001–009. |
| N9 | Medium | Prototype sequence order is wrong: TP starts recording **before** deployment ((5)(c)(i) → (ii) deploy → (iii) ignite → (iv) retract → (v) stop); prototype has "Deploy → Ignite → Record". TP step (4) "open fuel valve and purge line" is missing. | TP §2.3, p. 5 | Rebuild the timeline from TP §2.3 with each stage cited. |
| N10 | Low | Two approximate cells in Table IX burn time (FLEX–227 "~6", FLEX–229 "~9"); six rows whose four mole fractions sum to 0.98 (2-dp rounding). | Table IX | Parser preserves "~" and raw strings; sum check reports, does not normalize. |
| N11 | Info | The 80-µm fiber being silicon carbide is not stated in the TP; it is stated in Nayagam et al. 2014 (NTRS 20140006750), a FLEX-team conference paper. Dietrich 2014 abstract (VERIFIED, abstract only) confirms the 1.5–5.0 mm / 0.1–0.4 / 0.7–3.0 atm envelope wording and the post-radiative-extinction cool-flame observation. | NTRS 20140006750; Dietrich 2014 abstract | SiC claim → partially supported via secondary source; Dietrich figure values still UNVERIFIED. |

---

## 5. What already exists from this review (non-destructive)

| Item | Path | Status |
|---|---|---|
| Git checkpoint with read-only copies of all inputs | `sources/`, `prototype/original/`, `SOURCE_CHECKSUMS.sha256` | Committed `f90c20f` |
| Table IX extractor (verbatim cells kept, "–" → null, "~" flagged, PDF page recorded, source PDF hash recorded) | `tools/extract_table_ix.py` | Ran: 276 rows, all with 15 tokens; spot-checked against rendered page 24 |
| Table IX as CSV (staging, not yet a released dataset) | `data/extracted/table_ix.csv` | Not yet schema-validated |

Not yet done: unit tests for the extractor, a full row-by-row check against page images, any change to the prototype.

---

## 6. Feature inventory: keep / revise / remove / defer

| Feature | Decision | Treatment |
|---|---|---|
| Scope banner, non-endorsement statement | Keep | Calmer styling; add needle-contamination and data-availability notices. |
| Replay / Explore / OOD modes | Revise | Replay = source data only. Explore = disabled until a documented model exists (then D²-law educational baseline). OOD = computed from Table IX coverage, not a mode button. |
| Archived test selector | Revise | Populate from Table IX (all 276 rows, searchable). Literature-figure cases become a separate entity type with "candidate test mapping" status. |
| 3D apparatus | Keep | Conceptual watermark stays; add click-picking, all three camera frusta, cite each component fact. |
| Science bubbles | Revise | Every sentence gets a claim ID or an "interpretive" tag; "Live state" → "Typical state at this stage (illustrative)". |
| Procedure timeline | Revise | Re-sequence per TP §2.3; time zero = igniter ON (App. A.1, App. B); planned JSC timings labelled "planned, unverified". |
| Diagnostic camera views | Revise | Keep the channel distinctions. Synthetic frames labelled CONCEPTUAL ILLUSTRATION. Remove "CV threshold" measurement readout. |
| D²(t) / flame plots | Revise | Show digitized series (where digitized) with provenance; otherwise "time series unavailable" + Table IX scalars. |
| FSR plot | Revise | Only as ratio of two loaded series at matched times; otherwise unavailable. |
| Prediction card | Revise | Becomes the Brief §6.1 result-transparency panel. |
| Radial T/Y profiles | Revise | Persistent "CONCEPTUAL ILLUSTRATION — NOT SOLVER OUTPUT"; no fuel-specific peak temperatures. |
| Mechanism selector | Remove (defer) | Replace with a policy text; re-enable when a mechanism file is loaded. |
| Governing-equations table | Keep | As documentation, labelled "not implemented", with the audit's F2 corrections. |
| Monte Carlo interval | Remove | Re-introduce only with a declared input-distribution table and a documented model. |
| Sobol chart | Remove | Re-introduce only when computed (SALib) with design, N, S1/ST and CIs. |
| Uncertainty budget table | Keep (rewrite) | Statuses: reported / estimated / assumed / not quantified. |
| Claim ledger | Keep (rebuild) | Machine-readable registry; atomic claims; two status fields. |
| Research Commons | Remove for now | Badge-governance table can stay as policy text. No seeded posts. Forum deferred until persistence exists. |
| Run UUID / SHA-256 header | Revise | Genuine SHA-256 or "unavailable"; test ID stable; run ID only when a computation actually executes. |
| RO-Crate export | Revise | Package with real files, chosen spec version, validated; until then the button says "Export JSON manifest (not an RO-Crate)". |

---

## 7. Proposed architecture for this revision

Constraint that shapes the design: the page must work offline and from `file://`. Browsers block ES-module imports and `fetch()` of local JSON from `file://`, and the CDNs are unreachable in some environments (confirmed here).

**Proposal: modular source, single-file build.**

```
open-flex/
  sources/            immutable inputs + SHA-256 manifest (read-only)
  data/
    extracted/        verbatim extractions (Table IX CSV)          — PUBLISHED (tabulated)
    digitized/        per-figure CSV + digitization record JSON    — DIGITIZED
    derived/          fits, D², FSR computed from the above        — DERIVED
    registry/         sources.json, claims.json, discrepancies.json
    schemas/          JSON Schemas for every record type
    MANIFEST.json     every data file with SHA-256, parent, method
  app/                modular JS/CSS (classic scripts, one namespace)
  vendor/             pinned three.js r128, OrbitControls, Plotly 2.27.0 (from npm, hashed)
  science/            Python: d2_baseline (educational), digitize, fit, rocrate; future solver interfaces
  tools/              extract, digitize, build, validate, export
  tests/              pytest (tools/science), node --test (pure JS), Playwright (browser)
  dist/open_flex.html single self-contained file built from the above
  docs/               this plan, data dictionary, V&V plan, model cards, milestone reports
```

Record types and identity (JSON Schema in `data/schemas/`):

- `PhysicalTest`: `test_id` = NASA "FLEX–xxx" preserved verbatim + `cir_identifier` + platform UUID; conditions as printed; `data_quality_flags` (needle contamination, early-shutter, FOV gaps…).
- `LiteratureFigureCase`: DOI, figure/panel, extracted conditions, `candidate_test_ids` with mapping status.
- `Dataset`: id + semantic version + file hashes + `evidence_class` (SOURCE_MEASUREMENT / PUBLISHED_TABULATED / DIGITIZED / DERIVED).
- `AnalysisRun` / `SimulationRun`: new UUID per execution; parent dataset/test IDs; inputs; code version; never carries a NASA test ID as its own identity.
- `Source`, `Claim` (two fields: `evidence_class` and `verification_status`), `Discrepancy` (all values kept, preferred value + reason if any).

---

## 8. Milestones

Each milestone ends with a report (objective, files, scientific justification, changes, tests run, results, limitations, unresolved issues) and a git commit.

| M | Objective | Main changes | Acceptance tests (must actually run) |
|---|---|---|---|
| **M1** | Scientific integrity fixes in the existing single file | Remove seeded posts, Sobol chart, MC interval, FNV fallback, CV-threshold readout, cool-flame rule engine, fake replay. Replay shows Table IX scalars for the selected test + "time series unavailable". Presets replaced by Table IX rows; literature cases split off with "candidate mapping". Export renamed "JSON manifest (not RO-Crate)", NASA ID only on unmodified source records, computed composition sum. Radial tab labelled conceptual; mechanism selector disabled. Two-status badges. | Playwright: no element contains the removed strings; Replay plot has 0 synthetic points; SHA-256("abc") = ba7816bf…; hash path returns "unavailable" when `crypto.subtle` is stubbed out; export from modified Explore state has `legacy_nasa_test_id: null`; Table IX values shown for FLEX–023/–035 equal the CSV; console has no errors with and without CDN. |
| **M2** | Genuine data architecture | Extract data/registry into files; schemas; manifest with hashes; loader; vendored libraries; single-file build; full Table IX selector; discrepancy register (N2–N7, OF-36). | pytest on extractor (count, nulls, "~", raw preserved, page numbers); schema validation of every record; manifest hashes recomputed independently; build reproducible (same bytes twice); offline browser test. |
| **M3** | Digitized replay pilot | Digitize Appendix B Fig. 27 (FLEX–023) and Fig. 39 (FLEX–035) from the embedded JPEGs by colour-marker detection with recorded axis calibration; overlay check images; D²(t), LLUV and colour series kept separate; gaps preserved; D² fit on digitized data with N, window, residuals and an autocorrelation caveat; compare fitted K with Table IX K as a digitization check (not validation). | Calibration residual at tick marks < 1 px; overlay image reviewed by eye and attached; fitted K reported beside Table IX K with difference; plotted point count equals file rows. |
| **M4** | Transparency and uncertainty | Brief §6.1 result panel on every quantitative result; rewritten budget table; claim ledger from registry (atomic, searchable, locators clickable); per-series provenance in legends and tooltips; domain status from Table IX coverage (nearest tests per fuel/diluent). | Every rendered claim has an ID or "interpretive" tag (automated scan); no interval without type/method/coverage; NASA ±50/200/250 µm never labelled σ or CI (automated string check). |
| **M5** | Dashboard redesign and accessibility | Light default theme per Ground-Truth Brief §9; five workspaces (Overview, Experiment, Physics & Results, Uncertainty & Validation, Evidence & Reproducibility); 3D click-picking + keyboard list; three camera frusta with FOV values and discrepancy note; timeline re-sequenced (N9); reduced-motion; ARIA tabs. | Keyboard-only walkthrough script; axe-core automated audit (0 serious/critical); screenshots at 3 widths; reduced-motion stops autoplay. |
| **M6** | Reproducible export and future-ready science layer | RO-Crate 1.2 zip (descriptor, root dataset, data files with hashes, provenance); Python `science/` package: schemas, D²-law educational baseline with code-verification tests against the analytic solution, documented interfaces for a future spherical 1-D solver, Cantera adapter stub, UQ/ML placeholders; V&V plan document. | `roc-validator` passes on the exported crate; unzipped file hashes match metadata; pytest for baseline (analytic limits, units). |

Explore mode stays **disabled** until M6. When enabled, it runs only the documented D²-law baseline, with property values from a cited source, labelled "educational baseline — no extinction, no radiation, not validated", and shown with a parity plot against Table IX so its error is visible.

---

## 9. Scientific assumptions this plan makes

1. Table IX scalars are treated as **PUBLISHED_TABULATED** (authors' analysis results), not raw measurements.
2. Digitized Appendix B points are **DIGITIZED**: approximate, with extraction uncertainty from image resolution and marker size; never called raw.
3. NASA ±50/±200/±250 µm are stored as `reported_measurement_uncertainty`, coverage "not stated", distribution "not specified", and not propagated statistically.
4. Ideal microgravity in any model = body-force g = 0 with finite density; residual acceleration is not modelled.
5. "Cool flame" is shown only as the TP's inference, quoted with its caption locator.
6. Where two sources disagree, both values are shown; a "preferred" value is chosen only with a stated reason (e.g. Table IX for actual composition, because App. A.1 says it is reconstructed from detailed records).

---

## 10. Unresolved source requirements (what would unblock more)

| Need | Unblocks | Priority |
|---|---|---|
| The per-test **text data files** that accompany the TP (App. B says "available in a text file associated with this report"; App. A mentions a DVD addendum; PSI-69 "FLEX HEP / FLEX MeOH") | Replace digitization with source time series for all tests | **Highest** |
| Dietrich et al. 2014, full text (Figs. 3–6 captions, test numbers, LOI section) | Confirm or reject literature-case mappings; LOI claims; drift values | High |
| Nayagam et al. 2013 (methanol, CO₂/He) | Methanol FSR/K claims | Medium |
| Williams 2009 slides ("Test 0035") | Whether it is FLEX–035 | Medium |
| FLEX Test 023 video (S08) metadata | 33.4 % O₂ value's origin | Medium |
| Banu 2008 (CIR optics) | FOV / scale-factor discrepancies (OF-36, N6) | Medium |
| CIR accelerometer records | Any g-jitter representation | Low (feature disabled meanwhile) |
| A cited property dataset for methanol and n-heptane (λ, c_p, ρ_l, L, T_b, ΔH_c) | D²-law educational baseline | Needed for M6 |
| JSC-17962-27, FLEX_Quad | 196 / 258 counts; planned timings | Low |

---

## 11. Decisions requested before implementation

1. **Approve the milestone plan** (M1 → M6), or narrow it.
2. **Architecture:** modular source + single-file offline build (recommended), versus going straight to the Master Brief's Vite/TypeScript + FastAPI stack now.
3. **Digitization pilot** of Appendix B Figs. 27 and 39 (recommended), versus waiting for the original text files.
4. **Research Commons:** remove for now (recommended), versus keep as a clearly labelled local-only demo.
