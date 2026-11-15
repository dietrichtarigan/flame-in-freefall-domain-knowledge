"""M3 tests: digitization provenance, calibration, determinism, analysis semantics, validator guards."""
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PDF = os.path.join(ROOT, "sources", "original", "NASA-TP-2015-216046.pdf")
import glob as _glob
CFGS = {json.load(open(c))["test_id"]: os.path.relpath(c, ROOT) for c in sorted(_glob.glob(os.path.join(ROOT, "data/digitization/configs/*.json")))}
RECS = {t: c.replace("configs/", "").replace(".json", "_record.json") for t, c in CFGS.items()}
ALL = sorted(CFGS)
TABLE = {r["flex_test"]: r for r in csv.DictReader(open(os.path.join(ROOT, "data/extracted/table_ix.csv"), encoding="utf-8"))}


def j(rel):
    return json.load(open(os.path.join(ROOT, rel), encoding="utf-8"))


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def copy_repo(tmp):
    for sub in ("tools", "schemas", "data"):
        shutil.copytree(os.path.join(ROOT, sub), tmp / sub)
    os.makedirs(tmp / "docs")
    return tmp


@pytest.mark.parametrize("test_id", ALL)
def test_source_image_is_the_embedded_jpeg(tmp_path, test_id):
    rec = j(RECS[test_id])
    page = rec["source"]["locator"].split("PDF p. ")[1].rstrip(")")
    subprocess.run(["pdfimages", "-j", "-f", page, "-l", page, PDF, str(tmp_path / "x")], check=True)
    assert sha(tmp_path / "x-000.jpg") == rec["source_image"]["sha256"] == sha(os.path.join(ROOT, rec["source_image"]["path"]))
    assert rec["source"]["source_pdf_sha256"] == sha(PDF)


@pytest.mark.parametrize("test_id", ALL)
def test_calibration_and_self_check(test_id):
    rec = j(RECS[test_id])
    for ax, c in rec["calibration"].items():
        assert len(c["major_tick_px"]) == len(c["tick_labels_as_read"]) >= 4, ax
        assert c["max_abs_residual_px"] < 1.0, ax                     # tick placement within 1 px
    for s in rec["series"]:
        assert s["points"] > 40
        sc = s["self_check"]
        ok = sc["recall_coloured_pixels_covered"] >= 0.85 and sc["precision_redrawn_ring_pixels_coloured"] >= 0.80
        assert (s["quality_flag"] == "OK") == ok                      # every weaker series is flagged, never silently accepted
        assert sc["recall_coloured_pixels_covered"] >= 0.70 and sc["precision_redrawn_ring_pixels_coloured"] >= 0.65
    review = {i["test_id"]: i for i in j("data/digitization/overlay_review.json")["items"]}
    assert review[test_id]["result"] == "PASS (visual)"
    assert os.path.exists(os.path.join(ROOT, rec["overlay_image"]))
    assert rec["evidence_class"] == "DIGITIZED" and len(rec["limitations"]) >= 4


def test_digitization_is_deterministic(tmp_path):
    d = copy_repo(tmp_path)
    for t, cfg in [(t, CFGS[t]) for t in ("FLEX-023", "FLEX-035", "FLEX-110")]:
        subprocess.run([sys.executable, "-I", "tools/digitize_figure.py", PDF, str(d / cfg), str(d)], cwd=ROOT, check=True, capture_output=True)
        rec = j(RECS[t])
        assert open(d / RECS[t], encoding="utf-8").read() == open(os.path.join(ROOT, RECS[t]), encoding="utf-8").read()
        for s in rec["series"]:
            assert sha(d / s["path"]) == sha(os.path.join(ROOT, s["path"])), s["path"]


def test_tick_label_count_mismatch_fails(tmp_path):
    d = copy_repo(tmp_path)
    cfg = json.load(open(d / CFGS["FLEX-035"]))
    cfg["axes"]["x"]["tick_labels_as_read"] = [0, 10, 20]               # one label missing
    json.dump(cfg, open(d / "bad.json", "w"))
    r = subprocess.run([sys.executable, "-I", "tools/digitize_figure.py", PDF, str(d / "bad.json"), str(d)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode != 0 and "major ticks detected" in (r.stderr + r.stdout)


@pytest.mark.parametrize("test_id", ALL)
def test_analysis_semantics(test_id):
    a = j(f"data/analysis/{test_id}_d2_fit.json")
    o = a["outputs"]
    assert a["verification_kind"] == "comparison with published value (not validation)"
    assert a["run_id"].startswith("ANA-") and a["about_physical_test"] == test_id
    assert o["table_ix_K_mm2_s"]["raw"] == TABLE[test_id]["K_mm2_s_raw"]
    lo, hi = o["K_range_over_windows_and_estimators_mm2_s"]
    a_, b_ = o["table_ix_K_rounding_interval_mm2_s"]
    assert o["table_ix_K_within_range"] == (lo <= b_ and a_ <= hi)        # rule: rounding interval overlaps fitted range
    if test_id == "FLEX-051":
        assert not o["table_ix_K_within_range"]                           # recorded as DSC-025, not tuned away
    assert "Not a confidence or prediction interval" in o["K_range_semantics"]
    txt = json.dumps(a).lower()
    for banned in ("std_err", "stderr", "\"ci", "confidence_interval", "p_value", "validated"):
        assert banned not in txt, banned
    man = {d["dataset_id"]: d for d in j("data/MANIFEST.json")["datasets"]}
    for inp in a["inputs"]:
        assert man[inp["dataset_id"]]["sha256"] == inp["sha256"]


def test_records_mark_digitized_only_for_pilot():
    recs = {r["test_id"]: r for r in j("data/records/physical_tests.json")["records"]}
    dig = sorted(t for t, r in recs.items() if r["time_series"]["status"] == "DIGITIZED")
    assert dig == ALL and len(ALL) == 13
    assert all(r["time_series"]["status"] == "UNAVAILABLE" for t, r in recs.items() if t not in dig)
    assert "DSC-023" in recs["FLEX-023"]["discrepancies"]


@pytest.mark.parametrize("mutation", ["drop_row", "edit_config"])
def test_validator_catches_digitization_tampering(tmp_path, mutation):
    d = copy_repo(tmp_path)
    if mutation == "drop_row":
        p = d / "data/digitized/FLEX-035_fig039_droplet_d2.csv"
        lines = open(p).read().splitlines(True); open(p, "w").write("".join(lines[:-1]))
    else:
        p = d / CFGS["FLEX-023"]; c = json.load(open(p)); c["label_reading_note"] += " edited"; json.dump(c, open(p, "w"))
    r = subprocess.run([sys.executable, "-I", "tools/validate_data.py", str(d)], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 1, r.stdout


def test_test_matrix_image_check_complete():
    s = j("data/verification/test_matrix_image_summary.json")
    assert s["rows_checked"] == 153 and s["cells_checked"] == s["ocr_agreements"] + s["ocr_disagreements"]
    rev = j("data/verification/test_matrix_manual_review.json")
    dis = [(r["flex_test"], r["field"]) for r in csv.DictReader(open(os.path.join(ROOT, "data/verification/test_matrix_cell_checks.csv"), encoding="utf-8")) if r["ocr_status"] == "DISAGREE"]
    assert sorted(dis) == sorted((i["flex_test"], i["field"]) for i in rev["items"])
    assert all(i["result"] == "CSV MATCHES IMAGE" for i in rev["items"])
