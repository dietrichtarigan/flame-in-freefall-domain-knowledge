// ---------------------------------------------------------------------------
// Open FLEX — views for the selected physical test record.
// Two independent statuses are shown wherever a value appears:
//   evidence class (where it came from) and computation (what was done to it).
// ---------------------------------------------------------------------------
OF.state = { testId: null, recordSha256: null };

OF.populateTestSelect = function () {
  var sel = document.getElementById("test-select");
  var groups = { methanol: [], heptane: [] };
  OF.D.table_ix.forEach(function (r) { groups[r.fuel].push(r); });
  sel.innerHTML = ["heptane", "methanol"].map(function (fuel) {
    return '<optgroup label="' + (fuel === "heptane" ? "n-Heptane" : "Methanol") + '">' + groups[fuel].map(function (r) {
      var p = r.P_mmHg === null ? "?" : (r.P_mmHg / 760).toFixed(2);
      var dil = r.X_CO2 > 0 ? " CO₂ " + r.X_CO2_raw : (r.X_He > 0 ? " He " + r.X_He_raw : "");
      return '<option value="' + r.flex_test + '">' + OF.esc(r.flex_test_as_printed) + " · " + p + " atm · O₂ " + OF.esc(r.X_O2_raw) + dil + " · D₀ " + OF.esc(r.D0_mm_raw) + " mm · " + OF.esc(r.test_end) + ((OF.D.digitized || {})[r.flex_test] ? " · digitized" : "") + "</option>";
    }).join("") + "</optgroup>";
  }).join("");
};

OF.selectTest = async function (id) {
  OF.state.testId = id;
  document.getElementById("test-select").value = id;
  var r = OF.testById[id];
  document.getElementById("hdr-test-id").textContent = r.flex_test_as_printed + " (" + r.cir_identifier + ")";
  document.getElementById("test-locator").innerHTML = "Source: [S01] NASA/TP-2015-216046, Table IX, printed p. " + OF.esc(r.printed_page) + " (PDF p. " + OF.esc(r.pdf_page) + "). Values shown exactly as printed.";
  OF.renderRecordTable(r);
  OF.renderMatrix(id);
  OF.renderFlags(id);
  OF.renderTimeSeriesStatus(id);
  OF.renderResultPanel(r);
  OF.renderDiagnostic();
  OF.renderBudget(r);
  if (OF.explore && OF.explore.on) OF.exploreSeed(id);
  if (OF.loadTimeline) { OF.loadTimeline(id); var rec0 = OF.recordFor(id); OF.timeline.fiber = !!(rec0 && rec0.fiber.status !== "DIFFERS" && /^Fiber-supported/.test(rec0.fiber.display)); OF.updateScene(); }
  if (document.getElementById("cov-form")) OF.renderCoverage(true);
  var rec = OF.exportableRecord(r);
  OF.state.recordSha256 = await OF.sha256Hex(OF.canonicalJSON(rec));
  var h = document.getElementById("hdr-sha256");
  if (OF.state.recordSha256) { h.textContent = OF.state.recordSha256.slice(0, 16) + "…"; h.title = OF.state.recordSha256 + " (SHA-256 of the canonical JSON of this test record)"; }
  else { h.textContent = "unavailable (Web Crypto SHA-256 not available in this context)"; h.title = ""; }
};

OF.renderRecordTable = function (r) {
  var d = OF.derived(r);
  var PUB = "Published (Table IX)", DER = "Derived here";
  var rows = [
    ["Test number (as printed)", r.flex_test_as_printed, PUB],
    ["CIR identifier", r.cir_identifier, PUB],
    ["Date (m/d/yy) • time GMT", r.date_mdy_as_printed + " • " + r.time_gmt, PUB],
    ["Fuel", r.fuel === "heptane" ? "n-heptane (C₇H₁₆)" : "methanol (CH₃OH)", PUB],
    ["Ambient pressure", r.P_mmHg_raw + " mmHg", PUB],
    ["Ambient pressure (÷ 760)", d.P_atm === null ? "—" : d.P_atm.toFixed(3) + " atm", DER],
    ["Mole fractions O₂ / N₂ / CO₂ / He", [r.X_O2_raw, r.X_N2_raw, r.X_CO2_raw, r.X_He_raw].join(" / "), PUB],
    ["Sum of the four printed mole fractions", d.composition_sum === null ? "—" : d.composition_sum.toFixed(2) + (Math.abs(d.composition_sum - 1) > 0.011 ? " (≠ 1; printed rounding — not normalized)" : ""), DER],
    ["D₀ at igniter ON (CLM-018)", OF.fmtRaw(r.D0_mm_raw) + (r.D0_mm_raw === "–" ? "" : " mm"), PUB],
    ["Visible-flame extinction diameter", OF.fmtRaw(r.D_ext_visible_mm_raw) + (r.D_ext_visible_mm_raw === "–" ? "" : " mm") + (r.D_ext_visible_mm_raw === "0" ? " (printed '0'; see DSC-011)" : ""), PUB],
    ["Burning rate K (CLM-019)", OF.fmtRaw(r.K_mm2_s_raw) + (r.K_mm2_s_raw === "–" ? "" : " mm²/s"), PUB],
    ["Burn time", OF.fmtRaw(r.t_burn_s_raw) + (r.t_burn_s_raw === "–" ? "" : " s"), PUB],
    ["Test end", r.test_end, PUB],
  ];
  var rec = OF.recordFor(r.flex_test);
  if (rec) {
    var fb = rec.fiber;
    rows.push(["Fiber support", fb.display + (fb.status === "DIFFERS" ? " — " + fb.evidence.join(" vs ") : ""),
      fb.status === "AGREE" ? "Published (test matrix + caption agree)" : fb.status === "CAPTION_ONLY" ? "Published (caption only)" : fb.status === "MATRIX_ONLY" ? "Published (test matrix only)" : fb.status === "DIFFERS" ? "Sources disagree" : "Unknown"]);
    if (rec.table_ix.extraction_check) rows.push(["Extraction check of this row", rec.table_ix.extraction_check.second_parser + "; " + rec.table_ix.extraction_check.page_image, "Verification (M2)"]);
  }
  document.getElementById("record-table").innerHTML = rows.map(function (x) {
    var c = x[2], prov = c.indexOf("Derived") === 0 ? 'data-derived="arithmetic on printed Table IX values"' :
      c.indexOf("Verification") === 0 ? 'data-source="data/verification (M2)"' :
      c.indexOf("Published (Table IX)") === 0 ? 'data-source="S01 Table IX p. ' + OF.esc(r.printed_page) + '"' : 'data-source="S01 Tables I–VIII / App. B captions"';
    return "<tr " + prov + "><td>" + OF.esc(x[0]) + '</td><td class="mono">' + OF.esc(x[1]) + "</td><td>" + OF.esc(x[2]) + "</td></tr>";
  }).join("");
};

// Test-matrix (Tables I–VIII) entry for the selected test, shown beside — never merged with — Table IX.
OF.renderMatrix = function (id) {
  var rec = OF.recordFor(id), el = document.getElementById("record-matrix");
  if (!el) return;
  if (!rec) { el.innerHTML = ""; return; }
  var tm = rec.test_matrix;
  if (!tm.present) {
    el.innerHTML = '<div class="alert-box alert-info" data-source="DSC-022"><strong>Test-matrix entry:</strong> ' + OF.esc(tm.absent_reason) + "</div>";
    return;
  }
  var diff = {};
  rec.crosscheck.forEach(function (c) { diff[c.field] = c; });
  var names = { D0_mm: ["D₀", "mm", "D0_mm"], P_atm: ["Pressure", "atm", "P"], X_O2: ["O₂", "", "X_O2"], X_CO2: ["CO₂", "", "X_CO2"], X_N2: ["N₂", "", "X_N2"] };
  var rows = Object.keys(names).filter(function (k) { return tm.values[k]; }).map(function (k) {
    var v = tm.values[k], n = names[k], d = diff[n[2]];
    var ixKey = { D0_mm: "D0_mm", P_atm: "P_mmHg", X_O2: "X_O2", X_CO2: "X_CO2", X_N2: "X_N2" }[k];
    var ix = rec.table_ix.present ? rec.table_ix.values[ixKey] : null;
    var cmp = !ix ? "not compared (no Table IX row)" : (ix.raw === "–" ? "not compared (Table IX prints –)" :
      (d ? '<span class="matrix-diff">differs from ' + OF.esc(d.other.split(" (")[0]) + " beyond printed rounding</span>" : "agrees within printed rounding"));
    return "<tr><td>" + n[0] + (v.origin === "table header" ? " <em>(table header)</em>" : "") + '</td><td class="mono">' + OF.esc(v.raw) + (n[1] ? " " + n[1] : "") +
      "</td><td>" + cmp + "</td></tr>";
  });
  if (diff.date) rows.push('<tr><td>Date</td><td class="mono">' + OF.esc(tm.date_as_printed) + '</td><td><span class="matrix-diff">differs from Table IX date</span></td></tr>');
  el.innerHTML = '<details class="matrix-box" open data-source="S01 ' + OF.esc(tm.source.locator) + '"><summary>Test-matrix entry (nominal conditions) — [S01] ' + OF.esc(tm.source.locator) + "</summary>" +
    '<p class="sub-note">Tables I–VIII give nominal/planned conditions and are a different table from Table IX. Differences are listed, not corrected (DSC-003, DSC-013).</p>' +
    '<table aria-label="Test-matrix entry for the selected test"><thead><tr><th>Quantity</th><th>As printed</th><th>Compared with Table IX</th></tr></thead><tbody>' + rows.join("") + "</tbody></table></details>";
};

OF.renderFlags = function (id) {
  var flags = OF.flagsFor(id), ann = OF.annotationFor(id), rec = OF.recordFor(id);
  var dscIds = rec ? rec.discrepancies : (ann.discrepancies || []);
  var html = '<div class="alert-box alert-warn"><strong>Data-quality notes</strong><ul style="margin:4px 0 0 16px;padding:0">' +
    flags.map(function (f) { return '<li data-claims="' + (f.claims || []).join(" ") + '"' + ((f.claims || []).length ? "" : ' data-source="S01 Table IX cell"') + ">" + OF.esc(f.text) + (f.claims && f.claims.length ? " [" + f.claims.map(OF.claimLink).join(", ") + "]" : "") + "</li>"; }).join("") +
    dscIds.map(function (did) { var d = OF.discById[did]; return '<li data-source="' + OF.esc(did) + '">Source discrepancy ' + OF.dscLink(did) + ": " + OF.esc(d.topic) + " — " + d.values.map(function (v) { return OF.esc(v.value) + " (" + OF.esc(v.source) + ")"; }).join("; ") + "</li>"; }).join("") +
    "</ul></div>";
  document.getElementById("record-flags").innerHTML = html;
  var lit = OF.literatureFor(id);
  document.getElementById("record-literature").innerHTML = lit.length ? '<div class="alert-box alert-info"><strong>Literature cases (candidate links only)</strong><ul style="margin:4px 0 0 16px;padding:0">' + lit.map(function (c) {
    var s = OF.sourceById[c.source.source_id];
    return '<li data-source="' + OF.esc(c.source.source_id) + ' (candidate)"><span class="mono">' + OF.esc(c.case_id) + "</span> — [" + OF.esc(c.source.source_id) + "] " + OF.esc(c.source.locator) + ": <em>" + OF.esc(c.linked_physical_test.status) + "</em>. " + OF.esc(c.linked_physical_test.basis) + (c.note ? " " + OF.esc(c.note) : "") + "</li>";
  }).join("") + "</ul></div>" : "";
};

OF.SERIES_STYLE = {   // dataviz palette slots 1–3 from the active theme (validated light on #fff, dark on the dark surface)
  droplet_d2: { slot: "s1", label: "Droplet diameter² (red markers in source)" },
  lluv_flame_diameter: { slot: "s2", label: "LLUV flame diameter (blue markers in source)" },
  color_camera_flame_diameter: { slot: "s3", label: "Colour-camera flame diameter (green markers in source)" }
};

OF.renderTimeSeriesStatus = function (id) {
  var fig = OF.D.figures[id], dig = (OF.D.digitized || {})[id];
  var badge = document.getElementById("plot-prov-badge");
  var src = fig ? "<strong>[S01] Appendix B, Figure " + fig.figure + "</strong>, printed p. " + OF.esc(fig.printed_page) + " (PDF p. " + OF.esc(fig.pdf_page) + ")" : "";
  var cap = fig ? '<p class="small" data-source="S01 App. B caption (verbatim)"><strong>Caption (verbatim, NASA authors\' observations):</strong> ' + OF.esc(fig.caption_verbatim) + "</p>" : "";
  if (!dig) {
    badge.className = "badge badge-danger"; badge.textContent = "UNAVAILABLE IN THIS BUILD";
    document.getElementById("timeseries-status").innerHTML =
      '<div class="alert-box alert-danger" style="margin-top:0" data-source="data/records time_series.status"><strong>Time series unavailable.</strong> No measured or digitized D²(t), LLUV or colour-camera flame-diameter series is loaded for this test, so none is plotted.</div>' +
      (fig ? '<p class="small" data-claims="CLM-040">The source shows this test as a plot: ' + src + ". The TP says the per-test data are also in a text file associated with the report (CLM-040); that file was not available. Only selected plots have been digitized (" + Object.keys(OF.D.digitized || {}).length + " tests; marked '· digitized' in the test list).</p>" + cap : "");
    return;
  }
  badge.className = "badge badge-warn"; badge.textContent = "DIGITIZED FROM SOURCE PLOT";
  var R = dig.record, A = dig.analysis;
  var html = '<div class="alert-box alert-warn" style="margin-top:0" data-claims="CLM-018 CLM-039"><strong>Digitized, not original data.</strong> Points were read from ' + src +
    " by marker detection on the embedded plot image (DIGITIZED). Overlapping markers are sampled, so points are not individual camera frames. Time zero = igniter energized (CLM-018).</div>" +
    '<div id="plot-digitized-d2" class="dig-plot" role="img" aria-label="Digitized droplet diameter squared versus time for ' + OF.esc(id) + '"></div>' +
    '<div id="plot-digitized-flame" class="dig-plot" role="img" aria-label="Digitized flame diameter versus time for ' + OF.esc(id) + '"></div>';
  if (A) {
    var o = A.outputs;
    html += '<div data-derived="' + OF.esc(A.run_id) + '"><h3 style="margin:10px 0 4px">Digitization check: D² slope vs printed K <span class="badge badge-scope">ANALYSIS · ' + OF.esc(A.run_id) + "</span></h3>" +
      '<p class="sub-note" style="margin-top:0">Linear fits of the digitized D² over pre-declared windows (fractions of the Table IX burn time). The spread is window/estimator sensitivity, <strong>not</strong> an uncertainty interval. These fitted values do not replace the printed K. Not a validation.</p>' +
      '<table aria-label="D squared fit results"><thead><tr><th>Window</th><th>t range, s</th><th>N points</th><th>K (OLS), mm²/s</th><th>K (Theil–Sen), mm²/s</th></tr></thead><tbody>' +
      o.fits.map(function (f) { return "<tr><td>" + f.window + '</td><td class="mono">' + f.t_start_s + "–" + f.t_end_s + '</td><td class="mono">' + f.n_points + '</td><td class="mono">' + f.K_ols_mm2_s.toFixed(3) + '</td><td class="mono">' + f.K_theil_sen_mm2_s.toFixed(3) + "</td></tr>"; }).join("") +
      "</tbody></table>" +
      '<p style="font-size:11.5px">Printed Table IX K: <span class="mono">' + OF.esc(o.table_ix_K_mm2_s.raw) + "</span> mm²/s — " + (o.table_ix_K_within_range ? "consistent with" : "<strong>not consistent with</strong>") +
      " the range of digitized fits (" + o.K_range_over_windows_and_estimators_mm2_s[0].toFixed(3) + "–" + o.K_range_over_windows_and_estimators_mm2_s[1].toFixed(3) + " mm²/s). Rule: " + OF.esc(o.within_range_rule || "printed value inside the range") + ".</p>" +
      (o.point_checks.length ? '<ul style="font-size:11.5px;margin:4px 0 0 16px;padding:0">' + o.point_checks.map(function (c) {
        var sup = function (x) { return OF.esc(x).replace(/\^2/g, "²"); };
        return "<li>" + sup(c.quantity) + ": Table IX " + sup(c.table_ix_value) + "; digitized " + (c.digitized_median_mm2 === null ? "— (" + OF.esc(c.note) + ")" : "median " + c.digitized_median_mm2.toFixed(2) + " mm² of " + c["n_points_within_0.2_s"] + " points within ±0.2 s") + "</li>";
      }).join("") + "</ul>" : "") + OF.analysisCard(A, id) + "</div>";
  }
  html += '<details style="margin-top:8px" data-source="digitization record ' + OF.esc(R.source_image.path) + '"><summary style="cursor:pointer;font-size:12px">How these points were digitized</summary><ul style="font-size:11px;margin:4px 0 0 16px;padding:0">' +
    "<li>Source image: " + OF.esc(R.source_image.path) + ", SHA-256 " + OF.esc(R.source_image.sha256.slice(0, 16)) + "… (" + OF.esc(R.source_image.extraction) + ")</li>" +
    "<li>Axis calibration from major tick marks; largest residual at the ticks (px): " + Object.keys(R.calibration_max_residual_px).map(function (k) { return k + " " + R.calibration_max_residual_px[k]; }).join(", ") + ". " + OF.esc(R.label_reading_note) + "</li>" +
    R.series.map(function (s) { return "<li>" + OF.esc(s.legend_text) + ": " + s.points + " points; self-check: " + Math.round(100 * s.self_check.recall_coloured_pixels_covered) + "% of coloured pixels explained, " + Math.round(100 * s.self_check.precision_redrawn_ring_pixels_coloured) + "% of redrawn rings on colour</li>"; }).join("") +
    "<li>Overlay image for visual inspection: " + OF.esc(R.overlay_image) + "</li>" +
    R.limitations.map(function (l) { return "<li><em>" + OF.esc(l) + "</em></li>"; }).join("") + "</ul></details>" + cap +
    '<details data-source="DIGITIZED datasets"><summary style="cursor:pointer;font-size:12px">Table view of digitized points</summary><div id="dig-table"></div></details>';
  document.getElementById("timeseries-status").innerHTML = html;
  OF.drawDigitized(id, dig);
};

OF.drawDigitized = function (id, dig) {
  var tbl = document.getElementById("dig-table");
  tbl.innerHTML = dig.series.map(function (s) {
    return '<p class="mono" style="font-size:10.5px;margin:6px 0 2px">' + OF.esc(s.dataset_id) + " (" + OF.esc(s.unit) + ")</p>" +
      '<table class="dig-tbl"><thead><tr><th>t, s</th><th>value</th></tr></thead><tbody>' +
      s.t.map(function (t, i) { return '<tr><td class="mono">' + t.toFixed(3) + '</td><td class="mono">' + s.v[i].toFixed(3) + "</td></tr>"; }).join("") + "</tbody></table>";
  }).join("");
  if (!OF.libStatus().plotly) {
    ["plot-digitized-d2", "plot-digitized-flame"].forEach(function (k) {
      document.getElementById(k).innerHTML = '<div class="alert-box alert-danger">Plot library unavailable — use the table view below.</div>';
    });
    return;
  }
  var tmin = Infinity, tmax = -Infinity;
  dig.series.forEach(function (s) { s.t.forEach(function (t) { tmin = Math.min(tmin, t); tmax = Math.max(tmax, t); }); });
  var xr = [Math.floor(tmin) - 0.5, Math.ceil(tmax) + 0.5];
  function trace(s) {
    var st = OF.SERIES_STYLE[s.name] || { slot: "s1", label: s.name }, B = OF.plotBase();
    return { x: s.t, y: s.v, mode: "markers", type: "scatter", name: st.label + " · DIGITIZED",
      marker: { color: B[st.slot], size: 8, line: { color: B.surface, width: 1 } },
      hovertemplate: "t = %{x:.2f} s<br>%{y:.2f} " + s.unit.replace("^2", "²") + "<extra>" + st.label + " · DIGITIZED</extra>" };
  }
  function layout(title, ytitle, showLegend) {
    var B = OF.plotBase();
    return { paper_bgcolor: B.paper_bgcolor, plot_bgcolor: B.plot_bgcolor, font: B.font,
      margin: { l: 56, r: 16, t: 34, b: showLegend ? 78 : 40 }, height: showLegend ? 300 : 260, hovermode: "closest",
      title: { text: title, font: { size: 11.5 }, x: 0, xanchor: "left" },
      xaxis: { title: "Time since igniter ON, s", range: xr, gridcolor: B.grid, zeroline: true, zerolinecolor: B.font.color },
      yaxis: { title: ytitle, gridcolor: B.grid, rangemode: "tozero" },
      showlegend: showLegend, legend: { orientation: "h", y: -0.32, yanchor: "top" } };
  }
  var d2 = dig.series.filter(function (s) { return s.name === "droplet_d2"; });
  var fl = dig.series.filter(function (s) { return s.name !== "droplet_d2"; });
  var A = dig.analysis, traces = d2.map(trace);
  Plotly.react("plot-digitized-d2", traces,
    layout(OF.esc(id) + " · droplet D² — DIGITIZED from Fig. " + OF.D.figures[id].figure, "D², mm²", false), { displayModeBar: false, responsive: true });
  Plotly.react("plot-digitized-flame", fl.map(trace),
    layout(OF.esc(id) + " · " + (fl.length === 1 ? (OF.SERIES_STYLE[fl[0].name] || {}).label.split(" (")[0] : "flame diameter") + " — DIGITIZED from Fig. " + OF.D.figures[id].figure, "Flame diameter, mm", fl.length > 1), { displayModeBar: false, responsive: true });
};


// Conceptual diagnostic view: FOV square to scale with a droplet of the printed
// D₀ drawn at the centre. No flame is drawn because no flame data are loaded.
// Adds provenance attributes to each <p> from the claim / discrepancy / section references it contains;
// paragraphs with none are tagged interpretive.
OF.tagParagraphs = function (html) {
  return html.replace(/<p>([\s\S]*?)<\/p>/g, function (all, inner) {
    var cl = inner.match(/CLM-\d{3}/g) || [], ds = inner.match(/DSC-\d{3}/g) || [], sec = inner.match(/§[\d.]+/g) || [];
    var attr = cl.length ? ' data-claims="' + cl.join(" ") + '"' : (ds.length || sec.length ? ' data-source="S01 ' + ds.concat(sec).join(" ") + '"' : ' data-interpretive="channel description"');
    return "<p" + attr + ">" + inner + "</p>";
  });
};

OF.CHANNELS = {
  hibms: { fov: 30.25, label: "HiBMs backlit view",
    html: "<p><strong>Measurand:</strong> projected droplet area → droplet size (dark droplet on light background). Also soot volume fraction for sooting flames (not reported in the TP).</p><p><strong>FOV:</strong> approx. 30 mm (§2.2); 30.25 mm on 1024 px (§3.1.2); scale factor 32.5 px/mm (§3.1.1) — inconsistent, see DSC-006.</p><p><strong>Reported estimate:</strong> ±50 µm on droplet size; coverage not stated (CLM-009).</p><p><strong>Limits:</strong> the flame itself is not imaged; droplets often drifted out of this FOV, ending or interrupting the record (CLM-017). Tests 001–009 used a 1/30 s shutter (CLM-026).</p>" },
  lluv: { fov: 57.8, label: "LLUV 310 nm",
    html: "<p><strong>Measurand:</strong> outer edge of OH* chemiluminescence at 310 nm (10 nm FWHM). Not the radius of peak temperature (CLM-013).</p><p><strong>FOV:</strong> approx. 50 mm (§2.2); 57.8 mm on 512 px binned (§3.2.2) — see DSC-007.</p><p><strong>Reported estimate:</strong> ±200 µm on flame size; coverage not stated (CLM-011).</p><p><strong>Limits:</strong> dim, noisy images; a smudged/damaged window caused asymmetries; no deconvolution performed (§3.0, §3.2.1).</p>" },
  colour: { fov: 93.2, label: "MDCA colour camera",
    html: "<p><strong>Measurand:</strong> outer edge of the visible flame. Typically about three-fourths of the LLUV diameter, less for sooting heptane flames (CLM-014). Not interchangeable with the LLUV edge.</p><p><strong>FOV:</strong> approx. 110 × 90 mm (§2.2); 93.2 mm wide on 640 px (§3.3.2) — see DSC-007.</p><p><strong>Reported estimate:</strong> ±250 µm on flame size; coverage not stated (CLM-012).</p>" },
  radiometer: { fov: null, label: "Radiometers",
    html: "<p>A broadband and an H₂O-filtered radiometer were installed. For the tests reported, they were not sensitive enough to provide reliable quantitative information, and the data are not reported (CLM-015). No radiometric values are shown or modelled here.</p>" }
};

OF.renderDiagnostic = function () {
  var ch = document.getElementById("cam-channel").value, C = OF.CHANNELS[ch];
  var canvas = document.getElementById("diag-canvas"), ctx = canvas.getContext("2d");
  var r = OF.testById[OF.state.testId];
  ctx.clearRect(0, 0, 240, 240);
  ctx.fillStyle = "#f3f4f6"; ctx.fillRect(0, 0, 240, 240);
  var extra = "";
  if (C.fov) {
    var px = 240 / C.fov;
    ctx.strokeStyle = "#6b7280"; ctx.strokeRect(0.5, 0.5, 239, 239);
    ctx.fillStyle = "#374151"; ctx.font = "10px monospace";
    ctx.fillText("FOV " + C.fov + " mm (one TP value)", 6, 14);
    if (r && r.D0_mm !== null) {
      ctx.fillStyle = "#1f2937"; ctx.beginPath(); ctx.arc(120, 120, Math.max(1, r.D0_mm / 2 * px), 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = "#374151"; ctx.fillText("droplet at Table IX D₀ = " + r.D0_mm_raw + " mm", 6, 232);
      extra = "<p class='sub-note'>Drawing: droplet circle of the printed D₀ at the stated FOV scale. No flame is drawn: no flame-size data are loaded.</p>";
    }
  } else {
    ctx.fillStyle = "#a61b1b"; ctx.font = "bold 12px sans-serif"; ctx.fillText("NO RADIOMETER DATA REPORTED", 22, 115);
    ctx.fillStyle = "#374151"; ctx.font = "11px sans-serif"; ctx.fillText("NASA/TP-2015-216046 §2.2, p. 4", 40, 135);
  }
  document.getElementById("cam-desc").innerHTML = "<strong>" + OF.esc(C.label) + "</strong>" + OF.tagParagraphs(C.html) + extra;
};
