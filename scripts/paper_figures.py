#!/usr/bin/env python3
"""Ambil gambar (figure) dari PDF paper + caption-nya, supaya asisten bisa menunjukkan gambar asli.

Cara kerja (mirip pdffigures: berjangkar pada caption, bukan pada gambar raster):
  1. Posisi tiap baris teks dibaca dengan poppler `pdftohtml -xml` (satuan poin).
  2. Baris yang diawali "Figure N", "Fig. N" atau "Gambar N" dianggap caption; baris daftar isi
     (titik-titik pemandu, nomor halaman di ujung) dibuang.
  3. Area gambar = ruang di ATAS caption sampai baris teks badan terdekat. Label sumbu di dalam
     grafik tidak dihitung sebagai pembatas (baris pendek/sempit). Bila ruangnya terlalu kecil,
     dicoba area di BAWAH caption.
  4. Area itu dipotret dengan `pdftoppm` (150 dpi) — grafik vektor ikut tertangkap.
  5. Kalimat di badan paper yang menyebut "Figure N" disimpan sebagai konteks pencarian.

Keluaran: analysis/figures/<paper>/p<hal>_<label>.png dan analysis/figures/figures.json.
Setiap gambar membawa judul paper, DOI (bila ada di basis data), halaman, dan caption asli.
Ini heuristik: periksa hasilnya; gambar yang terpotong salah bisa dihapus dari figures.json.

  python scripts/paper_figures.py --pdf "kb/raw/.../paper.pdf"     # satu atau beberapa berkas
  python scripts/paper_figures.py --dir "D:/papers"                 # semua PDF di folder (rekursif)
  python scripts/paper_figures.py --from-db                         # PDF yang tercatat di freefall.sqlite
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbpaths import gold_db  # noqa: E402
GOLD = gold_db()
OUT = ROOT / "analysis" / "figures"
INDEX = OUT / "figures.json"
DPI = 150

# huruf kapital setelah nomor HARUS kapital sungguhan ((?-i:...)), supaya "Figure 17 shows ..." di badan teks tidak lolos
CAPTION = re.compile(r"^\s*(fig(?:ure)?\.?|gambar)\s*(\d+(?:\.\d+)?[a-z]?)\s*([.:|\-–—](?!\d)|\s+(?-i:[A-Z(]))", re.I)
TOC = re.compile(r"\.{4,}|\s\d+\s*$")
MENTION = re.compile(r"(?:Fig(?:ure)?s?\.?|Gambar)\s*(\d+(?:\.\d+)?[a-z]?)", re.I)


def tool(name):
    """Cari biner poppler (PATH, lalu lokasi MiKTeX yang umum di Windows)."""
    p = shutil.which(name)
    if p and name != "pdftotext":
        return p
    for base in (Path.home() / "AppData/Local/Programs/MiKTeX/miktex/bin/x64", Path("C:/Program Files/MiKTeX/miktex/bin/x64")):
        if (base / f"{name}.exe").exists():
            return str(base / f"{name}.exe")
    return p


def pages_lines(pdf):
    """[(nomor halaman, lebar, tinggi, [baris])]; baris = dict(top, bottom, left, right, text). Satuan poin."""
    xml = subprocess.run([tool("pdftohtml"), "-xml", "-i", "-q", "-zoom", "1", "-stdout", str(pdf)],
                         capture_output=True, timeout=300).stdout.decode("utf-8", "replace")
    xml = re.sub(r"<!DOCTYPE[^>]*>", "", xml)
    xml = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", xml)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return []
    out = []
    for pg in root.iter("page"):
        items = []
        for t in pg.iter("text"):
            txt = "".join(t.itertext()).strip()
            if not txt:
                continue
            top, left, w, h = (float(t.get(k, 0)) for k in ("top", "left", "width", "height"))
            items.append({"top": top, "bottom": top + h, "left": left, "right": left + w, "text": txt})
        items.sort(key=lambda x: (round(x["top"]), x["left"]))
        lines = []                                      # gabungkan potongan teks yang sebaris
        for it in items:
            if lines and abs(it["top"] - lines[-1]["top"]) < 2.5 and it["left"] - lines[-1]["right"] < 40:
                L = lines[-1]
                L.update(bottom=max(L["bottom"], it["bottom"]), right=max(L["right"], it["right"]), text=L["text"] + " " + it["text"])
            else:
                lines.append(dict(it))
        out.append((int(pg.get("number")), float(pg.get("width")), float(pg.get("height")), lines))
    return out


def is_body(line, page_w):
    """Baris teks badan (bukan label sumbu/angka di dalam grafik)."""
    return (line["right"] - line["left"]) > 0.40 * page_w or len(line["text"]) > 70


def caption_block(lines, i):
    """Caption = baris i + baris berikutnya yang rapat dan sejajar (maks 8 baris)."""
    cap, last = [lines[i]], lines[i]
    for L in lines[i + 1:i + 9]:
        if L["top"] - last["bottom"] > 6 or L["left"] < cap[0]["left"] - 30 or CAPTION.match(L["text"]):
            break
        cap.append(L)
        last = L
    text = re.sub(r"\s+", " ", " ".join(c["text"] for c in cap)).strip()
    return text, cap[0]["top"], cap[-1]["bottom"]


def regions(lines, page_w, page_h, cap_top, cap_bottom):
    """Kandidat area gambar [(x0, y0, x1, y1, posisi)] dalam poin: di atas caption, lalu di bawahnya."""
    margin, out = 30, []
    above = [L for L in lines if L["bottom"] <= cap_top - 2 and is_body(L, page_w) and not CAPTION.match(L["text"])]
    y0 = max((L["bottom"] for L in above), default=margin) + 4
    if cap_top - y0 >= 50:
        out.append((margin, y0, page_w - margin, cap_top - 3, "above"))
    below = [L for L in lines if L["top"] >= cap_bottom + 2 and is_body(L, page_w)]   # tabel/gambar di bawah caption
    y1 = min((L["top"] for L in below), default=page_h - margin) - 4
    if y1 - cap_bottom >= 50:
        out.append((margin, cap_bottom + 3, page_w - margin, y1, "below"))
    return out


def ink(png):
    """Fraksi piksel yang tidak putih — potongan kosong (< ~1,5 %) dibuang."""
    from PIL import Image
    im = Image.open(png).convert("L")
    im.thumbnail((300, 300))
    px = list(im.getdata())
    return sum(1 for p in px if p < 235) / max(1, len(px))


def render(pdf, page, box, dest):
    s = DPI / 72.0
    x0, y0, x1, y1 = box
    dest.parent.mkdir(parents=True, exist_ok=True)
    base = str(dest.with_suffix(""))
    subprocess.run([tool("pdftoppm"), "-png", "-singlefile", "-r", str(DPI), "-f", str(page), "-l", str(page),
                    "-x", str(int(x0 * s)), "-y", str(int(y0 * s)), "-W", str(int((x1 - x0) * s)), "-H", str(int((y1 - y0) * s)),
                    str(pdf), base], capture_output=True, timeout=120)
    return dest.exists()


def paper_meta():
    """pdf_path (dinormalkan) -> {title, doi, url, source}."""
    meta = {}
    if not GOLD.exists():
        return meta
    con = sqlite3.connect(GOLD)
    for doi, title, path, url in con.execute("SELECT doi, title, pdf_path, doi_url FROM papers_doi WHERE pdf_path IS NOT NULL AND pdf_path != ''"):
        meta[Path(path.replace("\\", "/")).name.lower()] = {"title": title, "doi": doi, "url": url or f"https://doi.org/{doi}", "source": "doi"}
    for pid, title, path, url in con.execute("SELECT id, title, pdf_path, record_url FROM papers WHERE pdf_path IS NOT NULL AND pdf_path != ''"):
        meta.setdefault(Path(path.replace("\\", "/")).name.lower(), {"title": title, "doi": None, "url": url, "source": f"ntrs:{pid}"})
    meta["_psi"] = {acc: (acr or title, url, doi) for acc, acr, title, url, doi in
                    con.execute("SELECT accession, acronym, title, psi_url, doi FROM investigations")}
    return meta


def file_meta(pdf, meta):
    """Metadata untuk PDF yang tidak tercatat sebagai paper: berkas PSI -> halaman investigasinya."""
    m = re.search(r"(PSI-\d+)", pdf.name)
    if m and m.group(1) in meta.get("_psi", {}):
        name, url, doi = meta["_psi"][m.group(1)]
        title = re.sub(r"^PSI-\d+_[^_]+_", "", pdf.stem).replace("_", " ")
        return {"title": f"{title} ({m.group(1)} {name})", "doi": doi, "url": url or (f"https://doi.org/{doi}" if doi else None),
                "source": f"psi:{m.group(1)}"}
    return {}


def db_pdfs():
    con = sqlite3.connect(GOLD)
    paths = [r[0] for r in con.execute("SELECT pdf_path FROM papers_doi WHERE pdf_path IS NOT NULL AND pdf_path != '' "
                                       "UNION SELECT pdf_path FROM papers WHERE pdf_path IS NOT NULL AND pdf_path != ''")]
    out = []
    for p in paths:
        p = p.replace("\\", "/")                     # katalog ditulis di Windows: raw\papers\pdf\...
        for cand in (Path(p), ROOT / p, ROOT / "kb" / p):
            if cand.exists():
                out.append(cand)
                break
    return out


def slug(pdf):
    s = re.sub(r"[^A-Za-z0-9]+", "_", pdf.stem)[:60].strip("_")
    return f"{s}_{hashlib.sha1(str(pdf.resolve()).encode()).hexdigest()[:6]}"


def extract(pdf, meta):
    pl = pages_lines(pdf)
    if not pl:
        return [], "pdftohtml gagal / tidak ada teks (PDF hasil scan?)"
    body = " ".join(L["text"] for _, _, _, lines in pl for L in lines)
    sentences = re.split(r"(?<=[.!?])\s+", body)
    m = meta.get(pdf.name.lower()) or file_meta(pdf, meta)
    figs, seen = [], set()
    for page, pw, ph, lines in pl:
        # halaman daftar gambar/isi: banyak baris mirip caption -> bukan caption sungguhan
        n_cap = sum(1 for L in lines if CAPTION.match(L["text"]))
        if n_cap >= 4 or any(re.search(r"\b(list of (figures|illustrations)|table of contents|daftar (gambar|isi))\b", L["text"], re.I) for L in lines):
            continue
        for i, L in enumerate(lines):
            mm = CAPTION.match(L["text"])
            if not mm or TOC.search(L["text"]):
                continue
            label = f"{'Figure' if mm.group(1).lower().startswith('f') else 'Gambar'} {mm.group(2)}"
            if label in seen:                          # label yang sama dua kali = rujukan, bukan caption
                continue
            cap, ct, cb = caption_block(lines, i)
            rel = Path(slug(pdf)) / f"p{page}_{re.sub(r'[^A-Za-z0-9.]', '', label)}.png"
            best = None                                # render tiap kandidat area, ambil yang paling berisi
            for k, cand in enumerate(regions(lines, pw, ph, ct, cb)):
                tmp = OUT / rel.with_name(rel.stem + f"_c{k}.png")
                if render(pdf, page, cand[:4], tmp):
                    v = ink(tmp)
                    if best is None or v > best[0]:
                        if best:
                            best[2].unlink(missing_ok=True)
                        best = (v, cand, tmp)
                    else:
                        tmp.unlink(missing_ok=True)
            if not best or best[0] < 0.015:
                if best:
                    best[2].unlink(missing_ok=True)
                continue
            box = best[1]
            best[2].replace(OUT / rel)
            seen.add(label)
            num = mm.group(2)
            ctx = [s.strip() for s in sentences if any(x.group(1) == num for x in MENTION.finditer(s)) and not CAPTION.match(s)][:2]
            figs.append({"id": f"{slug(pdf)}:{label}", "label": label, "page": page, "caption": cap[:900],
                         "mentions": [c[:400] for c in ctx], "png": rel.as_posix(), "region": box[4],
                         "bbox_pt": [round(v, 1) for v in box[:4]],
                         "paper": {"title": m.get("title") or pdf.stem, "doi": m.get("doi"), "url": m.get("url"),
                                   "source": m.get("source", "file"), "pdf": os.path.relpath(pdf, ROOT).replace("\\", "/")},
                         "method": "caption-anchored crop (pdftohtml -xml + pdftoppm)"})
    return figs, None


# ---------------------------------------------------------------- persamaan bernomor
EQNUM = re.compile(r"^\(?\s*(\d+(?:\.\d+)?[a-z]?)\s*\)\s*,?\s*$")


def extract_equations(pdf, meta):
    """Persamaan bernomor: nomor "(N)" sendirian di margin kanan; area = baris non-badan di sekitarnya.
    Disimpan sebagai POTRET ASLI dari PDF (tidak diketik ulang) + teks mentah + kalimat penjelas."""
    m = meta.get(pdf.name.lower()) or file_meta(pdf, meta)
    out, seen = [], set()
    for page, pw, ph, lines in pages_lines(pdf):
        if sum(1 for L in lines if CAPTION.match(L["text"])) >= 4:          # halaman daftar isi/gambar
            continue
        for i, L in enumerate(lines):
            mm = EQNUM.match(L["text"])
            if not mm or L["left"] < 0.7 * pw or mm.group(1) in seen:
                continue
            top, bot = L["top"] - 4, L["bottom"] + 4
            body_above = [x for x in lines if x["bottom"] <= L["top"] and is_body(x, pw)]
            body_below = [x for x in lines if x["top"] >= L["bottom"] and is_body(x, pw)]
            lim_top = max((x["bottom"] for x in body_above), default=30) + 1
            lim_bot = min((x["top"] for x in body_below), default=ph - 30) - 1
            parts = [x for x in lines if x is not L and x["bottom"] > lim_top and x["top"] < lim_bot
                     and not is_body(x, pw) and abs((x["top"] + x["bottom"]) / 2 - (L["top"] + L["bottom"]) / 2) < 40]
            if not parts:
                continue
            top = max(lim_top, min([top] + [x["top"] - 3 for x in parts]))
            bot = min(lim_bot, max([bot] + [x["bottom"] + 3 for x in parts]))
            raw = " ".join(x["text"] for x in sorted(parts, key=lambda x: (round(x["top"]), x["left"])))
            if "=" not in raw and "∝" not in raw and "~" not in raw:
                continue
            before = " ".join(x["text"] for x in body_above[-2:])
            after = " ".join(x["text"] for x in body_below[:3])
            num = mm.group(1)
            rel = Path(slug(pdf)) / f"eq_p{page}_{num}.png"
            if not render(pdf, page, (40, top, pw - 30, bot), OUT / rel) or ink(OUT / rel) < 0.005:
                (OUT / rel).unlink(missing_ok=True)
                continue
            seen.add(num)
            out.append({"id": f"{slug(pdf)}:eq{num}", "label": f"Equation ({num})", "page": page, "raw_text": raw[:300],
                        "context_before": before[-400:], "context_after": after[:400], "png": rel.as_posix(),
                        "paper": {"title": m.get("title") or pdf.stem, "doi": m.get("doi"), "url": m.get("url"),
                                  "source": m.get("source", "file"), "pdf": os.path.relpath(pdf, ROOT).replace("\\", "/")},
                        "method": "numbered-equation crop (pdftohtml -xml + pdftoppm); image of the original, not retyped"})
    return out


# ---------------------------------------------------------------- pencarian (dipakai asisten)
STOP = set("the a an of and or in on for to with by from at as is are was were be this that these those it its "
           "figure fig shows shown show using used dan yang di ke dari untuk dengan pada gambar".split())


def _tok(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if w not in STOP and len(w) > 1]


EQ_INDEX = OUT / "equations.json"
_IDXS = {}


def _bm25(index, text_of, query, k):
    """BM25 (k1=1.2, b=0.75) atas teks tiap entri indeks; minimal separuh kata kunci harus cocok."""
    import math
    if not index.exists():
        return []
    mt = index.stat().st_mtime
    st = _IDXS.get(str(index))
    if not st or st["mtime"] != mt:
        items = json.loads(index.read_text(encoding="utf-8"))
        docs = [(f, _tok(text_of(f))) for f in items]
        df = {}
        for _, toks in docs:
            for w in set(toks):
                df[w] = df.get(w, 0) + 1
        st = _IDXS[str(index)] = {"mtime": mt, "docs": docs, "df": df, "avg": sum(len(t) for _, t in docs) / max(1, len(docs))}
    docs, df, avg, n = st["docs"], st["df"], st["avg"], len(st["docs"])
    q = set(_tok(query))
    need = max(1, math.ceil(len(q) / 2))
    scored = []
    for f, toks in docs:
        tf, sc, hit = {}, 0.0, 0
        for w in toks:
            tf[w] = tf.get(w, 0) + 1
        for w in q:
            if w in tf:
                hit += 1
                idf = math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5))
                sc += idf * tf[w] * 2.2 / (tf[w] + 1.2 * (0.25 + 0.75 * len(toks) / avg))
        if sc > 0 and hit >= need:
            scored.append((sc, f))
    scored.sort(key=lambda x: -x[0])
    return scored[:max(1, min(int(k or 4), 8))]


def search(query, k=4):
    """Gambar: caption (bobot ganda) + kalimat yang merujuknya + judul paper."""
    res = _bm25(INDEX, lambda f: f["caption"] + " " + f["caption"] + " " + " ".join(f["mentions"]) + " " + f["paper"]["title"], query, k)
    return [{"id": f["id"], "label": f["label"], "page": f["page"], "caption": f["caption"][:400],
             "image": "/figures/" + f["png"], "score": round(sc, 2), "paper": f["paper"]["title"],
             "doi": f["paper"]["doi"], "url": f["paper"]["url"]} for sc, f in res]


def search_equations(query, k=3):
    """Persamaan bernomor: teks mentah + kalimat sebelum/sesudahnya (definisi variabel) + judul paper."""
    res = _bm25(EQ_INDEX, lambda e: e["raw_text"] + " " + e["context_before"] + " " + e["context_after"] + " " + e["paper"]["title"], query, k)
    return [{"id": e["id"], "label": e["label"], "page": e["page"],
             "caption": (e["context_after"] or e["context_before"])[:400], "raw_text": e["raw_text"],
             "image": "/figures/" + e["png"], "score": round(sc, 2), "paper": e["paper"]["title"],
             "doi": e["paper"]["doi"], "url": e["paper"]["url"], "kind": "equation"} for sc, e in res]


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pdf", nargs="*", default=[])
    ap.add_argument("--dir", help="folder berisi PDF (rekursif)")
    ap.add_argument("--from-db", action="store_true", help="semua PDF yang tercatat di freefall.sqlite dan ada di disk")
    ap.add_argument("--fresh", action="store_true", help="hapus indeks lama dulu")
    a = ap.parse_args()
    if not tool("pdftohtml") or not tool("pdftoppm"):
        sys.exit("Butuh poppler (pdftohtml, pdftoppm). Windows: ikut MiKTeX, atau pasang poppler.")
    pdfs = [Path(p) for p in a.pdf]
    if a.dir:
        pdfs += sorted(Path(a.dir).rglob("*.pdf"))
    if a.from_db:
        pdfs += db_pdfs()
    pdfs = list(dict.fromkeys(p.resolve() for p in pdfs if p.exists()))
    if not pdfs:
        sys.exit("Tidak ada PDF. Pakai --pdf, --dir, atau --from-db (PDF mentah ada di kb/raw/, tidak ikut git).")
    old = [] if a.fresh or not INDEX.exists() else json.loads(INDEX.read_text(encoding="utf-8"))
    old_eq = [] if a.fresh or not EQ_INDEX.exists() else json.loads(EQ_INDEX.read_text(encoding="utf-8"))
    done = {f["paper"]["pdf"] for f in old} | {e["paper"]["pdf"] for e in old_eq}
    meta, allf, alle, log = paper_meta(), [f for f in old], [e for e in old_eq], []
    for k, pdf in enumerate(pdfs, 1):
        rel = os.path.relpath(pdf, ROOT).replace("\\", "/")
        if rel in done:
            continue
        figs, err = extract(pdf, meta)
        eqs = [] if err else extract_equations(pdf, meta)
        allf += figs
        alle += eqs
        log.append({"pdf": rel, "figures": len(figs), "equations": len(eqs), "error": err})
        print(f"[{k}/{len(pdfs)}] {len(figs):3d} gambar {len(eqs):3d} persamaan  {pdf.name[:70]}" + (f"  ({err})" if err else ""))
    OUT.mkdir(parents=True, exist_ok=True)
    INDEX.write_text(json.dumps(allf, ensure_ascii=False, indent=1), encoding="utf-8")
    EQ_INDEX.write_text(json.dumps(alle, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "extract_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"total {len(allf)} gambar, {len(alle)} persamaan dari {len({f['paper']['pdf'] for f in allf})} PDF -> {INDEX.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
