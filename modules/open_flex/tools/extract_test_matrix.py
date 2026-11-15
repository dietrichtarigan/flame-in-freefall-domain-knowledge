#!/usr/bin/env python3
"""Extract the FLEX test matrices (Tables I-VIII) from NASA/TP-2015-216046.

These tables give, per planned/conducted test: date, fuel, nominal initial droplet diameter D0,
fiber yes/no (Tables III-VII), nominal pressure P (atm) and nominal composition.  They are a
different table from Table IX (measured/reconstructed results) and the two disagree in places;
this extractor only records what Tables I-VIII print.  Nothing is corrected.

Provenance rules (same as extract_table_ix.py):
  * read-only access to the PDF through `pdftotext -layout` (one call per page);
  * every cell kept verbatim in `*_raw` next to the parsed value;
  * constants stated in a table header (Tables I, II: composition; "droplet not supported by a fiber")
    are copied to the rows with column `*_source = header`, never silently;
  * each row records the table number, the PDF page and the printed page.

Usage: python3 -I tools/extract_test_matrix.py <TP.pdf> <out.csv>
"""
import csv
import hashlib
import re
import subprocess
import sys

DATE = r"([A-Z][a-z]{2,4}\.?\s+\d{1,2},\s+\d{4})"
ROWRE = re.compile(r"^\s*(\d{3})\s+" + DATE + r"\s+(.*?)\s*$")
TITLE = re.compile(r"TABLE\s+(I{1,3}|IV|VI{0,3}|V|IX)\.—")

# table -> (fuel (None = column), has_fiber_column, numeric columns after the optional ones)
SPEC = {
    "I":    dict(fuel=None, fiber=False, cols=["D0_mm", "P_atm"]),
    "II":   dict(fuel=None, fiber=False, cols=["D0_mm", "P_atm"]),
    "III":  dict(fuel=None, fiber=True,  cols=["D0_mm", "P_atm", "X_O2", "X_N2"]),
    "IV":   dict(fuel="methanol", fiber=True, cols=["D0_mm", "P_atm", "X_O2", "X_N2"]),
    "V":    dict(fuel="heptane", fiber=True,  cols=["D0_mm", "P_atm", "X_O2", "X_N2"]),
    "VI":   dict(fuel="methanol", fiber=True, cols=["D0_mm", "P_atm", "X_O2", "X_CO2", "X_N2"]),
    "VII":  dict(fuel="heptane", fiber=True,  cols=["D0_mm", "P_atm", "X_O2", "X_CO2", "X_N2"]),
    "VIII": dict(fuel=None, fiber=False, cols=["D0_mm", "P_atm", "X_O2", "X_CO2", "X_N2"]),
}
# Constants printed in table headers (verbatim wording kept in header_note)
HEADER_CONST = {
    "I": dict(X_O2="0.21", X_CO2="0.005", X_N2="0.79", fiber="No",
              note="[Droplet not supported by a fiber; ... 0.21 oxygen, 0.005 carbon dioxide, 0.79 nitrogen (balance) at 1.0-atm pressure.]"),
    "II": dict(X_O2="0.21", X_CO2="0.700", X_N2="0.090", fiber="No",
               note="[Droplet not supported by a fiber; 0.21 oxygen, 0.700 carbon dioxide, 0.090 nitrogen mole fraction.]"),
    "VIII": dict(fiber="No", note="[Droplets not supported by a fiber.]"),
}


def num(tok):
    t = tok.strip()
    if t.startswith("."):
        t = "0" + t
    return float(t)


def main(pdf, out):
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    rows, seen = [], {}
    for page in range(14, 26):                      # Tables I-VIII are on PDF pp. 16-21; scan a margin
        txt = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page), pdf, "-"],
                             capture_output=True, text=True, check=True).stdout
        printed = re.search(r"NASA/TP—2015-216046\s+(\d+)", txt)
        table = None
        for line in txt.splitlines():
            t = TITLE.search(line)
            if t and t.group(1) != "IX":
                table = t.group(1)
                continue
            if "TABLE IX" in line:
                table = None
            m = ROWRE.match(line)
            if not m or table is None:
                continue
            test, date, rest = m.groups()
            spec = SPEC[table]
            toks = rest.split()
            rec = {"table": table, "flex_test": f"FLEX-{test}", "date_as_printed": date,
                   "pdf_page": page, "printed_page": int(printed.group(1)) if printed else None}
            i = 0
            if spec["fuel"] is None:
                rec["fuel"] = toks[0].lower(); rec["fuel_source"] = "column"; i = 1
            else:
                rec["fuel"] = spec["fuel"]; rec["fuel_source"] = "table title"
            ncols = len(spec["cols"]) + (1 if spec["fiber"] else 0)
            if len(toks) - i != ncols:
                raise SystemExit(f"Table {table} p{page}: expected {ncols} cells, got {toks[i:]!r} in {line!r}")
            cells = {}
            for name in spec["cols"][:1]:
                cells[name] = toks[i]; i += 1
            if spec["fiber"]:
                cells["fiber"] = toks[i]; i += 1
            for name in spec["cols"][1:]:
                cells[name] = toks[i]; i += 1
            const = HEADER_CONST.get(table, {})
            for name in ["D0_mm", "P_atm", "X_O2", "X_CO2", "X_N2"]:
                if name in cells:
                    rec[name + "_raw"] = cells[name]; rec[name] = num(cells[name]); rec[name + "_source"] = "cell"
                elif name in const:
                    rec[name + "_raw"] = const[name]; rec[name] = num(const[name]); rec[name + "_source"] = "table header"
                else:
                    rec[name + "_raw"] = ""; rec[name] = ""; rec[name + "_source"] = "not given"
            if "fiber" in cells:
                rec["fiber"] = cells["fiber"]; rec["fiber_source"] = "cell"
            else:
                rec["fiber"] = const.get("fiber", ""); rec["fiber_source"] = "table header" if const.get("fiber") else "not given"
            rec["header_note"] = const.get("note", "")
            if rec["flex_test"] in seen:
                raise SystemExit(f"Duplicate {rec['flex_test']} in tables {seen[rec['flex_test']]} and {table}")
            seen[rec["flex_test"]] = table
            rec["source"] = f"NASA/TP-2015-216046 Table {table}"
            rec["source_pdf_sha256"] = sha
            rows.append(rec)
    rows.sort(key=lambda r: r["flex_test"])
    fields = ["flex_test", "table", "date_as_printed", "fuel", "fuel_source", "D0_mm_raw", "D0_mm", "D0_mm_source",
              "fiber", "fiber_source", "P_atm_raw", "P_atm", "P_atm_source", "X_O2_raw", "X_O2", "X_O2_source",
              "X_CO2_raw", "X_CO2", "X_CO2_source", "X_N2_raw", "X_N2", "X_N2_source", "header_note",
              "pdf_page", "printed_page", "source", "source_pdf_sha256"]
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows to {out}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
