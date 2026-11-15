"""Read-only access to the Open FLEX data package, with SHA-256 checks against data/MANIFEST.json.

Every loader returns values exactly as stored; nothing is interpolated, filled or smoothed. Physical tests
(FLEX-nnn), digitized series, analysis runs and simulation runs stay separate objects.
"""
import csv
import hashlib
import json
import os

DEFAULT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DataPackage:
    def __init__(self, root=DEFAULT_ROOT, verify=True):
        self.root = root
        self.manifest = self._json("data/MANIFEST.json")
        self.datasets = {d["dataset_id"]: d for d in self.manifest["datasets"]}
        if verify:
            self.verify()

    def _path(self, rel):
        return os.path.join(self.root, rel)

    def _json(self, rel):
        with open(self._path(rel), encoding="utf-8") as fh:
            return json.load(fh)

    def verify(self):
        """Raise if any dataset file is missing or differs from its manifest hash."""
        bad = []
        for d in self.datasets.values():
            p = self._path(d["path"])
            if not os.path.exists(p) or hashlib.sha256(open(p, "rb").read()).hexdigest() != d["sha256"]:
                bad.append(d["path"])
        if bad:
            raise ValueError("dataset files differ from data/MANIFEST.json: " + ", ".join(bad))

    def table_ix(self):
        """Table IX rows as printed (strings); *_raw columns keep the printed text."""
        with open(self._path("data/extracted/table_ix.csv"), encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def physical_test(self, test_id):
        recs = self._json("data/records/physical_tests.json")["records"]
        for r in recs:
            if r["test_id"] == test_id:
                return r
        raise KeyError(test_id)

    def digitized_series(self, test_id):
        """{series name: {'dataset_id', 'unit', 't', 'v'}} for a test; empty if none was digitized."""
        out = {}
        for d in self.datasets.values():
            if d.get("data_class") == "DIGITIZED" and d.get("test_id") == test_id and d.get("series"):
                with open(self._path(d["path"]), encoding="utf-8") as fh:
                    rows = list(csv.reader(fh))[1:]
                out[d["series"]] = {"dataset_id": d["dataset_id"], "unit": d.get("unit"),
                                    "t": [float(r[0]) for r in rows], "v": [float(r[1]) for r in rows]}
        return out

    def model_properties(self):
        return self._json("data/model/d2law_properties.json")

    def simulation_runs(self):
        return self._json("data/simulations/d2law_baseline_runs.json")["runs"]

    def code_verification(self):
        return self._json("data/verification/d2law_code_verification.json")
