# Phase B — Milestone M2 report: data architecture

Project: Open FLEX (original FLEX only). Source: [S01] NASA/TP-2015-216046 (SHA-256 `b4f6ca98…c471e79d`).
Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product; a NASA citation does not imply endorsement.

## 1. Objective

Give every data value a typed record with source, locator, evidence class and processing history; add the
fiber and nominal-condition information from the test-matrix tables; check the Table IX extraction cell by
cell against the PDF; and extend the discrepancy register with what those checks find. No values are
corrected, merged or invented.

## 2. Files added or modified

| Area | Files |
|---|---|
| Schemas (new) | `schemas/common`, `source`, `claim`, `discrepancy`, `physical_test`, `literature_figure_case`, `dataset`, `analysis_run`, `simulation_run` (`.schema.json`, JSON Schema 2020-12) |
| Extraction (new) | `tools/extract_test_matrix.py` → `data/extracted/test_matrix.csv` (Tables I–VIII, 153 rows) |
| Cross-checks (new) | `tools/crosscheck_tables.py` → `data/derived/crosscheck_matrix_vs_ix.csv`, `data/derived/fiber_from_captions.csv` |
| Verification (new) | `tools/verify_table_ix.py`, `tools/verify_test_matrix.py`, `tools/row_crops.py` → `data/verification/*`; montages in `docs/verification/` |
| Records (new) | `tools/build_records.py` → `data/records/physical_tests.json` (277); `data/records/literature_cases.json` (8) |
| Manifest | `data/datasets.spec.json` (new, hand-authored metadata); `tools/build_app.py` now writes `data/MANIFEST.json` as 14 Dataset records |
| Validation (new) | `tools/validate_data.py`; `tools/run_pipeline.sh`; `requirements.txt` |
| Registries | `claims.json` 0.2.0 (+CLM-035…038; CLM-029 status normalised); `discrepancies.json` 0.2.0 (+DSC-013…022, `tests` field) |
| App | `20_data.js`, `40_views.js`, `50_panels.js`, `90_main.js`, `body.html`, `styles.css` |
| Tests (new) | `tests/unit/test_m2_data.py` (14), `tests/browser/test_m2_browser.py` (10) |

## 3. Scientific justification

* **Two tables, two meanings.** Tables I–VIII are the test matrix (nominal conditions, fiber yes/no);
  Table IX is the results table with reconstructed composition and D₀ at igniter ON (App. A.1, CLM-018).
  They are stored and displayed side by side and never merged. Where they differ beyond printed rounding
  the difference is listed, with no judgement about which is right.
* **Fiber status** is printed in Tables III–VII, stated in the headers of Tables I, II and VIII (CLM-035), and
  described in every Appendix B caption (CLM-036). It is not in Table IX (DSC-012). Both places are
  reported; the record says whether they agree.
* **Identity separation.** The schemas give physical tests (`FLEX-nnn`), literature figure cases
  (`LIT-…`), analysis runs (`ANA-…`), simulation runs (`SIM-…`) and datasets (`DS-…`) separate ID
  patterns. A simulation run may cite the test whose printed conditions seeded it, but must list every
  modified input and can never use the test ID as its own identity (enforced by schema and validator).
* **Uncertainty.** The common schema allows an uncertainty statement only with explicit `coverage_factor`
  and `distribution` fields, which must say "not stated" / "not specified" unless the source states them.

## 4. Technical changes

1. **Test-matrix extraction.** Tables I–VIII: 153 tests (FLEX–001 to –166, missing 072, 131–139, 144–146).
   Each cell is verbatim (`*_raw`) plus parsed. Header constants carry `origin = "table header"`.
2. **Cross-check** (DERIVED; rule: agreement within half a unit of each printed last digit):
   * fiber: 150 agree, **2 differ** (FLEX–053, FLEX–124);
   * date: 3 differ (FLEX–054, –069, –114);
   * D₀: 127 of 145 differ (Table IX smaller in 131/145, median −0.07 mm). FLEX–070 differs by +3.37 mm;
   * composition: O₂ 14, N₂ 11, CO₂ 4 differ; P: 3 differ (including FLEX–114 printed as 0 mmHg);
   * the 276 captions classify cleanly: 212 free-floating, 64 fiber-supported, 0 ambiguous.
3. **Additional scans of Table IX.** Duplicate identity: FLEX–070 and –073 share CIR ID `193F001`, date
   and GMT time. FLEX–114 and –118 share date and time. Six rows have mole fractions summing to 0.98.
4. **Discrepancy register** extended with DSC-013…022 (D₀ meaning; FLEX–053 and –124 fiber; FLEX–070/073
   identity; FLEX–114 date; matrix dates; FLEX–162–165 composition; small differences; sums ≠ 1; matrix
   coverage). Each new entry names its tests and the tool that found it; `preferred` stays null.
5. **Records.** 277 PhysicalTest records (276 Table IX tests + FLEX–156, which appears only in the
   matrix). Each holds Table IX values, matrix values, fiber status with evidence, the Appendix B caption,
   flags, discrepancies, the cross-check differences, the extraction-check result, and
   `time_series.status = UNAVAILABLE`.
6. **Literature cases.** The eight M1 candidate links became LiteratureFigureCase records with
   `conditions.status = ATTRIBUTED_NOT_CHECKED` and link status CANDIDATE.
7. **Dataset manifest.** 14 Dataset records (ID, semantic version, class, origin, method, inputs, processing
   history, row count, SHA-256, limitations). Original, extracted, derived, verification, registry and record
   data are separate datasets.
8. **App.** The record table shows fiber status and the extraction check for the row. A collapsible
   "Test-matrix entry" box shows the matrix values with "agrees / differs / not compared" per value. The
   discrepancy list now comes from the record. Literature cases come from the new records. The Evidence tab
   has a Dataset Manifest table. The export record gains `record_schema_version`, `fiber`, `test_matrix` and
   `discrepancies`, and is still labelled "not an RO-Crate".

## 5. Verification of the Table IX extraction

| Route | What it compares | Result |
|---|---|---|
| A (M1 extractor) | pdftotext -layout | 276 rows × 15 cells |
| B second parser | pdfplumber word boxes (independent code path, same text layer) | **4140/4140 cells match** |
| C page image | 300-dpi rendering; Tesseract digits + connected-component layout (decimal point/dash) | 3972 match; 88 match allowing O/0 or dash-glyph equivalence; 80 disagree |
| Visual review | 80 crops viewed (`docs/verification/*.png`) | **80/80 CSV matches image** |

Tesseract alone dropped leading decimal points (".21" → "21") in about a quarter of the cells. That is why
route C reads the layout separately. Every check is recorded per cell in
`data/verification/table_ix_cell_checks.csv`.

Test matrix: route B 153/153 rows match; all 8 header phrases found. In addition, 10 matrix rows and their
Table IX rows were checked by eye on page crops: FLEX–053, 054, 069, 070, 073, 114, 124, 157, 162 and 165.

## 6. Tests performed and results

| Suite | Tests | Result |
|---|---|---|
| M1 browser (unchanged) | 12 | pass |
| M1 unit (extractors) | 2 | pass |
| M2 unit: reproducible test-matrix extraction, cross-check and records (byte-identical rerun); known cells; record content; validator passes and **fails on 4 injected errors** (unknown claim ID, FLEX ID on a literature case, edited CSV, invalid evidence class); verification completeness; all schemas valid 2020-12 | 14 | pass |
| M2 browser (offline, headless Chrome): fiber display for 5 tests including both conflicts; matrix box FLEX–023; "not compared" when Table IX prints –; FLEX–200 no matrix entry; DSC-016 on FLEX–070; literature cases shown as CANDIDATE; manifest table SHA-256 equals file hashes; export contains fiber/matrix/discrepancies | 10 | pass |
| **Total** | **38** | **38 passed** |

`setup_and_test.sh` was also run on a fresh copy of the repository. It ran the whole pipeline and 38/38
tests passed. The rebuilt HTML and CSVs were byte-identical to the committed files.

What these tests do not show: they check data handling and display, not the scientific correctness of
NASA's printed values. No validation (comparison of a model with experiment) has been done; none is
claimed.

## 7. Remaining limitations

* The visual review of the 80 disagreeing cells was done by me, the AI assistant, not by an independent
  human. Letter O versus digit 0 in CIR identifiers cannot be decided by eye at this resolution, so that
  rests on the PDF text layer.
* Route C reads the same page rendering that the text layer produced. It confirms that what is drawn matches
  the CSV; it cannot detect errors NASA made when typesetting the table.
* The test-matrix extraction was checked by a second text-layer parser, plus 10 rows by eye. It was not
  checked cell by cell against images as Table IX was.
* The literature-case conditions are still as attributed by the original prototype. Only the k values for
  FIG6 are supported by the Dietrich et al. (2014) abstract.
* The analysis/simulation-run schemas exist but no runs exist yet (M3 and M6 will create the first ones).
* The page bundle grew from 4.8 to 5.7 MB because the records repeat Table IX values. This is acceptable
  for now; trimming is a candidate for M5.

## 8. Known unresolved issues (new in M2)

* **FLEX–070 / –073 (DSC-016).** The two Table IX rows share one identity. The FLEX–070 Table IX values
  (D₀ 4.67 mm) conflict with the matrix (1.30 mm), and its caption says the colour camera recorded nothing
  after deployment. This should be checked against the electronic data files or with the authors.
* **FLEX–114 (DSC-010, DSC-017).** Pressure is printed as 0, and the date and time duplicate FLEX–118's.
* **FLEX–053 and FLEX–124 fiber (DSC-014/015).** Two parts of the TP disagree.
* **Composition sums of 0.98 (DSC-021)** and the unprinted H₂O and fuel-vapour columns (DSC-012).

## 9. Next

M3: digitize Appendix B Fig. 27 (FLEX–023) and Fig. 39 (FLEX–035) as DIGITIZED datasets, with a
calibration record, an overlay check, and an AnalysisRun for the D² fit compared with Table IX K (a
digitization check, not a validation).
