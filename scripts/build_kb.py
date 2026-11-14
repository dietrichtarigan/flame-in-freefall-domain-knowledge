#!/usr/bin/env python3
"""Bangun lapisan bersih + siap pakai dari data mentah PSI/NTRS.

Membaca kb/raw dan kb/manifest, menulis:
  kb/clean/tables/*.csv        tabel uji per investigasi, dirapikan, kolom asli dipertahankan
  kb/gold/investigations.csv   katalog eksperimen
  kb/gold/tests.csv            SEMUA uji dalam satu skema seragam
  kb/gold/publications.csv     publikasi + DOI per investigasi
  kb/gold/paper_chunks.csv     teks paper (NTRS + DOI) dipotong per halaman/bagian
  kb/gold/freefall.sqlite      semuanya dalam satu database (files, papers, paper_chunks,
                                plus tabel FTS5 `paper_search` untuk cari di dalam teks)

Hanya butuh Python 3.9+. Aman dijalankan ulang (menimpa hasil lama).
Opsional: pip install pymupdf -- tanpa ini, teks PDF paper DOI dilewati (NTRS tetap jalan,
sudah berupa .txt polos).
  python scripts/build_kb.py
"""
import argparse
import csv
import json
import re
import sqlite3
import sys
from pathlib import Path

try:
    import fitz  # pymupdf, opsional: teks per halaman untuk PDF paper DOI
except ImportError:
    fitz = None

MMHG, ATM, BAR = 0.133322, 101.325, 100.0
NUM = re.compile(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?")

TEST_COLS = ["test_uid", "accession", "acronym", "table_name", "granularity", "source_file",
             "source_row", "test_id", "date", "fuel_phase", "fuel", "configuration",
             "o2_mole_frac", "o2_final_mole_frac", "pressure_kpa", "diluent", "diluent_mole_frac",
             "flow_cm_s", "flow_direction", "gravity", "ignited", "outcome", "burn_time_s",
             "size_mm", "metric_name", "metric_value", "metric_unit", "notes", "raw_json"]


def read_csv(path):
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return list(csv.reader(text.splitlines()))


def clean_header(h):
    return re.sub(r"\s+", " ", h).strip()


def num(v):
    """Angka tunggal; None bila kosong/bukan angka. '~ 21.5' -> 21.5; '21.5 - 21.7' -> rata-rata."""
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"^[~\u2248<>\s]*(" + NUM.pattern + ")", s.replace(",", ""))
    if not m:  # teks seperti 'LOW O2' atau 'RAMPED' bukan angka
        return None
    first = float(m.group(1))
    m2 = re.match(r"\s*(?:-|to)\s*(" + NUM.pattern + ")", s.replace(",", "")[m.end():])
    if m2:
        return round((first + float(m2.group(1))) / 2, 6)
    return first


def r6(v):
    return None if v is None else round(v, 6)


def g(row, *names):
    """Ambil nilai kolom pertama yang namanya diawali salah satu `names` (tidak peka huruf besar)."""
    for n in names:
        for k, v in row.items():
            if k.lower().startswith(n.lower()):
                return v.strip()
    return ""


def base(**kw):
    d = dict.fromkeys(TEST_COLS, None)
    d.update(kw)
    return d


# ---- pemeta per tabel: baris asli -> skema seragam -------------------------------------

def m_flex(r):
    co2, he = num(g(r, "CO initial")) or 0, num(g(r, "He initial")) or 0
    p = num(g(r, "Ambient pressure"))
    return base(test_id=g(r, "FLEX Identifier"), date=g(r, "Test Date"), fuel_phase="droplet",
                fuel=g(r, "Fuel"), o2_mole_frac=num(g(r, "O initial")),
                pressure_kpa=r6(p * MMHG) if p else None,
                diluent="CO2" if co2 > 0 else "He" if he > 0 else "N2",
                diluent_mole_frac=co2 if co2 > 0 else he if he > 0 else num(g(r, "N initial")),
                outcome=g(r, "Test end"), burn_time_s=num(g(r, "Burn time")),
                size_mm=num(g(r, "Droplet initial")), metric_name="burning_rate",
                metric_value=num(g(r, "Burning rate")),
                metric_unit="as published ('mm' in source; time unit not stated)",
                notes="CO2 column is headed 'CO' in the source file")


def m_cfi(r):
    p, he = num(g(r, "Pressure")), num(g(r, "Helium")) or 0
    return base(test_id=g(r, "CIR") or g(r, "Flex Number"), date=g(r, "Test Date"),
                fuel_phase="droplet", fuel=g(r, "Fuel"), o2_mole_frac=num(g(r, "Oxygen")),
                pressure_kpa=r6(p * ATM) if p else None, diluent="He" if he > 0 else "N2",
                diluent_mole_frac=he if he > 0 else num(g(r, "Nitrogen")),
                configuration="fiber-supported" if g(r, "Fiber").lower() == "yes" else "free droplet")


def m_bass2(r):
    o2, o2f = num(g(r, "Calibrated initial O2")), num(g(r, "Calibrated final O2"))
    return base(test_id=g(r, "Test #"), date=g(r, "Date"), fuel_phase="solid",
                fuel=g(r, "Fuel Sample Material"), o2_mole_frac=r6(o2 / 100) if o2 else None,
                o2_final_mole_frac=r6(o2f / 100) if o2f is not None else None,
                configuration="flow restrictor " + g(r, "Flow restrictor"),
                notes="PI " + g(r, "PI") + "; flow is given as fan/air display settings, not cm/s; "
                      "flame spread rate is not tabulated (video only)")


def m_bass(r):
    return base(test_id=g(r, "Test #") or g(r, "As Run"), date=g(r, "Date"), fuel_phase="solid",
                fuel=g(r, "Fuel Sample Material"),
                notes="test matrix only; conditions and results are in video and reports")


def _end(v):
    v = v.strip()
    return {"SE": "self-extinguished", "FT": "flow terminated"}.get(v.upper(), None if v in ("", "-") else v)


def _ign(v):
    v = v.strip().lower()
    return "yes" if v.startswith("y") else "no" if v.startswith("n") else None


def m_cfig_normal(r):
    p = num(g(r, "approx p"))
    return base(test_id=g(r, "Test"), fuel_phase="gas", fuel=g(r, "Fuel"),
                configuration="normal flame (fuel issues into oxidizer)",
                o2_mole_frac=num(g(r, "XO2 before")), o2_final_mole_frac=num(g(r, "XO2 after")),
                pressure_kpa=r6(p * BAR) if p else None, ignited=_ign(g(r, "Hot ignition")),
                outcome=_end(g(r, "Self-ext", "Self -ext")), burn_time_s=num(g(r, "burn time")),
                metric_name="adiabatic_flame_temperature", metric_value=num(g(r, "Tad")),
                metric_unit="K", notes=("; ".join(x for x in [
                    "cool flame: " + g(r, "Cool flame") if g(r, "Cool flame") else "",
                    g(r, "Comments")] if x)) or None)


def m_cfig_inverse(r):
    p = num(g(r, "approx p"))
    return base(test_id=g(r, "Test"), fuel_phase="gas", fuel=g(r, "Fuel"),
                configuration="inverse flame (oxidizer issues into fuel)",
                o2_mole_frac=num(g(r, "XO2")), pressure_kpa=r6(p * BAR) if p else None,
                ignited=_ign(g(r, "Hot ignition")), outcome=_end(g(r, "Self -ext", "Self-ext")),
                burn_time_s=num(g(r, "burn time")), metric_name="adiabatic_flame_temperature",
                metric_value=num(g(r, "Tad")), metric_unit="K", notes=g(r, "Comments") or None)


def m_fd_normal(r):
    p = num(g(r, "pmean")) or num(g(r, "pinit"))
    return base(test_id=g(r, "Test"), fuel_phase="gas", fuel=g(r, "Fuel"),
                configuration="normal flame", o2_mole_frac=num(g(r, "XO2 (init)")),
                o2_final_mole_frac=num(g(r, "XO2 (final)")),
                pressure_kpa=r6(p * ATM) if p else None, diluent="N2",
                metric_name="adiabatic_flame_temperature", metric_value=num(g(r, "Tad")),
                metric_unit="K", notes="ramped flow" if "RAMP" in g(r, "Xfuel").upper() else None)


def m_fd_inverse(r):
    p = num(g(r, "pmean")) or num(g(r, "pinit"))
    return base(test_id=g(r, "Test"), fuel_phase="gas", fuel="C2H4",
                configuration="inverse flame", o2_mole_frac=num(g(r, "XO2")),
                pressure_kpa=r6(p * ATM) if p else None, diluent="N2",
                metric_name="adiabatic_flame_temperature", metric_value=num(g(r, "Tad")),
                metric_unit="K")


def m_spice(r):
    return base(test_id="GMT" + g(r, "GMT date") + " " + g(r, "GMT ignition"),
                date="GMT day " + g(r, "GMT date"), fuel_phase="gas", fuel=g(r, "Fuel"),
                configuration="co-flow jet, nozzle " + g(r, "Nozzle") + " mm",
                flow_cm_s=num(g(r, "Air Rate")), flow_direction="co-flow",
                metric_name="fuel_rate", metric_value=num(g(r, "Fuel Rate (mg/s)")),
                metric_unit="mg/s")


def m_samer(r):
    return base(test_id=g(r, "SAME Test"), date=g(r, "Date"), fuel_phase="smoke",
                fuel=g(r, "Sample Type"), flow_cm_s=num(g(r, "Inlet velocity")),
                burn_time_s=num(g(r, "Duration")), metric_name="net_aging_time",
                metric_value=num(g(r, "Net aging")), metric_unit="s",
                notes=g(r, "Description") or None)


def m_same(r):
    return base(test_id=g(r, "Sample #"), fuel_phase="smoke", fuel=g(r, "Sample Material"),
                flow_cm_s=num(g(r, "Air Flow")), metric_name="weight_loss_rate",
                metric_value=num(g(r, "Weight loss")), metric_unit="mg/min")


def m_saffire(r):
    o2 = num(g(r, "Percent O2"))
    out = g(r, "?-g Burn Length")
    return base(test_id=g(r, "Sample Number"), fuel_phase="solid", fuel=g(r, "Material"),
                o2_mole_frac=r6(o2 / 100) if o2 else None, flow_cm_s=num(g(r, "Air Flow")),
                flow_direction=(g(r, "Flow Direction") or g(r, "Direction")).lower() or None,
                burn_time_s=num(g(r, "Burn Time")), outcome=("burn length " + out) if out else None,
                metric_name="spread_rate" if g(r, "?-g Spread") else None,
                metric_value=num(g(r, "?-g Spread")) if "mm/s" in g(r, "?-g Spread") else None,
                metric_unit="mm/s" if "mm/s" in g(r, "?-g Spread") else None,
                configuration="sample " + " x ".join(x for x in [
                    g(r, "Sample Thickness", "Samle Thickness"), g(r, "Sample Length"),
                    g(r, "Sample Width")] if x),
                notes="large-scale test in Cygnus; O2 raw: " + g(r, "Percent O2")
                if g(r, "Percent O2") else "large-scale test in Cygnus")


def m_campaign(phase):
    def f(r):
        fuel = g(r, "Fuel Bottle", "Fuel Type", "Sample (Fuel", "Sample Material")
        return base(fuel_phase=phase, fuel=fuel or None, date=g(r, "Test Date", "Actual Day") or None,
                    test_id=g(r, "Test Day", "Session Name", "Data ID") or None,
                    notes="summary row (one per test day or fuel), not a single test")
    return f


# accession, potongan nama file -> (pemeta, granularitas)
MAPPERS = [
    ("PSI-69", "FLEX", m_flex, "test"), ("PSI-39", "CFI", m_cfi, "test"),
    ("PSI-25", "BASS-II", m_bass2, "test"), ("PSI-26", "BASS", m_bass, "test"),
    ("PSI-159", "Normal", m_cfig_normal, "test"), ("PSI-159", "Inverse", m_cfig_inverse, "test"),
    ("PSI-10", "Normal", m_fd_normal, "test"), ("PSI-10", "Inverse", m_fd_inverse, "test"),
    ("PSI-107", "Spice", m_spice, "test"), ("PSI-101", "SAME-R", m_samer, "test"),
    ("PSI-102", "SAME", m_same, "test"), ("PSI-98", "SAFFIRE", m_saffire, "test"),
    ("PSI-99", "SAFFIRE", m_saffire, "test"), ("PSI-100", "SAFFIRE", m_saffire, "test"),
    ("PSI-68", "Flex2", m_campaign("droplet"), "campaign"),
    ("PSI-20", "BRE", m_campaign("gas"), "campaign"), ("PSI-21", "CLD", m_campaign("gas"), "campaign"),
    ("PSI-22", "E-FIELD", m_campaign("gas"), "campaign"),
    ("PSI-23", "s-Flame", m_campaign("gas"), "campaign"),
    ("PSI-106", "Slice", m_campaign("gas"), "campaign"),
    ("PSI-47", "DAFT", m_campaign("smoke"), "campaign"),
    ("PSI-142", "Data Summary", m_campaign("gas"), "campaign"),
]


def chunk_text(text, size=3000, overlap=200):
    """Potong teks panjang jadi bagian ber-overlap, untuk dokumen tanpa halaman asli (NTRS .txt)."""
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return []
    out, i, step = [], 0, max(1, size - overlap)
    while i < len(text):
        out.append(text[i:i + size].strip())
        i += step
    return [c for c in out if c]


def pdf_pages(path):
    """Teks per halaman asli PDF; [] bila pymupdf tak ada atau file tak terbaca."""
    if fitz is None:
        return []
    try:
        doc = fitz.open(path)
        pages = [p.get_text().strip() for p in doc]
        doc.close()
        return pages
    except Exception:
        return []


def is_note_row(cells):
    """Baris catatan kaki / keterangan, bukan uji: hanya 1-2 sel terisi dari banyak kolom."""
    filled = [c for c in cells if c.strip()]
    first = cells[0].strip().lower() if cells else ""
    return (len(cells) >= 8 and len(filled) <= 2) or first.startswith("note")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    here = Path(__file__).resolve().parent.parent / "kb"
    ap.add_argument("--root", type=Path, default=here, help="folder kb (default: ../kb)")
    ap.add_argument("--out", type=Path, default=None, help="folder keluaran (default: --root)")
    a = ap.parse_args()
    root, out = a.root, (a.out or a.root)
    clean_dir, gold = out / "clean" / "tables", out / "gold"
    clean_dir.mkdir(parents=True, exist_ok=True)
    gold.mkdir(parents=True, exist_ok=True)

    inv = {}
    for p in sorted((root / "raw" / "psi" / "investigations").glob("PSI-*.json")):
        inv[p.stem] = json.loads(p.read_text(encoding="utf-8"))

    tests, table_stats = [], {}
    files = sorted((root / "raw" / "psi" / "files").glob("*/Experimental table/*.csv"))
    for path in files:
        acc = path.parts[-3]
        mp = next((m for m in MAPPERS if m[0] == acc and m[1].lower() in path.name.lower()), None)
        rows = read_csv(path)
        header = [clean_header(h) for h in rows[0]]
        tname = re.sub(r"^PSI-\d+_Experimental table_", "", path.stem)
        acr = (inv.get(acc, {}).get("investigationAcronym") or "").strip()
        proj = (inv.get(acc, {}).get("projectType") or "").lower()
        gravity = "microgravity" if "microgravity" in proj else "reduced gravity" \
            if "reduced" in proj else "ground" if "ground" in proj else None
        cleaned, n_test, n_note = [], 0, 0
        for i, cells in enumerate(rows[1:], start=1):
            if not any(c.strip() for c in cells):
                continue
            cells = [c.strip() for c in cells] + [""] * (len(header) - len(cells))
            kind = "note" if is_note_row(cells) else "test"
            rowd = dict(zip(header, cells))
            cleaned.append([acc, tname, i, kind] + cells[:len(header)])
            if kind == "note" or mp is None:
                n_note += kind == "note"
                continue
            t = mp[2](rowd)
            t.update(test_uid=f"{acc}:{tname}:{i}", accession=acc, acronym=acr, table_name=tname,
                     granularity=mp[3], source_file=path.name, source_row=i,
                     gravity=t["gravity"] or gravity,
                     raw_json=json.dumps({k: v for k, v in rowd.items() if v}, ensure_ascii=False))
            tests.append(t)
            n_test += 1
        with open(clean_dir / f"{acc}__{re.sub(r'[^A-Za-z0-9]+', '_', tname)}.csv", "w",
                  newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["_accession", "_table", "_source_row", "_row_kind"] + header)
            w.writerows(cleaned)
        table_stats.setdefault(acc, []).append((tname, n_test, n_note))
        print(f"  {acc:8s} {tname[:34]:34s} {n_test:5d} uji  {n_note:2d} catatan"
              + ("" if mp else "  (tanpa pemeta)"))

    with open(gold / "tests.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TEST_COLS)
        w.writeheader()
        w.writerows(tests)

    # ---- manifest file & paper ----------------------------------------------------------
    def load(name):
        p = root / "manifest" / name
        if not p.exists():
            return []
        with open(p, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    mfiles, papers, papers_doi = load("psi_files.csv"), load("ntrs_papers.csv"), load("papers_doi.csv")
    have = {}
    for r in mfiles:
        h = have.setdefault(r["accession"], [0, 0, 0, 0])
        h[0] += 1
        h[1] += int(r["size_bytes"] or 0)
        if r["status"] in ("downloaded", "exists"):
            h[2] += 1
            h[3] += int(r["size_bytes"] or 0)

    # ---- katalog & publikasi -------------------------------------------------------------
    inv_cols = ["accession", "acronym", "title", "doi", "research_area", "sub_area", "project_type",
                "platform", "hardware", "start", "end", "people", "license", "n_tables",
                "n_test_rows", "n_files_listed", "gb_listed", "n_files_local", "gb_local",
                "related", "psi_url", "objective", "hypothesis", "approach", "impacts"]
    inv_rows, pub_rows = [], []
    for acc in sorted(inv, key=lambda x: int(x.split("-")[1])):
        j, h = inv[acc], have.get(acc, [0, 0, 0, 0])
        ppl = "; ".join(f"{c.get('firstName', '')} {c.get('lastName', '')}".strip() + " (" +
                        ", ".join(x.get("annotationValue", "") for x in c.get("roles") or []) + ")"
                        for c in j.get("contacts") or [])
        ts = table_stats.get(acc, [])
        inv_rows.append(dict(zip(inv_cols, [
            acc, (j.get("investigationAcronym") or "").strip(), (j.get("title") or "").strip(),
            j.get("doi"), j.get("researchArea"), j.get("subResearchArea"), j.get("projectType"),
            j.get("flightProgram"), j.get("experimentHardware"), j.get("investigationStartDate"),
            j.get("investigationEndDate"), ppl, j.get("licenseIdentifier"), len(ts),
            sum(t[1] for t in ts), h[0], round(h[1] / 1e9, 3), h[2], round(h[3] / 1e9, 3),
            j.get("relatedInvestigations") or "",
            f"https://psi.nasa.gov/physci/repo/data/investigations/{acc}",
            j.get("objective"), j.get("hypothesis"), j.get("approach"), j.get("researchImpacts")])))
        for p in j.get("publications") or []:
            if not isinstance(p, dict) or not (p.get("title") or p.get("doi")):
                continue
            pub_rows.append({"accession": acc, "title": (p.get("title") or "").strip(),
                             "authors": (p.get("authorList") or "").strip(),
                             "doi": (p.get("doi") or "").strip(),
                             "status": (p.get("status") or {}).get("annotationValue", "")
                             if isinstance(p.get("status"), dict) else ""})
    pub_cols = ["accession", "title", "authors", "doi", "status"]
    for name, cols, rows in (("investigations.csv", inv_cols, inv_rows),
                             ("publications.csv", pub_cols, pub_rows)):
        with open(gold / name, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            w.writerows(rows)

    # ---- teks paper, dipotong per halaman (DOI/PDF) atau per bagian (NTRS/.txt) -----------
    chunks = []
    off = root / "manifest" / "ntrs_offtopic.csv"   # dari scripts/ntrs_relevance.py
    skip = {o["id"] for o in csv.DictReader(open(off, encoding="utf-8"))} if off.exists() else set()
    for r in papers:  # NTRS: .txt polos, tanpa nomor halaman asli -> potong per ~3000 karakter
        if r.get("txt_status") != "downloaded" or not r.get("txt_path") or r["id"] in skip:
            continue
        p = root / r["txt_path"]
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, part in enumerate(chunk_text(text)):
            chunks.append({"paper_uid": "ntrs:" + r["id"], "source": "ntrs", "title": r["title"],
                           "page": None, "chunk_index": i, "text": part[:6000]})

    n_pdf_text = 0
    for r in papers_doi:  # DOI: PDF asli -> teks per halaman; tanpa PDF -> abstrak sebagai 1 bagian
        uid, got_pdf = "doi:" + r["doi"], False
        if r.get("pdf_path"):
            p = root / r["pdf_path"]
            if p.exists():
                for i, text in enumerate(pdf_pages(p), start=1):
                    if text:
                        chunks.append({"paper_uid": uid, "source": "doi", "title": r["title"],
                                       "page": i, "chunk_index": i - 1, "text": text[:6000]})
                        got_pdf = True
        if got_pdf:
            n_pdf_text += 1
        elif r.get("abstract"):
            chunks.append({"paper_uid": uid, "source": "doi", "title": r["title"],
                           "page": None, "chunk_index": 0, "text": r["abstract"][:6000]})

    # Sumber resmi NASA (scripts/nasa_resources_fetch.py): latar tiap investigasi,
    # tiga kecelakaan kebakaran, dan alih-teknologi ke pemadam kebakaran di Bumi.
    # Ikut diindeks supaya asisten bisa menjawab pertanyaan konteks/sejarah --
    # termasuk bagian "penerapan di Bumi" yang diminta brief -- dengan sitasi,
    # bukan dari ingatan model.
    res_man = root / "manifest" / "nasa_resources.csv"
    n_res = 0
    for r in (list(csv.DictReader(open(res_man, encoding="utf-8")))
              if res_man.exists() else []):
        tp = root / r["text_path"] if r.get("text_path") else None
        if not tp or not tp.exists():
            continue
        text = tp.read_text(encoding="utf-8", errors="replace")
        if len(text) < 400:            # halaman JS kosong (PSI, YouTube)
            continue
        for i, part in enumerate(chunk_text(text)):
            chunks.append({"paper_uid": "nasa:" + r["key"], "source": "nasa_resource",
                           "title": r["description"] or r["key"],
                           "page": None, "chunk_index": i, "text": part[:6000]})
        n_res += 1
    for p in sorted((root / "raw" / "nasa_resources" / "pdf").glob("*.pdf")):
        pages_txt = pdf_pages(p)
        if not pages_txt:
            continue
        for i, text in enumerate(pages_txt, start=1):
            if text:
                chunks.append({"paper_uid": "nasa:" + p.stem, "source": "nasa_resource",
                               "title": p.stem.replace("-", " "),
                               "page": i, "chunk_index": i - 1, "text": text[:6000]})
        n_res += 1

    chunk_cols = ["paper_uid", "source", "title", "page", "chunk_index", "text"]
    with open(gold / "paper_chunks.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=chunk_cols)
        w.writeheader()
        w.writerows(chunks)
    if fitz is None and papers_doi:
        print("\nCATATAN: pymupdf tidak terpasang -- teks PDF paper DOI dilewati "
              "(hanya abstrak dipakai). Jalankan 'pip install pymupdf' lalu ulangi untuk teks penuh.")

    # ---- SQLite ----------------------------------------------------------------------------
    db = gold / "freefall.sqlite"
    if db.exists():
        db.unlink()
    con = sqlite3.connect(db)

    def put(table, cols, rows, numeric=()):
        con.execute(f"CREATE TABLE {table} (" + ", ".join(
            f'"{c}" ' + ("REAL" if c in numeric else "TEXT") for c in cols) + ")")
        con.executemany(f"INSERT INTO {table} VALUES ({','.join('?' * len(cols))})",
                        [[r.get(c) for c in cols] for r in rows])
    put("tests", TEST_COLS, tests, {"source_row", "o2_mole_frac", "o2_final_mole_frac",
                                    "pressure_kpa", "diluent_mole_frac", "flow_cm_s",
                                    "burn_time_s", "size_mm", "metric_value"})
    put("investigations", inv_cols, inv_rows, {"n_tables", "n_test_rows", "n_files_listed",
                                               "gb_listed", "n_files_local", "gb_local"})
    put("publications", pub_cols, pub_rows)
    if mfiles:
        put("files", list(mfiles[0].keys()), mfiles, {"size_bytes"})
    if papers:
        put("papers", list(papers[0].keys()), papers)
    if papers_doi:
        put("papers_doi", list(papers_doi[0].keys()), papers_doi)
    # ---- hasil tambang: telemetri ACME & episode video BASS ----------------------------
    # Dibangun oleh scripts/telemetry_mine.py + telemetry_join.py dan
    # scripts/video_analyze.py + video_join.py. Dimasukkan bila berkasnya ada,
    # supaya satu perintah build_kb.py tetap menghasilkan basis data lengkap.
    def load_csv(p):
        return list(csv.DictReader(open(p, encoding="utf-8"))) if p.exists() else []

    tel = load_csv(root.parent / "analysis" / "telemetry" / "telemetry_joined.csv")
    if tel:
        # Kenaikan suhu tipis bisa berasal dari panas sisa atau panas pemantik,
        # bukan api (lihat kasus 21106 G8 di analysis/telemetry/README.md), jadi
        # ditandai -- bukan dibuang: dari 35 uji sinyal lemah yang punya label
        # NASA, 31 memang menyala. Nyala dingin wajar bersinyal lemah.
        for r in tel:
            try:
                v = float(r.get("tc_burner_rise_v") or 0)
            except ValueError:
                v = 0.0
            r["signal_strength"] = ("lemah" if r.get("ignited_tel") == "ya" and v < 0.002
                                    else "kuat" if r.get("ignited_tel") == "ya" else "")
        tcols = list(tel[0].keys())
        put("telemetry", tcols, tel,
            {"burn_duration_s", "t_ignite_s", "t_extinct_s", "tc_burner_rise_v",
             "fuel_flow_mean", "record_s", "n_samples", "o2_mole_frac", "pressure_kpa"})
        con.execute("CREATE INDEX idx_tel_acc ON telemetry(accession)")
        con.execute("CREATE INDEX idx_tel_tp ON telemetry(test_point)")

    vid = load_csv(root.parent / "analysis" / "video_full" / "measurements.csv")
    if vid:
        vcols = list(vid[0].keys())
        put("video_episodes", vcols, vid,
            {"episode", "t_start_s", "t_end_s", "burn_duration_s", "area_max_px",
             "area_median_px", "tail_frac_of_peak", "drift_px_per_s", "o2_mole_frac"})
        con.execute("CREATE INDEX idx_vid_test ON video_episodes(test_id)")

    if chunks:
        put("paper_chunks", chunk_cols, chunks)
        con.execute("CREATE VIRTUAL TABLE paper_search USING fts5("
                    "paper_uid, title, text, page UNINDEXED, source UNINDEXED, "
                    "tokenize='porter unicode61')")
        con.executemany(
            "INSERT INTO paper_search (paper_uid, title, text, page, source) VALUES (?,?,?,?,?)",
            [(c["paper_uid"], c["title"], c["text"], c["page"], c["source"]) for c in chunks])
    con.execute("CREATE INDEX idx_tests_acc ON tests(accession)")
    con.execute("CREATE INDEX idx_tests_phase ON tests(fuel_phase)")
    con.commit()
    con.close()

    n_t = sum(t["granularity"] == "test" for t in tests)
    print(f"\nSelesai: {len(inv_rows)} investigasi, {len(files)} tabel, {n_t} uji per-baris + "
          f"{len(tests) - n_t} baris ringkasan, {len(pub_rows)} publikasi.")
    print(f"Teks paper: {len(chunks)} potongan ({n_pdf_text} paper dengan PDF asli, "
          f"sisanya abstrak/txt). Cari lewat tabel FTS5 'paper_search'.")
    print(f"Sumber resmi NASA terindeks: {n_res} dokumen (latar, kecelakaan, spinoff).")
    if tel:
        ig = sum(1 for r in tel if r.get("ignited_tel") == "ya")
        weak = sum(1 for r in tel if r.get("signal_strength") == "lemah")
        print(f"Telemetri ACME: {len(tel)} uji ({ig} menyala, {weak} bersinyal lemah).")
    if vid:
        print(f"Episode video BASS: {len(vid)} "
              f"({sum(1 for r in vid if r.get('matched') == 'ya')} cocok ke tabel uji).")
    print("Keluaran:", gold)
    return 0


if __name__ == "__main__":
    sys.exit(main())
