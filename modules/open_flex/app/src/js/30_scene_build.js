// ---------------------------------------------------------------------------
// Open FLEX — 3D apparatus (Phase B M5). Units: millimetres.
//
// Layout source: NASA/TP-2015-216046 Fig. 3 (MDCA viewed from the top, PDF p. 9) and Fig. 4 (camera views).
// Fig. 3 plane = horizontal x–z plane here (y up); Fig. 3 "up" = −z.
//
// TO SCALE (true mm, around the droplet): droplet and flame (from OF.Timeline), needle OD 0.25 mm (CLM-005),
// fiber 80 µm (CLM-007), camera fields of view (HiBMs 30.25 mm, LLUV 57.8 mm, colour 93.2 × 76.3 mm; see
// DSC-006/007), igniter loops about 10 mm from the droplet (read from Fig. 4(c); approximate).
// LAYOUT SKETCH, NOT TO SCALE: chamber, rails, motors, syringe, camera bodies (positions from Fig. 3; sizes
// invented for legibility; not CAD).
// ---------------------------------------------------------------------------
let scene, camera, renderer, controls, threeReady = false;
OF.S = {};                      // scene objects
OF.pickables = [];

OF.SCENE = {
  chamberR: 230, chamberH: 260,
  needleOD: 0.25, needleRetract: 45, fiberD: 0.08,
  igniterDist: 10, igniterRetract: 55,
  fov: { hibms: [30.25, 30.25], lluv: [57.8, 57.8], colour: [93.2, 76.3] },
  // Fig. 3 corners (top view): LLUV upper-left, HiBMs upper-right, LED lower-left. Colour camera: not shown in
  // Fig. 3 — placed above at an oblique angle (Fig. 4 colour images are oblique views); conceptual.
  cams: { lluv: [-150, 0, -150], hibms: [150, 0, -150], led: [-150, 0, 150], colour: [120, 140, 140] }
};

OF.themeColor = function (name, fallback) {
  var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
};

function mat(color, opts) {
  var m = new THREE.MeshStandardMaterial(Object.assign({ color: color, roughness: 0.55, metalness: 0.35 }, opts || {}));
  (OF.S.envMats = OF.S.envMats || []).push(m);
  return m;
}
// Hardware finishes seen in NASA colour-camera footage (CLM-049): bright machined aluminium, black anodised
// plates, brass fittings. Appearance only.
function alu() { return mat(0xaab0b8, { metalness: 1.0, roughness: 0.34 }); }
function anod() { return mat(0x16181c, { metalness: 0.55, roughness: 0.45 }); }
function brass() { return mat(0xc9a15a, { metalness: 1.0, roughness: 0.28 }); }

function addPick(obj, hotspot) {
  obj.traverse(function (o) { if (o.isMesh) { o.userData.hotspot = hotspot; OF.pickables.push(o); } });
  obj.userData.hotspot = hotspot;
}

// Sprite with canvas text, for in-scene labels (fixed screen size).
function textSprite(text, color) {
  var c = document.createElement("canvas"), ctx = c.getContext("2d");
  ctx.font = "600 28px system-ui, sans-serif";
  var w = Math.ceil(ctx.measureText(text).width) + 24;
  c.width = w; c.height = 44;
  ctx.font = "600 28px system-ui, sans-serif";
  ctx.fillStyle = "rgba(255,255,255,0.86)"; ctx.fillRect(0, 0, w, 44);
  ctx.fillStyle = color || "#1f2937"; ctx.fillText(text, 12, 32);
  var tex = new THREE.CanvasTexture(c);
  var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false, sizeAttenuation: false, transparent: true }));
  sp.scale.set(w / 1700, 44 / 1700, 1);
  sp.renderOrder = 10;
  (OF.S.labels = OF.S.labels || []).push(sp);
  return sp;
}

// ---------------------------------------------------------------------------
// Volumetric flame (ray-marched emission inside a sphere). Physics content:
//  * the flame sheet is a thin spherical shell whose OUTER edge is the measured diameter (CLM-046); its glow
//    is integrated along each line of sight through an optically thin layer, so the rim looks brighter than
//    the centre (limb brightening) — a consequence of projection, not a styling choice;
//  * soot luminosity, when the caption reports it, is a diffuse emitting region inside the blue envelope
//    (CLM-045); its radius is not measured, so it is drawn as a broad distribution, never as a sharp edge;
//  * nothing emits inside the droplet; the clear liquid passes light from the far side (refraction ignored).
// Colours and absolute brightness are approximate (not radiometric). Film-like response: 1 − exp(−E).
// Object space: visible flame radius = 0.5 (mesh scale = measured diameter in mm); bounding sphere 0.56.
// ---------------------------------------------------------------------------
function dashedRingTexture() {
  var c = document.createElement("canvas"); c.width = c.height = 128;
  var ctx = c.getContext("2d");
  ctx.strokeStyle = "rgba(147,197,253,0.95)"; ctx.lineWidth = 6; ctx.setLineDash([12, 10]);
  ctx.beginPath(); ctx.arc(64, 64, 54, 0, Math.PI * 2); ctx.stroke();
  ctx.fillStyle = "rgba(147,197,253,0.95)"; ctx.font = "bold 46px system-ui"; ctx.textAlign = "center"; ctx.fillText("?", 64, 80);
  return new THREE.CanvasTexture(c);
}

OF.FLAME_BOUND = 0.56;
// Radial emission profiles (object space, visible edge at 0.5). Used both by the projection table and by the
// in-volume ray march, so the two paths draw the same physics.
OF.FLAME_PROFILE = { wB: 0.022, rB: 0.5 - 1.3 * 0.022, rS: 0.25, wS: 0.075 };
OF.flameEmission = function (r, rDrop) {
  var P = OF.FLAME_PROFILE;
  var eb = Math.exp(-Math.pow((r - P.rB) / P.wB, 2));
  var x = Math.min(1, Math.max(0, (r - rDrop) / (0.8 * rDrop || 1e-9))), ss = x * x * (3 - 2 * x);
  var es = Math.exp(-Math.pow((r - P.rS) / P.wS, 2)) * (rDrop > 0 ? ss : 1);
  return [eb, es];
};
// Abel projection: emission integrated along a straight line at impact parameter p (optically thin, no
// refraction). Returned as an RGBA8 texture: R = blue integral, G = soot integral, each scaled by its maximum.
OF.flameLUT = function (rDrop) {
  var key = rDrop.toFixed(4);
  OF._lutCache = OF._lutCache || {};
  if (OF._lutCache[key]) return OF._lutCache[key];
  var N = 512, M = 600, RB = OF.FLAME_BOUND, B = new Float32Array(N), S = new Float32Array(N), mb = 0, ms = 0;
  for (var i = 0; i < N; i++) {
    var p = (i + 0.5) / N * RB, half = Math.sqrt(Math.max(0, RB * RB - p * p)), dz = 2 * half / M, sb = 0, so = 0;
    for (var k = 0; k < M; k++) {
      var z = -half + (k + 0.5) * dz, e = OF.flameEmission(Math.sqrt(p * p + z * z), rDrop);
      sb += e[0] * dz; so += e[1] * dz;
    }
    B[i] = sb; S[i] = so; mb = Math.max(mb, sb); ms = Math.max(ms, so);
  }
  var data = new Uint8Array(N * 4);
  for (i = 0; i < N; i++) { data[4 * i] = Math.round(255 * B[i] / mb); data[4 * i + 1] = Math.round(255 * S[i] / ms); data[4 * i + 3] = 255; }
  var tex = new THREE.DataTexture(data, N, 1, THREE.RGBAFormat);
  tex.minFilter = tex.magFilter = THREE.LinearFilter; tex.needsUpdate = true;
  var keys = Object.keys(OF._lutCache); if (keys.length > 64) delete OF._lutCache[keys[0]];
  return (OF._lutCache[key] = { tex: tex, maxB: mb, maxS: ms });
};

// ---------------------------------------------------------------------------
// Volumetric flame. Physics content:
//  * the flame sheet is a thin spherical shell whose OUTER edge is the measured diameter (CLM-046); its glow
//    is integrated along each line of sight through an optically thin layer, so the rim looks brighter than
//    the centre (limb brightening) — a consequence of projection, not a styling choice;
//  * soot luminosity, when the caption reports it, is a diffuse emitting region inside the blue envelope
//    (CLM-045); its radius is not measured, so it is drawn as a broad distribution, never as a sharp edge;
//  * nothing emits inside the droplet; the clear liquid passes light from the far side (refraction ignored).
// Viewed from outside: exact projection from OF.flameLUT (one texture read per pixel). Camera inside the
// flame: ray march of the same profiles. Colours/brightness approximate (not radiometric); film-like
// response 1 − exp(−E). Object space: visible flame radius 0.5 (mesh scale = measured diameter in mm).
// ---------------------------------------------------------------------------
function flameVolumeMaterial(blueCol) {
  var P = OF.FLAME_PROFILE, f = function (x) { return x.toFixed(5); };
  return new THREE.ShaderMaterial({
    uniforms: {
      uCamObj: { value: new THREE.Vector3() }, uRdrop: { value: 0.05 }, uSoot: { value: 0 },
      uBlueGain: { value: 1.6 }, uSootGain: { value: 3.0 }, uBlueCol: { value: new THREE.Vector3().fromArray(blueCol) },
      uSootCol: { value: new THREE.Vector3(1.0, 0.58, 0.36) }, uExposure: { value: 1.0 },
      uLUT: { value: null }, uMaxB: { value: 1 }, uMaxS: { value: 1 }
    },
    vertexShader: "varying vec3 vPos; void main(){ vPos = position; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }",
    fragmentShader: [
      "uniform vec3 uCamObj; uniform float uRdrop; uniform float uSoot; uniform float uBlueGain; uniform float uSootGain;",
      "uniform vec3 uBlueCol; uniform vec3 uSootCol; uniform float uExposure; uniform sampler2D uLUT; uniform float uMaxB; uniform float uMaxS;",
      "varying vec3 vPos;",
      "const float RB = " + f(OF.FLAME_BOUND) + ";",
      "const float WB = " + f(P.wB) + "; const float RBL = " + f(P.rB) + "; const float RS = " + f(P.rS) + "; const float WS = " + f(P.wS) + ";",
      "void main(){",
      "  vec3 ro = uCamObj; vec3 rd = normalize(vPos - ro); vec2 I;",
      "  if (dot(ro, ro) > RB * RB) {",
      "    float pimp = length(cross(ro, rd)); if (pimp >= RB) discard;",
      "    vec4 L = texture2D(uLUT, vec2(pimp / RB, 0.5)); I = vec2(L.r * uMaxB, L.g * uMaxS);",
      "  } else {",
      "    float b = dot(ro, rd); float h = sqrt(max(b*b - (dot(ro, ro) - RB*RB), 0.0)); float t1 = -b + h;",
      "    const int N = 96; float dt = t1 / float(N); I = vec2(0.0);",
      "    for (int i = 0; i < N; i++) { float r = length(ro + rd * ((float(i) + 0.5) * dt));",
      "      float eb = exp(-pow((r - RBL) / WB, 2.0));",
      "      float x = clamp((r - uRdrop) / max(0.8 * uRdrop, 1e-6), 0.0, 1.0); float ss = uRdrop > 0.0 ? x*x*(3.0 - 2.0*x) : 1.0;",
      "      I += vec2(eb, exp(-pow((r - RS) / WS, 2.0)) * ss) * dt; }",
      "  }",
      "  vec3 acc = uBlueCol * I.x * uBlueGain + uSootCol * I.y * uSoot * uSootGain;",
      "  gl_FragColor = vec4(1.0 - exp(-acc * uExposure), 1.0);",
      "}"].join("\n"),
    transparent: true, depthWrite: false, depthTest: true, blending: THREE.AdditiveBlending, side: THREE.BackSide
  });
}

function frustum(from, fovWH, color, hotspot) {
  var g = new THREE.Group(), P = OF.SCENE;
  var o = new THREE.Vector3().fromArray(from), c = new THREE.Vector3(0, 0, 0);
  var dir = c.clone().sub(o).normalize();
  var up = Math.abs(dir.y) > 0.9 ? new THREE.Vector3(0, 0, 1) : new THREE.Vector3(0, 1, 0);
  var right = new THREE.Vector3().crossVectors(dir, up).normalize();
  var up2 = new THREE.Vector3().crossVectors(right, dir).normalize();
  var hw = fovWH[0] / 2, hh = fovWH[1] / 2;
  var corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(function (k) {
    return c.clone().add(right.clone().multiplyScalar(k[0] * hw)).add(up2.clone().multiplyScalar(k[1] * hh));
  });
  var pts = [];
  corners.forEach(function (q) { pts.push(o, q); });
  for (var i = 0; i < 4; i++) pts.push(corners[i], corners[(i + 1) % 4]);
  var geo = new THREE.BufferGeometry().setFromPoints(pts);
  var lines = new THREE.LineSegments(geo, new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.7 }));
  g.add(lines);
  var plane = new THREE.Mesh(new THREE.BufferGeometry().setFromPoints([corners[0], corners[1], corners[2], corners[0], corners[2], corners[3]]),
    new THREE.MeshBasicMaterial({ color: color, transparent: true, opacity: 0.07, side: THREE.DoubleSide, depthWrite: false }));
  g.add(plane);
  g.userData = { hotspot: hotspot, origin: o, dir: dir, fov: fovWH };
  return g;
}

function cameraBody(pos, color, label, hotspot) {
  var g = new THREE.Group();
  var body = new THREE.Mesh(new THREE.BoxGeometry(44, 34, 64), mat(color, { metalness: 0.4, roughness: 0.4 }));
  var lens = new THREE.Mesh(new THREE.CylinderGeometry(9, 11, 18, 24), mat(0x1f2937, { metalness: 0.6, roughness: 0.3 }));
  lens.rotation.x = Math.PI / 2; lens.position.z = 40;
  g.add(body); g.add(lens);
  g.position.fromArray(pos);
  g.lookAt(0, 0, 0);
  var lab = textSprite(label);
  lab.position.set(0, 34, 0);
  g.add(lab);
  addPick(g, hotspot);
  return g;
}

function initThreeScene() {
  var container = document.getElementById("three-container");
  var fallback = document.getElementById("fallback-canvas");
  if (typeof THREE === "undefined") {
    container.style.display = "none"; fallback.style.display = "block";
    return;
  }
  try {
    var P = OF.SCENE;
    scene = new THREE.Scene();
    // Chamber interior is dark during the burn: the colour-camera LED is off from just before deployment
    // (CLM-048). It is on during droplet formation; OF.updateScene switches lights accordingly.
    scene.background = new THREE.Color(0x030405);
    var w = container.clientWidth || 720, h = container.clientHeight || 480;
    camera = new THREE.PerspectiveCamera(40, w / h, 0.05, 5000);
    renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.1;
    renderer.outputEncoding = THREE.sRGBEncoding;
    container.innerHTML = "";
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");
    if (THREE.OrbitControls) {
      controls = new THREE.OrbitControls(camera, renderer.domElement);
      controls.enableDamping = !OF.reducedMotion; controls.dampingFactor = 0.08;
      controls.minDistance = 4; controls.maxDistance = 1400;
    }
    // Reflections: a neutral studio environment (RoomEnvironment) gives metal its look; its strength follows
    // the LED (bright during droplet formation, almost nothing during the burn).
    if (THREE.RoomEnvironment && THREE.PMREMGenerator) {
      var pm = new THREE.PMREMGenerator(renderer);
      scene.environment = pm.fromScene(new THREE.RoomEnvironment(), 0.04).texture;
      OF.S.hasEnv = true;
    }
    OF.S.hemi = new THREE.HemisphereLight(0xdfe8ff, 0x20242a, 0.6); scene.add(OF.S.hemi);
    OF.S.ledLight = new THREE.DirectionalLight(0xffffff, 1.2); OF.S.ledLight.position.fromArray(P.cams.led).add(new THREE.Vector3(0, 120, 0)); scene.add(OF.S.ledLight);
    OF.S.flameLight = new THREE.PointLight(0x9fb6ff, 0, 260, 2); scene.add(OF.S.flameLight);   // the flame lights its surroundings
    OF.S.envMats = [];
    // Bloom + film response (cosmetic, like a camera viewing a bright source); plain rendering if unavailable.
    if (THREE.EffectComposer && THREE.RenderPass && THREE.UnrealBloomPass && THREE.ShaderPass && THREE.GammaCorrectionShader) {
      renderer.outputEncoding = THREE.LinearEncoding;
      OF.S.composer = new THREE.EffectComposer(renderer);
      OF.S.composer.addPass(new THREE.RenderPass(scene, camera));
      OF.S.bloom = new THREE.UnrealBloomPass(new THREE.Vector2(w, h), 0.85, 0.55, 0.78);
      OF.S.composer.addPass(OF.S.bloom);
      OF.S.composer.addPass(new THREE.ShaderPass(THREE.GammaCorrectionShader));
    }

    // --- chamber (layout sketch): octagonal prism inscribed in a circle, as in Fig. 3 ---
    var oct = new THREE.CylinderGeometry(P.chamberR, P.chamberR, P.chamberH, 8, 1, true);
    oct.rotateY(Math.PI / 8);
    var shell = new THREE.Mesh(oct, new THREE.MeshStandardMaterial({ color: 0x2a2f36, transparent: true, opacity: 0.25, side: THREE.DoubleSide, depthWrite: false, metalness: 0.2, roughness: 0.7 }));
    var edges = new THREE.LineSegments(new THREE.EdgesGeometry(oct), new THREE.LineBasicMaterial({ color: 0x64748b, transparent: true, opacity: 0.6 }));
    OF.S.chamber = new THREE.Group(); OF.S.chamber.add(shell); OF.S.chamber.add(edges);
    scene.add(OF.S.chamber); addPick(OF.S.chamber, "cir_chamber");
    var deck = new THREE.Mesh(new THREE.CylinderGeometry(P.chamberR * 0.98, P.chamberR * 0.98, 6, 8), anod());
    deck.rotation.y = Math.PI / 8; deck.position.y = -60; scene.add(deck);

    // --- MDCA frame rails (dark anodised hardware, Fig. 2 photo; layout from Fig. 3) ---
    var rails = new THREE.Group();
    [-125, 125].forEach(function (z) {
      var r = new THREE.Mesh(new THREE.BoxGeometry(330, 10, 14), alu()); r.position.set(0, -50, z); rails.add(r);
    });
    [-125, 125].forEach(function (x) {
      var r = new THREE.Mesh(new THREE.BoxGeometry(14, 10, 250), alu()); r.position.set(x, -50, 0); rails.add(r);
    });
    scene.add(rails); addPick(rails, "mdca_insert");

    // --- deployment needles: opposed thin tips meeting at the droplet (along x, Fig. 3), each carried on an
    //     L-shaped arm that leaves in the opposite direction (as in NASA colour footage, CLM-049) ---
    OF.S.needles = [];
    [-1, 1].forEach(function (s) {
      var g = new THREE.Group(), L = 9;
      var tip = new THREE.Mesh(new THREE.CylinderGeometry(P.needleOD / 2, P.needleOD / 2, L, 16), mat(0xe2e6ea, { metalness: 1.0, roughness: 0.18 }));
      tip.rotation.z = Math.PI / 2; tip.position.x = s * L / 2;
      var visLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 0, 0), new THREE.Vector3(s * L, 0, 0)]), new THREE.LineBasicMaterial({ color: 0x8a9099 }));
      var arm = new THREE.Mesh(new THREE.BoxGeometry(2.2, 2.2, 52), alu()); arm.position.set(s * L, 0, s * 26);
      var holder = new THREE.Mesh(new THREE.BoxGeometry(16, 14, 22), alu()); holder.position.set(s * L, 0, s * 60);
      var screw = new THREE.Mesh(new THREE.CylinderGeometry(3, 3, 2, 6), brass()); screw.position.set(s * L, 8, s * 60);
      g.add(tip); g.add(visLine); g.add(arm); g.add(holder); g.add(screw);
      scene.add(g); addPick(g, "needles"); OF.S.needles.push({ g: g, s: s });
    });

    // --- igniters: open D-shaped hot-wire loops (CLM-049), 180° apart in the needle plane (CLM-006), on the
    //     Fig. 3 diagonal. Wire diameter and loop size are not given in the TP (drawn ≈0.25 mm wire, ≈4 mm loop).
    OF.S.igniters = [];
    var diag = new THREE.Vector3(-1, 0, -1).normalize();
    [1, -1].forEach(function (s) {
      var g = new THREE.Group();
      var pts = [];
      for (var k = 0; k <= 40; k++) { var th = (35 + k * 290 / 40) * Math.PI / 180; pts.push(new THREE.Vector3(-2 + 2 * Math.cos(th), 2 * Math.sin(th), 0)); }
      pts.unshift(new THREE.Vector3(1.2, 0.35, 0)); pts.push(new THREE.Vector3(1.2, -0.35, 0));
      var wireMat = new THREE.MeshStandardMaterial({ color: 0xb8bec6, metalness: 0.9, roughness: 0.3, emissive: 0x000000 });
      OF.S.envMats.push(wireMat);
      var loop = new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 120, 0.125, 8, false), wireMat);
      var shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 58, 12), alu()); shaft.rotation.z = Math.PI / 2; shaft.position.x = 1.2 + 29;
      var hex = new THREE.Mesh(new THREE.CylinderGeometry(4.2, 4.2, 14, 6), alu()); hex.rotation.z = Math.PI / 2; hex.position.x = 64;
      var body = new THREE.Mesh(new THREE.CylinderGeometry(3.2, 3.2, 40, 16), anod()); body.rotation.z = Math.PI / 2; body.position.x = 91;
      var glow = new THREE.PointLight(0xffa860, 0, 40, 2); glow.position.set(-2, 0, 0);
      g.add(loop); g.add(shaft); g.add(hex); g.add(body); g.add(glow);
      var dir = diag.clone().multiplyScalar(s);
      g.userData.dir = dir;
      g.rotation.y = Math.atan2(-dir.z, dir.x);   // local +x points away from the droplet along the diagonal
      scene.add(g); addPick(g, "igniters");
      OF.S.igniters.push({ g: g, loop: loop, dir: dir, glow: glow });
    });

    // --- fiber holder (Fig. 3, top) and 80 µm fiber across x, shown only for fiber-supported tests ---
    OF.S.fiberHolder = new THREE.Group();
    var bar = new THREE.Mesh(new THREE.BoxGeometry(150, 8, 8), anod()); bar.position.set(0, 0, -95); OF.S.fiberHolder.add(bar);
    [-1, 1].forEach(function (s) { var a = new THREE.Mesh(new THREE.BoxGeometry(8, 8, 95), anod()); a.position.set(s * 71, 0, -47.5); OF.S.fiberHolder.add(a); });
    OF.S.fiber = new THREE.Group();
    var fib = new THREE.Mesh(new THREE.CylinderGeometry(P.fiberD / 2, P.fiberD / 2, 142, 8), mat(0x52525b));
    fib.rotation.z = Math.PI / 2;
    OF.S.fiber.add(fib);
    OF.S.fiber.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-71, 0, 0), new THREE.Vector3(71, 0, 0)]), new THREE.LineBasicMaterial({ color: 0x52525b })));
    scene.add(OF.S.fiberHolder); scene.add(OF.S.fiber);
    addPick(OF.S.fiberHolder, "fiber"); addPick(OF.S.fiber, "fiber");

    // --- fuel syringe + deployment motor (Fig. 3 right side; layout only) ---
    var res = new THREE.Group();
    var barrel = new THREE.Mesh(new THREE.CylinderGeometry(9, 9, 80, 20), new THREE.MeshStandardMaterial({ color: 0xdbe4ee, transparent: true, opacity: 0.55, roughness: 0.1 }));
    barrel.rotation.x = Math.PI / 2; barrel.position.set(150, 0, -10);
    var motor = new THREE.Mesh(new THREE.BoxGeometry(30, 30, 46), mat(0x6b7280)); motor.position.set(118, 0, 40);
    res.add(barrel); res.add(motor);
    scene.add(res); addPick(res, "reservoirs");

    // --- cameras and frusta (positions per Fig. 3; FOV sizes from the TP) ---
    OF.S.cams = {
      lluv: cameraBody(P.cams.lluv, 0x5b4fb0, "LLUV (310 nm)", "lluv_colour"),
      hibms: cameraBody(P.cams.hibms, 0x2563eb, "HiBMs (backlit)", "hibms"),
      colour: cameraBody(P.cams.colour, 0x0f766e, "Colour camera (position conceptual)", "lluv_colour")
    };
    var led = new THREE.Group();
    var ledBox = new THREE.Mesh(new THREE.BoxGeometry(40, 30, 40), anod());
    var ledFace = new THREE.Mesh(new THREE.CircleGeometry(9, 32), new THREE.MeshBasicMaterial({ color: 0xffffff, toneMapped: false })); ledFace.position.z = 20.5; led.add(ledFace); OF.S.ledFace = ledFace;
    led.add(ledBox); led.position.fromArray(P.cams.led); led.lookAt(0, 0, 0);
    var ledLab = textSprite("'LED light source' (Fig. 3; DSC-026)"); ledLab.position.set(0, 30, 0); led.add(ledLab);
    scene.add(led); addPick(led, "hibms");
    Object.keys(OF.S.cams).forEach(function (k) { scene.add(OF.S.cams[k]); });
    OF.S.frusta = {
      hibms: frustum(P.cams.hibms, P.fov.hibms, 0x2563eb, "hibms"),
      lluv: frustum(P.cams.lluv, P.fov.lluv, 0x6d28d9, "lluv_colour"),
      colour: frustum(P.cams.colour, P.fov.colour, 0x0f766e, "lluv_colour")
    };
    Object.keys(OF.S.frusta).forEach(function (k) { scene.add(OF.S.frusta[k]); });

    // --- droplet and flame (sizes set every frame from OF.Timeline) ---
    // Liquid droplet: clear refracting sphere (ior 1.33 methanol / 1.39 n-heptane: handbook values at room
    // temperature, not from the TP; appearance only). HiBMs view swaps in an opaque silhouette.
    OF.S.dropGlass = new THREE.MeshPhysicalMaterial({ color: 0xffffff, metalness: 0, roughness: 0.02, transmission: 0.92, ior: 1.36, transparent: true, clearcoat: 1.0, clearcoatRoughness: 0.02 });
    OF.S.dropShadow = new THREE.MeshBasicMaterial({ color: 0x0b0c0e });
    OF.S.envMats.push(OF.S.dropGlass);
    OF.S.droplet = new THREE.Mesh(new THREE.SphereGeometry(0.5, 64, 48), OF.S.dropGlass);
    scene.add(OF.S.droplet); addPick(OF.S.droplet, "droplet_flame");
    OF.S.flameVis = new THREE.Mesh(new THREE.SphereGeometry(OF.FLAME_BOUND, 64, 48), flameVolumeMaterial([0.22, 0.42, 1.0]));
    OF.S.flameVis.renderOrder = 5;
    OF.S.uvGlow = new THREE.Mesh(new THREE.SphereGeometry(OF.FLAME_BOUND, 64, 48), flameVolumeMaterial([0.62, 0.45, 1.0]));   // LLUV view
    OF.S.uvGlow.renderOrder = 5;
    // LLUV (OH*) outer edge as a measurement overlay: a thin camera-facing ring of the measured diameter.
    // The 310 nm emission is invisible to the eye and to the colour camera, so it is an overlay, not light.
    OF.S.flameUV = new THREE.Mesh(new THREE.RingGeometry(0.494, 0.5, 160), new THREE.MeshBasicMaterial({ color: 0xc4b5fd, transparent: true, opacity: 0.9, side: THREE.DoubleSide, depthWrite: false, toneMapped: false }));
    OF.S.glyph = new THREE.Sprite(new THREE.SpriteMaterial({ map: dashedRingTexture(), transparent: true, depthTest: false, sizeAttenuation: false }));
    OF.S.glyph.scale.set(0.09, 0.09, 1);
    [OF.S.flameVis, OF.S.uvGlow, OF.S.flameUV, OF.S.glyph].forEach(function (o) { scene.add(o); addPick(o, "droplet_flame"); });
    // in-scene scale bar: 10 mm
    var sb = new THREE.Group();
    sb.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-5, -22, 0), new THREE.Vector3(5, -22, 0)]), new THREE.LineBasicMaterial({ color: 0xe5e7eb })));
    var sbl = textSprite("10 mm"); sbl.position.set(0, -26, 0); sb.add(sbl);
    OF.S.scaleBar = sb; scene.add(sb);

    // --- picking: click/tap on a part selects its component card ---
    var ray = new THREE.Raycaster(), ndc = new THREE.Vector2();
    renderer.domElement.addEventListener("pointerdown", function (e) {
      var r = renderer.domElement.getBoundingClientRect();
      ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1; ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
      ray.setFromCamera(ndc, camera);
      var hit = ray.intersectObjects(OF.pickables.filter(function (o) { return o.visible && isVisibleChain(o); }), false)[0];
      if (hit && hit.object.userData.hotspot) { OF.selectHotspot(hit.object.userData.hotspot); OF.flashPick(hit.object.userData.hotspot); }
    });
    function isVisibleChain(o) { while (o) { if (!o.visible) return false; o = o.parent; } return true; }

    window.addEventListener("resize", OF.resize3D);
    threeReady = true;
    OF.setCameraView("flame");
  } catch (err) {
    OF.threeError = String(err && err.stack || err);
    threeReady = false;
    container.style.display = "none"; fallback.style.display = "block";
    document.getElementById("lib-status-3d").innerHTML = '<span class="badge badge-danger">WEBGL UNAVAILABLE — 2D FALLBACK</span>';
  }
}

OF.resize3D = function () {
  if (!threeReady) return;
  var c = document.getElementById("three-container"), w = c.clientWidth, h = c.clientHeight;
  if (!w || !h) return;
  camera.aspect = w / h; camera.updateProjectionMatrix(); renderer.setSize(w, h);
  if (OF.S.composer) OF.S.composer.setSize(w, h);
};

OF.flashPick = function (hotspot) {
  var el = document.getElementById("pick-status");
  if (el) el.textContent = "Selected: " + (OF.HOTSPOTS.filter(function (h) { return h.id === hotspot; })[0] || {}).name;
};

// Camera presets. "As seen by" views put the virtual camera at that camera's Fig. 3 position and set the
// vertical view angle so the TP field of view fills the frame (approximate: lens geometry not given).
OF.setCameraView = function (view) {
  if (!threeReady) return;
  var P = OF.SCENE, t = new THREE.Vector3(0, 0, 0);
  camera.fov = 40;
  if (view === "droplet") camera.position.set(6, 3.5, 10);
  else if (view === "flame") camera.position.set(28, 16, 44);
  else if (view === "optics") camera.position.set(0, 330, 120);
  else if (view === "layout") camera.position.set(0, 620, 0.01);
  else if (view === "chamber") camera.position.set(430, 300, 520);
  else if (P.cams[view]) {
    var o = new THREE.Vector3().fromArray(P.cams[view]).multiplyScalar(0.8), d = o.length();
    camera.position.copy(o);                                   // just in front of the lens, on the optical axis
    camera.fov = 2 * Math.atan((P.fov[view][1] / 2) / d) * 180 / Math.PI;
  }
  Object.keys(OF.S.cams || {}).forEach(function (k) { OF.S.cams[k].visible = k !== view; });
  (OF.S.labels || []).forEach(function (l) { l.visible = !P.cams[view]; });     // no labels inside camera views
  Object.keys(OF.S.frusta || {}).forEach(function (k) { OF.S.frusta[k].visible = OF.showFrusta && !P.cams[view]; });
  camera.updateProjectionMatrix();
  camera.lookAt(t);
  if (controls) { controls.target.copy(t); controls.update(); }
  OF.currentView = view;
  if (OF.timeline) OF.updateScene();
  document.querySelectorAll("[data-view]").forEach(function (b) { b.setAttribute("aria-pressed", b.getAttribute("data-view") === view ? "true" : "false"); });
};

OF.cutaway = false;
OF.toggleCutaway = function () {
  OF.cutaway = !OF.cutaway;
  if (OF.S.chamber) OF.S.chamber.visible = !OF.cutaway;
  var b = document.getElementById("btn-cutaway"); if (b) b.setAttribute("aria-pressed", OF.cutaway ? "true" : "false");
};
OF.showFrusta = true;
OF.toggleFrusta = function () {
  OF.showFrusta = !OF.showFrusta;
  Object.keys(OF.S.frusta || {}).forEach(function (k) { OF.S.frusta[k].visible = OF.showFrusta; });
  var b = document.getElementById("btn-frusta"); if (b) b.setAttribute("aria-pressed", OF.showFrusta ? "true" : "false");
};
