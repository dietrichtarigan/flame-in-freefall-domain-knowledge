#!/usr/bin/env python3
"""Page-image check of data/extracted/test_matrix.csv (Tables I-VIII), cell by cell.

Same method as tools/verify_table_ix.py route C: 300-dpi rendering by pdftoppm, each word cropped using its
pdfplumber box (geometry only), numbers read as Tesseract digits + connected-component layout (decimal point
/ dash), words (dates, fuel, Yes/No) read by Tesseract directly.  Disagreements are written as crop images
for visual review; the review result is recorded by hand in data/verification/test_matrix_manual_review.json.

Usage: python3 -I tools/verify_test_matrix_images.py <TP.pdf> <repo-root>
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

import pdfplumber
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_table_ix import CAP, DPI, TESS_VERSION, norm, ocr, skeleton_of_image, skeleton_of_text  # noqa: E402
from verify_test_matrix import ORDER  # noqa: E402


def expected_tokens(r):
    exp = [("test_number", r["flex_test"][5:])]
    for i, w in enumerate(r["date_as_printed"].split()):
        exp.append((f"date_{i}", w))
    if r["fuel_source"] == "column":
        exp.append(("fuel", r["fuel"].capitalize()))
    for k in ORDER[r["table"]]:
        exp.append((k, r[k] if k == "fiber" else r[k + "_raw"]))
    return exp


def main(pdf, root):
    rows = list(csv.DictReader(open(os.path.join(root, "data/extracted/test_matrix.csv"), encoding="utf-8")))
    out = os.path.join(root, "data/verification")
    crops = os.path.join(out, "test_matrix_ocr_disagreements")
    os.makedirs(crops, exist_ok=True)
    checks = []
    with pdfplumber.open(pdf) as pl, tempfile.TemporaryDirectory() as tmp:
        pages = {}
        for r in rows:
            pg = int(r["pdf_page"])
            if pg not in pages:
                base = os.path.join(tmp, f"p{pg}")
                subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(pg), "-l", str(pg), "-gray", "-png", "-singlefile", pdf, base], check=True)
                pages[pg] = (Image.open(base + ".png"), pl.pages[pg - 1].extract_words(x_tolerance=1.5, y_tolerance=2))
            img, ws = pages[pg]
            s = DPI / 72.0
            st = [w for w in ws if w["text"] == r["flex_test"][5:] and w["x0"] < 200][0]
            line = sorted([w for w in ws if abs(w["top"] - st["top"]) < 2.5], key=lambda w: w["x0"])
            for (field, val), w in zip(expected_tokens(r), line):
                pad = 1.2
                cell = img.crop((int((w["x0"] - pad) * s), int((w["top"] - pad) * s), int((w["x1"] + pad) * s), int((w["bottom"] + pad) * s)))
                big = Image.new("L", (cell.width + 40, cell.height + 40), 255)
                big.paste(cell, (20, 20))
                if re.fullmatch(r"[0-9.]+", val):
                    digits = ocr(big, "0123456789")
                    sk = skeleton_of_image(big, CAP * (w["bottom"] - w["top"]) * s)
                    o = f"digits={digits} layout={sk}"
                    ok = re.sub(r"\D", "", digits) == re.sub(r"\D", "", val) and sk == skeleton_of_text(val)
                else:
                    o = ocr(big)
                    ok = norm(o) == norm(val)
                st_ = "MATCH" if ok else "DISAGREE"
                if not ok:
                    big.save(os.path.join(crops, f"{r['flex_test']}_{field}.png"))
                checks.append({"flex_test": r["flex_test"], "table": r["table"], "field": field, "csv": val, "ocr": o,
                               "ocr_status": st_, "pdf_page": r["pdf_page"]})
    with open(os.path.join(out, "test_matrix_cell_checks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]), lineterminator="\n")
        w.writeheader(); w.writerows(checks)
    summary = {"tool": "tools/verify_test_matrix_images.py", "ocr_engine": TESS_VERSION, "render": f"pdftoppm {DPI} dpi grayscale",
               "rows_checked": len({c["flex_test"] for c in checks}), "cells_checked": len(checks),
               "ocr_agreements": sum(c["ocr_status"] == "MATCH" for c in checks),
               "ocr_disagreements": sum(c["ocr_status"] == "DISAGREE" for c in checks),
               "note": "Disagreements are resolved by visual inspection; see test_matrix_manual_review.json."}
    json.dump(summary, open(os.path.join(out, "test_matrix_image_summary.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
