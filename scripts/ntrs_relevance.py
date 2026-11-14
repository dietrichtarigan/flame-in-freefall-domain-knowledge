#!/usr/bin/env python3
"""Saring dokumen NTRS yang di luar topik pembakaran sebelum diindeks.

Kata kunci pendek (mis. "SoFIE") ikut menarik dokumen lain bernama sama (detektor sinar kosmik
SOFIE, logika orde tinggi, ...). Dokumen dinilai dari jumlah kata kunci pembakaran di teksnya:
  relevan    judul memuat kata kunci, atau >= 10 kemunculan DAN >= 1 per 10 ribu karakter
  lemah      >= 3 kemunculan dan >= 0,3 per 10 ribu karakter
  luar_topik sisanya
Kepadatan perlu: prosiding 1,2 juta karakter (konferensi sinar kosmik) punya 10 kemunculan
kebetulan (0,09 per 10 rb), sedangkan paper keselamatan api ~77 per 10 rb.
Yang 'luar_topik' dan 'lemah' ditulis ke kb/manifest/ntrs_offtopic.csv dan DILEWATI oleh
build_kb.py saat membangun indeks pencarian. Berkasnya tidak dihapus.

  python scripts/ntrs_relevance.py
"""
import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "kb"
KW = re.compile(r"\b(flame|combust|fire|ignit|burn|flammab|smold|droplet|soot|extinction)\w*", re.I)


def main():
    rows = list(csv.DictReader(open(KB / "manifest" / "ntrs_papers.csv", encoding="utf-8")))
    out, stat = [], Counter()
    for r in rows:
        p = (r.get("txt_path") or "").strip()
        f = KB / p if p else None
        if not (f and f.is_file()):
            stat["tanpa_teks"] += 1
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        n = len(KW.findall(text))
        dens = n / max(len(text), 1) * 1e4            # kemunculan per 10 ribu karakter
        if KW.search(r["title"] or "") or (n >= 10 and dens >= 1.0):
            k = "relevan"
        elif n >= 3 and dens >= 0.3:
            k = "lemah"
        else:
            k = "luar_topik"
        stat[k] += 1
        if k != "relevan":
            out.append({"id": r["id"], "label": k, "hits": n, "tags": r["tags"], "title": r["title"]})
    with open(KB / "manifest" / "ntrs_offtopic.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "label", "hits", "tags", "title"])
        w.writeheader(); w.writerows(out)
    print(dict(stat), "->", len(out), "dokumen dikecualikan dari indeks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
