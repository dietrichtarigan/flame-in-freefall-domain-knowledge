#!/usr/bin/env python3
"""Kumpulkan paper/laporan dari NASA Technical Reports Server (NTRS).

Menyimpan metadata JSON, PDF, dan teks polos tiap dokumen. Hanya butuh
Python 3.9+. Aman dijalankan ulang (file yang sudah ada dilewati).

Contoh:
  python scripts/ntrs_fetch.py --dry-run        # hanya metadata + daftar
  python scripts/ntrs_fetch.py                  # + unduh PDF dan teks
  python scripts/ntrs_fetch.py --per-query 80   # lebih banyak per kata kunci
"""
import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://ntrs.nasa.gov"
UA = {"User-Agent": "Mozilla/5.0 (SpaceApps-2026 knowledge-base builder)"}
ROOT = Path(__file__).resolve().parent.parent / "kb"
RAW = ROOT / "raw" / "ntrs"
MANIFEST = ROOT / "manifest"

# Kata kunci per eksperimen. Tambah/ubah sesuka hati lalu jalankan ulang.
QUERIES = {
    "BASS": "Burning and Suppression of Solids BASS microgravity",
    "BASS-II": "BASS-II flame spread microgravity solid fuel",
    "FLEX": "Flame Extinguishment Experiment FLEX droplet combustion",
    "FLEX-2": "FLEX-2 droplet combustion microgravity",
    "Cool flames": "cool flame droplet combustion microgravity",
    "ACME": "Advanced Combustion via Microgravity Experiments ACME",
    "ACME s-Flame": "spherical diffusion flames microgravity s-Flame",
    "ACME BRE": "Burning Rate Emulator microgravity",
    "ACME E-FIELD": "electric field effects laminar diffusion flames microgravity",
    "ACME CLD": "coflow laminar diffusion flame microgravity",
    "Flame Design": "Flame Design microgravity soot spherical flame",
    "Saffire": "Saffire spacecraft fire experiment large scale flammability",
    "SoFIE": "Solid Fuel Ignition and Extinction SoFIE",
    "Confined Combustion": "confined combustion flame spread microgravity",
    "SAME": "Smoke Aerosol Measurement Experiment spacecraft smoke detection",
    "SPICE": "Smoke Point In Coflow Experiment",
    "SLICE": "Structure and Liftoff In Combustion Experiment",
    "DAFT": "Dust and Aerosol Measurement Feasibility Test",
    "Fire safety": "spacecraft fire safety microgravity material flammability",
    "Partial gravity": "partial gravity lunar Martian material flammability flame spread",
    "Exploration atmosphere": "exploration atmosphere oxygen pressure flammability spacecraft",
    "NASA-STD-6001": "NASA-STD-6001 upward flame propagation test microgravity",
    "Extinction limits": "flammability limits low velocity flow microgravity quenching",
    "Fire suppression": "fire suppression extinguisher microgravity spacecraft",
    # Kata kunci pendek: pencarian NTRS menuntut semua kata cocok, jadi yang panjang terlalu sempit
    "Saffire (short)": "Saffire",
    "BASS (short)": "BASS-II",
    "FLEX (short)": "FLEX droplet",
    "SoFIE (short)": "SoFIE flame",   # "SoFIE" saja menarik detektor sinar kosmik SOFIE (47 dok. luar topik)
    "Droplet": "droplet combustion microgravity",
    "Flame spread": "microgravity flame spread",
    "Solid flammability": "material flammability microgravity",
    "Spacecraft fire": "spacecraft fire safety",
    "Smoke detection": "spacecraft smoke detection",
    "Lunar gravity": "lunar gravity flammability",
    "Narrow channel": "narrow channel apparatus flame",
    "Oxygen index": "limiting oxygen microgravity",
    # tambahan 2026-11-11: celah bahan padat, kabel, dan pengujian di darat
    "PMMA": "PMMA flame spread microgravity",
    "SIBAL": "cotton fiberglass SIBAL",
    "Opposed flow": "opposed flow flame spread",
    "Concurrent flow": "concurrent flow flame spread",
    "Wire insulation": "wire insulation flammability microgravity",
    "FLARE": "FLARE JAXA flammability",
    "Smoldering": "smoldering microgravity",
    "Mars gravity": "Martian gravity flammability",
    "Drop tower": "drop tower combustion",
    "Parabolic flight": "parabolic flight flame",
    "CIR": "Combustion Integrated Rack",
    "MSG combustion": "Microgravity Science Glovebox combustion",
    "Radiative extinction": "radiative extinction flame microgravity",
    "Ignition solid": "ignition solid fuel microgravity",
    "Cool flame gas": "cool flame gaseous fuel microgravity",
}


def http(url, timeout=90, retries=4):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                raise
        except Exception as e:
            last = e
        time.sleep(2 * (i + 1))
    raise last


def search(q, n):
    out, start = [], 0
    while len(out) < n:
        size = min(100, n - len(out))
        url = HOST + "/api/citations/search?" + urllib.parse.urlencode(
            {"q": q, "page.size": size, "page.from": start})
        res = json.loads(http(url).decode("utf-8")).get("results") or []
        if not res:
            break
        out += res
        start += len(res)
        if len(res) < size:
            break
    return out


def save(url_path, dest):
    if dest.exists() and dest.stat().st_size > 0:
        return "exists"
    try:
        data = http(HOST + url_path if url_path.startswith("/") else url_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return "downloaded"
    except Exception as e:
        return "failed: " + repr(e)[:100]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--per-query", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true", help="tanpa mengunduh PDF/teks")
    ap.add_argument("--no-pdf", action="store_true", help="hanya teks polos, tanpa PDF")
    a = ap.parse_args()
    for d in (RAW / "citations", RAW / "pdf", RAW / "txt", MANIFEST):
        d.mkdir(parents=True, exist_ok=True)

    docs = {}
    for tag, q in QUERIES.items():
        try:
            res = search(q, a.per_query)
        except Exception as e:
            print(f"GAGAL cari '{tag}': {e!r}")
            continue
        new = 0
        for r in res:
            cid = str(r.get("id"))
            if cid not in docs:
                docs[cid] = {"rec": r, "tags": []}
                new += 1
            docs[cid]["tags"].append(tag)
        print(f"{tag:24s} {len(res):3d} hasil, {new:3d} baru")
        time.sleep(0.5)

    rows = []
    for i, (cid, d) in enumerate(sorted(docs.items()), 1):
        r = d["rec"]
        (RAW / "citations" / f"{cid}.json").write_text(
            json.dumps(r, indent=1), encoding="utf-8")
        links = {}
        for dl in r.get("downloads") or []:
            links = dl.get("links") or {}
            if links.get("pdf") or links.get("fulltext"):
                break
        authors = "; ".join(
            (x.get("meta", {}).get("author", {}) or {}).get("name", "")
            for x in (r.get("authorAffiliations") or []))
        pubs = r.get("publications") or [{}]
        row = {"id": cid, "title": r.get("title", ""),
               "year": (pubs[0].get("publicationDate") or r.get("distributionDate")
                        or r.get("created") or "")[:4],
               "authors": authors, "sti_type": r.get("stiType", ""),
               "tags": "|".join(d["tags"]),
               "record_url": f"{HOST}/citations/{cid}",
               "pdf_status": "none", "txt_status": "none",
               "pdf_path": "", "txt_path": ""}
        if not a.dry_run:
            if links.get("pdf") and not a.no_pdf:
                p = RAW / "pdf" / f"{cid}.pdf"
                row["pdf_status"] = save(links["pdf"], p)
                row["pdf_path"] = str(p.relative_to(ROOT))
            if links.get("fulltext"):
                p = RAW / "txt" / f"{cid}.txt"
                row["txt_status"] = save(links["fulltext"], p)
                row["txt_path"] = str(p.relative_to(ROOT))
            if i % 25 == 0:
                print(f"  [{i}/{len(docs)}] diunduh")
            time.sleep(0.3)
        else:
            row["pdf_status"] = "available" if links.get("pdf") else "none"
            row["txt_status"] = "available" if links.get("fulltext") else "none"
        rows.append(row)

    with open(MANIFEST / "ntrs_papers.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)
    print(f"Selesai: {len(rows)} dokumen unik. Manifest: {MANIFEST / 'ntrs_papers.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
