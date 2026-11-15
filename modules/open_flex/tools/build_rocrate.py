#!/usr/bin/env python3
"""Write ro-crate-metadata.json (RO-Crate 1.2) at the repository root, from data/MANIFEST.json and the registries.

What the crate describes
  * every dataset in data/MANIFEST.json (File entities with SHA-256, size, format, evidence class as a keyword),
  * the schemas, the tools and the openflex package (SoftwareSourceCode), the built app, the docs and tests,
  * one CreateAction per derived dataset: which tool made it from which inputs,
  * the NASA report as a contextual (web) entity, with its SHA-256; the PDF itself is not packaged,
  * the cited sources (S01–S47) as contextual entities.

Not claimed: a licence for this repository (none has been chosen; the crate says so), NASA endorsement,
validation of any model. Deterministic output (no timestamps; datePublished is the release date below).

Validate: rocrate-validator validate -p ro-crate-1.2 .
Usage: python3 -I tools/build_rocrate.py [repo-root]
"""
import glob
import hashlib
import json
import os
import sys

RELEASE_DATE = "2026-11-15"
VERSION = "0.6.1"
FORMATS = {".csv": "text/csv", ".json": "application/json", ".py": "text/x-python", ".js": "text/javascript", ".html": "text/html",
           ".md": "text/markdown", ".png": "image/png", ".sh": "application/x-sh", ".css": "text/css", ".toml": "application/toml",
           ".txt": "text/plain", ".sha256": "text/plain"}


LANG = {".py": ("#python", "Python", "https://www.python.org/", "3.13 (tested; >=3.10 required)"),
        ".js": ("#javascript", "JavaScript", "https://tc39.es/ecma262/", "ECMAScript 2017+ (browser)"),
        ".sh": ("#bash", "Bash", "https://www.gnu.org/software/bash/", "5"),
        ".html": ("#html", "HTML", "https://html.spec.whatwg.org/", "HTML Living Standard"),
        ".css": ("#css", "CSS", "https://www.w3.org/Style/CSS/", "CSS3")}


def describe(root, rel):
    """One-line description taken from the file itself (docstring, header comment, schema title, first heading)."""
    path = os.path.join(root, rel)
    ext = os.path.splitext(rel)[1]
    try:
        txt = open(path, encoding="utf-8").read(4000)
    except UnicodeDecodeError:
        return None
    if ext == ".py":
        import ast
        try:
            doc = ast.get_docstring(ast.parse(open(path, encoding="utf-8").read()))
        except SyntaxError:
            doc = None
        return doc.strip().splitlines()[0] if doc else None
    if ext == ".json" and rel.startswith("schemas/"):
        sc = json.loads(open(path, encoding="utf-8").read())
        return "JSON Schema: " + sc.get("title", rel) + (". " + sc["description"] if sc.get("description") else "")
    if ext == ".md":
        for line in txt.splitlines():
            if line.startswith("#"):
                return line.lstrip("# ").strip()
    if ext in (".js", ".sh", ".css"):
        for line in txt.splitlines():
            t = line.strip().lstrip("/#*! ").strip()
            if t and not set(t) <= set("-=") and not t.startswith("usr/bin") and "set -" not in t:
                return t
    return None


def main(root):
    def sha(rel):
        return hashlib.sha256(open(os.path.join(root, rel), "rb").read()).hexdigest()

    def file_entity(rel, name, desc=None, extra=None):
        e = {"@id": rel, "@type": "File", "name": name, "contentSize": str(os.path.getsize(os.path.join(root, rel))),
             "encodingFormat": FORMATS.get(os.path.splitext(rel)[1], "application/octet-stream"), "sha256": sha(rel)}
        desc = desc or describe(root, rel)
        if desc:
            e["description"] = desc
        if extra:
            e.update(extra)
        return e

    man = json.load(open(os.path.join(root, "data/MANIFEST.json"), encoding="utf-8"))
    sources = json.load(open(os.path.join(root, "data/registry/sources.json"), encoding="utf-8"))["sources"]
    graph, parts, actions = [], [], []

    def add(e):
        graph.append(e)
        parts.append({"@id": e["@id"]})

    # data
    for d in man["datasets"]:
        if d["path"].startswith("sources/"):
            continue                                  # the source PDF is not packaged; see the NASA web entity
        add(file_entity(d["path"], d["dataset_id"] + " v" + d["version"],
                        f"{d['data_class']} dataset. Origin: {d['origin']}. Method: {d['method']}." + (f" Limitations: {d['limitations']}" if d.get("limitations") else ""),
                        {"keywords": ", ".join([d["data_class"]] + ([d["test_id"]] if d.get("test_id") else [])), "version": d["version"], "identifier": d["dataset_id"]}))
    data_ids = {e["@id"] for e in graph}
    # the manifest itself, schemas, code, app, docs, tests
    extra = ["data/MANIFEST.json", "data/datasets.spec.json", "README.md", "requirements.txt", "pyproject.toml", "setup_and_test.sh",
             "SOURCE_CHECKSUMS.sha256", "dist/open_flex_lab.html", "vendor/VENDOR.json"]
    extra += sorted(glob.glob("schemas/*.json", root_dir=root)) + sorted(glob.glob("docs/*.md", root_dir=root))
    for rel in extra:
        if rel in data_ids or not os.path.exists(os.path.join(root, rel)):
            continue
        desc = {"dist/open_flex_lab.html": "Built single-file offline application (tools/build_app.py).",
                "data/MANIFEST.json": "Dataset manifest: version, class, origin, method, SHA-256 of every data file.",
                "data/datasets.spec.json": "Hand-maintained dataset specification from which tools/build_app.py writes data/MANIFEST.json.",
                "requirements.txt": "Pinned Python packages used by the tools and tests.",
                "pyproject.toml": "Python packaging metadata for the openflex package.",
                "vendor/VENDOR.json": "Pinned third-party files (library, test-only and validation files) with versions, sources and SHA-256.",
                "SOURCE_CHECKSUMS.sha256": "SHA-256 of the NASA source PDF expected in sources/original/."}.get(rel)
        add(file_entity(rel, os.path.basename(rel), desc))
    descs_code = {"app/src/body.html": "Application page markup (five workspaces), inlined by tools/build_app.py."}
    code = sorted(glob.glob("tools/*.py", root_dir=root) + glob.glob("tools/*.sh", root_dir=root) + glob.glob("openflex/*.py", root_dir=root)
                  + glob.glob("app/src/js/*.js", root_dir=root) + ["app/src/body.html", "app/src/styles.css"])
    for rel in code:
        if os.path.basename(rel) == "__init__.py" and rel.startswith("tools/"):
            continue
        add(file_entity(rel, rel, descs_code.get(rel), {"@type": ["File", "SoftwareSourceCode"], "programmingLanguage": {"@id": LANG[os.path.splitext(rel)[1]][0]}}))
    for rel in sorted(glob.glob("tests/**/*.py", root_dir=root, recursive=True)):
        add(file_entity(rel, rel, None, {"@type": ["File", "SoftwareSourceCode"], "programmingLanguage": {"@id": "#python"}}))
    code_ids = {e["@id"] for e in graph if "SoftwareSourceCode" in e["@type"]}

    # provenance: one CreateAction per dataset made by a tool in this repository
    for d in man["datasets"]:
        tool = d["method"].split()[0].rstrip(",;:")
        if d["path"] not in data_ids or tool not in code_ids:
            continue
        objs = [{"@id": i} for i in d.get("inputs", []) if i in data_ids or i in code_ids]
        if any(i.startswith("sources/") for i in d.get("inputs", [])):
            objs.append({"@id": "https://ntrs.nasa.gov/citations/20150023456"})
        a = {"@id": "#create-" + d["dataset_id"], "@type": "CreateAction", "name": "Create " + d["dataset_id"],
             "instrument": {"@id": tool}, "result": {"@id": d["path"]}, "description": d["method"]}
        if objs:
            a["object"] = objs[0] if len(objs) == 1 else objs
        actions.append(a)

    s01 = next(s for s in sources if s["source_id"] == "S01")
    ctx = [
        {"@id": "https://ntrs.nasa.gov/citations/20150023456", "@type": "CreativeWork", "name": "NASA/TP-2015-216046 (source S01)",
         "description": s01["citation"] + " The PDF is not packaged in this crate; place it at sources/original/NASA-TP-2015-216046.pdf to rebuild. Rights as shown on NTRS: Public Use Permitted.",
         "sha256": s01["sha256"]},
        {"@id": "#licence-not-chosen", "@type": "CreativeWork", "name": "No licence chosen yet",
         "description": "The owner of this repository has not yet chosen a licence. Until one is chosen, no reuse licence is granted by this crate. Third-party content keeps its own terms (NASA report: NTRS public use; vendored libraries: see vendor/VENDOR.json)."},
        {"@id": "#claude", "@type": "SoftwareApplication", "name": "Claude (Anthropic AI assistant)", "url": "https://claude.ai",
         "version": "Claude Opus 5.5", "description": "Prepared the code, data processing and documentation under the repository owner's direction."},
    ]
    for lid, name, url, ver in LANG.values():
        ctx.append({"@id": lid, "@type": "ComputerLanguage", "name": name, "url": url, "version": ver})
    for s in sources:
        if s["source_id"] == "S01":
            continue
        ctx.append({"@id": s["url"], "@type": "CreativeWork", "name": s["source_id"] + " (Open FLEX source register)", "description": s["citation"]})

    rootent = {
        "@id": "./", "@type": "Dataset", "name": "Open FLEX virtual laboratory — evidence-traceable data package (Phase B M6)",
        "description": ("Independent, evidence-traceable reconstruction of the original NASA Flame Extinguishment Experiment (FLEX, ISS 2009–2011) "
                        "from NASA/TP-2015-216046: Table IX and test-matrix extractions with cell-level checks, digitized Appendix B plots, "
                        "registries of claims, sources and discrepancies, a single-file offline lab application, and a code-verified D²-law "
                        "educational baseline (not validated against FLEX). Not a NASA product; citing NASA does not imply endorsement."),
        "datePublished": RELEASE_DATE, "version": VERSION, "license": {"@id": "#licence-not-chosen"},
        "creditText": "Open FLEX virtual laboratory, Phase B (2026), data from NASA/TP-2015-216046.",
        "isBasedOn": {"@id": "https://ntrs.nasa.gov/citations/20150023456"},
        "keywords": ["FLEX", "droplet combustion", "microgravity", "International Space Station", "provenance"],
        "contributor": {"@id": "#claude"},
        "hasPart": parts, "mentions": [{"@id": a["@id"]} for a in actions],
        "citation": [{"@id": "https://ntrs.nasa.gov/citations/20150023456"}] + [{"@id": s["url"]} for s in sources if s["source_id"] != "S01"],
    }
    meta = {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"}, "about": {"@id": "./"}}
    crate = {"@context": "https://w3id.org/ro/crate/1.2/context", "@graph": [meta, rootent] + graph + actions + ctx}
    with open(os.path.join(root, "ro-crate-metadata.json"), "w", encoding="utf-8") as fh:
        json.dump(crate, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(f"ro-crate-metadata.json: {len(parts)} data entities, {len(actions)} CreateActions, {len(ctx)} contextual entities")


if __name__ == "__main__":
    main(os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
