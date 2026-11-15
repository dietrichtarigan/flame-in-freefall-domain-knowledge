// ---------------------------------------------------------------------------
// Open FLEX — burn timeline engine (Phase B M5). No DOM, no THREE: pure data → state.
//
// OF.Timeline.build(testId) returns an object whose state(t) gives, for time t in seconds since the
// igniters were turned ON (time zero of Table IX and Appendix B, CLM-018):
//   droplet: { D_mm, source }               source ∈ DIGITIZED | RECONSTRUCTED | PRINTED_D0 | NONE
//   flame:   { present, visible_D_mm, lluv_D_mm, size_source, soot, dim }
//   events passed, and a provenance list.
//
// Rules (each one stated in the UI; nothing here is a combustion model):
//  * Droplet, digitized test: running median of the digitized D² within ±HALF s, D = sqrt(D²).
//  * Droplet, other tests: D² = D0² − K·t for 0 ≤ t ≤ t_b, using the printed D0 and K — the TP's own
//    linear-fit description of K (CLM-019). Before t = 0 the droplet is shown at D0.
//  * End of the burn at the printed 'Burn time' t_b (its definition is not given in the TP, DSC-024):
//      Extinction → flame off; droplet frozen at the reconstructed size (post-extinction vaporization is
//                   not reconstructed). Digitized tests keep following the digitized D².
//      Completion → droplet D → 0 at t_b.      Disruption → droplet removed at t_b (disruption event).
//  * Flame size only from DIGITIZED flame series (colour camera = visible edge; LLUV = OH* outer edge,
//    CLM-013, CLM-014). Where no data exist at time t the size is null and the UI draws an unscaled glyph.
//  * Flame appearance only from the test's own caption (keyword flags, DERIVED from NASA text); soot is drawn
//    inside the blue envelope as the TP reports (CLM-045), with no radius.
//  * Spherical shape: microgravity removes buoyant convection (CLM-016, CLM-043); flame edges are outer edges (CLM-046).
// ---------------------------------------------------------------------------
OF.Timeline = (function () {
  var HALF = 0.25;   // s, half-width of the display running median (a display choice, not an analysis)

  function median(a) {
    if (!a.length) return null;
    var s = a.slice().sort(function (x, y) { return x - y; }), m = s.length >> 1;
    return s.length % 2 ? s[m] : 0.5 * (s[m - 1] + s[m]);
  }

  function series(dig, name) {
    if (!dig) return null;
    var s = dig.series.filter(function (x) { return x.name === name; })[0];
    if (!s) return null;
    var idx = s.t.map(function (_, i) { return i; }).sort(function (a, b) { return s.t[a] - s.t[b]; });
    return { t: idx.map(function (i) { return s.t[i]; }), v: idx.map(function (i) { return s.v[i]; }), dataset_id: s.dataset_id };
  }

  var BRIDGE = 0.75;  // s; detection gaps up to this distance on each side are bridged by linear interpolation
  // Returns { v, interp } or null. Running median within ±HALF; otherwise linear interpolation between the
  // nearest digitized points before and after t if both lie within BRIDGE (dense trails are sampled with gaps).
  // Longer gaps (e.g. droplet out of the camera view) stay gaps.
  function windowMedian(S, t) {
    if (!S) return null;
    var vals = [], lo = -1, hi = -1;
    for (var i = 0; i < S.t.length; i++) {
      if (Math.abs(S.t[i] - t) <= HALF) vals.push(S.v[i]);
      if (S.t[i] <= t) lo = i; else if (hi < 0) hi = i;
    }
    if (vals.length) return { v: median(vals), interp: false };
    if (lo >= 0 && hi >= 0 && t - S.t[lo] <= BRIDGE && S.t[hi] - t <= BRIDGE) {
      var f = (t - S.t[lo]) / (S.t[hi] - S.t[lo]);
      return { v: S.v[lo] + f * (S.v[hi] - S.v[lo]), interp: true };
    }
    return null;
  }
  function val(x) { return x === null ? null : x.v; }

  function captionFlags(caption) {
    var c = (caption || "").toLowerCase();
    var fr = null, m = c.match(/(one-third|one-quarter|halfway|two-thirds|three-quarters) (of the way )?(through|into)?/);
    if (m) fr = { "one-quarter": 0.25, "one-third": 1 / 3, "halfway": 0.5, "two-thirds": 2 / 3, "three-quarters": 0.75 }[m[1]];
    var luminous = /soot|luminous|yellow/.test(c);
    var toBlue = /(dimmed to blue|then dim blue|dim blue flame surrounded|luminous flame disappeared|disappeared abruptly)/.test(c);
    return {
      soot_or_luminous: luminous, luminous_ends: toBlue, luminous_end_fraction: toBlue ? fr : null,
      dim: /very dim|dim flame|flame was dim|barely detectable|almost undetectable/.test(c),
      cool_flame_inferred: /cool flame/.test(c), fiber: /fiber-supported/.test(c)
    };
  }

  function build(id) {
    var r = OF.testById[id], dig = (OF.D.digitized || {})[id], fig = OF.D.figures[id];
    var D2 = series(dig, "droplet_d2"), COL = series(dig, "color_camera_flame_diameter"), UV = series(dig, "lluv_flame_diameter");
    var D0 = r.D0_mm, K = r.K_mm2_s, tb = r.t_burn_s, end = r.test_end;
    var flags = captionFlags(fig ? fig.caption_verbatim : "");
    var prov = [];
    if (D2) prov.push({ what: "droplet size", source: "DIGITIZED " + D2.dataset_id + " (running median ±" + HALF + " s; detection gaps ≤ " + BRIDGE + " s each side interpolated; display only)" });
    else if (D0 !== null && K !== null && tb !== null) prov.push({ what: "droplet size", source: "RECONSTRUCTED: D² = D0² − K·t from printed Table IX D0 = " + r.D0_mm_raw + " mm, K = " + r.K_mm2_s_raw + " mm²/s (CLM-019)" });
    else prov.push({ what: "droplet size", source: D0 !== null ? "PRINTED D0 only (K or burn time not printed)" : "NONE (D0 not printed)" });
    if (COL || UV) prov.push({ what: "flame size", source: "DIGITIZED " + [COL, UV].filter(Boolean).map(function (s) { return s.dataset_id; }).join(", ") + " (running median ±" + HALF + " s)" });
    else prov.push({ what: "flame size", source: "NOT AVAILABLE — flame drawn as an unscaled marker" });
    prov.push({ what: "flame appearance", source: fig ? "Caption keywords, App. B Fig. " + fig.figure + " (DERIVED from NASA text)" : "no caption" });
    prov.push({ what: "end of burn", source: "Table IX burn time " + r.t_burn_s_raw + " s (definition not stated, DSC-024) and test end '" + end + "'" });

    var tEnd = tb !== null ? tb : (D2 ? D2.t[D2.t.length - 1] : 0);
    var tMax = Math.max(tEnd, D2 ? D2.t[D2.t.length - 1] : 0) + 1.5;
    var tStart = Math.min(-1.5, D2 ? D2.t[0] : -1.5);
    // flame shown from the first digitized flame point (not before t = 0); without flame data, from t = 0
    var firsts = [COL, UV].filter(function (s) { return s && s.t.length; }).map(function (s) { return s.t[0]; });
    var flameT0 = firsts.length ? Math.max(0, Math.min.apply(null, firsts)) : 0;

    function reconstructedD2(t) {
      if (D0 === null) return null;
      if (t <= 0 || K === null) return D0 * D0;
      var tt = tb !== null ? Math.min(t, tb) : t;
      return Math.max(0, D0 * D0 - K * tt);
    }

    function state(t) {
      var burnOver = tb !== null && t > tb;
      // droplet
      var d2, dsrc;
      if (D2) {
        var w = windowMedian(D2, t);
        d2 = val(w);
        dsrc = w !== null ? (w.interp ? "DIGITIZED_INTERP" : "DIGITIZED") : (t < D2.t[0] ? "BEFORE_DATA" : "GAP_OR_AFTER_DATA");
      } else {
        d2 = reconstructedD2(t);
        dsrc = d2 === null ? "NONE" : (K === null || t <= 0 ? "PRINTED_D0" : "RECONSTRUCTED");
      }
      var removed = false;
      if (burnOver && end === "Disruption") { removed = true; }
      if (burnOver && end === "Completion" && !D2) { d2 = 0; }
      var D = (d2 === null || removed) ? null : Math.sqrt(Math.max(0, d2));
      // flame
      var present = t >= flameT0 && tb !== null && t <= tb;
      var vis = present ? val(windowMedian(COL, t)) : null, uv = present ? val(windowMedian(UV, t)) : null;
      var soot = present && flags.soot_or_luminous && !(flags.luminous_ends && flags.luminous_end_fraction !== null && t > flags.luminous_end_fraction * tb);
      return {
        t: t,
        droplet: { D_mm: D, source: removed ? "REMOVED_AT_DISRUPTION" : dsrc },
        flame: { present: present, visible_D_mm: vis, lluv_D_mm: uv,
          size_source: (vis !== null || uv !== null) ? "DIGITIZED" : (present ? "NOT_AVAILABLE" : "NONE"),
          soot: soot, dim: present && flags.dim },
        igniters_on: t >= 0 && t < 0.5,          // duration not reported: animation timing illustrative
        phase: t < 0 ? "pre-ignition" : (present ? "burning" : (burnOver ? "after end of burn" : "ignition"))
      };
    }

    var events = [{ t: 0, label: "Igniters ON (time zero, CLM-018)" }];
    if (tb !== null) events.push({ t: tb, label: (end === "Extinction" ? "Visible flame extinction" : end === "Completion" ? "Burned to completion" : "Disruption") + " at printed burn time " + r.t_burn_s_raw + " s" + (end === "Extinction" && r.D_ext_visible_mm !== null ? " (printed extinction diameter " + r.D_ext_visible_mm_raw + " mm)" : "") });
    if (flags.cool_flame_inferred) events.push({ t: tb !== null ? tb : 0, label: "Caption infers cool-flame burning after extinction (not visible; not drawn)" });
    var check = null;
    if (!D2 && D0 !== null && K !== null && tb !== null && r.D_ext_visible_mm !== null && end === "Extinction") {
      var recon = Math.sqrt(Math.max(0, D0 * D0 - K * tb));
      check = { reconstructed_D_at_tb_mm: Math.round(recon * 1000) / 1000, printed_D_ext_mm: r.D_ext_visible_mm,
        note: "Reconstruction from D0 and K vs printed extinction diameter; a difference shows the limits of the linear model, not an error in either value." };
    }
    return { id: id, tStart: tStart, tMax: tMax, tb: tb, end: end, flags: flags, events: events, provenance: prov,
      consistency: check, hasDigitizedDroplet: !!D2, hasFlameSize: !!(COL || UV), state: state };
  }

  return { build: build, HALF: HALF, BRIDGE: BRIDGE, captionFlags: captionFlags, windowMedian: windowMedian };
})();
