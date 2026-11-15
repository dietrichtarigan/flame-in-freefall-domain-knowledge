# Open FLEX — evidence-traceable virtual laboratory (Phase B)

Independent prototype about the original NASA Flame Extinguishment Experiment (FLEX, 2009–2011).
Not a NASA product; not NASA-endorsed.

- Open `dist/open_flex_lab.html` in a browser (works offline).
- Rebuild: `python3 -I tools/build_app.py` (deterministic).
- Full setup check (deps, PDF hash, pipeline, all tests): `CHROME=/path/to/chrome ./setup_and_test.sh`
- Tests only: `python3 -m pytest -q tests` (needs Playwright + Chrome + poppler `pdftotext` + the source PDF).
- Source PDF expected at `sources/original/NASA-TP-2015-216046.pdf` (SHA-256 in `SOURCE_CHECKSUMS.sha256`;
  NTRS 20150023456). It is omitted from the lightweight zip.
- Rebuild all data from the PDF and validate: `./tools/run_pipeline.sh` (add `--verify` to redo the ~9-min page-image checks of Table IX and Tables I–VIII).
- Python packages: `python3 -m pip install -r requirements.txt`; system: poppler, Chrome; tesseract only for `--verify`.
- Data layout: `data/extracted` (as printed) · `data/derived` (comparisons) · `data/verification` · `data/registry` (sources, claims, discrepancies) · `data/records` (PhysicalTest, LiteratureFigureCase) · `data/digitization` + `data/digitized` (DIGITIZED: 13 tests, method 1.1.0; overlay review in overlay_review.json) · `data/analysis` (AnalysisRun) · `data/registry/uncertainty_components.json` (UC-01…14) · `tools/coverage.py` (Table IX coverage) · `data/MANIFEST.json` (Dataset records) · `data/model` (D²-law property table) · `data/simulations` (SimulationRun, `SIM-` ids, never FLEX ids) · `schemas/` (JSON Schema 2020-12) · `ro-crate-metadata.json` (RO-Crate 1.2 description of the whole package).
- Reports: `docs/PHASE_B_01_Independent_Assessment_and_Revision_Plan.md`, `docs/PHASE_B_M1_Report.md`, `docs/PHASE_B_M2_Report.md`, `docs/PHASE_B_M3_Report.md`, `docs/PHASE_B_M4_Report.md`, `docs/PHASE_B_M5_Report.md`, `docs/PHASE_B_M5_1_Rendering_Addendum.md`, `docs/PHASE_B_M6_Report.md` (with `docs/PHASE_B_M6_D2law_Model.md` and `docs/PHASE_B_M6_VV_Plan.md`), `docs/PHASE_B_M6_1_Sharing.md`.

## M6: Explore mode, Python package, RO-Crate

- **D²-law educational baseline** (classical quasi-steady theory). It is code-verified (24 checks,
  `python3 -I tools/verify_d2law.py`) but **not validated** against FLEX. In the app: Physics & Results →
  "Explore with a model". Its runs are simulations seeded from a test's printed conditions; they are never the
  test itself.
- **Python package**, no dependencies:
  - `python3 -m openflex info`
  - `python3 -m openflex test FLEX-035`
  - `python3 -m openflex baseline FLEX-035 --O2 0.15`
  - in code, `from openflex.data import DataPackage` gives hash-checked access to the data.
- **Share a run, check someone else's (M6.1).** After changing inputs in Explore you can save a run file or copy
  a post for a forum; anyone can re-run it in the app or with `python3 -m openflex check-run run.json`.
  **Reproduced** means the documented model gives the same numbers from the same inputs. It is not validation.
  See `docs/PHASE_B_M6_1_Sharing.md`.
- **Property table.** Only regenerating it needs CoolProp 8.0.0: `./tools/run_pipeline.sh --properties`.
- **RO-Crate 1.2.**
  - Rebuild: `python3 -I tools/build_rocrate.py .`
  - Validate: `python3 tools/validate_rocrate.py .` (rocrate-validator 0.13.1, profile ro-crate-1.2). The wrapper
    serves only the RO-Crate 1.2 JSON-LD context from a pinned copy when w3id.org is unreachable.
  - Online, `rocrate-validator validate -p ro-crate-1.2 .` gives the same checks.
- **No licence has been chosen for this repository yet**; the crate says so explicitly.

## Integration into Flame in Freefall

This package lives at `modules/open_flex/` in the flame-in-freefall repository. Changes made for that:

- **Deep link.** `dist/open_flex_lab.html#test=FLEX-035&tab=lab` opens that test in that workspace
  (`overview`, `lab`, `physics`, `uq`, `evidence`). Unknown values are ignored, never guessed
  (`app/src/js/90_main.js`, tests in `tests/browser/test_deeplink_browser.py`).
- **Build without the PDF.** If `sources/original/NASA-TP-2015-216046.pdf` is absent, `tools/build_app.py`
  records the registered SHA-256 from `SOURCE_CHECKSUMS.sha256` in the manifest (same value, so an
  unchanged build is byte-identical). Tests that read the PDF still need it.
- The host's server (`scripts/brain.py`) serves the built page at `/openflex/` and links PSI-69 tests to
  Table IX tests by CIR identifier (not by test number; PSI-69 numbering diverges from Table IX from FLEX-156).
- `docs/digitization/*.png` are tracked (a unit test and the app cite them; they need the PDF to regenerate).
