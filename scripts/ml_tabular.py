#!/usr/bin/env python3
"""Model ML lanjutan untuk tabel uji, dibandingkan jujur dengan model logistik/linear yang ada.

Target (sama dengan scripts/build_model.py, supaya bisa dibandingkan):
  cfig_ign      P(menyala)                         ACME CFI-G  (PSI-159)
  cfig_selfext  P(padam sendiri | menyala)         ACME CFI-G
  flex_ext      P(padam sebelum droplet habis)     FLEX        (PSI-69)
  flex_K        laju bakar K (mm^2/s), regresi     FLEX

Dua skema validasi:
  acak   : 5-lipat berstrata x 5 ulangan (sebanding dengan laporan lama)
  per-hari: GroupKFold menurut hari uji. Uji di hari yang sama berbagi gas
            ruang, kalibrasi, dan kru. Skema ini menjawab "seberapa baik untuk
            hari uji yang BELUM pernah dilihat" dan menjadi angka utama.

Fitur hanya kondisi yang DIRENCANAKAN. Kolom hasil (burn time, peak burner T,
warna, komentar) dan TFP (arti tidak terdokumentasi) sengaja tidak dipakai.

  python scripts/ml_tabular.py      # -> analysis/ml/tabular_report.md, tabular_results.json
"""
import csv
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
from sklearn.base import clone
from sklearn.ensemble import (ExtraTreesClassifier, ExtraTreesRegressor,
                              HistGradientBoostingClassifier, HistGradientBoostingRegressor,
                              RandomForestClassifier, RandomForestRegressor,
                              StackingClassifier, StackingRegressor)
from sklearn.gaussian_process import GaussianProcessClassifier, GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import GroupKFold, RepeatedStratifiedKFold, RepeatedKFold
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "ml"
P0 = 101.325
SEED = 7


def fnum(v):
    try:
        x = float(str(v).strip())
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ data
def load():
    T = list(csv.DictReader(open(ROOT / "kb" / "gold" / "tests.csv", encoding="utf-8")))
    sets = {}

    # ---- CFI-G
    rows = []
    for r in T:
        if r["accession"] != "PSI-159":
            continue
        j = json.loads(r["raw_json"])
        g = lambda *pre: next((fnum(v) for k, v in j.items()
                               if any(k.strip().lower().startswith(p) for p in pre)), None)
        fl = r["fuel"].lower()
        o2, p = fnum(r["o2_mole_frac"]), fnum(r["pressure_kpa"])
        xf = g("xf")
        if o2 is None or xf is None or not p:
            continue
        inv = 1.0 if "Inverse" in r["table_name"] else 0.0
        rows.append({
            "x": [inv, 1.0 if "propane" in fl else 0.0, 1.0 if "butane" in fl else 0.0,
                  o2, xf, math.log(p / P0),
                  g("mhc", "hc burnrate") or 0.0, g("o2 flow") or 0.0,
                  g("tad") or np.nan, g("zst") or np.nan],
            "day": r["test_id"].strip()[:5],   # kode hari GMT, mis. 21106
            "id": r["test_id"], "ign": r["ignited"], "out": r["outcome"]})
    fc = ["inverse", "propane", "butane", "o2", "x_fuel", "ln_p", "fuel_flow_mg_s",
          "o2_flow_mg_s", "Tad_K", "Zst"]
    base_c = [0, 1, 2, 3, 4, 5]          # fitur model lama
    I = [r for r in rows if r["ign"] in ("yes", "no")]
    sets["cfig_ign"] = dict(kind="clf", names=fc, base=base_c,
                            X=np.array([r["x"] for r in I]),
                            y=np.array([r["ign"] == "yes" for r in I], int),
                            g=np.array([r["day"] for r in I]), ids=[r["id"] for r in I],
                            what="P(menyala), ACME CFI-G")
    S = [r for r in rows if r["ign"] == "yes" and r["out"] in ("self-extinguished", "flow terminated")]
    sets["cfig_selfext"] = dict(kind="clf", names=fc, base=base_c,
                                X=np.array([r["x"] for r in S]),
                                y=np.array([r["out"] == "self-extinguished" for r in S], int),
                                g=np.array([r["day"] for r in S]), ids=[r["id"] for r in S],
                                what="P(padam sendiri | menyala), ACME CFI-G")

    # ---- FLEX
    fr = []
    for r in T:
        if r["accession"] != "PSI-69":
            continue
        j = json.loads(r["raw_json"])
        g = lambda pre: next((fnum(v) for k, v in j.items() if k.startswith(pre)), None)
        o2, p = fnum(r["o2_mole_frac"]), fnum(r["pressure_kpa"])
        if o2 is None or not p:
            continue
        fr.append({"x": [1.0 if r["fuel"] == "Heptane" else 0.0, o2, g("CO initial") or 0.0,
                         g("He initial") or 0.0, math.log(p / P0), fnum(r["size_mm"])],
                   "K": fnum(r["metric_value"]), "end": r["outcome"],
                   "day": (j.get("Test Date") or "").strip(), "id": r["test_id"]})
    ff = ["heptane", "o2", "x_co2", "x_he", "ln_p", "d0_mm"]
    E = [r for r in fr if r["end"] in ("Extinction", "Completion") and r["x"][5]]
    sets["flex_ext"] = dict(kind="clf", names=ff, base=list(range(6)),
                            X=np.array([r["x"] for r in E]),
                            y=np.array([r["end"] == "Extinction" for r in E], int),
                            g=np.array([r["day"] for r in E]), ids=[r["id"] for r in E],
                            what="P(padam sebelum droplet habis), FLEX")
    K = [r for r in fr if r["K"] is not None]
    sets["flex_K"] = dict(kind="reg", names=ff[:5], base=list(range(5)),
                          X=np.array([r["x"][:5] for r in K]),
                          y=np.array([r["K"] for r in K]),
                          g=np.array([r["day"] for r in K]), ids=[r["id"] for r in K],
                          what="laju bakar K (mm²/s), FLEX")
    return sets


# ------------------------------------------------------------------ model
class Cols:
    """Pilih subset kolom + isi NaN dengan median (fit di lipatan latih)."""
    def __init__(self, cols): self.cols = cols
    def fit(self, X, y=None):
        self.med_ = np.nanmedian(X[:, self.cols], axis=0)
        return self
    def transform(self, X):
        Z = X[:, self.cols].copy()
        idx = np.where(np.isnan(Z))
        Z[idx] = np.take(self.med_, idx[1])
        return Z
    def get_params(self, deep=True): return {"cols": self.cols}
    def set_params(self, **p): self.cols = p["cols"]; return self


def models(kind, n_feat, base):
    allc = list(range(n_feat))
    sc = lambda *s: make_pipeline(Cols(allc), StandardScaler(), *s)
    if kind == "clf":
        m = {
            "logistik (fitur lama)": make_pipeline(Cols(base), StandardScaler(),
                                                   LogisticRegression(C=1.0, max_iter=2000)),
            "logistik (fitur penuh)": sc(LogisticRegression(C=1.0, max_iter=2000)),
            "random forest": make_pipeline(Cols(allc), RandomForestClassifier(
                500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)),
            "extra trees": make_pipeline(Cols(allc), ExtraTreesClassifier(
                500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)),
            "gradient boosting": make_pipeline(Cols(allc), HistGradientBoostingClassifier(
                max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                min_samples_leaf=10, random_state=SEED)),
            "SVM RBF": sc(SVC(C=2.0, probability=True, random_state=SEED)),
            "proses Gaussian": sc(GaussianProcessClassifier(
                1.0 * RBF(np.ones(n_feat)), random_state=SEED)),
            "MLP (jaringan saraf)": sc(MLPClassifier(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=3000,
                                                     early_stopping=False, random_state=SEED)),
        }
        m["stacking"] = StackingClassifier(
            [(k, v) for k, v in m.items() if k in ("random forest", "gradient boosting",
                                                    "logistik (fitur penuh)")],   # tanpa GP: terlalu lambat
            final_estimator=LogisticRegression(C=1.0), cv=5, stack_method="predict_proba")
    else:
        k = ConstantKernel() * RBF(np.ones(n_feat)) + WhiteKernel()
        m = {
            "ridge (fitur lama)": make_pipeline(Cols(base), StandardScaler(), Ridge(1e-3)),
            "random forest": make_pipeline(Cols(allc), RandomForestRegressor(
                500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)),
            "extra trees": make_pipeline(Cols(allc), ExtraTreesRegressor(
                500, min_samples_leaf=3, random_state=SEED, n_jobs=-1)),
            "gradient boosting": make_pipeline(Cols(allc), HistGradientBoostingRegressor(
                max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0,
                min_samples_leaf=10, random_state=SEED)),
            "proses Gaussian": sc(GaussianProcessRegressor(k, normalize_y=True,
                                                           random_state=SEED)),
            "MLP (jaringan saraf)": sc(MLPRegressor(hidden_layer_sizes=(32, 16), alpha=1e-2, max_iter=5000,
                                                   random_state=SEED)),
        }
        m["stacking"] = StackingRegressor(
            [(k, v) for k, v in m.items() if k in ("random forest", "gradient boosting",
                                                    "ridge (fitur lama)")],
            final_estimator=Ridge(1.0), cv=5)
    return m


# ------------------------------------------------------------------ evaluasi
def splits(d, scheme):
    n = len(d["y"])
    if scheme == "acak":
        cv = (RepeatedStratifiedKFold(n_splits=5, n_repeats=5, random_state=SEED)
              if d["kind"] == "clf" else RepeatedKFold(n_splits=5, n_repeats=5, random_state=SEED))
        return list(cv.split(d["X"], d["y"])), 5
    k = min(5, len(set(d["g"])))
    return list(GroupKFold(n_splits=k).split(d["X"], d["y"], d["g"])), 1


def evaluate(model, d, scheme):
    X, y = d["X"], d["y"]
    sp, reps = splits(d, scheme)
    pred = np.zeros((reps, len(y)))
    for i, (tr, te) in enumerate(sp):
        m = clone(model).fit(X[tr], y[tr])
        r = i // (len(sp) // reps)
        pred[r, te] = m.predict_proba(X[te])[:, 1] if d["kind"] == "clf" else m.predict(X[te])
    out = []
    for p in pred:
        if d["kind"] == "clf":
            out.append([roc_auc_score(y, p), brier_score_loss(y, p), np.mean((p > 0.5) == y)])
        else:
            out.append([r2_score(y, p), math.sqrt(mean_squared_error(y, p))])
    a = np.array(out)
    return a.mean(0), a.std(0)


def ceiling(d):
    """Uji dengan kondisi IDENTIK tetapi hasil berbeda: batas bawah galat yang tak tereduksi."""
    if d["kind"] != "clf":
        return None
    key = {}
    for x, y in zip(d["X"], d["y"]):
        key.setdefault(tuple(np.round(np.nan_to_num(x), 6)), []).append(y)
    dup = [v for v in key.values() if len(v) > 1]
    mixed = [v for v in dup if len(set(v)) > 1]
    return {"kelompok_duplikat": len(dup), "kelompok_hasil_campur": len(mixed),
            "uji_dalam_kelompok_campur": sum(len(v) for v in mixed)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="satu target saja, mis. cfig_ign (untuk menjalankan paralel)")
    only = ap.parse_args().only
    OUT.mkdir(parents=True, exist_ok=True)
    sets = load()
    if only:
        sets = {only: sets[only]}
    tag = f"_{only}" if only else ""
    res = {}
    rep = ["# Model ML lanjutan — tabel uji", "",
           "Dibuat oleh `scripts/ml_tabular.py`. Pembanding: model lama di "
           "`kb/gold/model_report.md` (logistik/linear, fitur lama).", "",
           "**Angka utama = validasi per-hari** (GroupKFold menurut hari uji): model diuji pada hari "
           "yang tidak pernah dilihatnya. Validasi acak (5×5 lipat) disertakan untuk perbandingan "
           "dengan laporan lama, tetapi cenderung optimistis karena uji sehari mirip satu sama lain.",
           ""]
    for name, d in sets.items():
        n, nf = len(d["y"]), d["X"].shape[1]
        print(f"\n== {name}: n={n}, hari={len(set(d['g']))}", flush=True)
        res[name] = {"what": d["what"], "n": n, "days": len(set(d["g"])), "models": {}}
        rep += [f"## {name} — {d['what']}", "",
                f"n = {n} uji, {len(set(d['g']))} hari. "
                + (f"Laju positif {d['y'].mean():.3f}." if d["kind"] == "clf" else
                   f"Simpangan baku K = {d['y'].std():.4f}."), ""]
        if d["kind"] == "clf":
            rep += ["| Model | AUC per-hari | Brier per-hari | Akurasi per-hari | AUC acak | Brier acak |",
                    "|---|---|---|---|---|---|"]
            mj = d["y"].mean()
            rep.append(f"| *tebak mayoritas* | 0.500 | {mj*(1-mj):.4f} | {max(mj,1-mj):.3f} | 0.500 | {mj*(1-mj):.4f} |")
        else:
            rep += ["| Model | R² per-hari | RMSE per-hari | R² acak | RMSE acak |", "|---|---|---|---|---|"]
            rep.append(f"| *rata-rata saja* | ≤ 0 | {d['y'].std():.4f} | 0 | {d['y'].std():.4f} |")
        for mname, m in models(d["kind"], nf, d["base"]).items():
            g_m, g_s = evaluate(m, d, "per-hari")
            r_m, r_s = evaluate(m, d, "acak")
            res[name]["models"][mname] = {"per_hari": g_m.round(4).tolist(),
                                          "acak": r_m.round(4).tolist(), "acak_sd": r_s.round(4).tolist()}
            print(f"  {mname:24s} per-hari {np.round(g_m,3)}  acak {np.round(r_m,3)}", flush=True)
            if d["kind"] == "clf":
                rep.append(f"| {mname} | {g_m[0]:.3f} | {g_m[1]:.4f} | {g_m[2]:.3f} | "
                           f"{r_m[0]:.3f} ± {r_s[0]:.3f} | {r_m[1]:.4f} |")
            else:
                rep.append(f"| {mname} | {g_m[0]:.3f} | {g_m[1]:.4f} | {r_m[0]:.3f} ± {r_s[0]:.3f} | {r_m[1]:.4f} |")
        # pemenang menurut per-hari
        key = (lambda v: v["per_hari"][0])
        if d["kind"] == "clf":
            key = (lambda v: -v["per_hari"][1])   # Brier terkecil
        best = max(res[name]["models"].items(), key=lambda kv: key(kv[1]))[0]
        baseline = "logistik (fitur lama)" if d["kind"] == "clf" else "ridge (fitur lama)"
        res[name]["best"] = best
        rep += ["", f"Terbaik per-hari: **{best}**"
                + (" (Brier terkecil)." if d["kind"] == "clf" else " (R² tertinggi).")]
        c = ceiling(d)
        if c:
            res[name]["ceiling"] = c
            rep.append(f"Uji berkondisi identik: {c['kelompok_duplikat']} kelompok, "
                       f"{c['kelompok_hasil_campur']} di antaranya berhasil-campur "
                       f"({c['uji_dalam_kelompok_campur']} uji). Bagian ini tidak bisa "
                       "dijelaskan model apa pun dari kondisi yang direncanakan.")
        # kepentingan fitur (permutasi) pada model terbaik, dilatih penuh
        m = clone(models(d["kind"], nf, d["base"])[best]).fit(d["X"], d["y"])
        pi = permutation_importance(m, d["X"], d["y"], n_repeats=20, random_state=SEED,
                                    scoring="roc_auc" if d["kind"] == "clf" else "r2")
        order = np.argsort(-pi.importances_mean)
        res[name]["importance"] = {d["names"][i]: round(float(pi.importances_mean[i]), 4) for i in order}
        rep += ["", "Kepentingan fitur (permutasi, pada data latih, model terbaik): "
                + ", ".join(f"`{d['names'][i]}` {pi.importances_mean[i]:.3f}" for i in order[:6]), ""]
    (OUT / f"tabular_results{tag}.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / f"tabular_report{tag}.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\nDitulis:", OUT / "tabular_report.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
