#!/usr/bin/env python3
"""Tambang telemetri sensor ACME: 943 berkas `*_data.csv` (3,5 GB) jadi satu tabel.

Berkas-berkas ini adalah rekaman sensor mentah ~125 Hz dari tiga investigasi ACME
(PSI-10 Flame Design, PSI-23 s-Flame, PSI-159 CFI-G) dan belum pernah masuk basis
data kita. Tabel uji PSI hanya memuat kondisi yang DIRENCANAKAN; berkas ini memuat
apa yang benar-benar TERJADI pada tiap uji.

Yang diekstrak per uji:
  - waktu nyala dan padam, serta durasi nyala  (dari arus ion)
  - puncak arus ion                            (indikator kuat nyala)
  - kenaikan suhu burner                       (termokopel, relatif terhadap awal)
  - laju alir bahan bakar rata-rata saat nyala (MFC)
  - ada/tidaknya nyala sama sekali

Detektor nyala: KENAIKAN SUHU BURNER (termokopel), bukan arus ion.

Arus ion sempat dipakai -- nyala hidrokarbon menghasilkan ion -- tetapi diuji
terhadap kolom `ignited` NASA pada 320 uji CFI-G dan GAGAL: kecocokannya 45,6%,
jauh di bawah tebak-mayoritas 81,9%. Sebabnya terlihat begitu datanya dipilah:

    konfigurasi   NASA       n    kenaikan arus ion (median)
    inverse       menyala   130      0,04 V
    inverse       tidak      14      0,06 V
    normal        menyala   131      2,31 V
    normal        tidak      44      2,29 V

Nilainya praktis sama antara menyala dan tidak, jadi kanal itu sebenarnya
mengikuti aliran bahan bakar, bukan keberadaan api. Masuk akal secara fisika:
CFI-G adalah investigasi NYALA DINGIN (~500 K), yang hampir tidak menghasilkan
ionisasi maupun cahaya tampak.

Termokopel burner memisahkan dengan tajam (api memanaskan burner, berlaku untuk
nyala normal, inverse, maupun nyala dingin):

    tidak menyala : median 0,00001-0,00003 V, p90 = 0,00053 V
    menyala       : median 0,00392-0,00606 V, p10 = 0,00062 V

Ambang 0,0006 V diambil di celah antara keduanya. Lihat scripts/telemetry_validate.py.

PERINGATAN SATUAN: semua kanal adalah TEGANGAN MENTAH, bukan satuan fisis
terkalibrasi. "Kenaikan suhu burner" di sini adalah kenaikan tegangan termokopel
(volt), BUKAN derajat Celsius. Angka-angka ini sah untuk membandingkan antar-uji
dan untuk penentuan waktu, tetapi tidak boleh ditampilkan sebagai suhu atau fluks
dalam satuan SI tanpa kurva kalibrasi NASA yang belum kita punya.

  python scripts/telemetry_mine.py --limit 20     # coba dulu
  python scripts/telemetry_mine.py                # semua 943 berkas
"""
import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "kb" / "raw" / "psi" / "files"
OUT = ROOT / "analysis" / "telemetry"

USECOLS = ["Time", "IonCurrent", "TCBurner", "MFCA3FuelFlow",
           "MFCA1StaticMixerFlow", "PTA1"]
IGNITE_FRAC = 0.30       # fraksi kenaikan suhu untuk menandai jendela nyala
TC_RISE_MIN_V = 0.0006   # ambang menyala/tidak (celah terukur; lihat docstring)
MIN_BURN_S = 1.0


def parse_header(line):
    """Baris pertama memuat metadata uji: 'Test Point: 21088C1', gas, skala penuh."""
    out = {}
    m = re.search(r"Test Point:\s*([A-Za-z0-9]+)", line)
    out["test_point"] = m.group(1) if m else ""
    m = re.search(r"Experiment:\s*(\d+)", line)
    out["experiment"] = m.group(1) if m else ""
    m = re.match(r"\s*(\d{4}-\d{2}-\d{2})", line)
    out["date"] = m.group(1) if m else ""
    for g in ("MFCA1", "MFCA2", "MFCA3"):
        m = re.search(g + r" Gas:\s*(\d+)", line)
        out[g.lower() + "_gas"] = m.group(1) if m else ""
    return out


def time_seconds(col):
    """'19:21:10:644' -> detik sejak awal rekaman (tahan terhadap baris rusak)."""
    s = col.astype(str).str.strip()
    p = s.str.split(":", expand=True)
    if p.shape[1] < 3:
        return None
    h = pd.to_numeric(p[0], errors="coerce")
    m = pd.to_numeric(p[1], errors="coerce")
    sec = pd.to_numeric(p[2], errors="coerce")
    ms = pd.to_numeric(p[3], errors="coerce").fillna(0) if p.shape[1] > 3 else 0
    t = h * 3600 + m * 60 + sec + ms / 1000.0
    # Sebagian rekaman memuat satu-dua baris stempel waktu rusak (terpantau 1
    # baris di antara 5.920 pada PSI-23_19352D5). Dibiarkan, NaN-nya merambat
    # dan durasi uji itu ikut jadi NaN. Karena waktunya monoton pada ~125 Hz,
    # nilai tetangga adalah tambalan yang aman dan tidak mengubah hasil.
    t = t.ffill().bfill()
    t = t - t.iloc[0]
    return t.where(t >= 0, t + 86400)        # lewat tengah malam


def analyze(path):
    head = open(path, encoding="utf-8", errors="replace").readline()
    meta = parse_header(head)
    cols = [c.strip() for c in
            open(path, encoding="utf-8", errors="replace").readlines()[1].split(",")]
    use = [c for c in USECOLS if c in cols]
    if "Time" not in use or "IonCurrent" not in use:
        return None
    df = pd.read_csv(path, skiprows=1, usecols=use, low_memory=False)
    if len(df) < 50:
        return None
    t = time_seconds(df["Time"])
    if t is None:
        return None
    t = t.values
    ion = pd.to_numeric(df["IonCurrent"], errors="coerce").ffill().fillna(0).values
    if "TCBurner" not in df.columns:
        return None
    tc = pd.to_numeric(df["TCBurner"], errors="coerce").ffill().fillna(0).values

    nbase = max(10, len(tc) // 20)                 # 5% awal = sebelum penyalaan
    tc_base = float(np.median(tc[:nbase]))
    tc_peak = float(np.percentile(tc, 99))
    tc_rise = tc_peak - tc_base
    row = {**meta, "file": path.name,
           "accession": next(x for x in path.parts if x.startswith("PSI-")),
           "n_samples": len(df), "record_s": round(float(t[-1]), 2),
           "tc_burner_rise_v": round(tc_rise, 6),
           # arus ion tetap dicatat sebagai konteks, TIDAK dipakai memutuskan
           "ion_rise_v": round(float(np.percentile(ion, 99) - np.percentile(ion, 5)), 4)}

    def no_flame():
        row.update({"ignited": "tidak", "t_ignite_s": "", "t_extinct_s": "",
                    "burn_duration_s": "", "fuel_flow_mean": "", "ended": ""})
        return row

    if tc_rise < TC_RISE_MIN_V:
        return no_flame()

    on = tc > tc_base + IGNITE_FRAC * tc_rise
    idx = np.flatnonzero(on)
    if len(idx) == 0:
        return no_flame()
    i0, i1 = int(idx[0]), int(idx[-1])
    dur = float(t[i1] - t[i0])
    if dur < MIN_BURN_S:
        return no_flame()

    # Apakah rekaman berhenti saat burner masih panas? Membedakan pendinginan
    # yang sempat terekam dari rekaman yang terpotong lebih dulu.
    ended = ("mendingin dalam rekaman" if i1 < len(tc) - 5
             else "rekaman berakhir saat burner masih panas")

    ff = ""
    if "MFCA3FuelFlow" in df.columns:
        f = pd.to_numeric(df["MFCA3FuelFlow"], errors="coerce").ffill().fillna(0).values
        ff = round(float(np.median(f[i0:i1 + 1])), 4)

    row.update({"ignited": "ya", "t_ignite_s": round(float(t[i0]), 2),
                "t_extinct_s": round(float(t[i1]), 2),
                "burn_duration_s": round(dur, 2),
                "fuel_flow_mean": ff, "ended": ended})
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--acc", help="batasi ke satu investigasi, mis. PSI-159")
    a = ap.parse_args()

    files = sorted(SRC.rglob("*_data.csv"))
    if a.acc:
        files = [f for f in files if a.acc in str(f)]
    if a.limit:
        files = files[:a.limit]
    if not files:
        print("Tidak ada berkas telemetri.")
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    rows, bad = [], 0
    for n, f in enumerate(files, 1):
        try:
            r = analyze(f)
        except Exception as e:
            r, bad = None, bad + 1
            if bad <= 3:
                print(f"    GAGAL {f.name[:50]}: {e!r}"[:120])
        if r:
            rows.append(r)
        if n % 50 == 0 or n == len(files):
            ig = sum(1 for x in rows if x.get("ignited") == "ya")
            print(f"  [{n}/{len(files)}] terbaca {len(rows)}, menyala {ig}, gagal {bad}")

    if not rows:
        print("Tidak ada yang berhasil dibaca.")
        return 1
    keys = list(rows[0].keys())
    dest = OUT / "acme_telemetry.csv"
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    ig = [r for r in rows if r["ignited"] == "ya"]
    print(f"\n{len(rows)} uji terbaca, {len(ig)} menyala, {len(rows)-len(ig)} tidak.")
    if ig:
        d = np.array([float(r["burn_duration_s"]) for r in ig])
        print(f"Durasi nyala: median {np.median(d):.1f} s, "
              f"rentang {d.min():.1f}-{d.max():.1f} s")
        cut = sum(1 for r in ig if r["ended"] == "rekaman berakhir saat menyala")
        print(f"Rekaman terpotong saat masih menyala: {cut} "
              f"(durasinya batas bawah, bukan waktu padam)")
    print("Ditulis:", dest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
