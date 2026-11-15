#!/usr/bin/env python3
"""Check every cell of data/extracted/table_ix.csv by two routes that are independent of the extractor.

Route B — second text-layer parser.  pdfplumber word boxes (not pdftotext), rows grouped by y position.
          Catches parsing/column-assignment errors in the pdftotext-based extractor.  It reads the same
          text layer, so it cannot catch a text layer that differs from what is drawn on the page.
Route C — reading the rendered page image.  Each page is rendered by pdftoppm at 300 dpi; every cell is
          cropped using the word box from route B (geometry only).  Tesseract drops leading decimal points
          and lone dashes (tested: ".21" -> "21"), so numeric cells are read in two parts:
            (1) digits: Tesseract with a digits-only whitelist;
            (2) layout: connected-component analysis of the ink (OpenCV) classifies each blob as a glyph,
                a decimal point (small, near-square, sitting on the baseline) or a dash (wide, thin,
                mid-height), giving a skeleton such as ".#" for ".6" or "–" for "–".
          A numeric cell matches when both the digit string and the skeleton equal those of the CSV value.
          Text cells (identifier, fuel, test end) are read by Tesseract directly; for the CIR identifier
          the letters O/I and digits 0/1 are treated as equivalent and such cells get the weaker status
          MATCH_O0_I1 (Times O and 0 are hard for OCR).  This compares the CSV with what a reader sees.  OCR makes its own mistakes, so an OCR disagreement is a
          prompt to look at the image, not a finding; every disagreement is written out as a crop image
          and must be resolved by a human look (recorded in data/verification/table_ix_manual_review.json).

Outputs (data/verification/):
  table_ix_cell_checks.csv     one row per cell: csv value, route-B value, OCR value, statuses
  table_ix_ocr_disagreements/  crop image per OCR disagreement (gitignored; regenerate with this tool)
  table_ix_verification_summary.json

Usage: python3 -I tools/verify_table_ix.py <TP.pdf> <repo-root>
"""
import csv
import json
import os
import re
import subprocess
import sys
import tempfile

import cv2
import numpy as np
import pdfplumber
from PIL import Image

FIELDS = ["flex_test_as_printed", "cir_identifier", "date_mdy_as_printed", "time_gmt", "fuel_as_printed",
          "P_mmHg_raw", "X_O2_raw", "X_N2_raw", "X_CO2_raw", "X_He_raw", "D0_mm_raw",
          "D_ext_visible_mm_raw", "K_mm2_s_raw", "t_burn_s_raw", "test_end_raw"]
NUMERIC = set(FIELDS[5:14]) | {"date_mdy_as_printed", "time_gmt"}
DPI = 300
CAP = 0.66   # Times digit height as a fraction of the font box height (pdfplumber word box)
TESS_VERSION = subprocess.run(["tesseract", "--version"], capture_output=True, text=True).stdout.split("\n")[0]


def norm(s):
    s = s.strip().replace(" ", "")
    s = re.sub(r"[—–−\-_~]+$", lambda m: "–" if "~" not in m.group(0) else m.group(0), s)
    s = s.replace("—", "–").replace("−", "–").replace("-", "–")
    return s


def ocr(img, whitelist=None):
    with tempfile.NamedTemporaryFile(suffix=".png") as f:
        img.save(f.name)
        cfg = ["--psm", "7"]
        if whitelist:
            cfg += ["-c", "tessedit_char_whitelist=" + whitelist]
        r = subprocess.run(["tesseract", f.name, "-", *cfg], capture_output=True, text=True)
        return r.stdout.strip()


def skeleton_of_image(img, cap=None):
    """'#' = run of glyph blobs, '.' = decimal point, '–' = dash, '~' = tilde-like wide blob above mid."""
    a = np.array(img)
    n, _, stats, _ = cv2.connectedComponentsWithStats((a < 128).astype(np.uint8), connectivity=8)
    blobs = [tuple(stats[i]) for i in range(1, n) if stats[i][4] >= 4]
    if not blobs:
        return ""
    cap = cap or max(b[3] for b in blobs)          # cap: glyph height in px (from the font box when known)
    tall = [b for b in blobs if b[3] > 0.5 * cap]
    base = max(b[1] + b[3] for b in tall) if tall else max(b[1] + b[3] for b in blobs)
    out = []
    for x, y, w, h, area in sorted(blobs, key=lambda b: b[0]):
        if h <= 0.3 * cap and w <= 0.3 * cap and abs((y + h) - base) <= 0.15 * cap:
            k = "."
        elif w >= 1.8 * h and h <= 0.25 * cap:
            k = "–"
        else:
            k = "#"
        if k == "#" and out and out[-1] == "#":
            continue
        out.append(k)
    return "".join(out)


def skeleton_of_text(s):
    return re.sub(r"#+", "#", re.sub(r"[0-9]", "#", s))


def main(pdf, root):
    csv_rows = {r["flex_test"]: r for r in csv.DictReader(open(os.path.join(root, "data/extracted/table_ix.csv"), encoding="utf-8"))}
    outdir = os.path.join(root, "data/verification")
    crops = os.path.join(outdir, "table_ix_ocr_disagreements")
    os.makedirs(crops, exist_ok=True)
    checks = []
    with pdfplumber.open(pdf) as pl, tempfile.TemporaryDirectory() as tmp:
        for page in range(26, 35):
            p = pl.pages[page - 1]
            base = os.path.join(tmp, f"p{page}")
            subprocess.run(["pdftoppm", "-r", str(DPI), "-f", str(page), "-l", str(page), "-gray", "-png",
                            "-singlefile", pdf, base], check=True)
            img = Image.open(base + ".png")
            s = DPI / 72.0
            ws = p.extract_words(x_tolerance=1.5, y_tolerance=2)
            for st in [w for w in ws if w["text"].startswith("FLEX–") and w["x0"] < 80]:
                row = sorted([w for w in ws if abs(w["top"] - st["top"]) < 2.5], key=lambda w: w["x0"])
                test = st["text"].replace("–", "-")
                rec = csv_rows.get(test)
                if len(row) != 15 or rec is None:
                    checks.append({"flex_test": test, "field": "ROW", "csv": "", "route_b": f"{len(row)} words",
                                   "ocr": "", "route_b_status": "ROW_NOT_PARSED", "ocr_status": "", "pdf_page": page})
                    continue
                rec = dict(rec, fuel_as_printed=rec["fuel"].capitalize())
                for field, w in zip(FIELDS, row):
                    pad = 1.2
                    box = (int((w["x0"] - pad) * s), int((w["top"] - pad) * s),
                           int((w["x1"] + pad) * s), int((w["bottom"] + pad) * s))
                    cell = img.crop(box)
                    big = Image.new("L", (cell.width + 40, cell.height + 40), 255)
                    big.paste(cell, (20, 20))
                    v_csv, v_b = rec[field], w["text"]
                    b_ok = v_csv == v_b
                    if field in NUMERIC and field not in ("date_mdy_as_printed", "time_gmt"):
                        digits = ocr(big, "0123456789") if re.search(r"\d", v_csv) else ""
                        sk = skeleton_of_image(big, CAP * (w["bottom"] - w["top"]) * s)
                        o = f"digits={digits} layout={sk}"
                        ok = re.sub(r"\D", "", digits) == re.sub(r"\D", "", v_csv) and sk == skeleton_of_text(v_csv)
                        o_status = "MATCH" if ok else "DISAGREE"
                    elif field in ("date_mdy_as_printed", "time_gmt"):
                        if v_csv in ("–", "-"):
                            o = "layout=" + skeleton_of_image(big, CAP * (w["bottom"] - w["top"]) * s)
                            o_status = "MATCH" if o == "layout=–" else "DISAGREE"
                        else:
                            o = ocr(big, "0123456789/:")
                            o_status = "MATCH" if norm(o) == norm(v_csv) else "DISAGREE"
                    else:
                        o = ocr(big)
                        if norm(o) == norm(v_csv):
                            o_status = "MATCH"
                        elif field == "cir_identifier" and norm(o).replace("O", "0").replace("I", "1") == v_csv.replace("O", "0").replace("I", "1"):
                            o_status = "MATCH_O0_I1"
                        elif field == "flex_test_as_printed" and re.sub(r"\D", "", o) == re.sub(r"\D", "", v_csv) and o.startswith("FLEX"):
                            o_status = "MATCH_DASH_GLYPH"
                        else:
                            o_status = "DISAGREE"
                    o_ok = o_status == "MATCH"
                    if o_status == "DISAGREE":
                        big.save(os.path.join(crops, f"{test}_{field}.png"))
                    checks.append({"flex_test": test, "field": field, "csv": v_csv, "route_b": v_b, "ocr": o,
                                   "route_b_status": "MATCH" if b_ok else "MISMATCH",
                                   "ocr_status": o_status, "pdf_page": page})
    with open(os.path.join(outdir, "table_ix_cell_checks.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(checks[0]), lineterminator="\n")
        w.writeheader(); w.writerows(checks)
    cells = [c for c in checks if c["field"] != "ROW"]
    summary = {
        "tool": "tools/verify_table_ix.py",
        "ocr_engine": TESS_VERSION, "render": f"pdftoppm {DPI} dpi grayscale",
        "rows_checked": len({c["flex_test"] for c in cells}),
        "cells_checked": len(cells),
        "route_b_mismatches": sum(c["route_b_status"] == "MISMATCH" for c in cells),
        "rows_not_parsed_by_route_b": sum(c["field"] == "ROW" for c in checks),
        "ocr_status_counts": {k: sum(c["ocr_status"] == k for c in cells) for k in sorted({c["ocr_status"] for c in cells})},
        "ocr_agreements": sum(c["ocr_status"] == "MATCH" for c in cells),
        "ocr_disagreements": sum(c["ocr_status"] == "DISAGREE" for c in cells),
        "csv_rows_not_seen": sorted(set(csv_rows) - {c["flex_test"] for c in checks}),
        "note": "OCR disagreements are resolved by human inspection of the crop images; see table_ix_manual_review.json.",
    }
    json.dump(summary, open(os.path.join(outdir, "table_ix_verification_summary.json"), "w"), indent=1, sort_keys=True)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
