#!/usr/bin/env python3
"""Second-parser check of data/extracted/test_matrix.csv (Tables I-VIII).

pdfplumber word boxes (not pdftotext) are grouped into rows by y position; for every row whose first word
is a 3-digit test number at the left margin, the row's words are compared with the CSV cells in order
(test, date words, [fuel], D0, [fiber], P, [O2], [CO2/N2 in printed order]).  Header constants (Tables I,
II, VIII) are not in the rows and are checked separately against the header text.

Usage: python3 -I tools/verify_test_matrix.py <TP.pdf> <repo-root>
"""
import csv
import json
import os
import sys

import pdfplumber

ORDER = {"III": ["D0_mm", "fiber", "P_atm", "X_O2", "X_N2"], "IV": ["D0_mm", "fiber", "P_atm", "X_O2", "X_N2"],
         "V": ["D0_mm", "fiber", "P_atm", "X_O2", "X_N2"],
         "VI": ["D0_mm", "fiber", "P_atm", "X_O2", "X_CO2", "X_N2"], "VII": ["D0_mm", "fiber", "P_atm", "X_O2", "X_CO2", "X_N2"],
         "I": ["D0_mm", "P_atm"], "II": ["D0_mm", "P_atm"], "VIII": ["D0_mm", "P_atm", "X_O2", "X_CO2", "X_N2"]}
HEADER_TEXT = {"I": ["0.21 oxygen mole fraction", "0.005 carbon dioxide mole fraction", "0.79 nitrogen mole fraction",
                     "Droplet not supported by a fiber"],
               "II": ["0.21 oxygen mole fraction, 0.700 carbon", "0.090 nitrogen mole fraction", "Droplet not supported by a fiber"],
               "VIII": ["Droplets not supported by a fiber."]}


def main(pdf, root):
    rows = list(csv.DictReader(open(os.path.join(root, "data/extracted/test_matrix.csv"), encoding="utf-8")))
    res = []
    with pdfplumber.open(pdf) as pl:
        page_words = {}
        for r in rows:
            pg = int(r["pdf_page"])
            if pg not in page_words:
                page_words[pg] = pl.pages[pg - 1].extract_words(x_tolerance=1.5, y_tolerance=2)
            ws = page_words[pg]
            num = r["flex_test"][5:]
            st = [w for w in ws if w["text"] == num and w["x0"] < 200]
            if len(st) != 1:
                res.append({"flex_test": r["flex_test"], "status": f"ROW_NOT_FOUND ({len(st)} hits)"}); continue
            line = [w["text"] for w in sorted([w for w in ws if abs(w["top"] - st[0]["top"]) < 2.5], key=lambda w: w["x0"])]
            exp = [num] + r["date_as_printed"].split()
            if r["fuel_source"] == "column":
                exp.append(r["fuel"].capitalize())
            exp += [r[k] if k == "fiber" else r[k + "_raw"] for k in ORDER[r["table"]]]
            res.append({"flex_test": r["flex_test"], "status": "MATCH" if line == exp else "MISMATCH",
                        "expected": exp, "found": line})
        header_checks = []
        for t, phrases in HEADER_TEXT.items():
            pg = int(next(r["pdf_page"] for r in rows if r["table"] == t))
            txt = " ".join(pl.pages[pg - 1].extract_text().split())
            for ph in phrases:
                header_checks.append({"table": t, "phrase": ph, "found": ph in txt})
    summary = {"tool": "tools/verify_test_matrix.py", "rows": len(res),
               "match": sum(x["status"] == "MATCH" for x in res),
               "problems": [x for x in res if x["status"] != "MATCH"],
               "header_constants": header_checks}
    os.makedirs(os.path.join(root, "data/verification"), exist_ok=True)
    json.dump(summary, open(os.path.join(root, "data/verification/test_matrix_verification.json"), "w"),
              indent=1, ensure_ascii=False, sort_keys=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "header_constants"}, indent=1)[:3000])
    print("header phrases found:", sum(h["found"] for h in header_checks), "/", len(header_checks))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
