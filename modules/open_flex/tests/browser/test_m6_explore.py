"""M6 browser tests: Explore mode with the D²-law educational baseline.

* the browser port reproduces the Python reference implementation (and its run ids) for every Table IX test;
* simulation runs are kept apart from physical tests (SIM ids, seed named, modifications listed);
* Explore mode is gated on a current, passing code-verification record;
* Explore mode does not change the physical record or the 3D scene;
* accessibility (axe) with the panel open, both themes; works without the plot library.
"""
import json
import os

import pytest
from test_m1_browser import DIST, NOVENDOR, ROOT, browser, open_page  # noqa: F401

RUNS = {r["seeded_from_physical_test"]: r for r in json.load(open(os.path.join(ROOT, "data/simulations/d2law_baseline_runs.json"), encoding="utf-8"))["runs"]}
AXE = open(os.path.join(ROOT, "vendor/test-only/axe-core-4.10.3/axe.min.js"), encoding="utf-8").read()


def rel(a, b):
    if a is None or b is None:
        return 0.0 if a is b else 1.0
    return abs(a - b) / max(abs(b), 1e-30)


def test_js_port_matches_python_for_every_test(browser):
    ctx, page, errors = open_page(browser, DIST)
    res = page.evaluate("""async () => {
        const T = OF.D.model.properties, sha = OF.D.model.verification.property_table_sha256, out = {};
        for (const r of OF.D.table_ix) {
            const I = OF.D2.seededInputs(r), o = OF.D2.solve(OF.D2.forSolve(I), T);
            out[r.flex_test] = {id: await OF.D2.runId(I, sha), K: o.K_mm2_s, B: o.B, Tf: o.T_flame_K, fsr: o.flame_standoff_ratio,
                                Tp: o.T_prop_K, tb: o.t_burn_s, flags: o.flags};
        }
        return out; }""")
    assert len(res) == len(RUNS) == 276
    worst = 0.0
    for tid, js in res.items():
        py = RUNS[tid]
        assert js["id"] == py["run_id"], tid                         # same identity rule in both implementations
        o = py["outputs"]
        for a, b in ((js["K"], o["K_mm2_s"]), (js["B"], o["B"]), (js["Tf"], o["T_flame_K"]), (js["fsr"], o["flame_standoff_ratio"]),
                     (js["Tp"], o["T_prop_K"]), (js["tb"], o["t_burn_s"])):
            worst = max(worst, rel(a, b))
        assert js["flags"] == o["flags"], tid
    assert worst < 1e-5, worst                                       # Python values are stored to 6 significant figures
    assert errors == []
    ctx.close()


def test_explore_mode_seeds_labels_and_separates_simulation(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-physics")
    assert page.is_enabled("#mode-explore")
    assert page.is_hidden("#explore-panel")
    page.click("#mode-explore")
    page.wait_for_function("document.getElementById('ex-run-id') && /^SIM-[0-9a-f]{12}$/.test(document.getElementById('ex-run-id').textContent)")
    st = page.inner_text("#ex-status")
    assert "SIMULATION" in st and "not FLEX data" in st and "FLEX–035" in st and "Modified" not in st
    assert page.inner_text("#ex-run-id") == RUNS["FLEX-035"]["run_id"]
    assert page.evaluate("OF.explore.last.seeded_from") == "FLEX-035"
    out = page.inner_text("#ex-out")
    assert "Table IX" in out and ".43" in out and "not validation" in out.lower()
    # change O2: modified run, new id, printed K no longer offered as the comparison, N2 takes the balance
    page.fill("#ex-o2", "0.15")
    page.dispatch_event("#ex-o2", "change")
    page.wait_for_function("OF.explore.last && OF.explore.last.modified.length > 0")
    st = page.inner_text("#ex-status")
    assert "Modified" in st and "X_O2 0.21 → 0.15" in st and "does not describe FLEX–035" in st
    last = page.evaluate("OF.explore.last")
    assert last["run_id"] != RUNS["FLEX-035"]["run_id"] and abs(last["inputs"]["X"]["N2"] - 0.85) < 1e-9
    assert "inputs differ from the test" in page.inner_text("#ex-out")
    assert not page.inner_text("#ex-run-id").startswith("FLEX")
    # physical record untouched; reset restores the printed seed
    assert page.inner_text("#record-table").count("0.21") + page.inner_text("#record-table").count(".21") >= 1
    page.click("#btn-explore-reset")
    page.wait_for_function("OF.explore.last && OF.explore.last.modified.length === 0")
    # follows test selection; switching back to Source record hides the panel
    page.evaluate("OF.selectTest('FLEX-023')")
    page.wait_for_function("OF.explore.last && OF.explore.last.seeded_from === 'FLEX-023'")
    assert page.inner_text("#ex-run-id") == RUNS["FLEX-023"]["run_id"]
    page.click("#mode-replay")
    assert page.is_hidden("#explore-panel")
    assert errors == []
    ctx.close()


def test_explore_does_not_change_scene_or_record(browser):
    ctx, page, errors = open_page(browser, DIST)
    snap = """() => ({rec: document.getElementById('record-table').textContent, tb: OF.timeline.tb,
                     u: OF.S.flameVis ? OF.S.flameVis.material.uniforms.uRdrop.value : null, t: OF.anim ? OF.anim.t : null})"""
    before = page.evaluate(snap)
    page.click("#tabbtn-physics")
    page.click("#mode-explore")
    page.fill("#ex-o2", "0.30")
    page.dispatch_event("#ex-o2", "change")
    page.fill("#ex-d0", "4.5")
    page.dispatch_event("#ex-d0", "change")
    page.wait_for_function("OF.explore.last.modified.length === 3")    # O2, N2 (balance), D0
    after = page.evaluate(snap)
    assert before == after
    assert errors == []
    ctx.close()


def test_explore_gate(browser):
    ctx, page, errors = open_page(browser, DIST)
    assert page.evaluate("OF.D.model.verification_current") is True
    assert page.evaluate("OF.D.model.verification.status") == "PASS"
    assert page.evaluate("OF.modelAvailable().ok") is True
    assert page.evaluate("(() => { OF.D.model.verification.status = 'FAIL'; return OF.modelAvailable().ok; })()") is False
    assert page.evaluate("(() => { OF.D.model.verification.status = 'PASS'; OF.D.model.verification_current = false; return OF.modelAvailable().ok; })()") is False
    ctx.close()
    # a page whose embedded record is not current starts with Explore disabled and says why
    ctx, page, errors = open_page(browser, DIST, init_script="""
        Object.defineProperty(window, 'OPEN_FLEX_DATA', {configurable: true, set(v) { v.model.verification_current = false;
            Object.defineProperty(window, 'OPEN_FLEX_DATA', {value: v, writable: true}); }});""")
    assert page.is_disabled("#mode-explore")
    assert "does not match" in page.inner_text("#mode-note")
    ctx.close()


def test_verification_table_and_sensitivity(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-physics")
    page.click("#mode-explore")
    page.wait_for_function("OF.explore.last")
    page.evaluate("document.querySelectorAll('#explore-panel details').forEach(d => d.open = true)")
    v = page.inner_text("#ex-verification")
    assert v.count("PASS") == page.evaluate("OF.D.model.verification.n_checks") and "FAIL" not in v
    s = page.inner_text("#ex-sens")
    assert "property temperature 600 K" in s and "%" in s
    assert "not an uncertainty interval" in page.inner_text("#explore-panel")
    assert page.evaluate("document.querySelectorAll('#explore-panel .js-plotly-plot').length") == 3
    assert errors == []
    ctx.close()


def test_explore_without_plot_library(browser):
    ctx, page, errors = open_page(browser, NOVENDOR)
    page.click("#tabbtn-physics")
    page.click("#mode-explore")
    page.wait_for_function("OF.explore.last")
    assert "Plot library unavailable" in page.inner_text("#explore-panel")
    assert "Burning-rate constant" in page.inner_text("#ex-out")
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_axe_explore(browser, theme):
    ctx, page, errors = open_page(browser, DIST)
    page.add_script_tag(content=AXE)
    if theme == "dark":
        page.click("#btn-theme")
    page.click("#tabbtn-physics")
    page.click("#mode-explore")
    page.wait_for_function("OF.explore.last")
    page.evaluate("document.querySelectorAll('#explore-panel details').forEach(d => d.open = true)")
    v = page.evaluate("""async () => (await axe.run(document.getElementById('tab-physics'), {runOnly: {type: 'tag', values:
        ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice']}})).violations.map(v => [v.id, v.impact, v.nodes.length, v.nodes[0].html.slice(0, 120)])""")
    assert v == [], v
    assert errors == []
    ctx.close()


def test_export_keeps_simulation_separate(browser):
    ctx, page, errors = open_page(browser, DIST)
    m = page.evaluate("OF.exportManifest()")
    assert m["is_ro_crate"] is False and "simulation_runs" not in m and "ro-crate-metadata.json" in m["note"]
    page.click("#tabbtn-physics")
    page.click("#mode-explore")
    page.wait_for_function("OF.explore.last")
    page.fill("#ex-o2", "0.18")
    page.dispatch_event("#ex-o2", "change")
    page.wait_for_function("OF.explore.last.modified.length > 0")
    m = page.evaluate("OF.exportManifest()")
    s = m["simulation_runs"][0]
    assert s["run_id"].startswith("SIM-") and s["seeded_from_physical_test"] == "FLEX-035" and s["inputs_modified_from_test"]
    assert m["record"]["test_id_normalized"] == "FLEX-035" and m["record"]["fields"]["X_O2"]["as_printed"] == ".21"   # record unchanged
    assert errors == []
    ctx.close()
