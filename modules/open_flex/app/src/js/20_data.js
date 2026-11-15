// ---------------------------------------------------------------------------
// Open FLEX — data access. All values come from window.OPEN_FLEX_DATA, which
// the build embeds from files under data/ (see tools/build_app.py and
// data/MANIFEST.json). Nothing in this file creates scientific values.
// ---------------------------------------------------------------------------
OF.D = window.OPEN_FLEX_DATA;

OF.testById = {};
OF.D.table_ix.forEach(function (r) { OF.testById[r.flex_test] = r; });

OF.claimById = {};
OF.D.claims.claims.forEach(function (c) { OF.claimById[c.claim_id] = c; });

OF.sourceById = {};
OF.D.sources.sources.forEach(function (s) { OF.sourceById[s.source_id] = s; });

OF.discById = {};
OF.D.discrepancies.discrepancies.forEach(function (d) { OF.discById[d.discrepancy_id] = d; });

OF.testNumber = function (id) { return parseInt(id.slice(5), 10); };

// Flags that apply to a test, from data/registry/test_annotations.json.
OF.flagsFor = function (id) {
  var A = OF.D.annotations, n = OF.testNumber(id), out = [];
  A.global_flags.forEach(function (f) { out.push(f); });
  A.range_flags.forEach(function (f) { if (n >= f.first && n <= f.last) out.push(f); });
  var r = OF.testById[id];
  ["K_mm2_s", "t_burn_s", "D0_mm", "D_ext_visible_mm"].forEach(function (k) {
    if (r[k + "_approx"]) out.push({ flag: "APPROXIMATE_CELL", text: "Table IX prints '" + r[k + "_raw"] + "' (approximate) for " + k + ".", claims: [] });
  });
  return out;
};

OF.annotationFor = function (id) { return OF.D.annotations.tests[id] || {}; };

// Derived quantities: transparent arithmetic on printed values, labelled DERIVED.
OF.derived = function (r) {
  var sum = null, parts = [r.X_O2, r.X_N2, r.X_CO2, r.X_He];
  if (parts.every(function (x) { return x !== null; })) sum = parts.reduce(function (a, b) { return a + b; }, 0);
  return {
    P_atm: r.P_mmHg === null ? null : r.P_mmHg / 760,
    composition_sum: sum
  };
};

OF.fmtRaw = function (raw) { return raw === "–" ? "– (not reported)" : raw; };

// M2 records (data/records/*.json, built by tools/build_records.py).
OF.recordFor = function (id) { return (OF.D.records || {})[id] || null; };
OF.literatureFor = function (id) {
  return ((OF.D.literature_cases || {}).cases || []).filter(function (c) { return c.linked_physical_test.test_id === id; });
};
