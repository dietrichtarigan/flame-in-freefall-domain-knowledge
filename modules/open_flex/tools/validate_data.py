#!/usr/bin/env python3
"""Validate registries, records and the dataset manifest against schemas/ and check cross-references.

Checks
  1. JSON Schema (draft 2020-12) validation of: sources, claims, discrepancies, physical tests (each record),
     literature cases (each case), manifest datasets (each dataset).
  2. Referential integrity: every CLM-/DSC-/S- id that is cited exists; every Table IX test has a record;
     every dataset path exists and its SHA-256 equals the manifest; record values equal the CSVs.
  3. Identity rules: PhysicalTest ids match ^FLEX-\\d{3}$; no record of another type uses a FLEX id as its id.

Exit status 0 only if everything passes.  Usage: python3 -I tools/validate_data.py [repo-root]
"""
import csv
import hashlib
import json
import os
import re
import sys

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


def load(root, rel):
    return json.load(open(os.path.join(root, rel), encoding="utf-8"))


def main(root):
    errors = []
    sch_dir = os.path.join(root, "schemas")
    schemas = {f: json.load(open(os.path.join(sch_dir, f), encoding="utf-8")) for f in os.listdir(sch_dir) if f.endswith(".json")}
    reg = Registry().with_resources([(s["$id"], Resource.from_contents(s)) for s in schemas.values()])
    for s in schemas.values():
        Draft202012Validator.check_schema(s)

    def check(schema_file, inst, label):
        v = Draft202012Validator(schemas[schema_file], registry=reg)
        for e in sorted(v.iter_errors(inst), key=lambda e: list(e.path)):
            errors.append(f"[schema] {label}: {'/'.join(map(str, e.path))}: {e.message[:200]}")

    sources = load(root, "data/registry/sources.json")
    claims = load(root, "data/registry/claims.json")
    dscs = load(root, "data/registry/discrepancies.json")
    recs = load(root, "data/records/physical_tests.json")
    lits = load(root, "data/records/literature_cases.json")
    man = load(root, "data/MANIFEST.json")
    check("source.schema.json", sources, "sources.json")
    check("claim.schema.json", claims, "claims.json")
    check("discrepancy.schema.json", dscs, "discrepancies.json")
    for r in recs["records"]:
        check("physical_test.schema.json", r, r.get("test_id", "?"))
    for c in lits["cases"]:
        check("literature_figure_case.schema.json", c, c.get("case_id", "?"))
    for d in man["datasets"]:
        check("dataset.schema.json", d, d.get("dataset_id", "?"))

    import glob
    digs = {}
    for f in sorted(glob.glob(os.path.join(root, "data/digitization/*_record.json"))):
        dr = json.load(open(f, encoding="utf-8"))
        digs[os.path.relpath(f, root)] = dr
        check("digitization_record.schema.json", dr, os.path.relpath(f, root))
        img = os.path.join(root, dr["source_image"]["path"])
        if not os.path.exists(img) or hashlib.sha256(open(img, "rb").read()).hexdigest() != dr["source_image"]["sha256"]:
            errors.append(f"[digitization] source image missing or hash differs: {dr['source_image']['path']}")
        cfgp = os.path.join(root, dr["config"])
        if hashlib.sha256(open(cfgp, "rb").read()).hexdigest() != dr["config_sha256"]:
            errors.append(f"[digitization] config changed since digitization: {dr['config']}")
        for se in dr["series"]:
            n = sum(1 for _ in csv.DictReader(open(os.path.join(root, se["path"]), encoding="utf-8")))
            if n != se["points"]:
                errors.append(f"[digitization] {se['path']}: {n} rows, record says {se['points']}")
    runs = {}
    for f in sorted(glob.glob(os.path.join(root, "data/analysis/*.json"))):
        ar = json.load(open(f, encoding="utf-8"))
        runs[ar["run_id"]] = ar
        check("analysis_run.schema.json", ar, os.path.relpath(f, root))
        for inp in ar["inputs"]:
            d = next((x for x in man["datasets"] if x["dataset_id"] == inp["dataset_id"]), None)
            if d is None:
                errors.append(f"[analysis] {ar['run_id']} input {inp['dataset_id']} not in manifest")
            elif d["sha256"] != inp["sha256"]:
                errors.append(f"[analysis] {ar['run_id']} input {inp['dataset_id']} hash differs from manifest (re-run analysis)")
        if ar["run_id"].startswith("FLEX-"):
            errors.append(f"[identity] analysis run uses a FLEX id: {ar['run_id']}")
        txt = json.dumps(ar).lower()
        for banned in ("confidence interval\": [", "\"ci95", "validated"):
            if banned in txt:
                errors.append(f"[analysis] {ar['run_id']} contains forbidden term {banned!r}")
    unc = load(root, "data/registry/uncertainty_components.json")
    check("uncertainty_component.schema.json", unc, "uncertainty_components.json")
    sids = {s["source_id"] for s in sources["sources"]}
    cids = {c["claim_id"] for c in claims["claims"]}
    dids = {d["discrepancy_id"] for d in dscs["discrepancies"]}
    for coll, key in ((sources["sources"], "source_id"), (claims["claims"], "claim_id"), (dscs["discrepancies"], "discrepancy_id")):
        ids = [x[key] for x in coll]
        if len(ids) != len(set(ids)):
            errors.append(f"[ids] duplicate {key}")
    for c in claims["claims"]:
        for s in c["sources"]:
            if s["source_id"] not in sids:
                errors.append(f"[ref] {c['claim_id']} cites unknown {s['source_id']}")
    for c in lits["cases"]:
        if c["source"]["source_id"] not in sids:
            errors.append(f"[ref] {c['case_id']} cites unknown source")
        if c["case_id"].startswith("FLEX-"):
            errors.append(f"[identity] literature case uses a FLEX id: {c['case_id']}")
    for u in unc["components"]:
        for c in u["claims"]:
            if c not in cids:
                errors.append(f"[ref] {u['id']} cites unknown {c}")
    rec_by = {r["test_id"]: r for r in recs["records"]}
    for r in recs["records"]:
        for f in r["flags"]:
            for c in f["claims"]:
                if c not in cids:
                    errors.append(f"[ref] {r['test_id']} flag cites unknown {c}")
        for d in r["discrepancies"]:
            if d not in dids:
                errors.append(f"[ref] {r['test_id']} cites unknown {d}")
    for d in dscs["discrepancies"]:
        for t in d.get("tests", []):
            if t not in rec_by:
                errors.append(f"[ref] {d['discrepancy_id']} names {t}, which has no record")
            elif d["discrepancy_id"] not in rec_by[t]["discrepancies"]:
                errors.append(f"[ref] {t} record does not list {d['discrepancy_id']}")
    ix = list(csv.DictReader(open(os.path.join(root, "data/extracted/table_ix.csv"), encoding="utf-8")))
    for row in ix:
        r = rec_by.get(row["flex_test"])
        if r is None or not r["table_ix"]["present"]:
            errors.append(f"[records] no Table IX record for {row['flex_test']}"); continue
        for k, cell in r["table_ix"]["values"].items():
            if cell["raw"] != row[k + "_raw"]:
                errors.append(f"[records] {row['flex_test']} {k}: record raw {cell['raw']!r} != CSV {row[k + '_raw']!r}")
    for d in man["datasets"]:
        path = os.path.join(root, d["path"])
        if not os.path.exists(path):
            errors.append(f"[manifest] missing file {d['path']}")
        elif hashlib.sha256(open(path, "rb").read()).hexdigest() != d["sha256"]:
            errors.append(f"[manifest] SHA-256 mismatch for {d['path']} (rebuild with tools/build_app.py)")
    dsids = {d["dataset_id"] for d in man["datasets"]}
    for r in recs["records"]:
        for did in r["time_series"].get("dataset_ids", []):
            if did not in dsids:
                errors.append(f"[ref] {r['test_id']} time series cites unknown dataset {did}")
        if not re.fullmatch(r"FLEX-\d{3}", r["test_id"]):
            errors.append(f"[identity] bad test id {r['test_id']}")

    # M6: simulation runs (schema, identity separation, seeds exist) and the code-verification record
    sims = load(root, "data/simulations/d2law_baseline_runs.json")["runs"]
    seen = set()
    for s in sims:
        check("simulation_run.schema.json", s, s.get("run_id", "?"))
        if s["run_id"] in seen:
            errors.append(f"[identity] duplicate simulation run id {s['run_id']}")
        seen.add(s["run_id"])
        if re.fullmatch(r"FLEX-\d{3}", str(s["run_id"])):
            errors.append(f"[identity] simulation run uses a FLEX id: {s['run_id']}")
        if s.get("seeded_from_physical_test") and s["seeded_from_physical_test"] not in rec_by:
            errors.append(f"[ref] {s['run_id']} seeded from unknown test {s['seeded_from_physical_test']}")
    ver = load(root, "data/verification/d2law_code_verification.json")
    fsha = lambda rel: hashlib.sha256(open(os.path.join(root, rel), "rb").read()).hexdigest()  # noqa: E731
    if ver["status"] != "PASS" or ver["n_passed"] != ver["n_checks"]:
        errors.append("[verification] D²-law code verification is not PASS")
    if ver["implementation_sha256"] != fsha("openflex/d2law.py") or ver["property_table_sha256"] != fsha("data/model/d2law_properties.json"):
        errors.append("[verification] D²-law verification record is stale (re-run tools/verify_d2law.py)")
    for src in load(root, "data/model/d2law_properties.json")["sources"]:
        if src["source_id"] not in sids:
            errors.append(f"[ref] property table cites unknown {src['source_id']}")

    summary = {"sources": len(sids), "claims": len(cids), "discrepancies": len(dids), "physical_tests": len(rec_by),
               "literature_cases": len(lits["cases"]), "datasets": len(man["datasets"]),
               "uncertainty_components": len(unc["components"]), "digitization_records": len(digs), "analysis_runs": len(runs), "errors": len(errors)}
    print(json.dumps(summary))
    for e in errors[:60]:
        print(e)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
