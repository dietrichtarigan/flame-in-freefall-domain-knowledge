#!/usr/bin/env python3
"""Ambil metadata, abstrak, dan PDF akses-terbuka untuk daftar DOI.

Membaca kb/manifest/doi_list.csv (kolom: doi, source, priority), menanyakan OpenAlex,
lalu:
  - menyimpan judul, tahun, jurnal, abstrak, status akses untuk SEMUA DOI
  - mengunduh PDF hanya bila ada salinan akses-terbuka yang sah
  - menandai sisanya 'manual' supaya bisa diambil lewat akses kampus

Hasil: kb/raw/papers/pdf/*.pdf dan kb/manifest/papers_doi.csv
Hanya butuh Python 3.9+. Aman dijalankan ulang.

  python scripts/papers_fetch.py --dry-run     # metadata + abstrak saja
  python scripts/papers_fetch.py               # + unduh PDF akses-terbuka
  python scripts/papers_fetch.py --priority 1  # hanya yang prioritas 1
"""
import argparse
import csv
import difflib
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "kb"
PDF_DIR = ROOT / "raw" / "papers" / "pdf"
MANIFEST = ROOT / "manifest"
UA = {"User-Agent": "Mozilla/5.0 (SpaceApps-2026 knowledge-base builder)"}
COLS = ["doi", "priority", "source", "title", "year", "journal", "oa_status", "pdf_status",
        "pdf_path", "oa_url", "doi_url", "abstract"]


# Cookie diperlukan: beberapa penerbit (Springer, Nature) mengalihkan lewat halaman cookie dulu
OPENER = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def http(url, timeout=60, retries=3, accept=None):
    last = None
    for i in range(retries):
        try:
            h = dict(UA)
            if accept:
                h["Accept"] = accept
            with OPENER.open(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 401, 403, 404):
                raise
            time.sleep(5 * (i + 1))  # 429 / 5xx: tunggu lalu coba lagi
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def norm(t):
    return re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).strip()


def candidates(doi, work, title):
    """Semua tempat sah yang mungkin menyimpan PDF akses-terbuka, urut dari yang paling pasti."""
    urls = []
    for loc in [work.get("best_oa_location") or {}] + (work.get("locations") or []):
        if loc.get("pdf_url"):
            urls.append(loc["pdf_url"])
        m = re.search(r"pmc/articles/(?:PMC)?(\d+)", loc.get("landing_page_url") or "")
        if m:  # salinan PubMed Central, lewat Europe PMC
            urls.append("https://europepmc.org/backend/ptpmcrender.fcgi?accid=PMC"
                        + m.group(1) + "&blobtype=pdf")
    oa = (work.get("open_access") or {})
    if oa.get("oa_url"):
        urls.append(oa["oa_url"])
    if oa.get("is_oa"):
        if doi.startswith("10.1007/"):
            urls.append("https://link.springer.com/content/pdf/" + doi + ".pdf")
        if doi.startswith("10.1038/"):
            urls.append("https://www.nature.com/articles/" + doi.split("/", 1)[1] + ".pdf")
    # Naskah versi NASA di NTRS (banyak penulisnya pegawai NASA): cocokkan judul
    if title:
        try:
            q = urllib.parse.urlencode({"q": title[:200], "page.size": 5})
            res = json.loads(http("https://ntrs.nasa.gov/api/citations/search?" + q)
                             .decode("utf-8")).get("results") or []
            for r in res:
                if difflib.SequenceMatcher(None, norm(r.get("title")), norm(title)).ratio() > 0.92:
                    for dl in r.get("downloads") or []:
                        link = (dl.get("links") or {}).get("pdf")
                        if link:
                            urls.append("https://ntrs.nasa.gov" + link)
        except Exception:
            pass
    seen, out = set(), []
    for u in urls:
        if u and u not in seen and "sciencedirect.com" not in u:  # ScienceDirect menolak skrip
            seen.add(u)
            out.append(u)
    return out


def abstract_of(inv):
    """OpenAlex menyimpan abstrak sebagai indeks terbalik {kata: [posisi]}."""
    if not inv:
        return ""
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="tanpa mengunduh PDF")
    ap.add_argument("--priority", help="hanya DOI dengan prioritas ini (mis. 1)")
    a = ap.parse_args()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    src = MANIFEST / "doi_list.csv"
    if not src.exists():
        print("Tidak ada", src)
        return 1
    with open(src, newline="", encoding="utf-8") as f:
        todo = [r for r in csv.DictReader(f) if not a.priority or r["priority"] == a.priority]

    prev = {}
    if (MANIFEST / "papers_doi.csv").exists():
        with open(MANIFEST / "papers_doi.csv", newline="", encoding="utf-8") as f:
            prev = {x["doi"].lower(): x for x in csv.DictReader(f)}
    out = []
    for n, r in enumerate(todo, 1):
        doi = r["doi"].strip().lower()
        row = dict.fromkeys(COLS, "")
        row.update(doi=doi, priority=r.get("priority", ""), source=r.get("source", ""),
                   doi_url="https://doi.org/" + doi, pdf_status="manual")
        dest = PDF_DIR / (re.sub(r"[^a-z0-9._-]+", "_", doi) + ".pdf")
        old = prev.get(doi)
        if old and old.get("title") and dest.exists() and dest.stat().st_size > 1000:
            old.update(priority=row["priority"], source=row["source"])
            if not old["pdf_status"].startswith("downloaded"):
                old.update(pdf_status="downloaded_manual", pdf_path=str(dest.relative_to(ROOT)))
            out.append(old)  # sudah lengkap: tidak perlu ditanyakan ulang
            continue
        w = {}
        try:
            url = ("https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/")
                   + "?select=title,publication_year,primary_location,open_access,"
                     "best_oa_location,locations,abstract_inverted_index")
            w = json.loads(http(url).decode("utf-8"))
            loc = w.get("primary_location") or {}
            oa = w.get("open_access") or {}
            best = w.get("best_oa_location") or {}
            row.update(title=w.get("title") or "", year=w.get("publication_year") or "",
                       journal=((loc.get("source") or {}).get("display_name")) or "",
                       oa_status=oa.get("oa_status") or ("oa" if oa.get("is_oa") else "closed"),
                       oa_url=best.get("pdf_url") or oa.get("oa_url") or "",
                       abstract=abstract_of(w.get("abstract_inverted_index")))
        except urllib.error.HTTPError as e:
            row["oa_status"] = "not_in_openalex" if e.code == 404 else f"error_{e.code}"
        except Exception as e:
            row["oa_status"] = "error " + repr(e)[:60]

        if dest.exists() and dest.stat().st_size > 1000:
            row.update(pdf_status="downloaded_manual", pdf_path=str(dest.relative_to(ROOT)))
        elif not a.dry_run:
            cands = candidates(doi, w, row["title"])
            if cands:
                row["pdf_status"] = "manual_oa_page"
            for u in cands:
                try:
                    data = http(u, timeout=120, retries=2, accept="application/pdf,*/*")
                except Exception:
                    continue
                if data[:5] == b"%PDF-":
                    dest.write_bytes(data)
                    row.update(pdf_status="downloaded", oa_url=u,
                               pdf_path=str(dest.relative_to(ROOT)))
                    break
        elif row["oa_url"]:
            row["pdf_status"] = "oa_available"
        out.append(row)
        if n % 20 == 0 or n == len(todo):
            print(f"  [{n}/{len(todo)}]")
        time.sleep(0.25)

    done = {r["doi"] for r in out}
    out += [x for d, x in prev.items() if d not in done]  # baris di luar filter tetap disimpan
    with open(MANIFEST / "papers_doi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)
    counts = {}
    for r in out:
        counts[r["pdf_status"]] = counts.get(r["pdf_status"], 0) + 1
    print("Selesai:", counts)
    need = [r for r in out if r["pdf_status"].startswith("manual") and r["priority"] == "1"]
    if need:
        print(f"\nPrioritas 1 yang perlu diambil manual ({len(need)}):")
        for r in need:
            print("  ", r["doi_url"], "|", (r["title"] or "")[:70])
        print("Simpan PDF-nya ke", PDF_DIR, "dengan nama apa saja.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
