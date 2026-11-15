#!/usr/bin/env python3
"""Extract Table IX ("Results by test number and FLEX identifier") from NASA/TP-2015-216046.

Provenance rules (Phase B):
  * The source PDF is never modified; it is read through `pdftotext -layout`.
  * Every cell is kept verbatim (column `*_raw`) next to its parsed value.
  * "–" (en dash) is the TP's own "not available / did not occur" marker -> parsed value None.
  * "~" prefixes (e.g. "~6") are preserved and flagged as approximate.
  * Each row records the PDF page it came from, so any value can be checked by eye.

Usage: python3 -I tools/extract_table_ix.py <path-to-TP-pdf> <out.csv>
"""
import csv
import hashlib
import re
import subprocess
import sys

ROW = re.compile(r"^\s*(FLEX–\d{3})\s+(\S+)\s+(\d{1,2}/\d{1,2}/\d{2})\s+(\S+)\s+(Methanol|Heptane)\s+(.*)$")
COLS = ["P_mmHg", "X_O2", "X_N2", "X_CO2", "X_He", "D0_mm", "D_ext_visible_mm", "K_mm2_s", "t_burn_s", "test_end"]


def num(tok):
    """Return (value, approximate_flag). '–' -> None."""
    if tok in ("–", "-"):
        return None, False
    approx = tok.startswith("~")
    t = tok.lstrip("~")
    if t.startswith("."):
        t = "0" + t
    return float(t), approx


def main(pdf, out):
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    rows = []
    # Table IX lives on PDF pages 25-32 (printed pp. 19-27); scan a margin either side.
    for page in range(22, 36):
        txt = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
                             capture_output=True, text=True, check=True).stdout
        printed = re.search(r"NASA/TP—2015-216046\s+(\d+)", txt)
        for line in txt.splitlines():
            m = ROW.match(line)
            if not m:
                continue
            test, ident, date, gmt, fuel, rest = m.groups()
            toks = rest.split()
            if len(toks) != 10:
                raise SystemExit(f"Unexpected column count on page {page}: {line!r}")
            rec = {"flex_test": test.replace("–", "-"), "flex_test_as_printed": test,
                   "cir_identifier": ident, "date_mdy_as_printed": date, "time_gmt": gmt,
                   "fuel": fuel.lower()}
            for name, tok in zip(COLS, toks):
                rec[name + "_raw"] = tok
                if name == "test_end":
                    rec[name] = tok
                    continue
                v, approx = num(tok)
                rec[name] = v
                rec[name + "_approx"] = approx
            rec["pdf_page"] = page
            rec["printed_page"] = printed.group(1) if printed else ""
            rec["source"] = "NASA/TP-2015-216046 Table IX"
            rec["source_pdf_sha256"] = sha
            rows.append(rec)
    fields = list(rows[0].keys())
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
