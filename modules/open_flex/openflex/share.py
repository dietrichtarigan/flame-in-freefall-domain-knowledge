"""Shareable simulation-run files and their reproduction check (reference implementation).

A run file lets someone post a D²-law baseline run (inputs, results, versions) so that anyone with the
package or the app can re-run it and see whether the same numbers come out. It contains no personal data and
no timestamps. The browser implementation (app/src/js/62_share.js) must agree with this module; the tests
check both directions on the same files.

What "REPRODUCED" means: the documented model, run on the file's inputs, gives the file's outputs. It does
NOT mean the model agrees with FLEX. Nothing here validates a model.

Statuses of a check
  REPRODUCED      every check passed
  NOT_REPRODUCED  the file's model matches this one but a result, id, modification list, comparison or hash differs
  CANNOT_CHECK    the file was made with a different model version or property table: results may legitimately differ
  INVALID         not a run file of this format, or inputs outside the model's range / unknown test
"""
import hashlib
import json
import math
import re

from . import d2law

FORMAT = "OpenFLEXSharedRun"
FORMAT_VERSION = "1.0"
MAX_BYTES = 200_000
SCOPE = ("D²-law educational baseline run (NUMERICAL_SIMULATION). Not a FLEX measurement, not a prediction of extinction, "
         "and not validated against FLEX. Reproduced means the documented model gives these numbers from these inputs.")
TOP_KEYS = {"record_type", "format_version", "labels", "run_id", "model", "seeded_from_physical_test", "modified_inputs",
            "inputs", "outputs", "comparison", "exported_by", "content_sha256"}
INPUT_KEYS = {"fuel", "X", "D0_mm", "T_inf_K", "T_prop_K", "rho_l_at", "Q_variant", "P_atm", "T_prop_rule"}
OUTPUT_KEYS = ("B", "K_mm2_s", "t_burn_s", "flame_standoff_ratio", "T_flame_K", "T_prop_K")
MOD_KEYS = ["fuel", "X.O2", "X.N2", "X.CO2", "X.He", "D0_mm", "T_inf_K", "T_prop_K", "Q_variant", "rho_l_at"]
REL_TOL = 1e-6


# --- canonical JSON, same rules as OF.canonicalJSON in the app and tools/canonical_json.py -------------------------
def _num(x):
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if math.isfinite(x) and x == int(x) and abs(x) < 1e21:
        return str(int(x))
    return repr(x)


def canonical(v):
    if v is None:
        return "null"
    if isinstance(v, (bool, int, float)):
        return _num(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(v[k]) for k in sorted(v)) + "}"
    raise TypeError(type(v))


def sha(v):
    return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()


def r8(x):
    return None if x is None else float(f"{x:.8g}")


# --- building -------------------------------------------------------------------------------------------------------
def seeded_inputs(row):
    """Inputs for a Table IX row, exactly as tools/run_d2law_baseline.py builds them."""
    num = lambda k: None if row[k] in ("", "None") else float(row[k])  # noqa: E731
    p = num("P_mmHg")
    return {"fuel": row["fuel"], "X": {"O2": num("X_O2"), "N2": num("X_N2"), "CO2": num("X_CO2"), "He": num("X_He")},
            "D0_mm": num("D0_mm"), "T_inf_K": 298.15, "P_atm": round(p / 760.0, 6) if p else None,
            "rho_l_at": "boil", "Q_variant": "nominal", "T_prop_rule": "(T_s+T_f)/2, iterated"}


def modified_keys(seed, inputs):
    mk = []
    if inputs.get("fuel") != seed.get("fuel"):
        mk.append("fuel")
    for k in ("O2", "N2", "CO2", "He"):
        if (inputs["X"].get(k) or 0) != (seed["X"].get(k) or 0):
            mk.append("X." + k)
    if inputs.get("D0_mm") != seed.get("D0_mm"):
        mk.append("D0_mm")
    if inputs.get("T_inf_K") != seed.get("T_inf_K"):
        mk.append("T_inf_K")
    if inputs.get("T_prop_K") is not None:
        mk.append("T_prop_K")
    if inputs.get("Q_variant") != seed.get("Q_variant"):
        mk.append("Q_variant")
    if inputs.get("rho_l_at") != seed.get("rho_l_at"):
        mk.append("rho_l_at")
    return mk


def _isnum(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def input_problem(inp):
    """Return a message if the inputs are outside what the model accepts, else None."""
    if not isinstance(inp, dict):
        return "inputs is not an object"
    extra = set(inp) - INPUT_KEYS
    if extra:
        return "unknown input fields: " + ", ".join(sorted(extra))
    if inp.get("fuel") not in ("methanol", "heptane"):
        return "fuel must be methanol or heptane"
    X = inp.get("X")
    if not isinstance(X, dict) or set(X) - set(d2law.SPECIES):
        return "X must hold O2, N2, CO2, He"
    for k, v in X.items():
        if v is not None and not (_isnum(v) and 0 <= v <= 1):
            return f"mole fraction {k} outside 0–1"
    if sum((v or 0) for v in X.values()) <= 0:
        return "no ambient composition"
    if inp.get("D0_mm") is not None and not (_isnum(inp["D0_mm"]) and inp["D0_mm"] > 0):
        return "D0_mm must be positive"
    if not (_isnum(inp.get("T_inf_K")) and 200 <= inp["T_inf_K"] <= 600):
        return "T_inf_K must be 200–600 K"
    if "T_prop_K" in inp and inp["T_prop_K"] is not None and not (_isnum(inp["T_prop_K"]) and 300 <= inp["T_prop_K"] <= 2000):
        return "T_prop_K must be 300–2000 K"
    if inp.get("rho_l_at") not in ("boil", "298") or inp.get("Q_variant") not in ("nominal", "low", "high"):
        return "rho_l_at or Q_variant has an unknown value"
    if inp.get("P_atm") is not None and not (_isnum(inp["P_atm"]) and inp["P_atm"] >= 0):
        return "P_atm must be a non-negative number or null"
    if "T_prop_rule" in inp and not (isinstance(inp["T_prop_rule"], str) and len(inp["T_prop_rule"]) <= 40):
        return "T_prop_rule must be a short string"
    return None


def _solve(inputs, table):
    I = dict(inputs)
    I["X"] = {k: (inputs["X"].get(k) or 0.0) for k in d2law.SPECIES}
    return d2law.solve(I, table)


def _comparison(row, inputs, seed, outputs):
    raw = row.get("K_mm2_s_raw") or None
    printed = None if row.get("K_mm2_s") in ("", "None", None) else float(row["K_mm2_s"])
    applies = set(modified_keys(seed, inputs)) <= {"D0_mm"}
    ratio = r8(outputs["K_mm2_s"] / printed) if (applies and printed and outputs["K_mm2_s"]) else None
    return {"printed_K_as_printed": raw, "printed_basis": "Table IX, PUBLISHED TABULATED (comparison only, not validation)",
            "applies": applies, "model_over_printed": ratio}


def build_run(pkg, test_id, inputs=None, exported_by=None):
    from . import __version__
    exported_by = exported_by or "openflex CLI " + __version__
    row = next(r for r in pkg.table_ix() if r["flex_test"] == test_id)
    table, ver = pkg.model_properties(), pkg.code_verification()
    seed = seeded_inputs(row)
    inputs = json.loads(json.dumps(inputs if inputs is not None else seed))
    prob = input_problem(inputs)
    if prob:
        raise ValueError(prob)
    out = _solve(inputs, table)
    if out["K_mm2_s"] is None:
        raise ValueError("the model does not burn at these inputs (B <= 0)")
    psha = ver["property_table_sha256"]
    run = {
        "record_type": FORMAT, "format_version": FORMAT_VERSION,
        "labels": {"evidence_class": "NUMERICAL_SIMULATION", "status": "EDUCATIONAL_BASELINE", "scope": SCOPE},
        "run_id": "SIM-" + sha({"model": d2law.MODEL_VERSION, "inputs": inputs, "table": psha})[:12],
        "model": {"name": d2law.MODEL_NAME, "version": d2law.MODEL_VERSION, "property_table_sha256": psha,
                  "implementation_sha256": ver["implementation_sha256"]},
        "seeded_from_physical_test": test_id, "modified_inputs": modified_keys(seed, inputs), "inputs": inputs,
        "outputs": dict({k: r8(out[k]) for k in OUTPUT_KEYS}, flags=list(out["flags"])),
        "comparison": _comparison(row, inputs, seed, out), "exported_by": exported_by,
    }
    run["content_sha256"] = sha(run)
    return run


# --- checking -------------------------------------------------------------------------------------------------------
def _close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) <= REL_TOL * max(abs(b), 1e-30)


def verify_run(obj, pkg):
    """Re-run a run file with this package. Returns {"status", "checks": [{"id","name","pass","detail"}]}."""
    checks = []

    def add(cid, name, ok, detail=""):
        checks.append({"id": cid, "name": name, "pass": bool(ok), "detail": detail})
        return ok

    def done(status):
        return {"status": status, "checks": checks}

    if not isinstance(obj, dict) or obj.get("record_type") != FORMAT or obj.get("format_version") != FORMAT_VERSION:
        add("F1", "file format", False, f"not an {FORMAT} v{FORMAT_VERSION} file")
        return done("INVALID")
    extra = set(obj) - TOP_KEYS
    if not add("F1", "file format and fields", not extra and len(json.dumps(obj)) <= MAX_BYTES,
               "unknown or oversized fields: " + ", ".join(sorted(extra)) if extra else ""):
        return done("INVALID")
    lab = obj.get("labels") or {}
    if not add("F2", "labelled as a NUMERICAL_SIMULATION with a SIM- id (never a FLEX id)",
               lab.get("evidence_class") == "NUMERICAL_SIMULATION" and re.fullmatch(r"SIM-[0-9a-f]{12}", str(obj.get("run_id")))):
        return done("INVALID")
    table, ver = pkg.model_properties(), pkg.code_verification()
    rows = {r["flex_test"]: r for r in pkg.table_ix()}
    prob = input_problem(obj.get("inputs"))
    seed_id = obj.get("seeded_from_physical_test")
    if not add("F3", "inputs within the model's range; seeding test exists in Table IX", prob is None and seed_id in rows, prob or ("unknown test " + str(seed_id) if seed_id not in rows else "")):
        return done("INVALID")
    m = obj.get("model") or {}
    same = (m.get("name") == d2law.MODEL_NAME and m.get("version") == d2law.MODEL_VERSION
            and m.get("property_table_sha256") == ver["property_table_sha256"] and m.get("implementation_sha256") == ver["implementation_sha256"])
    add("F4", "same model version, property table and implementation as this package", same,
        "" if same else f"file: {m.get('name')} {m.get('version')}, table {str(m.get('property_table_sha256'))[:12]}…; this package: {d2law.MODEL_NAME} {d2law.MODEL_VERSION}, table {ver['property_table_sha256'][:12]}…")
    body = {k: v for k, v in obj.items() if k != "content_sha256"}
    ok_hash = obj.get("content_sha256") == sha(body)
    add("F9", "content hash (detects accidental changes only; anyone can recompute it after editing)", ok_hash)
    if not same:
        return done("CANNOT_CHECK")
    seed = seeded_inputs(rows[seed_id])
    add("F5", "list of modified inputs matches the inputs", sorted(obj.get("modified_inputs", [])) == sorted(modified_keys(seed, obj["inputs"])))
    rid = "SIM-" + sha({"model": d2law.MODEL_VERSION, "inputs": obj["inputs"], "table": ver["property_table_sha256"]})[:12]
    add("F6", "run id equals the hash of model version, inputs and property table", rid == obj["run_id"], "" if rid == obj["run_id"] else "recomputed " + rid)
    out = _solve(obj["inputs"], table)
    fo = obj.get("outputs") or {}
    bad = [k for k in OUTPUT_KEYS if not _close(fo.get(k), out[k])]
    if fo.get("flags") != out["flags"]:
        bad.append("flags")
    add("F7", "outputs equal a fresh run (relative tolerance 1e-6)", not bad, ", ".join(bad))
    cmp_ = _comparison(rows[seed_id], obj["inputs"], seed, out)
    fc = obj.get("comparison") or {}
    add("F8", "printed-value comparison equals this package's Table IX", fc.get("printed_K_as_printed") == cmp_["printed_K_as_printed"]
        and fc.get("applies") == cmp_["applies"] and _close(fc.get("model_over_printed"), cmp_["model_over_printed"]))
    return done("REPRODUCED" if all(c["pass"] for c in checks) else "NOT_REPRODUCED")


def explain(status):
    return {"REPRODUCED": "The documented model gives these numbers from these inputs. This does not show that the model agrees with FLEX.",
            "NOT_REPRODUCED": "The file's model matches this one, but at least one result, id, list or hash differs; the file was edited or made by faulty software.",
            "CANNOT_CHECK": "The file was made with a different model version or property table; results may legitimately differ. Use the matching version to check it.",
            "INVALID": "Not a usable run file."}[status]
