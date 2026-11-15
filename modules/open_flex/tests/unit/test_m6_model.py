"""M6 unit tests: D²-law educational baseline, its code verification, simulation-run records, Python scaffold."""
import copy
import csv
import importlib
import json
import os
import statistics
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from openflex import d2law as m  # noqa: E402
from openflex.data import DataPackage  # noqa: E402

TABLE = json.load(open(os.path.join(ROOT, "data/model/d2law_properties.json"), encoding="utf-8"))
RUNS = json.load(open(os.path.join(ROOT, "data/simulations/d2law_baseline_runs.json"), encoding="utf-8"))["runs"]


def verify_module():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import verify_d2law
    return importlib.reload(verify_d2law)


def test_code_verification_passes_and_record_is_current():
    rec = verify_module().main(out_path=False)
    assert rec["status"] == "PASS" and rec["n_passed"] == rec["n_checks"] == 24
    stored = json.load(open(os.path.join(ROOT, "data/verification/d2law_code_verification.json"), encoding="utf-8"))
    assert stored == rec                                              # deterministic and up to date


@pytest.mark.parametrize("bug", ["conductivity", "profile", "k_factor"])
def test_code_verification_detects_injected_bugs(monkeypatch, bug):
    """The checks must be able to fail: inject a defect and confirm the record says FAIL."""
    V = verify_module()
    if bug == "conductivity":                                         # 1 % error in the mixture conductivity
        orig = m.mixture_cp_k
        monkeypatch.setattr(m, "mixture_cp_k", lambda t, x, T: (orig(t, x, T)[0], orig(t, x, T)[1] * 1.01))
    elif bug == "profile":                                            # wrong sign in the outer temperature profile
        orig_p = m.profiles

        def bad(*a, **k):
            lam, rf, YF, YO, T = orig_p(*a, **k)
            return lam, rf, YF, YO, (lambda r: T(r) if r <= rf else T(r) * 1.001)
        monkeypatch.setattr(m, "profiles", bad)
    else:                                                             # 7 instead of 8 in K
        orig_s = m.solve

        def bad_s(i, t, **k):
            o = orig_s(i, t, **k)
            if o.get("K_mm2_s"):
                o["K_mm2_s"] *= 7 / 8
            return o
        monkeypatch.setattr(m, "solve", bad_s)
    rec = V.main(out_path=False)
    assert rec["status"] == "FAIL", bug


def test_simulation_runs_reproduce_and_stay_separate():
    ids = set()
    for r in RUNS:
        assert r["run_id"].startswith("SIM-") and not r["run_id"].startswith("FLEX")
        assert r["run_id"] not in ids
        ids.add(r["run_id"])
        assert r["evidence_class"] == "NUMERICAL_SIMULATION" and r["model"]["status"] == "EDUCATIONAL_BASELINE"
        I = copy.deepcopy(r["inputs"])
        I["X"] = {k: (v or 0.0) for k, v in I["X"].items()}
        o = m.solve(I, TABLE)
        for k in ("K_mm2_s", "B", "T_flame_K", "flame_standoff_ratio", "t_burn_s"):
            a, b = o[k], r["outputs"][k]
            assert (a is None and b is None) or abs(a - b) <= 1e-5 * abs(b), (r["seeded_from_physical_test"], k)
    assert len(RUNS) == 276


def test_comparison_claim_numbers():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data/analysis/d2law_vs_table_ix.csv"), encoding="utf-8")))
    rat = {f: [float(x["ratio_model_to_printed"]) for x in rows if x["fuel"] == f and x["ratio_model_to_printed"]] for f in ("methanol", "heptane")}
    assert (len(rat["methanol"]), len(rat["heptane"])) == (151, 109)
    assert round(statistics.median(rat["methanol"]), 1) == 2.1 and round(statistics.median(rat["heptane"]), 1) == 4.3
    assert min(min(v) for v in rat.values()) > 1                      # CLM-057: model above printed K for every test


def test_model_limits_and_scope_flags():
    no_o2 = m.solve({"fuel": "heptane", "X": {"O2": 0.0, "N2": 1.0}, "D0_mm": 3, "T_inf_K": 298.15}, TABLE)
    assert no_o2["K_mm2_s"] is None and any("outside scope" in f for f in no_o2["flags"])
    with pytest.raises(ValueError):
        m.solve({"fuel": "heptane", "X": {"O2": 0.21, "N2": 0.79}, "D0_mm": 3, "T_inf_K": 298.15, "T_prop_K": 2500}, TABLE)


def test_property_table_regenerates_identically(tmp_path):
    cp = pytest.importorskip("CoolProp")
    if cp.__version__ != "8.0.0":
        pytest.skip("CoolProp 8.0.0 needed")
    os.makedirs(tmp_path / "data" / "model")
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools/build_model_properties.py"), str(tmp_path)], check=True, capture_output=True)
    assert open(tmp_path / "data/model/d2law_properties.json", "rb").read() == open(os.path.join(ROOT, "data/model/d2law_properties.json"), "rb").read()


def test_property_table_provenance():
    assert TABLE["coolprop_version"] == "8.0.0" and TABLE["evidence_class"] == "DERIVED"
    for f in TABLE["fuels"].values():
        assert f["dcH_liquid"]["sources"] and f["Q_lhv_vapour_range_J_kg"][0] <= f["Q_lhv_vapour_J_kg"] <= f["Q_lhv_vapour_range_J_kg"][1]
    assert any("298.15 K" in a and "ambient temperature" in a for a in TABLE["assumptions"])


def test_data_package_detects_tampering(monkeypatch):
    pkg = DataPackage()
    assert pkg.code_verification()["status"] == "PASS"
    assert "droplet_d2" in pkg.digitized_series("FLEX-035")
    pkg.datasets["DS-TP-TABLE-IX"] = dict(pkg.datasets["DS-TP-TABLE-IX"], sha256="0" * 64)
    with pytest.raises(ValueError):
        pkg.verify()


def test_cli():
    env = dict(os.environ, PYTHONPATH=ROOT)
    out = subprocess.run([sys.executable, "-m", "openflex", "info"], capture_output=True, text=True, cwd=ROOT, env=env, check=True).stdout
    assert "PASS (24/24)" in out and "not validated" in out
    out = subprocess.run([sys.executable, "-m", "openflex", "baseline", "FLEX-035", "--O2", "0.15"], capture_output=True, text=True, cwd=ROOT, env=env, check=True).stdout
    assert out.startswith("SIMULATION") and "MODIFIED inputs — not the conditions of FLEX-035" in out and "not validation" in out


def test_rocrate_is_current_and_valid():
    """ro-crate-metadata.json lists every packaged file with its current SHA-256 and passes rocrate-validator
    (profile ro-crate-1.2, REQUIRED) through tools/validate_rocrate.py."""
    pytest.importorskip("rocrate_validator")
    import hashlib
    crate = json.load(open(os.path.join(ROOT, "ro-crate-metadata.json"), encoding="utf-8"))
    files = [e for e in crate["@graph"] if "File" in (e["@type"] if isinstance(e["@type"], list) else [e["@type"]])]
    assert len(files) > 150
    for e in files:
        p = os.path.join(ROOT, e["@id"])
        assert os.path.exists(p), e["@id"]
        assert hashlib.sha256(open(p, "rb").read()).hexdigest() == e["sha256"], f"stale crate entry {e['@id']} (re-run tools/build_rocrate.py)"
    root = next(e for e in crate["@graph"] if e["@id"] == "./")
    assert root["license"] == {"@id": "#licence-not-chosen"}                 # no licence is invented
    assert not any(e["@id"].startswith("sources/") for e in files)            # the NASA PDF is not packaged
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/validate_rocrate.py"), ROOT, "--severity", "required",
                        "--json", os.path.join(ROOT, ".pytest_cache", "rocrate_report.json")], capture_output=True, text=True)
    rep = json.load(open(os.path.join(ROOT, ".pytest_cache", "rocrate_report.json"), encoding="utf-8"))
    assert r.returncode == 0 and rep["passed"] is True and rep["statistics"]["total_failed_checks"] == 0, rep["issues"][:5]
