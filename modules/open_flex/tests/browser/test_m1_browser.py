"""M1 browser acceptance tests (headless Chrome via Playwright).

All network requests are blocked, so these tests also prove the page works offline.
Run: python3 -m pytest -q tests/browser
"""
import csv
import json
import os
import re
import subprocess
import sys

import pytest
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIST = "file://" + os.path.join(ROOT, "dist", "open_flex_lab.html")
NOVENDOR = "file://" + os.path.join(ROOT, "dist", "test_no_vendor.html")
CHROME = os.environ.get("CHROME", "/usr/bin/google-chrome")

TABLE = {r["flex_test"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data", "extracted", "table_ix.csv"), encoding="utf-8"))}
CLAIMS = {c["claim_id"] for c in json.load(open(os.path.join(ROOT, "data", "registry", "claims.json"), encoding="utf-8"))["claims"]}
DISCS = {d["discrepancy_id"] for d in json.load(open(os.path.join(ROOT, "data", "registry", "discrepancies.json"), encoding="utf-8"))["discrepancies"]}

BANNED = [
    "D. Dietrich (Archival", "FTMD-ITB", "0.381", "± 0.019", "First-Order Sensitivity Ranking",
    "Seeded Monte Carlo", "Re-Run Seeded", "RO-Crate 1.3", "NASA_REPORTED / REPLAY", "SOURCE-TRACEABLE REPLAY",
    "PHYSICS_SIMULATION", "COOL_FLAME", "Archived / Replay", "CV Segmented", "kBarReported",
    "Dietrich2014-Fig", "2010-04-12", "2009-07-15", "FLEX-0035", "IN-DOMAIN (2009",
]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        yield b
        b.close()


def open_page(browser, url, init_script=None):
    ctx = browser.new_context(accept_downloads=True)
    ctx.route(re.compile(r"^https?://"), lambda route: route.abort())  # offline
    if init_script:
        ctx.add_init_script(init_script)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append("console.error: " + m.text) if m.type == "error" else None)
    page.goto(url)
    page.wait_for_function("window.OF && window.OF.ready === true", timeout=20000)
    return ctx, page, errors


def test_loads_offline_without_errors(browser):
    ctx, page, errors = open_page(browser, DIST)
    assert page.evaluate("typeof THREE") == "object"
    assert page.evaluate("typeof Plotly") == "object"
    page.wait_for_timeout(500)
    assert errors == [], errors
    print("threeReady (WebGL in headless Chrome):", page.evaluate("threeReady"))
    ctx.close()


def test_removed_content_absent(browser):
    ctx, page, _ = open_page(browser, DIST)
    # visible/readable text of every workspace (hidden tabs included); chart SVG path data and scripts excluded
    html = page.evaluate("""(() => { const c = document.body.cloneNode(true);
        c.querySelectorAll('script, svg, style').forEach(e => e.remove()); return c.textContent; })()""")
    for s in BANNED:
        assert s not in html, s
    assert page.locator("#plot-d2").count() == 0 and page.locator("#plot-fsr").count() == 0
    assert page.locator("#plot-sobol").count() == 0 and page.locator("#plot-mc-hist").count() == 0
    assert page.locator("#tab-commons").count() == 0
    ctx.close()


@pytest.mark.parametrize("tid", ["FLEX-023", "FLEX-035"])
def test_record_values_equal_table_ix(browser, tid):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", tid)
    page.wait_for_timeout(200)
    cells = page.eval_on_selector_all("#record-table tr", "rows => rows.map(r => [...r.cells].map(c => c.textContent))")
    got = {c[0]: c[1] for c in cells}
    r = TABLE[tid]
    assert got["Test number (as printed)"] == r["flex_test_as_printed"]
    assert got["CIR identifier"] == r["cir_identifier"]
    assert got["Ambient pressure"] == r["P_mmHg_raw"] + " mmHg"
    assert got["Mole fractions O₂ / N₂ / CO₂ / He"] == " / ".join(r[k] for k in ["X_O2_raw", "X_N2_raw", "X_CO2_raw", "X_He_raw"])
    assert got["D₀ at igniter ON (CLM-018)"].startswith(r["D0_mm_raw"])
    assert got["Burning rate K (CLM-019)"].startswith(r["K_mm2_s_raw"])
    assert got["Test end"] == r["test_end"]
    assert "Digitized, not original data." in page.inner_text("#timeseries-status")   # M3: pilot figures digitized
    assert errors == []
    ctx.close()


def test_every_table_ix_test_loads(browser):
    ctx, page, errors = open_page(browser, DIST)
    ids = page.eval_on_selector_all("#test-select option", "o => o.map(x => x.value)")
    assert sorted(ids) == sorted(TABLE)
    assert len(ids) == 276
    bad = page.evaluate("""async (ids) => { const bad = [];
        for (const id of ids) { await OF.selectTest(id);
          const first = document.querySelector('#record-table tr td:nth-child(2)').textContent;
          if (first !== OF.testById[id].flex_test_as_printed) bad.push(id); }
        return bad; }""", ids)
    assert bad == []
    assert errors == []
    ctx.close()


def test_sha256_is_genuine(browser):
    ctx, page, _ = open_page(browser, DIST)
    assert page.evaluate("OF.sha256Hex('abc')") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert re.fullmatch(r"[0-9a-f]{64}", page.evaluate("OF.state.recordSha256"))
    ctx.close()


def test_sha256_unavailable_is_reported_not_faked(browser):
    ctx, page, errors = open_page(browser, DIST, init_script="Object.defineProperty(window.crypto, 'subtle', {get(){return undefined}});")
    assert page.evaluate("OF.hashAvailable()") is False
    assert page.evaluate("OF.sha256Hex('abc')") is None
    assert "unavailable" in page.inner_text("#hdr-sha256")
    assert errors == []
    ctx.close()


def test_export_manifest(browser, tmp_path):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-035")
    page.wait_for_timeout(200)
    page.click("#tabbtn-evidence")
    with page.expect_download() as dl:
        page.click("#btn-export")
    path = tmp_path / "m.json"
    dl.value.save_as(path)
    m = json.load(open(path, encoding="utf-8"))
    assert m["is_ro_crate"] is False
    assert m["record"]["test_id_as_printed"] == "FLEX–035"
    assert m["record"]["fields"]["K_mm2_s"]["as_printed"] == TABLE["FLEX-035"]["K_mm2_s_raw"]
    assert abs(m["derived_here"]["composition_sum"]["value"] - 1.0) < 1e-9
    assert m["reported_measurement_uncertainty"]["coverage_factor"] == "not stated"
    assert re.fullmatch(r"[0-9a-f-]{36}", m["export_id"])
    r = subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "canonical_json.py"), str(path)], capture_output=True, text=True)
    assert "MATCH" in r.stdout and r.returncode == 0, r.stdout
    assert errors == []
    ctx.close()


def test_procedure_order_follows_tp(browser):
    ctx, page, _ = open_page(browser, DIST)
    labels = page.eval_on_selector_all(".stage-pill", "p => p.map(x => x.textContent)")
    idx = lambda s: [i for i, l in enumerate(labels) if s in l][0]
    assert idx("Start recording") < idx("Deploy") < idx("Ignite") < idx("Igniters off") < idx("Stop recording")
    assert idx("purge") < idx("Dispense") < idx("Stretch")
    ctx.close()


def test_component_card_tracks_stage(browser):
    ctx, page, _ = open_page(browser, DIST)
    page.evaluate("OF.jumpStage(8)")
    assert "Ignite" in page.inner_text("#bubble-content")
    page.evaluate("OF.jumpStage(2)")
    assert "Activate MDCA" in page.inner_text("#bubble-content")
    ctx.close()


def test_every_referenced_id_resolves(browser):
    ctx, page, _ = open_page(browser, DIST)
    texts = []
    for tid in ["FLEX-023", "FLEX-035", "FLEX-114", "FLEX-005"]:
        page.select_option("#test-select", tid)
        page.wait_for_timeout(100)
        for chip in page.eval_on_selector_all(".chip", "c => c.map(x => x.dataset.id)"):
            page.evaluate("id => OF.selectHotspot(id)", chip)
            texts.append(page.evaluate("document.body.innerText"))
    t = "\n".join(texts)
    assert set(re.findall(r"CLM-\d{3}", t)) <= CLAIMS, set(re.findall(r"CLM-\d{3}", t)) - CLAIMS
    assert set(re.findall(r"DSC-\d{3}", t)) <= DISCS
    ctx.close()


def test_library_unavailable_path(browser):
    ctx, page, errors = open_page(browser, NOVENDOR)
    assert page.evaluate("typeof THREE") == "undefined"
    assert "3D LIBRARY UNAVAILABLE" in page.inner_text("#lib-status-3d")
    page.click("#tabbtn-physics")
    assert "Plot library unavailable" in page.inner_text("#plot-radial")
    assert errors == [], errors
    ctx.close()
