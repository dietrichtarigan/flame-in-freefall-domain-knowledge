#!/usr/bin/env python3
"""Ekstrak jejak nyala api dari video eksperimen BASS / BASS-II (PSI-25, PSI-26).

Masalah yang dipecahkan: tabel uji BASS-II punya 129 baris TANPA satu pun kolom
hasil, dan hanya 2 dari 264 uji bahan padat di seluruh basis data yang punya laju
rambat. Angkanya ada di video. Skrip ini menarik sebagian ke bentuk terukur.

Yang diukur per video (per frame, pada fps sampel):
  - luas tampak nyala (piksel) dan intensitas puncaknya
  - sentroid nyala (kolom, baris) -> untuk laju rambat pada sampel datar
  - waktu nyala-pertama dan nyala-terakhir -> durasi pembakaran tampak

Yang TIDAK diklaim skrip ini:
  - Satuan fisis mutlak. Tanpa penanda skala di bidang pandang, luas tetap dalam
    piksel dan laju dalam piksel/detik. Konversi ke mm butuh kalibrasi manual
    (lihat --scale-mm-per-px) dari lebar sampel yang diketahui.
  - Bahwa setiap wilayah terang adalah api. Perangkat keras yang tersorot lampu
    dan layar kamera Nikon di sebagian video juga terang; penyaring kekompakan
    di bawah membuang sebagian besar, tetapi hasil WAJIB diperiksa lewat lembar
    bukti (--proof) sebelum dipakai.

Keluaran:
  analysis/video_pilot/traces/<test>.csv   jejak per frame
  analysis/video_pilot/summary.csv         satu baris per video
  analysis/video_pilot/proof/<test>.png    montase frame + kotak deteksi (--proof)

Butuh: ffmpeg di PATH, numpy, scipy. Tidak butuh OpenCV.

  python scripts/video_analyze.py --limit 8 --proof
  python scripts/video_analyze.py --video "<path.mp4>" --proof
"""
import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "video_pilot"
VID_DIRS = [ROOT / "kb/raw/psi/files/PSI-25/Raw Data",
            ROOT / "kb/raw/psi/files/PSI-26/Raw Data"]

W, H = 180, 120          # resolusi analisis (video asli 720x480)
OVERLAY_ROWS = 30        # baris teratas berisi overlay teks FUEL/AIR/FAN/RAD
FPS = 2.0                # frame per detik yang disampel
THRESH = 55              # ambang kecerahan (0-255); latar video ini ~0-12
GAP_S = 6.0              # jeda gelap >= ini memisahkan dua episode pembakaran
MIN_EPISODE_S = 3.0      # episode lebih pendek dari ini dianggap derau/kilatan
MIN_EPISODE_FRAMES = 5   # dan harus punya cukup frame terdeteksi, bukan 2 kilatan
# Gerbang adegan gelap. Rekaman nyala BASS selalu berlatar hitam (median frame = 0),
# sedangkan berkas "2ND_VIEW" ternyata bukan rekaman api sama sekali: itu kamera
# luar yang menyorot glovebox berikut astronotnya (median frame 84-93). Tanpa
# gerbang ini, pantulan terang di adegan tersorot terbaca sebagai "api" selama
# ratusan detik. Pengukuran hanya sah terhadap latar gelap.
# Nilai 8 dipilih dari sebaran terukur: frame nyala sejati bermedian 0, frame
# berlampu menyala bermedian 30 (interior duct) sampai 93 (kamera luar).
SCENE_MAX_MEDIAN = 8
MIN_AREA = 12            # blob lebih kecil dari ini = derau sensor
MAX_AREA_FRAC = 0.22     # blob lebih besar dari ini = lampu/layar, bukan api
MAX_EXTENT_FRAC = 0.75   # blob yang membentang >75% lebar frame = bukan api
# Saringan bentuk. Nyala mikrogravitasi padat dan membulat; dua pengganggu yang
# benar-benar muncul di rekaman ini tidak: (1) tepi sampel yang tersorot lampu
# membentuk garis sangat panjang-tipis, (2) sebagian video menyelipkan potret
# layar LCD kamera Nikon, yang kotak histogramnya adalah persegi BERONGGA.
MAX_ASPECT = 4.0         # rasio sisi bbox; garis tipis jauh melampaui ini
MIN_FILL = 0.45          # area / luas bbox; rangka berongga jatuh di bawah ini


def probe_duration(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return None


def read_gray(path, fps=FPS, w=W, h=H):
    """Seluruh video sebagai array (n, h, w) uint8 grayscale."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", f"fps={fps},scale={w}:{h},format=gray", "-f", "rawvideo", "pipe:1"],
        capture_output=True)
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    n = len(a) // (w * h)
    if n == 0:
        return None
    return a[:n * w * h].reshape(n, h, w)


def flame_in_frame(frame):
    """Blob api terbesar yang lolos saringan kekompakan.

    Mengembalikan dict atau None. Frame sudah dipotong overlay-nya.
    """
    mask = frame > THRESH
    if not mask.any():
        return None
    lab, n = ndimage.label(mask)
    if n == 0:
        return None
    areas = ndimage.sum(mask, lab, range(1, n + 1))
    total_px = frame.size
    best = None
    for i in np.argsort(areas)[::-1]:
        area = areas[i]
        if area < MIN_AREA:
            break                      # sisanya lebih kecil lagi
        if area > MAX_AREA_FRAC * total_px:
            continue                   # terlalu besar: lampu / layar kamera
        ys, xs = np.where(lab == i + 1)
        wspan = xs.max() - xs.min() + 1
        hspan = ys.max() - ys.min() + 1
        if wspan > MAX_EXTENT_FRAC * frame.shape[1]:
            continue                   # membentang selebar frame: bukan api
        if hspan > MAX_EXTENT_FRAC * frame.shape[0]:
            continue
        if max(wspan / hspan, hspan / wspan) > MAX_ASPECT:
            continue                   # garis panjang-tipis: tepi sampel tersorot
        if area / (wspan * hspan) < MIN_FILL:
            continue                   # berongga: rangka kotak layar kamera
        best = {"area_px": int(area),
                "cx": float(xs.mean()), "cy": float(ys.mean()),
                "x0": int(xs.min()), "x1": int(xs.max()),
                "y0": int(ys.min()), "y1": int(ys.max()),
                "peak": int(frame[ys, xs].max())}
        break
    return best


def analyze(path, fps=FPS):
    vid = read_gray(path, fps)
    if vid is None:
        return None, []
    body = vid[:, OVERLAY_ROWS:, :]
    rows = []
    for i, frame in enumerate(body):
        lit = float(np.median(frame)) > SCENE_MAX_MEDIAN
        f = None if lit else flame_in_frame(frame)
        rows.append({"t_s": round(i / fps, 2), "scene_lit": int(lit),
                     "area_px": f["area_px"] if f else 0,
                     "peak": f["peak"] if f else int(frame.max()),
                     "cx_px": round(f["cx"], 2) if f else "",
                     "cy_px": round(f["cy"], 2) if f else "",
                     "x0": f["x0"] if f else "", "x1": f["x1"] if f else "",
                     "y0": f["y0"] if f else "", "y1": f["y1"] if f else ""})
    return body, rows


def episodes_of(rows, fps=FPS):
    """Pisahkan jejak menjadi episode pembakaran.

    Satu video kerap memuat beberapa segmen uji (mis. BASS-II P1: aliran udara
    disetel 5 lalu 2, dipisah jeda gelap). Menggabungkannya jadi satu jendela
    akan melaporkan 'satu pembakaran panjang' yang tidak pernah terjadi, maka
    setiap rentang gelap >= GAP_S memulai episode baru.
    """
    live = [i for i, r in enumerate(rows) if r["area_px"] > 0]
    if not live:
        return []
    gap = max(1, int(round(GAP_S * fps)))
    runs, start, prev = [], live[0], live[0]
    for i in live[1:]:
        if i - prev > gap:
            runs.append((start, prev))
            start = i
        prev = i
    runs.append((start, prev))

    eps = []
    for a, b in runs:
        dur = (b - a) / fps
        seg = [rows[i] for i in range(a, b + 1) if rows[i]["area_px"] > 0]
        if dur < MIN_EPISODE_S or len(seg) < MIN_EPISODE_FRAMES:
            continue                      # kilatan / derau, bukan pembakaran
        areas = [r["area_px"] for r in seg]
        cxs = [r["cx_px"] for r in seg if r["cx_px"] != ""]
        # Cara episode berakhir: 3 frame terdeteksi terakhir dibandingkan puncaknya.
        # Membedakan padam bertahap (nyala mengerut dulu, khas batas padam) dari
        # pemutusan mendadak (aliran dihentikan / rekaman terpotong). Memakai
        # jumlah frame tetap, bukan proporsi durasi, karena pengerutan menjelang
        # padam berlangsung pada skala waktu mutlak beberapa detik -- jendela
        # proporsional pada episode panjang ikut merata-ratakan fase stabilnya.
        tail_frac = float(np.mean(areas[-3:]) / max(areas))
        ending = ("padam bertahap" if tail_frac < 0.4
                  else "berakhir mendadak" if tail_frac > 0.6
                  else "peralihan")
        eps.append({"t_start_s": round(a / fps, 2), "t_end_s": round(b / fps, 2),
                    "duration_s": round(dur, 2), "n_frames": len(seg),
                    "area_max_px": int(max(areas)),
                    "area_median_px": int(np.median(areas)),
                    "area_first_px": int(areas[0]), "area_last_px": int(areas[-1]),
                    "tail_frac_of_peak": round(tail_frac, 3), "ending": ending,
                    "drift_px": round(max(cxs) - min(cxs), 2) if len(cxs) > 1 else "",
                    "drift_px_per_s": round((max(cxs) - min(cxs)) / dur, 3)
                    if len(cxs) > 1 and dur > 0 else ""})
    return eps


def summarize(rows, fps=FPS):
    eps = episodes_of(rows, fps)
    n_live = sum(1 for r in rows if r["area_px"] > 0)
    lit_frac = round(sum(r["scene_lit"] for r in rows) / max(1, len(rows)), 3)
    # Mayoritas frame tersorot = ini bukan rekaman nyala (kamera luar glovebox).
    kind = "adegan tersorot (bukan rekaman nyala)" if lit_frac > 0.5 else "latar gelap"
    if not eps:
        return {"n_frames": len(rows), "scene": kind, "lit_frac": lit_frac,
                "n_flame_frames": n_live, "n_episodes": 0,
                "t_first_s": "", "t_last_s": "", "total_burn_s": "",
                "longest_episode_s": "", "area_max_px": 0}
    return {"n_frames": len(rows), "scene": kind, "lit_frac": lit_frac,
            "n_flame_frames": n_live, "n_episodes": len(eps),
            "t_first_s": eps[0]["t_start_s"], "t_last_s": eps[-1]["t_end_s"],
            "total_burn_s": round(sum(e["duration_s"] for e in eps), 2),
            "longest_episode_s": round(max(e["duration_s"] for e in eps), 2),
            "area_max_px": max(e["area_max_px"] for e in eps)}


def proof_sheet(body, rows, dest, cols=6, tiles=12):
    """Montase PNG: frame contoh dari jendela nyala, kotak deteksi ditandai.

    Ditulis sebagai PNG 8-bit lewat ffmpeg agar tak perlu pustaka gambar.
    """
    live = [i for i, r in enumerate(rows) if r["area_px"] > 0]
    if not live:
        return False
    pick = np.linspace(min(live), max(live), min(tiles, len(live))).astype(int)
    th, tw = body.shape[1], body.shape[2]
    rws = int(np.ceil(len(pick) / cols))
    sheet = np.zeros((rws * th, cols * tw), np.uint8)
    lut = (255 * (np.arange(256) / 255) ** 0.45).astype(np.uint8)  # gamma: adegan gelap
    for k, i in enumerate(pick):
        f = lut[body[i]]
        r = rows[i]
        if r["x0"] != "":                      # gambar kotak putih
            x0, x1, y0, y1 = r["x0"], r["x1"], r["y0"], r["y1"]
            f[y0, x0:x1 + 1] = 255
            f[y1, x0:x1 + 1] = 255
            f[y0:y1 + 1, x0] = 255
            f[y0:y1 + 1, x1] = 255
        f[0, :] = 90                           # garis pemisah antar petak
        f[:, 0] = 90
        rr, cc = divmod(k, cols)
        sheet[rr * th:(rr + 1) * th, cc * tw:(cc + 1) * tw] = f
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo",
                        "-pix_fmt", "gray", "-s", f"{sheet.shape[1]}x{sheet.shape[0]}",
                        "-i", "pipe:0", "-frames:v", "1", str(dest)],
                       input=sheet.tobytes(), capture_output=True)
    return p.returncode == 0


def test_id_of(path):
    m = re.search(r"TEST[_-]([A-Za-z0-9]+)", path.name, re.I)
    if m:
        return m.group(1)
    m = re.search(r"test-([A-Za-z0-9]+)", path.name, re.I)
    return m.group(1) if m else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", help="analisis satu file saja")
    ap.add_argument("--limit", type=int, default=0, help="batasi jumlah video")
    ap.add_argument("--fps", type=float, default=FPS)
    ap.add_argument("--proof", action="store_true", help="tulis lembar bukti PNG")
    ap.add_argument("--out", help="folder keluaran (bawaan: analysis/video_pilot)")
    ap.add_argument("--pattern", default="TEST", help="hanya nama file yang memuat ini")
    ap.add_argument("--exclude", default="", help="lewati nama file yang memuat ini, "
                    "dipisah koma (mis. 2ND_VIEW: terbukti kamera luar, bukan nyala)")
    a = ap.parse_args()
    global OUT
    if a.out:
        OUT = Path(a.out) if Path(a.out).is_absolute() else ROOT / a.out

    if a.video:
        vids = [Path(a.video)]
    else:
        skip = [s.strip().lower() for s in a.exclude.split(",") if s.strip()]
        vids = []
        for d in VID_DIRS:
            if d.exists():
                vids += sorted(p for p in d.glob("*.mp4")
                               if a.pattern.lower() in p.name.lower()
                               and "Still_Sequence" not in p.name
                               and not any(s in p.name.lower() for s in skip))
        if a.limit:
            vids = vids[:a.limit]
    if not vids:
        print("Tidak ada video yang cocok.")
        return 1

    (OUT / "traces").mkdir(parents=True, exist_ok=True)
    summary, ep_rows = [], []
    for n, v in enumerate(vids, 1):
        tid = test_id_of(v)
        body, rows = analyze(v, a.fps)
        if body is None:
            print(f"  [{n}/{len(vids)}] GAGAL BACA {v.name[:60]}")
            continue
        s = summarize(rows, a.fps)
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", v.stem)[-70:]
        with open(OUT / "traces" / f"{stem}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        proof = ""
        if a.proof and s["n_flame_frames"]:
            ok = proof_sheet(body, rows, OUT / "proof" / f"{stem}.png")
            proof = f"proof/{stem}.png" if ok else ""
        acc = "PSI-25" if "PSI-25" in str(v) else "PSI-26"
        summary.append({"accession": acc, "test_id": tid, "file": v.name,
                        "duration_s": round(len(rows) / a.fps, 1),
                        **s, "trace_csv": f"traces/{stem}.csv", "proof_png": proof})
        for k, e in enumerate(episodes_of(rows, a.fps), 1):
            ep_rows.append({"accession": acc, "test_id": tid, "episode": k,
                            "file": v.name, **e})
        print(f"  [{n}/{len(vids)}] {tid or '?':>6} {s['n_episodes']} episode"
              f"  nyala {s['total_burn_s']} s  luas maks {s['area_max_px']} px"
              f"  {v.name[:38]}")

    if summary:
        with open(OUT / "summary.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
            w.writeheader()
            w.writerows(summary)
        det = sum(1 for s in summary if s["n_episodes"])
        print(f"\n{len(summary)} video dianalisis, {det} dengan nyala terdeteksi, "
              f"{len(ep_rows)} episode pembakaran.")
        print("Ringkasan:", OUT / "summary.csv")
    if ep_rows:
        with open(OUT / "episodes.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(ep_rows[0].keys()))
            w.writeheader()
            w.writerows(ep_rows)
        print("Episode :", OUT / "episodes.csv")
        if a.proof:
            print("PERIKSA lembar bukti di", OUT / "proof",
                  "sebelum memakai angkanya.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
