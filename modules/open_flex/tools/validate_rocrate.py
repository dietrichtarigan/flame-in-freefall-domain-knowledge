#!/usr/bin/env python3
"""Validate ro-crate-metadata.json with rocrate-validator (profile ro-crate-1.2), working offline.

The validator downloads the RO-Crate 1.2 JSON-LD context from https://w3id.org/ro/crate/1.2/context. When that
host is unreachable (as in the build environment), this wrapper serves that one URL from a pinned copy of the
official file: vendor/test-only/ro-crate-1.2/context.jsonld (from the RO-Crate specification repository, CC0;
SHA-256 checked against vendor/VENDOR.json). Nothing else is changed: the validator's checks, profiles and
severity rules run as shipped. Any other URL still goes to the network.

Exit status is the validator's (0 = valid at the requested severity).
Usage: python3 tools/validate_rocrate.py [repo-root] [--severity required|recommended|optional] [--json OUT]
"""
import hashlib
import io
import json
import os
import sys
import urllib.request

CONTEXT_URL = "https://w3id.org/ro/crate/1.2/context"


def main(argv):
    root = os.path.abspath(argv[0]) if argv and not argv[0].startswith("--") else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sev = argv[argv.index("--severity") + 1] if "--severity" in argv else "required"
    out_json = argv[argv.index("--json") + 1] if "--json" in argv else None
    vend = json.load(open(os.path.join(root, "vendor/VENDOR.json"), encoding="utf-8"))
    entry = next(f for f in vend["test_only_files"] if f["path"].endswith("ro-crate-1.2/context.jsonld"))
    body = open(os.path.join(root, "vendor", entry["path"]), "rb").read()
    if hashlib.sha256(body).hexdigest() != entry["sha256"]:
        sys.exit("pinned RO-Crate context differs from vendor/VENDOR.json")

    def is_ctx(url):
        return url.rstrip("/").split("#")[0] in (CONTEXT_URL, "http://w3id.org/ro/crate/1.2/context")

    import requests
    import requests.adapters
    orig_send = requests.adapters.HTTPAdapter.send

    def send(self, request, *a, **k):
        if is_ctx(request.url):
            r = requests.Response()
            r.status_code, r._content, r.url, r.request = 200, body, request.url, request
            r.headers["Content-Type"] = "application/ld+json"
            return r
        return orig_send(self, request, *a, **k)
    requests.adapters.HTTPAdapter.send = send

    import rdflib._networking as net
    import rdflib.parser as rp
    orig_open = net._urlopen

    def _urlopen(req):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        if is_ctx(url):
            resp = urllib.response.addinfourl(io.BytesIO(body), {"Content-Type": "application/ld+json"}, url, 200)
            return resp
        return orig_open(req)
    net._urlopen = rp._urlopen = _urlopen

    from rocrate_validator.cli.main import cli
    args = ["validate", "-p", "ro-crate-1.2", "-l", sev, "--no-cache", "--no-paging", "--skip-availability-check", "-w", "160"]
    if out_json:
        args += ["-f", "json", "-o", out_json]
    args.append(root)
    try:
        cli.main(args=args, prog_name="rocrate-validator", standalone_mode=False)
        return 0
    except SystemExit as e:
        return int(e.code or 0)


if __name__ == "__main__":
    import urllib.response  # noqa: F401  (used inside the patched opener)
    sys.exit(main(sys.argv[1:]))
