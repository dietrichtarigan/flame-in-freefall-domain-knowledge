# Phase B — M6 report: D²-law educational baseline, Explore mode, Python package, RO-Crate 1.2, V&V plan

Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product; NASA citations do not imply endorsement.

## 1. Objective

The M6 milestone has four parts:
- a documented, **code-verified** model that turns on the app's Explore mode, while keeping simulations apart
  from physical tests;
- a Python package for working with the data;
- a validated **RO-Crate 1.2** description of the whole package;
- a verification-and-validation (V&V) plan.

## 2. Files

| Area | Files |
|---|---|
| Model | `openflex/d2law.py` (reference), `app/src/js/60_model.js` (browser port) |
| Properties | `tools/build_model_properties.py` → `data/model/d2law_properties.json` |
| Verification | `tools/verify_d2law.py` → `data/verification/d2law_code_verification.json` |
| Runs | `tools/run_d2law_baseline.py` → `data/simulations/d2law_baseline_runs.json` (276 SimulationRuns), `data/analysis/d2law_vs_table_ix.csv` |
| Explore UI | `app/src/js/61_explore.js`, `app/src/body.html`, `app/src/styles.css`, `app/src/js/50_panels.js` (export), `90_main.js`, `40_views.js` |
| Python package | `openflex/__init__.py`, `openflex/data.py`, `openflex/__main__.py`, `pyproject.toml` |
| RO-Crate | `tools/build_rocrate.py` → `ro-crate-metadata.json`; `tools/validate_rocrate.py`; `vendor/test-only/ro-crate-1.2/context.jsonld` (pinned, CC0) |
| Registries and schemas | Sources S42–S47; claims CLM-051–057; DSC-027; evidence class `REFERENCE_DATA`; dataset class `SIMULATION`; 4 new datasets |
| Checks | `tools/validate_data.py` now also checks the SimulationRun schema, run-identity rules and that the verification record is current |
| Docs | `docs/PHASE_B_M6_D2law_Model.md`, `docs/PHASE_B_M6_VV_Plan.md`, this report, README |
| Tests | `tests/unit/test_m6_model.py` (12), `tests/browser/test_m6_explore.py` (9) |

## 3. Justification of the main choices

- **Model.** The classical quasi-steady flame-sheet model is the theory the TP cites (CLM-051). It needs no
  parameters fitted to FLEX and can be verified exactly, so its distance from FLEX is informative rather than
  tuned away.
- **Property data.** No unsourced number enters the model:
  - fluid properties come from a pinned property library, CoolProp 8.0.0 (S42); the generator refuses other
    versions;
  - the heats of combustion come from cited tertiary sources (S43–S45), with their spread kept (DSC-027);
  - the ambient temperature of 298.15 K is labelled an assumption, because the TP says only "ambient temperature"
    (CLM-052).
- **Gas properties of the ambient mixture.** CoolProp's methanol and heptane equations are valid only to
  620 K and 600 K, so fuel-vapour properties at flame temperatures would be extrapolations. This is stated as a
  model limitation.
- **Explore mode is gated.** It switches on only if the embedded verification record is PASS *and* its hashes
  match the embedded implementation and property table.
- **RO-Crate.** It describes the repository as an attached crate, with SHA-256 on every file and one
  CreateAction per derived dataset. The NASA PDF is referenced, not packaged. **No licence is invented**: the
  crate states that none has been chosen.

## 4. Changes

1. **D²-law model.** It gives B, K, burn time, flame standoff ratio, flame temperature and radial profiles.
   T_prop = (T_s+T_f)/2 is found by fixed-point iteration; mixture conductivity uses Wassiljewa/Mason–Saxena
   (S46, S47).
2. **Code verification.** 24 checks, listed in the model document §4: conservation residuals, boundary and jump
   conditions, surface energy balance, RK4 convergence order, fixed point, invariances and an independent hand
   calculation.
3. **Simulation runs** at the printed conditions of all 276 Table IX tests:
   - run ids are `SIM-` + 12 hex digits of a hash of the model version, inputs and property table;
   - each run names `seeded_from_physical_test`, lists its modifications, and carries a scope statement.
4. **Explore mode** in Physics & Results:
   - inputs are seeded from the selected test and the form can be reset to the printed values;
   - N₂ is the balance;
   - every changed input is listed, and the status changes to "Modified … does not describe FLEX–nnn";
   - the outputs table sits next to the printed values, labelled "comparison only, not validation";
   - three plots: D² and flame diameter against the digitized data, and the model's radial profiles. A model curve
     beyond the data axis is stated in the plot title, not hidden;
   - model-form sensitivity and the verification table are in collapsible sections;
   - the 3D view and the physical record do not change.
5. **Export.** The JSON export now points to the repository RO-Crate. When Explore is on, it adds the current
   simulation run in a separate `simulation_runs` section; the physical `record` is unchanged.
6. **Python package `openflex`** (no dependencies):
   - hash-checked data access;
   - CLI commands `info`, `test` and `baseline`. A modified baseline prints "MODIFIED inputs — not the conditions
     of FLEX-nnn".
7. **RO-Crate 1.2.** 178 data entities, 75 CreateActions and 30 contextual entities, including ComputerLanguage
   entities and the cited sources.
8. **Pipeline.** `run_pipeline.sh` now runs verification, the baseline runs, crate generation and crate
   validation; `--properties` also regenerates the property table.
9. **Correction to M5.1.** The comparison sheet `docs/screens/m5_1_photoreal_sheet.png` called FLEX-035
   "methanol". Tables V and IX both say **n-heptane**, and the caption is now corrected. The rendering itself was
   right: the figure caption reports no soot or luminous zone, so none was drawn.

## 5. Tests

| Test | Result |
|---|---|
| Code verification, 24 checks, record deterministic and current | pass |
| Injected defects (1 % conductivity, wrong outer profile, 7 instead of 8) each turn the record to FAIL | pass (3) |
| All 276 SimulationRuns reproduce from their inputs; ids unique, never FLEX ids | pass |
| Comparison-claim numbers (CLM-057) recomputed from the CSV | pass |
| Property table regenerated byte for byte with CoolProp 8.0.0 | pass |
| Scope flags (no O₂ → no burning; property temperature outside the table → error) | pass |
| `DataPackage` detects a changed file hash; CLI output labels | pass |
| RO-Crate: every file entity exists with its current SHA-256; validator passes ro-crate-1.2 at REQUIRED | pass |
| Browser port equals Python for all 276 tests (outputs < 10⁻⁵ relative, identical run ids and flags) | pass |
| Explore: seeding, SIM id equal to the Python record, modification listing, N₂ balance, reset, follows test selection | pass |
| Explore does not change the record, the timeline or the flame uniforms | pass |
| Gate: disabled with a reason when the record is FAIL or not current | pass |
| Export: simulation run separate; record unchanged | pass |
| No plot library: tables still shown, plots replaced by a notice | pass |
| axe-core audit of the physics workspace with Explore open, light and dark themes | pass, no violations |
| **Full suite** | **158 / 158 pass** (137 earlier + 21 new; 10 min) |

The browser tests ran in headless Chrome with software WebGL only.

## 6. Results

- **Code verification: PASS 24/24.**
  - Conservation residual ≤ 2.5·10⁻⁸.
  - RK4 observed order 3.88.
  - Hand calculation agrees to 1.6·10⁻¹⁵: heptane in air at T_prop = 1500 K gives K = 2.226 mm²/s,
    B = 9.12, T_f = 2576 K, r_f/r_s = 36.0.
- **Comparison with Table IX.** The model K is above the printed K for every one of the 260 tests with both
  values. Model/printed median: 2.1 for methanol (151 tests), 4.3 for heptane (109). For FLEX-035 the model's
  flame-to-droplet diameter ratio is ≈ 36; the digitized ratio is 4–11. This is a comparison, not validation, and
  its causes are not quantified.
- **Model-form sensitivity.** The property temperature dominates: fixed at 600 K or 2000 K, K changes by −40 % or
  +22–24 %. Liquid density changes K by 5–10 %, the heating value by under 2 %.
- **RO-Crate 1.2.** At REQUIRED severity, 30/30 requirements and 63 checks pass; 3 checks are skipped (web
  availability while offline, and the detached-crate rule, which does not apply). At RECOMMENDED severity 79 of
  81 requirements pass. The two open ones need the owner's decision: `publisher`, and a licence URL.

## 7. Limitations

- The model represents none of FLEX's distinctive physics: extinction, radiation, soot, cool flames, unsteady
  effects, pressure dependence and the ignition transient. The full list is in the model document §6.
- Gas properties are those of the ambient gas, not of fuel vapour and products. The property-temperature rule is a
  modelling choice with ±20–40 % effect on K.
- The heats of combustion are tertiary sources read from web search results; their primary references were not
  checked.
- CoolProp's transport correlations are used at up to 2000 K, the equations' stated upper limit. Their accuracy
  near that limit was not assessed here.
- **RO-Crate validation offline.** Validation used a pinned copy of the official 1.2 context
  (RO-Crate repository commit a7055166, SHA-256 in VENDOR.json), served by the wrapper because w3id.org was
  unreachable; the checks themselves are unchanged. Web-based entities (source URLs) were not checked for
  availability.
- The app's per-test export is still plain JSON, not an RO-Crate.

## 8. Unresolved issues (owner's decisions)

1. **A licence for the repository.** It would close the RO-Crate licence recommendation; until then no reuse
   licence is granted.
2. **A publisher name** (person or organisation) for the crate.
3. **The validation metric and acceptance criteria** (V&V plan §3), to be agreed before any validation run.
4. **Next data step.** The planned user data come next: per-test NASA text files and the Dietrich et al. 2014 full
   text.
