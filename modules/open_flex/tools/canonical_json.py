#!/usr/bin/env python3
"""Canonical JSON and SHA-256, matching OF.canonicalJSON in app/src/js/10_util.js.

Rule: objects have keys sorted (by UTF-16 code unit order, as JavaScript's default
sort does; identical to Python's order for the ASCII keys used here); no whitespace;
strings escaped as JSON.stringify does for the characters used in the data;
numbers formatted as JavaScript would format them.

Usage: python3 -I tools/canonical_json.py manifest.json   -> recomputes record_sha256
"""
import hashlib
import json
import math
import sys


def _num(x):
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, int):
        return str(x)
    if math.isfinite(x) and x == int(x) and abs(x) < 1e21:
        return str(int(x))
    return repr(x)  # shortest round-trip repr, same digits as JS for values used here


def canonical(v):
    if v is None:
        return "null"
    if isinstance(v, bool) or isinstance(v, (int, float)):
        return _num(v)
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return "[" + ",".join(canonical(x) for x in v) + "]"
    if isinstance(v, dict):
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + canonical(v[k]) for k in sorted(v)) + "}"
    raise TypeError(type(v))


def sha256_of(v):
    return hashlib.sha256(canonical(v).encode("utf-8")).hexdigest()


if __name__ == "__main__":
    m = json.load(open(sys.argv[1], encoding="utf-8"))
    got = sha256_of(m["record"])
    print("recomputed:", got)
    print("in file:   ", m.get("record_sha256"))
    print("MATCH" if got == m.get("record_sha256") else "MISMATCH")
    sys.exit(0 if got == m.get("record_sha256") else 1)
