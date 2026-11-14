#!/usr/bin/env python3
"""Lokasi freefall.sqlite yang SELALU sesuai versi terbaru di git.

freefall.sqlite (>100 MB) tidak dilacak git; yang dilacak kb/gold/freefall.sqlite.gz. Fungsi gold_db()
membuka .gz bila .sqlite belum ada atau lebih tua darinya. Di Windows, berkas lama yang masih dibuka
proses lain tidak bisa ditimpa; salinan baru (freefall.sqlite.new) dipakai langsung dan peringatan dicetak.

  python scripts/kbpaths.py        # pasang/perbarui freefall.sqlite dari .gz
Variabel FREEFALL_DB menimpa semuanya (mis. untuk uji).
"""
import gzip
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD_DIR = ROOT / "kb" / "gold"
_CACHE = {}


def gold_db():
    if os.environ.get("FREEFALL_DB"):
        return Path(os.environ["FREEFALL_DB"])
    if "p" in _CACHE:
        return _CACHE["p"]
    db, gz, new = GOLD_DIR / "freefall.sqlite", GOLD_DIR / "freefall.sqlite.gz", GOLD_DIR / "freefall.sqlite.new"
    path = db
    if gz.exists() and (not db.exists() or db.stat().st_mtime < gz.stat().st_mtime):
        if not (new.exists() and new.stat().st_mtime >= gz.stat().st_mtime):
            tmp = GOLD_DIR / "freefall.sqlite.tmp"
            with gzip.open(gz, "rb") as f, open(tmp, "wb") as g:
                shutil.copyfileobj(f, g, 1 << 20)
            os.replace(tmp, new)
        try:
            os.replace(new, db)
        except OSError:
            print("PERINGATAN: kb/gold/freefall.sqlite lama sedang dibuka proses lain; memakai freefall.sqlite.new. "
                  "Tutup server lama lalu jalankan: python scripts/kbpaths.py", file=sys.stderr)
            path = new
    _CACHE["p"] = path
    return path


if __name__ == "__main__":
    print(gold_db())
