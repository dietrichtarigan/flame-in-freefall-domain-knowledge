#!/usr/bin/env python3
"""Integrasikan sekumpulan PDF paper ke kb/raw/papers/pdf/ secara otomatis.

Tiga batch pertama memakai peta nama->DOI yang ditulis tangan. Untuk batch
besar (196 berkas) cara itu tidak lagi masuk akal, jadi skrip ini membaca
DOI langsung dari halaman pertama PDF.

Paper tanpa DOI tercetak (makalah konferensi AIAA/SAE dan prosiding lama)
tidak dibuang: diberi kunci lokal `local/<nama berkas>` supaya tetap masuk
indeks pencarian teks. Kolom `doi_url` sengaja dikosongkan untuk paper
semacam itu, supaya antarmuka tidak pernah menampilkan tautan DOI palsu.

  python scripts/integrate_papers_auto.py --src arsip/batch4_staging
  python scripts/integrate_papers_auto.py --src <folder> --dry-run
"""
import argparse
import csv
import re
import shutil
import sys
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "kb" / "raw" / "papers" / "pdf"
MANIFEST = ROOT / "kb" / "manifest" / "papers_doi.csv"
COLS = ["doi", "priority", "source", "title", "year", "journal", "oa_status",
        "pdf_status", "pdf_path", "oa_url", "doi_url", "abstract"]

DOI_RE = re.compile(r"\b(10\.\d{4,9}/[-._;()/:A-Za-z0-9]+)")
YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
# Baris yang jelas bukan judul: penerbit, hak cipta, nomor halaman, URL.
JUNK = re.compile(r"(?i)^(available online|contents lists|journal homepage|www\.|https?:|"
                  r"doi|copyright|©|issn|isbn|all rights|proceedings of the combustion institute \d|"
                  r"american institute of aeronautics|\d+\s*$|page \d+|crossmark|"
                  r"check for updates|downloaded from|view online)")


# Nama jurnal sering dicetak sebesar judul; dibuang bila menempel di awal.
JOURNALS = ("Combustion Science and Technology", "Combustion and Flame",
            "Fire Safety Journal", "Proceedings of the Combustion Institute",
            "Microgravity Science and Technology", "Combustion Theory and Modelling",
            "Scientific Reports", "Energy & Fuels", "Fire Technology",
            "Journal of Aerosol Science", "Progress in Energy and Combustion Science",
            "International Journal of Heat and Mass Transfer")


def head_text(path, pages=2):
    doc = fitz.open(path)
    t = "\n".join(doc[i].get_text() for i in range(min(pages, len(doc))))
    doc.close()
    return t


def find_doi(text):
    """DOI pertama yang masuk akal, dicari BARIS DEMI BARIS.

    Versi pertama menghapus newline lebih dulu, sehingga DOI menyambung ke teks
    baris berikutnya dan menghasilkan kunci palsu seperti
    "10.1196/annals.1362.037570DUNN-RANKIN" -- beserta doi_url yang mati.

    Tetapi per baris saja juga belum cukup: DOI yang terbungkus ke baris
    berikutnya jadi terpenggal ("10.1146/annurev-chembioeng-"). Maka hasil yang
    terlihat belum utuh dicoba ulang pada baris yang sudah disambung.
    """
    lines = text.split("\n")

    def clean(m):
        return m.group(1).rstrip(".,;)")

    def looks_cut(d):
        tail = d.split("/", 1)[1] if "/" in d else ""
        return d.endswith(("-", ".", "_")) or len(tail) < 6

    for i, line in enumerate(lines):
        m = DOI_RE.search(line)
        if not m:
            continue
        doi = clean(m)
        if looks_cut(doi) and i + 1 < len(lines):
            joined = line.rstrip() + lines[i + 1].strip()
            m2 = DOI_RE.search(joined)
            if m2 and len(clean(m2)) > len(doi):
                doi = clean(m2)
        # Masih terlihat terpenggal setelah disambung? Lebih baik mengaku tidak
        # punya DOI (kunci lokal) daripada menyimpan tautan doi.org yang mati.
        return None if looks_cut(doi) else doi
    return None


def title_by_font(path):
    """Judul = teks dengan ukuran font terbesar di halaman pertama.

    Jauh lebih andal daripada menebak dari panjang baris: judul paper memang
    dicetak paling besar, sedangkan teks isi seragam kecil. Menebak dari
    panjang baris sebelumnya menghasilkan potongan teks isi yang acak.
    """
    doc = fitz.open(path)
    spans = []
    for b in doc[0].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l.get("spans", []):
                t = sp["text"].strip()
                # Huruf hiasan (drop cap) dicetak paling besar dan akan
                # mengalahkan judul; potongan 1-2 aksara dibuang lebih dulu.
                if len(t) > 2:
                    spans.append((round(sp["size"], 1), sp["bbox"][1], sp["bbox"][0], t))
    doc.close()
    if not spans:
        return ""
    top = max(s[0] for s in spans)
    parts = [t for sz, y, x, t in sorted(spans, key=lambda s: (s[1], s[2]))
             if sz == top and not JUNK.match(t)]
    title = re.sub(r"\s+", " ", " ".join(parts)).strip()
    for j in JOURNALS:
        if title.lower().startswith(j.lower()):
            title = title[len(j):].strip(" -–—:|")
    return title[:300]


def safe_name(key):
    return re.sub(r"[^a-z0-9._-]+", "_", key.lower()) + ".pdf"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", required=True, help="folder berisi PDF")
    ap.add_argument("--source-tag", default="manual-batch", help="nilai kolom source")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if fitz is None:
        print("Butuh pymupdf: pip install pymupdf")
        return 1

    src = Path(a.src) if Path(a.src).is_absolute() else ROOT / a.src
    pdfs = sorted(src.rglob("*.pdf"))
    if not pdfs:
        print("Tidak ada PDF di", src)
        return 1

    rows = list(csv.DictReader(open(MANIFEST, encoding="utf-8")))
    by_key = {r["doi"].strip().lower(): r for r in rows}
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    added, updated, skipped, nodoi, failed = [], [], [], [], []
    seen = set()
    for p in pdfs:
        try:
            text = head_text(p)
        except Exception as e:
            failed.append((p.name, repr(e)[:60]))
            continue
        doi = find_doi(text)
        key = (doi or f"local/{p.stem}").lower()
        if key in seen:                      # duplikat di dalam batch ini
            skipped.append((p.name, key, "duplikat dalam batch"))
            continue
        seen.add(key)
        if not doi:
            nodoi.append(p.name)

        dest = PDF_DIR / safe_name(key)
        r = by_key.get(key)
        if r and r.get("pdf_status") in ("downloaded", "downloaded_manual") and dest.exists():
            skipped.append((p.name, key, "sudah ada PDF"))
            continue

        if not a.dry_run:
            shutil.copy2(p, dest)
        try:
            auto_title = title_by_font(p)
        except Exception:
            auto_title = ""
        title = (r or {}).get("title") or auto_title
        ym = YEAR_RE.search(text[:1200])
        if r:
            r.update(pdf_status="downloaded_manual",
                     pdf_path=str(dest.relative_to(ROOT / "kb")),
                     title=title or r.get("title", ""))
            updated.append((p.name, key))
        else:
            rows.append({"doi": doi or f"local/{p.stem}", "priority": "3",
                         "source": a.source_tag, "title": title,
                         "year": ym.group(1) if ym else "", "journal": "",
                         "oa_status": "", "pdf_status": "downloaded_manual",
                         "pdf_path": str(dest.relative_to(ROOT / "kb")),
                         "oa_url": "", "doi_url": f"https://doi.org/{doi}" if doi else "",
                         "abstract": ""})
            added.append((p.name, key))

    if not a.dry_run:
        with open(MANIFEST, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLS)
            w.writeheader()
            w.writerows(rows)

    print(f"{len(pdfs)} PDF diperiksa{' (DRY RUN)' if a.dry_run else ''}")
    print(f"  baru ditambahkan : {len(added)}")
    print(f"  diperbarui       : {len(updated)}  (DOI sudah terdaftar, PDF kini ada)")
    print(f"  dilewati         : {len(skipped)}")
    print(f"  gagal dibaca     : {len(failed)}")
    print(f"  tanpa DOI tercetak: {len(nodoi)} -> diberi kunci local/<nama>")
    if updated[:6]:
        print("\nContoh yang melengkapi entri lama:")
        for n, k in updated[:6]:
            print(f"  {n[:38]:40s} {k}")
    if failed:
        print("\nGagal dibaca:")
        for n, e in failed[:5]:
            print(f"  {n[:40]:42s} {e}")
    tot = sum(1 for r in rows if r["pdf_status"] in ("downloaded", "downloaded_manual"))
    print(f"\nTotal paper dengan PDF di manifest: {tot} dari {len(rows)} entri")
    return 0


if __name__ == "__main__":
    sys.exit(main())
