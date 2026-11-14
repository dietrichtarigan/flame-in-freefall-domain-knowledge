#!/usr/bin/env python3
"""Gabungkan hasil telemetri ACME ke tabel uji, lalu ringkas nilai tambahnya.

Tiga pola pemasangan, sesuai bentuk tabel masing-masing investigasi:

  PSI-159 CFI-G       test_id per uji     -> pasangan satu-satu
  PSI-10 Flame Design test_id per uji     -> pasangan satu-satu
  PSI-23 s-Flame      test_id per HARI    -> telemetri memekarkan 18 baris
                                             ringkasan menjadi ratusan uji

Keluaran: analysis/telemetry/telemetry_joined.csv

  python scripts/telemetry_join.py
"""
import csv
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEL = ROOT / "analysis" / "telemetry" / "acme_telemetry.csv"
DB = ROOT / "kb" / "gold" / "freefall.sqlite"
ACC = ("PSI-10", "PSI-23", "PSI-159")


def norm(s):
    return (s or "").strip().lower().replace(" ", "")


def day_of(test_point):
    """'19254A1' -> '19254' (kode hari di awal kode uji ACME)."""
    m = re.match(r"(\d{5})", test_point or "")
    return m.group(1) if m else ""


def main():
    if not TEL.exists():
        print("Belum ada", TEL, "— jalankan scripts/telemetry_mine.py dulu.")
        return 1
    tel = list(csv.DictReader(open(TEL, encoding="utf-8")))

    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT accession, test_id, granularity, fuel, configuration, "
        "o2_mole_frac, pressure_kpa, ignited, outcome FROM tests "
        f"WHERE accession IN {ACC}").fetchall()
    con.close()

    exact = {(r["accession"], norm(r["test_id"])): r for r in rows}
    by_day = {(r["accession"], norm(r["test_id"])): r for r in rows
              if r["granularity"] == "campaign"}

    out, how = [], Counter()
    for t in tel:
        acc, tp = t["accession"], t["test_point"]
        g = exact.get((acc, norm(tp)))
        kind = "uji" if g else ""
        if not g:
            g = by_day.get((acc, norm(day_of(tp))))
            kind = "hari" if g else "tidak ada"
        how[kind] += 1
        out.append({
            "accession": acc, "test_point": tp, "match": kind,
            # --- terukur dari telemetri ---
            "ignited_tel": t["ignited"], "burn_duration_s": t["burn_duration_s"],
            "t_ignite_s": t["t_ignite_s"], "t_extinct_s": t["t_extinct_s"],
            "tc_burner_rise_v": t["tc_burner_rise_v"],
            "fuel_flow_mean": t["fuel_flow_mean"], "record_s": t["record_s"],
            "n_samples": t["n_samples"], "ended": t["ended"],
            # --- dari tabel uji NASA ---
            "table_row": (g["test_id"] if g else ""),
            "table_granularity": (g["granularity"] if g else ""),
            "fuel": (g["fuel"] if g else ""),
            "configuration": (g["configuration"] if g else ""),
            "o2_mole_frac": (g["o2_mole_frac"] if g else ""),
            "pressure_kpa": (g["pressure_kpa"] if g else ""),
            "ignited_table": (g["ignited"] if g else ""),
            "file": t["file"],
        })

    dest = TEL.parent / "telemetry_joined.csv"
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print(f"{len(out)} uji telemetri. Ditulis: {dest}\n")
    print("Cara terpasang ke tabel:")
    for k, v in how.most_common():
        print(f"  {k:10s} {v:4d}")

    print("\nNilai tambah per investigasi:")
    hdr = f"  {'inv':<9} {'uji telemetri':>13} {'baris tabel':>12} {'menyala':>8} {'durasi median':>14}"
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    tbl_n = Counter(r["accession"] for r in rows)
    for a in ACC:
        sub = [o for o in out if o["accession"] == a]
        if not sub:
            continue
        ig = [o for o in sub if o["ignited_tel"] == "ya"]
        d = sorted(float(o["burn_duration_s"]) for o in ig
                   if o["burn_duration_s"] not in ("", "nan"))
        med = f"{d[len(d)//2]:.1f} s" if d else "—"
        print(f"  {a:<9} {len(sub):>13} {tbl_n[a]:>12} {len(ig):>8} {med:>14}")

    exp = [o for o in out if o["match"] == "hari"]
    if exp:
        days = len({o["table_row"] for o in exp})
        print(f"\n  PSI-23: {len(exp)} uji individual dipulihkan dari {days} baris "
              f"ringkasan harian ({len(exp)/max(1,days):.0f}x lipat).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
