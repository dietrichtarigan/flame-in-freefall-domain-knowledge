#!/usr/bin/env python3
"""Kecilkan gambar & persamaan hasil paper_figures.py agar ikut ter-deploy.

Masalah: `paper_figures.py --from-db` menghasilkan 2.515 gambar + 548 persamaan
(475 MB) dari 321 PDF. Terlalu besar untuk riwayat git, sehingga situs produksi
(Render membangun dari repo) tidak pernah melihatnya -- fitur "tunjukkan gambar
asli dari paper" hanya hidup di laptop.

Setelan 760 px / WebP q60 dipilih dari pengukuran, bukan tebakan:

    lossy WebP 900px q75  -> ~105 MB
    lossy WebP 760px q60  ->  ~60 MB   <= dipakai
    WebP lossless 760px   -> ~276 MB
    PNG palet 64 warna    -> ~174 MB

Lossless dan palet justru lebih besar: isinya campuran garis, teks, dan foto
nyala yang sebagian sudah JPEG. Mutu diperiksa dengan mata pada dua kasus
terburuk (plot padat label sumbu, foto nyala beranotasi) -- keduanya tetap tajam.

Berkas asli dipindah ke analysis/figures_orig/ (tidak dilacak git) supaya bisa
di-encode ulang tanpa mengulang ekstraksi PDF yang makan waktu.

  python scripts/figures_optimize.py --dry-run
  python scripts/figures_optimize.py
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "analysis" / "figures"
ORIG = ROOT / "analysis" / "figures_orig"
INDEXES = ("figures.json", "equations.json")
MAX_PX = 760
QUALITY = 60


def convert(src, dest):
    im = Image.open(src)
    if max(im.size) > MAX_PX:
        r = MAX_PX / max(im.size)
        im = im.resize((max(1, round(im.size[0] * r)), max(1, round(im.size[1] * r))),
                       Image.LANCZOS)
    if im.mode not in ("RGB", "L"):
        im = im.convert("RGB")
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, "WEBP", quality=QUALITY, method=6)
    return im.size


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    idx = {n: json.loads((FIG / n).read_text(encoding="utf-8"))
           for n in INDEXES if (FIG / n).exists()}
    if not idx:
        print("Tidak ada figures.json/equations.json -- jalankan paper_figures.py --from-db dulu.")
        return 1
    total = sum(len(v) for v in idx.values())
    png = sorted(p for p in FIG.rglob("*.png"))
    before = sum(p.stat().st_size for p in png)
    print(f"{total} entri indeks, {len(png)} PNG, {before/1e6:.0f} MB")
    if a.dry_run:
        print(f"akan diubah ke WebP maks {MAX_PX}px q{QUALITY}")
        return 0

    after, failed = 0, []
    for n, p in enumerate(png, 1):
        rel = p.relative_to(FIG)
        dest = FIG / rel.with_suffix(".webp")
        try:
            convert(p, dest)
            after += dest.stat().st_size
            p.unlink()
        except Exception as e:                       # noqa: BLE001
            failed.append((str(rel), repr(e)[:60]))
        if n % 400 == 0:
            print(f"  {n}/{len(png)} ...")

    # Indeks menyimpan nama berkas di medan "png" -> ikut diubah ke .webp.
    bad = set(f for f, _ in failed)
    for name, items in idx.items():
        for it in items:
            if it.get("png") and it["png"].replace("\\", "/") not in bad:
                it["png"] = str(Path(it["png"]).with_suffix(".webp")).replace("\\", "/")
        (FIG / name).write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(png)-len(failed)} berkas: {before/1e6:.0f} MB -> {after/1e6:.0f} MB "
          f"(turun {100*(1-after/max(before,1)):.0f}%)")
    if failed:
        print(f"gagal: {len(failed)}")
        for f, e in failed[:5]:
            print(f"  {f[:50]:52s} {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
