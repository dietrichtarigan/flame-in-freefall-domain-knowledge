"""M2 browser tests: fiber status, test-matrix box, discrepancies, literature cases, dataset manifest.

Headless Chrome via Playwright; all http(s) requests are aborted (offline).
"""
import hashlib
import json
import os

import pytest
from test_m1_browser import CHROME, DIST, ROOT, browser, open_page  # noqa: F401  (fixture reuse)

RECS = {r["test_id"]: r for r in json.load(open(os.path.join(ROOT, "data/records/physical_tests.json"), encoding="utf-8"))["records"]}
MAN = json.load(open(os.path.join(ROOT, "data/MANIFEST.json"), encoding="utf-8"))


def record_rows(page):
    cells = page.eval_on_selector_all("#record-table tr", "rows => rows.map(r => [...r.cells].map(c => c.textContent))")
    return {c[0]: (c[1], c[2]) for c in cells}


@pytest.mark.parametrize("tid,display,klass", [
    ("FLEX-023", "Free-floating", "Published (test matrix + caption agree)"),
    ("FLEX-040", "Fiber-supported", "Published (test matrix + caption agree)"),
    ("FLEX-053", "Sources disagree", "Sources disagree"),
    ("FLEX-124", "Sources disagree", "Sources disagree"),
    ("FLEX-200", "Free-floating (caption only)", "Published (caption only)"),
])
def test_fiber_status_shown(browser, tid, display, klass):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", tid)
    page.wait_for_timeout(150)
    val, cls = record_rows(page)["Fiber support"]
    assert val.startswith(display) and cls == klass
    if RECS[tid]["fiber"]["status"] == "DIFFERS":
        assert "Table" in val and "caption" in val
    assert errors == []
    ctx.close()


def test_matrix_box_flex_023(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-023")
    page.wait_for_timeout(150)
    txt = page.inner_text("#record-matrix")
    assert "Table III" in txt and "3.18" in txt and ".400" in txt
    assert txt.count("beyond printed rounding") >= 3          # D0, O2, N2 differ from Table IX
    # Table IX values are unchanged next to it
    assert record_rows(page)["D₀ at igniter ON (CLM-018)"][0].startswith("3.01")
    assert errors == []
    ctx.close()


def test_matrix_absent_and_discrepancies(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-200")
    page.wait_for_timeout(150)
    assert "Not listed in Tables I–VIII" in page.inner_text("#record-matrix")
    page.select_option("#test-select", "FLEX-053")
    page.wait_for_timeout(150)
    assert "not compared (Table IX prints –)" in page.inner_text("#record-matrix")   # D0 is '–' in Table IX
    page.select_option("#test-select", "FLEX-070")
    page.wait_for_timeout(150)
    flags = page.inner_text("#record-flags")
    assert "DSC-016" in flags and "193F001" in flags
    assert errors == []
    ctx.close()


def test_literature_cases_are_candidates(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-110")
    page.wait_for_timeout(150)
    lit = page.inner_text("#record-literature")
    assert "LIT-Dietrich-2014-FIG6-CO2" in lit and "CANDIDATE" in lit and "CONFIRMED" not in lit
    assert errors == []
    ctx.close()


def test_dataset_manifest_matches_files(browser):
    ctx, page, errors = open_page(browser, DIST)
    rows = page.eval_on_selector_all("#dataset-body tr", "rows => rows.map(r => [r.cells[0].textContent, r.cells[3].title])")
    assert len(rows) == len(MAN["datasets"])
    for d, (label, sha_title) in zip(MAN["datasets"], rows):
        assert label.startswith(d["dataset_id"])
        assert sha_title == hashlib.sha256(open(os.path.join(ROOT, d["path"]), "rb").read()).hexdigest()
    assert errors == []
    ctx.close()


def test_export_contains_fiber_and_matrix(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", "FLEX-053")
    page.wait_for_timeout(150)
    rec = page.evaluate("OF.exportableRecord(OF.testById['FLEX-053'])")
    assert rec["record_schema_version"] == "0.2.0"
    assert rec["fiber"]["status"] == "DIFFERS" and rec["test_matrix"]["locator"].startswith("Table V")
    assert "DSC-014" in rec["discrepancies"]
    assert errors == []
    ctx.close()
