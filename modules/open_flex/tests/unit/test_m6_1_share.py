"""M6.1 unit tests: shared-run file format, reproduction check, CLI round trip."""
import copy
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from openflex import share  # noqa: E402
from openflex.data import DataPackage  # noqa: E402
import canonical_json  # noqa: E402

PKG = DataPackage()
ROWS = {r["flex_test"]: r for r in PKG.table_ix()}
RUNS = PKG.simulation_runs()
SCHEMA = json.load(open(os.path.join(ROOT, "schemas/shared_run.schema.json"), encoding="utf-8"))


def status(obj):
    return share.verify_run(obj, PKG)["status"]


@pytest.fixture
def run():
    return share.build_run(PKG, "FLEX-035", inputs=dict(share.seeded_inputs(ROWS["FLEX-035"]), D0_mm=2.5))


def test_seeded_inputs_equal_every_stored_run():
    assert len(RUNS) == 276
    for r in RUNS:
        assert share.seeded_inputs(ROWS[r["seeded_from_physical_test"]]) == r["inputs"], r["seeded_from_physical_test"]


def test_canonical_matches_tools_implementation():
    for v in (RUNS[0], RUNS[100]["inputs"], {"b": [1, 2.5, None, True], "a": "x"}, share.seeded_inputs(ROWS["FLEX-035"])):
        assert share.canonical(v) == canonical_json.canonical(v)


def test_unmodified_and_modified_runs_are_reproduced(run):
    assert status(run) == "REPRODUCED"
    assert run["modified_inputs"] == ["D0_mm"] and run["comparison"]["applies"] is True
    base = share.build_run(PKG, "FLEX-035")
    assert status(base) == "REPRODUCED" and base["modified_inputs"] == []
    assert base["run_id"] == next(r["run_id"] for r in RUNS if r["seeded_from_physical_test"] == "FLEX-035")


def test_every_test_builds_a_reproducible_file():
    for tid, row in ROWS.items():
        if tid not in {r["seeded_from_physical_test"] for r in RUNS}:
            continue
        r = share.build_run(PKG, tid)
        assert status(r) == "REPRODUCED", tid
        if tid == "FLEX-001":
            break  # one check is enough here; the browser test sweeps all of them


def test_labels_and_privacy(run):
    assert run["labels"]["evidence_class"] == "NUMERICAL_SIMULATION" and run["run_id"].startswith("SIM-")
    assert "not validated against FLEX" in run["labels"]["scope"]
    text = json.dumps(run)
    assert "@" not in text and "/home/" not in text and not __import__("re").search(r"\d{4}-\d{2}-\d{2}", text)
    assert set(run) == share.TOP_KEYS


def test_schema_accepts_exports_and_rejects_changes(run):
    jsonschema = pytest.importorskip("jsonschema")
    from referencing import Registry, Resource
    sch = {f: json.load(open(os.path.join(ROOT, "schemas", f), encoding="utf-8")) for f in os.listdir(os.path.join(ROOT, "schemas")) if f.endswith(".json")}
    reg = Registry().with_resources([(x["$id"], Resource.from_contents(x)) for x in sch.values()])
    v = jsonschema.Draft202012Validator(SCHEMA, registry=reg)
    assert list(v.iter_errors(run)) == []
    bad = copy.deepcopy(run)
    bad["extra"] = 1
    assert list(v.iter_errors(bad))
    bad = copy.deepcopy(run)
    bad["labels"]["evidence_class"] = "PHYSICAL_MEASUREMENT"
    assert list(v.iter_errors(bad))


def tamper(run, fn):
    t = copy.deepcopy(run)
    fn(t)
    return t


@pytest.mark.parametrize("name,fn,expected", [
    ("output", lambda t: t["outputs"].__setitem__("K_mm2_s", t["outputs"]["K_mm2_s"] * 1.01), "NOT_REPRODUCED"),
    ("run_id", lambda t: t.__setitem__("run_id", "SIM-000000000000"), "NOT_REPRODUCED"),
    ("hash", lambda t: t.__setitem__("content_sha256", "0" * 64), "NOT_REPRODUCED"),
    ("modlist", lambda t: t.__setitem__("modified_inputs", ["fuel"]), "NOT_REPRODUCED"),
    ("comparison", lambda t: t["comparison"].__setitem__("model_over_printed", 1.0), "NOT_REPRODUCED"),
    ("flags", lambda t: t["outputs"].__setitem__("flags", ["invented"]), "NOT_REPRODUCED"),
    ("model_version", lambda t: t["model"].__setitem__("version", "9.9.9"), "CANNOT_CHECK"),
    ("table_hash", lambda t: t["model"].__setitem__("property_table_sha256", "0" * 64), "CANNOT_CHECK"),
    ("range", lambda t: t["inputs"].__setitem__("T_inf_K", 5000), "INVALID"),
    ("neg_fraction", lambda t: t["inputs"]["X"].__setitem__("O2", -0.1), "INVALID"),
    ("bad_fuel", lambda t: t["inputs"].__setitem__("fuel", "gasoline"), "INVALID"),
    ("unknown_input", lambda t: t["inputs"].__setitem__("secret", 1), "INVALID"),
    ("flex_id", lambda t: t.__setitem__("run_id", "FLEX-035"), "INVALID"),
    ("evidence_class", lambda t: t["labels"].__setitem__("evidence_class", "PHYSICAL_MEASUREMENT"), "INVALID"),
    ("unknown_seed", lambda t: t.__setitem__("seeded_from_physical_test", "FLEX-999"), "INVALID"),
    ("unknown_key", lambda t: t.__setitem__("extra", 1), "INVALID"),
    ("record_type", lambda t: t.__setitem__("record_type", "Other"), "INVALID"),
])
def test_tampering(run, name, fn, expected):
    assert status(tamper(run, fn)) == expected


@pytest.mark.parametrize("obj", [None, [], "text", 3, {}])
def test_garbage_is_invalid(obj):
    assert status(obj) == "INVALID"


def test_recomputed_hash_after_editing_still_fails_other_checks(run):
    t = copy.deepcopy(run)
    t["outputs"]["K_mm2_s"] *= 2
    t["content_sha256"] = share.sha({k: v for k, v in t.items() if k != "content_sha256"})
    res = share.verify_run(t, PKG)
    assert res["status"] == "NOT_REPRODUCED"
    assert {c["id"]: c["pass"] for c in res["checks"]}["F9"] is True      # the hash alone proves nothing
    assert {c["id"]: c["pass"] for c in res["checks"]}["F7"] is False     # re-running the model does


def run_cli(*args):
    return subprocess.run([sys.executable, "-m", "openflex", *args], cwd=ROOT, capture_output=True, text=True)


def test_cli_round_trip(tmp_path):
    f = str(tmp_path / "r.json")
    p = run_cli("baseline", "FLEX-035", "--O2", "0.15", "--export", f)
    assert p.returncode == 0 and "MODIFIED inputs" in p.stdout and "SIMULATION" in p.stdout and "not validation" in p.stdout, p.stdout + p.stderr
    c = run_cli("check-run", f)
    assert c.returncode == 0 and "REPRODUCED" in c.stdout
    obj = json.load(open(f))
    obj["outputs"]["B"] *= 1.1
    json.dump(obj, open(f, "w"))
    c = run_cli("check-run", f)
    assert c.returncode != 0 and "NOT_REPRODUCED" in c.stdout


def test_cli_refuses_oversize_and_non_json(tmp_path):
    f = tmp_path / "big.json"
    f.write_text(" " * (share.MAX_BYTES + 1))
    assert run_cli("check-run", str(f)).returncode != 0
    g = tmp_path / "bad.json"
    g.write_text("not json")
    c = run_cli("check-run", str(g))
    assert c.returncode != 0 and "Traceback" not in c.stderr
    assert run_cli("check-run", str(tmp_path / "missing.json")).returncode != 0
