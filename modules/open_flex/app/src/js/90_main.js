// ---------------------------------------------------------------------------
// Open FLEX — bootstrap, workspaces (ARIA tabs), theme, animation loop.
// ---------------------------------------------------------------------------
OF.TABS = ["overview", "lab", "physics", "uq", "evidence"];

OF.switchTab = function (id, btn) {
  btn = btn || document.getElementById("tabbtn-" + id);
  document.querySelectorAll(".workspace").forEach(function (w) { w.classList.remove("active"); });
  document.querySelectorAll(".tab-btn").forEach(function (b) { b.setAttribute("aria-selected", "false"); b.setAttribute("tabindex", "-1"); b.classList.remove("active"); });
  document.getElementById("tab-" + id).classList.add("active");
  btn.setAttribute("aria-selected", "true"); btn.setAttribute("tabindex", "0"); btn.classList.add("active");
  OF.activeTab = id;
  if (id === "physics") { OF.renderRadialSchematic(); if (OF.state.testId) OF.renderTimeSeriesStatus(OF.state.testId); }
  if (OF.libStatus().plotly) {           // charts drawn while their tab was hidden get the right width now
    document.querySelectorAll("#tab-" + id + " .js-plotly-plot").forEach(function (el) { try { Plotly.Plots.resize(el); } catch (e) { /* ignore */ } });
  }
  if (id === "lab") { OF.resize3D && OF.resize3D(); OF.updateScene(); }
  if (id === "uq" && document.getElementById("cov-form") && OF.state.testId) OF.renderCoverage(true);
};

// Keyboard: arrow keys / Home / End move between tabs (WAI-ARIA tabs pattern, automatic activation).
document.addEventListener("keydown", function (e) {
  var t = e.target;
  if (!t.classList || !t.classList.contains("tab-btn")) return;
  var i = OF.TABS.indexOf(t.id.replace("tabbtn-", "")), n = OF.TABS.length, j = null;
  if (e.key === "ArrowRight") j = (i + 1) % n;
  else if (e.key === "ArrowLeft") j = (i - 1 + n) % n;
  else if (e.key === "Home") j = 0;
  else if (e.key === "End") j = n - 1;
  if (j === null) return;
  e.preventDefault();
  var b = document.getElementById("tabbtn-" + OF.TABS[j]);
  OF.switchTab(OF.TABS[j], b); b.focus();
});

OF.reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Theme: light default; the choice is remembered in this browser only (storage may be unavailable).
OF.applyTheme = function (theme) {
  document.documentElement.setAttribute("data-theme", theme);
  var b = document.getElementById("btn-theme");
  if (b) { b.setAttribute("aria-pressed", theme === "dark" ? "true" : "false"); b.textContent = theme === "dark" ? "Light theme" : "Dark theme"; }
};
OF.toggleTheme = function () {
  var next = document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark";
  OF.applyTheme(next);
  try { localStorage.setItem("openflex-theme", next); } catch (e) { /* storage unavailable: not remembered */ }
  if (OF.state.testId) OF.selectTest(OF.state.testId);
  if (OF.activeTab === "physics") OF.renderRadialSchematic();
};

// Plot styling from the active theme (CSS variables), shared by every Plotly chart.
OF.plotBase = function () {
  return { paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: OF.themeColor("--plot-bg", "#ffffff"),
    font: { color: OF.themeColor("--plot-text", "#374151"), size: 12 }, grid: OF.themeColor("--plot-grid", "#e5e7eb"),
    s1: OF.themeColor("--s1", "#2a78d6"), s2: OF.themeColor("--s2", "#eb6834"), s3: OF.themeColor("--s3", "#1baf7a"),
    surface: OF.themeColor("--surface", "#ffffff") };
};

OF._last = performance.now();
OF.loop = function (now) {
  requestAnimationFrame(OF.loop);
  var dt = Math.min(0.1, (now - OF._last) / 1000); OF._last = now;
  if (OF.anim.playing && OF.activeTab === "lab") OF.advance(dt);
  if (threeReady && renderer && scene && camera && OF.activeTab === "lab") {
    if (controls) controls.update();
    if (OF.S.flameUV && OF.S.flameUV.visible) OF.S.flameUV.quaternion.copy(camera.quaternion);
    if (OF.S.scaleBar) OF.S.scaleBar.visible = OF.overlays && !OF.SCENE.cams[OF.currentView] && camera.position.distanceTo(controls ? controls.target : new THREE.Vector3()) < 200;
    OF.frameUniforms();
    if (OF.anim.playing) OF.updateCameraLook();
    if (OF.S.composer) OF.S.composer.render(); else renderer.render(scene, camera);
  }
};

window.addEventListener("DOMContentLoaded", function () {
  var saved = null;
  try { saved = localStorage.getItem("openflex-theme"); } catch (e) { saved = null; }
  OF.applyTheme(saved === "dark" ? "dark" : "light");
  var lib = OF.libStatus();
  document.getElementById("build-id").textContent = OF.D.build.build_id;
  document.getElementById("banner-ntests").textContent = OF.D.table_ix.length;
  document.getElementById("ov-ntests").textContent = OF.D.table_ix.length;
  document.getElementById("ov-ndig").textContent = Object.keys(OF.D.digitized || {}).length;
  document.getElementById("ov-nclaims").textContent = OF.D.claims.claims.length;
  document.getElementById("ov-ndsc").textContent = OF.D.discrepancies.discrepancies.length;
  if (!lib.three) document.getElementById("lib-status-3d").innerHTML = '<span class="badge badge-danger">3D LIBRARY UNAVAILABLE — 2D FALLBACK</span>';
  OF.activeTab = "overview";
  initThreeScene();
  OF.renderStagePills();
  OF.populateTestSelect();
  OF.renderHotspotChips();
  OF.renderClaims();
  OF.renderSources();
  OF.renderDiscrepancies();
  OF.renderDatasets();
  OF.initModeSwitch();
  OF.share.wire();
  OF.renderVerification();
  var link = OF.parseDeepLink(location.hash);
  OF.selectTest(link.test || "FLEX-035");
  OF.jumpStage(10);                     // start in the burn, about 30 % of the way to the printed burn time
  OF.anim.playing = false;
  OF.setPlayLabel();
  if (link.tab) OF.switchTab(link.tab);
  requestAnimationFrame(OF.loop);
  OF.ready = true;
});

// Deep link used by the Flame in Freefall dashboards: #test=FLEX-035&tab=lab.
// Unknown test ids and tab names are ignored (the default view is shown), never guessed.
OF.parseDeepLink = function (hash) {
  var out = { test: null, tab: null };
  (hash || "").replace(/^#/, "").split("&").forEach(function (kv) {
    var i = kv.indexOf("="), k = i < 0 ? kv : kv.slice(0, i), v = i < 0 ? "" : decodeURIComponent(kv.slice(i + 1));
    if (k === "test" && OF.testById[v]) out.test = v;
    if (k === "tab" && OF.TABS.indexOf(v) >= 0) out.tab = v;
  });
  return out;
};
window.addEventListener("hashchange", function () {
  if (!OF.ready) return;
  var link = OF.parseDeepLink(location.hash);
  if (link.test && link.test !== OF.state.testId) { OF.selectTest(link.test); OF.jumpStage(10); }
  if (link.tab) OF.switchTab(link.tab);
});
