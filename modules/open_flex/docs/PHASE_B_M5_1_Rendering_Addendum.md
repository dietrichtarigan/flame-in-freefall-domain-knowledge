# Phase B — M5.1 addendum: photorealistic rendering without changing the physics

Date: 15 Nov 2026. Prepared by Claude (AI assistant). Not a NASA product.

## 1. Objective

The user asked for lighting as photorealistic as their NASA video ("Amazing Flame Comes to Life in Space
Station Microgravity Combustion Science"), without sacrificing the physics. They supplied five
screenshots. Those frames are registered as source **S41**, in a new evidence class
**VISUAL_OBSERVATION**: qualitative appearance only. Which FLEX test the footage shows is not established,
so no size, colour value or timing is taken from it.

## 2. What the footage told us, and what changed

| Observation in the frames | Claim | Change in the 3D view |
|---|---|---|
| Igniters are open D-shaped wire loops at the ends of diagonal hex-fitted shafts | CLM‑049 | Igniters rebuilt as wire loops (0.25 mm wire, ≈4 mm loop; sizes not in the TP, stated as such) |
| Droplet held between thin opposed needle tips on L-shaped arms | CLM‑049 | Needles rebuilt as thin tips on L arms leaving in opposite directions |
| Machined aluminium, black anodised plates, brass fittings; dark surroundings | — | Physically based materials with environment reflections; reflections strong only while the LED is on (CLM‑048) |
| Hot igniter wires glow white at ignition | CLM‑050 | Incandescent glow from t = 0 with a small light; the cooling after retraction (time constant 0.6 s) is labelled illustrative |
| Bright luminous core around the droplet inside a dimmer blue spherical shell | CLM‑050, CLM‑045 | Volumetric flame (§3) |
| Coloured single-pixel noise on the dark background | CLM‑050 | Optional "Camera look" speckle, only in the colour-camera view, labelled cosmetic |

## 3. How the flame is rendered, and why it keeps the physics

- **Size and timing come only from data, as in M5.** The flame's outer edge is the digitized diameter. When
  only LLUV data exist, it is drawn at the LLUV edge and the readout says so. With no data, the unscaled "?"
  marker stays.
- **Radial emission model.** The flame emits in a thin blue sheet just inside the measured outer edge
  (CLM‑046). When, and only when, the caption reports soot luminosity, there is also a broad soot glow inside
  that blue envelope (CLM‑045); its radius is not measured, so it has no sharp edge. Nothing emits inside the
  droplet.
- **Abel projection.** What the camera sees is that emission integrated along each line of sight through an
  optically thin sphere. The projection is precomputed per droplet-to-flame size ratio into a lookup
  texture, which is exact and fast. Ray-marching of the same profiles is used only when the camera is inside
  the flame. The bright rim in the NASA frames (limb brightening) comes out of this integration; it is not
  painted on.
- **Lighting follows the procedure.**
  - The LED lights the hardware only during droplet formation; it is off from just before deployment
    (CLM‑048).
  - During the burn the flame is the only light source, with realistic falloff. Sooty flames are much
    brighter than blue ones; these values are approximate.
- **Instrument views unchanged.** HiBMs shows a silhouette, LLUV shows only the OH* edge, and the colour
  camera shows the visible flame. The ultraviolet LLUV ring is a measurement overlay and never appears in
  camera views.
- **What is approximate, and labelled so on screen** ("LIGHTING/COLOUR APPROXIMATE, NOT RADIOMETRIC"):
  colours and absolute brightness; the soot distribution's shape; the droplet's refraction (handbook
  refractive indices, not from the TP); bloom; film response; and speckle.

## 4. Libraries

Vendored from three.js r128 `examples/js`, pinned with SHA‑256 in `vendor/VENDOR.json`:
- EffectComposer, RenderPass, ShaderPass, UnrealBloomPass;
- CopyShader, LuminosityHighPassShader, GammaCorrectionShader;
- RoomEnvironment.

Without them the view renders without bloom; without three.js the 2D fallback still works.

## 5. Tests

7 new tests in `tests/browser/test_m5_render.py`.

| Check | Result |
|---|---|
| **Rendered flame edge equals the measured diameter.** The flame alone is rendered with bloom off, and the edge measured in screen pixels must match the projected data diameter within 3 px or 5 %. Tested on FLEX‑035, ‑023 (LLUV edge), ‑062 and ‑264. | pass |
| Volume uniforms follow the data (droplet/flame ratio, soot only when the caption says so) | pass |
| Lights follow the procedure: LED only during formation; flame light only with a measured flame; igniters cold before t = 0 and glowing after | pass |
| No flame volume or flame light for a test without flame data | pass |
| UV ring never in camera views; speckle only in the colour view and switchable | pass |
| Post-processing libraries vendored and active | pass |
| Full suite (including axe in both themes and the timeline checks for all 276 tests) | **137 / 137 pass** |

The tests were run in headless Chrome with software WebGL, which is slow: the full suite takes about
9 minutes. Real GPUs were not tested.

## 6. Limitations

- The footage's test is unknown. Matching its look does not mean matching its conditions.
- The early ignition shape in the video (a flame elongated along the igniters) is not drawn: there are no
  data for it, so the flame is spherical from the first data point.
- Hardware beyond what Fig. 3 and the frames show (cables, filters, chamber walls) is not added.
