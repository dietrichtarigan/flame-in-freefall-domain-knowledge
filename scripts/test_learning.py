#!/usr/bin/env python3
"""Uji ujung-ke-ujung tahap D (siklus belajar) TANPA mencemari log anotasi asli.

Semua putusan uji coba ditulis ke log sementara (FREEFALL_ANN), lalu otak dibangun ulang dari
log asli di akhir. Jalankan:  python scripts/test_learning.py
"""
import csv
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
tmp = Path(tempfile.mkdtemp(prefix="freefall_learn_"))
ENV = {**os.environ, "PYTHONUTF8": "1", "FREEFALL_ANN": str(tmp / "ann.jsonl"),
       "FREEFALL_HISTORY": str(tmp / "hist.jsonl"), "FREEFALL_STATE": str(tmp / "state.json")}


def sh(*args, env=ENV):
    r = subprocess.run([PY, *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
    if r.returncode:
        print(r.stdout, r.stderr)
        raise SystemExit(f"gagal: {args}")
    return r.stdout


def snap():
    c = sqlite3.connect(f"file:{ROOT / 'kb/gold/brain.sqlite'}?mode=ro", uri=True)
    q = lambda s, *a: c.execute(s, a).fetchall()
    sys.path.insert(0, str(ROOT / "scripts"))
    import brain
    brain.close_all()
    out = {"tiers": dict(q("SELECT tier, count(*) FROM measurement GROUP BY 1")),
           "alerts": brain.alerts()["counts"],
           "g8": q("SELECT tier, value_text, flags FROM measurement WHERE entity='test:PSI-159:21106G8' AND quantity='ignited'"),
           "card": json.loads((ROOT / "analysis/ml/telemetry_gb_card.json").read_text(encoding="utf-8"))}
    c.close()
    brain.close_all()                       # lepaskan berkas supaya pipeline bisa menukar otak
    return out


ok = True


def check(cond, msg):
    global ok
    print(("  LULUS  " if cond else "  GAGAL  ") + msg)
    ok &= bool(cond)


print("1. keadaan awal (log anotasi kosong, sementara)")
sh("scripts/learn.py", "run")
a0 = snap()
print("   ", a0["alerts"], "human_verified:", a0["tiers"].get("human_verified", 0))

vids = []
for r in csv.DictReader(open(ROOT / "analysis/video_full/measurements.csv", encoding="utf-8")):
    if r["source_video"] not in vids:
        vids.append(r["source_video"])
n_ep_ok = sum(1 for r in csv.DictReader(open(ROOT / "analysis/video_full/measurements.csv", encoding="utf-8"))
              if r["source_video"] == vids[0])

print("2. empat putusan manusia (uji coba)")
for args in (["--entity", "PSI-159:21106G8", "--quantity", "ignited", "--verdict", "salah", "--value_text", "tidak",
              "--note", "UJI: panas sisa pemantik G7, O2 tidak terpakai"],
             ["--entity", "PSI-159:21106F2", "--quantity", "ignited", "--verdict", "ok", "--value_text", "tidak",
              "--note", "UJI: setuju dengan tabel NASA"],
             ["--artifact", f"art:video:{vids[0]}", "--verdict", "ok", "--note", "UJI: kotak melingkupi nyala"],
             ["--artifact", f"art:video:{vids[1]}", "--verdict", "salah", "--note", "UJI: pantulan, bukan api"]):
    sh("scripts/learn.py", "annotate", *args, "--author", "uji-otomatis")
print("   status:", " ".join(l.split()[0] + ("*" if "BASI" in l else "") for l in sh("scripts/learn.py", "status").splitlines()))

print("3. siklus belajar berjalan")
print("   " + sh("scripts/learn.py", "run").strip().replace("\n", "\n   "))
a1 = snap()
print("   ", a1["alerts"], "human_verified:", a1["tiers"].get("human_verified", 0))

check(a1["alerts"]["kritis"] == a0["alerts"]["kritis"] - 1, f"kontradiksi 21106F2 selesai: kritis {a0['alerts']['kritis']} -> {a1['alerts']['kritis']}")
check(a1["alerts"]["perhatian"] < a0["alerts"]["perhatian"], f"peringatan G8 hilang: perhatian {a0['alerts']['perhatian']} -> {a1['alerts']['perhatian']}")
check(a1["tiers"].get("human_verified", 0) == a0["tiers"].get("human_verified", 0) + n_ep_ok + 2,
      f"tier naik: human_verified {a0['tiers'].get('human_verified', 0)} -> {a1['tiers'].get('human_verified', 0)} "
      f"(= {n_ep_ok} episode video + 2 putusan menyala)")
check(any(t == "human_verified" and v == "tidak" for t, v, _ in a1["g8"]), "G8 punya putusan manusia 'tidak'")
check(any("ditolak_manusia" in f for t, v, f in a1["g8"] if t == "derived_auto"), "angka turunan G8 ditandai ditolak_manusia")
check(a1["card"]["n_label_manusia"] == 2, f"model dilatih ulang dengan {a1['card']['n_label_manusia']} label manusia")
ver = ROOT / "analysis/video_full/measurements_verified.csv"
check(ver.exists() and sum(1 for _ in open(ver, encoding="utf-8")) - 1 == n_ep_ok, f"measurements_verified.csv berisi {n_ep_ok} episode video OK")
q = json.loads(subprocess.run([PY, "-c", "import sys,json;sys.path.insert(0,'scripts');import learn;print(json.dumps(learn.queue(500)))"],
                              cwd=ROOT, env=ENV, capture_output=True, text=True, encoding="utf-8").stdout)
ids = {it.get("entity") or it.get("artifact") for it in q["items"]}
check("test:PSI-159:21106G8" not in ids and "test:PSI-159:21106F2" not in ids and f"art:video:{vids[0]}" not in ids,
      "item yang sudah diputuskan keluar dari antrean verifikasi")
hist = [json.loads(l) for l in (tmp / "hist.jsonl").read_text(encoding="utf-8").splitlines()]
check(len(hist) == 2 and hist[-1]["n_annotations"] == 4, f"riwayat model mencatat {len(hist)} snapshot, {hist[-1]['n_annotations']} anotasi")
print("   prediksi GB yang berubah sisi:", hist[-1]["flipped_predictions"][:5])

print("4. bersih-bersih: bangun ulang dari log ASLI")
env_real = {k: v for k, v in os.environ.items() if not k.startswith("FREEFALL_")} | {"PYTHONUTF8": "1"}
sh("scripts/learn.py", "run", env=env_real)
a2 = snap()
check(a2["alerts"] == a0["alerts"] and a2["tiers"].get("human_verified", 0) == 0 and not ver.exists(),
      "otak kembali ke keadaan asli (tidak ada jejak uji coba)")
print("\nHASIL:", "SEMUA LULUS" if ok else "ADA YANG GAGAL")
sys.exit(0 if ok else 1)
