#!/usr/bin/env python3
"""Process corridor untuk telemetri ACME (Neuer, Machine Learning for Engineers, bab 6.5).

Untuk tiap kelompok uji (investigasi x konfigurasi x menyala/tidak) dan tiap kanal,
dibangun pita probabilitas P(x | t): kuantil 5/25/50/75/95 % per langkah waktu, dari
uji-uji dalam kelompok itu. Waktu diselaraskan ke SAAT MENYALA (t_ignite dari
telemetry_mine) untuk uji yang menyala, dan ke awal rekaman untuk yang tidak.

Skor anomali tiap uji = rata-rata |z| robust terhadap pita kelompoknya sendiri,
dihitung LEAVE-ONE-OUT (pita dibangun tanpa uji itu), pada kanal sinyal api.
Uji dengan skor tinggi = kurvanya keluar dari koridor normal -> periksa manual.

Satuan tetap TEGANGAN MENTAH (lihat analysis/telemetry/README.md).

  python scripts/telemetry_corridor.py   # -> analysis/telemetry/corridor/
"""
import csv
import json
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "telemetry" / "corridor"
HZ = 4
warnings.filterwarnings("ignore", category=RuntimeWarning)
PRE, POST = 8, 72                  # detik sebelum & sesudah titik selaras
CH_SHOW = ["TCBurner", "PMT1", "PMT2", "IonCurrent", "PTA2", "MFCA3FuelFlow"]
CH_SCORE = ["TCBurner", "PMT1", "PMT2", "PTA2"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    d = np.load(ROOT / "analysis" / "ml" / "telemetry_tensors.npz", allow_pickle=False)
    X, mask = d["X"], d["mask"]
    ch = list(d["channels"])
    tel = {(r["accession"], r["test_point"]): r for r in
           csv.DictReader(open(ROOT / "analysis" / "telemetry" / "telemetry_joined.csv", encoding="utf-8"))}
    acc, tp = d["accession"], d["test_point"]
    n, L = len(acc), X.shape[2]
    W = (PRE + POST) * HZ
    A = np.full((n, len(ch), W), np.nan, np.float32)
    meta = []
    for i in range(n):
        r = tel.get((acc[i], tp[i]), {})
        ign = r.get("ignited_tel") == "ya"
        t0 = float(r["t_ignite_s"]) if ign and r.get("t_ignite_s") not in (None, "", "nan") else PRE
        s = int(round((t0 - PRE) * HZ))
        for k in range(W):
            j = s + k
            if 0 <= j < L and mask[i, j] > 0:
                A[i, :, k] = X[i, :, j]
        conf = (r.get("configuration") or "").split(" ")[0] or "?"
        meta.append({"accession": str(acc[i]), "test_point": str(tp[i]), "config": conf, "config_inferred": False,
                     "ignited": "ya" if ign else "tidak", "t_align_s": round(t0, 2),
                     "tc_rise_v": r.get("tc_burner_rise_v", ""), "match": r.get("match", "")})
    # uji tanpa pasangan tabel: ambil konfigurasi dari uji sehari-seri (mis. 21106G8 <- 21106G7)
    known = {(m["accession"], m["test_point"][:6]): m["config"] for m in meta if m["config"] != "?"}
    for m in meta:
        if m["config"] == "?" and (m["accession"], m["test_point"][:6]) in known:
            m["config"] = known[(m["accession"], m["test_point"][:6])]
            m["config_inferred"] = True
    keys = sorted({(m["accession"], m["config"], m["ignited"]) for m in meta})
    t_axis = (np.arange(W) / HZ - PRE).round(2).tolist()
    bands, scores = {}, np.full(n, np.nan)
    sc_idx = [ch.index(c) for c in CH_SCORE]
    for key in keys:
        idx = np.array([i for i, m in enumerate(meta) if (m["accession"], m["config"], m["ignited"]) == key])
        if len(idx) < 8:
            continue
        G = A[idx]
        q = np.nanpercentile(G, [5, 25, 50, 75, 95], axis=0)       # (5, C, W)
        name = f"{key[0]}|{key[1]}|{key[2]}"
        bands[name] = {"n": int(len(idx)),
                       "channels": {c: q[:, ch.index(c), :].round(5).tolist() for c in CH_SHOW}}
        # skor leave-one-out
        for a, i in enumerate(idx):
            rest = np.delete(G, a, axis=0)
            med = np.nanmedian(rest[:, sc_idx], axis=0)
            iqr = (np.nanpercentile(rest[:, sc_idx], 75, axis=0) - np.nanpercentile(rest[:, sc_idx], 25, axis=0))
            scale = np.maximum(iqr / 1.349, 1e-6 + 0.05 * np.nanmax(np.abs(med), axis=1, keepdims=True))
            z = np.abs(A[i, sc_idx] - med) / scale
            scores[i] = float(np.nanmean(np.clip(z, 0, 20)))
            meta[i]["group"] = name
    for i, m in enumerate(meta):
        m["anomaly"] = None if np.isnan(scores[i]) else round(float(scores[i]), 3)
    ranked = sorted([m for m in meta if m["anomaly"] is not None], key=lambda m: -m["anomaly"])
    # ambang: di atas p95 skor dalam kelompoknya
    by_g = {}
    for m in ranked:
        by_g.setdefault(m["group"], []).append(m["anomaly"])
    thr = {g: float(np.percentile(v, 95)) for g, v in by_g.items()}
    for m in ranked:
        m["outlier"] = m["anomaly"] > thr[m["group"]]
    with open(OUT / "anomaly_scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ranked[0].keys()))
        w.writeheader(); w.writerows(ranked)
    (OUT / "corridors.json").write_text(json.dumps({"t_s": t_axis, "units": "V (mentah, belum terkalibrasi)",
                                                    "align": "t=0 saat menyala (uji menyala) / awal rekaman+8 s",
                                                    "groups": bands}), encoding="utf-8")
    print(f"{len(bands)} koridor, {len(ranked)} uji berskor, {sum(m['outlier'] for m in ranked)} di atas p95 kelompok")
    print("10 teratas:")
    for m in ranked[:10]:
        print(f"  {m['accession']:8s} {m['test_point']:9s} {m['group']:28s} skor {m['anomaly']:.2f} match={m['match']}")
    for t in ("21106G8", "21106G7", "21106G9"):
        m = next((x for x in meta if x["test_point"] == t), None)
        if m:
            g = by_g.get(m.get("group"), [])
            pct = 100 * np.mean(np.array(g) <= (m["anomaly"] or 0)) if g else float("nan")
            print(f"  cek {t}: skor {m['anomaly']} (persentil {pct:.0f} di {m.get('group')})")
    plot(A, meta, ch, t_axis, bands, ranked)
    return 0


def plot(A, meta, ch, t_axis, bands, ranked):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return
    show = [m for m in ranked if m["outlier"]][:4]
    fig, axes = plt.subplots(len(show), 3, figsize=(13, 2.6 * len(show)), squeeze=False)
    for row, m in zip(axes, show):
        b = bands[m["group"]]["channels"]
        i = next(k for k, x in enumerate(meta) if x is m)
        for ax, c in zip(row, ("TCBurner", "PMT1", "PTA2")):
            q = np.array(b[c])
            ax.fill_between(t_axis, q[0], q[4], color="#9ecae1", alpha=0.6, label="5–95%")
            ax.fill_between(t_axis, q[1], q[3], color="#3182bd", alpha=0.6, label="25–75%")
            ax.plot(t_axis, q[2], color="#08519c", lw=1)
            ax.plot(t_axis, A[i, ch.index(c)], color="#d6604d", lw=1.2, label=m["test_point"])
            ax.set_title(f"{m['test_point']} · {c} · skor {m['anomaly']:.1f}", fontsize=8)
            ax.tick_params(labelsize=7)
        row[0].legend(fontsize=6)
    fig.tight_layout()
    fig.savefig(OUT / "top_anomalies.png", dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
