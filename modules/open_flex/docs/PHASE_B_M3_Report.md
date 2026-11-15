# Phase B — Milestone M3 report: pilot digitization of two Appendix B plots (+ M2 carry-over)

Project: Open FLEX (original FLEX only). Source: [S01] NASA/TP-2015-216046 (SHA-256 `b4f6ca98…c471e79d`).
Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product; a NASA citation does not imply endorsement.

## 1. Objective

Recover droplet and flame time series for two tests from the report's raster plots, as **DIGITIZED** data with
a complete, reproducible record of how they were read:
- FLEX‑023: Appendix B Fig. 27, PDF p. 57;
- FLEX‑035: Appendix B Fig. 39, PDF p. 69.

Check the digitization against values NASA printed. All other tests keep showing "time series unavailable".

The M2 carry-over was a cell-by-cell page-image check of the test-matrix tables (Tables I–VIII).

## 2. Files added or modified

| Area | Files |
|---|---|
| Digitizer (new) | `tools/digitize_figure.py`; configs `data/digitization/configs/FIG027_FLEX-023.json`, `FIG039_FLEX-035.json` |
| Source images (new, ORIGINAL) | `data/digitization/source_images/*.jpg`: the embedded JPEGs, byte for byte |
| Digitized data (new) | `data/digitized/FLEX-023_fig027_{droplet_d2,lluv_flame_diameter}.csv`, `data/digitized/FLEX-035_fig039_{droplet_d2,lluv_flame_diameter,color_camera_flame_diameter}.csv` |
| Digitization records (new) | `data/digitization/*_record.json`; overlays in `docs/digitization/*_overlay.png` |
| Analysis (new) | `tools/analyze_d2_fit.py` → `data/analysis/FLEX-023_d2_fit.json` (ANA‑6da345abdab7), `FLEX-035_d2_fit.json` (ANA‑e100eb2bc4d5) |
| Schemas | new `digitization_record.schema.json`; `dataset.schema.json` gains `test_id`, `series`, `unit`, `digitization_record` and class `ANALYSIS` |
| M2 carry-over (new) | `tools/verify_test_matrix_images.py` → `data/verification/test_matrix_cell_checks.csv`, `test_matrix_image_summary.json`, `test_matrix_manual_review.json`; montage `docs/verification/test_matrix_ocr_disagreements_review.png` |
| Registries | `claims.json` 0.3.0 (+CLM‑039, ‑040); `discrepancies.json` 0.3.0 (+DSC‑023); `datasets.spec.json` 0.3.0 (27 datasets) |
| Pipeline/validation | `run_pipeline.sh` (digitize → analyze added; `--verify` also checks the matrix images); `validate_data.py` (digitization records, analysis runs, image/config hashes, row counts) |
| App | `40_views.js` (digitized panel, two charts, fit table, table view, no-library fallback), `styles.css`; `build_app.py` bundles digitized series and analyses |
| Tests (new) | `tests/unit/test_m3_digitization.py` (12), `tests/browser/test_m3_browser.py` (4); 2 earlier assertions updated for the pilot |

## 3. Scientific justification

- **Why digitize?** The report says per-test text data files exist (CLM‑040), but they were not available. The
  plots are the only route to time series, and Phase B allows digitized data only when labelled and
  documented. Every digitized value carries the class DIGITIZED and is never presented as a measurement.
- **What the plots show.** Droplet diameter squared (red), LLUV flame diameter (blue) and, for FLEX‑035,
  colour-camera flame diameter (green), against time from the igniter ON (CLM‑039, CLM‑018). The digitized
  series keep that time zero.
- **The check is a consistency check, not validation.** Fitting a straight line to the digitized D² and
  comparing the slope with Table IX's K only tests whether the digitization reproduces what NASA computed
  from its own data. It says nothing about any model.
- **No intervals.** Overlapping markers mean the digitized points are not independent observations: the
  residuals are autocorrelated (lag‑1 up to 0.29 and down to −0.34). Standard errors or confidence
  intervals would therefore be wrong, and none are reported. The spread over pre-declared fit windows is
  shown and explicitly labelled as window sensitivity.

## 4. Method (fully recorded in each digitization record)

1. **Source image.** `pdfimages -j` copies the embedded JPEG unchanged. Its SHA‑256 is recorded, and a test
   re-extracts it and compares the hash.
2. **Axis calibration.** Major tick marks are found automatically as the longest inward dark runs next to the
   frame. For Fig. 39 the length threshold is set explicitly, because 5‑s intermediate ticks are almost as
   long. The ticks are paired with tick-label values I typed from the image, and a straight line is fitted
   per axis. The run fails if the tick and label counts differ (tested).
3. **Marker detection.** A per-colour score is correlated with a ring template of the measured marker
   radius (5.5 px). Peaks at least 4 px apart and scoring at least 40% of the legend marker are kept.
   Up to three passes are made, each blanking pixels already explained by detected rings. The legend
   region is excluded.
4. **Self-check.** Rings are redrawn at the detected centres. Recall is the share of coloured pixels
   covered by a ring; precision is the share of ring pixels that are coloured. An overlay image is saved for
   visual inspection, and I inspected both overlays.

## 5. Results

**Calibration and detection**

| Test / series | Points | Recall | Precision | Largest calibration residual (px), x / left / right |
|---|---|---|---|---|
| FLEX‑023 D² | 132 | 0.90 | 0.93 | 0.39 / 0.19 / 0.41 |
| FLEX‑023 LLUV flame | 269 | 0.92 | 0.92 | (same figure) |
| FLEX‑035 D² | 161 | 0.92 | 0.97 | 0.20 / 0.38 / 0.30 |
| FLEX‑035 LLUV flame | 91 | 0.89 | 0.87 | (same figure) |
| FLEX‑035 colour flame | 89 | 0.90 | 0.94 | (same figure) |

One marker radius corresponds to about 0.05 s in time on Fig. 27 (0.20 s on Fig. 39) and about 0.08 mm² on
the D² axis. This is a scale statement only, not a claimed uncertainty.

**Digitization check against Table IX**

| Test | Printed K (mm²/s) | Digitized slopes over 4 windows × 2 estimators | Printed K inside the range? |
|---|---|---|---|
| FLEX‑035 | .43 | 0.425 – 0.431 | yes |
| FLEX‑023 | .73 | 0.662 – 0.754 | yes |

For FLEX‑023 the low end (0.662) comes from window W1. W1 runs to the printed burn time (13.1 s) and so
includes a D² plateau visible from about 11.3 s.

Point checks:

- **FLEX‑035, start.** Digitized D² near t = 0 is 14.59 mm² (4 points). Table IX D₀ = 3.85 mm gives
  14.82 mm².
- **FLEX‑035, extinction.** Digitized D² near t_b = 8.9 s is 11.11 mm² (2 points). Table IX
  D_ext = 3.34 mm gives 11.16 mm².
- **FLEX‑023, start.** No digitized point lies within ±0.2 s of t = 0. Here the plot's early D² values
  (≈ 9.2–11 mm², several clipped at the top of the axis) do not obviously match the printed
  D₀² = 9.06 mm². This is logged as **DSC‑023**; I did not choose between them.

**M2 carry-over: test-matrix tables against page images**

- 1432 cells were checked: 1407 matched automatically and 25 disagreed.
- All 25 disagreements are in the last row of a table (FLEX‑009, ‑018, ‑130, ‑166), where the table's
  bottom rule falls inside the crop.
- I reviewed all 25 visually, and every one matches the CSV (`test_matrix_manual_review.json`).
- Both extracted tables have now been checked cell by cell against page images.

## 6. App changes

- **FLEX‑023 and FLEX‑035.** The time-series panel now reads "DIGITIZED FROM SOURCE PLOT". It shows a
  warning box, and has two separate charts: D² and flame diameter, deliberately not one dual-axis chart.
  - The colours come from the validated palette; all checks pass on the app's dark panel colour.
  - Hover labels say DIGITIZED.
  - Below the charts are the fit table with its "not an uncertainty interval / not a validation" wording, the
    point checks, a collapsible digitization method (hashes, calibration residuals, self-check,
    limitations), and a table view of every point.
- **All other tests** still say "Time series unavailable".
- **Without the plotting library**, the charts are replaced by a message, and the table view still works
  (tested offline).

## 7. Tests performed and results

| Suite | Tests | Result |
|---|---|---|
| M1 + M2 (two assertions updated for the pilot) | 38 | pass |
| M3 unit: source-image hash equals a fresh `pdfimages` extraction (×2); calibration < 1 px and self-check ≥ 0.85 (×2); digitization byte-identical on rerun; tick/label mismatch fails; analysis semantics (no SE/CI/p-value/"validated", inputs hash-linked to the manifest, printed K inside the range) (×2); only the pilot tests marked DIGITIZED, DSC‑023 linked; validator rejects a dropped CSV row and an edited config; test-matrix image review complete | 12 | pass |
| M3 browser (offline, headless Chrome): panel for FLEX‑023/035 (labels, two charts, no second y-axis, plotted point count equals the CSV, table view complete); three other tests unavailable; charts fall back to the table without Plotly | 4 | pass |
| **Total** | **54** | **54 passed** |

**Fresh-copy check.** I deleted all digitized data, digitization records and analyses from a copy of the
repository, then ran `setup_and_test.sh`. It rebuilt everything from the PDF, and every data file and the
HTML came out byte-identical to the committed versions. All 54 tests passed.

## 8. Remaining limitations

- **Dense trails.** Where markers overlap heavily, detected centres sample the trail. The number of camera
  frames and their exact times cannot be recovered, and markers fully hidden under others are missed.
  Recall is 0.87–0.92, so not every coloured pixel is explained.
- **Clipped markers** at the top of the axis, partly outside the plot range, are mostly missed. This
  affects the early-time part of FLEX‑023.
- **Tick labels** were typed by me from the image, and the visual inspection of the overlays and crops was
  also mine, not an independent person's.
- **Fit windows.** The windows are tied to the printed burn time, and NASA's actual window is not reported.
  The ranges shown are not uncertainty statements.
- **Only two of 276 plots** are digitized (as approved for the pilot). The method generalizes, but each
  figure needs its own config (tick labels, legend box), a visual overlay check and, for some figures, an
  explicit tick-length threshold.

## 9. Known unresolved issues

- **DSC‑023:** FLEX‑023 Table IX D₀ vs the plotted early D² (new).
- All M2 issues remain open: FLEX‑070/073 shared identity, FLEX‑114, the fiber conflicts and the composition
  sums.
- If NASA's per-test text files become available, they should replace these digitized series. The digitized
  versions would then serve only as a check of the digitizer.

## 10. Next

M4: uncertainty transparency and the claim ledger in the app, and domain status from Table IX coverage.
