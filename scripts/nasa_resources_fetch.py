#!/usr/bin/env python3
"""Ambil sumber resmi NASA yang didaftarkan panitia (tab Resources) ke workspace.

Sumber-sumber ini bukan data uji, melainkan konteks naratif dan sejarah yang
dibutuhkan untuk menafsirkan data: latar tiap investigasi, tiga kecelakaan
kebakaran (Apollo 1, Apollo 13, Mir), dan contoh alih-teknologi NASA ke
pemadam kebakaran di Bumi. Brief meminta dashboard juga membahas penerapan
data PSI untuk keselamatan kebakaran di Bumi, jadi halaman Spinoff ikut diambil.

Menyimpan HTML mentah + teks bersih, supaya bisa dimasukkan ke indeks pencarian
paper (paper_search) tanpa perlu mengambil ulang dari internet saat hari-H.

  python scripts/nasa_resources_fetch.py
"""
import csv
import html
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "kb" / "raw" / "nasa_resources"
UA = {"User-Agent": "Mozilla/5.0 (SpaceApps-2026 knowledge-base builder)",
      "Accept": "text/html,application/xhtml+xml,application/pdf,*/*"}

SOURCES = [
    ("psi_repo_search", "https://psi.nasa.gov/physci/repo/search?q=combustion",
     "repositori", "Halaman pencarian PSI (aplikasi JavaScript; isinya diambil lewat API)"),
    ("nasa_combustion_science",
     "https://www.nasa.gov/glenn/glenn-expertise-space-exploration/physical-sciences-program/combustion-science/",
     "latar", "Informasi dasar sebagian besar investigasi pembakaran di PSI"),
    ("sciencecasts_video", "https://www.youtube.com/watch?v=W1oXykoz9zg",
     "video", "NASA ScienceCasts: The Power of Studying Combustion on the ISS (2018, 3,6 menit)"),
    ("researchers_guide",
     "https://www.nasa.gov/missions/station/a-researchers-guide-to-combustion-science/",
     "panduan", "A Researcher's Guide to ISS Combustion Science (2015, 50+ halaman)"),
    ("apollo_1", "https://sma.nasa.gov/sma-disciplines/accllp/apollo-1",
     "kecelakaan", "Apollo 1: kebakaran saat uji pra-peluncuran, awak gugur, investigasi, pelajaran"),
    ("apollo_13", "https://sma.nasa.gov/sma-disciplines/accllp/apollo-13",
     "kecelakaan", "Apollo 13: ledakan tangki oksigen dalam perjalanan ke Bulan"),
    ("mir_fire", "https://www.nasa.gov/history/25-years-ago-fire-aboard-space-station-mir/",
     "kecelakaan", "Kebakaran di Mir 1997 akibat kegagalan generator oksigen"),
    ("spinoff_air_tanks", "https://spinoff.nasa.gov/node/9582",
     "spinoff", "Tangki udara pemadam kebakaran dari teknologi baju antariksa (1970-an)"),
    ("spinoff_fire_detector", "https://spinoff.nasa.gov/node/9407",
     "spinoff", "Detektor asap shuttle yang membedakan asap dari debu (1970-an)"),
    ("spinoff_fire_attire", "https://spinoff.nasa.gov/node/9918",
     "spinoff", "Pakaian pemadam kebakaran dari teknologi baju antariksa (1980-an)"),
]


def http(url, timeout=60, retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read(), r.headers.get("Content-Type", "")
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (401, 403, 404):
                raise
            time.sleep(3 * (i + 1))
        except Exception as e:
            last = e
            time.sleep(2 * (i + 1))
    raise last


def to_text(raw):
    """HTML -> teks bersih tanpa pustaka tambahan."""
    s = raw.decode("utf-8", errors="replace")
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)\s*>", "\n", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r"\n\s*\n\s*\n+", "\n\n", s)
    return s.strip()


def find_pdfs(raw, base):
    """Tautan PDF di halaman (mis. Researcher's Guide)."""
    s = raw.decode("utf-8", errors="replace")
    urls = set()
    for m in re.finditer(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', s, re.I):
        u = m.group(1)
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = re.match(r"(https?://[^/]+)", base).group(1) + u
        elif not u.startswith("http"):
            continue
        urls.add(u)
    return sorted(urls)


def main():
    (OUT / "html").mkdir(parents=True, exist_ok=True)
    (OUT / "text").mkdir(parents=True, exist_ok=True)
    (OUT / "pdf").mkdir(parents=True, exist_ok=True)
    rows = []
    for n, (key, url, kind, desc) in enumerate(SOURCES, 1):
        rec = {"key": key, "url": url, "kind": kind, "description": desc,
               "status": "", "bytes": 0, "text_chars": 0,
               "html_path": "", "text_path": "", "pdf_links": ""}
        try:
            raw, ctype = http(url)
            rec["bytes"] = len(raw)
            if "pdf" in ctype.lower():
                p = OUT / "pdf" / f"{key}.pdf"
                p.write_bytes(raw)
                rec.update(status="pdf", html_path=str(p.relative_to(ROOT / "kb")))
            else:
                hp = OUT / "html" / f"{key}.html"
                hp.write_bytes(raw)
                txt = to_text(raw)
                tp = OUT / "text" / f"{key}.txt"
                tp.write_text(txt, encoding="utf-8")
                pdfs = find_pdfs(raw, url)
                rec.update(status="ok", text_chars=len(txt),
                           html_path=str(hp.relative_to(ROOT / "kb")),
                           text_path=str(tp.relative_to(ROOT / "kb")),
                           pdf_links=" ".join(pdfs[:6]))
        except Exception as e:
            rec["status"] = "gagal: " + repr(e)[:90]
        rows.append(rec)
        print(f"  [{n}/{len(SOURCES)}] {rec['status'][:28]:28s} {rec['text_chars']:>7} aksara  {key}")

    man = ROOT / "kb" / "manifest" / "nasa_resources.csv"
    with open(man, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    ok = sum(1 for r in rows if r["status"] in ("ok", "pdf"))
    print(f"\n{ok}/{len(rows)} sumber tersimpan. Manifest: {man}")
    pl = [r for r in rows if r["pdf_links"]]
    if pl:
        print("\nTautan PDF yang ditemukan di halaman (unduh terpisah bila perlu):")
        for r in pl:
            print(f"  {r['key']}: {r['pdf_links'][:150]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
