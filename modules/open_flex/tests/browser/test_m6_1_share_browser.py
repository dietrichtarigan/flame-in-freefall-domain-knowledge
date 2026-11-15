"""M6.1 browser tests: share a simulation run, check someone else's.

* a run file exported by the browser is accepted by the Python reference (check-run) and the other way round;
* tampering is caught; hostile strings are shown as text; an oversize file is refused;
* the post text keeps the labels (simulation, not FLEX, not validated, reproduced is not validated);
* the GitHub button appears only when a repository is configured; the run file holds no personal data or timestamp;
* accessibility (axe) with the share panel open, both themes.
"""
import copy
import json
import os
import re
import subprocess
import sys

import pytest
from test_m1_browser import DIST, NOVENDOR, ROOT, browser, open_page  # noqa: F401

AXE = open(os.path.join(ROOT, "vendor/test-only/axe-core-4.10.3/axe.min.js"), encoding="utf-8").read()


def py_check(path):
    p = subprocess.run([sys.executable, "-m", "openflex", "check-run", path], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": ROOT})
    return p.returncode, p.stdout + p.stderr


def py_export(tmp_path, test, *extra):
    f = str(tmp_path / "py_run.json")
    p = subprocess.run([sys.executable, "-m", "openflex", "baseline", test, *extra, "--export", f], cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": ROOT})
    assert p.returncode == 0, p.stderr
    return f


def open_explore(browser, test="FLEX-035"):
    ctx, page, errors = open_page(browser, DIST)
    page.click("#tabbtn-physics")
    page.evaluate("t => OF.selectTest(t)", test)
    page.click("#mode-explore")
    page.wait_for_function("document.getElementById('ex-run-id') && /^SIM-[0-9a-f]{12}$/.test(document.getElementById('ex-run-id').textContent)")
    page.wait_for_function("!document.getElementById('btn-share-export').disabled")
    return ctx, page, errors


def setv(page, sel, v):
    page.fill(sel, v)
    page.dispatch_event(sel, "change")


def check(page, obj):
    text = obj if isinstance(obj, str) else json.dumps(obj)
    return page.evaluate("async t => { const r = await OF.share.check(t); return {status: r.status, checks: r.checks}; }", text)


def test_browser_run_is_reproduced_by_python(browser, tmp_path):
    ctx, page, errors = open_explore(browser)
    setv(page, "#ex-o2", "0.15")
    page.wait_for_function("OF.explore.last && OF.explore.last.inputs.X.O2 === 0.15 && OF.share.current && OF.share.current.inputs.X.O2 === 0.15")
    run = page.evaluate("OF.share.current")
    assert run["labels"]["evidence_class"] == "NUMERICAL_SIMULATION" and run["run_id"].startswith("SIM-")
    assert "X.O2" in run["modified_inputs"]
    f = tmp_path / "browser_run.json"
    f.write_text(json.dumps(run), encoding="utf-8")
    rc, out = py_check(str(f))
    assert rc == 0 and "REPRODUCED" in out, out
    res = check(page, run)                                      # and the browser accepts its own file
    assert res["status"] == "REPRODUCED" and all(c["pass"] for c in res["checks"])
    assert errors == []
    ctx.close()


def test_python_run_is_reproduced_by_browser(browser, tmp_path):
    f = py_export(tmp_path, "FLEX-035", "--O2", "0.15")
    ctx, page, errors = open_explore(browser)
    res = check(page, open(f, encoding="utf-8").read())
    assert res["status"] == "REPRODUCED", res
    f2 = py_export(tmp_path, "FLEX-035")
    assert check(page, open(f2, encoding="utf-8").read())["status"] == "REPRODUCED"
    assert errors == []
    ctx.close()


def test_every_test_exports_and_reproduces(browser):
    ctx, page, errors = open_explore(browser)
    bad = page.evaluate("""async () => {
        const bad = [];
        for (const r of OF.D.table_ix) {
            const I = OF.D2.seededInputs(r), o = OF.D2.solve(OF.D2.forSolve(I), OF.D.model.properties);
            if (o.K_mm2_s === null) continue;
            await OF.selectTest(r.flex_test); if (!OF.explore.on) document.getElementById('mode-explore').click();
            await OF.exploreRun();
            const run = await OF.share.buildRun(); if (!run) { bad.push(r.flex_test + ':norun'); continue; }
            const res = await OF.share.check(JSON.stringify(run)); if (res.status !== 'REPRODUCED') bad.push(r.flex_test + ':' + res.status);
        }
        return bad; }""")
    assert bad == []
    ctx.close()


@pytest.mark.parametrize("case", ["output", "run_id", "hash", "model_version", "range", "flex_id", "unknown_key", "modlist", "comparison", "not_json", "wrong_record"])
def test_tampering_is_caught(browser, case):
    ctx, page, errors = open_explore(browser)
    run = page.evaluate("OF.share.current")
    t = copy.deepcopy(run)
    expect = "NOT_REPRODUCED"
    if case == "output":
        t["outputs"]["K_mm2_s"] *= 1.01
    elif case == "run_id":
        t["run_id"] = "SIM-000000000000"
    elif case == "hash":
        t["content_sha256"] = "0" * 64
    elif case == "model_version":
        t["model"]["version"] = "9.9.9"; expect = "CANNOT_CHECK"
    elif case == "range":
        t["inputs"]["T_inf_K"] = 5000; expect = "INVALID"
    elif case == "flex_id":
        t["run_id"] = "FLEX-035"; expect = "INVALID"
    elif case == "unknown_key":
        t["extra"] = 1; expect = "INVALID"
    elif case == "modlist":
        t["modified_inputs"] = ["fuel"]
    elif case == "comparison":
        t["comparison"]["model_over_printed"] = 1.0
    elif case == "not_json":
        t = "this is not json"; expect = "INVALID"
    elif case == "wrong_record":
        t["record_type"] = "SomethingElse"; expect = "INVALID"
    res = check(page, t)
    assert res["status"] == expect, (case, res)
    assert errors == []
    ctx.close()


def test_hostile_strings_are_shown_as_text(browser):
    ctx, page, errors = open_explore(browser)
    run = page.evaluate("OF.share.current")
    t = copy.deepcopy(run)
    t["exported_by"] = "<img src=x onerror=window.__pwn=1><script>window.__pwn=1</script>"
    t["model"]["name"] = "<b id=pwn2>x</b>"
    check(page, t)
    page.wait_for_timeout(200)
    assert page.evaluate("window.__pwn") is None
    assert page.evaluate("document.querySelector('#share-result img, #share-result script, #pwn2')") is None
    assert "<img" in page.inner_text("#share-result") or "&lt;" in page.inner_html("#share-result")
    assert errors == []
    ctx.close()


def test_oversize_and_garbage_are_refused(browser):
    ctx, page, errors = open_explore(browser)
    assert check(page, "x" * (page.evaluate("OF.share.MAX_BYTES") + 1))["status"] == "INVALID"
    assert check(page, "")["status"] == "INVALID"
    assert check(page, "[1,2,3]")["status"] == "INVALID"
    assert check(page, "null")["status"] == "INVALID"
    assert errors == []
    ctx.close()


def test_whole_pasted_post_is_accepted(browser):
    ctx, page, errors = open_explore(browser)
    post = page.input_value("#share-post")
    assert check(page, post)["status"] == "REPRODUCED"
    ctx.close()


def test_post_text_keeps_the_labels(browser):
    ctx, page, errors = open_explore(browser)
    setv(page, "#ex-d0", "3.5")
    page.wait_for_function("OF.share.current && OF.share.current.inputs.D0_mm === 3.5")
    post = page.input_value("#share-post")
    run = page.evaluate("OF.share.current")
    assert run["run_id"] in post.splitlines()[0]
    for must in ("SIMULATION", "not a FLEX measurement", "not validated against FLEX", "does not mean the model agrees with FLEX", "no personal data", "FLEX-035"):
        assert must in post, must
    assert "validated by" not in post.lower() and "NASA-validated" not in post
    m = re.search(r"```json\n(.*)\n```", post, re.S)
    assert m and json.loads(m.group(1))["run_id"] == run["run_id"]
    assert "(modified)" in post.splitlines()[0]
    ctx.close()


def test_github_button_only_when_configured(browser):
    ctx, page, errors = open_explore(browser)
    assert page.evaluate("OF.D.share_config.github_repo") is None
    assert page.is_hidden("#lnk-share-gh")
    assert "No GitHub repository" in page.inner_text("#share-gh-note")
    assert page.evaluate("OF.share.githubUrl()") is None
    page.evaluate("OF.D.share_config.github_repo = 'someone/open-flex'")
    page.evaluate("OF.share.update()")
    page.wait_for_function("!document.getElementById('lnk-share-gh').hidden")
    assert page.get_attribute("#lnk-share-gh", "href") == "https://github.com/someone/open-flex/discussions/new?category=shared-runs"
    assert "noopener" in page.get_attribute("#lnk-share-gh", "rel")
    for bad in ("evil.com/x?y", "a b/c", "../x", "a/b/c", "http://evil/x", ""):
        page.evaluate("r => { OF.D.share_config.github_repo = r; }", bad)
        assert page.evaluate("OF.share.githubUrl()") is None, bad
    ctx.close()


def test_run_file_has_no_personal_data_or_timestamp(browser):
    ctx, page, errors = open_explore(browser)
    text = json.dumps(page.evaluate("OF.share.current"))
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)               # no dates
    assert not re.search(r"[\w.]+@[\w.]+", text)                   # no e-mail addresses
    assert "sebastian" not in text.lower() and "/home/" not in text and "\\Users\\" not in text
    keys = set(json.loads(text))
    assert keys == {"record_type", "format_version", "labels", "run_id", "model", "seeded_from_physical_test", "modified_inputs", "inputs", "outputs",
                    "comparison", "exported_by", "content_sha256"}
    ctx.close()


def test_download_and_load_into_explore(browser, tmp_path):
    f = py_export(tmp_path, "FLEX-035", "--O2", "0.15", "--D0", "3.0")
    ctx, page, errors = open_explore(browser, "FLEX-001")
    page.set_input_files("#share-file", f)
    page.wait_for_function("OF.share.lastResult && OF.share.lastResult.status === 'REPRODUCED'")
    assert page.is_visible("#btn-share-load")
    page.click("#btn-share-load")
    page.wait_for_function("OF.explore.last && OF.explore.last.seeded_from === 'FLEX-035' && OF.explore.last.inputs.X.O2 === 0.15")
    assert page.input_value("#ex-o2") == "0.15" and page.input_value("#ex-d0") == "3"
    assert page.evaluate("OF.explore.last.run_id") == json.load(open(f))["run_id"]
    with page.expect_download() as dl:
        page.click("#btn-share-export")
    name = dl.value.suggested_filename
    assert re.fullmatch(r"OpenFLEX_run_SIM-[0-9a-f]{12}\.json", name)
    p2 = tmp_path / name
    dl.value.save_as(str(p2))
    rc, out = py_check(str(p2))
    assert rc == 0, out
    ctx.close()


def test_export_disabled_without_a_run(browser):
    ctx, page, errors = open_explore(browser)
    setv(page, "#ex-o2", "2")                                     # invalid: mole fraction above 1
    page.wait_for_function("document.getElementById('btn-share-export').disabled || OF.share.current === null")
    assert page.is_disabled("#btn-share-copy") or page.evaluate("OF.share.current") is None
    ctx.close()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_share_panel_accessibility(browser, theme):
    ctx, page, errors = open_explore(browser)
    if theme == "dark":
        page.evaluate("document.documentElement.setAttribute('data-theme','dark')")
    page.evaluate("OF.share.check(JSON.stringify(OF.share.current))")
    page.wait_for_function("OF.share.lastResult")
    page.add_script_tag(content=AXE)
    res = page.evaluate("axe.run('#share-details', {runOnly: ['wcag2a','wcag2aa','wcag21aa']})")
    assert [(v["id"], v["impact"]) for v in res["violations"]] == [], res["violations"]
    ctx.close()
