#!/usr/bin/env python3
"""Ketidakpastian jujur untuk angka-angka utama dashboard.

Metode (Zuev, Fundamentals of Statistical Inference):
  - bootstrap (bab 6), tetapi CLUSTER bootstrap: yang di-resample adalah HARI UJI,
    bukan uji satu per satu. Uji sehari berbagi gas ruang & kalibrasi, jadi tidak
    independen; bootstrap per-uji akan memberi selang yang terlalu sempit.
  - uji permutasi (bab 10.4) untuk perbedaan antar-kelompok, plus selang bootstrap
    cluster untuk besarnya perbedaan.

Keluaran: analysis/stats/uq.json, analysis/stats/uq_report.md
  python scripts/stats_uq.py
"""
import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ml_tabular  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "stats"
B = 4000
rng = np.random.default_rng(7)


def cluster_boot(vals, groups, stat=np.mean, B=B):
    vals, groups = np.asarray(vals, float), np.asarray(groups)
    ug = np.unique(groups)
    idx = {g: np.where(groups == g)[0] for g in ug}
    est = float(stat(vals))
    bs = []
    for _ in range(B):
        pick = rng.choice(ug, len(ug), replace=True)
        bs.append(stat(vals[np.concatenate([idx[g] for g in pick])]))
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return {"est": round(est, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "n": int(len(vals)), "days": int(len(ug))}


def naive_boot(vals, stat=np.mean):
    vals = np.asarray(vals, float)
    bs = [stat(rng.choice(vals, len(vals))) for _ in range(B)]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def perm_test(a, b, stat=np.mean, B=B):
    a, b = np.asarray(a, float), np.asarray(b, float)
    obs = stat(a) - stat(b)
    pool = np.concatenate([a, b])
    cnt = 0
    for _ in range(B):
        p = rng.permutation(pool)
        cnt += abs(stat(p[:len(a)]) - stat(p[len(a):])) >= abs(obs)
    return round(float(obs), 4), round((cnt + 1) / (B + 1), 4)


def diff_boot(a, ga, b, gb, stat=np.mean):
    """Selang bootstrap cluster untuk stat(a) - stat(b), resample hari di tiap kelompok."""
    a, b, ga, gb = map(np.asarray, (a, b, ga, gb))
    ua, ub = np.unique(ga), np.unique(gb)
    ia = {g: np.where(ga == g)[0] for g in ua}
    ib = {g: np.where(gb == g)[0] for g in ub}
    bs = []
    for _ in range(B):
        pa = np.concatenate([ia[g] for g in rng.choice(ua, len(ua))])
        pb = np.concatenate([ib[g] for g in rng.choice(ub, len(ub))])
        bs.append(stat(a[pa].astype(float)) - stat(b[pb].astype(float)))
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return [round(float(lo), 4), round(float(hi), 4)]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sets = ml_tabular.load()
    res, rep = {}, ["# Ketidakpastian angka utama", "",
                    "Selang 95 % dari **bootstrap cluster per hari uji** (4000 ulangan). Kolom "
                    "'naif' = bootstrap per uji, ditampilkan untuk menunjukkan seberapa terlalu "
                    "sempit selang bila korelasi antar-uji sehari diabaikan.", ""]

    # ---- CFI-G: laju menyala per konfigurasi x bahan bakar
    d = sets["cfig_ign"]
    X, y, g = d["X"], d["y"], d["g"]
    fuel = np.where(X[:, 1] == 1, "propane", np.where(X[:, 2] == 1, "butane", "ethane"))
    conf = np.where(X[:, 0] == 1, "inverse", "normal")
    rep += ["## CFI-G: peluang menyala", "", "| Kelompok | n | hari | laju | CI95 cluster | CI95 naif |", "|---|---|---|---|---|---|"]
    res["cfig_ign_rate"] = {}
    for c in ("normal", "inverse"):
        for f in ("ethane", "propane", "butane"):
            m = (conf == c) & (fuel == f)
            if m.sum() < 5:
                continue
            r = cluster_boot(y[m], g[m]); r["ci95_naif"] = naive_boot(y[m])
            res["cfig_ign_rate"][f"{c}|{f}"] = r
            rep.append(f"| {c} {f} | {r['n']} | {r['days']} | {r['est']:.3f} | {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f} | {r['ci95_naif'][0]:.3f}–{r['ci95_naif'][1]:.3f} |")
    a, b = y[conf == "inverse"], y[conf == "normal"]
    obs, p = perm_test(a, b)
    ci = diff_boot(a, g[conf == "inverse"], b, g[conf == "normal"])
    res["cfig_inverse_minus_normal"] = {"diff": obs, "p_perm": p, "ci95_cluster": ci}
    rep += ["", f"Inverse − normal: selisih laju menyala {obs:+.3f}, p permutasi = {p}, "
            f"CI95 cluster [{ci[0]:+.3f}, {ci[1]:+.3f}].", "",
            "**Perhatikan:** uji permutasi biasa menganggap tiap uji independen sehingga p tampak sangat kecil, "
            "tetapi selang bootstrap per hari masih mencakup nol. Konfigurasi biasanya tetap sepanjang satu hari, "
            "jadi efektifnya hanya ada ~8 hari per kelompok. Kesimpulan yang jujur: inverse *cenderung* lebih mudah "
            "menyala, belum terbukti.", ""]

    # ---- CFI-G: padam sendiri
    d = sets["cfig_selfext"]
    conf = np.where(d["X"][:, 0] == 1, "inverse", "normal")
    rep += ["## CFI-G: peluang padam sendiri (setelah menyala)", "", "| Konfigurasi | n | hari | laju | CI95 cluster |", "|---|---|---|---|---|"]
    res["cfig_selfext_rate"] = {}
    for c in ("normal", "inverse"):
        m = conf == c
        r = cluster_boot(d["y"][m], d["g"][m]); res["cfig_selfext_rate"][c] = r
        rep.append(f"| {c} | {r['n']} | {r['days']} | {r['est']:.3f} | {r['ci95'][0]:.3f}–{r['ci95'][1]:.3f} |")
    rep.append("")

    # ---- FLEX: K
    d = sets["flex_K"]
    X, y, g = d["X"], d["y"], d["g"]
    hep = X[:, 0] == 1
    he = X[:, 3] > 0.01
    rep += ["## FLEX: laju bakar K (mm²/s)", "", "| Kelompok | n | hari | rerata K | CI95 cluster | CI95 naif |", "|---|---|---|---|---|---|"]
    res["flex_K"] = {}
    for name, m in (("heptana", hep), ("metanol", ~hep), ("heptana + He", hep & he), ("heptana tanpa He", hep & ~he)):
        if m.sum() < 5:
            continue
        r = cluster_boot(y[m], g[m]); r["ci95_naif"] = naive_boot(y[m]); res["flex_K"][name] = r
        rep.append(f"| {name} | {r['n']} | {r['days']} | {r['est']:.4f} | {r['ci95'][0]:.4f}–{r['ci95'][1]:.4f} | {r['ci95_naif'][0]:.4f}–{r['ci95_naif'][1]:.4f} |")
    obs, p = perm_test(y[hep], y[~hep]); ci = diff_boot(y[hep], g[hep], y[~hep], g[~hep])
    res["flex_K_heptane_minus_methanol"] = {"diff": obs, "p_perm": p, "ci95_cluster": ci}
    obs2, p2 = perm_test(y[hep & he], y[hep & ~he]); ci2 = diff_boot(y[hep & he], g[hep & he], y[hep & ~he], g[hep & ~he])
    res["flex_K_he_effect_heptane"] = {"diff": obs2, "p_perm": p2, "ci95_cluster": ci2}
    rep += ["", f"Heptana − metanol: {obs:+.4f} mm²/s, p = {p}, CI95 cluster [{ci[0]:+.4f}, {ci[1]:+.4f}].",
            f"Efek He (heptana): {obs2:+.4f} mm²/s, p = {p2}, CI95 cluster [{ci2[0]:+.4f}, {ci2[1]:+.4f}]. "
            "Catatan: He biasanya diuji bersama O₂ dan tekanan yang berbeda, jadi ini asosiasi, bukan efek sebab-akibat murni.", ""]

    # ---- telemetri: durasi bakar per investigasi
    tel = list(csv.DictReader(open(ROOT / "analysis" / "telemetry" / "telemetry_joined.csv", encoding="utf-8")))
    rep += ["## Telemetri ACME: durasi bakar (s, termokopel; cenderung berlebih karena jeda termal)", "",
            "| Investigasi | n | hari | median | CI95 cluster |", "|---|---|---|---|---|"]
    res["telemetry_burn_median"] = {}
    for a_ in ("PSI-10", "PSI-23", "PSI-159"):
        s = [t for t in tel if t["accession"] == a_ and t["ignited_tel"] == "ya" and t["burn_duration_s"] not in ("", "nan")]
        v = [float(t["burn_duration_s"]) for t in s]; gg = [t["test_point"][:5] for t in s]
        r = cluster_boot(v, gg, np.median); res["telemetry_burn_median"][a_] = r
        rep.append(f"| {a_} | {r['n']} | {r['days']} | {r['est']:.1f} | {r['ci95'][0]:.1f}–{r['ci95'][1]:.1f} |")
    rep.append("")

    # ---- video BASS (BELUM diverifikasi manusia bila measurements_verified.csv belum ada)
    vf = ROOT / "analysis" / "video_full"
    src = vf / "measurements_verified.csv"
    verified = src.exists()
    src = src if verified else vf / "measurements.csv"
    if src.exists():
        mv = [m for m in csv.DictReader(open(src, encoding="utf-8")) if m.get("burn_duration_s")]
        byf = defaultdict(list)
        for m in mv:
            byf[m.get("fuel") or "?"].append(m)
        rep += [f"## Video BASS: durasi nyala per episode (s) — {'TERVERIFIKASI' if verified else '**BELUM diverifikasi manusia**'}", "",
                "| Material | episode | uji | median | CI95 cluster per uji |", "|---|---|---|---|---|"]
        res["video_duration_median"] = {"verified": verified, "groups": {}}
        for f_, ms in sorted(byf.items(), key=lambda kv: -len(kv[1])):
            if len(ms) < 4 or f_ in ("?", ""):
                continue
            v = [float(m["burn_duration_s"]) for m in ms]; gg = [m["test_id"] for m in ms]
            r = cluster_boot(v, gg, np.median); res["video_duration_median"]["groups"][f_] = r
            rep.append(f"| {f_} | {r['n']} | {r['days']} | {r['est']:.1f} | {r['ci95'][0]:.1f}–{r['ci95'][1]:.1f} |")
        rep.append("")

    # ---- validasi corridor
    an = ROOT / "analysis" / "telemetry" / "corridor" / "anomaly_scores.csv"
    if an.exists():
        import sqlite3
        con = sqlite3.connect(ROOT / "kb" / "gold" / "freefall.sqlite")
        note = {t.replace(" ", "").lower(): (n or "") for t, n in
                con.execute("SELECT test_id, notes FROM tests WHERE accession='PSI-159'")}
        S = [r for r in csv.DictReader(open(an, encoding="utf-8")) if r["accession"] == "PSI-159" and r["test_point"].lower() in note]
        x = np.array([float(r["anomaly"]) for r in S]); h = np.array([bool(note[r["test_point"].lower()].strip()) for r in S])
        obs, p = perm_test(x[h], x[~h], np.median)
        res["corridor_vs_nasa_comments"] = {"n": len(S), "with_comment": int(h.sum()), "median_diff": obs, "p_perm": p}
        rep += ["## Validasi skor anomali koridor", "",
                f"Uji PSI-159 yang diberi komentar operator NASA (n = {int(h.sum())} dari {len(S)}) punya skor anomali "
                f"median lebih tinggi {obs:+.2f}; p permutasi = {p}. Skor dihitung tanpa pernah melihat komentar.", ""]

    (OUT / "uq.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    (OUT / "uq_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
    print("\n".join(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
