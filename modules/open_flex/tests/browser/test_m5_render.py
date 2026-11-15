"""M5.1 photorealistic rendering: the look must not change the physics. Offline, headless Chrome (SwiftShader).

* The rendered flame edge (bloom off) lies at the measured diameter, measured in screen pixels.
* Volume uniforms follow the data (droplet radius ratio, soot flag); no flame volume without flame data.
* Lighting follows the procedure: LED light only during droplet formation; flame light only while a flame
  with a measured size exists; igniters glow from t = 0 and not before.
* LLUV ring (ultraviolet, invisible to the colour camera) is never drawn inside camera views.
* Cosmetic camera look appears only in the colour-camera view and can be switched off.
"""
import io
import json
import os
import re

import pytest
from PIL import Image
from test_m1_browser import DIST, ROOT, browser, open_page  # noqa: F401

VENDOR = json.load(open(os.path.join(ROOT, "vendor/VENDOR.json"), encoding="utf-8"))


def test_postprocessing_libraries_vendored_and_active(browser):
    paths = {f["path"] for f in VENDOR["files"]}
    for f in ("EffectComposer.js", "RenderPass.js", "ShaderPass.js", "UnrealBloomPass.js", "CopyShader.js",
              "LuminosityHighPassShader.js", "GammaCorrectionShader.js", "RoomEnvironment.js"):
        assert "three-r128/" + f in paths
    ctx, page, errors = open_page(browser, DIST)
    assert page.evaluate("threeReady && !!OF.S.composer && !!OF.S.bloom && !!OF.S.hasEnv")
    assert page.evaluate("renderer.toneMapping === THREE.ACESFilmicToneMapping")
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("tid,frac", [("FLEX-035", 0.45), ("FLEX-023", 0.25), ("FLEX-062", 0.5), ("FLEX-264", 0.4)])
def test_rendered_flame_edge_equals_measured_diameter(browser, tid, frac):
    ctx = browser.new_context(viewport={"width": 1200, "height": 900})
    try:
        _edge_check(ctx, tid, frac)
    finally:
        ctx.close()


def _edge_check(ctx, tid, frac):
    ctx.route(re.compile(r"^https?://"), lambda route: route.abort())
    page = ctx.new_page()
    page.goto(DIST)
    page.wait_for_function("window.OF && OF.ready === true")
    page.click("#tabbtn-lab")
    page.select_option("#test-select", tid)
    t = page.evaluate(f"""(() => {{ const T = OF.timeline; for (let k = 0; k < 40; k++) {{ const t = T.tb * ({frac} + 0.01 * k);
        const f = T.state(t).flame; if (f.visible_D_mm !== null || f.lluv_D_mm !== null) return t; }} return null; }})()""")
    assert t is not None
    page.evaluate(f"OF.scrub(OF.pOfT({t}))")
    fd = page.evaluate(f"(() => {{ const f = OF.timeline.state({t}).flame; return f.visible_D_mm !== null ? f.visible_D_mm : f.lluv_D_mm; }})()")
    # isolate the flame: no hardware, no overlays, no bloom; camera on an axis looking at the droplet
    page.evaluate("""(() => { OF.overlays = false; OF.S.bloom.enabled = false; OF.setCameraView('flame');
        scene.traverse(o => { if (o.isMesh || o.isLine || o.isLineSegments || o.isSprite) { if (o !== OF.S.flameVis) o.userData._v = o.visible; } });
        scene.children.forEach(o => { if (o !== OF.S.flameVis && !o.isLight) o.visible = false; });
        camera.position.set(0, 0, 200); camera.fov = 20; camera.updateProjectionMatrix(); camera.lookAt(0, 0, 0);
        if (controls) { controls.enabled = false; }
        OF.frameUniforms(); OF.S.composer.render(); })()""")
    page.wait_for_timeout(300)
    page.evaluate("OF.frameUniforms(); OF.S.composer.render();")
    shot = page.locator("#three-container canvas").screenshot()
    im = Image.open(io.BytesIO(shot)).convert("L")
    W, H = im.size
    row = [im.getpixel((x, H // 2)) for x in range(W)]
    bg = sorted(row)[len(row) // 10]
    peak = max(row)
    lit = [x for x, v in enumerate(row) if v - bg > 0.08 * (peak - bg)]
    r_meas = (lit[-1] - lit[0] + 1) / 2
    import math
    r_exp = (fd / 2) / (200 * math.tan(math.radians(10))) * (H / 2)
    assert abs(r_meas - r_exp) <= max(3, 0.05 * r_exp), (tid, r_meas, r_exp)


def test_uniforms_and_lights_follow_data(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-lab")
    page.select_option("#test-select", "FLEX-023")
    page.evaluate("OF.scrub(OF.pOfT(3))")
    u = page.evaluate("""(() => { const s = OF.timeline.state(3), U = OF.S.flameVis.material.uniforms;
        const fd = s.flame.visible_D_mm !== null ? s.flame.visible_D_mm : s.flame.lluv_D_mm;
        return [U.uRdrop.value, 0.5 * s.droplet.D_mm / fd, U.uSoot.value, s.flame.soot,
                OF.S.flameLight.intensity, OF.S.ledLight.intensity]; })()""")
    assert abs(u[0] - u[1]) < 1e-12 and u[2] == (1 if u[3] else 0) and u[4] > 0 and u[5] == 0
    # LED on during droplet formation, no flame light then; igniters cold before t = 0
    page.evaluate("OF.jumpStage(4)")
    assert page.evaluate("OF.S.ledLight.intensity > 0 && OF.S.flameLight.intensity === 0 && !OF.S.flameVis.visible")
    assert page.evaluate("OF.S.igniters.every(g => g.glow.intensity === 0)")
    page.evaluate("OF.scrub(OF.pOfT(0.1))")
    assert page.evaluate("OF.S.igniters.every(g => g.glow.intensity > 0)")
    # a test without flame data: no volume, no flame light, only the unscaled marker
    page.select_option("#test-select", "FLEX-200")
    page.evaluate("OF.scrub(OF.pOfT(5))")
    assert page.evaluate("!OF.S.flameVis.visible && OF.S.flameLight.intensity === 0 && OF.S.glyph.visible")
    assert errors == []
    ctx.close()


def test_camera_views_and_cosmetic_look(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-lab")
    page.select_option("#test-select", "FLEX-035")
    page.evaluate("OF.scrub(OF.pOfT(4))")
    assert page.evaluate("OF.S.flameUV.visible")                                     # overlay in the free view
    for v in ("colour", "hibms", "lluv"):
        page.click(f"[data-view={v}]")
        assert not page.evaluate("OF.S.flameUV.visible"), v                         # UV ring never in camera views
        assert page.is_visible("#camlook-canvas") == (v == "colour"), v
    page.click("[data-view=colour]")
    assert "cosmetic camera look" in page.inner_text("#camview-note")
    page.click("#btn-camlook")
    assert not page.is_visible("#camlook-canvas")
    page.click("#btn-camlook")
    page.click("[data-view=flame]")
    page.click("#btn-overlays")
    assert not page.evaluate("OF.S.flameUV.visible")
    assert errors == []
    ctx.close()
