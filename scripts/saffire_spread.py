#!/usr/bin/env python3
"""Laju rambat api skala besar dari citra Saffire (PSI-98 Saffire-I, PSI-100 Saffire-III).

Data: deret citra yang SUDAH DIPETAKAN NASA ("Mapped": distorsi lensa diluruskan). Kamera
bergantian merekam dua jenis frame:
  - frame gelap  : hanya nyala yang tampak  -> posisi UJUNG API (profil kanal merah per kolom)
  - frame terang : sampel disinari dari belakang -> FRONT HANGUS (kain utuh hijau terang,
                   bagian terbakar gelap; median per baris dari titik kanal hijau jatuh)
Dua front ini diukur terpisah, jadi lajunya bisa dibandingkan satu sama lain.

Skala, dua cara:
  - Saffire-I: gambar 'Distortion Grid 30mmBlock' yang juga sudah dipetakan. Satu periode pola
    papan catur = 60 mm (satu blok terang + satu gelap); periode dicari dari puncak spektrum
    FFT, dan ditolak bila skala arah x dan y berbeda lebih dari 5 %. (Autokorelasi sempat
    dipakai dan gagal: ia memilih kelipatan periode, x 6,58 vs y 3,47 px/mm.)
  - Saffire-III (tidak ada gambar grid): tinggi bidang sampel yang terang pada frame awal
    = lebar sampel 406 mm (paper "Flame spread: Effects of microgravity and scale", hlm. 6).
    Diuji silang pada Saffire-I: cara ini memberi 40,4 cm terhadap skala grid (selisih 0,5 %).

Laju: regresi Theil-Sen posisi terhadap waktu pada fase rambat tunak (10-90 % lintasan),
selang 95 % dari bootstrap blok waktu (frame berurutan saling berkorelasi).
Gerbang mutu, BUTA terhadap angka publikasi: lolos bila residu RMS < 20 mm DAN lebar selang
95 % < 20 % laju. Yang gagal tetap dilaporkan dengan tanda, tidak dibuang.

Pembanding: paper yang sama, hlm. 13, mencatat 1,8 mm/s (Saffire-I, 20 cm/s) dan 2,3 mm/s
(Saffire-III, 25 cm/s). Angka itu TIDAK dipakai untuk memilih parameter mana pun; ia hanya
dibandingkan setelah hasil keluar.

Keterbatasan yang dilaporkan, tidak disembunyikan:
  - skala berlaku di bidang sampel; pemetaan NASA diasumsikan benar
  - status tier: derived_auto sampai lembar bukti diperiksa manusia

  python scripts/saffire_spread.py      # -> analysis/saffire/
"""
import csv
import glob
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / "kb" / "raw" / "psi" / "files"
OUT = ROOT / "analysis" / "saffire"
RNG = np.random.default_rng(7)

# Angka pembanding publikasi: "Flame spread: Effects of microgravity and scale" (papers_doi; hlm. 6 & 13):
# sampel Saffire-1/-3 = 94 x 40,6 cm; laju rambat concurrent 1,8 mm/s (20 cm/s, Saffire-1) dan 2,3 mm/s (25 cm/s, Saffire-3).
PUB = "Flame spread: Effects of microgravity and scale, hlm. 13"
SAMPLE_WIDTH_MM = 406.0   # sumber yang sama, hlm. 6
RUNS = [  # (id, investigasi, label, [pola zip frame terpetakan], skala, aliran cm/s, laju publikasi mm/s, langkah cuplik)
    ("saffire1_C1", "PSI-98", "Saffire-I, kamera 1", ["PSI-98_Raw Data_SAFFIRE_I_S1C1_Raw2TIFF_Mapped_JPEGS.zip"],
     ("grid", "PSI-98_Raw Data_Mapped_SAFFIRE-1_F1C1_DistortionGrid_1280x*.zip"), 20, 1.8, 1),
    ("saffire1_C2", "PSI-98", "Saffire-I, kamera 2", ["PSI-98_Raw Data_SAFFIRE_S1C2_RAW2TIFF_Mapped_JPEGS.zip"],
     ("grid", "PSI-98_Raw Data_Mapped_SAFFIRE-1_F1C2_DistortionGrid_1280x*.zip"), 20, 1.8, 1),
    ("saffire3_C1", "PSI-100", "Saffire-III, kamera 1",
     [f"PSI-100_Raw Data_SAFFIRE_III_S1C1_JPEG_Mapped_part{k}.zip" for k in (1, 2, 3, 4)],
     ("sample_width", None), 25, 2.3, 8),
    ("saffire3_C2", "PSI-100", "Saffire-III, kamera 2",
     [f"PSI-100_Raw Data_SAFFIRE_III_S1C2_JPEG_Mapped_[Pp]art{k}.zip" for k in (1, 2, 3, 4)],
     ("sample_width", None), 25, 2.3, 8),
]


def find(acc, pat):
    hits = glob.glob(str(FILES / acc / "*" / pat))
    return Path(hits[0]) if hits else None


def frames(zpaths, step=1):
    """Gabungan frame dari satu atau beberapa zip, diurutkan menurut cap epoch (ms) di nama berkas."""
    items = []
    for zp in zpaths:
        z = zipfile.ZipFile(zp)
        for n in z.namelist():
            m = re.search(r"(\d{13})", n)
            if m and re.search(r"\.(jpe?g)$", n, re.I):
                items.append((int(m.group(1)), z, n))
    items.sort(key=lambda x: x[0])
    items = items[::step]
    ts = np.array([x[0] for x in items], dtype=np.int64)
    return [(x[1], x[2]) for x in items], (ts - ts[0]) / 1000.0, int(ts[0])


def load(z, name):
    return np.asarray(Image.open(io.BytesIO(z.read(name))).convert("RGB")).astype(np.float32)


def grid_scale(zpath):
    """px per mm dari papan catur 30 mm: periode autokorelasi profil hijau = 60 mm."""
    z = zipfile.ZipFile(zpath)
    name = next(n for n in z.namelist() if n.lower().endswith(".jpg") and "mono" not in n.lower())
    g = np.asarray(Image.open(io.BytesIO(z.read(name))).convert("RGB")).astype(np.float32)[..., 1]
    H, W = g.shape
    out = {}
    for axis, prof in (("x", g[int(H * 0.35):int(H * 0.65), int(W * 0.1):int(W * 0.9)].mean(0)),
                       ("y", g[int(H * 0.15):int(H * 0.85), int(W * 0.35):int(W * 0.65)].mean(1))):
        # Puncak spektrum Fourier = periode dasar pola (satu blok terang + satu gelap = 60 mm).
        # (Versi pertama memakai puncak autokorelasi dan menangkap KELIPATAN periode: x 6,58 vs y 3,47 px/mm.)
        p = (prof - prof.mean()) * np.hanning(len(prof))
        spec = np.abs(np.fft.rfft(p, n=8 * len(p)))
        freq = np.fft.rfftfreq(8 * len(p))
        ok = (freq > 1 / 400) & (freq < 1 / 30)             # periode 30..400 px
        f0 = freq[ok][np.argmax(spec[ok])]
        out[axis] = (1 / f0) / 60.0
    out["xy_rel_diff"] = abs(out["x"] - out["y"]) / out["x"]
    if out["xy_rel_diff"] > 0.05:
        raise ValueError(f"skala x dan y tidak sepakat ({out['x']:.3f} vs {out['y']:.3f} px/mm)")
    return out, (W, H), name


def width_scale(fr, lit_idx):
    """px per mm dari tinggi bidang sampel yang terang pada frame terang awal (kain hampir utuh) = 406 mm.
    Pada Saffire-I cara ini memberi 40,4 cm terhadap skala grid (selisih 0,5 %)."""
    hs = []
    for i in lit_idx[:15]:
        g = load(*fr[i])[..., 1]
        W = g.shape[1]
        col = g[:, int(W * 0.2):int(W * 0.45)].mean(1)
        on = np.where(col > 0.5 * np.percentile(col, 98))[0]
        if len(on):
            hs.append(on.max() - on.min())
    h = float(np.median(hs))
    return {"x": h / SAMPLE_WIDTH_MM, "y": h / SAMPLE_WIDTH_MM, "sample_height_px": h}


def measure(run):
    rid, acc, label, zpats, (scale_kind, gpat), flow, pub, step = run
    zps = [find(acc, zp) for zp in zpats]
    if not all(zps):
        return None, f"berkas tidak ada: {[zp for zp, ok in zip(zpats, zps) if not ok]}"
    fr, t, t0 = frames(zps, step)
    names = [n for _, n in fr]
    first = load(*fr[0])
    if scale_kind == "grid":
        gp = find(acc, gpat)
        scale, gsize, gname = grid_scale(gp)
        if (first.shape[1], first.shape[0]) != tuple(gsize):
            return None, f"ukuran frame {first.shape[1]}x{first.shape[0]} beda dengan grid {gsize}"
        scale_src = f"grid 30 mm ({gname})"
    else:
        lit_idx = [i for i in range(0, len(fr), max(1, len(fr) // 400)) if load(*fr[i])[..., 1].mean() > 15]
        scale = width_scale(fr, lit_idx)
        scale_src = "lebar sampel 406 mm (" + PUB.split(",")[0] + ", hlm. 6)"
    pxmm = scale["x"]
    ref_hi = [None]                                        # kecerahan kain utuh (frame terang pertama)
    rows = []
    lit_examples, dark_examples = [], []
    for i, (z, n) in enumerate(fr):
        a = load(z, n)
        G, R, B = a[..., 1], a[..., 0], a[..., 2]
        lit = G.mean() > 15
        rec = {"i": i, "t_s": round(float(t[i]), 3), "lit": int(lit), "flame_x_px": "", "flame_centroid_px": "",
               "char_x_px": "", "frame": n, "zip": Path(z.filename).name}
        H, W = G.shape
        band = slice(int(H * 0.25), int(H * 0.75))
        if lit:
            # front hangus per baris: kolom terakhir (dari kiri) yang masih terang.
            # Ambang MUTLAK dari frame terang pertama (kain masih utuh). Ambang per-frame (versi lama)
            # ikut turun saat kain sudah habis terbakar dan menangkap tepi bingkai sebagai "front".
            g = G[band, :]
            if ref_hi[0] is None:
                ref_hi[0] = float(np.percentile(g, 95))
            thr = 0.5 * ref_hi[0]
            if (g > thr).mean() >= 0.02:                  # masih ada kain utuh; selain itu: sudah habis
                xs = []
                for row in g[::4]:
                    bright = np.where(row > thr)[0]
                    if len(bright) > 20:
                        xs.append(bright.max())
                if xs:
                    rec["char_x_px"] = round(float(np.median(xs)), 1)
            if len(lit_examples) < 40:
                lit_examples.append(i)
        else:
            # nyala oranye: R jauh di atas latar; profil per kolom pada pita tengah.
            # Frame terang yang redup (latar hijau) ditolak: nyala harus didominasi merah.
            fl = np.clip(R[band, :] - np.median(R) - 6, 0, None) * (R[band, :] > B[band, :] + 2)
            prof = fl.sum(0)
            mask = fl > 0
            red_dominant = mask.any() and R[band, :][mask].mean() > G[band, :][mask].mean()
            if prof.max() > 200 and red_dominant and np.median(G) < 8:
                cols = np.where(prof > 0.2 * prof.max())[0]
                rec["flame_x_px"] = int(cols.min())             # tepi kiri pita nyala
                rec["flame_centroid_px"] = round(float((prof * np.arange(W)).sum() / prof.sum()), 1)
                if len(dark_examples) < 40:
                    dark_examples.append(i)
        rows.append(rec)
    return {"id": rid, "acc": acc, "label": label, "zip": "; ".join(z.name for z in zps), "scale_source": scale_src,
            "flow_cm_s": flow, "published_mm_s": pub, "published_ref": PUB, "frame_step": step,
            "px_per_mm": scale, "n_frames": len(names), "duration_s": round(float(t[-1]), 1),
            "t0_epoch_ms": int(t0), "rows": rows}, None


def rate(t, x, pxmm):
    """Theil-Sen pada 10-90 % lintasan; bootstrap blok waktu (blok 10 titik) untuk selang 95 %."""
    t, x = np.asarray(t, float), np.asarray(x, float)
    if len(t) < 10:
        return None
    lo, hi = np.percentile(x, [10, 90])
    keep = (x >= min(lo, hi)) & (x <= max(lo, hi))
    t, x = t[keep], x[keep]
    if len(t) < 8:
        return None

    def ts(tt, xx):
        i, j = np.triu_indices(len(tt), 1)
        dt = tt[j] - tt[i]
        ok = dt > 0.5
        return np.median((xx[j] - xx[i])[ok] / dt[ok])
    s = ts(t, x)
    blocks = [np.arange(k, min(k + 10, len(t))) for k in range(0, len(t), 10)]
    bs = []
    for _ in range(400):
        idx = np.concatenate([blocks[k] for k in RNG.integers(0, len(blocks), len(blocks))])
        idx.sort()
        if len(np.unique(t[idx])) > 5:
            bs.append(ts(t[idx], x[idx]))
    lo_, hi_ = np.percentile(bs, [2.5, 97.5])
    mmps = lambda v: abs(v) / pxmm
    resid = x - (np.median(x - s * t) + s * t)
    ci = sorted([round(mmps(lo_), 3), round(mmps(hi_), 3)])
    rms = round(float(np.sqrt(np.mean(resid ** 2))) / pxmm, 2)
    # Gerbang mutu yang TIDAK melihat angka publikasi: lintasan harus lurus (residu kecil) dan
    # selang sempit. Front yang gagal tetap dilaporkan, tetapi tidak dipakai sebagai hasil.
    ok = rms < 20 and (ci[1] - ci[0]) < 0.2 * max(mmps(s), 1e-9)
    return {"mm_per_s": round(mmps(s), 3), "ci95_mm_per_s": ci,
            "direction": "kiri" if s < 0 else "kanan", "n": int(len(t)), "t_range_s": [round(t.min(), 1), round(t.max(), 1)],
            "resid_mm_rms": rms, "travel_mm": round(float(abs(x.max() - x.min())) / pxmm, 1),
            "quality": "lolos" if ok else "gagal gerbang mutu"}


def proof(res, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    rows = res["rows"]
    zmap = {Path(p).name: zipfile.ZipFile(p) for p in (find(res["acc"], zp) for zp in RUNS_BY_ID[res["id"]][3])}
    pick_d = [r for r in rows if r["flame_x_px"] != ""]
    pick_l = [r for r in rows if r["char_x_px"] != ""]
    sel = [pick_d[k] for k in np.linspace(0, len(pick_d) - 1, 4).astype(int)] + \
          [pick_l[k] for k in np.linspace(0, len(pick_l) - 1, 4).astype(int)] if pick_d and pick_l else []
    fig = plt.figure(figsize=(14, 8.5))
    for k, r in enumerate(sel):
        ax = fig.add_subplot(3, 4, k + 1)
        a = load(zmap[r["zip"]], r["frame"])
        if not r["lit"]:
            a = np.clip(a * 12, 0, 255)
        ax.imshow(a.astype(np.uint8))
        x = r["flame_x_px"] if r["flame_x_px"] != "" else r["char_x_px"]
        ax.axvline(x, color="#ffffff" if not r["lit"] else "#ff3366", lw=1.2)
        ax.set_title(f"t={r['t_s']:.0f} s · {'ujung api' if not r['lit'] else 'front hangus'}", fontsize=8)
        ax.axis("off")
    ax = fig.add_subplot(3, 1, 3)
    pxmm = res["px_per_mm"]["x"]
    td = [r["t_s"] for r in pick_d]; xd = [r["flame_x_px"] / pxmm / 10 for r in pick_d]
    tl = [r["t_s"] for r in pick_l]; xl = [r["char_x_px"] / pxmm / 10 for r in pick_l]
    ax.plot(td, xd, ".", ms=3, label="ujung api (frame gelap)")
    ax.plot(tl, xl, "s", ms=3, label="front hangus (frame terang)")
    ax.set_xlabel("waktu sejak frame pertama (s)"); ax.set_ylabel("posisi (cm, sumbu citra)")
    ax.legend(fontsize=8); ax.grid(alpha=.3)
    f, c = res.get("flame_rate"), res.get("char_rate")
    ax.set_title(f"{res['label']}: ujung api {f['mm_per_s'] if f else '?'} mm/s · front hangus "
                 f"{c['mm_per_s'] if c else '?'} mm/s · skala {pxmm:.3f} px/mm ({res['scale_source'].split(' (')[0]})", fontsize=9)
    fig.tight_layout(); fig.savefig(path, dpi=110); plt.close(fig)


RUNS_BY_ID = {r[0]: r for r in RUNS}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "traces").mkdir(exist_ok=True)
    (OUT / "proof").mkdir(exist_ok=True)
    summary = []
    for run in RUNS:
        res, err = measure(run)
        if err:
            print(run[0], "DILEWATI:", err)
            continue
        pxmm = res["px_per_mm"]["x"]
        d = [(r["t_s"], r["flame_x_px"]) for r in res["rows"] if r["flame_x_px"] != ""]
        l = [(r["t_s"], r["char_x_px"]) for r in res["rows"] if r["char_x_px"] != ""]
        res["flame_rate"] = rate(*zip(*d), pxmm) if len(d) > 10 else None
        res["char_rate"] = rate(*zip(*l), pxmm) if len(l) > 10 else None
        with open(OUT / "traces" / f"{res['id']}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(res["rows"][0].keys()))
            w.writeheader(); w.writerows(res["rows"])
        proof(res, OUT / "proof" / f"{res['id']}.png")
        s = {k: v for k, v in res.items() if k != "rows"}
        s.update(n_dark_with_flame=len(d), n_lit=len(l))
        if s.get("flame_rate"):
            s["flame_vs_published_pct"] = round(100 * (s["flame_rate"]["mm_per_s"] - s["published_mm_s"]) / s["published_mm_s"], 1)
        summary.append(s)
        print(json.dumps({k: s.get(k) for k in ("id", "scale_source", "px_per_mm", "n_frames", "duration_s",
                                                "n_dark_with_flame", "n_lit", "flame_rate", "char_rate",
                                                "published_mm_s", "flame_vs_published_pct")}, ensure_ascii=False))
    (OUT / "spread_rates.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    with open(OUT / "spread_rates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "investigasi", "label", "aliran_cm_s", "front", "mm_per_s", "ci95_lo", "ci95_hi", "n_frame",
                    "lintasan_mm", "resid_rms_mm", "mutu", "px_per_mm", "sumber_skala", "publikasi_mm_s", "selisih_pct", "zip"])
        for s in summary:
            for front, key in (("ujung api", "flame_rate"), ("front hangus", "char_rate")):
                r = s.get(key)
                if r:
                    w.writerow([s["id"], s["acc"], s["label"], s["flow_cm_s"], front, r["mm_per_s"], *r["ci95_mm_per_s"],
                                r["n"], r["travel_mm"], r["resid_mm_rms"], r["quality"], round(s["px_per_mm"]["x"], 4), s["scale_source"],
                                s["published_mm_s"], round(100 * (r["mm_per_s"] - s["published_mm_s"]) / s["published_mm_s"], 1),
                                s["zip"]])
    return 0


if __name__ == "__main__":
    sys.exit(main())
