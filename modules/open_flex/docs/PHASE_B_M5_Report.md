# Phase B — Milestone M5 report: data-driven 3D experiment and dashboard redesign

Project: Open FLEX (original FLEX only). Source: [S01] NASA/TP-2015-216046.
Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product; a NASA citation does not imply endorsement.

## 1. Objective

1. **Redesign (from the plan):** a light default theme, five workspaces, ARIA and keyboard support,
   reduced motion and an axe-core audit.
2. **3D apparatus (user request):** a "more proper" setup like the user's reference video. The video could
   not be opened from this environment. As the user chose, the layout follows the report's own figures:
   Fig. 3 (top view of the MDCA) and Fig. 4 (camera views).
3. **Flame behaviour (user request):** "make sure it follows the physics". As the user chose, the flame is
   driven by data only. About 10 more Appendix B plots were digitized so that more tests have a real flame
   size.

## 2. Files added or modified

| Area | Files |
|---|---|
| Timeline engine (new) | `app/src/js/35_timeline.js`: state of the droplet and flame at any time, from data, with the source of each value |
| 3D apparatus (rewritten) | `30_scene_build.js` (layout per Fig. 3, picking, frusta, camera views), `31_scene_update.js` (procedure stages plus real-time burn, readouts, instrument views, 2D fallback) |
| Redesign | `body.html` (5 workspaces), `styles.css` (light/dark variables), `90_main.js` (ARIA tabs, theme, real-time loop); theme-aware charts in `40_views.js`, `45_transparency.js`, `50_panels.js`; h3 headings in `41_hotspots.js` |
| Digitization | 11 new configs; `digitize_figure.py` 1.1.0 (threshold 0.30, `tick_pairs_as_read`, quality flags); `analyze_d2_fit.py` 1.1.0 (rounding-aware rule, windows with < 5 points not fitted); `data/digitization/overlay_review.json` |
| Registries | claims +CLM‑043…048 (48 total); discrepancies +DSC‑025, ‑026 (26 total); `datasets.spec.json` 0.5.0 (92 datasets) |
| Vendor | `vendor/test-only/axe-core-4.10.3` (MPL‑2.0; tests only, never inlined) |
| Tests | new `tests/browser/test_m5_browser.py` (14), `tests/unit/test_m5_data.py` (9); M1–M4 tests adapted to the new layout and 13 digitized tests |

## 3. Scientific justification: what "follows the physics" means here

No combustion model runs in this release, and making one up would break Phase B's rules. The physics shown
comes from measured data and from statements in the report, each with a source.

| Behaviour | Rule in the app | Basis |
|---|---|---|
| Spherical droplet and flame | All drawn as spheres; no buoyant plume | No buoyant convection in microgravity (CLM‑016, CLM‑043) |
| Droplet becomes round after deployment | Shown spherical from deployment | Spherical within ≈1 s (CLM‑044) |
| Time zero | Igniters ON at t = 0 | App. A.1 (CLM‑018) |
| Droplet shrinking, 13 digitized tests | Digitized D²(t): running median ±0.25 s; detection gaps ≤ 0.75 s each side interpolated and labelled; longer gaps stay gaps | App. B plots, DIGITIZED |
| Droplet shrinking, other tests | D² = D₀² − K·t to the printed burn time, from printed D₀ and K | The report's own linear-fit definition of K (CLM‑019); labelled RECONSTRUCTED |
| End of burn | At the printed burn time: Extinction → flame off; Completion → droplet 0; Disruption → droplet removed | Table IX; burn-time definition not given (DSC‑024) |
| Flame size | Only from digitized flame data. Visible edge from the colour camera; LLUV (OH*) edge as a separate ring. No data → an unscaled "?" marker | CLM‑013, ‑014, ‑046 |
| Soot | Drawn inside the blue envelope, with no radius claimed, only when the caption reports soot or luminosity; switched off when the caption says it ended (e.g. "halfway") | CLM‑045; caption keywords (DERIVED) |
| Cool flame | Shown as an event note only, not drawn | Caption inference (FLEX‑035) |
| Dark chamber during the burn | Dark scene from "start recording" on; lighter while the LED is on during droplet formation | CLM‑048 |
| Instrument views | HiBMs: backlit silhouette with no flame. LLUV: OH* edge only, no droplet. Colour camera: visible flame | CLM‑047, CLM‑013 |
| Real time | 1 s of playback = 1 s of test time at 1× speed (0.25×–4× selectable) | — |

Things the app says it does not know: droplet drift (not shown), the igniter on-time (the 0.5 s is labelled
illustrative), the colour camera's position (not in Fig. 3, labelled conceptual), and post-extinction
vaporization for reconstructed tests (frozen and labelled).

**Classical quasi-steady droplet theory was not used for flame size.** It predicts flames several times
larger than FLEX measured, so it would not have followed the physics.

## 4. The 3D apparatus

- **True scale.** Everything is in millimetres. The droplet and flame are at true size, as are:
  - the needles (0.25 mm OD, CLM‑005);
  - the fiber (80 µm, CLM‑007);
  - the igniter loops, about 10 mm from the droplet (approximate, read from Fig. 4(c));
  - the camera fields of view: HiBMs 30.25 mm, LLUV 57.8 mm, colour 93.2 × 76.3 mm (DSC‑006/007).

  A 10 mm scale bar is shown close up.
- **Layout from Fig. 3.**
  - The chamber is an octagon, with LLUV in the upper-left corner, HiBMs upper-right, and the
    "LED light source" lower-left. The report's text conflicts with that LED label (DSC‑026).
  - The needles face each other along one axis; the igniters are 180° apart on the diagonal (CLM‑006).
  - The fiber holder is at the top, and the syringe and deployment motor are on the right.

  Hardware sizes are a sketch, and the view says so ("not CAD").
- **Fiber.** It is shown only when the test matrix and/or caption say the test was fiber-supported, and not
  when the two disagree (FLEX‑053, FLEX‑124).
- **Procedure.** The 13 steps of TP §2.3: needles together, then stretched, then retracted at deployment;
  igniters glow at t = 0, then retract. Steps before deployment are not to time scale, and the page says so.
- **Interaction.**
  - Clicking a part opens its component card (raycaster picking). The keyboard list of components gives
    the same access without the mouse.
  - Ten view presets, including "as HiBMs / LLUV / colour camera", whose angle of view frames that
    camera's field (tested: HiBMs frames exactly 30.25 mm).
  - Chamber and field-of-view toggles.
- **Readouts** beside the view give the droplet diameter, flame diameter, LLUV edge and appearance, each with
  its source, plus a "how this playback is driven" list for the selected test.
- **Without WebGL or Three.js**, a 2D fallback shows the Fig. 3 layout and a to-scale 40 mm inset of the
  droplet and flame.

## 5. Digitization, 11 more tests (13 in total)

**Tests chosen.** The 11 new tests span the conditions:

| Condition | Tests |
|---|---|
| Methanol and heptane in air | FLEX‑033, ‑049 |
| Near-limit O₂ | FLEX‑082 (0.13) |
| CO₂ dilution at 3 atm | FLEX‑010 |
| CO₂ dilution at 0.7 atm | FLEX‑110 |
| Heptane with CO₂ | FLEX‑198 |
| Helium dilution | FLEX‑263, ‑264 |
| Fiber-supported, burned to completion | FLEX‑051 |
| Literature-candidate tests | FLEX‑062, ‑204 |

**Method change, recorded as version 1.1.0.**
- *Problem:* with the M3 threshold (40% of the legend-marker score), many isolated LLUV markers in FLEX‑110
  scored just below the cut. Legend markers render crisper than data markers.
- *Change:* the threshold was lowered to 30% and all 13 figures were rerun, including the M3 pair.
- *Effect:* recall rose to 0.88–0.96 on every series.
- *Flag:* one series, FLEX‑263 LLUV (precision 0.70), is flagged because its markers sit under the
  colour-camera markers.
- *Review:* every overlay was inspected visually, and the review is recorded.

**Calibration.** The largest calibration residual on any axis is 0.45 px. Six axes needed an explicit
tick-length threshold. On three, data markers hide some tick marks, so tick and value pairs read from the
image are snapped to detected ticks (`tick_pairs_as_read`).

**Check against the printed K.** 12 of 13 tests are consistent. Two disclosed changes:
- **Rule refined.** The printed value's rounding interval must overlap the fitted range. Version 1.0.0
  compared the bare printed number; that failed FLEX‑198, whose range of 0.470–0.490 lies inside .49's
  rounding interval. The change is disclosed rather than hidden.
- **FLEX‑051 is not consistent.** The printed K is .65 and the fits give 0.68–0.79. The plotted D² is flat
  for about 1.5 s, drops steeply, then falls with steps; the caption reports fiber oscillations. Logged as
  **DSC‑025**. I did not choose a window after the fact to match the printed value.

## 6. Redesign and accessibility

- **Five workspaces:**
  - **Overview:** scope, counts and entry points.
  - **Experiment:** 3D view, timeline, readouts, components and diagnostics.
  - **Physics & Results:** record, test matrix, result cards, time series, target formulation and
    schematic.
  - **Uncertainty & Validation:** budget, removed items, coverage and label policy.
  - **Evidence & Reproducibility:** ledger, sources, discrepancies, manifest and export.
- **Header.** The test selector lives in the header, so it applies everywhere; digitized tests are marked
  "· digitized" in the list.
- **Theme and keyboard.**
  - Light by default, dark on request; the choice is remembered in this browser if storage works.
  - Tabs follow the WAI‑ARIA pattern: arrow keys, Home and End.
  - A skip link and visible focus outlines are present.
  - Scrollable tables can be reached by keyboard.
- **Charts.** The palette was validated with the dataviz validator: all checks pass in both themes. The
  aqua series is under 3:1 contrast on white, which is why every chart has a legend and a table view.
- **Reduced motion.** It disables animations; nothing auto-plays.

## 7. Tests performed and results

| Suite | Tests | Result |
|---|---|---|
| M1–M4 (adapted to the new layout and to 13 digitized tests; no check weakened) | 98 | pass |
| M5 data: claim phrases for CLM‑041 and ‑043…048 found on the cited PDF pages, with matching printed page numbers; DSC‑025/026; all 13 records at method 1.1.0 and reviewed; exactly one flagged series | 9 | pass |
| M5 browser: | 14 | pass |
| • timeline rules checked for all 276 tests: D² = D₀² − K t, monotone shrinking, flame only within [0, t_b], no flame size without data, test-end behaviour; for the 13 digitized tests, droplet and flame values identical to a Python re-implementation | | |
| • the scene follows the timeline (droplet and flame at true size, marker only without data, soot, fiber); flame gone after extinction | | |
| • fiber shown only when the sources agree; instrument views | | |
| • raycast picking by mouse click; keyboard tabs and component list | | |
| • axe-core: zero violations in all five workspaces, light and dark (WCAG 2.1 A/AA plus best practice) | | |
| • no horizontal overflow at 390, 1024 and 1440 px (screenshots in `docs/screens/m5_*`) | | |
| • real-time playback (1 s = 1 s; 4× works); reduced motion; caption-driven soot timing; 2D fallback without Three.js | | |
| Full suite | **130** | **130 passed** |

**Fresh-copy check.** I deleted all built HTML, digitized data, records, analyses and the manifest from a
copy of the repository, then ran `setup_and_test.sh`. Everything was rebuilt from the PDF, every file came
out byte-identical, and all 130 tests passed.

**What these tests do not cover.**
- WebGL ran in software (SwiftShader) in headless Chrome. No real GPU, phone, Safari or Firefox was tested.
- No screen-reader session was run; axe checks rules, not the experience.

## 8. Remaining limitations

- **Reference video.** I could not see it, so the look follows the NASA figures. Your screenshots could
  refine it.
- **Flame size.** It is real for 13 of 276 tests; the others show an unscaled marker. Their droplet history
  is a straight-line D² reconstruction, which cannot show the early non-linear behaviour seen in, for
  example, FLEX‑051.
- **Hardware geometry.** It is a sketch: no CAD or dimensions are in the report. The igniter distance is
  approximate, and the colour camera's position is conceptual.
- **Drift.** Droplet drift and the off-centre position seen in some tests are not shown.
- **Soot timing.** It is taken from caption wording, so only "quarter, third, halfway…" phrases are parsed.
- **Review.** All digitization reviews and label readings are mine, not an independent person's.
- **Display smoothing.** It is a display choice; the raw points are in the plots and tables.
- **Page size.** The page is now 6.0 MB.

## 9. Known unresolved issues

- **New:** DSC‑025 (FLEX‑051 K) and DSC‑026 (LED label).
- **Earlier:** DSC‑010, 014–017, 021, 023 and 024 remain open.

## 10. Next

M6, the final step:
- a validated RO-Crate 1.2 export (checked with `roc-validator`);
- the D²-law educational baseline, with code-verification tests, which enables Explore mode;
- the Python science scaffold and V&V plan;
- after that, adding the user's extra data (per-test NASA data files, Dietrich et al. 2014), as agreed.
