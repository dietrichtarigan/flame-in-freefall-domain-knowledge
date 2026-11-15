#!/usr/bin/env python3
"""Condition coverage of Table IX ("domain status") — reference implementation.

Answers: how close is a set of conditions (fuel, diluent, P, X_O2, D0) to conditions that were actually tested?
It says nothing about whether any model is valid there; no model in this project is validated.

Definitions (also implemented in app/src/js/45_transparency.js as OF.coverage; tests check they agree):
  * group = Table IX rows with the same fuel and diluent class.  Diluent class: "He" if X_He > 0, else "CO2" if
    X_CO2 > 0, else "N2".  (Printed values; cabin-air CO2 of 0.005 is printed as 0 in Table IX.)
  * variables: P_atm = P_mmHg / 760, X_O2, D0_mm (all as printed in Table IX).
  * excluded rows: any of the three values missing ("–") or P printed as 0 (FLEX-114, DSC-010).
  * per-variable status: inside if group min <= value <= group max.
  * distance to a test: sqrt(sum_v ((q_v - x_v) / range_v)^2), range_v = group max - group min (1 if zero).
  * labels (declared conventions, not statistics):
        NO_TESTS           no rows in the group
        OUTSIDE_RANGE      at least one variable outside the group's min-max
        INSIDE_NEAR_TEST   inside all ranges and nearest normalized distance <= 0.25
        INSIDE_SPARSE      inside all ranges but nearest normalized distance > 0.25
Usage: python3 -I tools/coverage.py <fuel> <N2|CO2|He> <P_atm> <X_O2> <D0_mm> [exclude_test_id]
"""
import csv
import json
import math
import os
import sys

VARS = ("P_atm", "X_O2", "D0_mm")
NEAR = 0.25


def diluent(r):
    if (r["X_He"] or 0) > 0:
        return "He"
    if (r["X_CO2"] or 0) > 0:
        return "CO2"
    return "N2"


def load_rows(root):
    out = []
    for r in csv.DictReader(open(os.path.join(root, "data/extracted/table_ix.csv"), encoding="utf-8")):
        v = {k: (None if r[k] in ("", "None") else float(r[k])) for k in ("P_mmHg", "X_O2", "X_CO2", "X_He", "D0_mm")}
        if v["P_mmHg"] is None or v["P_mmHg"] == 0 or v["X_O2"] is None or v["D0_mm"] is None:
            continue
        out.append({"test_id": r["flex_test"], "fuel": r["fuel"], "diluent": diluent(v),
                    "P_atm": v["P_mmHg"] / 760.0, "X_O2": v["X_O2"], "D0_mm": v["D0_mm"]})
    return out


def coverage(rows, fuel, dil, q, exclude=None, k=5):
    g = [r for r in rows if r["fuel"] == fuel and r["diluent"] == dil and r["test_id"] != exclude]
    if not g:
        return {"label": "NO_TESTS", "n_group": 0, "ranges": {}, "outside": [], "nearest": []}
    rng = {v: [min(r[v] for r in g), max(r[v] for r in g)] for v in VARS}
    outside = [v for v in VARS if not (rng[v][0] <= q[v] <= rng[v][1])]
    span = {v: (rng[v][1] - rng[v][0]) or 1.0 for v in VARS}
    d = sorted(((math.sqrt(sum(((q[v] - r[v]) / span[v]) ** 2 for v in VARS)), r["test_id"]) for r in g))
    near = [{"test_id": t, "distance": round(x, 4)} for x, t in d[:k]]
    if outside:
        label = "OUTSIDE_RANGE"
    else:
        label = "INSIDE_NEAR_TEST" if d[0][0] <= NEAR else "INSIDE_SPARSE"
    return {"label": label, "n_group": len(g), "ranges": {v: [round(a, 4), round(b, 4)] for v, (a, b) in rng.items()},
            "outside": outside, "nearest": near}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) not in (5, 6):
        raise SystemExit(__doc__)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    q = {"P_atm": float(a[2]), "X_O2": float(a[3]), "D0_mm": float(a[4])}
    print(json.dumps(coverage(load_rows(root), a[0], a[1], q, a[5] if len(a) == 6 else None), indent=1))
