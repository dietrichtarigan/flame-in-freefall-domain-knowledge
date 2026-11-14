#!/usr/bin/env python3
"""Mesin fisika: kalibrasi model dari kb/gold/tests.csv, validasi silang, lalu bangun simulator.

Alur:  tests.csv  ->  model_params.json + model_report.md + sim_data.json  ->  app/freefall_lab.html

Model (semuanya sederhana dan bisa dijelaskan di depan juri):
  1. FLEX   K   : konstanta laju bakar hukum d^2 (regresi linear)
  2. FLEX   P   : peluang api padam sebelum droplet habis (regresi logistik)
  3. CFI-G  P   : peluang menyala, dan peluang padam sendiri setelah menyala (logistik)
  Bahan padat TIDAK dimodelkan: hasil ujinya terlalu sedikit di tabel. Ditampilkan sebagai bukti.

Hanya butuh Python 3.9+ (tanpa numpy/pandas).   python scripts/build_model.py
"""
import argparse
import csv
import hashlib
import json
import math
import random
import sys
from pathlib import Path

P0 = 101.325  # kPa


# ---------- aljabar linear kecil (matriks <= 10x10) ---------------------------------------
def solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        for r in range(c + 1, n):
            f = M[r][c] / M[c][c]
            for k in range(c, n + 1):
                M[r][k] -= f * M[c][k]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        x[r] = (M[r][n] - sum(M[r][k] * x[k] for k in range(r + 1, n))) / M[r][r]
    return x


def xtwx(X, w, ridge):
    k = len(X[0])
    A = [[sum(w[i] * X[i][a] * X[i][b] for i in range(len(X))) for b in range(k)] for a in range(k)]
    for a in range(1, k):  # intersep tidak diberi penalti
        A[a][a] += ridge
    return A


def fit_ols(X, y, ridge=1e-6):
    w = [1.0] * len(X)
    return solve(xtwx(X, w, ridge), [sum(X[i][a] * y[i] for i in range(len(X))) for a in range(len(X[0]))])


def sigmoid(z):
    return 1 / (1 + math.exp(-max(-35, min(35, z))))


def fit_logit(X, y, ridge=0.1, iters=60):
    """IRLS pada fitur terstandar dengan penalti ridge kecil (stabil saat data hampir terpisah
    sempurna); koefisien dikembalikan ke skala asli fitur."""
    k, n = len(X[0]), len(X)
    mu = [0.0] + [sum(r[a] for r in X) / n for a in range(1, k)]
    sd = [1.0] + [math.sqrt(sum((r[a] - mu[a]) ** 2 for r in X) / n) or 1.0 for a in range(1, k)]
    Z = [[1.0] + [(r[a] - mu[a]) / sd[a] for a in range(1, k)] for r in X]
    beta = [0.0] * k
    for _ in range(iters):
        p = [sigmoid(sum(b * v for b, v in zip(beta, row))) for row in Z]
        w = [max(pi * (1 - pi), 1e-6) for pi in p]
        z = [sum(b * v for b, v in zip(beta, Z[i])) + (y[i] - p[i]) / w[i] for i in range(n)]
        new = solve(xtwx(Z, w, ridge), [sum(w[i] * Z[i][a] * z[i] for i in range(n)) for a in range(k)])
        done = max(abs(a - b) for a, b in zip(new, beta)) < 1e-8
        beta = new
        if done:
            break
    out = [beta[a] / sd[a] for a in range(k)]
    out[0] = beta[0] - sum(beta[a] * mu[a] / sd[a] for a in range(1, k))
    return out


def dot(beta, row):
    return sum(b * v for b, v in zip(beta, row))


def kfold(n, k=5, seed=7):
    idx = list(range(n))
    random.Random(seed).shuffle(idx)
    return [idx[i::k] for i in range(k)]


def cv_ols(X, y):
    pred = [0.0] * len(X)
    for fold in kfold(len(X)):
        s = set(fold)
        tr = [i for i in range(len(X)) if i not in s]
        b = fit_ols([X[i] for i in tr], [y[i] for i in tr])
        for i in fold:
            pred[i] = dot(b, X[i])
    return pred


def cv_logit(X, y):
    pred = [0.0] * len(X)
    for fold in kfold(len(X)):
        s = set(fold)
        tr = [i for i in range(len(X)) if i not in s]
        b = fit_logit([X[i] for i in tr], [y[i] for i in tr])
        for i in fold:
            pred[i] = sigmoid(dot(b, X[i]))
    return pred


def auc(p, y):
    pos = [a for a, b in zip(p, y) if b == 1]
    neg = [a for a, b in zip(p, y) if b == 0]
    if not pos or not neg:
        return None
    s = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg)
    return s / (len(pos) * len(neg))


def reg_metrics(y, fit, cv):
    m = sum(y) / len(y)
    sst = sum((v - m) ** 2 for v in y)
    rm = lambda p: math.sqrt(sum((a - b) ** 2 for a, b in zip(y, p)) / len(y))
    return {"n": len(y), "r2": round(1 - sum((a - b) ** 2 for a, b in zip(y, fit)) / sst, 3),
            "rmse_fit": round(rm(fit), 4), "rmse_cv": round(rm(cv), 4),
            "rmse_baseline": round(math.sqrt(sst / len(y)), 4)}


def cls_metrics(y, cv):
    base = sum(y) / len(y)
    brier = sum((p - v) ** 2 for p, v in zip(cv, y)) / len(y)
    acc = sum((p >= 0.5) == (v == 1) for p, v in zip(cv, y)) / len(y)
    a = auc(cv, y)
    return {"n": len(y), "positive_rate": round(base, 3), "accuracy_cv": round(acc, 3),
            "accuracy_baseline": round(max(base, 1 - base), 3), "brier_cv": round(brier, 4),
            "brier_baseline": round(base * (1 - base), 4), "auc_cv": None if a is None else round(a, 3)}


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rng(rows, key):
    v = [r[key] for r in rows if r.get(key) is not None]
    return [round(min(v), 4), round(max(v), 4)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    base = Path(__file__).resolve().parent.parent
    ap.add_argument("--root", type=Path, default=base / "kb")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--app", type=Path, default=None, help="folder keluaran simulator")
    a = ap.parse_args()
    gold = (a.out or a.root) / "gold"
    gold.mkdir(parents=True, exist_ok=True)
    src = a.root / "gold" / "tests.csv"
    raw = src.read_bytes()
    with open(src, newline="", encoding="utf-8") as f:
        T = list(csv.DictReader(f))

    # ================= FLEX (droplet) =================
    flex = []
    for r in T:
        if r["accession"] != "PSI-69":
            continue
        j = json.loads(r["raw_json"])
        g = lambda pre: next((fnum(v) for k, v in j.items() if k.startswith(pre)), None)
        o2, p = fnum(r["o2_mole_frac"]), fnum(r["pressure_kpa"])
        flex.append({"id": r["test_id"], "row": int(float(r["source_row"])), "fuel": r["fuel"],
                     "o2": o2, "p": p, "co2": g("CO initial") or 0.0, "he": g("He initial") or 0.0,
                     "d0": fnum(r["size_mm"]), "K": fnum(r["metric_value"]),
                     "t": fnum(r["burn_time_s"]), "end": r["outcome"],
                     "dext": g("Visible flame extinction")})
    fx = lambda r, with_d0: ([1.0, 1.0 if r["fuel"] == "Heptane" else 0.0, r["o2"], r["co2"], r["he"],
                              math.log(r["p"] / P0)] + ([r["d0"]] if with_d0 else []))
    Kset = [r for r in flex if r["K"] is not None and r["p"] and r["o2"] is not None]
    XK, yK = [fx(r, False) for r in Kset], [r["K"] for r in Kset]
    bK = fit_ols(XK, yK)
    fitK, cvK = [dot(bK, x) for x in XK], cv_ols(XK, yK)
    mK = reg_metrics(yK, fitK, cvK)
    # cek satuan: waktu bakar / (d0^2/K) harus <= ~1 bila K bersatuan mm^2/s
    ratio = sorted(r["t"] / (r["d0"] ** 2 / r["K"]) for r in Kset if r["t"] and r["d0"] and r["K"])
    unit_check = {"median": round(ratio[len(ratio) // 2], 2), "p90": round(ratio[int(len(ratio) * 0.9)], 2),
                  "n": len(ratio)}

    Eset = [r for r in flex if r["end"] in ("Extinction", "Completion") and r["p"] and r["d0"]]
    XE, yE = [fx(r, True) for r in Eset], [1 if r["end"] == "Extinction" else 0 for r in Eset]
    bE = fit_logit(XE, yE)
    mE = cls_metrics(yE, cv_logit(XE, yE))

    # ================= CFI-G (nyala gas) =================
    gas = []
    for r in T:
        if r["accession"] != "PSI-159":
            continue
        j = json.loads(r["raw_json"])
        xf = next((fnum(v) for k, v in j.items() if k.strip().lower().startswith("xf")), None)
        fl = r["fuel"].lower()
        gas.append({"id": r["test_id"], "row": int(float(r["source_row"])), "table": r["table_name"],
                    "fuel": r["fuel"], "base": "butane" if "butane" in fl else "propane" if "propane" in fl
                    else "ethane", "inv": 1.0 if "Inverse" in r["table_name"] else 0.0,
                    "o2": fnum(r["o2_mole_frac"]), "xf": xf, "p": fnum(r["pressure_kpa"]),
                    "ign": r["ignited"], "out": r["outcome"], "t": fnum(r["burn_time_s"]),
                    "tad": fnum(r["metric_value"])})
    gx = lambda r: [1.0, r["inv"], 1.0 if r["base"] == "propane" else 0.0,
                    1.0 if r["base"] == "butane" else 0.0, r["o2"], r["xf"], math.log(r["p"] / P0)]
    ok = lambda r: r["o2"] is not None and r["xf"] is not None and r["p"]
    Iset = [r for r in gas if ok(r) and r["ign"] in ("yes", "no")]
    XI, yI = [gx(r) for r in Iset], [1 if r["ign"] == "yes" else 0 for r in Iset]
    bI = fit_logit(XI, yI)
    mI = cls_metrics(yI, cv_logit(XI, yI))
    Sset = [r for r in gas if ok(r) and r["ign"] == "yes"
            and r["out"] in ("self-extinguished", "flow terminated")]
    XS, yS = [gx(r) for r in Sset], [1 if r["out"] == "self-extinguished" else 0 for r in Sset]
    bS = fit_logit(XS, yS)
    mS = cls_metrics(yS, cv_logit(XS, yS))

    # ================= bahan padat: bukti saja =================
    solids = []
    for r in T:
        if r["fuel_phase"] != "solid" or r["granularity"] != "test":
            continue
        solids.append({"acc": r["accession"], "exp": r["acronym"], "id": r["test_id"],
                       "row": int(float(r["source_row"])), "fuel": r["fuel"],
                       "o2": fnum(r["o2_mole_frac"]), "o2f": fnum(r["o2_final_mole_frac"]),
                       "flow": fnum(r["flow_cm_s"]), "dir": r["flow_direction"] or None,
                       "t": fnum(r["burn_time_s"]), "out": r["outcome"] or None,
                       "spread": fnum(r["metric_value"]) if r["metric_name"] == "spread_rate" else None})

    r5 = lambda v: [round(x, 5) for x in v]
    params = {
        "built_from": {"file": "kb/gold/tests.csv", "sha256": hashlib.sha256(raw).hexdigest()[:16],
                       "rows": len(T)},
        "flex_K": {"what": "d^2-law burning-rate constant K (mm^2/s): d^2 = d0^2 - K t",
                   "features": ["1", "heptane", "o2", "x_co2", "x_he", "ln(p/101.325)"],
                   "beta": r5(bK), "resid_sd": mK["rmse_cv"], "metrics": mK, "unit_check": unit_check,
                   "range": {"o2": rng(Kset, "o2"), "p": rng(Kset, "p"), "co2": rng(Kset, "co2"),
                             "he": rng(Kset, "he"), "d0": rng(Kset, "d0")}},
        "flex_ext": {"what": "P(flame extinguishes before droplet is consumed); disrupted tests excluded",
                     "features": ["1", "heptane", "o2", "x_co2", "x_he", "ln(p/101.325)", "d0_mm"],
                     "beta": r5(bE), "metrics": mE},
        "gas_ign": {"what": "P(hot ignition), ACME CFI-G",
                    "features": ["1", "inverse", "propane", "butane", "o2", "x_fuel", "ln(p/101.325)"],
                    "beta": r5(bI), "metrics": mI,
                    "range": {"o2": rng(Iset, "o2"), "p": rng(Iset, "p"), "xf": rng(Iset, "xf")}},
        "gas_selfext": {"what": "P(self-extinguished | ignited); otherwise ended by flow termination",
                        "features": ["1", "inverse", "propane", "butane", "o2", "x_fuel", "ln(p/101.325)"],
                        "beta": r5(bS), "metrics": mS},
        "solid": {"what": "no fitted model: too few tabulated outcomes", "n_tests": len(solids),
                  "n_with_outcome": sum(1 for s in solids if s["out"]),
                  "n_with_spread_rate": sum(1 for s in solids if s["spread"] is not None)},
    }
    (gold / "model_params.json").write_text(json.dumps(params, indent=1), encoding="utf-8")
    sim = {"flex": flex, "gas": gas, "solid": solids}
    (gold / "sim_data.json").write_text(json.dumps(sim, separators=(",", ":")), encoding="utf-8")

    def tbl(name, m):
        return "| " + name + " | " + " | ".join(str(m.get(k, "")) for k in cols) + " |"
    rep = ["# Laporan validasi model — Flame in Freefall", "",
           f"Sumber: `kb/gold/tests.csv` ({len(T)} baris, sha256 {params['built_from']['sha256']}). "
           "Validasi silang 5 lipatan, pembagian acak dengan benih tetap.", "",
           "## Penilaian keseluruhan: bagikan dengan catatan", "",
           "## Regresi", "", "| Model | n | R² | RMSE fit | RMSE CV | RMSE tanpa model |", "|---|---|---|---|---|---|",
           f"| FLEX K (mm²/s) | {mK['n']} | {mK['r2']} | {mK['rmse_fit']} | {mK['rmse_cv']} | {mK['rmse_baseline']} |",
           "", "## Klasifikasi", "",
           "| Model | n | laju positif | akurasi CV | akurasi tebak mayoritas | Brier CV | Brier dasar | AUC CV |",
           "|---|---|---|---|---|---|---|---|"]
    cols = ["n", "positive_rate", "accuracy_cv", "accuracy_baseline", "brier_cv", "brier_baseline", "auc_cv"]
    rep += [tbl("FLEX padam", mE), tbl("CFI-G menyala", mI), tbl("CFI-G padam sendiri", mS), "",
            "## Koefisien", ""]
    for key in ("flex_K", "flex_ext", "gas_ign", "gas_selfext"):
        rep.append(f"**{key}** — {params[key]['what']}")
        rep.append("")
        rep += [f"- `{n}`: {b}" for n, b in zip(params[key]["features"], params[key]["beta"])]
        rep.append("")
    rep += ["## Cek satuan K", "",
            f"Waktu bakar dibagi d0²/K: median {unit_check['median']}, persentil-90 {unit_check['p90']} "
            f"(n = {unit_check['n']}). Rasio yang berkumpul di bawah 1 konsisten dengan hukum d² bila K "
            "bersatuan mm²/s. Tabel sumber hanya menulis \"mm\".", "",
            "## Catatan wajib untuk pengguna", "",
            "- Uji FLEX yang berakhir \"Disruption\" dikeluarkan dari model padam; itu gangguan droplet, bukan hasil pembakaran.",
            "- Model hanya berlaku di dalam rentang data (lihat `range` di model_params.json). Di luar itu simulator menandai ekstrapolasi.",
            "- Semua data adalah mikrogravitasi. Model tidak mengandung variabel gravitasi.",
            "- Hubungan ini korelasi dalam matriks uji yang dirancang, bukan bukti sebab-akibat di luar rancangan itu.",
            f"- Bahan padat: {params['solid']['n_tests']} uji, hanya {params['solid']['n_with_outcome']} dengan hasil dan "
            f"{params['solid']['n_with_spread_rate']} dengan laju rambat. Tidak dimodelkan."]
    (gold / "model_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")

    tpl = Path(__file__).resolve().parent / "lab_template.html"
    if tpl.exists():
        app = a.app or (base / "app")
        app.mkdir(parents=True, exist_ok=True)
        html = tpl.read_text(encoding="utf-8").replace(
            "/*__MODEL__*/null", json.dumps(params, separators=(",", ":"))).replace(
            "/*__DATA__*/null", json.dumps(sim, separators=(",", ":")))
        (app / "freefall_lab.html").write_text(html, encoding="utf-8")
        print("Simulator:", app / "freefall_lab.html")
    print(json.dumps({"flex_K": mK, "unit_check": unit_check, "flex_ext": mE, "gas_ign": mI,
                      "gas_selfext": mS, "solid": params["solid"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
