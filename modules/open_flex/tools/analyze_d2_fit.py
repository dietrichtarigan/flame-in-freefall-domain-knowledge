#!/usr/bin/env python3
"""AnalysisRun: linear D^2(t) fits to DIGITIZED droplet data, compared with the printed Table IX values.

Purpose: a DIGITIZATION CHECK.  If the digitized points reproduce the slope NASA printed (K), the
digitization is at least consistent with the source.  This is not validation of any model and not a new
measurement of K.

Pre-declared choices (fixed before looking at the comparison; recorded in the output):
  * Fit windows are fractions of the Table IX burn time t_b (a printed value):
        W1 [0.1 t_b, 1.0 t_b]   W2 [0.1 t_b, 0.9 t_b]   W3 [0.2 t_b, 0.8 t_b]   W4 [0.1 t_b, 0.8 t_b]
    The TP says only "from shortly after ignition to extinction" (CLM-019); its exact window is not reported,
    so several windows are shown.  Their spread is a window sensitivity, NOT an uncertainty interval.
  * Two estimators: ordinary least squares and Theil-Sen (median of pairwise slopes; robust to outliers).
  * No standard errors or confidence intervals are reported: the digitized points are not independent
    observations (they sample an overlapping marker trail; residuals are autocorrelated), so textbook
    regression intervals would be wrong.  The lag-1 autocorrelation of OLS residuals is reported instead.
  * Point checks: digitized D^2 near t = 0 vs (Table IX D0)^2, and near t = t_b vs (Table IX extinction
    diameter)^2, using the median of points within +/-0.2 s, if any.

Output: data/analysis/<run_id>.json (schemas/analysis_run.schema.json); run_id = "ANA-" + first 12 hex of
SHA-256 over the canonical JSON of inputs + parameters + code version, so the same inputs give the same id.

Usage: python3 -I tools/analyze_d2_fit.py <repo-root> <test_id>
"""
import csv
import hashlib
import json
import os
import platform
import sys

import numpy as np
import scipy
from scipy import stats

CODE_VERSION = "1.1.0"   # 1.1.0: windows with < 5 points are reported, not fitted
WINDOWS = {"W1": (0.1, 1.0), "W2": (0.1, 0.9), "W3": (0.2, 0.8), "W4": (0.1, 0.8)}
HALF = 0.2


def half_unit(raw):
    raw = raw.strip().lstrip("~")
    return 0.5 * 10 ** (-len(raw.split(".")[1])) if "." in raw else 0.5


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def main(root, test_id):
    spec = json.load(open(os.path.join(root, "data/datasets.spec.json"), encoding="utf-8"))["datasets"]
    ds = [d for d in spec if d["data_class"] == "DIGITIZED" and d.get("test_id") == test_id and d.get("series") == "droplet_d2"]
    if len(ds) != 1:
        raise SystemExit(f"expected one DIGITIZED droplet_d2 dataset for {test_id} in data/datasets.spec.json, found {len(ds)}")
    d = dict(ds[0])
    path = os.path.join(root, d["path"])
    d["sha256"] = sha(path)
    ix = {r["flex_test"]: r for r in csv.DictReader(open(os.path.join(root, "data/extracted/table_ix.csv"), encoding="utf-8"))}[test_id]
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    T = np.array([float(r["t_s"]) for r in rows])
    V = np.array([float(r["droplet_d2_mm2"]) for r in rows])
    tb = float(ix["t_burn_s"])
    K_ix = float(ix["K_mm2_s"])
    params = {"windows_fraction_of_t_burn": WINDOWS, "t_burn_s_from_table_ix": ix["t_burn_s_raw"],
              "estimators": ["OLS", "Theil-Sen"], "point_check_half_width_s": HALF}
    inputs = [{"dataset_id": d["dataset_id"], "sha256": d["sha256"]}]
    run_id = "ANA-" + hashlib.sha256(canon({"inputs": inputs, "params": params, "code": CODE_VERSION, "test": test_id}).encode()).hexdigest()[:12]

    fits = []
    for name, (a, b) in WINDOWS.items():
        m = (T >= a * tb) & (T <= b * tb)
        t, v = T[m], V[m]
        if m.sum() < 5:
            fits.append({"window": name, "t_start_s": round(a * tb, 3), "t_end_s": round(b * tb, 3), "n_points": int(m.sum()),
                         "K_ols_mm2_s": None, "K_theil_sen_mm2_s": None, "intercept_ols_mm2": None, "residual_rms_mm2": None,
                         "residual_lag1_autocorrelation": None, "note": "fewer than 5 digitized points in window; not fitted"})
            continue
        ols = stats.linregress(t, v)
        res = v - (ols.intercept + ols.slope * t)
        r1 = float(np.corrcoef(res[:-1], res[1:])[0, 1]) if len(res) > 3 else None
        ts = stats.theilslopes(v, t)
        fits.append({"window": name, "t_start_s": round(a * tb, 3), "t_end_s": round(b * tb, 3), "n_points": int(m.sum()),
                     "K_ols_mm2_s": round(-float(ols.slope), 4), "K_theil_sen_mm2_s": round(-float(ts[0]), 4),
                     "intercept_ols_mm2": round(float(ols.intercept), 4),
                     "residual_rms_mm2": round(float(np.sqrt(np.mean(res ** 2))), 4),
                     "residual_lag1_autocorrelation": None if r1 is None else round(r1, 3)})
    ks = [f[k] for f in fits for k in ("K_ols_mm2_s", "K_theil_sen_mm2_s") if f[k] is not None]
    if not ks:
        raise SystemExit(f"{test_id}: no window has enough digitized points")

    def near(t0):
        m = np.abs(T - t0) <= HALF
        return (round(float(np.median(V[m])), 4), int(m.sum())) if m.any() else (None, 0)

    checks = []
    if ix["D0_mm_raw"] not in ("–", ""):
        val, n = near(0.0)
        checks.append({"quantity": "D^2 at t = 0 (igniter ON)", "table_ix_value": f"D0 = {ix['D0_mm_raw']} mm -> D0^2 = {float(ix['D0_mm']) ** 2:.3f} mm^2",
                       "digitized_median_mm2": val, "n_points_within_0.2_s": n,
                       "note": "no digitized point within 0.2 s of t = 0 (markers above the plotted axis range are clipped)" if n == 0 else ""})
    if ix["D_ext_visible_mm_raw"] not in ("–", "", "0"):
        val, n = near(tb)
        checks.append({"quantity": "D^2 at t = t_burn (visible-flame extinction)",
                       "table_ix_value": f"D_ext = {ix['D_ext_visible_mm_raw']} mm -> {float(ix['D_ext_visible_mm']) ** 2:.3f} mm^2 at t_b = {ix['t_burn_s_raw']} s",
                       "digitized_median_mm2": val, "n_points_within_0.2_s": n, "note": ""})

    run = {
        "record_type": "AnalysisRun", "run_id": run_id, "about_physical_test": test_id,
        "inputs": inputs,
        "method": "Linear fits of digitized D^2 vs t over pre-declared windows (OLS and Theil-Sen); point checks against Table IX.",
        "parameters": params,
        "software": {"tool": "tools/analyze_d2_fit.py", "code_version": CODE_VERSION, "python": platform.python_version(),
                     "numpy": np.__version__, "scipy": scipy.__version__},
        "outputs": {
            "fits": fits,
            "K_range_over_windows_and_estimators_mm2_s": [min(ks), max(ks)],
            "K_range_semantics": "Window/estimator sensitivity only. Not a confidence or prediction interval; no coverage is claimed.",
            "table_ix_K_mm2_s": {"raw": ix["K_mm2_s_raw"], "value": K_ix, "locator": f"S01 Table IX, PDF p. {ix['pdf_page']}"},
            "table_ix_K_rounding_interval_mm2_s": [round(K_ix - half_unit(ix["K_mm2_s_raw"]), 6), round(K_ix + half_unit(ix["K_mm2_s_raw"]), 6)],
            "table_ix_K_within_range": bool(min(ks) <= K_ix + half_unit(ix["K_mm2_s_raw"]) and K_ix - half_unit(ix["K_mm2_s_raw"]) <= max(ks)),
            "within_range_rule": "the printed value's rounding interval (± half a unit of its last printed digit) overlaps the range of fitted slopes (rule since 1.1.0; 1.0.0 compared the bare printed value)",
            "point_checks": checks,
            "interpretation_limits": [
                "Agreement shows the digitized points are consistent with the printed K; it does not validate any model.",
                "The fitted values are DERIVED from DIGITIZED data and must not replace the printed Table IX K.",
                "Standard errors/intervals deliberately not reported (non-independent, autocorrelated points)."]},
        "verification_kind": "comparison with published value (not validation)"}
    out = os.path.join(root, "data", "analysis", f"{test_id}_d2_fit.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(run, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")
    print(run_id, test_id, "K range", [min(ks), max(ks)], "Table IX", K_ix, "within:", run["outputs"]["table_ix_K_within_range"])
    for c in checks:
        print("  check:", c["quantity"], c["table_ix_value"], "digitized", c["digitized_median_mm2"], "n", c["n_points_within_0.2_s"])


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
