#!/usr/bin/env python3
"""Titik asap SPICE (PSI-107): data, model berbasis fisika, dan ketidakpastiannya.

Tabel uji PSI untuk SPICE TIDAK menandai titik asap: barisnya adalah kondisi nyala
(laju bahan bakar + coflow), dan untuk penyalaan yang sama lajunya bisa berbeda dari
laju di titik asap (mis. E16-2: tabel 1,97 mg/s, lembar titik asap 2,41 mg/s).
Label sebenarnya ada di berkas mentah NASA
  kb/raw/psi/files/PSI-107/Raw Data/PSI-107_Raw Data_SmokePointReview-0g-3.xlsx
(lembar "Smoke Point Datasheet", 55 titik asap, panjang nyala L_SP dalam mm).

Pedoman metode: Ihme, Chung & Mishra (2022), "Combustion machine learning",
Prog. Energy Combust. Sci. 91:101010, bagian 5:
  5.2 interpretabilitas -> model utama hukum pangkat, tiap koefisien bermakna fisik;
  5.3 ketidakpastian    -> selang prediksi + bootstrap cluster per hari;
  5.4 luar distribusi   -> model menandai "ekstrapolasi" di luar rentang uji;
  5.5 pengetahuan fisika -> GP hanya mengoreksi sisa dari hukum pangkat (hibrida).

Validasi utama: tinggalkan-satu-hari (11 hari). Uji pada hari yang sama berbagi
keadaan alat (Dotson 2009: saluran buang tersumbat jelaga mengubah titik asap
propilena 0,41 mm antar-hari), jadi lipatan acak terlalu optimistis.

  python scripts/spice_smoke_point.py                     # -> analysis/spice/
  python scripts/spice_smoke_point.py predict --fuel propylene --d 0.76 --u 30

Berkas mentah (±3,5 MB) diambil dengan fungsi download() dari psi_fetch.py; kalau
belum ada, skrip memakai analysis/spice/smoke_points.csv hasil ekstraksi sebelumnya.
"""
import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "kb" / "raw" / "psi" / "files" / "PSI-107" / "Raw Data"
XLSX = RAW / "PSI-107_Raw Data_SmokePointReview-0g-3.xlsx"
TABLE = ROOT / "kb" / "clean" / "PSI-107_Experimental_table_Spice.csv"
OUT = ROOT / "analysis" / "spice"
SEED = 20261114
N_BOOT = 4000

# Zst bahan bakar (aliran bahan bakar termasuk N2) - Dotson 2009, Tabel 3.1
ZST = {"ethylene": 0.0637, "propane": 0.0603, "propylene": 0.0637,
       "propylene75": 0.0768, "propylene50": 0.1018}
FUELS = ["propane", "ethylene", "propylene50", "propylene75", "propylene"]
LABEL = {"propane": "propana", "ethylene": "etilena", "propylene": "propilena",
         "propylene75": "75% propilena", "propylene50": "50% propilena"}
# Klaim terbitan yang diuji
PUB_EXP = {"d": -0.91, "u": 0.41,
           "sumber": "SPICE Final Report (PSI-107 Reports), abstrak: L_SP ~ d^-0.91 * u^0.41"}
PUB_RANK = ["propane", "ethylene", "propylene50", "propylene75", "propylene"]  # L_SP turun = makin berjelaga
REF = {"d": 1.6002, "u": 30.0}


def fuel_key(s):
    s = str(s).lower().replace(" ", "")
    if "75%" in s:
        return "propylene75"
    if "50%" in s:
        return "propylene50"
    for k in ("ethylene", "propylene", "propane", "methane"):
        if k in s:
            return k
    return s


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- data

def extract():
    """55 titik asap dari lembar NASA; mengembalikan list dict."""
    import openpyxl
    wb = openpyxl.load_workbook(XLSX, data_only=True, read_only=True)
    R = list(wb["Smoke Point Datasheet"].iter_rows(values_only=True))
    rows = []
    for i, r in enumerate(R, start=1):
        if i < 5 or len(r) < 46 or r[5] is None or r[6] is None or fnum(r[18]) is None:
            continue
        rows.append({
            "tp": str(r[5]), "day": int(str(r[0]).strip()), "gmt_ignition": str(r[1]),
            "gmt_data": str(r[3]), "fuel": fuel_key(r[6]), "d_mm": float(r[7]), "x_fuel": float(r[11]),
            "L_sp_mm": float(r[18]), "width_mm": fnum(r[20]), "u_air_cm_s": float(r[29]),
            "u_fuel_cm_s": fnum(r[30]), "mdot_total_mg_s": float(r[27]), "mdot_hc_mg_s": float(r[28]),
            "t_res_ms": fnum(r[45]), "tad_K": fnum(r[22]),
            "source": f"{XLSX.name}#Smoke Point Datasheet!row{i}"})
    return rows


def load_points():
    OUT.mkdir(parents=True, exist_ok=True)
    cached = OUT / "smoke_points.csv"
    if XLSX.exists():
        pts = extract()
        with open(cached, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(pts[0]))
            w.writeheader()
            w.writerows(pts)
        return pts, "xlsx"
    if cached.exists():
        pts = list(csv.DictReader(open(cached, encoding="utf-8")))
        for p in pts:
            for k in ("day",):
                p[k] = int(p[k])
            for k in ("d_mm", "x_fuel", "L_sp_mm", "u_air_cm_s", "mdot_total_mg_s", "mdot_hc_mg_s"):
                p[k] = float(p[k])
            for k in ("width_mm", "u_fuel_cm_s", "t_res_ms", "tad_K"):
                p[k] = fnum(p[k])
        return pts, "csv"
    sys.exit("Berkas mentah tidak ada. Ambil dulu (lihat docstring) atau sediakan analysis/spice/smoke_points.csv")


def table_crosscheck(pts):
    """Seberapa jauh tabel PSI dari titik asap: cocokkan per (hari, jam penyalaan)."""
    T = list(csv.DictReader(open(TABLE, encoding="utf-8")))
    def hm(s):
        s = str(s).replace(".", ":")
        p = s.split(":")
        return f"{int(p[0]):02d}:{p[1]}:{p[2][:2]}" if len(p) >= 3 and p[0].isdigit() else s
    by = {}
    for r in T:
        by.setdefault((int(r["gmt_date"]), hm(r["gmt_ignition"])), []).append(r)
    out = []
    for p in pts:
        rs = by.get((p["day"], hm(p["gmt_ignition"])))
        if not rs:
            out.append({"tp": p["tp"], "day": p["day"], "in_table": False})
            continue
        m = [fnum(r["hc_fuel_rate_mg_s"]) for r in rs if fnum(r["hc_fuel_rate_mg_s"])]
        near = min(m, key=lambda v: abs(v - p["mdot_hc_mg_s"])) if m else None
        out.append({"tp": p["tp"], "day": p["day"], "in_table": True, "n_rows": len(rs),
                    "sp_mdot_hc": p["mdot_hc_mg_s"], "table_nearest_mdot_hc": near,
                    "rel_diff": None if near is None else round(near / p["mdot_hc_mg_s"] - 1, 3)})
    # cek mutu tabel
    q = {"rows": len(T),
         "air_negative": sum(1 for r in T if (fnum(r["air_rate_cm_s"]) or 0) < 0),
         "air_missing": sum(1 for r in T if fnum(r["air_rate_cm_s"]) is None),
         "fuel_rate_missing": sum(1 for r in T if fnum(r["fuel_rate_mg_s"]) is None),
         "exact_duplicates_consecutive": sum(1 for i in range(1, len(T)) if T[i] == T[i - 1]),
         "fuel_label_variants": sorted({r["fuel"] for r in T}),
         "propylene75_bad_hc_fraction": sum(
             1 for r in T if fuel_key(r["fuel"]) == "propylene75" and fnum(r["fuel_rate_mg_s"])
             and fnum(r["hc_fuel_rate_mg_s"]) is not None
             and abs(fnum(r["hc_fuel_rate_mg_s"]) / fnum(r["fuel_rate_mg_s"]) - 0.818) > 0.02)}
    return out, q


# ---------------------------------------------------------------- model

def design(pts, kind, fuels):
    ld = np.log([p["d_mm"] for p in pts])
    lu = np.log([p["u_air_cm_s"] for p in pts])
    F = np.array([[1.0 if p["fuel"] == f else 0.0 for f in fuels] for p in pts])
    if kind == "mean":
        return F
    if kind == "pub":            # eksponen terbitan tetap; hanya intersep bahan bakar
        return F
    X = np.c_[F, lu, ld]
    if kind == "pow2":           # + kelengkungan diameter (Dotson: efek d tak linear)
        X = np.c_[X, ld ** 2]
    return X


def offset(pts, kind):
    if kind != "pub":
        return np.zeros(len(pts))
    return np.array([PUB_EXP["d"] * math.log(p["d_mm"]) + PUB_EXP["u"] * math.log(p["u_air_cm_s"]) for p in pts])


def ols(X, y):
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    dof = max(1, len(y) - np.linalg.matrix_rank(X))
    s2 = float(r @ r) / dof
    XtXi = np.linalg.pinv(X.T @ X)
    return beta, s2, XtXi, dof


def t_quant(p, dof):
    from scipy.stats import t
    return float(t.ppf(p, dof))


# --- GP pada sisa hukum pangkat (hibrida fisika + data) -----------------

def gp_feats(pts, fuels):
    ld = np.log([p["d_mm"] for p in pts])
    lu = np.log([p["u_air_cm_s"] for p in pts])
    F = np.array([[1.0 if p["fuel"] == f else 0.0 for f in fuels] for p in pts])
    return ld, lu, F


def kern(A, B, ls_c, ls_f, s2):
    (lda, lua, Fa), (ldb, lub, Fb) = A, B
    d2 = ((lda[:, None] - ldb[None]) ** 2 + (lua[:, None] - lub[None]) ** 2) / ls_c ** 2
    d2 = d2 + ((Fa[:, None, :] - Fb[None]) ** 2).sum(-1) / ls_f ** 2
    return s2 * np.exp(-0.5 * d2)


GRID = [(lc, lf, s2, nz) for lc in (0.3, 0.6, 1.2, 2.5) for lf in (0.7, 2.0, 1e3)
        for s2 in (0.003, 0.01, 0.04) for nz in (0.002, 0.005, 0.01, 0.02)]


def gp_fit(A, r):
    best = None
    n = len(r)
    for lc, lf, s2, nz in GRID:
        K = kern(A, A, lc, lf, s2) + nz * np.eye(n)
        try:
            L = np.linalg.cholesky(K)
        except np.linalg.LinAlgError:
            continue
        al = np.linalg.solve(L.T, np.linalg.solve(L, r))
        lml = -0.5 * r @ al - np.log(np.diag(L)).sum() - 0.5 * n * math.log(2 * math.pi)
        if best is None or lml > best[0]:
            best = (lml, (lc, lf, s2, nz), L, al)
    return best


def gp_predict(fit, A, B):
    _, (lc, lf, s2, nz), L, al = fit
    Ks = kern(B, A, lc, lf, s2)
    mu = Ks @ al
    v = np.linalg.solve(L, Ks.T)
    var = s2 - (v * v).sum(0) + nz
    return mu, np.maximum(var, 1e-9)


# ---------------------------------------------------------------- validasi

MODELS = {
    "mean": "rerata per bahan bakar (tanpa fisika)",
    "pub": "eksponen terbitan NASA tetap (d^-0.91 u^0.41), intersep per bahan bakar",
    "pow": "hukum pangkat dipasang: ln L = a_bb + b ln u + c ln d",
    "pow2": "hukum pangkat + (ln d)^2",
    "hybrid": "hukum pangkat + GP pada sisa (hibrida fisika-data)",
}
PI = 0.90


def fit_predict(kind, tr, te, fuels):
    y = np.log([p["L_sp_mm"] for p in tr])
    base = "pow" if kind == "hybrid" else kind
    X, Xt = design(tr, base, fuels), design(te, base, fuels)
    yo, yto = y - offset(tr, base), offset(te, base)
    beta, s2, XtXi, dof = ols(X, yo)
    mu = Xt @ beta + yto
    var = s2 * (1 + np.einsum("ij,jk,ik->i", Xt, XtXi, Xt))
    lo_q = t_quant(0.5 + PI / 2, dof)
    if kind != "hybrid":
        return mu, mu - lo_q * np.sqrt(var), mu + lo_q * np.sqrt(var)
    r = yo - X @ beta
    A, B = gp_feats(tr, fuels), gp_feats(te, fuels)
    fit = gp_fit(A, r)
    dmu, dvar = gp_predict(fit, A, B)
    z = 1.6449
    return mu + dmu, mu + dmu - z * np.sqrt(dvar), mu + dmu + z * np.sqrt(dvar)


def evaluate(pts, kind, groups):
    fuels = FUELS
    y = np.log([p["L_sp_mm"] for p in pts])
    pred, lo, hi = np.full(len(y), np.nan), np.full(len(y), np.nan), np.full(len(y), np.nan)
    skipped = 0
    for g in sorted(set(groups)):
        te_i = [i for i, x in enumerate(groups) if x == g]
        tr_i = [i for i, x in enumerate(groups) if x != g]
        tr = [pts[i] for i in tr_i]
        seen = {p["fuel"] for p in tr}
        ok = [i for i in te_i if pts[i]["fuel"] in seen]      # bahan bakar tak terlihat = tak bisa diprediksi
        skipped += len(te_i) - len(ok)
        if not ok:
            continue
        m, l, h = fit_predict(kind, tr, [pts[i] for i in ok], fuels)
        pred[ok], lo[ok], hi[ok] = m, l, h
    k = ~np.isnan(pred)
    err = pred[k] - y[k]
    return {"n_dinilai": int(k.sum()), "n_dilewati_bb_tak_terlihat": skipped,
            "rmse_ln": round(float(np.sqrt(np.mean(err ** 2))), 4),
            "galat_tipikal_pct": round(100 * (math.exp(float(np.sqrt(np.mean(err ** 2)))) - 1), 1),
            "mae_mm": round(float(np.mean(np.abs(np.exp(pred[k]) - np.exp(y[k])))), 2),
            "cakupan_PI90": round(float(np.mean((y[k] >= lo[k]) & (y[k] <= hi[k]))), 3),
            "lebar_PI90_ln": round(float(np.mean(hi[k] - lo[k])), 3)}, pred


def fit_full(pts):
    y = np.log([p["L_sp_mm"] for p in pts])
    X = design(pts, "pow", FUELS)
    beta, s2, XtXi, dof = ols(X, y)
    return beta, s2, XtXi, dof


def boot_by_day(pts):
    rng = np.random.default_rng(SEED)
    days = sorted({p["day"] for p in pts})
    byd = {d: [p for p in pts if p["day"] == d] for d in days}
    b_u, b_d, lref = [], [], {f: [] for f in FUELS}
    for _ in range(N_BOOT):
        s = [p for d in rng.choice(days, len(days)) for p in byd[d]]
        fu = [f for f in FUELS if any(p["fuel"] == f for p in s)]
        if len({p["d_mm"] for p in s}) < 2 or len({round(p["u_air_cm_s"]) for p in s}) < 3:
            continue
        y = np.log([p["L_sp_mm"] for p in s])
        beta, *_ = np.linalg.lstsq(design(s, "pow", fu), y, rcond=None)
        b_u.append(beta[len(fu)])
        b_d.append(beta[len(fu) + 1])
        for j, f in enumerate(fu):
            lref[f].append(math.exp(beta[j] + beta[len(fu)] * math.log(REF["u"]) + beta[len(fu) + 1] * math.log(REF["d"])))
    ci = lambda a: [round(float(np.percentile(a, 2.5)), 3), round(float(np.percentile(a, 97.5)), 3)]
    return {"n_boot_valid": len(b_u), "u": ci(b_u), "d": ci(b_d),
            "L_ref_ci": {f: ci(v) for f, v in lref.items() if len(v) > 100},
            "L_ref_n": {f: len(v) for f, v in lref.items()}, "_lref": lref}


def naive_ci(pts):
    beta, s2, XtXi, dof = fit_full(pts)
    k = len(FUELS)
    q = t_quant(0.975, dof)
    se = np.sqrt(np.diag(s2 * XtXi))
    return {"u": [round(beta[k] - q * se[k], 3), round(beta[k] + q * se[k], 3)],
            "d": [round(beta[k + 1] - q * se[k + 1], 3), round(beta[k + 1] + q * se[k + 1], 3)]}


def domain(pts):
    """Rentang berlaku per (bahan bakar, nosel): u_air min-maks yang benar-benar diuji."""
    dom = {}
    for p in pts:
        k = f"{p['fuel']}|{p['d_mm']:.4f}"
        a = dom.setdefault(k, [p["u_air_cm_s"], p["u_air_cm_s"], 0])
        a[0], a[1], a[2] = min(a[0], p["u_air_cm_s"]), max(a[1], p["u_air_cm_s"]), a[2] + 1
    return {k: {"u_min": round(v[0], 2), "u_max": round(v[1], 2), "n": v[2]} for k, v in dom.items()}


def length_correlation(pts):
    """L_SP vs mdot_total/Zst lewat titik asal (Dotson 2009 Gb. 4.5) + efek kedua u_a/u_f."""
    x = np.array([p["mdot_total_mg_s"] / ZST[p["fuel"]] for p in pts])
    y = np.array([p["L_sp_mm"] for p in pts])
    k = float(x @ y / (x @ x))
    r = y - k * x
    r2 = 1 - float(r @ r) / float(((y - y.mean()) ** 2).sum())
    ratio = np.array([p["u_air_cm_s"] / p["u_fuel_cm_s"] if p["u_fuel_cm_s"] else np.nan for p in pts])
    lo = ratio < 0.08
    rel = y / (k * x)
    return {"slope_mm_per_mg_s": round(k, 3), "r2": round(r2, 3),
            "rasio_ukur_per_prediksi_ua_uf_lt_0.08": round(float(np.median(rel[lo])), 3) if lo.any() else None,
            "rasio_ukur_per_prediksi_ua_uf_ge_0.08": round(float(np.median(rel[~lo])), 3),
            "n_ua_uf_lt_0.08": int(lo.sum())}


def day_residuals(pts):
    y = np.log([p["L_sp_mm"] for p in pts])
    beta, *_ = fit_full(pts)
    r = y - design(pts, "pow", FUELS) @ beta
    out = {}
    for d in sorted({p["day"] for p in pts}):
        idx = [i for i, p in enumerate(pts) if p["day"] == d]
        out[str(d)] = {"n": len(idx), "rerata_sisa_pct": round(100 * (math.exp(float(np.mean(r[idx]))) - 1), 1),
                       "bahan_bakar": sorted({pts[i]["fuel"] for i in idx})}
    worst = sorted(range(len(pts)), key=lambda i: -abs(r[i]))[:5]
    return out, [{"tp": pts[i]["tp"], "day": pts[i]["day"], "fuel": pts[i]["fuel"], "d_mm": pts[i]["d_mm"],
                  "sisa_pct": round(100 * (math.exp(float(r[i])) - 1), 1)} for i in worst]


# ---------------------------------------------------------------- prediksi

def predict(pts, fuel, d, u):
    fuel = fuel_key(fuel)
    if fuel not in FUELS:
        return {"status": "ditolak", "alasan": f"bahan bakar '{fuel}' tidak punya titik asap SPICE "
                "(metana: nyala menabrak pelat sebelum titik asap, Dotson 2009)"}
    m, lo, hi = fit_predict("hybrid", pts, [{"fuel": fuel, "d_mm": d, "u_air_cm_s": u, "L_sp_mm": 1.0}], FUELS)
    dom = domain(pts)
    k = f"{fuel}|{d:.4f}"
    near = [kk for kk in dom if kk.startswith(fuel + "|") and abs(float(kk.split("|")[1]) - d) < 0.01]
    flags = []
    if not near:
        flags.append("ekstrapolasi: kombinasi bahan bakar-nosel ini tidak pernah diuji")
    else:
        r = dom[near[0]]
        if not (r["u_min"] <= u <= r["u_max"]):
            flags.append(f"ekstrapolasi: coflow di luar {r['u_min']}-{r['u_max']} cm/s yang diuji untuk kombinasi ini")
    all_d = sorted({p["d_mm"] for p in pts})
    if not (min(all_d) - 1e-3 <= d <= max(all_d) + 1e-3):
        flags.append("ekstrapolasi: diameter di luar 0,41-1,6 mm")
    lmax = max(p["L_sp_mm"] for p in pts)
    if math.exp(m[0]) > lmax:
        flags.append(f"ekstrapolasi: L_SP di atas nyala terpanjang yang teramati ({lmax:.0f} mm); "
                     "nyala sepanjang ini bisa menabrak pelat ujung duct sebelum titik asap (Dotson 2009, metana)")
    return {"status": "ekstrapolasi" if flags else "dalam_rentang", "fuel": fuel, "d_mm": d, "u_air_cm_s": u,
            "L_sp_mm": round(math.exp(m[0]), 1), "PI90_mm": [round(math.exp(lo[0]), 1), round(math.exp(hi[0]), 1)], "interval_level_pct": 90,
            "tier": "model_prediction", "model": "spice_smoke_point_hybrid", "flags": flags}


# ---------------------------------------------------------------- gambar

def figure(pts, preds_day, beta, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {"propane": "#1b9e77", "ethylene": "#7570b3", "propylene50": "#e6ab02",
           "propylene75": "#d95f02", "propylene": "#e7298a"}
    mk = {0.4064: "^", 0.762: "s", 1.6002: "o"}
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.6))
    k = len(FUELS)
    for f in FUELS:
        for d in sorted({p["d_mm"] for p in pts}):
            s = [p for p in pts if p["fuel"] == f and p["d_mm"] == d]
            if not s:
                continue
            ax[0].scatter([p["u_air_cm_s"] for p in s], [p["L_sp_mm"] for p in s], c=col[f], marker=mk.get(d, "o"),
                          s=34, edgecolor="k", linewidth=0.4)
            uu = np.linspace(min(p["u_air_cm_s"] for p in s), max(p["u_air_cm_s"] for p in s), 30)
            ax[0].plot(uu, np.exp(beta[FUELS.index(f)] + beta[k] * np.log(uu) + beta[k + 1] * math.log(d)),
                       c=col[f], lw=1)
    for f in FUELS:
        ax[0].scatter([], [], c=col[f], label=LABEL[f])
    for d, m in mk.items():
        ax[0].scatter([], [], c="w", edgecolor="k", marker=m, label=f"d = {d:.2f} mm")
    ax[0].set(xlabel="kecepatan coflow u (cm/s)", ylabel="panjang titik asap L_SP (mm)",
              title="Titik asap SPICE + hukum pangkat", ylim=(0, 150))
    ax[0].legend(fontsize=7, ncol=3, loc="upper center")
    y = np.array([p["L_sp_mm"] for p in pts])
    ok = ~np.isnan(preds_day)
    ax[1].scatter(y[ok], np.exp(preds_day[ok]), c=[col[p["fuel"]] for p, o in zip(pts, ok) if o], s=30,
                  edgecolor="k", linewidth=0.4)
    lim = [10, 120]
    ax[1].plot(lim, lim, "k--", lw=0.8)
    ax[1].set(xscale="log", yscale="log", xlim=lim, ylim=lim, xlabel="L_SP terukur (mm)",
              ylabel="L_SP prediksi, hari ditinggalkan (mm)", title="Validasi tinggalkan-satu-hari (hibrida)")
    x = np.array([p["mdot_total_mg_s"] / ZST[p["fuel"]] for p in pts])
    ax[2].scatter(x, y, c=[col[p["fuel"]] for p in pts], s=30, edgecolor="k", linewidth=0.4)
    kk = float(x @ y / (x @ x))
    ax[2].plot([0, x.max()], [0, kk * x.max()], "k-", lw=0.8)
    ax[2].set(xlabel="ṁ / Zst (mg/s)", ylabel="L_SP (mm)", title=f"Panjang nyala ~ ṁ/Zst (kemiringan {kk:.2f})")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# ---------------------------------------------------------------- main

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")
    pp = sub.add_parser("predict")
    pp.add_argument("--fuel", required=True)
    pp.add_argument("--d", type=float, required=True, help="diameter nosel (mm)")
    pp.add_argument("--u", type=float, required=True, help="kecepatan coflow (cm/s)")
    a = ap.parse_args()

    pts, src = load_points()
    if a.cmd == "predict":
        print(json.dumps(predict(pts, a.fuel, a.d, a.u), ensure_ascii=False, indent=1))
        return

    days = [p["day"] for p in pts]
    rng = np.random.default_rng(SEED)
    rand_groups = list(rng.permutation(len(pts)) % 5)
    res, preds = {}, {}
    for kind in MODELS:
        res[kind] = {"model": MODELS[kind]}
        res[kind]["per_hari"], preds[kind] = evaluate(pts, kind, days)
        res[kind]["acak_5lipat"], _ = evaluate(pts, kind, rand_groups)

    beta, s2, XtXi, dof = fit_full(pts)
    k = len(FUELS)
    boot = boot_by_day(pts)
    lref_pt = {f: round(math.exp(beta[j] + beta[k] * math.log(REF["u"]) + beta[k + 1] * math.log(REF["d"])), 1)
               for j, f in enumerate(FUELS)}
    # peluang urutan terbitan bertahan di bootstrap (pasangan bersebelahan)
    boot.pop("_lref")
    # sampel bootstrap sejajar per ulangan: bandingkan intersep dua bahan bakar di ulangan yang sama
    pair = {f"{f1}>{f2}": None for f1, f2 in zip(PUB_RANK, PUB_RANK[1:])}
    rng2 = np.random.default_rng(SEED + 1)
    dset = sorted(set(days))
    byd = {d: [p for p in pts if p["day"] == d] for d in dset}
    wins, tot = {key: 0 for key in pair}, {key: 0 for key in pair}
    full_order = 0
    full_n = 0
    for _ in range(N_BOOT):
        s = [p for d in rng2.choice(dset, len(dset)) for p in byd[d]]
        fu = [f for f in FUELS if any(p["fuel"] == f for p in s)]
        if len({p["d_mm"] for p in s}) < 2:
            continue
        b, *_ = np.linalg.lstsq(design(s, "pow", fu), np.log([p["L_sp_mm"] for p in s]), rcond=None)
        a_ = {f: b[j] for j, f in enumerate(fu)}
        for f1, f2 in zip(PUB_RANK, PUB_RANK[1:]):
            if f1 in a_ and f2 in a_:
                tot[f"{f1}>{f2}"] += 1
                wins[f"{f1}>{f2}"] += a_[f1] > a_[f2]
        if all(f in a_ for f in PUB_RANK):
            full_n += 1
            full_order += all(a_[x] > a_[y] for x, y in zip(PUB_RANK, PUB_RANK[1:]))
    rank_test = {key: {"P_bertahan": round(wins[key] / tot[key], 3) if tot[key] else None, "n": tot[key]}
                 for key in pair}

    cross, quality = table_crosscheck(pts)
    in_tab = [c for c in cross if c["in_table"]]
    rel = [abs(c["rel_diff"]) for c in in_tab if c["rel_diff"] is not None]
    dres, worst = day_residuals(pts)

    out = {
        "sumber": {"titik_asap": f"{XLSX.name} (lembar 'Smoke Point Datasheet'), dibaca dari {src}",
                   "pedoman_metode": "Ihme, Chung & Mishra 2022, PECS 91:101010, bagian 5.2-5.5",
                   "klaim_diuji": ["SPICE Final Report: L_SP ~ d^-0.91 u^0.41",
                                   "Dotson 2009 (tesis, PSI-107 Reports): urutan berjelaga propana < etilena < "
                                   "50% < 75% < propilena; L_SP ~ mdot/Zst; efek hari pada propilena 0,41 mm"]},
        "n_titik_asap": len(pts), "hari": len(set(days)),
        "per_bahan_bakar": {f: sum(1 for p in pts if p["fuel"] == f) for f in FUELS},
        "catatan_jumlah": "Laporan akhir menyebut 52 titik asap, Tabel 3.1 tesis 52 (6/6/20/13/7); "
                          "lembar NASA berisi 55 (propilena 22, 75% 14). Dipakai apa adanya.",
        "eksponen": {"u": {"nilai": round(float(beta[k]), 3), "ci95_cluster_hari": boot["u"],
                           "ci95_naif": naive_ci(pts)["u"], "terbitan": PUB_EXP["u"]},
                     "d": {"nilai": round(float(beta[k + 1]), 3), "ci95_cluster_hari": boot["d"],
                           "ci95_naif": naive_ci(pts)["d"], "terbitan": PUB_EXP["d"]},
                     "n_boot": boot["n_boot_valid"]},
        "L_SP_rujukan": {"kondisi": f"d = {REF['d']} mm, u = {REF['u']} cm/s",
                         "nilai_mm": lref_pt, "ci95_cluster_hari": boot["L_ref_ci"]},
        "uji_urutan_berjelaga": {"urutan_terbitan_L_SP_turun": PUB_RANK, "pasangan": rank_test,
                                 "P_urutan_penuh_bertahan": round(full_order / full_n, 3) if full_n else None,
                                 "n_boot_semua_bb_ada": full_n},
        "validasi": res,
        "korelasi_panjang": length_correlation(pts),
        "sisa_per_hari": dres, "sisa_terbesar": worst,
        "rentang_berlaku": domain(pts),
        "tabel_psi_vs_titik_asap": {
            "penyalaan_titik_asap_ditemukan_di_tabel": f"{len(in_tab)}/{len(cross)}",
            "median_selisih_laju_relatif": round(float(np.median(rel)), 3) if rel else None,
            "n_selisih_gt_10pct": sum(1 for v in rel if v > 0.10),
            "mutu_tabel": quality},
    }
    (OUT / "spice_model.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "table_crosscheck.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tp", "day", "in_table", "n_rows", "sp_mdot_hc", "table_nearest_mdot_hc",
                                          "rel_diff"])
        w.writeheader()
        w.writerows(cross)
    figure(pts, preds["hybrid"], beta, OUT / "spice_smoke_points.png")
    print(json.dumps({k2: out[k2] for k2 in ("n_titik_asap", "hari", "eksponen", "L_SP_rujukan",
                                             "uji_urutan_berjelaga", "korelasi_panjang", "tabel_psi_vs_titik_asap")},
                     ensure_ascii=False, indent=1))
    for kind, r in res.items():
        print(f"{kind:7s} per-hari {r['per_hari']}  |  acak {r['acak_5lipat']['rmse_ln']}")
    print("sisa per hari:", dres)
    print("sisa terbesar:", worst)


if __name__ == "__main__":
    main()
