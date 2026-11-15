"""Deep link used by the Flame in Freefall dashboards: #test=FLEX-xxx&tab=<workspace>.

* a valid test id and tab open that test in that workspace;
* unknown test ids / tab names are ignored (default view), never guessed;
* changing the hash after load switches test and tab.
"""
from test_m1_browser import DIST, browser, open_page  # noqa: F401


def state(page):
    return page.evaluate("() => ({test: OF.state.testId, tab: OF.activeTab, sel: document.getElementById('test-select').value})")


def test_deeplink_opens_test_and_tab(browser):
    ctx, page, errors = open_page(browser, DIST + "#test=FLEX-110&tab=physics")
    assert state(page) == {"test": "FLEX-110", "tab": "physics", "sel": "FLEX-110"}
    assert errors == []
    ctx.close()


def test_deeplink_unknown_values_ignored(browser):
    ctx, page, errors = open_page(browser, DIST + "#test=FLEX-999&tab=nope")
    assert state(page) == {"test": "FLEX-035", "tab": "overview", "sel": "FLEX-035"}
    assert errors == []
    ctx.close()


def test_hashchange_after_load(browser):
    ctx, page, errors = open_page(browser, DIST)
    page.evaluate("() => { location.hash = 'test=FLEX-001&tab=evidence'; }")
    page.wait_for_function("OF.state.testId === 'FLEX-001' && OF.activeTab === 'evidence'", timeout=5000)
    assert errors == []
    ctx.close()
