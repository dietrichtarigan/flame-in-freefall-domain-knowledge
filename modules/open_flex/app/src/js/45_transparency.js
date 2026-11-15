// ---------------------------------------------------------------------------
// Open FLEX — transparency layer (Phase B M4).
//   * result cards (Ground-Truth Brief §6.1 fields) for every quantitative result
//   * uncertainty budget from data/registry/uncertainty_components.json
//   * condition coverage ("domain status") of Table IX — port of tools/coverage.py
//   * claim / source / discrepancy links that navigate to the Evidence tab
// Provenance attributes: every element that states a fact carries one of
//   data-claims="CLM-…", data-source="…", data-derived="…", data-interpretive="…"
// (checked by tests/browser/test_m4_browser.py).
// ---------------------------------------------------------------------------

// ---- links -------------------------------------------------------------------
OF.claimLink = function (id) {
  var c = OF.claimById[id];
  return '<a href="#clm-' + OF.esc(id) + '" class="mono ev-link" data-goto="clm-' + OF.esc(id) + '" title="' + OF.esc(c ? c.claim_text : "unknown claim") + '">' + OF.esc(id) + "</a>";
};
OF.dscLink = function (id) {
  var d = OF.discById[id];
  return '<a href="#dsc-' + OF.esc(id) + '" class="mono ev-link" data-goto="dsc-' + OF.esc(id) + '" title="' + OF.esc(d ? d.topic : "unknown discrepancy") + '">' + OF.esc(id) + "</a>";
};
OF.srcLink = function (id) {
  return '<a href="#src-' + OF.esc(id) + '" class="mono ev-link" data-goto="src-' + OF.esc(id) + '">' + OF.esc(id) + "</a>";
};
OF.gotoEvidence = function (anchor) {
  OF.switchTab("evidence", document.getElementById("tabbtn-evidence"));
  if (anchor.indexOf("clm-") === 0 && document.getElementById("claim-search").value) {
    document.getElementById("claim-search").value = ""; OF.renderClaims();
  }
  var el = document.getElementById(anchor);
  if (!el) return false;
  if (el.tagName === "DETAILS") el.open = true;
  el.scrollIntoView({ block: "center", behavior: OF.reducedMotion ? "auto" : "smooth" });
  el.classList.remove("ev-flash"); void el.offsetWidth; el.classList.add("ev-flash");
  el.setAttribute("tabindex", "-1"); el.focus({ preventScroll: true });
  return true;
};
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest("a.ev-link");
  if (!a) return;
  e.preventDefault();
  OF.gotoEvidence(a.getAttribute("data-goto"));
});

// ---- uncertainty components -------------------------------------------------
OF.componentsFor = function (testId) {
  var n = OF.testNumber(testId), dig = !!(OF.D.digitized || {})[testId];
  return OF.D.uncertainty.components.filter(function (u) {
    var a = u.applies_to;
    return a.kind === "all" || (a.kind === "range" && n >= a.first && n <= a.last) || (a.kind === "digitized" && dig);
  });
};
OF.ucById = {};
OF.D.uncertainty.components.forEach(function (u) { OF.ucById[u.id] = u; });

OF.fmtComponentValue = function (u) {
  if (u.value === null) return "—";
  return (u.interval_type.indexOf("±") >= 0 || u.interval_type.indexOf("resolution") === 0 ? "±" : "") + u.value + " " + u.unit;
};

OF.renderBudget = function (r) {
  var comps = OF.componentsFor(r.flex_test);
  document.getElementById("uq-budget-table").innerHTML = comps.map(function (u) {
    var prov = u.claims.length ? ' data-claims="' + u.claims.join(" ") + '"' : ' data-source="uncertainty registry ' + u.id + (u.record_ref ? " + " + u.record_ref : "") + '"';
    return "<tr" + prov + ' id="uc-' + u.id + '"><td class="mono">' + u.id + "</td><td><strong>" + OF.esc(u.component) + '</strong><br><span class="sub-note">' + OF.esc(u.measurand) + "</span></td>" +
      '<td class="mono">' + OF.esc(u.status) + '</td><td class="mono">' + OF.esc(OF.fmtComponentValue(u)) + "</td>" +
      '<td style="font-size:11px">' + OF.esc(u.interval_type) + "<br>coverage factor: " + OF.esc(u.coverage_factor) + "<br>distribution: " + OF.esc(u.distribution) + "</td>" +
      '<td style="font-size:11px">' + OF.esc(u.statement) + (u.claims.length ? " [" + u.claims.map(OF.claimLink).join(", ") + "]" : "") + "</td></tr>";
  }).join("");
  document.getElementById("uq-budget-count").textContent = comps.length + " of " + OF.D.uncertainty.components.length + " components apply to " + r.flex_test_as_printed;
};

// ---- result cards ------------------------------------------------------------
// One spec per quantitative Table IX result. Measurand definitions cite App. A.1 claims.
OF.RESULTS = {
  K_mm2_s: { label: "Burning-rate constant K", unit: "mm²/s", claims: ["CLM-019"],
    measurand: "Average burning-rate constant: slope of a linear fit of D² vs t from shortly after ignition to extinction",
    method: "Linear fit by the NASA authors; fit window, number of frames and weighting not reported", uc: ["UC-01", "UC-05", "UC-07", "UC-09"] },
  D0_mm: { label: "Initial droplet diameter D₀", unit: "mm", claims: ["CLM-018"],
    measurand: "Droplet diameter at time zero, when the igniters are turned ON",
    method: "HiBMs image analysis by the NASA authors (§3.1)", uc: ["UC-01", "UC-02", "UC-07", "UC-10"] },
  D_ext_visible_mm: { label: "Visible-flame extinction diameter", unit: "mm", claims: ["CLM-041"],
    measurand: "Droplet diameter when the visible flame extinguished; '–' = no extinction (completion or disruption)",
    method: "HiBMs image analysis by the NASA authors; sometimes extrapolated from the burning history (not marked per test)", uc: ["UC-01", "UC-06", "UC-07", "UC-10"] },
  t_burn_s: { label: "Burn time", unit: "s", claims: ["CLM-042"],
    measurand: "Printed as 'Burn time'; not defined in App. A.1 (DSC-024)",
    method: "Not described in the TP", uc: ["UC-07"] },
  P_mmHg: { label: "Ambient pressure", unit: "mmHg", claims: ["CLM-020"],
    measurand: "Absolute ambient pressure", method: "Chamber records (sensor uncertainty not stated)", uc: ["UC-07", "UC-08"] },
  X_O2: { label: "Oxygen mole fraction", unit: "", claims: ["CLM-020"],
    measurand: "Ambient O₂ mole fraction reconstructed from fill, recirculation, filter and combustion records",
    method: "Reconstruction by the NASA authors", uc: ["UC-07", "UC-08"] }
};

OF.diluentOf = function (r) { return (r.X_He || 0) > 0 ? "He" : ((r.X_CO2 || 0) > 0 ? "CO2" : "N2"); };

OF.resultCard = function (rows, prov) {
  return '<div class="result-card" ' + prov + ">" + rows.map(function (x) {
    return '<div class="pred-row"><span>' + OF.esc(x[0]) + '</span><span class="mono" style="text-align:right;max-width:64%">' + x[1] + "</span></div>";
  }).join("") + "</div>";
};

OF.renderResultPanel = function (r) {
  var sel = document.getElementById("result-select");
  if (!sel.options.length) {
    sel.innerHTML = Object.keys(OF.RESULTS).map(function (k) { return '<option value="' + k + '">' + OF.esc(OF.RESULTS[k].label) + "</option>"; }).join("");
    sel.onchange = function () { OF.renderResultPanel(OF.testById[OF.state.testId]); };
  }
  var key = sel.value, S = OF.RESULTS[key], raw = r[key + "_raw"], has = raw !== "–" && raw !== "";
  var comps = S.uc.filter(function (id) { return OF.componentsFor(r.flex_test).some(function (u) { return u.id === id; }); });
  var cov = OF.coverageForTest(r);
  var rows = [
    ["Result class", "Published tabulated value (PUBLISHED_TABULATED); computed by the NASA authors"],
    ["Measurand", OF.esc(S.measurand) + " [" + S.claims.map(OF.claimLink).join(", ") + "]"],
    ["Estimate", has ? OF.esc(raw) + (S.unit ? " " + S.unit : "") + " (as printed)" + (r[key + "_approx"] ? " — printed with '~' (approximate)" : "") : "Not reported (–)"],
    ["Interval", "None reported by the source"],
    ["Interval type / coverage", "Not applicable — no interval"],
    ["Method", OF.esc(S.method)],
    ["Sample size", "One physical test; no replicate statistics"],
    ["Domain status", "Observation, not a prediction. " + OF.esc(cov.text)],
    ["Uncertainty components", comps.map(function (id) { return '<a href="#uc-' + id + '" class="mono uc-link" data-uc="' + id + '">' + id + "</a> " + OF.esc(OF.ucById[id].status); }).join("; ")],
    ["Evidence", "[" + OF.srcLink("S01") + "] Table IX, printed p. " + OF.esc(r.printed_page) + " (PDF p. " + OF.esc(r.pdf_page) + ")"]
  ];
  document.getElementById("result-panel").innerHTML = OF.resultCard(rows, 'data-source="S01 Table IX" data-claims="' + S.claims.join(" ") + '"');
  document.getElementById("result-panel-title").textContent = "Result Transparency: " + S.label;
};
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest("a.uc-link");
  if (!a) return;
  e.preventDefault();
  OF.switchTab("uq", document.getElementById("tabbtn-uq"));
  var el = document.getElementById("uc-" + a.getAttribute("data-uc"));
  if (el) { el.scrollIntoView({ block: "center" }); el.classList.remove("ev-flash"); void el.offsetWidth; el.classList.add("ev-flash"); }
});

// Card for an AnalysisRun on digitized data (used by the digitized panel).
OF.analysisCard = function (A, testId) {
  var o = A.outputs, lo = o.K_range_over_windows_and_estimators_mm2_s[0], hi = o.K_range_over_windows_and_estimators_mm2_s[1];
  var rows = [
    ["Result class", "DERIVED from DIGITIZED data (AnalysisRun " + OF.esc(A.run_id) + ")"],
    ["Measurand", "Slope of the digitized D²(t) over pre-declared windows [" + OF.claimLink("CLM-019") + "]"],
    ["Estimate", "No single value is reported; see the window table"],
    ["Interval", '<span class="interval" data-interval-type="sensitivity range" data-method="4 windows × 2 estimators (OLS, Theil–Sen)" data-coverage="none">' + lo.toFixed(3) + "–" + hi.toFixed(3) + " mm²/s</span>"],
    ["Interval type / coverage", "Window/estimator sensitivity range; no coverage probability; not a confidence or prediction interval"],
    ["Method", OF.esc(A.method)],
    ["Sample size", "Digitized points per window (" + o.fits.map(function (f) { return f.window + " " + f.n_points; }).join(", ") + "); points are not independent (overlapping markers)"],
    ["Domain status", "Not applicable — consistency check of a digitization, not a prediction"],
    ["Uncertainty components", '<a href="#uc-UC-12" class="mono uc-link" data-uc="UC-12">UC-12</a>; <a href="#uc-UC-13" class="mono uc-link" data-uc="UC-13">UC-13</a>'],
    ["Purpose", "Checks that the digitization reproduces the printed K (" + OF.esc(o.table_ix_K_mm2_s.raw) + " mm²/s): " + (o.table_ix_K_within_range ? "consistent" : "not consistent") + " (printed rounding interval vs fitted range). Not a validation."]
  ];
  return OF.resultCard(rows, 'data-derived="' + OF.esc(A.run_id) + '"');
};

// ---- coverage (port of tools/coverage.py; keep in sync) ----------------------
OF.COV_VARS = ["P_atm", "X_O2", "D0_mm"];
OF.COV_NEAR = 0.25;
OF.coverageRows = (function () {
  var out = [];
  OF.D.table_ix.forEach(function (r) {
    if (r.P_mmHg === null || r.P_mmHg === 0 || r.X_O2 === null || r.D0_mm === null) return;
    out.push({ test_id: r.flex_test, fuel: r.fuel, diluent: OF.diluentOf(r), P_atm: r.P_mmHg / 760, X_O2: r.X_O2, D0_mm: r.D0_mm });
  });
  return out;
})();

OF.coverage = function (fuel, dil, q, exclude, k) {
  k = k || 5;
  var g = OF.coverageRows.filter(function (r) { return r.fuel === fuel && r.diluent === dil && r.test_id !== exclude; });
  if (!g.length) return { label: "NO_TESTS", n_group: 0, ranges: {}, outside: [], nearest: [] };
  var rng = {}, span = {};
  OF.COV_VARS.forEach(function (v) {
    var vals = g.map(function (r) { return r[v]; });
    rng[v] = [Math.min.apply(null, vals), Math.max.apply(null, vals)];
    span[v] = (rng[v][1] - rng[v][0]) || 1;
  });
  var outside = OF.COV_VARS.filter(function (v) { return !(rng[v][0] <= q[v] && q[v] <= rng[v][1]); });
  var d = g.map(function (r) {
    return [Math.sqrt(OF.COV_VARS.reduce(function (s, v) { var z = (q[v] - r[v]) / span[v]; return s + z * z; }, 0)), r.test_id];
  }).sort(function (a, b) { return a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0); });
  var r4 = function (x) { return Math.round(x * 1e4) / 1e4; };
  var label = outside.length ? "OUTSIDE_RANGE" : (d[0][0] <= OF.COV_NEAR ? "INSIDE_NEAR_TEST" : "INSIDE_SPARSE");
  var ranges = {};
  OF.COV_VARS.forEach(function (v) { ranges[v] = [r4(rng[v][0]), r4(rng[v][1])]; });
  return { label: label, n_group: g.length, ranges: ranges, outside: outside,
    nearest: d.slice(0, k).map(function (x) { return { test_id: x[1], distance: r4(x[0]) }; }) };
};

OF.COV_TEXT = {
  NO_TESTS: "No Table IX test with this fuel and diluent.",
  OUTSIDE_RANGE: "Outside the min–max of tested conditions for this fuel and diluent",
  INSIDE_NEAR_TEST: "Inside the tested ranges and near a tested condition",
  INSIDE_SPARSE: "Inside the tested ranges but not near any single tested condition"
};

OF.coverageForTest = function (r) {
  if (r.P_mmHg === null || r.P_mmHg === 0 || r.X_O2 === null || r.D0_mm === null) {
    return { text: "Coverage not computed (missing or zero printed value)." };
  }
  var c = OF.coverage(r.fuel, OF.diluentOf(r), { P_atm: r.P_mmHg / 760, X_O2: r.X_O2, D0_mm: r.D0_mm }, r.flex_test, 3);
  return { text: c.n_group + " other Table IX tests share fuel and diluent (" + OF.diluentOf(r) + "); most similar: " +
    c.nearest.map(function (n) { return n.test_id + " (distance " + n.distance.toFixed(2) + ")"; }).join(", ") + ".", cov: c };
};

OF.renderCoverage = function (fromTest) {
  var f = document.getElementById("cov-form");
  if (fromTest) {
    var r = OF.testById[OF.state.testId];
    f.fuel.value = r.fuel; f.diluent.value = OF.diluentOf(r);
    f.P_atm.value = r.P_mmHg ? (r.P_mmHg / 760).toFixed(3) : ""; f.X_O2.value = r.X_O2 === null ? "" : r.X_O2; f.D0_mm.value = r.D0_mm === null ? "" : r.D0_mm;
  }
  var q = { P_atm: parseFloat(f.P_atm.value), X_O2: parseFloat(f.X_O2.value), D0_mm: parseFloat(f.D0_mm.value) };
  var out = document.getElementById("cov-result");
  if (OF.COV_VARS.some(function (v) { return !isFinite(q[v]); })) { out.innerHTML = '<div class="alert-box alert-warn">Enter numbers for P, O₂ and D₀.</div>'; return; }
  var excl = document.getElementById("cov-exclude").checked ? OF.state.testId : null;
  var c = OF.coverage(f.fuel.value, f.diluent.value, q, excl, 5);
  var lab = { P_atm: "P, atm", X_O2: "O₂ mole fraction", D0_mm: "D₀, mm" };
  out.innerHTML = '<div data-derived="coverage of Table IX (tools/coverage.py rules)">' +
    '<p><span class="badge ' + (c.label === "INSIDE_NEAR_TEST" ? "badge-scope" : c.label === "INSIDE_SPARSE" ? "badge-warn" : "badge-danger") + '">' + c.label.replace(/_/g, " ") + "</span> " + OF.esc(OF.COV_TEXT[c.label]) +
    (c.outside.length ? ": " + c.outside.map(function (v) { return lab[v]; }).join(", ") : "") + ".</p>" +
    (c.n_group ? '<table aria-label="Tested ranges"><thead><tr><th>Variable</th><th>Query</th><th>Tested min–max (n = ' + c.n_group + ")</th></tr></thead><tbody>" +
      OF.COV_VARS.map(function (v) { return "<tr><td>" + lab[v] + '</td><td class="mono">' + q[v] + '</td><td class="mono">' + c.ranges[v][0] + "–" + c.ranges[v][1] + (c.outside.indexOf(v) >= 0 ? ' <span class="matrix-diff">outside</span>' : "") + "</td></tr>"; }).join("") +
      '</tbody></table><p style="font-size:11.5px">Nearest tested conditions (normalized distance): ' + c.nearest.map(function (n) {
        var t = OF.testById[n.test_id];
        return '<a href="#" class="mono cov-goto" data-test="' + n.test_id + '">' + n.test_id + "</a> (" + n.distance.toFixed(2) + "; P " + (t.P_mmHg / 760).toFixed(2) + " atm, O₂ " + OF.esc(t.X_O2_raw) + ", D₀ " + OF.esc(t.D0_mm_raw) + " mm, K " + OF.esc(t.K_mm2_s_raw) + ")";
      }).join("; ") + "</p>" : "") + "</div>";
  OF.drawCoverage(f.fuel.value, f.diluent.value, q, excl);
};

OF.drawCoverage = function (fuel, dil, q, excl) {
  var el = document.getElementById("plot-coverage");
  if (!OF.libStatus().plotly) { el.innerHTML = '<div class="alert-box alert-danger">Plot library unavailable — use the table above.</div>'; return; }
  var g = OF.coverageRows.filter(function (r) { return r.fuel === fuel && r.diluent === dil && r.test_id !== excl; });
  var B = OF.plotBase();
  Plotly.react(el, [
    { x: g.map(function (r) { return r.X_O2; }), y: g.map(function (r) { return r.P_atm; }), text: g.map(function (r) { return r.test_id + ", D₀ " + r.D0_mm + " mm"; }),
      mode: "markers", type: "scatter", name: "Tested conditions (Table IX, published)", marker: { color: B.s1, size: 9, line: { color: B.surface, width: 1 } },
      hovertemplate: "%{text}<br>O₂ %{x}<br>P %{y:.3f} atm<extra>Table IX · published</extra>" },
    { x: [q.X_O2], y: [q.P_atm], mode: "markers", type: "scatter", name: "Query conditions (entered)",
      marker: { color: B.s2, size: 14, symbol: "diamond", line: { color: B.surface, width: 2 } },
      hovertemplate: "Query<br>O₂ %{x}<br>P %{y:.3f} atm<extra>entered</extra>" }
  ], { paper_bgcolor: B.paper_bgcolor, plot_bgcolor: B.plot_bgcolor, font: B.font, height: 300,
    margin: { l: 56, r: 16, t: 30, b: 80 }, title: { text: fuel + " · " + dil + "-diluted: tested O₂ and pressure (D₀ in hover)", font: { size: 11.5 }, x: 0, xanchor: "left" },
    xaxis: { title: "O₂ mole fraction (as printed)", gridcolor: B.grid }, yaxis: { title: "Pressure, atm (mmHg ÷ 760)", gridcolor: B.grid },
    legend: { orientation: "h", y: -0.3, yanchor: "top" } }, { displayModeBar: false, responsive: true });
};
document.addEventListener("click", function (e) {
  var a = e.target.closest && e.target.closest("a.cov-goto");
  if (!a) return;
  e.preventDefault();
  OF.selectTest(a.getAttribute("data-test"));
  OF.renderCoverage(true);
});
