#!/usr/bin/env python3
"""Cross-check three places in NASA/TP-2015-216046 that describe the same tests.

Inputs (all extracted verbatim, nothing corrected):
  data/extracted/table_ix.csv           Table IX  (results; "actual" D0, P in mmHg, reconstructed composition)
  data/extracted/test_matrix.csv        Tables I-VIII (test matrix; D0, fiber, P in atm, nominal composition)
  data/extracted/appendix_b_figures.csv Appendix B captions (verbatim)

Outputs (DERIVED; comparison results, not new measurements):
  data/derived/fiber_from_captions.csv        caption keyword classification -> Fiber-supported / Free-floating
  data/derived/crosscheck_matrix_vs_ix.csv    one row per (test, field) where both tables give a value

Comparison rule (no statistical meaning): two printed numbers "agree within printed rounding" when
|a - b| <= (half a unit in the last printed digit of a) + (half a unit of b) + 1e-9.  P is compared as
P_IX[mmHg] / 760 against P_matrix[atm].  A difference beyond rounding is reported as DIFFERS — it is a
fact about the printed tables, not a judgement about which is right.  The tables have different
meanings (planned/nominal matrix vs. reconstructed results; App. A.1 defines Table IX D0 as the diameter
at igniter ON), so differences are expected and are not errors in themselves.

Usage: python3 -I tools/crosscheck_tables.py <repo-root>
"""
import csv
import datetime
import os
import re
import sys

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "June": 6, "July": 7, "Aug": 8,
          "Sept": 9, "Oct": 10, "Nov": 11, "Dec": 12}
FIBER_RE = re.compile(r"fiber[- ]supported", re.I)
FREE_RE = re.compile(r"free[- ]floating", re.I)


def half_ulp(raw):
    raw = raw.strip().lstrip("~")
    if "." not in raw:
        return 0.5
    return 0.5 * 10 ** (-len(raw.split(".")[1]))


def matrix_date(s):
    m = re.match(r"([A-Z][a-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", s)
    return datetime.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))


def ix_date(s):
    mo, d, y = s.split("/")
    return datetime.date(2000 + int(y), int(mo), int(d))


def main(root):
    rd = lambda p: list(csv.DictReader(open(os.path.join(root, p), encoding="utf-8")))
    ix = {r["flex_test"]: r for r in rd("data/extracted/table_ix.csv")}
    mx = {r["flex_test"]: r for r in rd("data/extracted/test_matrix.csv")}
    figs = rd("data/extracted/appendix_b_figures.csv")
    os.makedirs(os.path.join(root, "data/derived"), exist_ok=True)

    # 1. Fiber status from captions
    cap_rows = []
    for f in figs:
        c = f["caption_verbatim"]
        fib, free = bool(FIBER_RE.search(c)), bool(FREE_RE.search(c))
        status = "Fiber-supported" if fib and not free else "Free-floating" if free and not fib else "AMBIGUOUS"
        m = (FIBER_RE.search(c) or FREE_RE.search(c))
        cap_rows.append({"flex_test": f["flex_test"], "figure": f["figure"], "caption_fiber_status": status,
                         "matched_phrase": m.group(0) if m else "", "pdf_page": f["pdf_page"],
                         "method": "regex 'fiber[- ]supported' / 'free[- ]floating' on verbatim caption",
                         "evidence_class": "DERIVED"})
    with open(os.path.join(root, "data/derived/fiber_from_captions.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(cap_rows[0]), lineterminator="\n")
        w.writeheader(); w.writerows(cap_rows)
    cap = {r["flex_test"]: r for r in cap_rows}

    # 2. Matrix vs Table IX vs captions
    out = []

    def add(t, field, a_raw, a_src, b_raw, b_src, status, note=""):
        out.append({"flex_test": t, "field": field, "matrix_value_raw": a_raw, "matrix_locator": a_src,
                    "other_value_raw": b_raw, "other_locator": b_src, "status": status, "note": note})

    for t, m in sorted(mx.items()):
        mloc = f"Table {m['table']}, PDF p. {m['pdf_page']}"
        r = ix.get(t)
        c = cap.get(t)
        if c:
            mf = {"Yes": "Fiber-supported", "No": "Free-floating"}.get(m["fiber"], "")
            add(t, "fiber", m["fiber"] + (" (header)" if m["fiber_source"] == "table header" else ""), mloc,
                c["caption_fiber_status"], f"Appendix B Fig. {c['figure']}, PDF p. {c['pdf_page']}",
                "AGREE" if mf == c["caption_fiber_status"] else "DIFFERS")
        if r is None:
            add(t, "presence", "listed", mloc, "absent from Table IX", "Table IX", "DIFFERS")
            continue
        rloc = f"Table IX, PDF p. {r['pdf_page']}"
        add(t, "fuel", m["fuel"], mloc, r["fuel"], rloc, "AGREE" if m["fuel"] == r["fuel"] else "DIFFERS")
        add(t, "date", m["date_as_printed"], mloc, r["date_mdy_as_printed"], rloc,
            "AGREE" if matrix_date(m["date_as_printed"]) == ix_date(r["date_mdy_as_printed"]) else "DIFFERS")
        pairs = [("D0_mm", "D0_mm", "D0_mm", 1.0), ("P", "P_atm", "P_mmHg", 1 / 760.0),
                 ("X_O2", "X_O2", "X_O2", 1.0), ("X_N2", "X_N2", "X_N2", 1.0), ("X_CO2", "X_CO2", "X_CO2", 1.0)]
        for field, mk, rk, scale in pairs:
            a_raw, b_raw = m[mk + "_raw"], r[rk + "_raw"]
            if a_raw == "" or b_raw in ("", "–"):
                continue
            a, b = float(m[mk]), float(r[rk]) * scale
            tol = half_ulp(a_raw) + half_ulp(b_raw) * scale + 1e-9
            diff = b - a
            src_note = " (matrix value from table header)" if m[mk + "_source"] == "table header" else ""
            add(t, field, a_raw, mloc, b_raw + (" mmHg" if field == "P" else ""), rloc,
                "AGREE" if abs(diff) <= tol else "DIFFERS",
                f"difference {diff:+.4g}; rounding tolerance {tol:.4g}{src_note}")
    for t in sorted(set(ix) - set(mx)):
        pass  # tests after FLEX-166 (and 072, 131-139, 144-146) are not in Tables I-VIII; recorded in records
    with open(os.path.join(root, "data/derived/crosscheck_matrix_vs_ix.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]), lineterminator="\n")
        w.writeheader(); w.writerows(out)
    from collections import Counter
    cnt = Counter((o["field"], o["status"]) for o in out)
    for k in sorted(cnt):
        print(k, cnt[k])
    print("captions:", Counter(r["caption_fiber_status"] for r in cap_rows))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
