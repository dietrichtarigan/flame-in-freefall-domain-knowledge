#!/usr/bin/env python3
"""Inventaris isi semua arsip zip PSI tanpa mengekstrak.

Satu baris per zip: investigasi, kategori, jumlah anggota, ekstensi dominan, ukuran
terkompresi & asli, contoh nama anggota. Gunanya: tahu data apa yang tersembunyi di
dalam arsip (deret gambar Saffire, video asli BASS, data mentah SAME-R, ...) sebelum
memutuskan mana yang layak diekstrak dan dianalisis.

  python scripts/inventory_zips.py   # -> kb/manifest/zip_contents.csv
"""
import csv
import sys
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ROOT / "kb" / "raw" / "psi" / "files"


def main():
    rows = []
    for z in sorted(FILES.rglob("*.zip")):
        rel = z.relative_to(FILES)
        acc, cat = rel.parts[0], rel.parts[1] if len(rel.parts) > 2 else ""
        try:
            with zipfile.ZipFile(z) as zf:
                info = [i for i in zf.infolist() if not i.is_dir()]
        except (zipfile.BadZipFile, OSError) as e:
            rows.append({"accession": acc, "category": cat, "zip": z.name, "members": 0, "top_ext": "",
                         "zip_mb": round(z.stat().st_size / 1e6, 1), "raw_mb": "", "examples": f"RUSAK: {e}"})
            continue
        ext = Counter(i.filename.rsplit(".", 1)[-1].lower() if "." in i.filename else "" for i in info)
        rows.append({"accession": acc, "category": cat, "zip": z.name, "members": len(info),
                     "top_ext": " ".join(f"{e}:{n}" for e, n in ext.most_common(4)),
                     "zip_mb": round(z.stat().st_size / 1e6, 1),
                     "raw_mb": round(sum(i.file_size for i in info) / 1e6, 1),
                     "examples": " | ".join(i.filename for i in info[:3])})
    out = ROOT / "kb" / "manifest" / "zip_contents.csv"
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    by = Counter()
    for r in rows:
        for part in r["top_ext"].split():
            e, n = part.split(":")
            by[(r["accession"], e)] += int(n)
    print(f"{len(rows)} zip. Anggota per investigasi x ekstensi:")
    for (a, e), n in sorted(by.items()):
        print(f"  {a:8s} {e:8s} {n}")
    print("Ditulis:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
