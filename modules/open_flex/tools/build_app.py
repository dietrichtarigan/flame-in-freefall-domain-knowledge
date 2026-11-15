#!/usr/bin/env python3
"""Build the single-file Open FLEX app from modular sources.

Inputs (never modified):
  app/src/styles.css, app/src/body.html, app/src/js/*.js   application code
  data/datasets.spec.json + the files it lists              data, registries, records (validate first:
                                                             tools/validate_data.py)
  vendor/**                                                  pinned libraries (vendor/VENDOR.json)
Outputs:
  data/MANIFEST.json           Dataset records: SHA-256, rows, version, origin, method, history
  dist/open_flex_lab.html      self-contained page (works offline and from file://)

The build is deterministic: no timestamps; build_id is derived from the content hashes.

Usage: python3 -I tools/build_app.py [--no-vendor] [--out PATH]
  --no-vendor  omit Three.js/Plotly (used by tests of the library-unavailable path)
"""
import csv
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def p(*a):
    return os.path.join(ROOT, *a)


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def typed_table_ix(path):
    num = ["P_mmHg", "X_O2", "X_N2", "X_CO2", "X_He", "D0_mm", "D_ext_visible_mm", "K_mm2_s", "t_burn_s"]
    rows = []
    for r in csv.DictReader(open(path, encoding="utf-8")):
        for k in num:
            r[k] = None if r[k] in ("", "None") else float(r[k])
            r[k + "_approx"] = r[k + "_approx"] == "True"
        r["pdf_page"] = int(r["pdf_page"])
        rows.append(r)
    return rows


def figures(path):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        out[r["flex_test"]] = {"figure": int(r["figure"]), "pdf_page": int(r["pdf_page"]),
                               "printed_page": r["printed_page"], "caption_verbatim": r["caption_verbatim"]}
    return out


def digitized_bundle(spec):
    """Per test: DIGITIZED series (t, value), the digitization record summary and the AnalysisRun."""
    out = {}
    for d in spec["datasets"]:
        if d["data_class"] == "DIGITIZED" and d.get("series"):
            t = d["test_id"]
            rows = list(csv.reader(open(p(d["path"]), encoding="utf-8")))[1:]
            e = out.setdefault(t, {"series": [], "record": None, "analysis": None})
            e["series"].append({"dataset_id": d["dataset_id"], "name": d["series"], "unit": d["unit"],
                                "t": [float(r[0]) for r in rows], "v": [float(r[1]) for r in rows]})
            if e["record"] is None:
                rec = json.load(open(p(d["digitization_record"]), encoding="utf-8"))
                e["record"] = {k: rec[k] for k in ("source", "source_image", "time_zero", "limitations", "overlay_image", "label_reading_note")}
                e["record"]["calibration_max_residual_px"] = {k: round(v["max_abs_residual_px"], 2) for k, v in rec["calibration"].items()}
                e["record"]["series"] = [{k: s[k] for k in ("name", "legend_text", "color", "axis", "points", "self_check")} for s in rec["series"]]
        if d["data_class"] == "ANALYSIS" and d.get("test_id"):
            out.setdefault(d["test_id"], {"series": [], "record": None, "analysis": None})["analysis"] = json.load(open(p(d["path"]), encoding="utf-8"))
    return out


def model_bundle():
    """D²-law baseline: property table and code-verification record. Explore mode is enabled in the app
    only if the record says PASS and its hashes match the files being embedded."""
    props_path, ver_path = p("data", "model", "d2law_properties.json"), p("data", "verification", "d2law_code_verification.json")
    ver = json.load(open(ver_path, encoding="utf-8"))
    current = ver["implementation_sha256"] == sha(p("openflex", "d2law.py")) and ver["property_table_sha256"] == sha(props_path)
    return {"properties": json.load(open(props_path, encoding="utf-8")),
            "verification": {k: ver[k] for k in ("model", "status", "n_checks", "n_passed", "scope", "checks", "implementation_sha256", "property_table_sha256")},
            "verification_current": current}


def source_pdf_sha256():
    """SHA-256 of the NASA source PDF. The PDF is not distributed with the code (e.g. in the
    flame-in-freefall repo); when it is absent the registered checksum in SOURCE_CHECKSUMS.sha256
    is used, which is the hash every extracted dataset was checked against."""
    pdf = p("sources", "original", "NASA-TP-2015-216046.pdf")
    if os.path.exists(pdf):
        return sha(pdf)
    for line in open(p("SOURCE_CHECKSUMS.sha256"), encoding="utf-8"):
        if line.strip().endswith("original/NASA-TP-2015-216046.pdf"):
            print("note: source PDF not present; using registered SHA-256 from SOURCE_CHECKSUMS.sha256", file=sys.stderr)
            return line.split()[0]
    raise SystemExit("source PDF missing and no registered checksum in SOURCE_CHECKSUMS.sha256")


def main(argv):
    vendor = "--no-vendor" not in argv
    out = p("dist", "open_flex_lab.html")
    if "--out" in argv:
        out = os.path.abspath(argv[argv.index("--out") + 1])

    spec = json.load(open(p("data", "datasets.spec.json"), encoding="utf-8"))
    datasets = []
    for d in spec["datasets"]:
        path = p(d["path"])
        rows = None
        if d["path"].endswith(".csv"):
            rows = sum(1 for _ in csv.DictReader(open(path, encoding="utf-8")))
        datasets.append(dict(record_type="Dataset", sha256=sha(path), rows=rows, **d))
    manifest = {"manifest_version": "0.2.0", "source_pdf_sha256": source_pdf_sha256(),
                "datasets": sorted(datasets, key=lambda x: x["dataset_id"])}
    os.makedirs(p("data"), exist_ok=True)
    with open(p("data", "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")

    bundle = {
        "table_ix": typed_table_ix(p("data", "extracted", "table_ix.csv")),
        "figures": figures(p("data", "extracted", "appendix_b_figures.csv")),
        "sources": json.load(open(p("data", "registry", "sources.json"), encoding="utf-8")),
        "claims": json.load(open(p("data", "registry", "claims.json"), encoding="utf-8")),
        "discrepancies": json.load(open(p("data", "registry", "discrepancies.json"), encoding="utf-8")),
        "annotations": json.load(open(p("data", "registry", "test_annotations.json"), encoding="utf-8")),
        "records": {r["test_id"]: r for r in json.load(open(p("data", "records", "physical_tests.json"), encoding="utf-8"))["records"]},
        "literature_cases": json.load(open(p("data", "records", "literature_cases.json"), encoding="utf-8")),
        "manifest": manifest,
        "digitized": digitized_bundle(spec),
        "uncertainty": json.load(open(p("data", "registry", "uncertainty_components.json"), encoding="utf-8")),
        "model": model_bundle(),
        "share_config": json.load(open(p("data", "registry", "share_config.json"), encoding="utf-8")),
    }
    js_files = sorted(glob.glob(p("app", "src", "js", "*.js")))
    code_hash = hashlib.sha256(b"".join(open(f, "rb").read() for f in [p("app", "src", "styles.css"), p("app", "src", "body.html")] + js_files)).hexdigest()
    manifest_hash = sha(p("data", "MANIFEST.json"))
    vendor_meta = json.load(open(p("vendor", "VENDOR.json")))
    bundle["build"] = {
        "build_id": hashlib.sha256((code_hash + manifest_hash + str(vendor)).encode()).hexdigest()[:12],
        "app_source_sha256": code_hash,
        "data_manifest_sha256": manifest_hash,
        "vendor_inlined": vendor,
        "vendor": [{k: v[k] for k in ("package", "version", "path", "sha256")} for v in vendor_meta["files"] if v["path"].endswith(".js")],
        "milestone": "Phase B M6.1",
    }
    data_js = "window.OPEN_FLEX_DATA = " + json.dumps(bundle, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/") + ";"

    parts = ['<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8" />\n<meta name="viewport" content="width=device-width, initial-scale=1.0" />\n',
             "<title>Open FLEX Virtual Laboratory — original FLEX, evidence-traceable (independent prototype)</title>\n",
             "<style>\n" + open(p("app", "src", "styles.css"), encoding="utf-8").read() + "\n</style>\n</head>\n<body>\n",
             open(p("app", "src", "body.html"), encoding="utf-8").read()]
    if vendor:
        for v in vendor_meta["files"]:
            if not v["path"].endswith(".js"):
                continue
            path = p("vendor", v["path"])
            assert sha(path) == v["sha256"], "vendor file hash mismatch: " + v["path"]
            src = open(path, encoding="utf-8").read()
            assert "</script" not in src.lower(), "vendor file contains </script: " + v["path"]
            parts.append("<script>/* %s@%s %s sha256=%s */\n%s\n</script>\n" % (v["package"], v["version"], v["path"], v["sha256"], src))
    parts.append("<script>\n" + data_js + "\n</script>\n")
    for f in js_files:
        parts.append("<script>/* app/src/js/%s */\n%s\n</script>\n" % (os.path.basename(f), open(f, encoding="utf-8").read()))
    parts.append("</body>\n</html>\n")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("".join(parts))
    print("built", out, os.path.getsize(out), "bytes; build_id", bundle["build"]["build_id"], "; sha256", sha(out))


if __name__ == "__main__":
    main(sys.argv[1:])
