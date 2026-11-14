#!/usr/bin/env python3
"""Uji deteksi nyala berbasis suhu burner terhadap catatan NASA.

CFI-G (PSI-159) adalah satu-satunya investigasi yang tabel ujinya memuat kolom
`ignited` (ya/tidak) hasil penilaian NASA. Kolom itu dipakai sebagai nilai
rujukan: apakah kenaikan suhu burner yang dideteksi skrip benar-benar menandakan
nyala menurut NASA, pada uji yang sama.

Ini validasi yang sah karena kedua sisi dihasilkan secara independen -- skrip
tidak pernah melihat kolom `ignited` saat memutuskan.

  python scripts/telemetry_validate.py
"""
import csv
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEL = ROOT / "analysis" / "telemetry" / "acme_telemetry.csv"
DB = ROOT / "kb" / "gold" / "freefall.sqlite"


def norm(s):
    return (s or "").strip().lower().replace(" ", "")


def main():
    if not TEL.exists():
        print("Belum ada", TEL, "— jalankan scripts/telemetry_mine.py dulu.")
        return 1
    tel = list(csv.DictReader(open(TEL, encoding="utf-8")))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT accession, test_id, ignited, outcome, fuel, o2_mole_frac, "
        "pressure_kpa FROM tests WHERE ignited IS NOT NULL AND ignited != ''"
    ).fetchall()
    con.close()
    truth = {(r["accession"], norm(r["test_id"])): r for r in rows}

    pairs, miss = [], 0
    for t in tel:
        k = (t["accession"], norm(t["test_point"]))
        g = truth.get(k)
        if not g:
            miss += 1
            continue
        pairs.append((t, g))

    if not pairs:
        print(f"Tidak ada pasangan ({miss} telemetri tanpa nilai rujukan).")
        return 1

    tp = sum(1 for t, g in pairs if t["ignited"] == "ya" and g["ignited"] == "yes")
    tn = sum(1 for t, g in pairs if t["ignited"] == "tidak" and g["ignited"] == "no")
    fp = sum(1 for t, g in pairs if t["ignited"] == "ya" and g["ignited"] == "no")
    fn = sum(1 for t, g in pairs if t["ignited"] == "tidak" and g["ignited"] == "yes")
    n = len(pairs)
    acc = (tp + tn) / n

    print(f"Uji silang deteksi nyala — {n} uji berpasangan "
          f"({miss} telemetri tanpa nilai rujukan di tabel)\n")
    print("                      NASA: menyala   NASA: tidak")
    print(f"  termokopel: nyala {tp:>12}   {fp:>11}")
    print(f"  termokopel: tidak  {fn:>12}   {tn:>11}")
    print(f"\n  Kecocokan: {acc:.1%}  ({tp+tn}/{n})")

    base = max(sum(1 for _, g in pairs if g["ignited"] == "yes"),
               sum(1 for _, g in pairs if g["ignited"] == "no")) / n
    print(f"  Tebak mayoritas: {base:.1%} — kecocokan di bawah ini berarti tak berguna.")
    if fp or fn:
        print(f"\n  {fp} positif palsu, {fn} negatif palsu. Contoh:")
        for t, g in pairs:
            if (t["ignited"] == "ya") != (g["ignited"] == "yes"):
                print(f"    {t['test_point']:>9} suhu burner naik {t['tc_burner_rise_v']:>9} V"
                      f" -> skrip '{t['ignited']}', NASA '{g['ignited']}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
