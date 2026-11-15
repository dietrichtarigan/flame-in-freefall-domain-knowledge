"""M4 browser tests: provenance of every rendered quantitative statement, interval semantics, NASA ± wording,
claim navigation, result cards, uncertainty budget, coverage (parity with tools/coverage.py). Offline, headless Chrome."""
import json
import os
import random
import re
import sys

import pytest
from test_m1_browser import DIST, NOVENDOR, ROOT, browser, open_page  # noqa: F401

sys.path.insert(0, os.path.join(ROOT, "tools"))
import coverage as pycov  # noqa: E402

SCAN = open(os.path.join(os.path.dirname(__file__), "provenance_scan.js"), encoding="utf-8").read()
CLAIMS = {c["claim_id"] for c in json.load(open(os.path.join(ROOT, "data/registry/claims.json"), encoding="utf-8"))["claims"]}
DSCS = {d["discrepancy_id"] for d in json.load(open(os.path.join(ROOT, "data/registry/discrepancies.json"), encoding="utf-8"))["discrepancies"]}
UCS = {u["id"] for u in json.load(open(os.path.join(ROOT, "data/registry/uncertainty_components.json"), encoding="utf-8"))["components"]}
TESTS = ["FLEX-001", "FLEX-005", "FLEX-023", "FLEX-035", "FLEX-053", "FLEX-070", "FLEX-114", "FLEX-200", "FLEX-263", "FLEX-280"]


def visit_everything(page, tid, fn):
    page.select_option("#test-select", tid)
    page.wait_for_timeout(150)
    page.click("#tabbtn-lab")
    for ch in page.eval_on_selector_all("#cam-channel option", "o => o.map(x => x.value)"):
        page.select_option("#cam-channel", ch)
        fn(f"{tid}/{ch}")
    page.click("#tabbtn-physics")
    for opt in page.eval_on_selector_all("#result-select option", "o => o.map(x => x.value)"):
        page.select_option("#result-select", opt)
        fn(f"{tid}/result:{opt}")
    for chip in page.eval_on_selector_all(".chip", "c => c.map(x => x.dataset.id)")[:10]:
        page.evaluate("id => OF.selectHotspot(id)", chip)
        fn(f"{tid}/hotspot:{chip}")


def test_every_quantitative_statement_has_provenance(browser):
    ctx, page, errors = open_page(browser, DIST)
    bad = []
    for tid in TESTS:
        visit_everything(page, tid, lambda where: bad.extend(f"{where}: {x}" for x in page.evaluate(SCAN)))
    assert bad == [], "\n".join(bad[:30])
    assert errors == []
    ctx.close()


def test_all_rendered_ids_resolve(browser):
    ctx, page, errors = open_page(browser, DIST)
    for tid in TESTS:
        page.select_option("#test-select", tid)
        page.wait_for_timeout(100)
        text = page.evaluate("document.body.innerText")
        attrs = " ".join(page.eval_on_selector_all("[data-claims]", "e => e.map(x => x.getAttribute('data-claims'))"))
        for cid in set(re.findall(r"CLM-\d{3}", text + " " + attrs)):
            assert cid in CLAIMS, (tid, cid)
        for did in set(re.findall(r"DSC-\d{3}", text)):
            assert did in DSCS, (tid, did)
        for uid in set(re.findall(r"UC-\d{2}", text)):
            assert uid in UCS, (tid, uid)
    assert errors == []
    ctx.close()


SIGMA = re.compile(r"σ|sigma|standard deviation|95\s?%|confidence interval|\bCI\b", re.I)
NEG = re.compile(r"\b(not|no|never|wrongly|nor)\b", re.I)
NASA_PM = re.compile(r"±\s?(50|200|250)\s?µm")


def test_intervals_and_nasa_pm_semantics(browser):
    ctx, page, errors = open_page(browser, DIST)
    for tid in ["FLEX-023", "FLEX-035", "FLEX-005"]:
        page.select_option("#test-select", tid)
        page.wait_for_timeout(300)
        for el in page.eval_on_selector_all(".interval", "e => e.map(x => [x.dataset.intervalType, x.dataset.method, x.dataset.coverage])"):
            assert all(el), el                                            # type, method and coverage always present
        blocks = page.eval_on_selector_all("p, li, td, div.alert-box, .pred-row",
                                           "e => e.filter(x => !x.querySelector('p, li, td, div.alert-box, .pred-row')).map(x => x.innerText)")
        for b in blocks:
            if NASA_PM.search(b) and SIGMA.search(b):
                assert NEG.search(b), b                                   # ±50/200/250 µm never called σ/CI
            if re.search(r"\bconfidence interval\b|\b95\s?% (CI|interval)", b, re.I):
                assert NEG.search(b), b                                   # no interval is claimed to have coverage
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("selector,anchor_prefix", [("#record-flags a.ev-link[data-goto^='clm-']", "clm-"),
                                                     ("#record-flags a.ev-link[data-goto^='dsc-']", "dsc-")])
def test_links_navigate_to_evidence(browser, selector, anchor_prefix):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-070")
    page.click("#tabbtn-physics")
    page.wait_for_timeout(150)
    page.evaluate("document.getElementById('claim-search').value = 'zzz-no-match'; OF.renderClaims()")   # filtered ledger must be reset
    link = page.locator(selector).first
    target = link.get_attribute("data-goto")
    assert target.startswith(anchor_prefix)
    link.click()
    page.wait_for_timeout(300)
    assert page.evaluate("document.getElementById('tab-evidence').classList.contains('active')")
    assert page.locator("#" + target).is_visible()
    assert page.evaluate("t => document.activeElement && document.activeElement.id === t", target)
    assert errors == []
    ctx.close()


def test_source_link_in_ledger(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-evidence")
    page.locator("#clm-CLM-009 a.ev-link").first.click()
    page.wait_for_timeout(200)
    assert page.evaluate("document.activeElement.id") == "src-S01"
    assert errors == []
    ctx.close()


def test_result_cards(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-035")
    page.click("#tabbtn-physics")
    for opt in page.eval_on_selector_all("#result-select option", "o => o.map(x => x.value)"):
        page.select_option("#result-select", opt)
        rows = page.eval_on_selector_all("#result-panel .pred-row", "r => r.map(x => x.children[0].innerText)")
        assert rows == ["Result class", "Measurand", "Estimate", "Interval", "Interval type / coverage", "Method",
                        "Sample size", "Domain status", "Uncertainty components", "Evidence"], opt
        assert "None reported by the source" in page.inner_text("#result-panel")
    page.select_option("#result-select", "t_burn_s")
    assert "not defined in App. A.1" in page.inner_text("#result-panel")
    page.select_option("#result-select", "D_ext_visible_mm")
    assert "UC-06" in page.inner_text("#result-panel")
    # analysis card in digitized panel
    card = page.inner_text("#timeseries-status")
    assert "Window/estimator sensitivity range; no coverage probability" in card
    assert errors == []
    ctx.close()


@pytest.mark.parametrize("tid,has,lacks", [("FLEX-005", ["UC-10"], ["UC-12", "UC-13"]),
                                           ("FLEX-035", ["UC-12", "UC-13"], ["UC-10"]),
                                           ("FLEX-200", ["UC-01", "UC-06"], ["UC-10", "UC-12"])])
def test_budget_components(browser, tid, has, lacks):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", tid)
    ids = page.eval_on_selector_all("#uq-budget-table tr", "r => r.map(x => x.id.slice(3))")
    for u in has:
        assert u in ids
    for u in lacks:
        assert u not in ids
    txt = page.inner_text("#uq-budget-table")
    assert "coverage factor: not stated" in txt and "distribution: not specified" in txt
    assert errors == []
    ctx.close()


def test_coverage_parity_with_python(browser):
    ctx, page, errors = open_page(browser, DIST)
    rows = pycov.load_rows(ROOT)
    rnd = random.Random(42)
    queries = []
    for r in rows:                                                        # every test, excluding itself
        queries.append((r["fuel"], r["diluent"], {v: r[v] for v in pycov.VARS}, r["test_id"]))
    for _ in range(100):                                                  # random points, including outside ranges
        queries.append((rnd.choice(["heptane", "methanol"]), rnd.choice(["N2", "CO2", "He"]),
                        {"P_atm": rnd.uniform(0.4, 3.5), "X_O2": rnd.uniform(0.05, 0.45), "D0_mm": rnd.uniform(0.8, 5.5)}, None))
    js = page.evaluate("qs => qs.map(q => OF.coverage(q[0], q[1], q[2], q[3], 5))", queries)
    for q, got in zip(queries, js):
        exp = pycov.coverage(rows, q[0], q[1], q[2], q[3])
        assert got["label"] == exp["label"] and got["n_group"] == exp["n_group"], q
        assert got["outside"] == exp["outside"], q
        assert [n["test_id"] for n in got["nearest"]] == [n["test_id"] for n in exp["nearest"]], q
        assert all(abs(a["distance"] - b["distance"]) < 1e-4 for a, b in zip(got["nearest"], exp["nearest"])), q
    assert errors == []
    ctx.close()


def test_coverage_panel(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-035")
    page.click("#tabbtn-uq")
    assert "INSIDE NEAR TEST" in page.inner_text("#cov-result")
    page.fill("#cov-form [name=P_atm]", "3.0")
    page.click("#cov-form button[type=submit]")
    page.wait_for_timeout(150)
    t = page.inner_text("#cov-result")
    assert "OUTSIDE RANGE" in t and "P, atm" in t
    assert page.locator("#plot-coverage .main-svg").count() >= 1
    page.locator("#cov-result a.cov-goto").first.click()
    page.wait_for_timeout(150)
    assert page.evaluate("OF.state.testId") != "FLEX-035"
    assert errors == []
    ctx.close()


def test_coverage_without_plot_library(browser):
    ctx, page, errors = open_page(browser, NOVENDOR)
    page.click("#tabbtn-uq")
    assert "Plot library unavailable" in page.inner_text("#plot-coverage")
    assert "INSIDE" in page.inner_text("#cov-result") or "OUTSIDE" in page.inner_text("#cov-result")
    assert errors == []
    ctx.close()
