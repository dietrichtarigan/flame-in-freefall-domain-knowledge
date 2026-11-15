# Verification & validation plan (Phase B M6)

Status 15 Nov 2026. Prepared by Claude (AI assistant). Terms used:
- **code verification**: are the equations solved correctly?
- **solution verification**: how large is the numerical error of a given run?
- **validation**: how well does the model represent FLEX, judged against measured data with their uncertainties?

Validation is never claimed in this release. No NASA endorsement is implied.

## 1. Current status

| Item | Code verification | Solution verification | Validation |
|---|---|---|---|
| Table IX / test-matrix extraction | Cell-level checks against page images (M2) | — | — |
| Digitized Appendix B plots | Axis-calibration residuals, re-drawn overlays, self-checks (M3, M5) | — | Consistency of digitized D² slopes with printed K (13 tests; ANALYSIS, M4/M5) |
| 3D flame rendering | Pixel test: rendered edge equals the measured diameter (M5.1) | — | Not applicable (visualisation) |
| D²-law educational baseline | **24/24 checks PASS** (`data/verification/d2law_code_verification.json`) | Closed form; RK4 order check only (CV-05) | **Not validated.** The comparison with Table IX shows model K above printed K for every test (CLM-057). |
| Future spherical 1-D solver | — | — | — (target formulation only) |

## 2. Rules that stay in force

1. **IDs stay separate.** A SimulationRun has a `SIM-` id and is never identified by a FLEX id. It cites the test
   whose printed conditions seeded it and lists every modified input (enforced in `tools/validate_data.py`,
   the app and the tests).
2. **Explore mode is gated.** The app enables Explore only when the embedded code-verification record says PASS
   and its SHA-256 values match the embedded implementation and property table.
3. **No calibration to FLEX in this release.** The baseline has no parameters fitted to FLEX data. If any are
   introduced later, the tests used to fit them must be listed and excluded from any comparison.
4. **Comparison wording.** Model–data differences are reported as comparisons with their basis, not as
   "validated", "agrees" or "accurate".

## 3. What validation would need (not started)

| Need | Why | Where it could come from |
|---|---|---|
| Measured D²(t) and flame-diameter series per test | Validation needs the measured histories, not printed summaries | The per-test text files the TP mentions (CLM-040); planned user data after M6 |
| Uncertainties of K and of the diameters, with coverage | Without them no validation metric can be judged | TP gives ±50/200/250 µm image estimates without coverage (CLM-009, -011, -012); Dietrich et al. 2014 full text (planned) |
| A validation metric and acceptance criteria | Pass/fail must be decided before looking at results | **For the project owner to decide** (proposal below) |
| Validation domain | Which fuels, pressures, diluents and D₀ the claim covers | Table IX coverage map (M4) |
| A model able to represent extinction | FLEX's main outcomes are extinction diameters and limits | Future 1-D solver with radiation and finite-rate chemistry |

**Proposed procedure (draft for agreement, not yet adopted):**
1. Choose the validation quantities (K over a declared quasi-steady window, flame standoff ratio, extinction
   diameter).
2. Split the tests into calibration and validation sets *before* running.
3. Report model−data differences relative to the combined data and numerical uncertainty, per test and over
   the domain.
4. State the domain and every excluded test with its reason.

## 4. Next steps

1. Add the user-supplied per-test data files and the Dietrich et al. 2014 text. Register each as a source with
   SHA-256, and re-run the digitization checks against the original numbers where they overlap.
2. Agree the validation metric and acceptance criteria (§3) before any validation run.
3. Only after that, consider a 1-D solver. Its code verification would use method-of-manufactured-solutions and
   grid-convergence studies, and it would first be checked against this baseline in the limits where both apply.
