#!/usr/bin/env python3
"""Waktu bakar CFI-G sebagai RENTANG (P10/P50/P90), bukan satu angka.

Motivasi: Neuer, Machine Learning for Engineers, bab 6.4.4 (Mixture Density Network) —
model sebaiknya memprediksi distribusi, bukan titik. Di sini versi sederhananya:
gradient boosting dengan loss kuantil (tiga model: q = 0,1 / 0,5 / 0,9).

Waktu bakar CFI-G bimodal: nyala yang padam sendiri (pendek) vs yang dihentikan aliran
(panjang, ditentukan operator). Satu angka rata-rata menyesatkan; rentang lebih jujur.

Cek kalibrasi per-hari: berapa persen uji yang jatuh di dalam [P10, P90]? Idealnya 80 %.

  python scripts/ml_quantile.py   # -> analysis/ml/quantile_burn.json
"""
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ml_tabular  # noqa: E402

QS = (0.1, 0.5, 0.9)


def load():
    T = list(csv.DictReader(open(ROOT / "kb" / "gold" / "tests.csv", encoding="utf-8")))
    sets = ml_tabular.load()
    d = sets["cfig_ign"]
    ids = {i: k for k, i in enumerate(d["ids"])}
    bt = {}
    for r in T:
        if r["accession"] == "PSI-159" and r["ignited"] == "yes" and r["test_id"] in ids:
            v = ml_tabular.fnum(r["burn_time_s"])
            if v is not None and v > 0:
                bt[ids[r["test_id"]]] = v
    k = np.array(sorted(bt))
    return d["X"][k], np.array([bt[i] for i in k]), d["g"][k], d["names"]


def fit_q(X, ly):
    ms = []
    for q in QS:
        ms.append(HistGradientBoostingRegressor(loss="quantile", quantile=q, max_depth=3, learning_rate=0.05,
                                                max_iter=300, min_samples_leaf=10, random_state=7).fit(X, ly))
    return ms


def pred_q(ms, X):
    return np.sort(np.column_stack([m.predict(X) for m in ms]), axis=1)


def cqr_margin(X, ly, g, alpha=0.2):
    """Conformalized quantile regression: skor E = max(P10 - y, y - P90) pada lipatan
    per-hari bagian dalam; koreksi = kuantil (1-alpha) dari E (skala log)."""
    E = []
    for tr, te in GroupKFold(n_splits=4).split(X, ly, g):
        Q = pred_q(fit_q(X[tr], ly[tr]), X[te])
        E.append(np.maximum(Q[:, 0] - ly[te], ly[te] - Q[:, 2]))
    E = np.concatenate(E)
    n = len(E)
    return float(np.quantile(E, min(1.0, math.ceil((n + 1) * (1 - alpha)) / n)))


def main():
    X, y, g, names = load()
    ly = np.log(y)
    P = np.zeros((len(y), 3))
    Pc = np.zeros((len(y), 3))
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        Q = pred_q(fit_q(X[tr], ly[tr]), X[te])
        P[te] = np.exp(Q)
        q = cqr_margin(X[tr], ly[tr], g[tr])          # dihitung HANYA dari hari latih
        Pc[te] = np.exp(Q + np.array([-q, 0, q]))
    cover = float(np.mean((y >= P[:, 0]) & (y <= P[:, 2])))
    width = float(np.median(P[:, 2] - P[:, 0]))
    mae50 = float(np.mean(np.abs(y - P[:, 1])))
    cover_c = float(np.mean((y >= Pc[:, 0]) & (y <= Pc[:, 2])))
    width_c = float(np.median(Pc[:, 2] - Pc[:, 0]))
    # pembanding: kuantil marginal saja (tanpa model)
    mq = np.zeros((len(y), 3))
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        mq[te] = np.quantile(y[tr], QS)
    res = {"n": int(len(y)), "days": int(len(set(g))),
           "model": {"coverage_P10_P90": round(cover, 3), "median_width_s": round(width, 1), "mae_P50_s": round(mae50, 1)},
           "model_conformal": {"coverage_P10_P90": round(cover_c, 3), "median_width_s": round(width_c, 1),
                               "mae_P50_s": round(mae50, 1)},
           "marginal": {"coverage_P10_P90": round(float(np.mean((y >= mq[:, 0]) & (y <= mq[:, 2]))), 3),
                        "median_width_s": round(float(np.median(mq[:, 2] - mq[:, 0])), 1),
                        "mae_P50_s": round(float(np.mean(np.abs(y - mq[:, 1]))), 1)},
           "target_coverage": 0.8}
    out = ROOT / "analysis" / "ml" / "quantile_burn.json"
    out.write_text(json.dumps(res, indent=1), encoding="utf-8")
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
