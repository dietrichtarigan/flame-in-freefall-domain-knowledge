// ---------------------------------------------------------------------------
// Open FLEX — physics schematic, uncertainty budget, evidence tables, export.
// ---------------------------------------------------------------------------

// Dimensionless schematic of a droplet diffusion flame. Shapes only: no
// temperatures, no fuel dependence, no dependence on the selected test.
OF.renderRadialSchematic = function () {
  var el = document.getElementById("plot-radial");
  if (!OF.libStatus().plotly) { el.innerHTML = '<div class="alert-box alert-danger">Plot library unavailable — schematic not drawn.</div>'; return; }
  var x = [], th = [], yf = [], yo = [], rf = 5;
  for (var i = 0; i <= 120; i++) {
    var r = 1 + i * 0.1; x.push(r);
    th.push(r <= rf ? (r - 1) / (rf - 1) : rf / r);           // piecewise shape, illustrative
    yf.push(r <= rf ? 1 - (r - 1) / (rf - 1) : 0);
    yo.push(r <= rf ? 0 : 1 - rf / r);
  }
  var B = OF.plotBase();
  Plotly.react(el, [
    { x: x, y: th, name: "temperature (normalized shape) · CONCEPTUAL", line: { color: B.s2, width: 2.5 } },
    { x: x, y: yf, name: "fuel (normalized shape) · CONCEPTUAL", line: { color: B.s1, width: 2, dash: "dash" } },
    { x: x, y: yo, name: "oxidizer (normalized shape) · CONCEPTUAL", line: { color: B.s3, width: 2, dash: "dot" } }
  ], {
    paper_bgcolor: B.paper_bgcolor, plot_bgcolor: B.plot_bgcolor, font: B.font,
    margin: { l: 52, r: 16, t: 36, b: 44 },
    title: { text: "CONCEPTUAL ILLUSTRATION — NOT SOLVER OUTPUT", font: { size: 11 } },
    xaxis: { title: "r / r_s (arbitrary flame position)", gridcolor: B.grid },
    yaxis: { title: "normalized (no units)", range: [0, 1.05], gridcolor: B.grid },
    legend: { orientation: "h", y: 1.2 }
  }, { displayModeBar: false, responsive: true });
};


OF.renderClaims = function () {
  var q = (document.getElementById("claim-search").value || "").toLowerCase();
  var list = OF.D.claims.claims.filter(function (c) {
    return JSON.stringify(c).toLowerCase().indexOf(q) >= 0;
  });
  document.getElementById("claim-ledger-body").innerHTML = list.map(function (c) {
    var st = c.verification_status, cls = st === "VERIFIED" ? "badge-scope" : (st === "UNVERIFIED" ? "badge-danger" : "badge-warn");
    return '<tr id="clm-' + OF.esc(c.claim_id) + '" data-claims="' + OF.esc(c.claim_id) + '"><td class="mono"><strong>' + OF.esc(c.claim_id) + "</strong></td><td>" + OF.esc(c.claim_text) + '</td><td class="mono" style="font-size:10.5px">' + OF.esc(c.evidence_class) +
      '</td><td class="mono" style="font-size:10.5px">' + c.sources.map(function (s) { return "[" + OF.srcLink(s.source_id) + "] " + OF.esc(s.locator); }).join("<br/>") +
      '</td><td><span class="badge ' + cls + '">' + OF.esc(st) + '</span></td><td style="font-size:11px">' + OF.esc(c.note) + "</td></tr>";
  }).join("");
};

OF.renderSources = function () {
  document.getElementById("source-body").innerHTML = OF.D.sources.sources.map(function (s) {
    return '<tr id="src-' + OF.esc(s.source_id) + '" data-source="' + OF.esc(s.source_id) + '"><td class="mono">' + OF.esc(s.source_id) + "</td><td>" + OF.esc(s.citation) + '<br/><span class="mono small">' + OF.esc(s.url) + "</span>" +
      (s.sha256 ? '<br/><span class="mono" style="font-size:10px">SHA-256 ' + OF.esc(s.sha256) + "</span>" : "") +
      '</td><td class="mono" style="font-size:10.5px">' + OF.esc(s.source_class) + '</td><td style="font-size:11px">' + OF.esc(s.review_status) + "</td></tr>";
  }).join("");
};

OF.renderDiscrepancies = function () {
  document.getElementById("discrepancy-body").innerHTML = OF.D.discrepancies.discrepancies.map(function (d) {
    return '<div class="bubble-cell" style="margin-bottom:6px" id="dsc-' + OF.esc(d.discrepancy_id) + '" data-source="' + OF.esc(d.discrepancy_id) + '"><h3>' + OF.esc(d.discrepancy_id) + " — " + OF.esc(d.topic) + '</h3><ul style="margin:2px 0 4px 16px;padding:0;font-size:11.5px">' +
      d.values.map(function (v) { return "<li>" + OF.esc(v.value) + ' <span class="mono" style="font-size:10px">(' + OF.esc(v.source) + ")</span></li>"; }).join("") +
      '</ul><p style="font-size:11px">Preferred: ' + OF.esc(d.preferred || "none") + " — " + OF.esc(d.reason) + "</p>" +
      (d.tests && d.tests.length ? '<p style="font-size:10.5px" class="mono">Tests: ' + d.tests.map(OF.esc).join(", ") + "</p>" : "") +
      (d.detected_by ? '<p class="small">Found by: ' + OF.esc(d.detected_by) + "</p>" : "") + "</div>";
  }).join("");
};

// Dataset manifest (data/MANIFEST.json): every data file with version, class, origin, SHA-256.
OF.renderDatasets = function () {
  var el = document.getElementById("dataset-body");
  if (!el || !OF.D.manifest) return;
  el.innerHTML = OF.D.manifest.datasets.map(function (d) {
    return '<tr data-source="data/MANIFEST.json"><td class="mono" style="font-size:10.5px">' + OF.esc(d.dataset_id) + "<br>v" + OF.esc(d.version) + '</td><td class="mono" style="font-size:10.5px">' + OF.esc(d.data_class) +
      '</td><td style="font-size:11px">' + OF.esc(d.path) + (d.rows !== null ? " (" + d.rows + " rows)" : "") + "<br>" + OF.esc(d.method) +
      (d.limitations ? '<br><em>' + OF.esc(d.limitations) + "</em>" : "") + '</td><td class="mono" style="font-size:10px" title="' + OF.esc(d.sha256) + '">' + OF.esc(d.sha256.slice(0, 12)) + "…</td></tr>";
  }).join("");
};

// ---------------------------------------------------------------------------
// Export: a JSON manifest for one physical test record. Deliberately NOT
// labelled RO-Crate (no ro-crate-metadata.json, no packaged files).
// ---------------------------------------------------------------------------
OF.exportableRecord = function (r) {
  var fields = {};
  ["P_mmHg", "X_O2", "X_N2", "X_CO2", "X_He", "D0_mm", "D_ext_visible_mm", "K_mm2_s", "t_burn_s"].forEach(function (k) {
    fields[k] = { as_printed: r[k + "_raw"], parsed: r[k], approximate: !!r[k + "_approx"] };
  });
  fields.test_end = { as_printed: r.test_end };
  return {
    record_type: "PhysicalTestRecord",
    record_schema_version: "0.2.0",
    test_id_as_printed: r.flex_test_as_printed,
    test_id_normalized: r.flex_test,
    cir_identifier: r.cir_identifier,
    date_mdy_as_printed: r.date_mdy_as_printed,
    time_gmt_as_printed: r.time_gmt,
    fuel: r.fuel,
    evidence_class: "PUBLISHED_TABULATED",
    fields: fields,
    units: { P_mmHg: "mmHg", X: "mole fraction", D0_mm: "mm", D_ext_visible_mm: "mm", K_mm2_s: "mm^2/s", t_burn_s: "s" },
    source: { source_id: "S01", locator: "Table IX, printed p. " + r.printed_page + " (PDF p. " + r.pdf_page + ")", source_pdf_sha256: r.source_pdf_sha256 },
    fiber: (function () { var x = OF.recordFor(r.flex_test); return x ? { status: x.fiber.status, test_matrix: x.fiber.test_matrix, caption: x.fiber.caption, evidence: x.fiber.evidence } : null; })(),
    test_matrix: (function () { var x = OF.recordFor(r.flex_test); return x && x.test_matrix.present ? { locator: x.test_matrix.source.locator, date_as_printed: x.test_matrix.date_as_printed, values: x.test_matrix.values } : null; })(),
    discrepancies: (function () { var x = OF.recordFor(r.flex_test); return x ? x.discrepancies : []; })()
  };
};

OF.exportManifest = async function () {
  var r = OF.testById[OF.state.testId], rec = OF.exportableRecord(r), d = OF.derived(r);
  var recHash = await OF.sha256Hex(OF.canonicalJSON(rec));
  var used = {};
  OF.flagsFor(r.flex_test).forEach(function (f) { (f.claims || []).forEach(function (c) { used[c] = 1; }); });
  ["CLM-009", "CLM-011", "CLM-012", "CLM-018", "CLM-019", "CLM-020"].forEach(function (c) { used[c] = 1; });
  var m = {
    manifest_type: "OpenFLEX-PhysicalTestRecordExport",
    is_ro_crate: false,
    note: "Plain JSON manifest for one test record. Not an RO-Crate: no ro-crate-metadata.json descriptor and no packaged files. The repository as a whole is described by ro-crate-metadata.json (RO-Crate 1.2, checked with rocrate-validator; see docs/PHASE_B_M6_Report.md).",
    export_id: OF.uuid4(),
    export_id_note: "Identifies this export event only; it is not an experiment or simulation identifier.",
    created_utc: new Date().toISOString(),
    app_build: OF.D.build,
    record: rec,
    record_sha256: recHash || "unavailable",
    record_sha256_scope: "SHA-256 of the UTF-8 canonical JSON of `record` (object keys sorted recursively, no whitespace). Recompute with tools/canonical_json.py.",
    derived_here: {
      P_atm: { value: d.P_atm, method: "P_mmHg / 760" },
      composition_sum: { value: d.composition_sum, method: "sum of the four printed mole fractions; not normalized" }
    },
    reported_measurement_uncertainty: {
      HiBMs_droplet_size_um: 50, LLUV_flame_size_um: 200, colour_flame_size_um: 250,
      coverage_factor: "not stated", distribution: "not specified",
      source: "S01 §3.1.2, §3.2.2, §3.3.2 (pp. 8–9)",
      applies_to: "image measurements of size, not to Table IX K"
    },
    data_quality_flags: OF.flagsFor(r.flex_test),
    source_discrepancies: ((OF.recordFor(r.flex_test) || {}).discrepancies || OF.annotationFor(r.flex_test).discrepancies || []).map(function (id) { return OF.discById[id]; }),
    literature_candidates: OF.annotationFor(r.flex_test).literature_candidates || [],
    claims: Object.keys(used).sort().map(function (id) { return OF.claimById[id]; }),
    sources: [OF.sourceById.S01],
    not_included: ["time series (see the DIGITIZED datasets in the repository, where available)", "uncertainty intervals (none computed)"].concat(
      OF.explore && OF.explore.on && OF.explore.last ? [] : ["simulation runs (Explore mode was off at export)"])
  };
  if (OF.explore && OF.explore.on && OF.explore.last && OF.explore.last.outputs) {
    var L = OF.explore.last;
    m.simulation_runs = [{ record_type: "SimulationRun", run_id: L.run_id, evidence_class: "NUMERICAL_SIMULATION",
      model: { name: OF.D2.NAME, version: OF.D2.VERSION, status: "EDUCATIONAL_BASELINE" },
      seeded_from_physical_test: L.seeded_from, inputs_modified_from_test: L.modified, inputs: L.inputs,
      outputs: { B: L.outputs.B, K_mm2_s: L.outputs.K_mm2_s, t_burn_s: L.outputs.t_burn_s, flame_standoff_ratio: L.outputs.flame_standoff_ratio,
        T_flame_K: L.outputs.T_flame_K, T_prop_K: L.outputs.T_prop_K, flags: L.outputs.flags },
      claims_scope: "Educational baseline; not a FLEX measurement; code-verified, not validated (CLM-056). Kept separate from `record`." }];
  }
  var blob = new Blob([JSON.stringify(m, null, 2)], { type: "application/json" });
  var url = URL.createObjectURL(blob), a = document.createElement("a");
  a.href = url; a.download = "OpenFLEX_" + r.flex_test + "_record_manifest.json";
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  OF.lastManifest = m;
  OF.toast("Exported JSON manifest for " + r.flex_test_as_printed + " (not an RO-Crate)");
  return m;
};
