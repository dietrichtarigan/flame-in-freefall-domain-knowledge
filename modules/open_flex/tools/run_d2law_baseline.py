#!/usr/bin/env python3
"""Evaluate the D²-law educational baseline at the printed conditions of every Table IX test.

Outputs (deterministic):
  data/simulations/d2law_baseline_runs.json   one SimulationRun per test (schemas/simulation_run.schema.json).
      Run ids are SIM-<12 hex> hashes of model version + inputs; a run is never identified by a FLEX id.
      It only cites the test whose printed conditions seeded it (seeded_from_physical_test).
  data/analysis/d2law_vs_table_ix.csv          printed K (Table IX) next to the model K, with the ratio.
      This is a COMPARISON, not validation: the model is a classical baseline with no adjustable parameters
      and no FLEX data were used to set it.

Usage: python3 -I tools/run_d2law_baseline.py [repo-root]
"""
import csv
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__" and len(sys.argv) > 1:
    ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, ROOT)
from openflex import d2law as m  # noqa: E402
from tools.canonical_json import canonical  # noqa: E402

T_INF = 298.15
SCOPE = ("Educational baseline evaluated at the printed conditions of the cited test. May be used to show what classical "
         "quasi-steady theory predicts and how far it is from the printed values. May NOT be used as a FLEX measurement, "
         "a prediction of extinction, or evidence that the model is valid for FLEX.")


def r6(v):
    if isinstance(v, float):
        return float(f"{v:.6g}")
    if isinstance(v, dict):
        return {k: r6(x) for k, x in v.items()}
    return v


def main():
    table = json.load(open(os.path.join(ROOT, "data/model/d2law_properties.json"), encoding="utf-8"))
    runs, rows = [], []
    for r in csv.DictReader(open(os.path.join(ROOT, "data/extracted/table_ix.csv"), encoding="utf-8")):
        num = lambda k: None if r[k] in ("", "None") else float(r[k])  # noqa: E731
        X = {"O2": num("X_O2"), "N2": num("X_N2"), "CO2": num("X_CO2"), "He": num("X_He")}
        inputs = {"fuel": r["fuel"], "X": X, "D0_mm": num("D0_mm"), "T_inf_K": T_INF,
                  "P_atm": round(num("P_mmHg") / 760.0, 6) if num("P_mmHg") else None,
                  "rho_l_at": "boil", "Q_variant": "nominal", "T_prop_rule": "(T_s+T_f)/2, iterated"}
        modified = []
        if any(v is None for v in X.values()):
            modified.append("missing mole fractions taken as 0")
        approx = [k for k in ("X_O2", "X_N2", "X_CO2", "X_He", "D0_mm", "P_mmHg") if r.get(k + "_approx") == "True"]
        if approx:
            modified.append("printed as approximate: " + ", ".join(approx))
        out = m.solve(dict(inputs, X={k: (v or 0.0) for k, v in X.items()}), table)
        outputs = r6({k: out[k] for k in ("B", "K_mm2_s", "t_burn_s", "flame_standoff_ratio", "T_flame_K", "T_prop_K",
                                            "cp_J_kgK", "k_W_mK", "Y_O2_inf")})
        outputs["flags"] = out["flags"]
        rid = "SIM-" + hashlib.sha256(canonical({"model": m.MODEL_VERSION, "inputs": inputs, "table": hashlib.sha256(
            open(os.path.join(ROOT, "data/model/d2law_properties.json"), "rb").read()).hexdigest()}).encode()).hexdigest()[:12]
        runs.append({"record_type": "SimulationRun", "run_id": rid,
                     "model": {"name": m.MODEL_NAME, "version": m.MODEL_VERSION, "status": "EDUCATIONAL_BASELINE"},
                     "inputs": inputs, "seeded_from_physical_test": r["flex_test"], "inputs_modified_from_test": modified,
                     "outputs": outputs, "evidence_class": "NUMERICAL_SIMULATION", "claims_scope": SCOPE})
        Kp = num("K_mm2_s")
        Km = out["K_mm2_s"]
        rows.append({"flex_test": r["flex_test"], "fuel": r["fuel"], "K_printed_mm2_s": r["K_mm2_s_raw"],
                     "K_model_mm2_s": f"{Km:.4g}" if Km else "", "ratio_model_to_printed": f"{Km / Kp:.3g}" if (Km and Kp) else "",
                     "simulation_run_id": rid})
    os.makedirs(os.path.join(ROOT, "data/simulations"), exist_ok=True)
    with open(os.path.join(ROOT, "data/simulations/d2law_baseline_runs.json"), "w", encoding="utf-8") as fh:
        json.dump({"record_type": "SimulationRunSet", "model": m.MODEL_NAME, "model_version": m.MODEL_VERSION,
                   "note": "Simulation runs are not physical tests. seeded_from_physical_test names the test whose printed conditions were used.",
                   "runs": runs}, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    with open(os.path.join(ROOT, "data/analysis/d2law_vs_table_ix.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(len(runs), "runs")


if __name__ == "__main__":
    main()
