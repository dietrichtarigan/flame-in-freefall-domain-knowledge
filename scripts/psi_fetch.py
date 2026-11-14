#!/usr/bin/env python3
"""Ambil metadata + file dari NASA PSI (Physical Sciences Informatics).

Hanya butuh Python 3.9+ (tanpa pip install). Aman dijalankan ulang: file yang
sudah ada dan ukurannya cocok akan dilewati.

Contoh:
  python scripts/psi_fetch.py --dry-run          # hanya metadata + manifest
  python scripts/psi_fetch.py                    # + unduh semua file <= 10 MB
  python scripts/psi_fetch.py --max-mb 100       # perluas ke <= 100 MB
  python scripts/psi_fetch.py --ids PSI-25 --max-mb 2000 --ext mp4
"""
import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://psi.nasa.gov/geode-py/ws"
UA = {"User-Agent": "Mozilla/5.0 (SpaceApps-2026 knowledge-base builder)",
      "Accept": "application/json, text/plain, */*"}
ROOT = Path(__file__).resolve().parent.parent / "kb"
RAW = ROOT / "raw" / "psi"
MANIFEST = ROOT / "manifest"
FIELDS = ["accession", "acronym", "category", "file_name", "size_bytes",
          "version", "s3_path", "status", "sha256", "local_path", "note"]


def http(url, timeout=60, retries=4):
    """GET dengan retry; mengembalikan bytes."""
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
        except Exception as e:  # jaringan putus, timeout
            last = e
        time.sleep(2 * (i + 1))
    raise last


def get_json(url):
    return json.loads(http(url).decode("utf-8"))


def safe_name(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "unnamed"


def local_path_for(acc, category, file_name):
    p = RAW / "files" / acc / safe_name(category) / safe_name(file_name)
    if len(str(p)) > 235:  # batas panjang path Windows
        stem, suf = p.stem, p.suffix
        h = hashlib.md5(file_name.encode()).hexdigest()[:8]
        keep = max(20, len(stem) - (len(str(p)) - 235) - 9)
        p = p.with_name(stem[:keep] + "_" + h + suf)
    return p


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_catalog():
    url = BASE + "/repo/search?source=psi&type=investigation&size=1000"
    data = get_json(url)
    hits = [h["_source"] for h in data["hits"]["hits"]]
    total = data["hits"].get("total")
    total = total.get("value") if isinstance(total, dict) else total
    if total and len(hits) < total:
        print(f"PERINGATAN: katalog hanya {len(hits)} dari {total} investigasi")
    return hits


def file_rows(acc, inv):
    """Semua file milik satu investigasi (added + tabel + gambar), tanpa duplikat."""
    seen, rows = set(), []
    groups = [("added", None), ("experimentalTable", "Experimental table"),
              ("images", "Representative Image(s)")]
    for key, default_cat in groups:
        for f in inv.get(key) or []:
            name = f.get("file_name")
            if not name or f.get("visible") is False:
                continue
            s3 = f.get("s3_path") or ""
            ident = s3 or name
            if ident in seen:
                continue
            seen.add(ident)
            parts = s3.split("/")
            cat = parts[2] if len(parts) > 3 else (default_cat or "unknown")
            rows.append({"accession": acc,
                         "acronym": inv.get("investigationAcronym") or "",
                         "category": cat, "file_name": name,
                         "size_bytes": int(f.get("file_size") or 0),
                         "version": f.get("version") or "",
                         "s3_path": s3, "status": "listed", "sha256": "",
                         "local_path": "", "note":
                         "restricted" if f.get("restricted") else ""})
    return rows


def download(row):
    acc, name = row["accession"], row["file_name"]
    dest = local_path_for(acc, row["category"], name)
    size = row["size_bytes"]
    if dest.exists() and (not size or dest.stat().st_size == size):
        row.update(status="exists", local_path=str(dest.relative_to(ROOT)),
                   sha256=sha256_of(dest))
        return row
    q = {"file": name, "redirect": "false"}
    if row["version"] != "":
        q["version"] = row["version"]
    api = f"{BASE}/studies/{acc}/download?" + urllib.parse.urlencode(
        q, quote_via=urllib.parse.quote)
    try:
        signed = http(api).decode("utf-8").strip().strip('"')
        if not signed.startswith("http"):
            raise ValueError("API tidak mengembalikan URL: " + signed[:80])
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")
        req = urllib.request.Request(signed, headers={"User-Agent": UA["User-Agent"]})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as out:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(dest)
        got = dest.stat().st_size
        row.update(status="downloaded", local_path=str(dest.relative_to(ROOT)),
                   sha256=sha256_of(dest))
        if size and got != size:
            row["note"] = (row["note"] + f" size_mismatch(got={got})").strip()
    except Exception as e:
        row.update(status="failed", note=(row["note"] + " " + repr(e)[:150]).strip())
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--area", default="combustion science",
                    help="filter Research Area (default: combustion science)")
    ap.add_argument("--all-areas", action="store_true", help="ambil semua 133 investigasi")
    ap.add_argument("--ids", help="daftar accession dipisah koma, mis. PSI-25,PSI-69")
    ap.add_argument("--max-mb", type=float, default=10, help="batas ukuran per file (MB)")
    ap.add_argument("--ext", help="hanya ekstensi ini, dipisah koma (mis. csv,pdf,mp4)")
    ap.add_argument("--skip-category", default="",
                    help="lewati kategori, dipisah koma (mis. 'Raw Data')")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true", help="tanpa mengunduh file")
    a = ap.parse_args()

    for d in (RAW / "investigations", MANIFEST):
        d.mkdir(parents=True, exist_ok=True)

    print("1/3 Mengambil katalog investigasi ...")
    catalog = fetch_catalog()
    (RAW / "catalog.json").write_text(json.dumps(catalog, indent=1), encoding="utf-8")
    accs = [c["Accession"] for c in catalog if a.all_areas or
            a.area.lower() in str(c.get("Research Area", "")).lower()]
    only = None
    if a.ids:  # --ids hanya membatasi UNDUHAN; manifest tetap mencakup semua investigasi
        only = {x.strip() for x in a.ids.split(",") if x.strip()}
        accs = sorted(set(accs) | only, key=lambda x: int(x.split("-")[1]))
    print(f"    {len(catalog)} investigasi di katalog, {len(accs)} dicatat"
          + (f", unduhan dibatasi ke {len(only)}" if only else ""))

    print("2/3 Mengambil metadata tiap investigasi ...")
    rows, pubs = [], {}
    for acc in accs:
        try:
            inv = get_json(f"{BASE}/repo/investigations/{acc}")
        except Exception as e:
            print(f"    GAGAL {acc}: {e!r}")
            continue
        (RAW / "investigations" / f"{acc}.json").write_text(
            json.dumps(inv, indent=1), encoding="utf-8")
        pubs[acc] = {"title": inv.get("title"), "doi": inv.get("doi"),
                     "acronym": inv.get("investigationAcronym"),
                     "publications": inv.get("publications")}
        fr = file_rows(acc, inv)
        rows += fr
        gb = sum(r["size_bytes"] for r in fr) / 1e9
        print(f"    {acc:8s} {(inv.get('investigationAcronym') or ''):22s} "
              f"{len(fr):5d} file  {gb:9.2f} GB")
    (MANIFEST / "psi_publications.json").write_text(
        json.dumps(pubs, indent=1), encoding="utf-8")

    limit = a.max_mb * 1e6
    exts = {e.strip().lower().lstrip(".") for e in a.ext.split(",")} if a.ext else None
    skip = {c.strip().lower() for c in a.skip_category.split(",") if c.strip()}
    # sha256 dari manifest sebelumnya, supaya file lama tidak perlu di-hash ulang
    prev = {}
    mf = MANIFEST / "psi_files.csv"
    if mf.exists():
        with open(mf, newline="", encoding="utf-8") as f:
            for o in csv.DictReader(f):
                if o.get("sha256"):
                    prev[(o["accession"], o["file_name"], o["size_bytes"])] = o["sha256"]
    todo = []
    for r in rows:
        ext = r["file_name"].rsplit(".", 1)[-1].lower() if "." in r["file_name"] else ""
        dest = local_path_for(r["accession"], r["category"], r["file_name"])
        if dest.exists() and (not r["size_bytes"] or dest.stat().st_size == r["size_bytes"]):
            # sudah ada di disk dari proses sebelumnya: tetap dicatat, apa pun filternya
            key = (r["accession"], r["file_name"], str(r["size_bytes"]))
            r.update(status="exists", local_path=str(dest.relative_to(ROOT)),
                     sha256=prev.get(key) or sha256_of(dest))
        elif only and r["accession"] not in only:
            r["status"] = "skipped_not_selected"
        elif r["size_bytes"] > limit:
            r["status"] = "skipped_too_large"
        elif exts and ext not in exts:
            r["status"] = "skipped_ext"
        elif r["category"].lower() in skip:
            r["status"] = "skipped_category"
        else:
            todo.append(r)
    gb = sum(r["size_bytes"] for r in todo) / 1e9
    print(f"3/3 {len(todo)} file ({gb:.2f} GB) masuk kriteria dari {len(rows)} file terdaftar")

    if not a.dry_run and todo:
        done = 0
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for fut in as_completed([ex.submit(download, r) for r in todo]):
                r = fut.result()
                done += 1
                if r["status"] == "failed" or done % 50 == 0 or done == len(todo):
                    print(f"    [{done}/{len(todo)}] {r['status']:10s} {r['file_name'][:70]}")

    with open(MANIFEST / "psi_files.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("Selesai. Status:", counts)
    print("Manifest:", MANIFEST / "psi_files.csv")
    return 1 if counts.get("failed") else 0


if __name__ == "__main__":
    sys.exit(main())
