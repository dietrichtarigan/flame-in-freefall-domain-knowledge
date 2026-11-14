#!/usr/bin/env python3
"""Praproses telemetri ACME mentah -> tensor berukuran tetap untuk deep learning.

Untuk tiap berkas *_data.csv di analysis/telemetry/acme_telemetry.csv:
  - ambil 18 kanal bernama yang sama di PSI-10, PSI-23, PSI-159
  - cuplik ulang ke 4 Hz selama 128 s (512 langkah); di luar rekaman -> mask 0
  - kurangi nilai dasar per kanal (median 2 s pertama), supaya geseran
    kalibrasi antar-hari tidak terbaca sebagai sinyal
Label (hanya PSI-159, dari tabel NASA): ignited, self-extinguished, burn time.

  python scripts/ml_telemetry_prep.py     # -> analysis/ml/telemetry_tensors.npz (~1 menit/100 berkas)
"""
import csv
import re
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "analysis" / "ml"
CH = ["MFCA1StaticMixerFlow", "MFCA2BypassFlow", "MFCA3FuelFlow", "IonCurrent",
      "PTA1", "PTA2", "PTA3", "EfieldVoltage", "PMT1", "PMT2", "PMT3",
      "TCA", "TCB", "TCC", "TCD", "TC200A", "TC200B", "TCBurner"]
HZ, SEC = 4, 128
L = HZ * SEC


def tsec(s):
    h, m, sec, ms = (int(x) for x in s.strip().split(":"))
    return h * 3600 + m * 60 + sec + ms / 1000


def load_one(path):
    df = pd.read_csv(path, skiprows=1, usecols=["Time"] + CH, engine="c",
                     on_bad_lines="skip", low_memory=False)
    t = df["Time"].astype(str).map(tsec).to_numpy()
    t = t - t[0]
    t[t < 0] += 86400                       # lewat tengah malam
    v = df[CH].apply(pd.to_numeric, errors="coerce").to_numpy(np.float64)
    grid = np.arange(L) / HZ
    x = np.zeros((len(CH), L), np.float32)
    mask = (grid <= t[-1]).astype(np.float32)
    base = np.nanmedian(v[t <= 2.0], axis=0) if (t <= 2.0).any() else np.nanmedian(v[:50], axis=0)
    for c in range(len(CH)):
        ok = np.isfinite(v[:, c])
        if ok.sum() < 2:
            continue
        x[c] = np.interp(grid, t[ok], v[ok, c] - base[c]) * mask
    return x, mask, float(t[-1])


def job(a):
    acc, f = a
    try:
        return load_one(ROOT / "kb" / "raw" / "psi" / "files" / acc / "Raw Data" / f)
    except Exception as e:  # noqa: BLE001
        return str(e)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tel = list(csv.DictReader(open(ROOT / "analysis" / "telemetry" / "acme_telemetry.csv",
                                   encoding="utf-8")))
    con = sqlite3.connect(ROOT / "kb" / "gold" / "freefall.sqlite")
    lab = {}
    for tid, ig, out, bt, tbl in con.execute(
            "SELECT test_id, ignited, outcome, burn_time_s, table_name FROM tests "
            "WHERE accession='PSI-159'"):
        lab[tid.replace(" ", "").lower()] = (ig, out, bt, tbl)
    args = [(t["accession"], t["file"]) for t in tel]
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(job, args, chunksize=4))
    keep, X, M, rec = [], [], [], []
    for t, r in zip(tel, res):
        if isinstance(r, str):
            print("lewati", t["file"], r[:80])
            continue
        keep.append(t); X.append(r[0]); M.append(r[1]); rec.append(r[2])
    n = len(keep)
    y_ign = np.full(n, -1, np.int8); y_se = np.full(n, -1, np.int8)
    y_bt = np.full(n, np.nan, np.float32); inv = np.full(n, -1, np.int8)
    for i, t in enumerate(keep):
        if t["accession"] != "PSI-159":
            continue
        L_ = lab.get(t["test_point"].lower())
        if not L_:
            continue
        ig, out, bt, tbl = L_
        inv[i] = 1 if "Inverse" in (tbl or "") else 0
        if ig in ("yes", "no"):
            y_ign[i] = ig == "yes"
        if ig == "yes" and out in ("self-extinguished", "flow terminated"):
            y_se[i] = out == "self-extinguished"
        if ig == "yes" and bt is not None:
            y_bt[i] = bt
    np.savez_compressed(
        OUT / "telemetry_tensors.npz", X=np.stack(X), mask=np.stack(M), record_s=np.array(rec),
        y_ign=y_ign, y_selfext=y_se, y_burn=y_bt, inverse=inv, channels=np.array(CH),
        accession=np.array([t["accession"] for t in keep]),
        test_point=np.array([t["test_point"] for t in keep]),
        day=np.array([re.match(r"\d{5}", t["test_point"]).group(0) if re.match(r"\d{5}", t["test_point"])
                      else t["test_point"][:5] for t in keep]),
        rule_ign=np.array([1 if t["ignited"] == "ya" else 0 for t in keep], np.int8),
        tc_rise=np.array([float(t["tc_burner_rise_v"] or "nan") for t in keep]))
    print(f"{n} rekaman; berlabel menyala: {(y_ign >= 0).sum()}, padam-sendiri: {(y_se >= 0).sum()}, "
          f"waktu bakar: {np.isfinite(y_bt).sum()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
