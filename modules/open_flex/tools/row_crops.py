#!/usr/bin/env python3
"""Render table rows of NASA/TP-2015-216046 as images, for checking extracted values by eye.

For each (pdf_page, row_key) the row is located in the PDF text layer (pdfplumber word boxes), the page is
rendered by `pdftoppm` (poppler), and a horizontal strip around the row (plus the table header strip, when
asked) is saved as PNG.  The image comes from the page rendering, not from the text layer, so it shows what a
reader sees.

Usage: python3 -I tools/row_crops.py <TP.pdf> <out_dir> <pdf_page>:<row_key> [...]
       row_key = the first word of the row as printed, e.g. FLEX–053 (Table IX) or 053 (Tables I-VIII)
"""
import os
import subprocess
import sys
import tempfile

import pdfplumber
from PIL import Image

DPI = 200


def render(pdf, page, tmp):
    base = os.path.join(tmp, f"p{page}")
    out = base + ".png"
    if not os.path.exists(out):
        subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(page), "-l", str(page), "-png", "-singlefile",
                        pdf, base], check=True)
    return out


def crop_row(pdf, pl, page, key, out_dir, tmp, pad=3.0):
    p = pl.pages[page - 1]
    words = p.extract_words(keep_blank_chars=False, use_text_flow=False)
    hits = [w for w in words if w["text"] == key and w["x0"] < p.width * 0.25]
    if not hits:
        raise SystemExit(f"{key} not found at left margin of PDF page {page}")
    w = hits[0]
    img = Image.open(render(pdf, page, tmp))
    s = DPI / 72.0
    box = (0, int((w["top"] - pad) * s), img.width, int((w["bottom"] + pad) * s))
    path = os.path.join(out_dir, f"p{page}_{key.replace('–', '-')}.png")
    img.crop(box).save(path)
    return path


def main(pdf, out_dir, specs):
    os.makedirs(out_dir, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp, pdfplumber.open(pdf) as pl:
        for spec in specs:
            page, key = spec.split(":", 1)
            print(crop_row(pdf, pl, int(page), key, out_dir, tmp))


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
