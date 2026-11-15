#!/usr/bin/env python3
"""Index NASA/TP-2015-216046 Appendix B: Figure number <-> FLEX test, PDF page, printed page, caption.

The caption text is kept verbatim (whitespace normalized). Captions are the TP authors'
qualitative observations (e.g. drift, cool-flame inference) and are stored as such.

Usage: python3 -I tools/extract_appendix_b_index.py <TP.pdf> <out.csv>
"""
import csv
import re
import subprocess
import sys



def page_text(pdf, p):
    return subprocess.run(["pdftotext", "-layout", "-f", str(p), "-l", str(p), pdf, "-"],
                          capture_output=True, text=True, check=True).stdout


def main(pdf, out):
    npages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", pdf], capture_output=True, text=True).stdout).group(1))
    rows = []
    for p in range(35, npages + 1):
        t = page_text(pdf, p)
        printed = re.search(r"NASA/TP—2015-216046\s+(\d+)", t)
        body = t.split("NASA/TP—2015-216046")[0]
        for m in re.finditer(r"Figure (\d+)\.?—Test (FLEX[–−-]\d{3})\.", body):
            start = m.start()
            nxt = re.search(r"Figure \d+\.?—Test", body[m.end():])
            seg = body[start: m.end() + (nxt.start() if nxt else len(body) - m.end())]
            cap = " ".join(seg.split())
            test = re.sub(r"[–−]", "-", m.group(2))
            rows.append({"figure": int(m.group(1)), "flex_test": test, "pdf_page": p,
                         "printed_page": printed.group(1) if printed else "",
                         "caption_verbatim": cap,
                         "source": "NASA/TP-2015-216046 Appendix B"})
    rows.sort(key=lambda r: r["figure"])
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} figures -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
