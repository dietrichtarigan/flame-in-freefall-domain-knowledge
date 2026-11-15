"""M5 data tests: new claims are found on their cited PDF pages; new discrepancies; digitization method version."""
import glob
import json
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "sources", "original", "NASA-TP-2015-216046.pdf")
CLAIMS = {c["claim_id"]: c for c in json.load(open(os.path.join(ROOT, "data/registry/claims.json"), encoding="utf-8"))["claims"]}
PHRASES = {   # a verbatim phrase from the TP that each claim paraphrases
    "CLM-041": "we did estimate (extrapolate", "CLM-043": "Natural convection, however, destroys the spherical symmetry",
    "CLM-044": "assumes the expected spherical shape within approximately 1 s", "CLM-045": "inside the blue flame envelope",
    "CLM-046": "measurements are of the outer edge of the flame", "CLM-047": "an orthogonal view of the flame",
    "CLM-048": "the white LED turned off",
}


def page_text(n):
    return " ".join(subprocess.run(["pdftotext", "-layout", "-f", str(n), "-l", str(n), PDF, "-"], capture_output=True, text=True, check=True).stdout.split())


@pytest.mark.parametrize("cid", sorted(PHRASES))
def test_claim_phrase_on_cited_page(cid):
    loc = CLAIMS[cid]["sources"][0]["locator"]
    pdf_page = int(re.search(r"PDF p\. (\d+)", loc).group(1))
    printed = int(re.search(r"printed p\. (\d+)", loc).group(1))
    txt = page_text(pdf_page)
    assert " ".join(PHRASES[cid].split()) in txt, (cid, loc)
    assert re.search(r"NASA/TP—2015-216046 %d\b" % printed, txt), (cid, "printed page number does not match")


def test_new_discrepancies():
    d = {x["discrepancy_id"]: x for x in json.load(open(os.path.join(ROOT, "data/registry/discrepancies.json"), encoding="utf-8"))["discrepancies"]}
    assert d["DSC-025"]["tests"] == ["FLEX-051"] and d["DSC-025"]["preferred"] is None
    assert "Fig. 3" in d["DSC-026"]["values"][0]["source"]


def test_digitization_records_use_method_1_1_and_all_reviewed():
    recs = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(os.path.join(ROOT, "data/digitization/*_record.json")))]
    assert len(recs) == 13 and all(r["method_version"] == "1.1.0" for r in recs)
    assert all(r["marker_detection"]["threshold_fraction_of_legend_score"] == 0.30 for r in recs)
    review = json.load(open(os.path.join(ROOT, "data/digitization/overlay_review.json"), encoding="utf-8"))
    assert sorted(i["test_id"] for i in review["items"]) == sorted(r["test_id"] for r in recs)
    flagged = [(r["test_id"], s["name"]) for r in recs for s in r["series"] if s["quality_flag"] != "OK"]
    assert flagged == [("FLEX-263", "lluv_flame_diameter")]
