"""M4 unit tests: uncertainty-component registry rules, coverage reference implementation."""
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import coverage as cov  # noqa: E402

U = json.load(open(os.path.join(ROOT, "data/registry/uncertainty_components.json"), encoding="utf-8"))["components"]


def test_nasa_reported_values_keep_their_semantics():
    by = {u["id"]: u for u in U}
    for uid, val in (("UC-01", 50), ("UC-03", 200), ("UC-04", 250)):
        u = by[uid]
        assert u["value"] == val and u["unit"] == "µm" and u["status"] == "reported"
        assert u["coverage_factor"] == "not stated" and u["distribution"] == "not specified"
        assert u["propagated"] is False and u["claims"]
    assert all(not u["propagated"] for u in U)


@pytest.mark.parametrize("field,value", [("interval_type", "1-sigma standard deviation"), ("interval_type", "95% confidence"),
                                         ("coverage_factor", "2"), ("propagated", True), ("claims", [])])
def test_validator_rejects_bad_uncertainty_semantics(tmp_path, field, value):
    for sub in ("tools", "schemas", "data"):
        shutil.copytree(os.path.join(ROOT, sub), tmp_path / sub)
    p = tmp_path / "data/registry/uncertainty_components.json"
    j = json.load(open(p, encoding="utf-8"))
    j["components"][0][field] = value                                    # UC-01: reported, NASA ±50 µm
    json.dump(j, open(p, "w", encoding="utf-8"))
    r = subprocess.run([sys.executable, "-I", "tools/validate_data.py", str(tmp_path)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout


def test_coverage_reference_cases():
    rows = cov.load_rows(ROOT)
    assert all(r["P_atm"] > 0 for r in rows) and "FLEX-114" not in {r["test_id"] for r in rows}   # P printed 0 excluded
    c = cov.coverage(rows, "heptane", "N2", {"P_atm": 1.011, "X_O2": 0.21, "D0_mm": 3.85}, "FLEX-035")
    assert c["label"] == "INSIDE_NEAR_TEST" and c["nearest"][0]["distance"] <= 0.25
    c = cov.coverage(rows, "heptane", "N2", {"P_atm": 3.0, "X_O2": 0.21, "D0_mm": 3.85})
    assert c["label"] == "OUTSIDE_RANGE" and c["outside"] == ["P_atm"]
    c = cov.coverage(rows, "methanol", "N2", {"P_atm": 1.0, "X_O2": 0.40, "D0_mm": 3.0})
    assert "X_O2" in c["outside"]                                        # no Table IX test above 0.34 O2
    assert max(r["X_O2"] for r in rows) == 0.34
