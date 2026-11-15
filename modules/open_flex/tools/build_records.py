#!/usr/bin/env python3
"""Assemble one PhysicalTest record per FLEX test from the extracted tables and registries.

Inputs : data/extracted/{table_ix,test_matrix,appendix_b_figures}.csv, data/derived/*.csv,
         data/verification/table_ix_cell_checks.csv (optional), data/registry/*.json
Output : data/records/physical_tests.json  (validated by tools/validate_data.py against
         schemas/physical_test.schema.json)

Nothing is computed from physics here.  Values are copied as printed (raw text kept); comparisons are
copied from the DERIVED cross-check; fiber status is reported from both places it appears, never merged
silently.  Records are sorted by test id and serialised deterministically.

Usage: python3 -I tools/build_records.py [repo-root]
"""
import csv
import json
import os
import sys

IX_FIELDS = {"P_mmHg": "mmHg", "X_O2": "mole fraction", "X_N2": "mole fraction", "X_CO2": "mole fraction",
             "X_He": "mole fraction", "D0_mm": "mm", "D_ext_visible_mm": "mm", "K_mm2_s": "mm^2/s", "t_burn_s": "s"}
MX_FIELDS = {"D0_mm": "mm", "P_atm": "atm", "X_O2": "mole fraction", "X_CO2": "mole fraction", "X_N2": "mole fraction"}


def rd(root, rel):
    path = os.path.join(root, rel)
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []


def fnum(s):
    return None if s in ("", "None") else float(s)


def main(root):
    ix = {r["flex_test"]: r for r in rd(root, "data/extracted/table_ix.csv")}
    mx = {r["flex_test"]: r for r in rd(root, "data/extracted/test_matrix.csv")}
    figs = {r["flex_test"]: r for r in rd(root, "data/extracted/appendix_b_figures.csv")}
    capfib = {r["flex_test"]: r for r in rd(root, "data/derived/fiber_from_captions.csv")}
    cross = {}
    for r in rd(root, "data/derived/crosscheck_matrix_vs_ix.csv"):
        if r["status"] == "DIFFERS" and r["field"] != "presence":
            cross.setdefault(r["flex_test"], []).append(
                {"field": r["field"], "matrix": f"{r['matrix_value_raw']} ({r['matrix_locator']})",
                 "other": f"{r['other_value_raw']} ({r['other_locator']})", "status": "DIFFERS", "note": r["note"]})
    checks = {}
    for r in rd(root, "data/verification/table_ix_cell_checks.csv"):
        checks.setdefault(r["flex_test"], []).append(r)
    reviewed = set()
    mr = os.path.join(root, "data/verification/table_ix_manual_review.json")
    if os.path.exists(mr):
        for it in json.load(open(mr, encoding="utf-8"))["items"]:
            if it["result"] == "CSV MATCHES IMAGE":
                reviewed.add((it["flex_test"], it["field"]))
    ann = json.load(open(os.path.join(root, "data/registry/test_annotations.json"), encoding="utf-8"))
    dsc = json.load(open(os.path.join(root, "data/registry/discrepancies.json"), encoding="utf-8"))["discrepancies"]
    dsc_by_test = {}
    for d in dsc:
        for t in d.get("tests", []):
            dsc_by_test.setdefault(t, set()).add(d["discrepancy_id"])
    for t, a in ann["tests"].items():
        for d in a.get("discrepancies", []):
            dsc_by_test.setdefault(t, set()).add(d)

    spec_ds = json.load(open(os.path.join(root, "data/datasets.spec.json"), encoding="utf-8"))["datasets"]
    records = []
    for t in sorted(set(ix) | set(mx)):
        n = int(t[5:])
        r, m, f, c = ix.get(t), mx.get(t), figs.get(t), capfib.get(t)
        rec = {"record_type": "PhysicalTest", "test_id": t,
               "identity": {"flex_test_as_printed": r["flex_test_as_printed"] if r else f"{n:03d} (Table {m['table']})",
                            "cir_identifier": r["cir_identifier"] if r else None,
                            "note": "Physical test on the ISS documented in NASA/TP-2015-216046. This identity is never given to simulated or modified inputs."}}
        if r:
            ch = checks.get(t, [])
            auto = sum(1 for x in ch if x["ocr_status"] == "MATCH")
            weak = sum(1 for x in ch if x["ocr_status"] in ("MATCH_O0_I1", "MATCH_DASH_GLYPH"))
            rev = sum(1 for x in ch if x["ocr_status"] == "DISAGREE" and (t, x["field"]) in reviewed)
            rec["table_ix"] = {
                "present": True, "evidence_class": "PUBLISHED_TABULATED",
                "source": {"source_id": "S01", "locator": f"Table IX, printed p. {r['printed_page']} (PDF p. {r['pdf_page']})"},
                "date_as_printed": r["date_mdy_as_printed"], "time_gmt": r["time_gmt"], "fuel": r["fuel"],
                "values": {k: {"raw": r[k + "_raw"], "value": fnum(r[k]), "approx": r[k + "_approx"] == "True", "unit": u}
                           for k, u in IX_FIELDS.items()} | {"test_end": {"raw": r["test_end_raw"], "value": r["test_end"]}},
                "extraction_check": {
                    "second_parser": (f"{sum(1 for x in ch if x['route_b_status'] == 'MATCH')}/{len(ch)} cells match (pdfplumber)" if ch else "not run"),
                    "page_image": (f"{auto + weak + rev}/{len(ch)} cells agree with the page image"
                                   + (f"; {weak} allowing O/0 or dash-glyph equivalence" if weak else "")
                                   + (f"; {rev} confirmed by visual review" if rev else "") if ch else "not run")}}
        else:
            rec["table_ix"] = {"present": False}
        if m:
            vals = {k: {"raw": m[k + "_raw"], "value": fnum(m[k]), "unit": u, "origin": m[k + "_source"]}
                    for k, u in MX_FIELDS.items() if m[k + "_source"] != "not given"}
            rec["test_matrix"] = {
                "present": True, "table": m["table"], "evidence_class": "PUBLISHED_TABULATED",
                "source": {"source_id": "S01", "locator": f"Table {m['table']}, printed p. {m['printed_page']} (PDF p. {m['pdf_page']})"},
                "meaning": "Test matrix entry (nominal conditions; the TP does not define how matrix D0 was obtained).",
                "date_as_printed": m["date_as_printed"], "fuel": m["fuel"], "values": vals}
        else:
            rec["test_matrix"] = {"present": False,
                                  "absent_reason": "Not listed in Tables I–VIII (they cover FLEX–001 to –166 except 072, 131–139, 144–146); see DSC-022."}
        mf = {"Yes": "Fiber-supported", "No": "Free-floating"}.get(m["fiber"]) if m else None
        cf = c["caption_fiber_status"] if c else None
        status = ("AGREE" if mf == cf else "DIFFERS") if (mf and cf) else ("CAPTION_ONLY" if cf else "MATRIX_ONLY" if mf else "UNKNOWN")
        ev = []
        if m:
            ev.append(f"Table {m['table']}: {m['fiber']}" + (" (table header)" if m["fiber_source"] == "table header" else ""))
        if c:
            ev.append(f"Appendix B Fig. {c['figure']} caption: '{c['matched_phrase']}'")
        disp = {"AGREE": cf, "CAPTION_ONLY": f"{cf} (caption only)", "DIFFERS": "Sources disagree", "MATRIX_ONLY": f"{mf} (test matrix only)", "UNKNOWN": "Unknown"}[status]
        rec["fiber"] = {"status": status, "test_matrix": m["fiber"] if m else None, "caption": cf, "display": disp, "evidence": ev}
        rec["appendix_b"] = ({"figure": int(f["figure"]), "pdf_page": int(f["pdf_page"]), "printed_page": int(f["printed_page"]),
                              "caption_verbatim": f["caption_verbatim"],
                              "plot_kind": "raster plot: droplet D² (red) and LLUV flame size (blue) vs time"} if f else None)
        dig = [d for d in spec_ds if d.get("test_id") == t and d["data_class"] == "DIGITIZED" and d.get("series")]
        if dig:
            rec["time_series"] = {"status": "DIGITIZED", "dataset_ids": [d["dataset_id"] for d in dig],
                                  "note": "Read from the Appendix B plot (DIGITIZED, Phase B M3); not original measurements. See the digitization record for method and limits."}
        else:
            rec["time_series"] = {"status": "UNAVAILABLE",
                                  "note": "The TP prints these data only as plots; the electronic data files it mentions (CLM-040) were not available to this project, and this plot has not been digitized."}
        flags = [{"flag": g["flag"], "text": g["text"], "claims": g["claims"]} for g in ann["global_flags"]]
        flags += [{"flag": g["flag"], "text": g["text"], "claims": g["claims"]} for g in ann["range_flags"] if g["first"] <= n <= g["last"]]
        rec["flags"] = flags
        rec["discrepancies"] = sorted(dsc_by_test.get(t, []))
        rec["crosscheck"] = cross.get(t, [])
        lc = ann["tests"].get(t, {}).get("literature_candidates")
        if lc:
            rec["literature_candidates"] = lc
        records.append(rec)
    out = os.path.join(root, "data/records/physical_tests.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump({"registry_version": "0.2.0", "record_count": len(records), "records": records}, fh,
                  indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    print(f"wrote {len(records)} PhysicalTest records to {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
