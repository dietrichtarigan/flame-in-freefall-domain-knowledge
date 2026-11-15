"""Unit tests for the NASA/TP-2015-216046 extractors (run them fresh from the PDF)."""
import csv
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "sources", "original", "NASA-TP-2015-216046.pdf")


def run(tool, out):
    subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", tool), PDF, out], check=True, capture_output=True)
    return list(csv.DictReader(open(out, encoding="utf-8")))


def test_table_ix(tmp_path):
    rows = run("extract_table_ix.py", str(tmp_path / "t.csv"))
    by = {r["flex_test"]: r for r in rows}
    assert len(rows) == 276
    nums = sorted(int(k[5:]) for k in by)
    assert [i for i in range(1, 281) if i not in nums] == [156, 205, 213, 228]
    r = by["FLEX-023"]  # checked by eye against printed p. 20
    assert (r["cir_identifier"], r["P_mmHg_raw"], r["X_O2_raw"], r["D0_mm_raw"], r["D_ext_visible_mm_raw"], r["K_mm2_s_raw"], r["t_burn_s_raw"], r["test_end"]) == \
        ("196F002", "541.8", ".34", "3.01", "–", ".73", "13.1", "Disruption")
    assert r["D_ext_visible_mm"] == "" and r["printed_page"] == "20"
    assert by["FLEX-114"]["P_mmHg_raw"] == "0"  # source typo preserved, not corrected
    assert by["FLEX-227"]["t_burn_s_raw"] == "~6" and by["FLEX-227"]["t_burn_s_approx"] == "True"
    assert by["FLEX-063"]["D_ext_visible_mm_raw"] == "0"
    # the committed dataset equals a fresh extraction
    committed = list(csv.DictReader(open(os.path.join(ROOT, "data", "extracted", "table_ix.csv"), encoding="utf-8")))
    assert committed == rows


def test_appendix_b_index(tmp_path):
    rows = run("extract_appendix_b_index.py", str(tmp_path / "f.csv"))
    assert len(rows) == 276
    by = {r["flex_test"]: r for r in rows}
    assert (by["FLEX-023"]["figure"], by["FLEX-023"]["printed_page"]) == ("27", "51")
    assert (by["FLEX-035"]["figure"], by["FLEX-035"]["printed_page"]) == ("39", "63")
    assert by["FLEX-149"]["figure"] == "153"  # caption printed without a period after the number
    assert "cool flame" in by["FLEX-035"]["caption_verbatim"]
