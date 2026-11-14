#!/usr/bin/env python3
"""Peta batas mudah-terbakar + rekomendasi uji ISS berikutnya (active learning).

Ide: Schmidt (ed.), Machine Learning in Modeling and Simulation, bab 9.4 —
batas "aman/gagal" (limit-state surface) dipelajari dengan proses Gaussian, lalu
fungsi-U  U(x) = |mu(x)| / sigma(x)  menunjuk titik yang paling mungkin salah
diklasifikasi. Titik dengan U terkecil = uji berikutnya yang paling informatif.

Di sini mu, sigma adalah rerata dan simpangan baku fungsi laten GP klasifikasi
(aproksimasi Laplace), sehingga P(menyala) = Phi-ish(mu) dan U = |mu|/sigma.

Dua batas:
  cfig_ign   ACME CFI-G: menyala atau tidak       (O2, fraksi bahan bakar, tekanan, aliran)
  flex_ext   FLEX: padam sebelum droplet habis    (O2, tekanan, He, CO2, diameter awal)

Kandidat uji = kondisi uji nyata yang digeser sedikit (~5% rentang). Sampel acak di seluruh
kotak kondisi gagal: GP kembali ke prior (mu~0, sigma besar) jauh dari data sehingga U~0
secara trivial, dan kombinasi yang tak pernah diuji (mis. CO2 + He sekaligus) ikut muncul.

  python scripts/ml_boundary.py   # -> analysis/ml/boundary/
"""
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy.linalg import cho_solve, solve
from sklearn.gaussian_process import GaussianProcessClassifier
from sklearn.gaussian_process.kernels import RBF, ConstantKernel
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ml_tabular  # noqa: E402  (pemuat data yang sama)

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "ml" / "boundary"
SEED = 7


class GPBoundary:
    """GP klasifikasi biner + akses ke rerata & varians laten (untuk fungsi-U)."""

    def __init__(self, cols):
        self.cols = cols

    def fit(self, X, y):
        Z = X[:, self.cols]
        self.sc = StandardScaler().fit(Z)
        k = ConstantKernel(1.0, (1e-2, 1e2)) * RBF(np.ones(len(self.cols)), (1e-2, 1e2))
        self.gp = GaussianProcessClassifier(k, n_restarts_optimizer=2, random_state=SEED)
        self.gp.fit(self.sc.transform(Z), y)
        return self

    def latent(self, X):
        """Rerata dan simpangan baku f(x) — rumus sama dengan predict_proba sklearn."""
        b = self.gp.base_estimator_
        Zs = self.sc.transform(X[:, self.cols])
        Ks = b.kernel_(b.X_train_, Zs)
        mu = Ks.T.dot(b.y_train_ - b.pi_)
        v = solve(b.L_, b.W_sr_[:, np.newaxis] * Ks)
        var = b.kernel_.diag(Zs) - np.einsum("ij,ij->j", v, v)
        return mu, np.sqrt(np.clip(var, 1e-12, None))

    def proba(self, X):
        return self.gp.predict_proba(self.sc.transform(X[:, self.cols]))[:, 1]


def near_tested(S, dims, mult_dims, rng, n=3000, frac=0.05):
    """Kandidat = kondisi uji nyata yang digeser sedikit. Dimensi di mult_dims (diluen)
    digeser secara relatif, jadi nilai nol tetap nol (kombinasi yang tak pernah diuji
    tidak muncul)."""
    lo, hi = S.min(0), S.max(0)
    C = S[rng.integers(len(S), size=n)].copy()
    for j in dims:
        if j in mult_dims:
            C[:, j] *= 1 + frac * 2 * rng.standard_normal(n)
        else:
            C[:, j] += frac * (hi[j] - lo[j]) * rng.standard_normal(n)
        C[:, j] = np.clip(C[:, j], lo[j], hi[j])
    return C


def cv(d, cols):
    """Validasi per-hari: GP batas vs logistik pada fitur yang sama."""
    X, y, g = d["X"], d["y"], d["g"]
    p_gp, p_lr = np.zeros(len(y)), np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, g):
        m = GPBoundary(cols).fit(X[tr], y[tr])
        p_gp[te] = m.proba(X[te])
        sc = StandardScaler().fit(X[tr][:, cols])
        lr = LogisticRegression(max_iter=2000).fit(sc.transform(X[tr][:, cols]), y[tr])
        p_lr[te] = lr.predict_proba(sc.transform(X[te][:, cols]))[:, 1]
    f = lambda p: {"auc": round(float(roc_auc_score(y, p)), 3),
                   "brier": round(float(brier_score_loss(y, p)), 4),
                   "acc": round(float(np.mean((p > 0.5) == y)), 3)}
    return {"gp": f(p_gp), "logistik": f(p_lr), "mayoritas_brier": round(float(y.mean() * (1 - y.mean())), 4)}


def impute(X):
    X = X.copy()
    med = np.nanmedian(X, axis=0)
    i = np.where(np.isnan(X))
    X[i] = np.take(med, i[1])
    return X


def run_cfig(sets):
    d = sets["cfig_ign"]
    d["X"] = impute(d["X"])
    names = d["names"]
    # fitur yang bisa diatur operator: konfigurasi, bahan bakar, O2, x_fuel, ln p, aliran bahan bakar
    cols = [names.index(c) for c in ("inverse", "propane", "butane", "o2", "x_fuel", "ln_p", "fuel_flow_mg_s")]
    res = {"what": d["what"], "features": [names[c] for c in cols], "cv_per_hari": cv(d, cols)}
    m = GPBoundary(cols).fit(d["X"], d["y"])
    X = d["X"]
    groups = []
    rng = np.random.default_rng(SEED)
    cands = []
    for inv in (0.0, 1.0):
        for fuel in ("ethane", "propane", "butane"):
            sel = (X[:, 0] == inv) & (X[:, 1] == (fuel == "propane")) & (X[:, 2] == (fuel == "butane"))
            if sel.sum() < 5:
                continue
            S = X[sel]
            lo, hi = S.min(0), S.max(0)
            med = np.median(S, 0)
            # peta 2D: O2 x x_fuel, tekanan & aliran di median grup
            o2 = np.linspace(lo[3], hi[3], 40)
            xf = np.linspace(lo[4], hi[4], 40)
            G = np.array([[*med[:3], a, b, med[5], *med[6:]] for b in xf for a in o2])
            G[:, 0], G[:, 1], G[:, 2] = inv, fuel == "propane", fuel == "butane"
            mu, sd = m.latent(G)
            p = m.proba(G)
            tested = [{"o2": float(r[3]), "x_fuel": float(r[4]), "ignited": int(yy)}
                      for r, yy in zip(S, d["y"][sel])]
            groups.append({"config": "inverse" if inv else "normal", "fuel": fuel, "n_tests": int(sel.sum()),
                           "o2": o2.round(4).tolist(), "x_fuel": xf.round(4).tolist(),
                           "p_ignite": p.reshape(40, 40).round(3).tolist(),
                           "sigma_latent": sd.reshape(40, 40).round(3).tolist(),
                           "pressure_kpa": round(float(math.exp(med[5]) * 101.325), 1),
                           "fuel_flow_mg_s": round(float(med[6]), 3), "tested": tested})
            # kandidat acak di dalam kotak kondisi teruji grup ini (semua dimensi kontrol)
            C = near_tested(S, (3, 4, 5, 6), (), rng)
            mu, sd = m.latent(C)
            U = np.abs(mu) / sd
            for i in np.argsort(U)[:60]:
                cands.append({"config": "inverse" if inv else "normal", "fuel": fuel,
                              "o2": round(float(C[i, 3]), 4), "x_fuel": round(float(C[i, 4]), 4),
                              "pressure_kpa": round(float(math.exp(C[i, 5]) * 101.325), 1),
                              "fuel_flow_mg_s": round(float(C[i, 6]), 3),
                              "p_ignite": round(float(m.proba(C[i:i + 1])[0]), 3),
                              "U": round(float(U[i]), 3), "sigma": round(float(sd[i]), 3)})
    res["maps"] = groups
    res["recommend"] = diverse(cands, ["o2", "x_fuel", "pressure_kpa", "fuel_flow_mg_s"], 12)
    return res


def run_flex(sets):
    d = sets["flex_ext"]
    names = d["names"]
    cols = list(range(len(names)))
    res = {"what": d["what"], "features": names, "cv_per_hari": cv(d, cols)}
    m = GPBoundary(cols).fit(d["X"], d["y"])
    X = d["X"]
    groups, cands = [], []
    rng = np.random.default_rng(SEED)
    for hep in (0.0, 1.0):
        fuel = "heptane" if hep else "methanol"
        sel = X[:, 0] == hep
        if sel.sum() < 5:
            continue
        S = X[sel]
        lo, hi, med = S.min(0), S.max(0), np.median(S, 0)
        o2 = np.linspace(lo[1], hi[1], 40)
        lp = np.linspace(lo[4], hi[4], 40)
        G = np.array([[hep, a, med[2], med[3], b, med[5]] for b in lp for a in o2])
        mu, sd = m.latent(G)
        groups.append({"fuel": fuel, "n_tests": int(sel.sum()), "o2": o2.round(4).tolist(),
                       "pressure_kpa": (np.exp(lp) * 101.325).round(1).tolist(),
                       "p_extinction": m.proba(G).reshape(40, 40).round(3).tolist(),
                       "sigma_latent": sd.reshape(40, 40).round(3).tolist(),
                       "x_co2": round(float(med[2]), 3), "x_he": round(float(med[3]), 3),
                       "d0_mm": round(float(med[5]), 2),
                       "tested": [{"o2": float(r[1]), "pressure_kpa": float(math.exp(r[4]) * 101.325),
                                   "extinction": int(yy)} for r, yy in zip(S, d["y"][sel])]})
        C = near_tested(S, (1, 2, 3, 4, 5), (2, 3), rng)
        mu, sd = m.latent(C)
        U = np.abs(mu) / sd
        for i in np.argsort(U)[:60]:
            cands.append({"fuel": fuel, "o2": round(float(C[i, 1]), 4), "x_co2": round(float(C[i, 2]), 3),
                          "x_he": round(float(C[i, 3]), 3),
                          "pressure_kpa": round(float(math.exp(C[i, 4]) * 101.325), 1),
                          "d0_mm": round(float(C[i, 5]), 2),
                          "p_extinction": round(float(m.proba(C[i:i + 1])[0]), 3),
                          "U": round(float(U[i]), 3), "sigma": round(float(sd[i]), 3)})
    res["maps"] = groups
    res["recommend"] = diverse(cands, ["o2", "x_co2", "x_he", "pressure_kpa", "d0_mm"], 12)
    return res


def diverse(cands, keys, k):
    """Pilih k kandidat ber-U kecil yang tidak saling berdekatan (greedy, jarak ternormalisasi)."""
    cands = sorted(cands, key=lambda c: c["U"])
    A = np.array([[c[x] for x in keys] for c in cands], float)
    span = A.max(0) - A.min(0)
    span[span == 0] = 1
    A = A / span
    pick = []
    for i in range(len(cands)):
        if all(np.linalg.norm(A[i] - A[j]) > 0.15 or cands[i].get("fuel") != cands[j].get("fuel")
               or cands[i].get("config") != cands[j].get("config") for j in pick):
            pick.append(i)
        if len(pick) == k:
            break
    return [cands[i] for i in pick]


def plot(res, key, zkey, xk, yk, dest):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    maps = res["maps"]
    fig, axes = plt.subplots(1, len(maps), figsize=(4.2 * len(maps), 3.8), squeeze=False)
    for ax, g in zip(axes[0], maps):
        P = np.array(g[zkey])
        S = np.array(g["sigma_latent"])
        cs = ax.contourf(g[xk], g[yk], P, levels=np.linspace(0, 1, 11), cmap="viridis")
        ax.contour(g[xk], g[yk], P, levels=[0.5], colors="white", linewidths=2)
        ax.contour(g[xk], g[yk], S, levels=3, colors="white", linewidths=0.6, linestyles=":")
        for t in g["tested"]:
            ax.scatter(t[xk], t[yk], s=14, marker="o" if list(t.values())[-1] else "x",
                       c="white" if list(t.values())[-1] else "red", edgecolors="black", linewidths=0.3)
        ax.set_title(f"{g.get('config', '')} {g['fuel']} (n={g['n_tests']})", fontsize=9)
        ax.set_xlabel(xk); ax.set_ylabel(yk)
    fig.colorbar(cs, ax=axes[0].tolist(), label=zkey)
    fig.savefig(dest, dpi=130, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sets = ml_tabular.load()
    out = {"cfig_ign": run_cfig(sets), "flex_ext": run_flex(sets)}
    for k, r in out.items():
        print(f"\n== {k}: validasi per-hari {r['cv_per_hari']}")
        print("   rekomendasi uji berikutnya (U kecil = paling tidak pasti):")
        for c in r["recommend"][:8]:
            print("    ", c)
    (OUT / "boundary.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    plot(out["cfig_ign"], "cfig", "p_ignite", "o2", "x_fuel", OUT / "cfig_ignition_map.png")
    plot(out["flex_ext"], "flex", "p_extinction", "o2", "pressure_kpa", OUT / "flex_extinction_map.png")
    print("Ditulis:", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
