"""M3 browser tests: digitized plots, labels, table view, fallback without Plotly (offline, headless Chrome)."""
import csv
import os

import pytest
from test_m1_browser import DIST, NOVENDOR, ROOT, browser, open_page  # noqa: F401


def rows(rel):
    return sum(1 for _ in csv.DictReader(open(os.path.join(ROOT, rel), encoding="utf-8")))


@pytest.mark.parametrize("tid,fig,nseries", [("FLEX-023", 27, 2), ("FLEX-035", 39, 3)])
def test_digitized_panel(browser, tid, fig, nseries):
    ctx, page, errors = open_page(browser, DIST)
    page.select_option("#test-select", tid)
    page.wait_for_timeout(600)
    txt = page.inner_text("#timeseries-status")
    assert "Digitized, not original data." in txt and f"Figure {fig}" in txt
    assert page.inner_text("#plot-prov-badge") == "DIGITIZED FROM SOURCE PLOT"
    assert "not an uncertainty interval" in txt.replace("**", "") or "not\nan uncertainty interval" in txt or "not an uncertainty" in txt
    assert "Not a validation" in txt
    # Plotly drew both charts, separate axes (no dual-axis chart)
    assert page.locator("#plot-digitized-d2 .main-svg").count() >= 1
    assert page.locator("#plot-digitized-flame .main-svg").count() >= 1
    assert page.evaluate("document.getElementById('plot-digitized-d2').layout.yaxis2") is None
    n = page.evaluate("document.getElementById('plot-digitized-d2').data[0].x.length")
    assert n == rows(f"data/digitized/{tid}_fig{fig:03d}_droplet_d2.csv")
    assert page.evaluate("document.getElementById('plot-digitized-flame').data.length") == nseries - 1
    # table view has every point
    assert page.locator("#dig-table tbody tr").count() == sum(
        rows(f"data/digitized/{f}") for f in os.listdir(os.path.join(ROOT, "data/digitized")) if f.startswith(tid))
    assert errors == []
    ctx.close()


def test_other_tests_still_unavailable(browser):
    ctx, page, errors = open_page(browser, DIST)
    for tid in ["FLEX-001", "FLEX-070", "FLEX-280"]:
        page.select_option("#test-select", tid)
        page.wait_for_timeout(150)
        assert "Time series unavailable." in page.inner_text("#timeseries-status")
        assert page.inner_text("#plot-prov-badge") == "UNAVAILABLE IN THIS BUILD"
        assert page.locator("#plot-digitized-d2").count() == 0
    assert errors == []
    ctx.close()


def test_digitized_without_plot_library(browser):
    ctx, page, errors = open_page(browser, NOVENDOR)
    page.select_option("#test-select", "FLEX-035")
    page.wait_for_timeout(300)
    assert "Plot library unavailable — use the table view below." in page.inner_text("#plot-digitized-d2")
    assert page.locator("#dig-table tbody tr").count() > 100
    assert errors == []
    ctx.close()
