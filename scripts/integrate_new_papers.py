#!/usr/bin/env python3
"""Integrasikan batch kedua PDF manual (new_paper/ + isi zip-nya) ke kb/raw/papers/pdf/
dan perbarui kb/manifest/papers_doi.csv. Lihat integrate_manual_papers.py untuk batch pertama.
"""
import csv
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIRS = [ROOT / "arsip" / "new_paper_staging", ROOT / "arsip" / "new_paper_staging" / "_unzipped"]  # sudah diintegrasikan; staging diarsipkan
PDF_DIR = ROOT / "kb" / "raw" / "papers" / "pdf"
MANIFEST = ROOT / "kb" / "manifest" / "papers_doi.csv"

MAP = {
    "1-s2.0-S0360128525000437-main": "10.1016/j.pecs.2025.101251",
    "1-s2.0-S0379711225002899-main": "10.1016/j.firesaf.2025.104625",
    "1-s2.0-S0379711226000871-main": "10.1016/j.firesaf.2026.104719",
    "1-s2.0-S0379711226003206-main": "10.1016/j.firesaf.2026.104952",
    "1-s2.0-S1540748916304357-main": "10.1016/j.proci.2016.08.046",   # duplikat batch 1
    "1-s2.0-S1540748922000852-main": "10.1016/j.proci.2022.07.053",
    "1-s2.0-S1540748924003821-main": "10.1016/j.proci.2024.105574",
    "1-s2.0-S1540748926004566-main": "10.1016/j.proci.2026.106460",
    "Effects-of-Confinement-on-Opposed-Flow-Flame-Spread-over-Cellulose-and-Polymeric-Solids-in": "10.1007/s12217-024-10106-y",
    "Experimental-determination-of-diffusion-flame-extinction-boundaries-over-a-PMMA-sphere-The": "10.1016/j.combustflame.2025.114244",
    "Flame-spread-over-charring-and-non-charring-materials-in-microgravity-on-ISS-Kibo": "10.1016/j.combustflame.2026.114803",
    "bhattacharjee2016": "10.1016/j.firesaf.2015.11.011",            # duplikat batch 1
    "dietrich2014": "10.1007/s12217-014-9372-2",
    "dietrich2014_2": "10.1007/s12217-014-9372-2",                  # duplikat dalam batch ini
    "li2021": "10.1016/j.combustflame.2020.12.042",
    "olson2017": "10.1016/j.combustflame.2017.03.001",              # duplikat batch 1
    "urban2019": "10.1016/j.combustflame.2018.10.012",              # duplikat batch 1
}
SKIP = {"li2021_2": "file salah -- isinya paper linguistik Portugis dari JSTOR, bukan combustion"}


def doi_fname(doi):
    return re.sub(r"[^a-z0-9._-]+", "_", doi.lower()) + ".pdf"


def find_src(stem):
    for d in SRC_DIRS:
        p = d / f"{stem}.pdf"
        if p.exists():
            return p
    return None


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    by_doi = {r["doi"].lower(): r for r in rows}

    copied, newly_resolved, dup_skipped, unmatched = [], [], [], []
    seen_doi = set()
    for stem, doi in MAP.items():
        src = find_src(stem)
        if not src:
            unmatched.append(stem)
            continue
        dest = PDF_DIR / doi_fname(doi)
        r = by_doi.get(doi.lower())
        already = r and r["pdf_status"] in ("downloaded", "downloaded_manual")
        if doi.lower() not in seen_doi and not already:
            shutil.copy2(src, dest)
            copied.append((stem, doi, dest.name))
        elif already:
            dup_skipped.append((stem, doi))
        seen_doi.add(doi.lower())
        if r:
            if r["pdf_status"] not in ("downloaded", "downloaded_manual"):
                newly_resolved.append((doi, r.get("priority", ""), r.get("title", "")))
            r["pdf_status"] = "downloaded_manual"
            r["pdf_path"] = str(dest.relative_to(ROOT / "kb"))
        else:
            unmatched.append(f"{stem} -> DOI {doi} tidak ada di manifest")

    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Disalin: {len(copied)} file baru ke {PDF_DIR}")
    for stem, doi, name in copied:
        print(f"  {stem}.pdf -> {name}  ({doi})")
    print(f"\nDOI baru yang ter-resolve ({len(newly_resolved)}):")
    for doi, pr, title in newly_resolved:
        print(f"  [prio {pr}] {doi} -- {title[:70]}")
    if dup_skipped:
        print(f"\nSudah ada sebelumnya, dilewati ({len(dup_skipped)}):")
        for stem, doi in dup_skipped:
            print(f"  {stem}.pdf == {doi} (sudah downloaded_manual)")
    if SKIP:
        print(f"\nDilewati (bukan paper yang benar):")
        for stem, why in SKIP.items():
            print(f"  {stem}.pdf: {why}")
    if unmatched:
        print(f"\nTidak terproses ({len(unmatched)}):")
        for u in unmatched:
            print("  ", u)
    print(f"\nManifest diperbarui: {MANIFEST}")


if __name__ == "__main__":
    main()
