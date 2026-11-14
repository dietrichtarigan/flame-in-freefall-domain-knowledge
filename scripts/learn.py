#!/usr/bin/env python3
"""Tahap D — lapis BELAJAR (docs/rencana_dashboard_cerdas.md, L3).

Tiga mekanisme:

1. LOG ANOTASI (event sourcing). Putusan manusia ditulis ke kb/gold/annotations.jsonl dan tidak
   pernah diubah/dihapus. Otak (brain.sqlite) SELALU dibangun ulang dari data mentah + log ini,
   jadi setiap keputusan bisa ditelusuri dan diputar ulang. Putusan:
     ok     -> angka naik ke tier human_verified
     salah  -> angka diberi tanda 'ditolak_manusia' (keluar dari agregat & peringatan)
     ragu   -> tanda 'diragukan_manusia'
   Untuk besaran 'ignited' manusia boleh memberi nilainya sendiri (value_text ya/tidak).

2. PIPELINE BERGAYA MAKE. Tiap langkah punya masukan & keluaran; langkah dijalankan ulang hanya
   bila sidik jari masukannya berubah (kb/gold/pipeline_state.json).
     proof_apply  anotasi video          -> analysis/video_full/measurements_verified.csv
     ml_labels    tensor + label NASA + label manusia -> model GB menyala dari telemetri (latih ulang)
     stats_uq     ...                    -> analysis/stats/uq.json
     corridor / boundary / symreg / quantile (hanya mode --full; lambat)
     build_brain  semua + anotasi        -> kb/gold/brain.sqlite
     history      kartu model + jumlah tier + peringatan -> kb/gold/model_history.jsonl

3. ANTREAN VERIFIKASI (active learning untuk MANUSIA). Item diurutkan menurut
   nilai = ketidakpastian x dampak, supaya waktu manusia dipakai di tempat yang paling mengubah
   angka di dashboard.

CLI:
  python scripts/learn.py annotate --entity PSI-159:21106G8 --quantity ignited --verdict salah --note "..."
  python scripts/learn.py import-review analysis/video_full/review.csv
  python scripts/learn.py status            # langkah mana yang basi
  python scripts/learn.py run [--full]      # jalankan langkah basi
  python scripts/learn.py queue [-k 20]     # antrean verifikasi
"""
import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "kb" / "gold"
import os as _os
# Bisa dialihkan (uji coba tanpa mencemari log asli): FREEFALL_ANN, FREEFALL_HISTORY, FREEFALL_STATE
ANN = Path(_os.environ.get("FREEFALL_ANN", GOLD / "annotations.jsonl"))
STATE = Path(_os.environ.get("FREEFALL_STATE", GOLD / "pipeline_state.json"))
HISTORY = Path(_os.environ.get("FREEFALL_HISTORY", GOLD / "model_history.jsonl"))
BRAIN = GOLD / "brain.sqlite"
PY = sys.executable
VERDICTS = ("ok", "salah", "ragu")


def now():
    return datetime.now(timezone.utc).isoformat()


def canon(x):
    x = (x or "").strip()
    if not x or x.startswith(("test:", "art:", "m:")):
        return x
    acc, _, t = x.partition(":")
    t = re.sub(r"\s+", "", t)      # di luar f-string: backslash di dalam f-string baru sah sejak Python 3.12
    return f"test:{acc.upper()}:{t.upper()}"


# ================================================================ 1. log anotasi
def annotations():
    if not ANN.exists():
        return []
    return [json.loads(l) for l in ANN.read_text(encoding="utf-8").splitlines() if l.strip()]


def annotate(entity=None, quantity=None, measurement=None, artifact=None, verdict="ok", value_text=None,
             note="", author="anonim", source="ui"):
    """Validasi lalu tambahkan satu putusan ke log. Mengembalikan rekaman yang ditulis."""
    if verdict not in VERDICTS:
        raise ValueError(f"putusan harus salah satu dari {VERDICTS}")
    if not (measurement or artifact or (entity and quantity)):
        raise ValueError("butuh measurement, artifact, atau entity+quantity")
    rec = {"t": now(), "verdict": verdict, "note": str(note)[:2000], "author": str(author)[:60], "source": source}
    if measurement:
        rec["measurement"] = measurement
    if artifact:
        rec["artifact"] = artifact
    if entity:
        rec["entity"] = canon(entity)
    if quantity:
        rec["quantity"] = quantity
    if value_text is not None:
        if quantity != "ignited" or value_text not in ("ya", "tidak"):
            raise ValueError("value_text hanya untuk quantity=ignited dengan nilai ya/tidak")
        rec["value_text"] = value_text
    if BRAIN.exists():                                   # pastikan sasarannya ada
        c = sqlite3.connect(f"file:{BRAIN}?mode=ro", uri=True)
        if measurement and not c.execute("SELECT 1 FROM measurement WHERE id=?", (measurement,)).fetchone():
            raise ValueError(f"measurement {measurement} tidak ada")
        if artifact and not c.execute("SELECT 1 FROM artifact WHERE id=?", (artifact,)).fetchone():
            raise ValueError(f"artefak {artifact} tidak ada")
        if entity and not c.execute("SELECT 1 FROM entity WHERE id=?", (rec["entity"],)).fetchone():
            c.close()
            raise ValueError(f"entitas {rec['entity']} tidak ada")
        c.close()
    rec["id"] = hashlib.sha1(json.dumps(rec, sort_keys=True).encode()).hexdigest()[:12]
    with open(ANN, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def import_review(path, author="lembar-bukti"):
    """review.csv dari scripts/proof_review.py (file,test_id,verdict ok|bad|maybe,note) -> anotasi artefak video."""
    m = {"ok": "ok", "bad": "salah", "maybe": "ragu"}
    seen = {(a.get("artifact"), a["verdict"]) for a in annotations() if a.get("source") == "proof_review"}
    n = 0
    for r in csv.DictReader(open(path, encoding="utf-8")):
        v = m.get((r.get("verdict") or "").strip())
        if not v:
            continue
        art = f"art:video:{r['file']}"
        if (art, v) in seen:
            continue
        annotate(artifact=art, quantity="visible_flame_duration", verdict=v, note=r.get("note", ""),
                 author=author, source="proof_review")
        n += 1
    return n


def apply_annotations(c):
    """Dipanggil build_brain.py SETELAH semua data masuk, SEBELUM aturan jalan.
    Putusan terakhir menang untuk sasaran yang sama."""
    latest = {}
    for a in annotations():
        key = (a.get("measurement"), a.get("artifact"), a.get("entity"), a.get("quantity"))
        latest[key] = a
    stats = {"ok": 0, "salah": 0, "ragu": 0, "manusia_ignited": 0}
    for a in latest.values():
        where, args = [], []
        if a.get("measurement"):
            where.append("id=?"); args.append(a["measurement"])
        if a.get("artifact"):
            where.append("source_artifact=?"); args.append(a["artifact"])
        if a.get("entity"):
            where.append("entity=?"); args.append(a["entity"])
        if a.get("quantity"):
            where.append("quantity=?"); args.append(a["quantity"])
        rows = c.execute(f"SELECT id, tier, flags FROM measurement WHERE {' AND '.join(where)}", args).fetchall()
        for mid, tier, flags in rows:
            fl = [f for f in json.loads(flags) if f not in ("belum_diverifikasi_manusia", "ditolak_manusia", "diragukan_manusia")]
            new_tier = tier
            verdict = a["verdict"]
            if a.get("value_text") and tier == "derived_auto":
                # manusia memberi nilainya sendiri: angka turunan dinilai dengan membandingkannya
                cur = c.execute("SELECT value_text FROM measurement WHERE id=?", (mid,)).fetchone()[0]
                verdict = "ok" if (cur or "").lower() == a["value_text"] else "salah"
            if verdict == "ok" and tier == "derived_auto":
                new_tier = "human_verified"
            elif verdict == "salah":
                fl.append("ditolak_manusia")
            elif verdict == "ragu":
                fl.append("diragukan_manusia")
            c.execute("UPDATE measurement SET tier=?, flags=?, verified_by=? WHERE id=?",
                      (new_tier, json.dumps(fl, ensure_ascii=False), f"{a['author']} {a['t'][:10]} [{a['id']}]", mid))
            stats[verdict] += 1
        if a.get("value_text") and a.get("entity"):              # manusia memberi nilai menyala sendiri
            mid = f"m:{a['entity'][5:]}:ignited:human"
            c.execute("INSERT OR REPLACE INTO measurement VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (mid, a["entity"], "ignited", None, a["value_text"], "", None, None, "", "human_verified",
                       f"putusan manusia: {a['note'][:200]}", "", f"anotasi {a['id']}", "[]",
                       f"{a['author']} {a['t'][:10]} [{a['id']}]"))
            stats["manusia_ignited"] += 1
    return stats


# ================================================================ 2. pipeline
def _fp(paths):
    """Sidik jari masukan: sha1 isi untuk berkas kecil, ukuran+mtime untuk berkas besar."""
    h = hashlib.sha1()
    for p in paths:
        p = ANN if p == "kb/gold/annotations.jsonl" else ROOT / p        # log anotasi bisa dialihkan
        if not p.exists():
            h.update(f"{p}:absent".encode())
            continue
        st = p.stat()
        if st.st_size < 20e6:
            h.update(p.read_bytes())
        else:
            h.update(f"{p}:{st.st_size}:{st.st_mtime_ns}".encode())
    return h.hexdigest()


STEPS = [  # (nama, masukan, keluaran, perintah, hanya_full)
    ("proof_apply", ["kb/gold/annotations.jsonl", "analysis/video_full/measurements.csv"],
     ["analysis/video_full/measurements_verified.csv"], "internal:proof_apply", False),
    ("ml_labels", ["analysis/ml/telemetry_tensors.npz", "kb/gold/tests.csv", "kb/gold/annotations.jsonl", "scripts/ml_labels.py"],
     ["analysis/ml/telemetry_gb_predictions.csv"], [PY, "scripts/ml_labels.py"], False),
    ("stats_uq", ["analysis/video_full/measurements_verified.csv", "analysis/video_full/measurements.csv",
                  "analysis/telemetry/telemetry_joined.csv", "kb/gold/tests.csv", "scripts/stats_uq.py"],
     ["analysis/stats/uq.json"], [PY, "scripts/stats_uq.py"], False),
    ("corridor", ["analysis/ml/telemetry_tensors.npz", "analysis/telemetry/telemetry_joined.csv", "scripts/telemetry_corridor.py"],
     ["analysis/telemetry/corridor/anomaly_scores.csv"], [PY, "scripts/telemetry_corridor.py"], True),
    ("boundary", ["kb/gold/tests.csv", "scripts/ml_boundary.py"], ["analysis/ml/boundary/boundary.json"],
     [PY, "scripts/ml_boundary.py"], True),
    ("symreg", ["kb/gold/tests.csv", "scripts/symreg_flex.py"], ["analysis/ml/symreg_flex.json"], [PY, "scripts/symreg_flex.py"], True),
    ("quantile", ["kb/gold/tests.csv", "scripts/ml_quantile.py"], ["analysis/ml/quantile_burn.json"], [PY, "scripts/ml_quantile.py"], True),
    ("saffire", ["scripts/saffire_spread.py"], ["analysis/saffire/spread_rates.json"],
     [PY, "scripts/saffire_spread.py"], True),
    ("build_brain", ["kb/gold/freefall.sqlite", "kb/gold/annotations.jsonl", "analysis/telemetry/telemetry_joined.csv",
                     "analysis/telemetry/telemetry_calibrated.csv", "analysis/telemetry/corridor/anomaly_scores.csv",
                     "analysis/video_full/measurements.csv", "analysis/ml/telemetry_gb_predictions.csv",
                     "analysis/ml/boundary/boundary.json", "analysis/ml/symreg_flex.json", "analysis/ml/quantile_burn.json",
                     "analysis/saffire/spread_rates.json", "scripts/build_brain.py", "scripts/learn.py"],
     ["kb/gold/brain.sqlite"], [PY, "scripts/build_brain.py"], False),
]


def _is_stale(st, name, ins, outs):
    """Basi bila masukan berubah ATAU keluaran tidak lagi sama dengan yang dihasilkan langkah ini
    (mis. ditimpa proses lain / uji coba) — keluaran yang diubah diam-diam tidak boleh dipercaya."""
    rec = st.get(name)
    if not isinstance(rec, dict):
        return True
    return rec.get("in") != _fp(ins) or rec.get("out") != _fp(outs)


def _state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def status(full=False):
    st = _state()
    out = []
    for name, ins, outs, _, only_full in STEPS:
        if only_full and not full:
            continue
        missing = [o for o in outs if not (ROOT / o).exists() and name != "proof_apply"]
        out.append({"step": name, "stale": _is_stale(st, name, ins, outs) or bool(missing), "missing": missing})
    return out


def proof_apply():
    """measurements_verified.csv dari anotasi video (ok saja) — pengganti proof_review.py --apply."""
    latest = {}
    for a in annotations():
        if a.get("artifact", "").startswith("art:video:"):
            latest[a["artifact"][len("art:video:"):]] = a
    src = ROOT / "analysis" / "video_full" / "measurements.csv"
    dest = ROOT / "analysis" / "video_full" / "measurements_verified.csv"
    rows = [r for r in csv.DictReader(open(src, encoding="utf-8")) if latest.get(r["source_video"], {}).get("verdict") == "ok"]
    if rows:
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) + ["verified_by"])
            w.writeheader()
            for r in rows:
                a = latest[r["source_video"]]
                w.writerow({**r, "verified_by": f"{a['author']} {a['t'][:10]}"})
    elif dest.exists():
        dest.unlink()                                    # tidak ada lagi yang OK -> jangan pakai berkas lama
    return len(rows)


def run(full=False, trigger="manual", log=print, before=None, after=None):
    """before/after(name): kait per langkah — server memakainya untuk melepas berkas otak sebelum build_brain."""
    st = _state()
    ran = []
    t0 = time.time()
    for name, ins, outs, cmd, only_full in STEPS:
        if only_full and not full:
            continue
        if not _is_stale(st, name, ins, outs) and all((ROOT / o).exists() or name == "proof_apply" for o in outs):
            continue
        t = time.time()
        if before:
            before(name)
        if cmd == "internal:proof_apply":
            n = proof_apply()
            log(f"  {name}: {n} episode video terverifikasi")
        else:
            env = {**__import__("os").environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
            if r.returncode != 0:
                log(f"  {name}: GAGAL\n{r.stderr[-1500:]}")
                raise RuntimeError(f"langkah {name} gagal")
            log(f"  {name}: selesai ({time.time() - t:.1f} s)")
        if after:
            after(name)
        st[name] = {"in": _fp(ins), "out": _fp(outs)}     # masukan DAN keluaran yang dihasilkan langkah ini
        ran.append(name)
        STATE.write_text(json.dumps(st, indent=1), encoding="utf-8")
    if ran:
        snap = history_snapshot(trigger, ran)
        log(f"  history: {json.dumps(snap['summary'], ensure_ascii=False)}")
    return {"ran": ran, "seconds": round(time.time() - t0, 1)}


def history_snapshot(trigger, ran):
    """Riwayat model: metrik kartu, jumlah per tier, peringatan, dan berapa prediksi yang berubah."""
    c = sqlite3.connect(f"file:{BRAIN}?mode=ro", uri=True)
    tiers = dict(c.execute("SELECT tier, count(*) FROM measurement GROUP BY 1").fetchall())
    cards = {r[0]: json.loads(r[1]) for r in c.execute("SELECT id, metrics FROM model_card")}
    preds = dict(c.execute("SELECT entity, value FROM measurement WHERE quantity='p_ignite' AND method='model:gb_telemetry_labels'"))
    c.close()
    prev = None
    if HISTORY.exists():
        lines = [l for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]
        prev = json.loads(lines[-1]) if lines else None
    changed = []
    if prev and prev.get("gb_predictions"):
        for e, v in preds.items():
            p0 = prev["gb_predictions"].get(e)
            if p0 is not None and v is not None and (p0 > 0.5) != (v > 0.5):
                changed.append({"entity": e, "before": p0, "after": v})
    sys.path.insert(0, str(ROOT / "scripts"))
    import brain  # noqa: E402
    brain._CACHE.clear()
    al = brain.alerts()["counts"]
    snap = {"t": now(), "trigger": trigger, "ran": ran, "tiers": tiers, "alerts": al, "cards": cards,
            "n_annotations": len(annotations()), "flipped_predictions": changed,
            "gb_predictions": {e: round(v, 4) for e, v in preds.items() if v is not None},
            "summary": {"human_verified": tiers.get("human_verified", 0), "alerts": al,
                        "prediksi_berubah": len(changed), "anotasi": len(annotations())}}
    with open(HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(snap, ensure_ascii=False) + "\n")
    return snap


def history(limit=20):
    if not HISTORY.exists():
        return []
    rows = [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()][-limit:]
    for r in rows:
        r.pop("gb_predictions", None)
    return rows


# ================================================================ 3. antrean verifikasi
def queue(k=20):
    """Nilai = ketidakpastian x dampak. Hanya item yang BELUM diputuskan manusia."""
    c = sqlite3.connect(f"file:{BRAIN}?mode=ro", uri=True)
    decided_m, decided_e, decided_a = set(), set(), set()
    for a in annotations():
        decided_m.add(a.get("measurement")); decided_a.add(a.get("artifact"))
        decided_e.add((a.get("entity"), a.get("quantity")))
    items = []
    # (a) kontradiksi tabel NASA vs telemetri: dampak tinggi (peringatan kritis), ketidakpastian tinggi
    for e, a_, b_ in c.execute("""SELECT n.entity, n.value_text, d.value_text FROM measurement n JOIN measurement d
            ON d.entity=n.entity AND d.quantity='ignited' AND d.tier='derived_auto'
            WHERE n.quantity='ignited' AND n.tier='nasa_table'"""):
        if ((a_ or "").lower() in ("yes", "ya")) != ((b_ or "").lower() == "ya") and (e, "ignited") not in decided_e:
            items.append({"entity": e, "quantity": "ignited", "why": f"tabel NASA '{a_}' vs telemetri '{b_}'",
                          "uncertainty": 0.9, "impact": 1.0, "action": "lihat kurva termokopel & koridor; beri putusan ya/tidak"})
    # (b) aturan yang menandai kemungkinan salah pada uji yang hanya ada di telemetri
    for rid, e, det in c.execute("SELECT rule_id, entity, detail FROM rule_hit WHERE rule_id IN ('R3_tanpa_konsumsi_o2','R2_percobaan_ulang')"):
        if (e, "ignited") not in decided_e:
            items.append({"entity": e, "quantity": "ignited", "why": f"{rid}: {det}",
                          "uncertainty": 0.8 if rid.startswith("R3") else 0.5, "impact": 0.6,
                          "action": "putuskan apakah uji ini benar menyala"})
    # (c) prediksi model yang paling ragu (dekat 0,5) — label manusia paling mengubah model
    for e, mid, v, lo, hi in c.execute("""SELECT entity, id, value, lo, hi FROM measurement
            WHERE quantity='p_ignite' AND tier='model_prediction'"""):
        if v is None or (e, "ignited") in decided_e:
            continue
        u = 1 - abs(v - 0.5) * 2
        if u > 0.5:
            items.append({"entity": e, "quantity": "ignited", "measurement": mid,
                          "why": f"model ragu: P(menyala) {v:.2f}", "uncertainty": round(u, 3), "impact": 0.4,
                          "action": "beri label ya/tidak — langsung dipakai saat latih ulang"})
    # (d) video: satu putusan per video menaikkan banyak episode sekaligus
    for art, n, tot in c.execute("""SELECT source_artifact, count(*), sum(value) FROM measurement
            WHERE quantity='visible_flame_duration' AND flags LIKE '%belum_diverifikasi_manusia%' GROUP BY 1"""):
        if art in decided_a:
            continue
        items.append({"artifact": art, "quantity": "visible_flame_duration",
                      "why": f"{n} episode ({tot:.0f} s nyala) belum diverifikasi", "uncertainty": 0.6,
                      "impact": min(1.0, 0.2 + 0.1 * n), "action": "buka lembar bukti video; OK / Salah / Ragu"})
    for it in items:
        it["value"] = round(it["uncertainty"] * it["impact"], 3)
    c.close()
    items.sort(key=lambda x: -x["value"])
    return {"n": len(items), "items": items[:k]}


# ================================================================ CLI
def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("annotate")
    for f in ("entity", "quantity", "measurement", "artifact", "value_text", "note"):
        a.add_argument(f"--{f}")
    a.add_argument("--verdict", required=True, choices=VERDICTS)
    a.add_argument("--author", default="cli")
    r = sub.add_parser("import-review"); r.add_argument("path")
    s = sub.add_parser("status"); s.add_argument("--full", action="store_true")
    u = sub.add_parser("run"); u.add_argument("--full", action="store_true")
    q = sub.add_parser("queue"); q.add_argument("-k", type=int, default=20)
    sub.add_parser("history")
    x = ap.parse_args()
    if x.cmd == "annotate":
        print(json.dumps(annotate(x.entity, x.quantity, x.measurement, x.artifact, x.verdict, x.value_text,
                                  x.note or "", x.author, "cli"), ensure_ascii=False, indent=1))
    elif x.cmd == "import-review":
        print(import_review(x.path), "putusan baru dari lembar bukti")
    elif x.cmd == "status":
        for s_ in status(x.full):
            print(f"  {s_['step']:12s} {'BASI' if s_['stale'] else 'segar'} {s_['missing'] or ''}")
    elif x.cmd == "run":
        print(json.dumps(run(x.full), ensure_ascii=False))
    elif x.cmd == "queue":
        for it in queue(x.k)["items"]:
            print(f"  {it['value']:.2f}  {it.get('entity') or it.get('artifact')}  {it['why']}")
    elif x.cmd == "history":
        for h in history():
            print(h["t"][:19], h["trigger"], h["summary"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
