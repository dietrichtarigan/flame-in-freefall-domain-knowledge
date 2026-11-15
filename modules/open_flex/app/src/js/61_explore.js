// ---------------------------------------------------------------------------
// Open FLEX — Explore mode: the D²-law educational baseline next to the source record.
// A simulation run is never a physical test: it is identified by SIM-…, says which test's printed
// conditions seeded it, and lists every input changed from them. The 3D view keeps showing the
// physical test record only.
// ---------------------------------------------------------------------------
OF.explore = { on: false, inputs: null, seededFrom: null };

OF.initModeSwitch = function () {
  var av = OF.modelAvailable(), bE = document.getElementById("mode-explore"), bR = document.getElementById("mode-replay");
  var note = document.getElementById("mode-note");
  if (!av.ok) {
    bE.disabled = true; bE.textContent = "Explore with a model (unavailable)"; bE.title = av.why;
    note.textContent = av.why;
    return;
  }
  var v = OF.D.model.verification;
  bE.disabled = false; bE.textContent = "Explore with a model"; bE.title = "";
  note.innerHTML = 'Explore runs the D²-law educational baseline (classical theory, ' + OF.claimLink("CLM-051") + "): code-verified (" + v.n_passed + "/" + v.n_checks +
    " checks, " + OF.claimLink("CLM-056") + "), <strong>not validated</strong> against FLEX. The 3D view keeps showing the physical test record only.";
  function set(on) {
    OF.explore.on = on;
    bE.classList.toggle("active", on); bR.classList.toggle("active", !on);
    bE.setAttribute("aria-checked", on ? "true" : "false"); bR.setAttribute("aria-checked", on ? "false" : "true");
    document.getElementById("explore-panel").hidden = !on;
    if (on) OF.exploreSeed(OF.state.testId);
  }
  bE.addEventListener("click", function () { set(true); });
  bR.addEventListener("click", function () { set(false); });
  document.getElementById("explore-panel").addEventListener("input", function (e) { if (e.target.matches("[data-x]")) OF.exploreRead(); });
  document.getElementById("explore-panel").addEventListener("change", function (e) { if (e.target.matches("[data-x]")) OF.exploreRead(); });
  document.getElementById("btn-explore-reset").addEventListener("click", function () { OF.exploreSeed(OF.state.testId); });
};

OF.exploreSeed = function (id) {
  if (!OF.explore.on || !id) return;
  var r = OF.testById[id];
  OF.explore.seededFrom = id;
  OF.explore.seed = OF.D2.seededInputs(r);
  OF.explore.inputs = JSON.parse(JSON.stringify(OF.explore.seed));
  var I = OF.explore.inputs, g = function (k) { return document.getElementById(k); };
  g("ex-fuel").value = I.fuel;
  g("ex-o2").value = I.X.O2; g("ex-co2").value = I.X.CO2 || 0; g("ex-he").value = I.X.He || 0;
  g("ex-d0").value = I.D0_mm === null ? "" : I.D0_mm;
  g("ex-tinf").value = I.T_inf_K; g("ex-tprop").value = ""; g("ex-q").value = "nominal"; g("ex-rho").value = "boil";
  g("ex-seed-label").textContent = r.flex_test_as_printed;
  OF.exploreRun();
};

// Read the form; N2 is the balance so that the four printed fractions keep their printed sum.
OF.exploreRead = function () {
  var S = OF.explore.seed, g = function (k) { return document.getElementById(k).value; };
  var I = JSON.parse(JSON.stringify(S));
  I.fuel = g("ex-fuel");
  var o2 = parseFloat(g("ex-o2")), co2 = parseFloat(g("ex-co2")) || 0, he = parseFloat(g("ex-he")) || 0;
  var total = (S.X.O2 || 0) + (S.X.N2 || 0) + (S.X.CO2 || 0) + (S.X.He || 0);
  if (o2 !== S.X.O2 || co2 !== (S.X.CO2 || 0) || he !== (S.X.He || 0)) {
    I.X = { O2: o2, CO2: co2, He: he, N2: Math.round((total - o2 - co2 - he) * 1e6) / 1e6 };
  }
  var d0 = parseFloat(g("ex-d0")); I.D0_mm = isFinite(d0) && d0 > 0 ? d0 : S.D0_mm;
  var tinf = parseFloat(g("ex-tinf")); I.T_inf_K = isFinite(tinf) ? tinf : S.T_inf_K;
  var tp = parseFloat(g("ex-tprop"));
  if (isFinite(tp)) { I.T_prop_K = tp; I.T_prop_rule = "fixed"; }
  I.Q_variant = g("ex-q"); I.rho_l_at = g("ex-rho");
  OF.explore.inputs = I;
  OF.exploreRun();
};

OF.exploreModified = function () {
  var S = OF.explore.seed, I = OF.explore.inputs, m = [];
  if (I.fuel !== S.fuel) m.push("fuel " + S.fuel + " → " + I.fuel);
  ["O2", "N2", "CO2", "He"].forEach(function (k) { if ((I.X[k] || 0) !== (S.X[k] || 0)) m.push("X_" + k + " " + (S.X[k] || 0) + " → " + I.X[k] + (k === "N2" ? " (balance)" : "")); });
  if (I.D0_mm !== S.D0_mm) m.push("D₀ " + S.D0_mm + " → " + I.D0_mm + " mm");
  if (I.T_inf_K !== S.T_inf_K) m.push("T∞ " + S.T_inf_K + " → " + I.T_inf_K + " K (the TP gives no number; 298.15 K is itself an assumption, CLM-052)");
  if (I.T_prop_K !== undefined) m.push("property temperature fixed at " + I.T_prop_K + " K");
  if (I.Q_variant !== S.Q_variant) m.push("heating value: " + I.Q_variant + " end of the source range");
  if (I.rho_l_at !== S.rho_l_at) m.push("liquid density at 298.15 K instead of the boiling point");
  return m;
};

OF.fmt = function (v, n) { return v === null || v === undefined ? "—" : (Math.abs(v) >= 1e4 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(n - 1) : (+v.toPrecision(n)).toString()); };

OF.exploreRun = async function () {
  var T = OF.D.model.properties, I = OF.explore.inputs, id = OF.explore.seededFrom, r = OF.testById[id];
  var out, err = null;
  var bad = ["O2", "N2", "CO2", "He"].filter(function (k) { return !(I.X[k] >= 0 && I.X[k] <= 1); });
  try {
    if (bad.length) throw new Error("mole fraction outside 0–1 for " + bad.join(", ") + " (N₂ is the balance)");
    if (!(I.T_inf_K >= 200 && I.T_inf_K <= 600)) throw new Error("T∞ must be 200–600 K in this baseline");
    if (I.T_prop_K !== undefined && !(I.T_prop_K >= 300 && I.T_prop_K <= 2000)) throw new Error("property temperature must lie in the table range 300–2000 K");
    out = OF.D2.solve(OF.D2.forSolve(I), T);
  } catch (e) { err = e.message; }
  var mod = OF.exploreModified();
  var rid = await OF.D2.runId(I, OF.D.model.verification.property_table_sha256);
  OF.explore.last = { inputs: I, outputs: out, run_id: rid, modified: mod, seeded_from: id };
  if (OF.shareUpdate) OF.shareUpdate();
  var st = document.getElementById("ex-status");
  st.className = "alert-box " + (mod.length ? "alert-warn" : "alert-info");
  st.innerHTML = '<strong>SIMULATION <span class="mono" id="ex-run-id">' + OF.esc(rid || "SIM-(hash unavailable)") + "</span></strong> — D²-law educational baseline " + OF.D2.VERSION +
    " · NUMERICAL_SIMULATION · not FLEX data.<br>" + (mod.length ? "<strong>Modified</strong> from the printed conditions of " + OF.esc(r.flex_test_as_printed) + ": " + mod.map(OF.esc).join("; ") + ". This run does not describe " + OF.esc(r.flex_test_as_printed) + "."
      : "Inputs = printed Table IX conditions of " + OF.esc(r.flex_test_as_printed) + " (seed only; the run is not the test).");
  var o = document.getElementById("ex-out");
  if (err) { o.innerHTML = '<div class="alert-box alert-danger">' + OF.esc(err) + "</div>"; OF.explorePlots(null); return; }
  var printedK = (!mod.length || mod.every(function (s) { return /^D₀/.test(s); })) ? r.K_mm2_s_raw : null;
  var rows = [
    ["Transfer number B", OF.fmt(out.B, 4), "—"],
    ["Burning-rate constant K, mm²/s", OF.fmt(out.K_mm2_s, 4), printedK ? '<span class="mono">' + OF.esc(printedK) + "</span> (Table IX, PUBLISHED TABULATED)" : "— (inputs differ from the test)"],
    ["Burn time D₀²/K, s", OF.fmt(out.t_burn_s, 4), printedK ? '<span class="mono">' + OF.esc(r.t_burn_s_raw) + "</span> (Table IX)" : "—"],
    ["Flame standoff ratio r_f / r_s", OF.fmt(out.flame_standoff_ratio, 4), "see flame plot (digitized, where available)"],
    ["Flame temperature T_f, K", OF.fmt(out.T_flame_K, 4), "not measured in FLEX (§3)"],
    ["Property temperature, K", OF.fmt(out.T_prop_K, 4) + (out.iterations ? " (" + out.iterations + " iterations)" : " (fixed)"), "—"],
    ["Gas cp, J/(kg·K) · k, W/(m·K)", OF.fmt(out.cp_J_kgK, 4) + " · " + OF.fmt(out.k_W_mK, 4), "ambient-gas mixture, CoolProp (CLM-053)"],
    ["Ambient O₂ mass fraction", OF.fmt(out.Y_O2_inf, 4), "computed from the mole fractions"]
  ];
  o.innerHTML = '<table aria-label="Model outputs next to printed values"><thead><tr><th>Quantity</th><th>Model (SIMULATION)</th><th>Printed / measured (comparison only, not validation)</th></tr></thead><tbody>' +
    rows.map(function (x) { return "<tr><td>" + x[0] + '</td><td class="mono">' + x[1] + "</td><td>" + x[2] + "</td></tr>"; }).join("") + "</tbody></table>" +
    (out.flags.length ? '<p class="sub-note">Flags: ' + out.flags.map(OF.esc).join("; ") + "</p>" : "") +
    '<p class="sub-note" data-claims="CLM-057">Not represented: extinction (radiative or diffusive), soot and radiation, cool-flame burning, unsteady gas phase, droplet heating, fuel-vapour properties, water uptake by methanol, pressure (no pressure dependence in this model). At the printed conditions the model K is above the printed K for every Table IX test (CLM-057).</p>';
  OF.exploreSensitivity(I);
  OF.explorePlots(out);
};

// Model-form sensitivity: the same run with one modelling choice changed. Not an uncertainty interval.
OF.exploreSensitivity = function (I) {
  var T = OF.D.model.properties, base = OF.D2.solve(OF.D2.forSolve(I), T).K_mm2_s;
  var alt = [["property temperature 600 K", { T_prop_K: 600 }], ["property temperature 2000 K", { T_prop_K: 2000 }],
    ["heating value, low end", { Q_variant: "low" }], ["heating value, high end", { Q_variant: "high" }], ["liquid density at 298.15 K", { rho_l_at: "298" }]];
  var html = alt.map(function (a) {
    var J = JSON.parse(JSON.stringify(I)); Object.keys(a[1]).forEach(function (k) { J[k] = a[1][k]; });
    var k = OF.D2.solve(OF.D2.forSolve(J), T).K_mm2_s;
    return "<tr><td>" + a[0] + '</td><td class="mono">' + OF.fmt(k, 4) + '</td><td class="mono">' + (base && k ? (k / base * 100 - 100).toFixed(1) + " %" : "—") + "</td></tr>";
  }).join("");
  document.getElementById("ex-sens").innerHTML = '<table aria-label="Model-form sensitivity of K"><thead><tr><th>Changed modelling choice</th><th>K, mm²/s</th><th>vs this run</th></tr></thead><tbody>' + html + "</tbody></table>";
};

OF.explorePlots = function (out) {
  var ids = ["ex-plot-d2", "ex-plot-flame", "ex-plot-profiles"];
  if (!out || out.K_mm2_s === null) { ids.forEach(function (k) { document.getElementById(k).innerHTML = ""; }); return; }
  if (!OF.libStatus().plotly) { ids.forEach(function (k) { document.getElementById(k).innerHTML = '<div class="alert-box alert-danger">Plot library unavailable — values in the table above.</div>'; }); return; }
  var B = OF.plotBase(), I = OF.explore.inputs, id = OF.explore.seededFrom, r = OF.testById[id], dig = (OF.D.digitized || {})[id];
  var D0 = I.D0_mm, K = out.K_mm2_s, tb = D0 * D0 / K, n = 80, t = [], d2 = [], df = [];
  for (var i = 0; i <= n; i++) { var ti = tb * i / n; t.push(ti); var v = Math.max(D0 * D0 - K * ti, 0); d2.push(v); df.push(out.flame_standoff_ratio ? out.flame_standoff_ratio * Math.sqrt(v) : null); }
  var simName = "D²-law baseline · SIMULATION " + (OF.explore.last.run_id || "");
  var tr = [{ x: t, y: d2, mode: "lines", name: simName, line: { color: B.font.color, width: 2, dash: "dash" } }];
  var trF = [{ x: t, y: df, mode: "lines", name: "flame diameter = (r_f/r_s)·D · SIMULATION", line: { color: B.font.color, width: 2, dash: "dash" } }];
  if (dig) {
    dig.series.forEach(function (s) {
      var st = OF.SERIES_STYLE[s.name] || { slot: "s1", label: s.name };
      var m = { x: s.t, y: s.v, mode: "markers", name: st.label + " · DIGITIZED " + id, marker: { color: B[st.slot], size: 6 } };
      if (s.name === "droplet_d2") tr.push(m); else trF.push(m);
    });
  } else if (r.D0_mm !== null && r.K_mm2_s !== null && r.t_burn_s !== null) {
    tr.push({ x: [0, r.t_burn_s], y: [r.D0_mm * r.D0_mm, Math.max(r.D0_mm * r.D0_mm - r.K_mm2_s * r.t_burn_s, 0)], mode: "lines",
      name: "D₀² − K·t from printed D₀, K (RECONSTRUCTED, " + id + ")", line: { color: B.s1, width: 2 } });
  }
  function lay(title, yt) {
    return { paper_bgcolor: B.paper_bgcolor, plot_bgcolor: B.plot_bgcolor, font: B.font, height: 300, margin: { l: 56, r: 16, t: 34, b: 96 },
      title: { text: title, font: { size: 11.5 }, x: 0, xanchor: "left" }, hovermode: "closest",
      xaxis: { title: { text: "Time, s", standoff: 4 }, gridcolor: B.grid },
      yaxis: { title: yt, gridcolor: B.grid, rangemode: "tozero" }, legend: { orientation: "h", y: -0.24, yanchor: "top" } };
  }
  Plotly.react("ex-plot-d2", tr, lay("Droplet D²: model (dashed) vs " + (dig ? "digitized data" : "printed-value reconstruction"), "D², mm²"), { displayModeBar: false, responsive: true });
  // If data are shown, the axis spans the data; a model curve running above it is stated in the title, not hidden.
  var lf = lay("Flame diameter: model vs " + (dig ? "digitized data" : "no measured data loaded"), "diameter, mm"), dmax = 0, mmax = 0;
  trF.forEach(function (s, k) { s.y.forEach(function (v) { if (v === null) return; if (k === 0) mmax = Math.max(mmax, v); else dmax = Math.max(dmax, v); }); });
  if (dmax > 0 && mmax > 1.6 * dmax) {
    lf.yaxis.range = [0, 1.6 * dmax]; lf.yaxis.rangemode = undefined;
    lf.title.text = "Flame diameter: digitized data and model — model curve rises above this axis to " + mmax.toFixed(0) + " mm";
  }
  Plotly.react("ex-plot-flame", trF, lf, { displayModeBar: false, responsive: true });
  // Radial profiles of the model's flame-sheet solution (the profiles the code verification checks).
  var Ts = out.T_s_K, L = out.L_J_kg, cp = out.cp_J_kgK, Q = out.Q_J_kg, YO = out.Y_O2_inf, nu = out.nu;
  var lam = Math.log1p(out.B), rf = lam / Math.log1p(YO / nu), xr = [], Tr = [], YF = [], YOr = [];
  var rmax = Math.max(2 * rf, 3);
  for (var j = 0; j <= 200; j++) {
    var rr = 1 + (rmax - 1) * j / 200; xr.push(rr);
    if (rr <= rf) { Tr.push(Ts + (L / cp) * (Math.exp(lam - lam / rr) - 1)); YF.push(1 - Math.exp(lam / rf - lam / rr)); YOr.push(0); }
    else { Tr.push(Ts - L / cp + Q / cp + (I.T_inf_K - Ts + (L - Q) / cp) * Math.exp(-lam / rr)); YF.push(0); YOr.push(-nu + (YO + nu) * Math.exp(-lam / rr)); }
  }
  Plotly.react("ex-plot-profiles", [
    { x: xr, y: Tr, name: "temperature, K · SIMULATION", line: { color: B.s2, width: 2 } },
    { x: xr, y: YF, name: "fuel mass fraction · SIMULATION", yaxis: "y2", line: { color: B.s1, width: 2, dash: "dash" } },
    { x: xr, y: YOr, name: "O₂ mass fraction · SIMULATION", yaxis: "y2", line: { color: B.s3, width: 2, dash: "dot" } }
  ], (function () { var l = lay("Model radial profiles (flame sheet at r_f/r_s = " + OF.fmt(rf, 3) + ")", "temperature, K"); l.xaxis.title = { text: "r / r_s", standoff: 4 }; l.legend.y = -0.3; l.margin.b = 110; l.height = 320; l.yaxis2 = { title: "mass fraction", overlaying: "y", side: "right", range: [0, 1], showgrid: false }; l.margin.r = 52; return l; })(),
  { displayModeBar: false, responsive: true });
};

OF.renderVerification = function () {
  var el = document.getElementById("ex-verification");
  if (!el || !OF.D.model) return;
  var v = OF.D.model.verification;
  el.innerHTML = '<p class="sub-note">' + OF.esc(v.scope) + "</p><table aria-label=\"Code verification checks\"><thead><tr><th>ID</th><th>Check</th><th>Value</th><th>Tolerance</th><th>Result</th></tr></thead><tbody>" +
    v.checks.map(function (c) { return '<tr><td class="mono">' + OF.esc(c.id) + "</td><td>" + OF.esc(c.check) + (c.detail ? '<br><span class="small">' + OF.esc(c.detail) + "</span>" : "") + '</td><td class="mono">' + OF.esc(String(c.value)) + '</td><td class="mono">' + OF.esc(String(c.tolerance)) + '</td><td><span class="badge ' + (c.pass ? "badge-scope" : "badge-danger") + '">' + (c.pass ? "PASS" : "FAIL") + "</span></td></tr>"; }).join("") + "</tbody></table>";
};
