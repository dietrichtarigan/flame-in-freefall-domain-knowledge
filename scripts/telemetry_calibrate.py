#!/usr/bin/env python3
"""Ubah sebagian kanal telemetri ACME dari VOLT ke satuan fisis, lalu validasi.

Rumus diambil dari lembar kerja NASA sendiri:
  PSI-23 Engineering Documents / ACME Gas flow / ACMEFlowAndPressuresRawDataConversion.xlsx
    MFCAi (SLPM, basis N2) = V / 5 * FullScale_i        (FullScale dari baris kepala berkas)
    PTAi  (psia)           = (V - 0.5) * 14.5038 * 10      <- rumus lembar kerja, TERNYATA SALAH SKALA
Validasi terhadap tabel NASA menunjukkan transduser 0-10 bar pada sinyal 0,5-4,5 V:
    PTAi  (psia)           = (V - 0.5) * 145.038 / 4      <- dipakai di sini (tanpa fitting)
  hasil: PSI-10 MAE 2,2 kPa (~1 %), PSI-159 MAE 6,7 kPa (tabel PSI-159 hanya 'approx p (bar)').
  Regresi bebas memberi nol di 0,51-0,53 V dan 36,4 psia/V, konsisten dengan 145,04/4 = 36,26.
  PTA2/PTA3 = tekanan ruang (korelasi 0,997-1,000); PTA1 tidak berkorelasi (kanal lain).
Termokopel TIDAK ada di lembar itu -> tc_burner_rise_v tetap volt.

Validasi: tekanan awal (median 2 s pertama) dibandingkan dengan tekanan yang dicatat NASA
di tabel uji (PSI-159 'approx p (bar)', PSI-10 'pinit (atm)').

  python scripts/telemetry_calibrate.py  # -> analysis/telemetry/telemetry_calibrated.csv
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
PSIA_TO_KPA = 6.894757


def one(args):
    acc, f = args
    p = ROOT / "kb" / "raw" / "psi" / "files" / acc / "Raw Data" / f
    try:
        head = open(p, encoding="utf-8", errors="replace").readline()
        fs = {k: float(v) for k, v in re.findall(r"(MFCA\d) Full Scale:\s*([\d.]+)", head)}
        df = pd.read_csv(p, skiprows=1, usecols=["Time", "MFCA1StaticMixerFlow", "MFCA2BypassFlow",
                                                 "MFCA3FuelFlow", "PTA1", "PTA2", "PTA3"], low_memory=False)
        v = df.drop(columns="Time").apply(pd.to_numeric, errors="coerce")
        n0 = max(10, min(len(v), 250))                     # ~2 s pertama pada 125 Hz
        start = v.iloc[:n0].median()
        mid = v.iloc[len(v) // 3: 2 * len(v) // 3].median()
        out = {"file": f}
        for k in ("PTA1", "PTA2", "PTA3"):
            out[f"{k}_kpa_start"] = round((start[k] - 0.5) * 145.038 / 4 * PSIA_TO_KPA, 2)
            out[f"{k}_kpa_end"] = round((v[k].iloc[-n0:].median() - 0.5) * 145.038 / 4 * PSIA_TO_KPA, 2)
            out[f"{k}_kpa_max_rise"] = round(float((v[k].max() - start[k]) * 145.038 / 4 * PSIA_TO_KPA), 3)
        for k, col in (("MFCA1", "MFCA1StaticMixerFlow"), ("MFCA2", "MFCA2BypassFlow"), ("MFCA3", "MFCA3FuelFlow")):
            if k in fs:
                out[f"{k}_slpm_mid"] = round(mid[col] / 5 * fs[k], 5)
                out[f"{k}_fullscale"] = fs[k]
        return out
    except Exception as e:  # noqa: BLE001
        return {"file": f, "error": str(e)[:120]}


def main():
    tel = list(csv.DictReader(open(ROOT / "analysis" / "telemetry" / "telemetry_joined.csv", encoding="utf-8")))
    with ProcessPoolExecutor() as ex:
        res = {r["file"]: r for r in ex.map(one, [(t["accession"], t["file"]) for t in tel], chunksize=4)}
    con = sqlite3.connect(ROOT / "kb" / "gold" / "freefall.sqlite")
    tbl = {(a, t.replace(" ", "").lower()): p for a, t, p in
           con.execute("SELECT accession, test_id, pressure_kpa FROM tests WHERE accession IN ('PSI-10','PSI-159')")}
    rows = []
    for t in tel:
        r = dict(res.get(t["file"], {}))
        r.update({"accession": t["accession"], "test_point": t["test_point"],
                  "table_pressure_kpa": tbl.get((t["accession"], t["test_point"].lower()), "")})
        rows.append(r)
    keys = ["accession", "test_point", "table_pressure_kpa"] + sorted({k for r in rows for k in r} -
                                                                       {"accession", "test_point", "table_pressure_kpa", "file"}) + ["file"]
    out = ROOT / "analysis" / "telemetry" / "telemetry_calibrated.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} uji, {sum('error' in r for r in rows)} gagal dibaca. Ditulis: {out}\n")
    print("Validasi tekanan awal terhadap tabel NASA:")
    for acc in ("PSI-10", "PSI-159"):
        sub = [r for r in rows if r["accession"] == acc and r["table_pressure_kpa"] not in ("", None) and "error" not in r]
        y = np.array([float(r["table_pressure_kpa"]) for r in sub])
        for k in ("PTA1", "PTA2", "PTA3"):
            x = np.array([r[f"{k}_kpa_start"] for r in sub])
            ok = np.isfinite(x)
            if ok.sum() < 5:
                continue
            d = x[ok] - y[ok]
            rr = np.corrcoef(x[ok], y[ok])[0, 1]
            print(f"  {acc:8s} {k}: n={ok.sum():3d}  korelasi {rr:.3f}  selisih median {np.median(d):+7.2f} kPa  "
                  f"MAE {np.mean(np.abs(d)):6.2f} kPa  (tabel {y.min():.0f}–{y.max():.0f} kPa)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
