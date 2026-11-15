"""M5 browser tests: data-driven burn timeline (physics rules), 3D scene follows the timeline, instrument views,
picking, ARIA tabs, axe-core audit, responsive layout, reduced motion. Offline, headless Chrome (SwiftShader WebGL)."""
import csv
import json
import os
import re
import statistics

import pytest
from test_m1_browser import CHROME, DIST, NOVENDOR, ROOT, TABLE, browser, open_page  # noqa: F401

AXE = open(os.path.join(ROOT, "vendor/test-only/axe-core-4.10.3/axe.min.js"), encoding="utf-8").read()
SPEC = json.load(open(os.path.join(ROOT, "data/datasets.spec.json"), encoding="utf-8"))["datasets"]
DIG = {}
for d in SPEC:
    if d["data_class"] == "DIGITIZED" and d.get("series"):
        rows = list(csv.reader(open(os.path.join(ROOT, d["path"]), encoding="utf-8")))[1:]
        DIG.setdefault(d["test_id"], {})[d["series"]] = sorted((float(r[0]), float(r[1])) for r in rows)
RECS = {r["test_id"]: r for r in json.load(open(os.path.join(ROOT, "data/records/physical_tests.json"), encoding="utf-8"))["records"]}


def py_window(series, t, half=0.25, bridge=0.75):
    vals = [v for (tt, v) in series if abs(tt - t) <= half]
    if vals:
        return statistics.median(vals)
    lo = [p for p in series if p[0] <= t]
    hi = [p for p in series if p[0] > t]
    if lo and hi and t - lo[-1][0] <= bridge and hi[0][0] - t <= bridge:
        (t0, v0), (t1, v1) = lo[-1], hi[0]
        return v0 + (t - t0) / (t1 - t0) * (v1 - v0)
    return None


def test_timeline_rules_for_every_test(browser):
    """Reconstructed tests: D² = D0² − K t to the printed burn time; flame only in [0, t_b] and never with a size;
    test end applied after t_b. Digitized tests: droplet and flame equal the digitized data (same rule as Python)."""
    ctx, page, errors = open_page(browser, DIST)
    res = page.evaluate("""() => OF.D.table_ix.map(r => {
        const T = OF.Timeline.build(r.flex_test), tb = T.tb, ts = [];
        for (let t = T.tStart; t <= T.tMax; t += 0.37) ts.push(t);
        if (tb !== null) { ts.push(0); ts.push(tb); ts.push(tb + 0.2); }
        ts.sort((a, b) => a - b);
        return { id: r.flex_test, tb: tb, dig: T.hasDigitizedDroplet, flameData: T.hasFlameSize,
                 states: ts.map(t => { const s = T.state(t); return [t, s.droplet.D_mm, s.droplet.source, s.flame.present,
                     s.flame.visible_D_mm, s.flame.lluv_D_mm, s.flame.size_source]; }) };
    })""")
    assert len(res) == 276
    checked_dig = 0
    for r in res:
        row = TABLE[r["id"]]
        D0 = float(row["D0_mm"]) if row["D0_mm"] not in ("", "None") else None
        K = float(row["K_mm2_s"]) if row["K_mm2_s"] not in ("", "None") else None
        tb = r["tb"]
        prev = None
        for t, D, src, present, vis, uv, ssrc in r["states"]:
            if tb is not None:
                assert present == (t >= 0 and t <= tb) or (r["flameData"] and t >= 0 and t <= tb), (r["id"], t)
                if t > tb:
                    assert not present, (r["id"], t)
            if not r["flameData"]:
                assert vis is None and uv is None, (r["id"], t)                    # no flame size without data
                if present:
                    assert ssrc == "NOT_AVAILABLE"
            if r["dig"]:
                continue
            if t > (tb if tb is not None else 1e9):
                end = row["test_end"]
                if end == "Disruption":
                    assert D is None and src == "REMOVED_AT_DISRUPTION", (r["id"], t)
                elif end == "Completion":
                    assert D == 0, (r["id"], t)
                continue
            if D0 is not None and K is not None and tb is not None and t >= 0:
                assert abs(D * D - max(0.0, D0 * D0 - K * min(t, tb))) < 1e-9, (r["id"], t, D)
                if prev is not None:
                    assert D <= prev + 1e-12                                      # monotone shrinking during the burn
                prev = D
            elif D0 is not None and t <= 0:
                assert abs(D - D0) < 1e-12
        if r["dig"]:
            checked_dig += 1
            series = DIG[r["id"]]
            for t, D, src, present, vis, uv, ssrc in r["states"]:
                exp = py_window(series["droplet_d2"], t)
                if r["id"] and row["test_end"] == "Disruption" and tb is not None and t > tb:
                    continue
                if exp is None:
                    assert D is None, (r["id"], t)
                else:
                    assert abs(D - max(0.0, exp) ** 0.5) < 1e-9, (r["id"], t, D, exp)
                if present and "color_camera_flame_diameter" in series:
                    e2 = py_window(series["color_camera_flame_diameter"], t)
                    assert (vis is None and e2 is None) or abs(vis - e2) < 1e-9, (r["id"], t)
                if present and "lluv_flame_diameter" in series:
                    e3 = py_window(series["lluv_flame_diameter"], t)
                    assert (uv is None and e3 is None) or abs(uv - e3) < 1e-9, (r["id"], t)
    assert checked_dig == 13
    assert errors == []
    ctx.close()


def test_scene_follows_timeline(browser):
    ctx, page, errors = open_page(browser, DIST)
    assert page.evaluate("threeReady") is True
    page.click("#tabbtn-lab")
    for tid, t in [("FLEX-035", 3.0), ("FLEX-023", 4.0), ("FLEX-200", 5.0), ("FLEX-051", 2.0)]:
        page.select_option("#test-select", tid)
        page.evaluate(f"OF.scrub(OF.pOfT({t}))")
        s = page.evaluate(f"""(() => {{ const st = OF.timeline.state({t}); return {{
            D: st.droplet.D_mm, vis: st.flame.visible_D_mm, uv: st.flame.lluv_D_mm, soot: st.flame.soot,
            dropScale: OF.S.droplet.scale.x, dropVis: OF.S.droplet.visible, flameScale: OF.S.flameVis.scale.x,
            flameVis: OF.S.flameVis.visible, uvVis: OF.S.flameUV.visible, uvScale: OF.S.flameUV.scale.x,
            glyph: OF.S.glyph.visible, sootU: OF.S.flameVis.material.uniforms.uSoot.value, fiber: OF.S.fiber.visible,
            ro: document.getElementById('ro-droplet').textContent }} }})()""")
        assert s["dropVis"] and abs(s["dropScale"] - s["D"]) < 1e-9, tid               # droplet drawn at its true size
        assert s["ro"] == f"{s['D']:.2f} mm"
        if s["vis"] is not None:
            assert s["flameVis"] and abs(s["flameScale"] - s["vis"]) < 1e-9, tid
        elif s["uv"] is not None:
            assert s["flameVis"] and abs(s["flameScale"] - s["uv"]) < 1e-9, tid          # drawn at the LLUV edge
        if s["uv"] is not None:
            assert s["uvVis"] and abs(s["uvScale"] - s["uv"]) < 1e-9, tid
        if s["vis"] is None and s["uv"] is None:
            assert s["glyph"] and not s["flameVis"] and not s["uvVis"], tid             # unscaled marker only
        if s["vis"] is not None or s["uv"] is not None:
            assert s["sootU"] == (1 if s["soot"] else 0), tid                         # soot glow only when the caption reports it
        assert s["fiber"] == (tid == "FLEX-051"), tid
    # after extinction the flame is gone
    page.select_option("#test-select", "FLEX-035")
    page.evaluate("OF.scrub(OF.pOfT(9.5))")
    assert page.evaluate("!OF.S.flameVis.visible && !OF.S.flameUV.visible && !OF.S.glyph.visible")
    assert page.inner_text("#ro-flame") == "no flame"
    assert errors == []
    ctx.close()


def test_fiber_only_when_sources_say_so(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-lab")
    for tid in ["FLEX-051", "FLEX-040", "FLEX-035", "FLEX-053", "FLEX-124", "FLEX-233"]:
        page.select_option("#test-select", tid)
        page.evaluate("OF.jumpStage(10)")
        shown = page.evaluate("OF.S.fiber.visible")
        f = RECS[tid]["fiber"]
        assert shown == (f["status"] != "DIFFERS" and f["display"].startswith("Fiber-supported")), tid
    assert errors == []
    ctx.close()


def test_instrument_views(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-lab")
    page.select_option("#test-select", "FLEX-023")
    page.evaluate("OF.scrub(OF.pOfT(4))")
    page.click("[data-view=hibms]")
    assert page.evaluate("OF.S.droplet.visible && !OF.S.flameVis.visible && !OF.S.flameUV.visible && OF.S.droplet.material === OF.S.dropShadow")
    assert "backlit silhouette" in page.inner_text("#camview-note")
    page.click("[data-view=lluv]")
    assert page.evaluate("!OF.S.droplet.visible && OF.S.uvGlow.visible && !OF.S.flameVis.visible")
    assert page.evaluate("Math.abs(OF.S.uvGlow.scale.x - OF.timeline.state(4).flame.lluv_D_mm) < 1e-9")
    page.click("[data-view=colour]")
    assert page.evaluate("OF.S.flameVis.visible && OF.S.droplet.visible")
    # field of view of the 'as HiBMs' camera frames the TP's 30.25 mm square at the droplet
    page.click("[data-view=hibms]")
    h = page.evaluate("2 * camera.position.length() * Math.tan(camera.fov * Math.PI / 360)")
    assert abs(h - 30.25) < 1e-6
    page.click("[data-view=flame]")
    assert page.inner_text("#camview-note") == ""
    assert errors == []
    ctx.close()


def test_click_picking_selects_component(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-lab")
    page.select_option("#test-select", "FLEX-035")
    page.evaluate("OF.scrub(OF.pOfT(3)); OF.setCameraView('droplet')")
    page.wait_for_timeout(200)
    box = page.locator("#three-container canvas").bounding_box()
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_timeout(100)
    assert "Droplet and flame" in page.inner_text("#pick-status")
    assert page.evaluate("OF.activeHotspot") == "droplet_flame"
    page.evaluate("OF.setCameraView('layout')")
    page.wait_for_timeout(100)
    hits = page.evaluate("""(() => { const out = {}; const r = new THREE.Raycaster();
        OF.pickables.forEach(o => { if (o.userData.hotspot) out[o.userData.hotspot] = true; }); return Object.keys(out).sort(); })()""")
    assert {"cir_chamber", "needles", "igniters", "droplet_flame", "fiber", "hibms", "lluv_colour", "reservoirs", "mdca_insert"} <= set(hits)
    assert errors == []
    ctx.close()


def test_tabs_keyboard(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.focus("#tabbtn-overview")
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.id") == "tabbtn-lab"
    assert page.get_attribute("#tabbtn-lab", "aria-selected") == "true" and page.get_attribute("#tabbtn-lab", "tabindex") == "0"
    assert page.get_attribute("#tabbtn-overview", "tabindex") == "-1"
    assert page.is_visible("#tab-lab") and not page.is_visible("#tab-overview")
    page.keyboard.press("End")
    assert page.evaluate("document.activeElement.id") == "tabbtn-evidence"
    page.keyboard.press("ArrowRight")
    assert page.evaluate("document.activeElement.id") == "tabbtn-overview"
    page.keyboard.press("ArrowLeft")
    assert page.evaluate("document.activeElement.id") == "tabbtn-evidence"
    # every component is reachable without the 3D view (keyboard list)
    page.click("#tabbtn-lab")
    page.focus(".chip[data-id=igniters]")
    page.keyboard.press("Enter")
    assert page.evaluate("OF.activeHotspot") == "igniters"
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_axe_audit(browser, theme):
    ctx, page, errors = open_page(browser, DIST)
    page.add_script_tag(content=AXE)
    if theme == "dark":
        page.click("#btn-theme")
    found = []
    for tab in ["overview", "lab", "physics", "uq", "evidence"]:
        page.click(f"#tabbtn-{tab}")
        page.wait_for_timeout(300)
        v = page.evaluate("""async () => (await axe.run(document, {runOnly: {type: 'tag', values:
            ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}})).violations.map(v => [v.id, v.impact, v.nodes.length])""")
        found += [(tab,) + tuple(x) for x in v]
    assert [f for f in found if f[2] in ("serious", "critical")] == [], found
    assert found == [], found                                                         # in fact: no violations at all
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("width", [390, 1024, 1440])
def test_layout_widths(browser, width, tmp_path):
    ctx = browser.new_context(viewport={"width": width, "height": 900})
    ctx.route(re.compile(r"^https?://"), lambda route: route.abort())
    page = ctx.new_page()
    page.goto(DIST)
    page.wait_for_function("window.OF && OF.ready === true")
    for tab in ["overview", "lab", "physics", "uq", "evidence"]:
        page.click(f"#tabbtn-{tab}") if width > 500 else page.evaluate(f"OF.switchTab('{tab}')")
        page.wait_for_timeout(200)
        over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
        assert over <= 1, (tab, width, over)                                          # no horizontal page overflow
        page.screenshot(path=os.path.join(ROOT, "docs", "screens", f"m5_{tab}_{width}.png"), full_page=False)
    ctx.close()


def test_real_time_playback_and_reduced_motion(browser):
    ctx = browser.new_context(reduced_motion="reduce")
    ctx.route(re.compile(r"^https?://"), lambda route: route.abort())
    page = ctx.new_page()
    page.goto(DIST)
    page.wait_for_function("window.OF && OF.ready === true")
    assert page.evaluate("OF.reducedMotion") is True
    assert page.evaluate("OF.anim.playing") is False                                 # never autoplays
    page.click("#tabbtn-lab")
    page.evaluate("OF.scrub(OF.pOfT(2.0)); OF.anim.speed = 1")
    page.evaluate("OF.advance(1.0)")
    assert abs(page.evaluate("OF.tOfP(OF.anim.p)") - 3.0) < 1e-6                     # 1 s of wall time = 1 s of test time
    page.evaluate("OF.anim.speed = 4; OF.advance(0.5)")
    assert abs(page.evaluate("OF.tOfP(OF.anim.p)") - 5.0) < 1e-6
    assert page.evaluate("getComputedStyle(document.querySelector('.ev-flash') || document.body).animationName") in ("none", "")
    ctx.close()


def test_caption_driven_appearance(browser):
    ctx, page, errors = open_page(browser, DIST)
    r = page.evaluate("""(() => { const T = OF.Timeline.build('FLEX-051'); return [T.flags, T.state(0.3 * T.tb).flame.soot, T.state(0.6 * T.tb).flame.soot]; })()""")
    flags, early, late = r
    assert flags["soot_or_luminous"] and flags["luminous_ends"] and abs(flags["luminous_end_fraction"] - 0.5) < 1e-12
    assert early is True and late is False                                          # 'disappeared abruptly halfway'
    r2 = page.evaluate("OF.Timeline.build('FLEX-035').flags")
    assert r2["cool_flame_inferred"] and not r2["soot_or_luminous"]
    assert errors == []
    ctx.close()


def test_fallback_2d_without_three(browser):
    ctx, page, errors = open_page(browser, NOVENDOR)
    page.click("#tabbtn-lab")
    page.select_option("#test-select", "FLEX-035")
    page.evaluate("OF.scrub(OF.pOfT(3))")
    assert page.is_visible("#fallback-canvas") and not page.is_visible("#three-container")
    assert page.inner_text("#ro-droplet") != "—"
    assert errors == []
    ctx.close()
