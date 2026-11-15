"""Command line: python3 -m openflex <command>

  info                         data package summary (and hash check)
  test FLEX-035                printed Table IX row + digitized series available for a test
  baseline FLEX-035 [--O2 x]   D²-law educational baseline at that test's printed conditions; any option
                               that changes an input makes the output a modified simulation, reported as such
                               (--export run.json writes a shareable run file)
  check-run run.json           re-run a shared run file and report REPRODUCED / NOT_REPRODUCED / CANNOT_CHECK / INVALID
"""
import argparse
import json
import sys

from . import __version__
from . import d2law, share
from .data import DataPackage


def main(argv=None):
    ap = argparse.ArgumentParser(prog="openflex", description="Open FLEX data package and educational baseline")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("info")
    t = sub.add_parser("test")
    t.add_argument("test_id")
    b = sub.add_parser("baseline")
    b.add_argument("test_id")
    b.add_argument("--O2", type=float, help="replace the printed oxygen mole fraction (balance N2 adjusted)")
    b.add_argument("--D0", type=float, help="replace the printed initial diameter (mm)")
    b.add_argument("--T-prop", type=float, dest="T_prop", help="fixed property temperature (K) instead of the iterated rule")
    b.add_argument("--export", metavar="FILE", help="write a shareable run file (no personal data) and print its run id")
    c = sub.add_parser("check-run")
    c.add_argument("file")
    a = ap.parse_args(argv)
    pkg = DataPackage()

    if a.cmd == "info":
        v = pkg.code_verification()
        print(f"openflex {__version__}; {len(pkg.datasets)} datasets, all SHA-256 hashes match the manifest")
        print(f"D²-law baseline {v['model']['version']}: code verification {v['status']} ({v['n_passed']}/{v['n_checks']}); not validated")
        return 0

    if a.cmd == "check-run":
        raw = open(a.file, "rb").read()
        if len(raw) > share.MAX_BYTES:
            print("INVALID: file larger than", share.MAX_BYTES, "bytes")
            return 1
        try:
            res = share.verify_run(json.loads(raw.decode("utf-8")), pkg)
        except (ValueError, UnicodeDecodeError) as e:
            print("INVALID: not JSON:", e)
            return 1
        for ck in res["checks"]:
            print(("  ok   " if ck["pass"] else "  FAIL ") + ck["id"] + " " + ck["name"] + (" — " + ck["detail"] if ck["detail"] else ""))
        print(res["status"] + ": " + share.explain(res["status"]))
        return 0 if res["status"] == "REPRODUCED" else 1
    row = next((r for r in pkg.table_ix() if r["flex_test"] == a.test_id), None)
    if row is None:
        print(f"{a.test_id}: not in Table IX", file=sys.stderr)
        return 2
    if a.cmd == "test":
        print(json.dumps({k: row[k] for k in row if k.endswith("_raw") or k in ("flex_test", "fuel", "test_end")}, indent=1))
        s = pkg.digitized_series(a.test_id)
        print("digitized series:", ", ".join(f"{k} ({len(v['t'])} points, {v['dataset_id']})" for k, v in s.items()) or "none")
        return 0

    inputs = share.seeded_inputs(row)               # the exact inputs the stored simulation runs use
    modified = []
    if a.O2 is not None:
        X = inputs["X"]
        X["N2"] = round((X["N2"] or 0) + (X["O2"] or 0) - a.O2, 6)
        X["O2"] = a.O2
        modified.append(f"X_O2 {row['X_O2_raw']} -> {a.O2} (N2 balance)")
    if a.D0 is not None:
        inputs["D0_mm"] = a.D0
        modified.append(f"D0 {row['D0_mm_raw']} -> {a.D0} mm")
    if a.T_prop is not None:
        inputs["T_prop_K"], inputs["T_prop_rule"] = a.T_prop, "fixed"
        modified.append(f"property temperature fixed at {a.T_prop} K")
    out = share._solve(inputs, pkg.model_properties())
    print(f"SIMULATION (D²-law educational baseline {d2law.MODEL_VERSION}) seeded from the printed conditions of {a.test_id}")
    if modified:
        print("MODIFIED inputs — not the conditions of " + a.test_id + ": " + "; ".join(modified))
    for k in ("B", "K_mm2_s", "t_burn_s", "flame_standoff_ratio", "T_flame_K", "T_prop_K"):
        v = out.get(k)
        print(f"  {k:22s} {v:.4g}" if isinstance(v, float) else f"  {k:22s} {v}")
    print(f"  printed K (Table IX)   {row['K_mm2_s_raw']} mm²/s  [PUBLISHED TABULATED; comparison only, not validation]")
    for f in out["flags"]:
        print("  flag:", f)
    if a.export:
        run = share.build_run(pkg, a.test_id, inputs)
        with open(a.export, "w", encoding="utf-8") as fh:
            json.dump(run, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
        print(f"wrote {a.export}: run id {run['run_id']} (no personal data; check with: python3 -m openflex check-run {a.export})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
