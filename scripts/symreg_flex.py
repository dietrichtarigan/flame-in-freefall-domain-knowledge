#!/usr/bin/env python3
"""Regresi simbolik jarang (SINDy-style STLS) untuk laju bakar droplet FLEX.

Sumber metode: Scientific Machine Learning (Foundations, Algorithms, Applications), bab 10.2:
Sequential Thresholded Least Squares di atas pustaka suku kandidat.

Pustaka dibangun dari teori: hukum d^2,  K = (8 lambda / rho_l c_p) ln(1 + B),
dengan bilangan transfer B yang naik kira-kira linear terhadap fraksi O2.
  - ln(1 + k*O2) untuk beberapa k (bentuk teori), O2, O2^2, sqrt(O2)
  - He  (menaikkan konduktivitas termal lambda -> K naik), CO2 (pengencer, radiasi)
  - ln(p/p0), heptana (bahan bakar), dan interaksi bahan bakar x O2, He x O2

Pemilihan: jalur lambda -> tiap model dinilai RMSE validasi PER-HARI (GroupKFold).
Model akhir = model paling sederhana yang RMSE-nya <= terbaik + 1 SE (aturan 1-SE).

  python scripts/symreg_flex.py   # -> analysis/ml/symreg_flex.json, symreg_flex.md
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import GroupKFold

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ml_tabular  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "ml"


def library(X):
    hep, o2, co2, he, lnp = X[:, 0], X[:, 1], X[:, 2], X[:, 3], X[:, 4]
    T = {"1": np.ones_like(o2), "heptana": hep, "O2": o2, "O2^2": o2 ** 2, "sqrt(O2)": np.sqrt(o2)}
    for k in (2, 5, 10, 20):
        T[f"ln(1+{k}·O2)"] = np.log1p(k * o2)
    T.update({"He": he, "CO2": co2, "ln(p/p0)": lnp, "heptana·O2": hep * o2, "He·O2": he * o2,
              "CO2·O2": co2 * o2, "ln(p/p0)·O2": lnp * o2, "heptana·He": hep * he})
    return list(T.keys()), np.column_stack(list(T.values()))


def stls(Th, y, lam, iters=20):
    mu, sd = Th.mean(0), Th.std(0)
    sd[sd == 0] = 1
    Z = (Th - mu) / sd
    Z[:, 0] = 1.0                                   # intersep tak distandarkan
    xi = np.linalg.lstsq(Z, y, rcond=None)[0]
    for _ in range(iters):
        small = np.abs(xi) < lam
        small[0] = False                            # intersep selalu ada
        xi[small] = 0
        big = ~small
        xi[big] = np.linalg.lstsq(Z[:, big], y, rcond=None)[0]
    # kembalikan ke satuan asli
    beta = np.zeros_like(xi)
    beta[1:] = xi[1:] / sd[1:]
    beta[0] = xi[0] - np.sum(xi[1:] * mu[1:] / sd[1:])
    return beta


def cv_rmse(Th, y, g, lam):
    errs = []
    for tr, te in GroupKFold(n_splits=5).split(Th, y, g):
        b = stls(Th[tr], y[tr], lam)
        errs.append(np.sqrt(np.mean((Th[te] @ b - y[te]) ** 2)))
    return float(np.mean(errs)), float(np.std(errs) / math.sqrt(len(errs)))


O2_SHAPES = ["O2", "O2^2", "sqrt(O2)", "ln(1+2·O2)", "ln(1+5·O2)", "ln(1+10·O2)", "ln(1+20·O2)"]


def cv_subset(Th, y, g, cols):
    errs = []
    for tr, te in GroupKFold(n_splits=5).split(Th, y, g):
        A = Th[tr][:, cols]
        b = np.linalg.lstsq(A, y[tr], rcond=None)[0]
        errs.append(np.sqrt(np.mean((Th[te][:, cols] @ b - y[te]) ** 2)))
    return float(np.mean(errs)), float(np.std(errs) / math.sqrt(len(errs)))


def main():
    from itertools import combinations
    d = ml_tabular.load()["flex_K"]
    X, y, g = d["X"], d["y"], d["g"]
    names, Th = library(X)
    # 1) STLS pada pustaka penuh: dicatat sebagai percobaan yang gagal (suku O2 kolinear)
    st_r, _ = cv_rmse(Th, y, g, 0.02)
    st_b = stls(Th, y, 0.02)
    # 2) pencarian menyeluruh: <= 5 suku, paling banyak SATU bentuk O2
    o2i = [names.index(n) for n in O2_SHAPES]
    other = [i for i in range(1, len(names)) if i not in o2i]
    path = []
    for k in range(0, 6):
        for shape in [None] + o2i:
            rest_k = k - (shape is not None)
            if rest_k < 0:
                continue
            for comb in combinations(other, rest_k):
                cols = [0] + ([shape] if shape is not None else []) + list(comb)
                r, se = cv_subset(Th, y, g, cols)
                path.append({"cols": cols, "terms": len(cols) - 1, "cv_rmse": r, "se": se})
    best = min(path, key=lambda p: p["cv_rmse"])
    ok = [p for p in path if p["cv_rmse"] <= best["cv_rmse"] + best["se"]]
    pick = min(ok, key=lambda p: (p["terms"], p["cv_rmse"]))
    b_pick = np.linalg.lstsq(Th[:, pick["cols"]], y, rcond=None)[0]
    base = float(np.mean([np.sqrt(np.mean((y[te] - y[tr].mean()) ** 2))
                          for tr, te in GroupKFold(5).split(X, y, g)]))
    XL = np.column_stack([np.ones(len(y)), X])
    lin = float(np.mean([np.sqrt(np.mean((XL[te] @ np.linalg.lstsq(XL[tr], y[tr], rcond=None)[0] - y[te]) ** 2))
                         for tr, te in GroupKFold(5).split(X, y, g)]))
    terms = [(names[c], float(v)) for c, v in zip(pick["cols"], b_pick)]
    formula = "K ≈ " + " ".join(f"{'+' if c >= 0 else '−'} {abs(c):.3g}" + ("" if n == "1" else f"·{n}")
                                for n, c in terms).lstrip("+ ")
    fit = Th[:, pick["cols"]] @ b_pick
    r2 = 1 - np.sum((y - fit) ** 2) / np.sum((y - y.mean()) ** 2)
    pareto = {}
    for p in path:
        if p["terms"] not in pareto or p["cv_rmse"] < pareto[p["terms"]]["cv_rmse"]:
            pareto[p["terms"]] = p
    # bentuk O2 mana yang paling cocok (model 1 suku O2 + intersep)
    shape_rank = sorted(((names[s], cv_subset(Th, y, g, [0, s])[0]) for s in o2i), key=lambda t: t[1])
    res = {"n": int(len(y)), "days": int(len(set(g))), "library": names, "formula": formula,
           "terms": terms, "r2_fit": round(float(r2), 3), "cv_rmse_per_hari": round(pick["cv_rmse"], 4),
           "best_cv_rmse": round(best["cv_rmse"], 4), "baseline_mean_rmse": round(base, 4),
           "linear_raw_rmse": round(lin, 4), "stls_full_library_rmse": round(st_r, 4),
           "stls_max_abs_coef": float(np.abs(st_b).max()), "o2_shape_rank": shape_rank,
           "pareto": [{"terms": k, "cv_rmse": round(v["cv_rmse"], 4),
                       "formula_terms": [names[c] for c in v["cols"][1:]]} for k, v in sorted(pareto.items())]}
    (OUT / "symreg_flex.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    md = ["# Rumus laju bakar droplet FLEX dari data ISS (regresi simbolik)", "",
          f"n = {res['n']} uji, {res['days']} hari. Semua angka galat = RMSE validasi per hari (GroupKFold 5).", "",
          f"**{formula}**", "",
          "K dalam mm²/s; O2, He, CO2 fraksi mol; p0 = 101,325 kPa. "
          f"R² pada data latih = {r2:.3f}. Dipilih dengan aturan 1-SE: model tersederhana yang galatnya "
          "tidak lebih buruk dari model terbaik + 1 galat baku.", "",
          "| Model | RMSE per-hari |", "|---|---|",
          f"| rata-rata saja | {base:.4f} |", f"| linear, 5 fitur mentah | {lin:.4f} |",
          f"| STLS pada pustaka penuh (GAGAL, lihat bawah) | {st_r:.4f} |",
          f"| terbaik dari pencarian menyeluruh | {best['cv_rmse']:.4f} |",
          f"| **rumus terpilih ({pick['terms']} suku)** | **{pick['cv_rmse']:.4f}** |", "",
          "Bentuk ketergantungan O2 (model intersep + satu suku O2), dari yang paling cocok:", "",
          "| bentuk | RMSE |", "|---|---|"] + [f"| {n} | {r:.4f} |" for n, r in shape_rank] + [
          "", "Front Pareto:", "", "| suku | RMSE | suku |", "|---|---|---|"]
    md += [f"| {p['terms']} | {p['cv_rmse']:.4f} | {', '.join(p['formula_terms'])} |" for p in res["pareto"]]
    md += ["", "**Percobaan yang gagal, dicatat supaya tidak diulang:** STLS (SINDy) pada pustaka penuh "
               f"mempertahankan semua bentuk O2 sekaligus dengan koefisien sampai {res['stls_max_abs_coef']:.1e} "
               "yang saling meniadakan, karena suku-suku itu hampir kolinear. Rumus seperti itu tidak bermakna "
               "fisika. Solusinya: batasi satu bentuk O2 per model dan cari menyeluruh (pustaka kecil, murah).",
           "", "Rumus ini empiris dalam rentang kondisi FLEX yang diuji, bukan hukum universal. Bila bentuk "
               "ln(1+k·O2) terpilih, ia dapat dibaca sebagai suku ln(1+B) dari hukum d²."]
    text = chr(10).join(md) + chr(10)
    (OUT / "symreg_flex.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
