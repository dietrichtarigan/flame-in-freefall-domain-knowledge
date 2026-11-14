#!/usr/bin/env python3
"""Integrasikan batch ketiga PDF manual (paper.zip) ke kb/raw/papers/pdf/.

Isinya tepat 9 paper prioritas-1 yang masih kurang, sehingga set prioritas-1
menjadi lengkap 27/27. Lihat integrate_manual_papers.py (batch 1) dan
integrate_new_papers.py (batch 2).

DOI diverifikasi dari judul di halaman pertama tiap PDF.
"""
import csv
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "arsip" / "paper_zip_staging"
PDF_DIR = ROOT / "kb" / "raw" / "papers" / "pdf"
MANIFEST = ROOT / "kb" / "manifest" / "papers_doi.csv"

MAP = {
    "1-s2.0-S0010218021003801-main": "10.1016/j.combustflame.2021.111637",
    "1-s2.0-S037971122400050X-main": "10.1016/j.firesaf.2024.104137",
    "1-s2.0-S1540748918302050-main": "10.1016/j.proci.2018.06.022",
    "1-s2.0-S1540748924000105-main": "10.1016/j.proci.2024.105200",
    "1-s2.0-S1540748924001810-main": "10.1016/j.proci.2024.105373",
    "1-s2.0-S1540748924003031-main": "10.1016/j.proci.2024.105495",
    "1-s2.0-S1540748926000337-main": "10.1016/j.proci.2026.106032",
    "20200000557": "10.1016/j.combustflame.2018.10.016",
    "s41598-017-18398-4": "10.1038/s41598-017-18398-4",
}


def doi_fname(doi):
    return re.sub(r"[^a-z0-9._-]+", "_", doi.lower()) + ".pdf"


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    by_doi = {r["doi"].lower(): r for r in rows}

    copied, resolved, missing = [], [], []
    for stem, doi in MAP.items():
        src = SRC / f"{stem}.pdf"
        if not src.exists():
            missing.append(stem)
            continue
        dest = PDF_DIR / doi_fname(doi)
        shutil.copy2(src, dest)
        copied.append((stem, doi))
        r = by_doi.get(doi.lower())
        if r:
            if r["pdf_status"] not in ("downloaded", "downloaded_manual"):
                resolved.append((r.get("priority", ""), doi, r.get("title", "")))
            r["pdf_status"] = "downloaded_manual"
            r["pdf_path"] = str(dest.relative_to(ROOT / "kb"))
        else:
            missing.append(f"{stem} -> DOI {doi} tidak ada di manifest")

    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Disalin {len(copied)} PDF ke {PDF_DIR}")
    for stem, doi in copied:
        print(f"  {stem}.pdf -> {doi}")
    print(f"\nDOI yang baru ter-resolve ({len(resolved)}):")
    for pr, doi, title in sorted(resolved):
        print(f"  [prio {pr}] {doi} — {title[:66]}")

    p1 = [r for r in rows if r["priority"] == "1"]
    done = [r for r in p1 if r["pdf_status"] in ("downloaded", "downloaded_manual")]
    print(f"\nPrioritas 1: {len(done)}/{len(p1)} sudah punya PDF.")
    if missing:
        print("Tidak terproses:", missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
