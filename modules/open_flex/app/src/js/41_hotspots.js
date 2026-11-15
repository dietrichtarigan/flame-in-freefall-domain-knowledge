// ---------------------------------------------------------------------------
// Open FLEX — component information. Each text field is either backed by
// claim IDs (data/registry/claims.json) or tagged "interpretive".
// Statements from the original prototype that no available source supports
// were removed or moved to the "unverified" line.
// ---------------------------------------------------------------------------
OF.HOTSPOTS = [
  { id: "cir_chamber", name: "CIR combustion chamber",
    what: "90-L chamber of the Combustion Integrated Rack in the ISS Destiny module.", claims: ["CLM-001"],
    does: "Holds the test atmosphere and the MDCA. Rated approx. 0–9 atm; FLEX safety analysis limited working pressure to approx. 3 atm.", doesClaims: ["CLM-002", "CLM-003"],
    measures: "Rack accelerometer heads monitored the g/vibration environment (no accelerometer data are loaded here). PaRIS isolated the rack from higher-frequency ISS vibration.", measuresClaims: ["CLM-016"],
    limits: "Buoyant flow negligible, but g-jitter caused droplet drift (CLM-016).",
    unverified: "" },
  { id: "foma", name: "FOMA gas system",
    what: "Fuel and Oxidizer Mixing Apparatus: CIR facility subsystem (gas bottles, ISS nitrogen, valves, pressure transducers, mass-flow controllers); evacuation to the ISS overboard vent.", claims: [], tp: "S01 §2.1, p. 3",
    does: "Fills the chamber to the target pressure and composition; fill and evacuation pressure histories are used to compute the actual composition afterwards.", doesClaims: ["CLM-020"],
    measures: "Table IX composition is that reconstruction. Sensor uncertainties are not stated in the TP.", measuresClaims: ["CLM-020"],
    limits: "Nominal matrix compositions can differ from the reconstructed values (DSC-002, DSC-003).",
    unverified: "" },
  { id: "mdca_insert", name: "MDCA insert",
    what: "Multi-User Droplet Combustion Apparatus inside the CIR chamber; deploys and ignites droplets and provides the colour camera and radiometers.", claims: ["CLM-015"],
    does: "Forms the droplet between opposed needles, deploys it, ignites it.", doesClaims: ["CLM-022"],
    measures: "Colour camera (visible flame), radiometers (not reported).", measuresClaims: ["CLM-012", "CLM-015"],
    limits: "Geometry in this 3D view is conceptual; no dimensioned drawing was available.",
    unverified: "" },
  { id: "reservoirs", name: "Fuel reservoirs and lines",
    what: "Two replaceable reservoirs, each a gas-tight syringe with a remotely actuated gas-tight solenoid valve, connected to a needle by flexible Teflon tubing (approx. 2.5 ml methanol, 1.25 ml heptane).", claims: [], tp: "S01 §2.1, p. 3",
    does: "A stepper motor advances the syringe to purge the line and dispense fuel; stepper counts were used only as a guide to droplet size.", doesClaims: ["CLM-022"], tp2: "S01 §2.3 (4)–(5)(a), p. 5",
    measures: "No dispensed-volume measurement is reported.", measuresClaims: [],
    limits: "Each fuel is a separate dataset; fuels are never merged.",
    unverified: "Original prototype stated the valve closes after droplet formation — not found in the TP." },
  { id: "needles", name: "Deployment needles",
    what: "Opposed stainless-steel tubes, 250 µm outside diameter, specially treated ends.", claims: ["CLM-005"],
    does: "Bridge and stretch the fuel, then retract rapidly and simultaneously to deploy the droplet just before ignition.", doesClaims: ["CLM-022"],
    measures: "None.", measuresClaims: [],
    limits: "Droplets had residual velocity after deployment and were misshapen for about 1 s (TP p. 7). Needle coating contaminated the fuel in the TP tests (CLM-023).",
    unverified: "Drift of '1–2 mm/s' (CLM-032) is unverified." },
  { id: "igniters", name: "Hot-wire igniters",
    what: "Two hot-wire igniters 180° apart in the plane of the needles.", claims: ["CLM-006"],
    does: "Turned on after deployment for a preset time and power, then turned off and retracted a relatively large distance.", doesClaims: ["CLM-022"],
    measures: "Igniter ON defines time zero for Table IX D₀ and Appendix B plots.", measuresClaims: ["CLM-018"],
    limits: "Igniter light distorted HiBMs images in early tests (CLM-026).",
    unverified: "Planned 1–5 s energization (JSC plan, S02) not verified." },
  { id: "droplet_flame", name: "Droplet and flame",
    what: "Isolated methanol or n-heptane droplet with a spherical diffusion flame: buoyant convection is negligible in microgravity.", claims: ["CLM-016", "CLM-043"],
    does: "Burns until extinction, disruption or completion (Table IX 'Test end').", doesClaims: [],
    measures: "Droplet size (HiBMs), OH* flame edge (LLUV), visible flame edge (colour camera).", measuresClaims: ["CLM-009", "CLM-011", "CLM-012"],
    limits: "Some large heptane tests showed continued vaporization after visible extinction, which the authors describe as indicative of cool-flame burning (CLM-027) — an inference, not a direct measurement.",
    unverified: "" },
  { id: "fiber", name: "Support fiber (some tests)",
    what: "80 µm support fiber; optionally translated after ignition at a prescribed speed and duration.", claims: ["CLM-007", "CLM-008"],
    does: "Used when drift was unacceptable or to study sub-buoyant convective flow.", doesClaims: ["CLM-007"],
    measures: "Translation speed is a prescribed setting (not printed in Table IX).", measuresClaims: [],
    limits: "Fiber use is not in Table IX (DSC-012); the 3D view shows the fiber when the test matrix and/or caption say fiber-supported, and not when they disagree (DSC-014, DSC-015).",
    unverified: "Silicon-carbide material: secondary source only (CLM-008). Heat-conduction and flame-distortion effects: not quantified in the TP." },
  { id: "hibms", name: "HiBMs camera", what: "High-Bit-Depth Multispectral imaging package with 650–660 nm diode backlight operated below lasing threshold (noncoherent); 1024 × 1024, 12-bit, approx. 30 fps.", claims: ["CLM-010"],
    does: "Backlit view of the droplet.", doesClaims: [], measures: "Droplet size ±50 µm (reported estimate, coverage not stated).", measuresClaims: ["CLM-009"],
    limits: "Does not image the flame; FOV loss with drift (CLM-017); scale discrepancy DSC-006.", unverified: "" },
  { id: "lluv_colour", name: "LLUV and colour cameras",
    what: "LLUV: UV-intensified camera, 310 nm filter, 2 × 2 binned 512 × 512. Colour camera: NTSC 640 × 480 with zoom and LED illumination.", claims: ["CLM-011", "CLM-012"],
    does: "LLUV: OH* chemiluminescence; colour: visible flame.", doesClaims: ["CLM-013", "CLM-014"],
    measures: "Two different flame-edge definitions (±200 µm and ±250 µm reported estimates).", measuresClaims: ["CLM-011", "CLM-012"],
    limits: "Not interchangeable; colour ≈ ¾ LLUV typically (CLM-014). FOV values disagree within the TP (DSC-007).", unverified: "" }
];

OF.activeHotspot = "droplet_flame";

OF.renderHotspotChips = function () {
  document.getElementById("hotspot-chips").innerHTML = OF.HOTSPOTS.map(function (h) {
    return '<button class="chip" data-id="' + h.id + '" onclick="OF.selectHotspot(\'' + h.id + '\')">' + OF.esc(h.name) + "</button>";
  }).join("");
  OF.selectHotspot(OF.activeHotspot);
};

OF.selectHotspot = function (id) {
  OF.activeHotspot = id;
  var h = OF.HOTSPOTS.filter(function (x) { return x.id === id; })[0];
  document.querySelectorAll(".chip").forEach(function (c) { var on = c.dataset.id === id; c.classList.toggle("active", on); c.setAttribute("aria-pressed", on); });
  var pv = function (list, tp) { return (list && list.length) ? ' data-claims="' + list.join(" ") + '"' : (tp ? ' data-source="' + OF.esc(tp) + '"' : ' data-interpretive="component description"'); };
  var ev = function (list, tp) {
    var s = (list || []).map(OF.claimLink).join(", ");
    if (tp) s += (s ? "; " : "") + '<span class="mono">' + OF.esc(tp) + "</span>";
    return s ? ' <span class="sub-note">[' + s + "]</span>" : ' <span class="sub-note">[interpretive]</span>';
  };
  var stage = OF.STAGES[OF.stageIndex(OF.anim.p)];
  document.getElementById("bubble-source-tag").textContent = "Evidence: claim IDs per line";
  document.getElementById("bubble-content").innerHTML =
    '<div class="bubble-cell"><h3>1. What it is</h3><p' + pv(h.claims, h.tp) + ">" + OF.esc(h.what) + ev(h.claims, h.tp) + "</p></div>" +
    '<div class="bubble-cell"><h3>2. What it does</h3><p' + pv(h.doesClaims, h.tp2 || h.tp) + ">" + OF.esc(h.does) + ev(h.doesClaims, h.tp2) + "</p></div>" +
    '<div class="bubble-cell"><h3>3. At the current illustration stage</h3><p data-interpretive="illustration stage">' + OF.esc(stage.label) + ' <span class="sub-note">[illustrative]</span></p></div>' +
    '<div class="bubble-cell"><h3>4. Measurements &amp; uncertainty</h3><p' + pv(h.measuresClaims, h.tp) + ">" + OF.esc(h.measures) + ev(h.measuresClaims) + "</p></div>" +
    '<div class="bubble-cell"><h3>5. Limits</h3><p data-interpretive="limits (Phase B review)">' + OF.esc(h.limits) + "</p></div>" +
    '<div class="bubble-cell"><h3>6. Unverified statements</h3><p data-interpretive="unverified, shown as such">' + (h.unverified ? OF.esc(h.unverified) : "None recorded.") + "</p></div>";
};
