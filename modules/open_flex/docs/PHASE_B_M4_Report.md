# Phase B — Milestone M4 report: transparency, uncertainty and condition coverage

Project: Open FLEX (original FLEX only). Source: [S01] NASA/TP-2015-216046.
Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product; a NASA citation does not imply endorsement.

## 1. Objective

The approved plan (§8, M4) asked for:
- a result panel with the fields of Brief §6.1 on every quantitative result;
- a rewritten, registry-driven uncertainty budget;
- a claim ledger with clickable locators;
- per-series provenance in legends and tooltips;
- domain status from Table IX coverage.

Acceptance criteria:
- every rendered claim has an ID or an "interpretive" tag, checked by an automated scan;
- no interval without its type, method and coverage;
- NASA's ±50/200/250 µm never labelled σ or CI, checked by an automated string check.

## 2. Files added or modified

| Area | Files |
|---|---|
| Uncertainty registry (new) | `data/registry/uncertainty_components.json` (14 components, UC‑01…14); `schemas/uncertainty_component.schema.json` |
| Coverage (new) | `tools/coverage.py` (reference implementation); JS port in `app/src/js/45_transparency.js` |
| App (new module) | `45_transparency.js`: result cards, analysis card, budget, coverage panel and chart, claim/source/discrepancy/UC navigation |
| App (modified) | `40_views.js`, `41_hotspots.js`, `31_scene_update.js`, `50_panels.js` (provenance attributes, links, CONCEPTUAL/DIGITIZED in legend names; old budget/result/link functions removed), `body.html` (result selector, budget columns, coverage panel), `styles.css` |
| Registries | `claims.json` 0.4.0 (+CLM‑041, ‑042); `discrepancies.json` 0.4.0 (+DSC‑024); `datasets.spec.json` 0.4.0 (+DS‑REGISTRY‑UNCERTAINTY) |
| Tools | `validate_data.py` (uncertainty registry and claim references); `build_app.py` (bundles the registry) |
| Tests | new `tests/unit/test_m4_data.py` (9), `tests/browser/test_m4_browser.py` (11), `tests/browser/provenance_scan.js`; `tests/browser/conftest.py` (session fixture moved here) |

## 3. Scientific justification and new source findings

- **Extrapolated extinction diameters (CLM‑041, new).** App. A.1 states that when the droplet left the
  HiBMs view before extinction, the authors extrapolated the burning history to estimate the extinction
  diameter. Table IX does not mark which values were extrapolated. This is now uncertainty component UC‑06
  and appears on every extinction-diameter result card. The original audit and M1–M3 had missed it.
- **Undefined columns (CLM‑042, DSC‑024, new).** A.1 gives no definition for "Burn time", "Test end" or
  "He". The burn-time card says "not defined in App. A.1" instead of guessing whether it is counted from
  igniter ON or from ignition.
- **Uncertainty semantics.** NASA's ±50/±200/±250 µm are stored with coverage factor "not stated",
  distribution "not specified" and `propagated: false`. The schema forbids σ, "standard deviation",
  "confidence" or "95" in an interval type and allows coverage only as "not stated" or "not applicable".
  The validator rejects all five tested violations.
- **Coverage is not a validation domain.** The coverage panel answers only "how close is this to something
  that was tested?" It works within the same fuel and diluent class, using printed P, O₂ and D₀. Its labels
  (INSIDE_NEAR_TEST, INSIDE_SPARSE, OUTSIDE_RANGE, NO_TESTS) and its 0.25 distance threshold are declared
  conventions, not statistics. The panel says so and states that no model is validated anywhere. FLEX‑114
  (pressure printed as 0) is excluded from coverage.

## 4. What changed in the app

1. **Result cards (Brief §6.1).** A selector covers K, D₀, extinction diameter, burn time, pressure and O₂.
   Every card has the same ten fields: result class, measurand (with claim link), estimate, interval,
   interval type/coverage, method, sample size, domain status, uncertainty components (linked) and
   evidence (linked). The domain status of a physical test states "observation, not a prediction" and
   names the three most similar tests.
2. **Analysis card.** The digitized-fit results from M3 get the same ten fields. The K range is rendered as
   an `.interval` element carrying `data-interval-type="sensitivity range"`, a method and
   `data-coverage="none"`.
3. **Uncertainty budget.** The budget is generated from the registry and shows only the components that
   apply to the selected test: 13 of 14 for FLEX‑035, with UC‑10 only for FLEX‑001…009 and UC‑12/13 only
   for digitized tests. Each row shows its status, value, type, coverage factor, distribution and claims.
4. **Navigation.** Claim, discrepancy, source and uncertainty-component IDs are links:
   - clicking one switches tab, clears any ledger filter, scrolls to the entry, highlights it and moves
     keyboard focus there;
   - with reduced motion, the highlight is an outline instead of an animation;
   - source locators in the claim ledger link to the source registry.
5. **Coverage panel** (Uncertainty tab):
   - a form defaults to the selected test, with an option to exclude it;
   - it shows the label, a table of tested min–max per variable, and the five nearest tests with their
     printed values (each a link that selects that test);
   - a single-axis chart shows tested O₂ against pressure, with the query point;
   - without the plotting library, a message replaces the chart and the table still works.
6. **Provenance in legends.** Chart series names now end in "· DIGITIZED" or "· CONCEPTUAL", and hover
   labels state the class.

## 5. How the acceptance criteria are checked

| Criterion | Automated check | Result |
|---|---|---|
| Every rendered quantitative statement has provenance | `provenance_scan.js` walks every text node that contains a number with a unit and requires an ancestor carrying `data-claims`, `data-source`, `data-derived` or `data-interpretive`. It is run for 10 tests × every camera channel × every result option × every component card. | 0 untagged (77 before M4) |
| Every cited ID exists | All CLM‑/DSC‑/UC‑ IDs in the rendered text and attributes are resolved against the registries, for 10 tests. | pass |
| No interval without type, method and coverage | Every `.interval` element must carry all three attributes. | pass |
| NASA ± never σ/CI | Any block containing ±50/200/250 µm together with σ, sigma, standard deviation, 95 %, "confidence interval" or "CI" must also contain a negation. The same rule applies to any "confidence interval" or "95 % CI" anywhere. | pass |
| Registry semantics | Schema plus validator; five injected violations are all rejected. | pass |
| Coverage JS = Python | All 263 coverage rows (each excluding itself) and 100 random queries, including out-of-range points: label, group size, outside list, nearest five and distances (to 1e‑4) must be identical. | 363/363 identical |

**Limit of the scan.** It treats a "claim" as text containing a number with a unit. Qualitative statements
without numbers are covered only where whole containers are tagged (hotspot cards, channel descriptions,
the ledger, discrepancies, digitization panels), not sentence by sentence.

## 6. Tests performed and results

| Suite | Tests | Result |
|---|---|---|
| M1–M3 (unchanged except the fixture move) | 54 | pass |
| M4 unit: NASA values keep their semantics; validator rejects σ / "95 % confidence" interval types, coverage factor "2", `propagated: true`, and a reported component without claims; coverage reference cases (FLEX‑114 excluded; no test above O₂ 0.34) | 9 | pass |
| M4 browser: provenance scan; ID resolution; interval/± semantics; claim and discrepancy links navigate (with filtered ledger); source link; result cards (10 fields, burn-time note, UC‑06); budget for 3 tests; coverage parity (363 queries); coverage panel (out-of-range, chart, nearest-test link); coverage without Plotly | 11 | pass |
| **Total** | **74** | **74 passed** |

**Fresh-copy check.** I deleted all built HTML, digitized data, analyses, records and the manifest from a
copy of the repository, then ran `setup_and_test.sh`. It rebuilt everything from the PDF, every file came
out byte-identical, and all 74 tests passed.

## 7. Remaining limitations

- **Scan scope.** The provenance scan checks numbers with units. Qualitative sentences are tagged at the
  container level, so a new untagged qualitative sentence would not be caught automatically.
- **Coverage measure.** Coverage uses per-variable min–max and nearest-neighbour distance only, not the
  shape of the tested region. Two variables inside their ranges can still describe an untested combination;
  the INSIDE_SPARSE label covers part of this. Diluent fractions (how much CO₂ or He) are not a coverage
  variable yet.
- **Uncertainty components are not combined.** That is deliberate: the source gives no basis for combining
  them. No overall uncertainty of K exists in this build.
- **Interface.** The interface is still the dark M1 layout; M5 (redesign and accessibility audit) is next.
- **Review.** I wrote the uncertainty registry from my reading of the report; it has not been independently
  reviewed.

## 8. Known unresolved issues

- **New:** DSC‑024 (undefined columns), and CLM‑041 (extrapolated extinction diameters are not marked in
  Table IX).
- **Earlier:** DSC‑010, 014–017, 021 and 023 remain open.

## 9. Next

M5: the dashboard redesign (light default theme and five workspaces), 3D click-picking with a keyboard
list, camera frusta, ARIA and reduced motion, and an axe-core audit.
