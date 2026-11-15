// ---------------------------------------------------------------------------
// Open FLEX — D²-law educational baseline, browser implementation.
// Line-for-line port of openflex/d2law.py (reference implementation, code-verified by
// tools/verify_d2law.py). The browser test suite checks this port against the Python
// run records for all Table IX tests. NUMERICAL_SIMULATION; never a FLEX measurement.
// ---------------------------------------------------------------------------
OF.D2 = (function () {
  var SPECIES = ["O2", "N2", "CO2", "He"];
  var VERSION = "1.0.0", NAME = "d2law-educational-baseline";

  function bisectRight(a, x) { var lo = 0, hi = a.length; while (lo < hi) { var mid = (lo + hi) >> 1; if (x < a[mid]) hi = mid; else lo = mid + 1; } return lo; }

  function interp(grid, values, T) {
    if (!(grid[0] <= T && T <= grid[grid.length - 1])) throw new Error("T=" + T + " outside property table");
    var i = Math.min(Math.max(bisectRight(grid, T) - 1, 0), grid.length - 2);
    var w = (T - grid[i]) / (grid[i + 1] - grid[i]);
    return values[i] + w * (values[i + 1] - values[i]);
  }

  function moleFractions(X) {
    var s = 0; SPECIES.forEach(function (k) { s += X[k] || 0; });
    if (!(s > 0)) throw new Error("no ambient composition");
    var x = {}; SPECIES.forEach(function (k) { x[k] = (X[k] || 0) / s; });
    return { x: x, sum: s };
  }

  function massFractions(table, x) {
    var M = 0, Y = {};
    SPECIES.forEach(function (k) { M += x[k] * table.species[k].M_kg_mol; });
    SPECIES.forEach(function (k) { Y[k] = x[k] * table.species[k].M_kg_mol / M; });
    return Y;
  }

  function mixtureCpK(table, x, T) {
    var grid = table.T_grid_K, sp = SPECIES.filter(function (k) { return x[k] > 0; });
    var M = {}, cp = {}, kk = {}, mu = {};
    sp.forEach(function (k) {
      var s = table.species[k];
      M[k] = s.M_kg_mol; cp[k] = interp(grid, s.cp_J_kgK, T); kk[k] = interp(grid, s.k_W_mK, T); mu[k] = interp(grid, s.mu_Pa_s, T);
    });
    var Y = massFractions(table, x), cpMix = 0, kMix = 0;
    sp.forEach(function (k) { cpMix += Y[k] * cp[k]; });
    sp.forEach(function (i) {
      var den = 0;
      sp.forEach(function (j) {
        var phi = Math.pow(1 + Math.sqrt(mu[i] / mu[j]) * Math.pow(M[j] / M[i], 0.25), 2) / Math.sqrt(8 * (1 + M[i] / M[j]));
        den += x[j] * phi;
      });
      kMix += x[i] * kk[i] / den;
    });
    return { cp: cpMix, k: kMix };
  }

  // inputs: {fuel, X:{O2,N2,CO2,He}, D0_mm, T_inf_K, T_prop_K?, rho_l_at?, Q_variant?}
  function solve(inputs, table) {
    var f = table.fuels[inputs.fuel], flags = [];
    var mf = moleFractions(inputs.X), x = mf.x;
    if (Math.abs(mf.sum - 1) > 1e-6) flags.push("mole fractions summed to " + mf.sum.toFixed(4) + "; normalised");
    var YO = massFractions(table, x).O2, nu = f.nu_O2_per_fuel_mass, Ts = f.T_boil_K, L = f.L_v_at_boil_J_kg;
    var rho = (inputs.rho_l_at || "boil") === "boil" ? f.rho_l_at_boil_kg_m3 : f.rho_l_298_kg_m3;
    var qv = inputs.Q_variant || "nominal";
    var Q = qv === "nominal" ? f.Q_lhv_vapour_J_kg : (qv === "low" ? f.Q_lhv_vapour_range_J_kg[0] : f.Q_lhv_vapour_range_J_kg[1]);
    var Tinf = inputs.T_inf_K, grid = table.T_grid_K, lo = grid[0], hi = grid[grid.length - 1];
    function at(Tp) {
      var g = mixtureCpK(table, x, Tp);
      var B = (g.cp * (Tinf - Ts) + Q * YO / nu) / L;
      return { cp: g.cp, k: g.k, B: B, Tf: B > 0 ? Ts + (L / g.cp) * ((1 + B) / (1 + YO / nu) - 1) : null };
    }
    var Tp, s, it = 0;
    if (inputs.T_prop_K !== undefined && inputs.T_prop_K !== null) { Tp = +inputs.T_prop_K; s = at(Tp); }
    else {
      Tp = 1000.0;
      for (;;) {
        it++;
        s = at(Tp);
        var target = s.Tf !== null ? (Ts + s.Tf) / 2 : lo, nw = Math.min(Math.max(target, lo), hi);
        if (Math.abs(nw - Tp) < 1e-9 || it >= 200) { Tp = nw; s = at(Tp); break; }
        Tp = nw;
      }
      if (it >= 200) flags.push("property-temperature iteration did not converge");
      if (s.Tf !== null && !(lo <= (Ts + s.Tf) / 2 && (Ts + s.Tf) / 2 <= hi)) flags.push("property temperature limited to the table range");
    }
    var out = { Y_O2_inf: YO, nu: nu, T_s_K: Ts, L_J_kg: L, rho_l_kg_m3: rho, Q_J_kg: Q, T_prop_K: Tp, cp_J_kgK: s.cp, k_W_mK: s.k, B: s.B, iterations: it, flags: flags };
    if (s.B <= 0) {
      flags.push("B <= 0: no burning in this model (outside scope)");
      out.K_mm2_s = out.flame_standoff_ratio = out.T_flame_K = out.t_burn_s = null;
      return out;
    }
    out.K_mm2_s = 8 * s.k / (rho * s.cp) * Math.log1p(s.B) * 1e6;
    out.ln1pB = Math.log1p(s.B);
    out.T_flame_K = s.Tf;
    out.flame_standoff_ratio = YO > 0 ? Math.log1p(s.B) / Math.log1p(YO / nu) : null;
    out.t_burn_s = inputs.D0_mm ? inputs.D0_mm * inputs.D0_mm / out.K_mm2_s : null;
    return out;
  }

  // Inputs exactly as tools/run_d2law_baseline.py builds them for a Table IX row (so run ids match).
  function seededInputs(r) {
    var X = { O2: r.X_O2, N2: r.X_N2, CO2: r.X_CO2, He: r.X_He };
    return { fuel: r.fuel, X: X, D0_mm: r.D0_mm, T_inf_K: 298.15,
      P_atm: r.P_mmHg ? Math.round(r.P_mmHg / 760 * 1e6) / 1e6 : null,
      rho_l_at: "boil", Q_variant: "nominal", T_prop_rule: "(T_s+T_f)/2, iterated" };
  }

  function forSolve(inputs) {
    var X = {}; SPECIES.forEach(function (k) { X[k] = inputs.X[k] || 0; });
    var o = {}; Object.keys(inputs).forEach(function (k) { o[k] = inputs[k]; }); o.X = X;
    return o;
  }

  async function runId(inputs, tableSha) {
    var h = await OF.sha256Hex(OF.canonicalJSON({ model: VERSION, inputs: inputs, table: tableSha }));
    return h ? "SIM-" + h.slice(0, 12) : null;
  }

  return { solve: solve, interp: interp, mixtureCpK: mixtureCpK, seededInputs: seededInputs, forSolve: forSolve, runId: runId,
    VERSION: VERSION, NAME: NAME, SPECIES: SPECIES };
})();

// Explore mode is offered only when the embedded code-verification record says PASS and was made
// from the same implementation and property table that this build embeds.
OF.modelAvailable = function () {
  var m = OF.D.model;
  if (!m) return { ok: false, why: "No model is embedded in this build." };
  if (!m.verification_current) return { ok: false, why: "The code-verification record does not match the embedded model files; Explore mode is disabled." };
  if (m.verification.status !== "PASS") return { ok: false, why: "Code verification did not pass; Explore mode is disabled." };
  return { ok: true, why: "" };
};
