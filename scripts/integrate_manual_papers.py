#!/usr/bin/env python3
"""Integrasikan PDF yang diunduh manual (paper_downloaded/) ke kb/raw/papers/pdf/
dan perbarui kb/manifest/papers_doi.csv agar statusnya 'downloaded_manual'.

Pemetaan filename -> DOI dibuat manual dengan membaca judul di halaman pertama
tiap PDF dan mencocokkannya ke kb/manifest/papers_doi.csv / doi_list.csv.
"""
import csv
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "paper_downloaded"
PDF_DIR = ROOT / "kb" / "raw" / "papers" / "pdf"
MANIFEST = ROOT / "kb" / "manifest" / "papers_doi.csv"

# filename (tanpa .pdf) -> DOI, diverifikasi dari teks halaman pertama
MAP = {
    "24_235": "10.15011/jasma.24.3_235",
    "Flame-Spread-Over-Thin-Circular-PMMA-Rods-Experiments": "10.1080/00102202.2025.2465790",
    "Flame-spread-over-thin-circular-PMMA-rods-numerical-modelling": "10.1080/13647830.2025.2539131",
    "alam2015": "10.1016/j.proci.2014.06.043",
    "avedisian2000": "10.2514/2.5698",
    "bhattacharjee2016": "10.1016/j.firesaf.2015.11.011",
    "bhattacharjee2017": "10.1016/j.proci.2016.06.025",
    "bhattacharjee2020": "10.1016/j.ijheatmasstransfer.2020.119358",
    "cao2015": "10.1016/j.proci.2014.05.138",
    "carmignani2017": "10.1080/00102202.2017.1404587",
    "carmignani2019": "10.1007/s10694-019-00884-y",
    "chen1995": "10.1080/00102209508907795",
    "dietrich2016": "10.1080/00102202.2016.1225730",
    "farouk2011": "10.1080/13647830.2010.547601",
    "farouk2014": "10.1016/j.combustflame.2013.09.011",
    "farouk2015": "10.1016/j.proci.2014.06.015",
    "greenberg2015": "10.1016/j.firesaf.2015.04.004",
    "j.proci.2014.07.022": "10.1016/j.proci.2014.07.022",
    "j.proci.2016.08.046": "10.1016/j.proci.2016.08.046",
    "j.proci.2020.07.139": "10.1016/j.proci.2020.07.139",
    "liu2015": "10.1016/j.proci.2014.07.022",       # duplikat j.proci.2014.07.022
    "malhotra2013": "10.1080/13647830.2013.809797",
    "markan2018": "10.1016/j.combustflame.2018.01.044",
    "mikami2005": "10.1016/j.combustflame.2005.01.007",
    "nayagam2012": "10.1016/j.combustflame.2012.07.012",
    "nayagam2016": "10.2514/1.j054437",
    "nomura2011": "10.1016/j.proci.2010.06.130",
    "nomura2017": "10.1016/j.proci.2016.08.046",     # duplikat j.proci.2016.08.046
    "olson1991": "10.1080/00102209108951711",
    "olson2009": "10.1016/j.proci.2008.05.081",
    "olson2017": "10.1016/j.combustflame.2017.03.001",
    "park2009": "10.1021/ef900555u",
    "pepper2012": "10.2514/6.2012-3493",
    "seshadri2016": "10.1080/13647830.2016.1248494",
    "shih2003": "10.1088/1364-7830/7/4/005",
    "urban2009": "10.4271/2009-01-2468",
    "urban2019": "10.1016/j.combustflame.2018.10.012",
    "wang2019": "10.1016/j.jaerosci.2019.06.004",
    "zhao2017": "10.1016/j.proci.2016.06.028",
    "zhou2014": "10.1089/space.2013.0035",
}
# Bukan paper DOI, dokumen NASA mandiri -> disimpan terpisah dengan nama aslinya
STANDALONE = ["np-2015-10-034-jsc_combustion_in_reduced_gravity-iss-mini-book-011116-508"]


def doi_fname(doi):
    return re.sub(r"[^a-z0-9._-]+", "_", doi.lower()) + ".pdf"


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    by_doi = {r["doi"].lower(): r for r in rows}

    copied, matched_doi, unmatched = [], set(), []
    for stem, doi in MAP.items():
        src = SRC / f"{stem}.pdf"
        if not src.exists():
            unmatched.append(stem)
            continue
        dest = PDF_DIR / doi_fname(doi)
        if doi.lower() not in matched_doi:  # salin sekali per DOI (duplikat dilewati)
            shutil.copy2(src, dest)
            copied.append((stem, doi, dest.name))
        matched_doi.add(doi.lower())
        r = by_doi.get(doi.lower())
        if r:
            r["pdf_status"] = "downloaded_manual"
            r["pdf_path"] = str(dest.relative_to(ROOT / "kb"))
        else:
            unmatched.append(f"{stem} -> DOI {doi} tidak ada di manifest")

    # dokumen standalone (bukan DOI paper)
    standalone_dir = ROOT / "kb" / "raw" / "papers" / "standalone"
    standalone_dir.mkdir(parents=True, exist_ok=True)
    for stem in STANDALONE:
        src = SRC / f"{stem}.pdf"
        if src.exists():
            shutil.copy2(src, standalone_dir / f"{stem}.pdf")
            copied.append((stem, "(bukan DOI)", f"standalone/{stem}.pdf"))

    with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    print(f"Disalin: {len(copied)} file ke {PDF_DIR} (dan standalone/)")
    for stem, doi, name in copied:
        print(f"  {stem}.pdf -> {name}  ({doi})")
    if unmatched:
        print(f"\nTidak terproses ({len(unmatched)}):")
        for u in unmatched:
            print("  ", u)
    print(f"\nManifest diperbarui: {MANIFEST}")


if __name__ == "__main__":
    main()
