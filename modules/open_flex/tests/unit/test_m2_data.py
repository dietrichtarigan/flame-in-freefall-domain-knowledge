"""M2 data-architecture tests: extraction reproducibility, cross-checks, records, schemas, verification."""
import csv
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "sources", "original", "NASA-TP-2015-216046.pdf")
PY = [sys.executable, "-I"]


def rows(rel):
    return list(csv.DictReader(open(os.path.join(ROOT, rel), encoding="utf-8")))


def run(*args, cwd=ROOT, check=True):
    return subprocess.run([*PY, *args], cwd=cwd, capture_output=True, text=True, check=check)


@pytest.fixture(scope="module")
def tmp_repo(tmp_path_factory):
    """A copy of tools/, schemas/ and data/ so tools can be re-run without touching the repo."""
    d = tmp_path_factory.mktemp("repo")
    for sub in ("tools", "schemas", "data"):
        shutil.copytree(os.path.join(ROOT, sub), d / sub)
    os.makedirs(d / "sources" / "original")
    os.symlink(PDF, d / "sources" / "original" / "NASA-TP-2015-216046.pdf")
    return d


def test_test_matrix_reproducible(tmp_path):
    out = tmp_path / "m.csv"
    run("tools/extract_test_matrix.py", PDF, str(out))
    assert open(out, encoding="utf-8").read() == open(os.path.join(ROOT, "data/extracted/test_matrix.csv"), encoding="utf-8").read()


def test_test_matrix_known_cells():
    m = {r["flex_test"]: r for r in rows("data/extracted/test_matrix.csv")}
    assert len(m) == 153
    assert m["FLEX-019"]["X_O2_raw"] == "0.400" and m["FLEX-019"]["table"] == "III"
    assert m["FLEX-053"]["fiber"] == "No" and m["FLEX-124"]["fiber"] == "Yes"
    assert m["FLEX-001"]["X_CO2_raw"] == "0.005" and m["FLEX-001"]["X_CO2_source"] == "table header"
    assert m["FLEX-010"]["X_CO2_raw"] == "0.700" and m["FLEX-010"]["fiber_source"] == "table header"
    assert m["FLEX-070"]["D0_mm_raw"] == "1.30" and m["FLEX-073"]["D0_mm_raw"] == "4.72"
    assert m["FLEX-156"]["fuel"] == "heptane"
    missing = {f"FLEX-{i:03d}" for i in [72, *range(131, 140), 144, 145, 146]}
    assert missing.isdisjoint(m) and max(m) == "FLEX-166"


def test_crosscheck_reproducible(tmp_repo):
    run("tools/crosscheck_tables.py", str(tmp_repo))
    for rel in ("data/derived/crosscheck_matrix_vs_ix.csv", "data/derived/fiber_from_captions.csv"):
        assert open(tmp_repo / rel, encoding="utf-8").read() == open(os.path.join(ROOT, rel), encoding="utf-8").read(), rel


def test_crosscheck_findings():
    c = rows("data/derived/crosscheck_matrix_vs_ix.csv")
    differs = {(r["flex_test"], r["field"]) for r in c if r["status"] == "DIFFERS"}
    assert ("FLEX-053", "fiber") in differs and ("FLEX-124", "fiber") in differs
    assert sum(1 for r in c if r["field"] == "fiber" and r["status"] == "AGREE") == 150
    assert ("FLEX-114", "date") in differs and ("FLEX-070", "D0_mm") in differs
    caps = rows("data/derived/fiber_from_captions.csv")
    assert len(caps) == 276 and not [r for r in caps if r["caption_fiber_status"] == "AMBIGUOUS"]


def test_records_reproducible(tmp_repo):
    run("tools/build_records.py", str(tmp_repo))
    rel = "data/records/physical_tests.json"
    assert open(tmp_repo / rel, encoding="utf-8").read() == open(os.path.join(ROOT, rel), encoding="utf-8").read()


DIGITIZED_TESTS = {d["test_id"] for d in json.load(open(os.path.join(ROOT, "data/datasets.spec.json"), encoding="utf-8"))["datasets"]
                   if d["data_class"] == "DIGITIZED" and d.get("series")}


def test_records_content():
    recs = {r["test_id"]: r for r in json.load(open(os.path.join(ROOT, "data/records/physical_tests.json"), encoding="utf-8"))["records"]}
    assert len(recs) == 277                                     # 276 Table IX tests + FLEX-156 (matrix only)
    assert recs["FLEX-156"]["table_ix"] == {"present": False} and recs["FLEX-156"]["fiber"]["status"] == "MATRIX_ONLY"
    assert recs["FLEX-053"]["fiber"]["status"] == "DIFFERS" and "DSC-014" in recs["FLEX-053"]["discrepancies"]
    assert recs["FLEX-200"]["fiber"]["status"] == "CAPTION_ONLY" and not recs["FLEX-200"]["test_matrix"]["present"]
    assert set(recs["FLEX-070"]["discrepancies"]) >= {"DSC-016"} and set(recs["FLEX-073"]["discrepancies"]) >= {"DSC-016"}
    for r in recs.values():                                     # no simulated / predicted content in physical records
        assert r["time_series"]["status"] == ("DIGITIZED" if r["test_id"] in DIGITIZED_TESTS else "UNAVAILABLE")
        if r["table_ix"]["present"]:
            assert r["table_ix"]["evidence_class"] == "PUBLISHED_TABULATED"


def test_validator_passes():
    out = run("tools/validate_data.py")
    assert '"errors": 0' in out.stdout


@pytest.mark.parametrize("mutation", ["bad_claim_ref", "flex_id_on_literature_case", "edited_csv", "bad_evidence_class"])
def test_validator_catches_errors(tmp_path, mutation):
    d = tmp_path / "r"
    for sub in ("tools", "schemas", "data"):
        shutil.copytree(os.path.join(ROOT, sub), d / sub)
    if mutation == "bad_claim_ref":
        p = d / "data/records/physical_tests.json"; j = json.load(open(p))
        j["records"][0]["flags"][0]["claims"].append("CLM-999"); json.dump(j, open(p, "w"))
    elif mutation == "flex_id_on_literature_case":
        p = d / "data/records/literature_cases.json"; j = json.load(open(p))
        j["cases"][0]["case_id"] = "FLEX-035"; json.dump(j, open(p, "w"))
    elif mutation == "edited_csv":
        p = d / "data/extracted/table_ix.csv"; s = open(p, encoding="utf-8").read()
        open(p, "w", encoding="utf-8").write(s.replace(",0.52,0.52,", ",0.53,0.53,", 1))
    elif mutation == "bad_evidence_class":
        p = d / "data/registry/claims.json"; j = json.load(open(p))
        j["claims"][0]["evidence_class"] = "NASA_VALIDATED"; json.dump(j, open(p, "w"))
    r = run("tools/validate_data.py", str(d), check=False)
    assert r.returncode == 1, r.stdout


def test_table_ix_verification_complete():
    s = json.load(open(os.path.join(ROOT, "data/verification/table_ix_verification_summary.json")))
    assert s["rows_checked"] == 276 and s["cells_checked"] == 276 * 15
    assert s["route_b_mismatches"] == 0 and s["rows_not_parsed_by_route_b"] == 0
    review = json.load(open(os.path.join(ROOT, "data/verification/table_ix_manual_review.json"), encoding="utf-8"))
    reviewed = {(i["flex_test"], i["field"]): i["result"] for i in review["items"]}
    disagreements = [(r["flex_test"], r["field"]) for r in rows("data/verification/table_ix_cell_checks.csv") if r["ocr_status"] == "DISAGREE"]
    assert len(disagreements) == s["ocr_disagreements"] == len(reviewed)
    assert all(reviewed.get(k) == "CSV MATCHES IMAGE" for k in disagreements)


def test_test_matrix_verification():
    s = json.load(open(os.path.join(ROOT, "data/verification/test_matrix_verification.json"), encoding="utf-8"))
    assert s["rows"] == 153 and s["match"] == 153 and not s["problems"]
    assert all(h["found"] for h in s["header_constants"])


def test_schemas_are_valid_2020_12():
    from jsonschema import Draft202012Validator
    for f in os.listdir(os.path.join(ROOT, "schemas")):
        Draft202012Validator.check_schema(json.load(open(os.path.join(ROOT, "schemas", f), encoding="utf-8")))
