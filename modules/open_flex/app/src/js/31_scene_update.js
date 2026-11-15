// ---------------------------------------------------------------------------
// Open FLEX — procedure + burn playback (Phase B M5).
// The scrubber has three segments:
//   [0, PRE)        test-point procedure stages 1 … 5c-ii (TP §2.3), discrete, NOT to time scale
//   [PRE, POST)     real time in seconds since igniters ON (time zero, CLM-018), from tStart to tMax,
//                   driven by OF.Timeline (data, reconstruction or "not available")
//   [POST, 1]       stages 5c-v and 6 (stop recording, post-test), discrete
// ---------------------------------------------------------------------------
OF.STAGES = [
  { key: "activate_cir", label: "1 Activate CIR", tp: "§2.3 (1)", text: "CIR operators activate the rack and perform housekeeping for test-point operations." },
  { key: "foma_fill", label: "2 Fill chamber (FOMA)", tp: "§2.3 (2)", text: "The FOMA fills the CIR chamber to the target pressure and composition. Pressure histories are recorded so the actual composition can be computed afterwards (Table IX composition is this reconstruction: CLM-020)." },
  { key: "activate_mdca", label: "3 Activate MDCA", tp: "§2.3 (3)", text: "The MDCA is activated; all MDCA commands pass through the CIR computers." },
  { key: "purge", label: "4 Open valve, purge line", tp: "§2.3 (4)", text: "The operator advances the syringe stepper motor until fuel visibly appears at the needle." },
  { key: "dispense", label: "5a Dispense droplet", tp: "§2.3 (5)(a)", text: "Fuel is dispensed between the opposed needles. Stepper counts are used only as a guide; the operator estimates droplet size with the science team. The white LED is on for the colour camera (CLM-048)." },
  { key: "stretch", label: "5b Stretch", tp: "§2.3 (5)(b)", text: "Needles are slowly moved apart to slightly less than the separation at which fuel would pull off one needle (manual judgement)." },
  { key: "record_on", label: "5c-i Start recording", tp: "§2.3 (5)(c)(i)", text: "HiBMs, LLUV and MDCA colour cameras begin recording. The colour-camera LED is turned off; the HiBMs backlight stays on." },
  { key: "deploy", label: "5c-ii Deploy", tp: "§2.3 (5)(c)(ii)", text: "Needles retract rapidly and simultaneously, ideally leaving a motionless droplet; it becomes spherical within about 1 s (CLM-044). In practice droplets had residual velocity and drifted (CLM-016) — drift is not shown." },
  { key: "ignite", label: "5c-iii Ignite (t = 0)", tp: "§2.3 (5)(c)(iii); App. A.1", text: "Hot-wire igniters are turned on for a preset time and power. This instant is time zero for Table IX D₀ and Appendix B plots (CLM-018). The on-time is not reported; the 0.5 s shown is illustrative." },
  { key: "igniter_retract", label: "5c-iv Igniters off & retract", tp: "§2.3 (5)(c)(iv)", text: "Igniters are turned off and rapidly retracted a relatively large distance from the droplet." },
  { key: "burn", label: "Burning (data-driven)", tp: "interpretive", text: "Not a numbered TP step. Droplet and flame follow the data shown in the readout panel, with the source of each value; the burn ends at the printed burn time by extinction, disruption or completion (Table IX 'Test end')." },
  { key: "record_off", label: "5c-v Stop recording", tp: "§2.3 (5)(c)(v)", text: "Cameras stop after a preset time, typically on the order of 40 s (CLM-021)." },
  { key: "post", label: "6 Post-test", tp: "§2.3 (6)", text: "Housekeeping. If another test uses the same atmosphere, the chamber fan runs about 1 min to mix the gases." }
];
OF.PRE = 0.30; OF.POST = 0.95;
OF.N_PRE = 7;                       // stages 0..6 in the pre segment (deploy happens at the start of real time)
OF.anim = { p: OF.PRE, playing: false, speed: 1 };

OF.timeline = null;
OF.loadTimeline = function (id) {
  OF.timeline = OF.Timeline.build(id);
  OF.renderTimelineInfo();
  OF.updateScene();
};

OF.tOfP = function (p) {                         // seconds, or null in the discrete segments
  var T = OF.timeline;
  if (!T || p < OF.PRE || p >= OF.POST) return null;
  return T.tStart + (p - OF.PRE) / (OF.POST - OF.PRE) * (T.tMax - T.tStart);
};
OF.pOfT = function (t) {
  var T = OF.timeline;
  return OF.PRE + (t - T.tStart) / (T.tMax - T.tStart) * (OF.POST - OF.PRE);
};
OF.stageIndex = function (p) {
  if (p < OF.PRE) return Math.min(OF.N_PRE - 1, Math.floor(p / OF.PRE * OF.N_PRE));
  if (p >= OF.POST) return p >= OF.POST + (1 - OF.POST) / 2 ? 12 : 11;
  var t = OF.tOfP(p), T = OF.timeline;
  if (t < 0) return 7;
  if (t < 0.5) return 8;
  if (t < 1.0) return 9;
  if (T.tb !== null && t > T.tb) return 11;
  return 10;
};

OF.renderStagePills = function () {
  var c = document.getElementById("stage-pills");
  c.innerHTML = OF.STAGES.map(function (s, i) {
    return '<button class="stage-pill" data-i="' + i + '" onclick="OF.jumpStage(' + i + ')">' + OF.esc(s.label) + "</button>";
  }).join("");
};
OF.jumpStage = function (i) {
  var p;
  if (i < OF.N_PRE) p = (i + 0.5) / OF.N_PRE * OF.PRE;
  else if (i === 7) p = OF.pOfT(Math.max(OF.timeline.tStart, -0.75));
  else if (i === 8) p = OF.pOfT(0.05);
  else if (i === 9) p = OF.pOfT(0.6);
  else if (i === 10) p = OF.pOfT(Math.min(1.5, OF.timeline.tb !== null ? OF.timeline.tb * 0.3 : 1.5));
  else if (i === 11) p = OF.POST + 0.01;
  else p = 0.999;
  OF.anim.playing = false; OF.setPlayLabel();
  OF.scrub(p);
};
OF.stepStage = function (d) { OF.jumpStage(Math.max(0, Math.min(OF.STAGES.length - 1, OF.stageIndex(OF.anim.p) + d))); };
OF.setPlayLabel = function () { var b = document.getElementById("btn-play"); b.textContent = OF.anim.playing ? "Pause" : "Play"; b.setAttribute("aria-pressed", OF.anim.playing ? "true" : "false"); };
OF.togglePlay = function () {
  OF.anim.playing = !OF.anim.playing;
  if (OF.anim.playing && OF.anim.p >= 0.999) OF.anim.p = 0;
  OF.setPlayLabel();
};
OF.setSpeed = function (v) { OF.anim.speed = parseFloat(v); };
OF.scrub = function (p) { OF.anim.p = Math.max(0, Math.min(1, p)); OF.updateScene(); };

// Called by the animation loop: discrete stages advance at one per 1.5 s of wall time; real time at speed × 1.
OF.advance = function (dt) {
  var p = OF.anim.p;
  if (p < OF.PRE || p >= OF.POST) p += dt / 1.5 * (p < OF.PRE ? OF.PRE / OF.N_PRE : (1 - OF.POST) / 2);
  else { var T = OF.timeline; p += dt * OF.anim.speed / (T.tMax - T.tStart) * (OF.POST - OF.PRE); }
  if (p >= 1) { p = 1; OF.anim.playing = false; OF.setPlayLabel(); }
  OF.anim.p = p;
  OF.updateScene();
};

// State shown at scrubber position p. In discrete segments a representative time is used.
OF.stateAt = function (p) {
  var T = OF.timeline, t = OF.tOfP(p);
  if (t === null) t = p < OF.PRE ? T.tStart : T.tMax;
  return T.state(t);
};

OF.fmtMm = function (x) { return x === null || x === undefined ? "—" : x.toFixed(2) + " mm"; };

OF.updateScene = function () {
  if (!OF.timeline) return;
  var p = OF.anim.p, i = OF.stageIndex(p), s = OF.STAGES[i], T = OF.timeline, t = OF.tOfP(p);
  var st = OF.stateAt(p), pre = p < OF.PRE;
  document.getElementById("time-scrubber").value = p;
  document.getElementById("time-scrubber").setAttribute("aria-valuetext", t === null ? s.label : "t = " + t.toFixed(2) + " s since igniters ON");
  document.getElementById("time-readout").textContent = t === null ? "Procedure stage (not to time scale)" : "t = " + (t >= 0 ? "+" : "") + t.toFixed(2) + " s since igniters ON";
  document.getElementById("regime-readout").textContent = s.label;
  document.querySelectorAll(".stage-pill").forEach(function (el) {
    var on = parseInt(el.dataset.i, 10) === i;
    el.classList.toggle("active", on);
    el.setAttribute("aria-current", on ? "step" : "false");
  });
  if (OF._lastStage !== i) {
    OF._lastStage = i;
    if (OF.HOTSPOTS && document.querySelector(".chip")) OF.selectHotspot(OF.activeHotspot);
    var sd = document.getElementById("stage-detail");
    sd.removeAttribute("data-source"); sd.removeAttribute("data-interpretive");
    sd.setAttribute(s.tp === "interpretive" ? "data-interpretive" : "data-source", s.tp === "interpretive" ? "procedure illustration" : "S01 " + s.tp);
    sd.innerHTML = "<strong>" + OF.esc(s.label) + "</strong> <span class='mono small'>[" + OF.esc(s.tp === "interpretive" ? "interpretive, not a TP step" : "S01 " + s.tp) + "]</span><br/>" + OF.esc(s.text);
  }
  // live readouts (every value names its source)
  var droplet = pre ? (i >= 4 ? { D_mm: T.state(T.tStart).droplet.D_mm, source: "shown at the starting size (not measured during formation)" } : { D_mm: null, source: "not yet dispensed" }) : st.droplet;
  var flame = (pre || p >= OF.POST) ? { present: false } : st.flame;
  var srcTxt = { DIGITIZED: "DIGITIZED (App. B plot)", DIGITIZED_INTERP: "DIGITIZED (interpolated across a short detection gap)", RECONSTRUCTED: "RECONSTRUCTED from printed D₀ and K", PRINTED_D0: "PRINTED D₀ (Table IX)", NONE: "not available", BEFORE_DATA: "before first digitized point", GAP_OR_AFTER_DATA: "no digitized point at this time (gap or droplet out of view)", REMOVED_AT_DISRUPTION: "droplet disrupted (Table IX test end)" };
  document.getElementById("ro-droplet").textContent = OF.fmtMm(droplet.D_mm);
  document.getElementById("ro-droplet-src").textContent = srcTxt[droplet.source] || droplet.source;
  document.getElementById("ro-flame").textContent = !flame.present ? "no flame" : (flame.visible_D_mm !== null ? OF.fmtMm(flame.visible_D_mm) + " (visible edge)" : (flame.lluv_D_mm !== null ? "—" : "present, size not measured"));
  document.getElementById("ro-lluv").textContent = flame.present && flame.lluv_D_mm !== null ? OF.fmtMm(flame.lluv_D_mm) : "—";
  document.getElementById("ro-flame-src").textContent = !flame.present ? "—" : (flame.size_source === "DIGITIZED" ? "DIGITIZED (App. B plot)" : "NOT AVAILABLE — unscaled marker shown");
  document.getElementById("ro-appearance").textContent = !flame.present ? "—" : (flame.soot ? "soot luminosity reported in caption (drawn inside the blue envelope, CLM-045)" : "no soot luminosity reported for this time") + (flame.dim ? "; caption: dim flame" : "");
  document.getElementById("ro-phase").textContent = pre ? "procedure" : st.phase;

  if (!threeReady) { OF.drawFallback(i, droplet, flame, st); return; }
  var P = OF.SCENE, S = OF.S;
  // needles: together → stretched → retracted at deploy (time scale illustrative)
  var D0 = droplet.D_mm || (T.state(T.tStart).droplet.D_mm || 3);
  var gap;
  if (i < 4) gap = 0.6; else if (i === 4) gap = D0 * 0.35; else if (i === 5 || i === 6) gap = D0 * 0.45;
  else { var tt = t === null ? 99 : t - T.tStart; gap = D0 * 0.45 + Math.min(1, tt / 0.3) * P.needleRetract; }
  S.needles.forEach(function (n) { n.g.position.set(n.s * gap, 0, 0); });
  // igniters: in place before ignition; incandescent from t = 0 (on-time 0.5 s, not reported: illustrative),
  // then retracted and cooling. Cooling shown as exp(−Δt / 0.6 s): an illustrative time constant, not data.
  var ign = 0;
  if (!pre && t !== null && t >= 0) ign = t < 0.5 ? 1 : Math.exp(-(t - 0.5) / 0.6);
  if (p >= OF.POST) ign = 0;
  var retract = !pre && t !== null && t >= 0.5 ? Math.min(1, (t - 0.5) / 0.4) : 0;
  if (p >= OF.POST) retract = 1;
  S.igniters.forEach(function (g) {
    g.g.position.copy(g.dir.clone().multiplyScalar(P.igniterDist + retract * P.igniterRetract));
    var m = g.loop.material;
    m.emissive.setRGB(1.0 * ign, 0.52 * ign, 0.22 * ign); m.emissiveIntensity = 1 + 7 * ign;
    g.glow.intensity = 2.5 * ign;
  });
  // fiber (only for tests the sources mark fiber-supported)
  var fiberShown = OF.timeline.fiber === true && i >= 4;
  S.fiber.visible = fiberShown; S.fiberHolder.visible = OF.timeline.fiber === true;
  // droplet (true size)
  S.droplet.visible = droplet.D_mm !== null && droplet.D_mm > 0;
  if (S.droplet.visible) S.droplet.scale.setScalar(droplet.D_mm);
  S.droplet.material = S.dropGlass;
  S.dropGlass.ior = /heptane/i.test(OF.testById[OF.timeline.id].fuel) ? 1.39 : 1.33;
  // Under LED light: refracting glass bead (transmission). In the flame-lit chamber the transmission buffer
  // holds only the dark hardware, so the droplet is drawn as faint clear glass with highlights instead.
  var lit = i <= 5;
  S.dropGlass.transmission = lit ? 0.92 : 0.0;
  S.dropGlass.opacity = lit ? 1.0 : 0.35;
  // in the flame-lit chamber the clear droplet shows the surrounding flame light (appearance only)
  var glowCol = flame.present ? (flame.soot ? [0.55, 0.36, 0.26] : [0.12, 0.2, 0.45]) : [0, 0, 0];
  S.dropGlass.emissive.setRGB(glowCol[0], glowCol[1], glowCol[2]);
  // flame (true size from data only). Volume drawn at the visible (colour-camera) edge; if only LLUV data
  // exist it is drawn at the LLUV edge and the readout says so (the visible flame is typically smaller, CLM-014).
  var hasVis = flame.present && flame.visible_D_mm !== null, hasUV = flame.present && flame.lluv_D_mm !== null;
  var fd = hasVis ? flame.visible_D_mm : (hasUV ? flame.lluv_D_mm : null);
  S.flameVis.visible = fd !== null;
  var U = S.flameVis.material.uniforms;
  if (fd !== null) {
    S.flameVis.scale.setScalar(fd);
    U.uRdrop.value = droplet.D_mm ? 0.5 * droplet.D_mm / fd : 0;
    var lut = OF.flameLUT(Math.round(U.uRdrop.value * 2000) / 2000);
    U.uLUT.value = lut.tex; U.uMaxB.value = lut.maxB; U.uMaxS.value = lut.maxS;
    U.uSoot.value = flame.soot ? 1 : 0;
    U.uBlueGain.value = flame.dim ? 0.7 : 1.6;
  }
  S.flameUV.visible = hasUV && OF.overlays && !OF.SCENE.cams[OF.currentView];
  if (hasUV) { S.flameUV.scale.setScalar(flame.lluv_D_mm); S.flameUV.quaternion.copy(camera.quaternion); }
  S.glyph.visible = flame.present && fd === null;
  // lighting: the LED is on during droplet formation (stages 5a–5b, CLM-048); during the burn the flame is the
  // light source (soot luminosity is much brighter than the blue flame; values are approximate).
  var ledOn = i <= 5;
  S.ledLight.intensity = ledOn ? 0.75 : 0.0;
  S.hemi.intensity = ledOn ? 0.12 : 0.015;
  if (S.bloom) { S.bloom.threshold = ledOn ? 0.95 : 0.78; S.bloom.strength = ledOn ? 0.35 : 0.85; }
  S.ledFace.material.color.setHex(ledOn ? 0xffffff : 0x202326);
  OF.S.envMats.forEach(function (m) { m.envMapIntensity = ledOn ? 0.45 : 0.06; });
  scene.background.setHex(ledOn ? 0x0b0c0e : 0x030405);
  var fl = fd === null ? 0 : (flame.soot ? 1.6 : (flame.dim ? 0.15 : 0.4));
  S.flameLight.intensity = fl;
  S.flameLight.color.setHex(flame.soot ? 0xffb27a : 0x8fa8ff);
  var fdMax = Math.max(fd || 0, hasUV ? flame.lluv_D_mm : 0, D0 || 0);
  S.scaleBar.position.y = 22 - Math.max(6, fdMax / 2 + 5);     // keep the 10 mm bar just below the flame
  S.uvGlow.visible = false;
  // What each instrument records (camera views): HiBMs = backlit silhouette, no flame (CLM-047);
  // LLUV = OH* emission only, droplet not visible at 310 nm (CLM-013); colour camera = visible flame.
  var v = OF.currentView;
  if (v === "hibms") {
    scene.background.setHex(0xdfe3e8);
    S.droplet.material = S.dropShadow;
    S.flameVis.visible = S.flameUV.visible = S.glyph.visible = false;
    S.flameLight.intensity = 0;
  } else if (v === "lluv") {
    scene.background.setHex(0x020203);
    S.droplet.visible = S.flameVis.visible = S.flameUV.visible = false;
    S.uvGlow.visible = hasUV;
    if (hasUV) {
      var UU = S.uvGlow.material.uniforms, l0 = OF.flameLUT(0);
      S.uvGlow.scale.setScalar(flame.lluv_D_mm); UU.uRdrop.value = 0; UU.uSoot.value = 0;
      UU.uLUT.value = l0.tex; UU.uMaxB.value = l0.maxB; UU.uMaxS.value = l0.maxS;
    }
    S.glyph.visible = flame.present && !hasUV;
    S.flameLight.intensity = 0; S.hemi.intensity = 0; S.ledLight.intensity = 0;
  }
  var cv = document.getElementById("camview-note");
  if (cv) cv.textContent = v === "hibms" ? "As HiBMs: backlit silhouette of the droplet; the flame is not imaged (CLM-047)." :
    v === "lluv" ? "As LLUV: OH* chemiluminescence edge only (310 nm); the droplet is not visible (CLM-013)." :
    v === "colour" ? "As colour camera: visible flame; 93.2 × 76.3 mm field (DSC-007)." + (OF.cameraLook ? " Sensor speckle is a cosmetic camera look (CLM-050)." : "") : "";
  OF.updateCameraLook();
};

// Per-frame: the flame volume needs the camera position in its own coordinates.
OF.frameUniforms = function () {
  [OF.S.flameVis, OF.S.uvGlow].forEach(function (m) {
    if (m && m.visible) m.material.uniforms.uCamObj.value.copy(m.worldToLocal(camera.position.clone()));
  });
};

// Measurement overlays (LLUV edge ring, scale bar) — on by default, hidden inside camera views.
OF.overlays = true;
OF.toggleOverlays = function () {
  OF.overlays = !OF.overlays;
  var b = document.getElementById("btn-overlays"); if (b) b.setAttribute("aria-pressed", OF.overlays ? "true" : "false");
  OF.updateScene();
};

// Cosmetic colour-camera look: sparse coloured single-pixel noise, as seen in NASA footage (CLM-050).
// Shown only in the "As colour cam" view and only while the toggle is on. Carries no data.
OF.cameraLook = true;
OF.toggleCameraLook = function () {
  OF.cameraLook = !OF.cameraLook;
  var b = document.getElementById("btn-camlook"); if (b) b.setAttribute("aria-pressed", OF.cameraLook ? "true" : "false");
  OF.updateScene();
};
OF.updateCameraLook = function () {
  var c = document.getElementById("camlook-canvas");
  if (!c) return;
  var on = OF.cameraLook && OF.currentView === "colour" && threeReady;
  c.style.display = on ? "block" : "none";
  if (!on) return;
  var w = c.clientWidth, h = c.clientHeight;
  if (c.width !== w || c.height !== h) { c.width = w; c.height = h; OF._speckSeed = null; }
  if (OF._speckSeed && !OF.anim.playing) return;
  OF._speckSeed = true;
  var ctx = c.getContext("2d"); ctx.clearRect(0, 0, w, h);
  var n = Math.round(w * h / 900), cols = ["rgba(255,80,80,", "rgba(90,140,255,", "rgba(90,255,140,", "rgba(255,255,255,"];
  for (var k = 0; k < n; k++) {
    ctx.fillStyle = cols[k % 4] + (0.25 + 0.5 * Math.random()).toFixed(2) + ")";
    ctx.fillRect(Math.random() * w | 0, Math.random() * h | 0, 1.5, 1.5);
  }
};

// 2D fallback (no WebGL / no Three.js): top view after Fig. 3 plus a to-scale inset of droplet and flame.
OF.drawFallback = function (stageIdx, droplet, flame) {
  var c = document.getElementById("fallback-canvas");
  if (!c) return;
  var ctx = c.getContext("2d");
  c.width = c.clientWidth || 720; c.height = c.clientHeight || 480;
  var fg = OF.themeColor("--text", "#111827"), mut = OF.themeColor("--text-muted", "#4b5563");
  ctx.fillStyle = OF.themeColor("--scene-bg", "#e9eef5"); ctx.fillRect(0, 0, c.width, c.height);
  ctx.fillStyle = fg; ctx.font = "13px system-ui, sans-serif";
  ctx.fillText("2D view (3D unavailable): left, top-view layout after NASA TP Fig. 3 (sketch, not to scale); right, droplet and flame to scale", 12, c.height - 12);
  var cx = c.width * 0.24, cy = c.height * 0.55, R = Math.min(c.width * 0.2, c.height * 0.36);
  ctx.strokeStyle = mut; ctx.lineWidth = 2; ctx.beginPath();
  for (var k = 0; k <= 8; k++) { var a = Math.PI / 8 + k * Math.PI / 4; ctx[k ? "lineTo" : "moveTo"](cx + R * Math.cos(a), cy + R * Math.sin(a)); }
  ctx.stroke();
  ctx.font = "12px system-ui"; ctx.fillStyle = fg;
  ctx.fillText("LLUV", cx - R * 0.78, cy - R * 0.72); ctx.fillText("HiBMs", cx + R * 0.55, cy - R * 0.72); ctx.fillText("LED light source", cx - R * 0.95, cy + R * 0.8);
  ctx.strokeStyle = fg; ctx.lineWidth = 2; ctx.beginPath();
  var ret = stageIdx >= 7 ? R * 0.35 : R * 0.03;
  ctx.moveTo(cx - R * 0.6, cy); ctx.lineTo(cx - ret, cy); ctx.moveTo(cx + R * 0.6, cy); ctx.lineTo(cx + ret, cy); ctx.stroke();
  // inset, true scale: 40 mm across
  var ix = c.width * 0.72, iy = c.height * 0.55, half = Math.min(c.width * 0.24, c.height * 0.38), mmpx = half / 20;
  ctx.strokeStyle = mut; ctx.strokeRect(ix - half, iy - half, 2 * half, 2 * half);
  ctx.fillStyle = fg; ctx.fillText("To scale: 40 mm × 40 mm around the droplet", ix - half, iy - half - 8);
  if (flame && flame.present) {
    var fd = flame.visible_D_mm !== null && flame.visible_D_mm !== undefined ? flame.visible_D_mm : flame.lluv_D_mm;
    if (fd !== null && fd !== undefined) { ctx.strokeStyle = "#2563eb"; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(ix, iy, fd / 2 * mmpx, 0, Math.PI * 2); ctx.stroke(); }
    else { ctx.setLineDash([6, 5]); ctx.strokeStyle = "#2563eb"; ctx.beginPath(); ctx.arc(ix, iy, 22, 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]); ctx.fillText("flame: size not measured", ix - 70, iy + 40); }
  }
  if (droplet && droplet.D_mm) { ctx.fillStyle = "#334155"; ctx.beginPath(); ctx.arc(ix, iy, Math.max(1, droplet.D_mm / 2 * mmpx), 0, Math.PI * 2); ctx.fill(); }
};

OF.renderTimelineInfo = function () {
  var T = OF.timeline, el = document.getElementById("timeline-info");
  if (!el) return;
  el.innerHTML = '<ul class="prov-list">' + T.provenance.map(function (x) {
    return '<li data-source="' + OF.esc(x.source) + '"><strong>' + OF.esc(x.what) + ":</strong> " + OF.esc(x.source) + "</li>";
  }).join("") + "</ul>" +
    '<ul class="prov-list" data-source="Table IX / caption">' + T.events.map(function (e) { return "<li><span class=\"mono\">t = " + e.t + " s</span> — " + OF.esc(e.label) + "</li>"; }).join("") + "</ul>" +
    (T.consistency ? '<p class="small" data-derived="reconstruction check">Reconstructed droplet size at the printed burn time: <span class="mono">' + T.consistency.reconstructed_D_at_tb_mm.toFixed(2) + " mm</span>; printed extinction diameter: <span class=\"mono\">" + T.consistency.printed_D_ext_mm + " mm</span>. " + OF.esc(T.consistency.note) + "</p>" : "") +
    '<p class="small" data-claims="CLM-016 CLM-043 CLM-046">Shape: spherical, because buoyant convection is negligible in the FLEX microgravity environment (CLM-016, CLM-043). Flame edges are outer edges (CLM-046). Droplet drift (CLM-016) is not shown: the droplet is kept at the centre.</p>';
};
