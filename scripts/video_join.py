#!/usr/bin/env python3
"""Gabungkan episode pembakaran hasil video_analyze.py dengan kondisi uji NASA.

Inilah langkah yang mengubah piksel menjadi sains: tiap episode dari video
dipasangkan ke baris tabel uji BASS/BASS-II lewat test_id, sehingga durasi
nyala dan cara padamnya berdampingan dengan material, O2, dan setelan aliran.

Alasan pekerjaan ini ada: tabel uji BASS-II memuat 129 baris TANPA satu pun
kolom hasil, dan hanya 2 dari 264 uji bahan padat di seluruh basis data yang
punya laju rambat. Durasi nyala dan cara berakhirnya tidak pernah ditabulasi
NASA di PSI; video adalah satu-satunya sumbernya.

Keluaran: analysis/video_pilot/measurements.csv
          (+ ringkasan ke layar)

  python scripts/video_join.py
"""
import csv
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import os
OUT = ROOT / (os.environ.get("VIDEO_OUT") or "analysis/video_pilot")
DB = ROOT / "kb" / "gold" / "freefall.sqlite"


def load_tests():
    """Peta (accession, test_id) -> kondisi uji dari basis data."""
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT accession, test_id, fuel, o2_mole_frac, outcome, raw_json "
        "FROM tests WHERE accession IN ('PSI-25','PSI-26')").fetchall()
    con.close()
    out = {}
    for r in rows:
        tid = (r["test_id"] or "").strip()
        if not tid:
            continue
        raw = {}
        try:
            raw = json.loads(r["raw_json"] or "{}")
        except ValueError:
            pass
        out[(r["accession"], tid.lower())] = {
            "fuel": r["fuel"] or "",
            "o2_mole_frac": r["o2_mole_frac"],
            "table_outcome": r["outcome"] or "",
            "air_display": raw.get("Air display", ""),
            "fan_display": raw.get("Fan display", ""),
            "sample": raw.get("Sample #", ""),
            "date": raw.get("Date", ""),
        }
    return out


def airflow_settings(air_display):
    """Berapa setelan aliran udara yang dicatat NASA untuk satu uji.

    Kolom "Air display" berisi deret setelan, mis. "10   2   1" (tiga setelan)
    atau "5  2   slow decr to ext" (dua setelan lalu diturunkan sampai padam).
    Isi dalam kurung adalah pembacaan potensiometer, bukan setelan tersendiri,
    jadi dibuang dulu.
    """
    if not air_display:
        return None
    s = re.sub(r"\([^)]*\)", " ", str(air_display))
    nums = re.findall(r"\d+(?:\.\d+)?", s)
    return len(nums) or None


def main():
    ep_path = OUT / "episodes.csv"
    if not ep_path.exists():
        print("Belum ada", ep_path, "— jalankan scripts/video_analyze.py dulu.")
        return 1
    tests = load_tests()
    eps = list(csv.DictReader(open(ep_path, encoding="utf-8")))

    rows, matched = [], 0
    for e in eps:
        key = (e["accession"], e["test_id"].strip().lower())
        t = tests.get(key)
        if t:
            matched += 1
        rows.append({
            "accession": e["accession"], "test_id": e["test_id"],
            "episode": e["episode"],
            # --- diukur dari video ---
            "t_start_s": e["t_start_s"], "t_end_s": e["t_end_s"],
            "burn_duration_s": e["duration_s"],
            "area_max_px": e["area_max_px"], "area_median_px": e["area_median_px"],
            "ending": e["ending"], "tail_frac_of_peak": e["tail_frac_of_peak"],
            "drift_px_per_s": e["drift_px_per_s"],
            # --- dari tabel uji NASA ---
            "matched": "ya" if t else "tidak",
            "fuel": t["fuel"] if t else "",
            "o2_mole_frac": t["o2_mole_frac"] if t else "",
            "air_display": t["air_display"] if t else "",
            "fan_display": t["fan_display"] if t else "",
            "sample": t["sample"] if t else "",
            "table_outcome": t["table_outcome"] if t else "",
            "source_video": e["file"],
        })

    dest = OUT / "measurements.csv"
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows)} episode, {matched} cocok dengan baris tabel uji NASA.")
    print(f"Ditulis: {dest}\n")

    have_outcome = sum(1 for r in rows if r["matched"] == "ya" and r["table_outcome"])
    print("Nilai tambah yang terukur:")
    print(f"  durasi nyala baru      : {matched} episode (tabel NASA tidak punya kolom ini)")
    print(f"  episode yang tabelnya sudah punya hasil: {have_outcome}")
    print()
    hdr = f"{'uji':>5} {'ep':>2} {'material':<22} {'O2':>6} {'aliran':<12} {'nyala(s)':>9} {'akhir':<18}"
    print(hdr)
    print("-" * len(hdr))
    for r in sorted(rows, key=lambda x: (x["test_id"], x["episode"])):
        if r["matched"] != "ya":
            continue
        o2 = f"{float(r['o2_mole_frac']):.3f}" if r["o2_mole_frac"] not in ("", None) else "—"
        print(f"{r['test_id']:>5} {r['episode']:>2} {r['fuel'][:22]:<22} {o2:>6} "
              f"{str(r['air_display'])[:12]:<12} {r['burn_duration_s']:>9} {r['ending']:<18}")

    unmatched = sorted({r["test_id"] for r in rows if r["matched"] == "tidak"})
    if unmatched:
        print("\nTest_id tanpa pasangan di tabel:", ", ".join(unmatched))

    # --- uji ulang: dua rekaman independen atas uji yang sama ---
    # Sebagian uji terekam dua kali sebagai berkas terpisah. Keduanya diukur
    # tanpa saling melihat, jadi selisihnya adalah perkiraan ketelitian metode
    # ini -- satu-satunya angka ketelitian yang bisa kita peroleh tanpa nilai
    # rujukan dari NASA (tabelnya memang tidak memuat durasi nyala).
    # Dua berkas dengan test_id sama belum tentu rekaman ulang hal yang sama:
    #   "First_Ignition_Attempts" vs "Second_Ignition_Attempts" -> dua penyalaan berbeda
    #   "Part-1" vs "Part-2"                                    -> dua potongan berurutan
    #   "Flame-Blowoff-..."                                     -> klip cuplikan, bukan uji penuh
    # Membandingkan pasangan semacam itu berarti membandingkan kejadian berbeda
    # dan menghasilkan "ketelitian" palsu, maka semuanya dikeluarkan.
    #   "vlc-record-..."  -> rekaman layar saat video diputar, hanya sepotong
    SEGMENT_MARKERS = ("part-", "part_", "first_ignition", "second_ignition",
                       "blowoff", "excerpt", "clip", "vlc-record")
    by_test = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if r["matched"] != "ya":
            continue
        if any(m in r["source_video"].lower() for m in SEGMENT_MARKERS):
            continue
        by_test[r["test_id"]][r["source_video"]].append(r)
    dupes = {t: v for t, v in by_test.items() if len(v) > 1}
    if dupes:
        print("\nUji ulang — uji yang sama terekam di dua berkas:")
        print(f"  {'uji':>5} {'ep':>3} {'durasi A':>9} {'durasi B':>9} {'selisih':>9}")
        diffs = []
        for tid, vids in sorted(dupes.items()):
            a, b = list(vids.values())[:2]
            for ea, eb in zip(sorted(a, key=lambda x: x["episode"]),
                              sorted(b, key=lambda x: x["episode"])):
                da, db = float(ea["burn_duration_s"]), float(eb["burn_duration_s"])
                rel = abs(da - db) / max(da, db)
                diffs.append(rel)
                print(f"  {tid:>5} {ea['episode']:>3} {da:>9.1f} {db:>9.1f} {rel:>8.0%}")
        if diffs:
            print(f"  Selisih relatif rata-rata: {sum(diffs)/len(diffs):.0%} "
                  f"(n={len(diffs)} episode berpasangan)")

    # --- catatan: setelan aliran BUKAN penghitung episode ---
    # Dugaan awal "jumlah episode = jumlah setelan aliran" tidak terbukti, dan
    # alasannya fisis: mengubah aliran di tengah pembakaran tidak memadamkan
    # api, sehingga satu episode bisa mencakup beberapa setelan; sebaliknya
    # penyalaan ulang pada setelan yang sama menghasilkan beberapa episode dari
    # satu nilai. Perbandingannya tetap dicetak sebagai konteks, bukan validasi.
    per_video = defaultdict(int)
    info = {}
    for r in rows:
        if r["matched"] != "ya":
            continue
        per_video[r["source_video"]] += 1
        info[r["source_video"]] = (r["test_id"], r["air_display"])
    pairs = [(info[k][0], info[k][1], n, airflow_settings(info[k][1]))
             for k, n in per_video.items()]
    pairs = [p for p in pairs if p[3]]
    if pairs:
        agree = sum(1 for _, _, n, s in pairs if n == s)
        print(f"\nKonteks (bukan validasi): episode vs jumlah angka di kolom "
              f"'Air display' — {agree}/{len(pairs)} kebetulan sama.")
        print("  Keduanya memang mengukur hal berbeda; lihat catatan di README.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
