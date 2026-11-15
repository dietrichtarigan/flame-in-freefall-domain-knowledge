// ---------------------------------------------------------------------------
// Open FLEX — share a simulation run, and check someone else's.
// Port of openflex/share.py (the reference); the tests check both directions on the same files.
// A run file has no personal data and no timestamps. "REPRODUCED" means the documented model gives the
// file's numbers from the file's inputs; it never means the model agrees with FLEX.
// Everything read from an imported file is untrusted: size-limited, validated, and escaped before display.
// ---------------------------------------------------------------------------
OF.share = (function () {
  var FORMAT = "OpenFLEXSharedRun", FORMAT_VERSION = "1.0", MAX_BYTES = 200000, REL_TOL = 1e-6;
  var SCOPE = "D²-law educational baseline run (NUMERICAL_SIMULATION). Not a FLEX measurement, not a prediction of extinction, and not validated against FLEX. Reproduced means the documented model gives these numbers from these inputs.";
  var TOP = ["record_type", "format_version", "labels", "run_id", "model", "seeded_from_physical_test", "modified_inputs", "inputs", "outputs", "comparison", "exported_by", "content_sha256"];
  var INPUT = ["fuel", "X", "D0_mm", "T_inf_K", "T_prop_K", "rho_l_at", "Q_variant", "P_atm", "T_prop_rule"];
  var OUT = ["B", "K_mm2_s", "t_burn_s", "flame_standoff_ratio", "T_flame_K", "T_prop_K"];
  var SPECIES = OF.D2.SPECIES;

  function isNum(x) { return typeof x === "number" && isFinite(x); }
  function r8(x) { return x === null || x === undefined ? null : +x.toPrecision(8); }
  function plain(o) { return JSON.parse(JSON.stringify(o)); }          // drops undefined so canonical JSON matches Python
  function close(a, b) { if (a === null || b === null || a === undefined || b === undefined) return (a === null || a === undefined) && (b === null || b === undefined); return Math.abs(a - b) <= REL_TOL * Math.max(Math.abs(b), 1e-30); }
  function sameSet(a, b) { a = (a || []).slice().sort(); b = b.slice().sort(); return a.length === b.length && a.every(function (x, i) { return x === b[i]; }); }
  function without(o, k) { var c = {}; Object.keys(o).forEach(function (x) { if (x !== k) c[x] = o[x]; }); return c; }
  async function sha(o) { return await OF.sha256Hex(OF.canonicalJSON(o)); }

  function inputProblem(inp) {
    if (!inp || typeof inp !== "object" || Array.isArray(inp)) return "inputs is not an object";
    var extra = Object.keys(inp).filter(function (k) { return INPUT.indexOf(k) < 0; });
    if (extra.length) return "unknown input fields: " + extra.sort().join(", ");
    if (inp.fuel !== "methanol" && inp.fuel !== "heptane") return "fuel must be methanol or heptane";
    var X = inp.X;
    if (!X || typeof X !== "object" || Array.isArray(X) || Object.keys(X).some(function (k) { return SPECIES.indexOf(k) < 0; })) return "X must hold O2, N2, CO2, He";
    var total = 0, bad = null;
    Object.keys(X).forEach(function (k) { var v = X[k]; if (v !== null && !(isNum(v) && v >= 0 && v <= 1)) bad = k; else total += v || 0; });
    if (bad) return "mole fraction " + bad + " outside 0–1";
    if (!(total > 0)) return "no ambient composition";
    if (inp.D0_mm !== null && inp.D0_mm !== undefined && !(isNum(inp.D0_mm) && inp.D0_mm > 0)) return "D0_mm must be positive";
    if (!(isNum(inp.T_inf_K) && inp.T_inf_K >= 200 && inp.T_inf_K <= 600)) return "T_inf_K must be 200–600 K";
    if (inp.T_prop_K !== undefined && inp.T_prop_K !== null && !(isNum(inp.T_prop_K) && inp.T_prop_K >= 300 && inp.T_prop_K <= 2000)) return "T_prop_K must be 300–2000 K";
    if (["boil", "298"].indexOf(inp.rho_l_at) < 0 || ["nominal", "low", "high"].indexOf(inp.Q_variant) < 0) return "rho_l_at or Q_variant has an unknown value";
    if (inp.P_atm !== undefined && inp.P_atm !== null && !(isNum(inp.P_atm) && inp.P_atm >= 0)) return "P_atm must be a non-negative number or null";
    if (inp.T_prop_rule !== undefined && !(typeof inp.T_prop_rule === "string" && inp.T_prop_rule.length <= 40)) return "T_prop_rule must be a short string";
    return null;
  }

  function modifiedKeys(seed, inp) {
    var m = [];
    if (inp.fuel !== seed.fuel) m.push("fuel");
    SPECIES.forEach(function (k) { if ((inp.X[k] || 0) !== (seed.X[k] || 0)) m.push("X." + k); });
    if (inp.D0_mm !== seed.D0_mm) m.push("D0_mm");
    if (inp.T_inf_K !== seed.T_inf_K) m.push("T_inf_K");
    if (inp.T_prop_K !== undefined && inp.T_prop_K !== null) m.push("T_prop_K");
    if (inp.Q_variant !== seed.Q_variant) m.push("Q_variant");
    if (inp.rho_l_at !== seed.rho_l_at) m.push("rho_l_at");
    return m;
  }

  var MODTEXT = { fuel: "fuel", "X.O2": "X_O2", "X.N2": "X_N2 (balance)", "X.CO2": "X_CO2", "X.He": "X_He", D0_mm: "D₀", T_inf_K: "T∞", T_prop_K: "fixed property temperature", Q_variant: "heating value", rho_l_at: "liquid-density temperature" };

  function comparison(row, inputs, seed, out) {
    var raw = row.K_mm2_s_raw || null, printed = row.K_mm2_s;
    var applies = modifiedKeys(seed, inputs).every(function (k) { return k === "D0_mm"; });
    return { printed_K_as_printed: raw, printed_basis: "Table IX, PUBLISHED TABULATED (comparison only, not validation)", applies: applies,
      model_over_printed: (applies && printed && out.K_mm2_s) ? r8(out.K_mm2_s / printed) : null };
  }

  function solveFor(inputs) { return OF.D2.solve(OF.D2.forSolve(inputs), OF.D.model.properties); }

  async function buildRun() {
    var L = OF.explore && OF.explore.last;
    if (!L || !L.outputs || L.outputs.K_mm2_s === null || !OF.hashAvailable()) return null;
    var row = OF.testById[L.seeded_from], seed = OF.D2.seededInputs(row), inputs = plain(L.inputs), V = OF.D.model.verification;
    if (inputProblem(inputs)) return null;
    var out = L.outputs, run = {
      record_type: FORMAT, format_version: FORMAT_VERSION,
      labels: { evidence_class: "NUMERICAL_SIMULATION", status: "EDUCATIONAL_BASELINE", scope: SCOPE },
      run_id: L.run_id,
      model: { name: OF.D2.NAME, version: OF.D2.VERSION, property_table_sha256: V.property_table_sha256, implementation_sha256: V.implementation_sha256 },
      seeded_from_physical_test: L.seeded_from, modified_inputs: modifiedKeys(seed, inputs), inputs: inputs,
      outputs: { B: r8(out.B), K_mm2_s: r8(out.K_mm2_s), t_burn_s: r8(out.t_burn_s), flame_standoff_ratio: r8(out.flame_standoff_ratio), T_flame_K: r8(out.T_flame_K), T_prop_K: r8(out.T_prop_K), flags: out.flags.slice() },
      comparison: comparison(row, inputs, seed, out), exported_by: "Open FLEX app build " + OF.D.build.build_id
    };
    run = plain(run);
    run.content_sha256 = await sha(run);
    return run;
  }

  // Reproduction check; same checks, ids and statuses as openflex.share.verify_run.
  async function verify(obj) {
    var checks = [], ok2load = false;
    function add(id, name, ok, detail) { checks.push({ id: id, name: name, pass: !!ok, detail: detail || "" }); return !!ok; }
    function done(status) { return { status: status, checks: checks, loadable: ok2load }; }
    if (!obj || typeof obj !== "object" || Array.isArray(obj) || obj.record_type !== FORMAT || obj.format_version !== FORMAT_VERSION) {
      add("F1", "file format", false, "not an " + FORMAT + " v" + FORMAT_VERSION + " file"); return done("INVALID");
    }
    var extra = Object.keys(obj).filter(function (k) { return TOP.indexOf(k) < 0; });
    if (!add("F1", "file format and fields", extra.length === 0, extra.length ? "unknown fields: " + extra.sort().join(", ") : "")) return done("INVALID");
    var lab = obj.labels || {};
    if (!add("F2", "labelled as a NUMERICAL_SIMULATION with a SIM- id (never a FLEX id)", lab.evidence_class === "NUMERICAL_SIMULATION" && /^SIM-[0-9a-f]{12}$/.test(String(obj.run_id)))) return done("INVALID");
    var prob = inputProblem(obj.inputs), seedId = obj.seeded_from_physical_test, row = OF.testById[seedId];
    if (!add("F3", "inputs within the model's range; seeding test exists in Table IX", !prob && !!row && /^FLEX-\d{3}$/.test(String(seedId)), prob || (!row ? "unknown test" : ""))) return done("INVALID");
    ok2load = true;
    if (!OF.hashAvailable()) { add("F4", "SHA-256 available in this browser context", false, "cannot recompute ids or hashes here"); return done("CANNOT_CHECK"); }
    var V = OF.D.model.verification, m = obj.model || {};
    var same = m.name === OF.D2.NAME && m.version === OF.D2.VERSION && m.property_table_sha256 === V.property_table_sha256 && m.implementation_sha256 === V.implementation_sha256;
    add("F4", "same model version, property table and implementation as this app", same, same ? "" : "file: " + OF.esc(m.name) + " " + OF.esc(m.version) + "; this app: " + OF.D2.NAME + " " + OF.D2.VERSION);
    add("F9", "content hash (detects accidental changes only; anyone can recompute it after editing)", obj.content_sha256 === await sha(without(obj, "content_sha256")));
    if (!same) return done("CANNOT_CHECK");
    var seed = OF.D2.seededInputs(row);
    add("F5", "list of modified inputs matches the inputs", sameSet(obj.modified_inputs, modifiedKeys(seed, obj.inputs)));
    var rid = await OF.D2.runId(obj.inputs, V.property_table_sha256);
    add("F6", "run id equals the hash of model version, inputs and property table", rid === obj.run_id, rid === obj.run_id ? "" : "recomputed " + rid);
    var out = solveFor(obj.inputs), fo = obj.outputs || {};
    var bad = OUT.filter(function (k) { return !close(fo[k], out[k]); });
    if (JSON.stringify(fo.flags) !== JSON.stringify(out.flags)) bad.push("flags");
    add("F7", "outputs equal a fresh run (relative tolerance 1e-6)", bad.length === 0, bad.join(", "));
    var c = comparison(row, obj.inputs, seed, out), fc = obj.comparison || {};
    add("F8", "printed-value comparison equals this app's Table IX", fc.printed_K_as_printed === c.printed_K_as_printed && fc.applies === c.applies && close(fc.model_over_printed, c.model_over_printed));
    return done(checks.every(function (x) { return x.pass; }) ? "REPRODUCED" : "NOT_REPRODUCED");
  }

  var EXPLAIN = {
    REPRODUCED: "The documented model gives these numbers from these inputs. This does not show that the model agrees with FLEX.",
    NOT_REPRODUCED: "The file's model matches this one, but at least one result, id, list or hash differs; the file was edited or made by faulty software.",
    CANNOT_CHECK: "The file was made with a different model version or property table (or SHA-256 is unavailable here); results may legitimately differ. Use the matching version to check it.",
    INVALID: "Not a usable run file."
  };

  function slug(name) { return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, ""); }

  function githubUrl() {
    var c = OF.D.share_config || {};
    if (typeof c.github_repo !== "string" || !/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9_.-]{1,100}$/.test(c.github_repo) || /^\.{1,2}$/.test(c.github_repo.split("/")[1])) return null;
    var u = "https://github.com/" + c.github_repo + "/discussions/new";
    return c.discussion_category ? u + "?category=" + encodeURIComponent(slug(c.discussion_category)) : u;
  }

  function f(v) { return v === null || v === undefined ? "—" : String(+(+v).toPrecision(5)); }

  function postText(run) {
    var I = run.inputs, X = I.X, mods = run.modified_inputs.length ? run.modified_inputs.map(function (k) { return MODTEXT[k] || k; }).join(", ") : "none (printed conditions)";
    var o = run.outputs, c = run.comparison;
    var title = "Open FLEX shared run " + run.run_id + " — D²-law baseline, seeded from " + run.seeded_from_physical_test + (run.modified_inputs.length ? " (modified)" : "");
    var body = [
      "**Shared simulation run — please try to reproduce it**",
      "",
      "This is a D²-law educational baseline SIMULATION, not a FLEX measurement and not validated against FLEX.",
      "",
      "- Run id: " + run.run_id,
      "- Seeded from the printed conditions of " + run.seeded_from_physical_test + " (NASA/TP-2015-216046, Table IX). Modified inputs: " + mods,
      "- Model: " + run.model.name + " " + run.model.version + " (property table SHA-256 " + run.model.property_table_sha256.slice(0, 12) + "…)",
      "- Inputs: " + I.fuel + "; X_O2 " + f(X.O2) + ", X_N2 " + f(X.N2) + ", X_CO2 " + f(X.CO2) + ", X_He " + f(X.He) + "; D0 " + f(I.D0_mm) + " mm; T∞ " + f(I.T_inf_K) + " K" + (I.T_prop_K ? "; property T " + f(I.T_prop_K) + " K" : ""),
      "- Results: K = " + f(o.K_mm2_s) + " mm²/s; B = " + f(o.B) + "; flame standoff ratio = " + f(o.flame_standoff_ratio) + "; T_flame = " + f(o.T_flame_K) + " K",
      "- Printed K (Table IX): " + (c.printed_K_as_printed || "—") + " mm²/s" + (c.applies ? " (model/printed = " + f(c.model_over_printed) + ")" : " (not compared: inputs differ from the test)") + ". A comparison, not validation.",
      "",
      "**How to check:** Open FLEX app → Physics & Results → Explore → \"Share this run, or check someone else's\" → paste the JSON below → Check; or `python3 -m openflex check-run run.json`.",
      "*Reproduced* means the model gives these numbers from these inputs. It does not mean the model agrees with FLEX. The run file contains no personal data.",
      "",
      "<details><summary>Run file (save as run.json)</summary>",
      "",
      "```json",
      JSON.stringify(run, null, 1),
      "```",
      "",
      "</details>"
    ].join("\n");
    return { title: title, body: body };
  }

  async function update() {
    var ex = document.getElementById("btn-share-export"), cp = document.getElementById("btn-share-copy"), ta = document.getElementById("share-post"), gh = document.getElementById("lnk-share-gh"), why = document.getElementById("share-why");
    if (!ex) return;
    var run = await buildRun();
    OF.share.current = run;
    ex.disabled = cp.disabled = !run;
    if (run) { var p = postText(run); ta.value = p.title + "\n\n" + p.body; why.textContent = ""; }
    else { ta.value = ""; why.textContent = OF.hashAvailable() ? "No run to share: the current inputs gave an error or no burning (see the status above)." : "SHA-256 is not available in this browser context, so run files cannot be made here."; }
    var u = githubUrl();
    gh.hidden = !u;
    if (u) gh.href = u;
    document.getElementById("share-gh-note").textContent = u
      ? "GitHub cannot pre-fill a Discussion from a link (to our knowledge), so copy the post text first, then paste it into the page that opens. The app itself makes no network request; the link opens only when you click it."
      : "No GitHub repository is set (data/registry/share_config.json), so only \"Copy post text\" is offered.";
  }

  function download(name, text) {
    var blob = new Blob([text], { type: "application/json" }), url = URL.createObjectURL(blob), a = document.createElement("a");
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  function parseLoose(text) {
    try { return JSON.parse(text); } catch (e) { /* maybe a whole post was pasted: take the outermost braces */ }
    var i = text.indexOf("{"), j = text.lastIndexOf("}");
    if (i >= 0 && j > i) { try { return JSON.parse(text.slice(i, j + 1)); } catch (e2) { /* fall through */ } }
    throw new Error("not JSON");
  }

  async function check(text) {
    var el = document.getElementById("share-result"), ld = document.getElementById("btn-share-load");
    OF.share.checked = null; ld.hidden = true;
    var obj, res;
    if (text.length > MAX_BYTES) res = { status: "INVALID", checks: [{ id: "F1", name: "file size", pass: false, detail: "larger than " + MAX_BYTES + " bytes" }], loadable: false };
    else {
      try { obj = parseLoose(text); } catch (e) { res = { status: "INVALID", checks: [{ id: "F1", name: "file is JSON", pass: false, detail: "could not be parsed" }], loadable: false }; }
      if (!res) { try { res = await verify(obj); } catch (e) { res = { status: "INVALID", checks: [{ id: "F1", name: "file could be checked", pass: false, detail: "unexpected content" }], loadable: false }; } }
    }
    var cls = { REPRODUCED: "badge-scope", NOT_REPRODUCED: "badge-danger", CANNOT_CHECK: "badge-warn", INVALID: "badge-danger" }[res.status];
    var facts = "";
    if (res.status !== "INVALID" && obj) {
      facts = '<p class="small">From the file: run <span class="mono">' + OF.esc(obj.run_id) + "</span>, seeded from <span class=\"mono\">" + OF.esc(obj.seeded_from_physical_test) + "</span>; modified inputs: " +
        OF.esc((obj.modified_inputs || []).map(function (k) { return MODTEXT[k] || k; }).join(", ") || "none") + "; exported by " + OF.esc(obj.exported_by) + ".</p>";
    }
    el.innerHTML = '<p><span class="badge ' + cls + '">' + OF.esc(res.status.replace("_", " ")) + "</span> " + OF.esc(EXPLAIN[res.status]) + "</p>" + facts +
      '<table aria-label="Reproduction checks"><thead><tr><th>ID</th><th>Check</th><th>Result</th></tr></thead><tbody>' +
      res.checks.map(function (c) { return '<tr><td class="mono">' + OF.esc(c.id) + "</td><td>" + OF.esc(c.name) + (c.detail ? '<br><span class="small">' + OF.esc(c.detail) + "</span>" : "") + '</td><td><span class="badge ' + (c.pass ? "badge-scope" : "badge-danger") + '">' + (c.pass ? "PASS" : "FAIL") + "</span></td></tr>"; }).join("") + "</tbody></table>";
    OF.share.lastResult = res;
    if (res.loadable) { OF.share.checked = obj; ld.hidden = false; }
    return res;
  }

  async function loadIntoExplore() {
    var o = OF.share.checked;
    if (!o || inputProblem(o.inputs) || !OF.testById[o.seeded_from_physical_test]) return;
    OF.switchTab("physics");
    await OF.selectTest(o.seeded_from_physical_test);
    if (!OF.explore.on) document.getElementById("mode-explore").click();
    var I = plain(o.inputs), g = function (k) { return document.getElementById(k); };
    g("ex-fuel").value = I.fuel; g("ex-o2").value = I.X.O2 || 0; g("ex-co2").value = I.X.CO2 || 0; g("ex-he").value = I.X.He || 0;
    g("ex-d0").value = I.D0_mm === null ? "" : I.D0_mm; g("ex-tinf").value = I.T_inf_K; g("ex-tprop").value = I.T_prop_K === undefined || I.T_prop_K === null ? "" : I.T_prop_K;
    g("ex-q").value = I.Q_variant; g("ex-rho").value = I.rho_l_at;
    OF.explore.inputs = I;
    await OF.exploreRun();
    OF.toast("Loaded the run's inputs into Explore");
  }

  function wire() {
    var g = function (k) { return document.getElementById(k); };
    if (!g("btn-share-export")) return;
    g("btn-share-export").addEventListener("click", function () {
      var run = OF.share.current; if (!run) return;
      download("OpenFLEX_run_" + run.run_id + ".json", JSON.stringify(run, null, 1) + "\n");
      OF.toast("Saved run file " + run.run_id + " (no personal data)");
    });
    g("btn-share-copy").addEventListener("click", async function () {
      var ta = g("share-post"), ok = false;
      try { await navigator.clipboard.writeText(ta.value); ok = true; } catch (e) { /* fall back below */ }
      if (!ok) { ta.focus(); ta.select(); try { ok = document.execCommand("copy"); } catch (e2) { ok = false; } }
      OF.toast(ok ? "Post text copied" : "Could not copy automatically: select the text and copy it");
    });
    g("share-file").addEventListener("change", function (e) {
      var file = e.target.files && e.target.files[0]; if (!file) return;
      if (file.size > MAX_BYTES) { g("share-paste").value = ""; check("x".repeat(MAX_BYTES + 1)); return; }
      var rd = new FileReader();
      rd.onload = function () { g("share-paste").value = String(rd.result); check(String(rd.result)); };
      rd.readAsText(file);
    });
    g("btn-share-check").addEventListener("click", function () { check(g("share-paste").value); });
    g("btn-share-load").addEventListener("click", loadIntoExplore);
  }

  return { buildRun: buildRun, verify: verify, check: check, update: update, wire: wire, postText: postText, githubUrl: githubUrl,
    inputProblem: inputProblem, modifiedKeys: modifiedKeys, current: null, checked: null, lastResult: null, MAX_BYTES: MAX_BYTES };
})();

OF.shareUpdate = function () { return OF.share.update(); };
