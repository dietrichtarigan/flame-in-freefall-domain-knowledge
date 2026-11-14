#!/usr/bin/env python3
"""Lapis penalaran + API otak (docs/rencana_dashboard_cerdas.md, L2 & bagian 3).

Fungsi (dipakai tampilan DAN asisten — klien yang sama):
  entity(id)          dosir lengkap: atribut, semua angka dengan tier, tautan, aturan yang kena
  explain(id)         hipotesis "kenapa" berperingkat, masing-masing dengan bukti & tier (abduktif)
  relevance(id, k)    entitas paling relevan terhadap fokus (Ware, degree-of-relevance)
  provenance(mid)     rantai asal-usul satu angka
  coverage()          peta yang belum diketahui: angka per investigasi x tier
  search(q)           cari uji + paper (FTS5 di freefall.sqlite)

CLI:
  python scripts/brain.py entity PSI-159:21106G8
  python scripts/brain.py explain PSI-159:21106G8
  python scripts/brain.py relevance PSI-159:21106G8
  python scripts/brain.py coverage
  python scripts/brain.py serve --port 8765     # GET /entity/<id>, /explain/<id>, /relevance/<id>,
                                                #     /provenance/<mid>, /coverage, /search?q=
"""
import json
import math
import re
import sqlite3
import sys
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

if __name__ == "__main__":        # learn/assistant mengimpor 'brain' -> pakai modul yang SAMA (satu daftar koneksi)
    sys.modules.setdefault("brain", sys.modules[__name__])

ROOT = Path(__file__).resolve().parent.parent
BRAIN = ROOT / "kb" / "gold" / "brain.sqlite"
GOLD = ROOT / "kb" / "gold" / "freefall.sqlite"
TIER_RANK = {"nasa_table": 1, "nasa_calibrated": 2, "human_verified": 3, "derived_auto": 4,
             "paper_claim": 5, "model_prediction": 6}
TIER_ID = {"nasa_table": "tabel NASA", "nasa_calibrated": "sinyal NASA terkalibrasi",
           "derived_auto": "turunan otomatis (belum dicek manusia)", "human_verified": "diverifikasi manusia",
           "paper_claim": "klaim paper", "model_prediction": "prediksi model"}


import threading

_LOCAL = threading.local()
_ALL_CONNS = []
_CONN_LOCK = threading.Lock()
REBUILD_LOCK = threading.RLock()          # dipegang selama otak ditukar; permintaan menunggu sebentar


_GEN = [0]
_OPEN = threading.Event()          # dibersihkan selama otak ditukar: koneksi baru menunggu sebentar
_OPEN.set()


def db():
    """Satu koneksi baca per thread, dipakai ulang. Setelah close_all() generasi naik, sehingga
    setiap thread membuka koneksi baru ke otak yang sudah ditukar."""
    if not _OPEN.is_set():
        _OPEN.wait(60)
    c = getattr(_LOCAL, "conn", None)
    if c is None or getattr(_LOCAL, "gen", -1) != _GEN[0]:
        c = sqlite3.connect(f"file:{BRAIN}?mode=ro", uri=True, check_same_thread=False)
        c.row_factory = sqlite3.Row
        _LOCAL.conn, _LOCAL.gen = c, _GEN[0]
        with _CONN_LOCK:
            _ALL_CONNS.append(c)
    return c


def close_all():
    """Tutup semua koneksi (dari thread mana pun) dan kosongkan cache — dipanggil sebelum otak ditukar."""
    with _CONN_LOCK:
        _GEN[0] += 1
        for c in _ALL_CONNS:
            try:
                c.close()
            except Exception:  # noqa: BLE001
                pass
        _ALL_CONNS.clear()
    _CACHE.clear()


def canon(x):
    x = x.strip()
    if x.startswith("test:"):
        return x
    acc, _, t = x.partition(":")
    t = re.sub(r"\s+", "", t)      # di luar f-string: backslash di dalam f-string baru sah sejak Python 3.12
    return f"test:{acc.upper()}:{t.upper()}"


def _ms(c, e):
    out = []
    for r in c.execute("SELECT * FROM measurement WHERE entity=? ORDER BY quantity", (e,)):
        d = dict(r)
        d["flags"] = json.loads(d["flags"])
        d["tier_label"] = TIER_ID[d["tier"]]
        out.append(d)
    return out


def entity(id_):
    c = db()
    e = canon(id_) if ":" in id_ and not id_.startswith(("inv:", "art:", "paper:")) else id_
    r = c.execute("SELECT * FROM entity WHERE id=?", (e,)).fetchone()
    if not r:
        return {"error": f"entitas {e} tidak ada"}
    ms = _ms(c, e)
    by_q = defaultdict(list)
    for m in ms:
        by_q[m["quantity"]].append(m)
    for q in by_q:                                   # urutkan: tier paling tepercaya dulu
        by_q[q].sort(key=lambda m: TIER_RANK[m["tier"]])
    links = [dict(x) for x in c.execute("SELECT dst, rel, weight FROM link WHERE src=?", (e,))]
    hits = [dict(x) for x in c.execute(
        "SELECT h.rule_id, h.detail, r.effect, r.reason FROM rule_hit h JOIN rule r ON r.id=h.rule_id WHERE h.entity=?", (e,))]
    return {"id": e, "kind": r["kind"], "accession": r["accession"], "label": r["label"],
            "attrs": json.loads(r["attrs"]), "measurements": by_q, "links": links, "rule_hits": hits,
            "contradictions": contradictions(by_q)}


def contradictions(by_q):
    """Dua sumber berbeda untuk besaran yang sama yang tidak sepakat."""
    out = []
    ig = by_q.get("ignited", [])
    vals = {m["tier"]: (m["value_text"] or "").lower() for m in ig}
    if "nasa_table" in vals and "derived_auto" in vals:
        nasa, tel = vals["nasa_table"] in ("yes", "ya"), vals["derived_auto"] == "ya"
        if nasa != tel:
            out.append({"quantity": "ignited", "detail": f"tabel NASA '{vals['nasa_table']}' vs telemetri "
                        f"'{vals['derived_auto']}' — tabel NASA diutamakan"})
    return out


_CACHE = {}


def _table():
    """Satu baris ringkas per uji, dimuat sekali (untuk daftar, filter, relevansi, what-if)."""
    if "tests" in _CACHE:
        return _CACHE["tests"]
    c = db()
    rows = {}
    for e, acc, lab, attrs in c.execute("SELECT id, accession, label, attrs FROM entity WHERE kind='test'"):
        a = json.loads(attrs)
        rows[e] = {"id": e, "accession": acc, "label": lab, "granularity": a.get("granularity"),
                   "fuel": a.get("fuel"), "config": (a.get("configuration") or "").split(" ")[0].lower(),
                   "o2": None, "p_kpa": None, "ignited": None, "ignited_tier": None, "flags": [], "rules": []}
    best = {}
    for e, q, v, t, tier, fl in c.execute("""SELECT entity, quantity, value, value_text, tier, flags FROM measurement
            WHERE quantity IN ('o2_mole_frac','pressure','chamber_pressure_start','ignited','configuration','fuel')"""):
        r = rows.get(e)
        if not r:
            continue
        rank = TIER_RANK[tier]
        key = {"pressure": "p_kpa", "chamber_pressure_start": "p_kpa", "o2_mole_frac": "o2",
               "ignited": "ignited", "configuration": "config", "fuel": "fuel"}[q]
        for f in json.loads(fl):
            if f not in r["flags"]:
                r["flags"].append(f)
        if (e, key) in best and best[(e, key)] <= rank:
            continue
        best[(e, key)] = rank
        if key == "ignited":
            r["ignited"] = {"yes": True, "ya": True, "no": False, "tidak": False}.get((t or "").lower())
            r["ignited_tier"] = tier
        elif key == "config":
            r["config"] = (t or "").split(" ")[0].lower()
        elif key == "fuel":
            r["fuel"] = t
        else:
            r[key] = v
    for e, fl in c.execute("SELECT entity, flags FROM measurement WHERE flags != '[]'"):
        if e in rows:
            for f in json.loads(fl):
                if f not in rows[e]["flags"]:
                    rows[e]["flags"].append(f)
    for rid, e in c.execute("SELECT rule_id, entity FROM rule_hit"):
        if e in rows and rid not in rows[e]["rules"]:
            rows[e]["rules"].append(rid)
    _CACHE["tests"] = rows
    return rows


def tests(acc=None, q=None, limit=5000):
    rows = [r for r in _table().values() if (not acc or r["accession"] == acc)
            and (not q or q.lower() in (r["label"] + " " + (r["fuel"] or "")).lower())]
    rows.sort(key=lambda r: (r["accession"], r["label"]))
    return {"n": len(rows), "tests": rows[:limit]}


def relevance(id_, k=15):
    """Derajat relevansi (Ware, Algoritma 7) terhadap fokus, lintas jenis entitas:
    uji     = tautan graf (seri 1,0 / hari 0,4) + kedekatan kondisi exp(-d) dalam (O2, ln p), konfigurasi sama
    paper   = pencarian teks pada akronim investigasi + bahan bakar
    artefak = berkas yang tertaut langsung (telemetri, video)"""
    c = db()
    e = canon(id_)
    T = _table()
    if e not in T:
        return {"error": f"entitas {e} tidak ada"}
    me = T[e]
    score, why = defaultdict(float), defaultdict(list)
    for dst, rel, w in c.execute("SELECT dst, rel, weight FROM link WHERE src=? AND dst LIKE 'test:%'", (e,)):
        score[dst] += w
        why[dst].append(rel)
    if me["o2"] is not None and me["p_kpa"]:
        lp = math.log(me["p_kpa"])
        for o in T.values():
            if o["id"] == e or o["accession"] != me["accession"] or o["config"] != me["config"] \
                    or o["o2"] is None or not o["p_kpa"]:
                continue
            d = math.hypot((o["o2"] - me["o2"]) / 0.05, (math.log(o["p_kpa"]) - lp) / 0.3)
            s = math.exp(-d)
            if s > 0.2:
                score[o["id"]] += s
                why[o["id"]].append(f"kondisi mirip (jarak {d:.2f})")
    top = sorted(score.items(), key=lambda kv: -kv[1])[:k]
    related = [{"id": o, "kind": "test", "label": T[o]["label"] if o in T else o.split(":")[-1],
                "score": round(s, 3), "why": why[o],
                "ignited": T[o]["ignited"] if o in T else None,
                "ignited_tier": T[o]["ignited_tier"] if o in T else None} for o, s in top]
    arts = [{"id": a, "kind": "artifact", "score": 1.0, "why": [rel]}
            for a, rel in c.execute("SELECT dst, rel FROM link WHERE src=? AND dst LIKE 'art:%'", (e,))]
    inv = c.execute("SELECT label FROM entity WHERE id=?", (f"inv:{me['accession']}",)).fetchone()
    papers = []
    terms = [t for t in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", (inv[0] if inv else "") + " " + (me["fuel"] or ""))
             if t.lower() not in ("and", "the", "with")][:3]
    if terms:
        res = search(" OR ".join('"' + t + '"' for t in terms), 8)
        seen = set()
        for p_ in res["papers"]:
            if p_["title"] not in seen:
                seen.add(p_["title"])
                papers.append({"kind": "paper", "title": p_["title"], "page": p_["page"], "snippet": p_["snippet"],
                               "why": ["teks memuat: " + ", ".join(terms)]})
    return {"focus": e, "related": related, "artifacts": arts, "papers": papers}


LEVEL = {"kritis": 3, "perhatian": 2, "info": 1}


def alerts(entity_id=None, min_level="info"):
    """Peringatan bertingkat (Ware, Algoritma 10): sistem yang memanggil perhatian.
    kritis    = sumber bertentangan (tabel NASA vs turunan kita)
    perhatian = kemungkinan positif palsu, keluar koridor, percobaan ulang tak ditabulasi
    info      = sinyal lemah, angka belum diverifikasi manusia"""
    c = db()
    T = _table()
    out = []
    # sudah diputuskan manusia -> bukan lagi peringatan (tahap D, learn.py)
    resolved = {e for (e,) in c.execute("""SELECT DISTINCT entity FROM measurement WHERE quantity='ignited' AND
            (tier='human_verified' OR flags LIKE '%ditolak_manusia%')""")}
    for e, a, b in c.execute("""SELECT n.entity, n.value_text, d.value_text FROM measurement n JOIN measurement d
            ON d.entity=n.entity AND d.quantity='ignited' AND d.tier='derived_auto'
            WHERE n.quantity='ignited' AND n.tier='nasa_table'"""):
        if e in resolved:
            continue
        if ((a or "").lower() in ("yes", "ya")) != ((b or "").lower() == "ya"):
            out.append({"level": "kritis", "entity": e, "title": "tabel NASA dan telemetri tidak sepakat soal menyala",
                        "evidence": [f"tabel NASA: {a}", f"telemetri (turunan): {b}"],
                        "action": "periksa koridor & catatan operator; tabel NASA diutamakan"})
    names = {"R3_tanpa_konsumsi_o2": ("perhatian", "kemungkinan positif palsu (tanpa konsumsi O2)"),
             "R2_percobaan_ulang": ("perhatian", "percobaan ulang yang tidak ditabulasi NASA"),
             "R1_sinyal_lemah": ("info", "sinyal termokopel lemah"),
             "R6_beda_sumber": ("perhatian", "tabel NASA dan paper mencatat nilai berbeda")}
    for rid, e, det in c.execute("SELECT rule_id, entity, detail FROM rule_hit"):
        if rid in names and e not in resolved:
            lv, title = names[rid]
            out.append({"level": lv, "entity": e, "title": title, "evidence": [det], "action": f"lihat aturan {rid}"})
    for e, v, loc in c.execute("""SELECT entity, value, source_locator FROM measurement
            WHERE quantity='corridor_anomaly' AND flags LIKE '%keluar_koridor%'"""):
        out.append({"level": "perhatian", "entity": e, "title": "kurva sensor keluar koridor normal",
                    "evidence": [f"skor {v:.2f} di atas p95 kelompok {loc}"], "action": "buka koridor telemetri"})
    n_unver = c.execute("SELECT count(*) FROM measurement WHERE flags LIKE '%belum_diverifikasi_manusia%'").fetchone()[0]
    if n_unver:
        out.append({"level": "info", "entity": None, "title": f"{n_unver} angka video belum diverifikasi manusia",
                    "evidence": ["analysis/video_full/review.html"], "action": "jalankan pemeriksaan lembar bukti"})
    if entity_id:
        e = canon(entity_id)
        out = [a for a in out if a["entity"] == e]
    out = [a for a in out if LEVEL[a["level"]] >= LEVEL.get(min_level, 1)]
    for a in out:
        a["label"] = T[a["entity"]]["label"] if a["entity"] in T else None
        a["id"] = f"{a['level']}|{a['entity']}|{a['title']}"
    out.sort(key=lambda a: (-LEVEL[a["level"]], a["entity"] or ""))
    counts = {lv: sum(a["level"] == lv for a in out) for lv in LEVEL}
    return {"counts": counts, "alerts": out}


def _grid_lookup(xs, ys, Z, x, y):
    """Interpolasi bilinear di grid (xs: kolom, ys: baris). None bila di luar rentang."""
    import bisect
    if not (xs[0] <= x <= xs[-1] and ys[0] <= y <= ys[-1]):
        return None
    i = min(max(bisect.bisect_right(xs, x) - 1, 0), len(xs) - 2)
    j = min(max(bisect.bisect_right(ys, y) - 1, 0), len(ys) - 2)
    tx = (x - xs[i]) / (xs[i + 1] - xs[i]) if xs[i + 1] != xs[i] else 0
    ty = (y - ys[j]) / (ys[j + 1] - ys[j]) if ys[j + 1] != ys[j] else 0
    z = lambda a, b: Z[b][a]
    return ((1 - tx) * (1 - ty) * z(i, j) + tx * (1 - ty) * z(i + 1, j)
            + (1 - tx) * ty * z(i, j + 1) + tx * ty * z(i + 1, j + 1))


def whatif(exp="cfig", **p):
    """Simulator what-if (Big Book bab 4) dari keluaran model yang sudah disimpan.
    cfig: config(normal|inverse), fuel(ethane|propane|butane), o2, x_fuel  -> P(menyala) + sigma laten
    flex: fuel(heptane|methanol), o2, pressure_kpa, he                     -> P(padam) + K (rumus jarang)
    Selalu disertai uji nyata terdekat dan status rentang berlaku."""
    if "boundary" not in _CACHE:
        _CACHE["boundary"] = json.loads((ROOT / "analysis" / "ml" / "boundary" / "boundary.json").read_text(encoding="utf-8"))
        sr = ROOT / "analysis" / "ml" / "symreg_flex.json"
        _CACHE["symreg"] = json.loads(sr.read_text(encoding="utf-8")) if sr.exists() else None
    B = _CACHE["boundary"]
    f = lambda k, d=None: float(p[k]) if p.get(k) not in (None, "") else d
    out = {"exp": exp, "input": p, "tier": "model_prediction"}
    if exp == "cfig":
        g = next((m for m in B["cfig_ign"]["maps"] if m["config"] == p.get("config", "normal")
                  and m["fuel"] == p.get("fuel", "butane")), None)
        if not g:
            return {**out, "valid": False, "error": "kombinasi konfigurasi/bahan bakar tidak ada di data"}
        o2, xf = f("o2", 0.21), f("x_fuel", 0.3)
        pr = _grid_lookup(g["o2"], g["x_fuel"], g["p_ignite"], o2, xf)
        sd = _grid_lookup(g["o2"], g["x_fuel"], g["sigma_latent"], o2, xf)
        out.update({"p_ignite": None if pr is None else round(pr, 3), "sigma_latent": None if sd is None else round(sd, 3),
                    "valid": pr is not None, "range": {"o2": [g["o2"][0], g["o2"][-1]], "x_fuel": [g["x_fuel"][0], g["x_fuel"][-1]]},
                    "fixed": {"pressure_kpa": g["pressure_kpa"], "fuel_flow_mg_s": g["fuel_flow_mg_s"]},
                    "model": "gp_boundary_cfig_ign", "metrics": B["cfig_ign"]["cv_per_hari"]})
        out["nearest_tests"] = sorted(g["tested"], key=lambda t: math.hypot((t["o2"] - o2) / 0.05, (t["x_fuel"] - xf) / 0.05))[:5]
    else:
        g = next((m for m in B["flex_ext"]["maps"] if m["fuel"] == p.get("fuel", "heptane")), None)
        o2, pk, he = f("o2", 0.2), f("pressure_kpa", 101.3), f("he", 0.0)
        pr = _grid_lookup(g["o2"], g["pressure_kpa"], g["p_extinction"], o2, pk) if g else None
        sd = _grid_lookup(g["o2"], g["pressure_kpa"], g["sigma_latent"], o2, pk) if g else None
        out.update({"p_extinction": None if pr is None else round(pr, 3), "sigma_latent": None if sd is None else round(sd, 3),
                    "valid": pr is not None, "model": "gp_boundary_flex_ext", "metrics": B["flex_ext"]["cv_per_hari"],
                    "range": {"o2": [g["o2"][0], g["o2"][-1]], "pressure_kpa": [g["pressure_kpa"][0], g["pressure_kpa"][-1]]} if g else None,
                    "fixed": {"x_co2": g["x_co2"], "x_he_map": g["x_he"], "d0_mm": g["d0_mm"]} if g else None})
        S = _CACHE["symreg"]
        if S:
            coef = dict(S["terms"])
            K = coef.get("1", 0) + coef.get("O2", 0) * o2 + coef.get("He", 0) * he
            out["K_mm2_s"] = {"value": round(K, 4), "formula": S["formula"], "rmse_per_hari": S["cv_rmse_per_hari"]}
        if g:
            out["nearest_tests"] = sorted(g["tested"], key=lambda t: math.hypot((t["o2"] - o2) / 0.05,
                                          math.log(t["pressure_kpa"] / pk) / 0.3))[:5]
    if not out.get("valid"):
        out["warning"] = "di luar rentang kondisi yang pernah diuji: model tidak menjawab (ekstrapolasi)"
    return out


NOTES = ROOT / "kb" / "gold" / "notes.jsonl"


def add_note(entity_id, text, author="anonim"):
    """Externalizing (Ware bab 11): catatan pengguna disimpan bersama, bukan hanya di browser."""
    from datetime import datetime, timezone
    rec = {"t": datetime.now(timezone.utc).isoformat(), "entity": canon(entity_id) if entity_id else None,
           "text": str(text)[:2000], "author": str(author)[:60]}
    with open(NOTES, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def notes(entity_id=None):
    if not NOTES.exists():
        return {"notes": []}
    rs = [json.loads(l) for l in NOTES.read_text(encoding="utf-8").splitlines() if l.strip()]
    if entity_id:
        rs = [r for r in rs if r["entity"] == canon(entity_id)]
    return {"notes": rs}


def explain(id_):
    """Penalaran abduktif: kumpulkan hipotesis, beri bukti, urutkan menurut kekuatan bukti."""
    d = entity(id_)
    if "error" in d:
        return d
    c = db()
    e, ms, H = d["id"], d["measurements"], []

    def val(q, tier=None):
        for m in ms.get(q, []):
            if tier is None or m["tier"] == tier:
                return m
        return None

    for m in ms.get("ignited", []):                       # putusan manusia mengalahkan semua heuristik
        if m["tier"] == "human_verified":
            H.append({"hipotesis": f"diputuskan manusia: menyala = {m['value_text'] or m['value']}",
                      "bukti": [m["method"], m["verified_by"] or ""], "kekuatan": 1.0, "sumber": "putusan manusia (tahap D)"})
    for h in d["rule_hits"]:
        strength = {"R3_tanpa_konsumsi_o2": 0.9, "R2_percobaan_ulang": 0.8, "R1_sinyal_lemah": 0.4,
                    "R5_ada_catatan_operator": 0.7, "R4_kanal_aliran_inverse": 0.2, "R6_beda_sumber": 0.8}.get(h["rule_id"], 0.5)
        H.append({"hipotesis": h["effect"], "bukti": [h["detail"], "dasar aturan: " + h["reason"]],
                  "kekuatan": strength, "sumber": f"aturan {h['rule_id']}"})
    an = val("corridor_anomaly")
    if an:
        z = an["value"]
        H.append({"hipotesis": "kurva sensor menyimpang dari uji sejenis" if "keluar_koridor" in an["flags"]
                  else "kurva sensor sesuai uji sejenis",
                  "bukti": [f"skor koridor {z:.2f} ({an['source_locator']})"],
                  "kekuatan": 0.6 if "keluar_koridor" in an["flags"] else 0.15, "sumber": "koridor proses"})
    if d["attrs"].get("note") == "tidak ada di tabel uji NASA":
        H.append({"hipotesis": "uji tidak ditabulasi NASA (dibatalkan/uji coba/terlewat)",
                  "bukti": ["hanya ada berkas telemetri; tidak ada baris di tabel uji PSI"],
                  "kekuatan": 0.5, "sumber": "struktur data"})
    # tetangga seri: apa yang terjadi sebelum/sesudah
    for rel in ("prev_in_series", "next_in_series"):
        for l in d["links"]:
            if l["rel"] == rel:
                n = entity(l["dst"])
                ig = (n["measurements"].get("ignited") or [{}])[0]
                note = (n["measurements"].get("operator_note") or [{}])[0].get("value_text")
                H.append({"hipotesis": f"konteks seri: {'sebelum' if rel.startswith('prev') else 'sesudah'} = {n['label']}",
                          "bukti": [f"menyala: {ig.get('value_text')} ({ig.get('tier_label', '-')})"]
                          + ([f"catatan NASA: {note}"] if note else []),
                          "kekuatan": 0.3, "sumber": "tautan seri"})
    for x in d["contradictions"]:
        H.append({"hipotesis": "sumber saling bertentangan", "bukti": [x["detail"]], "kekuatan": 0.7,
                  "sumber": "pemeriksa kontradiksi"})
    rel = relevance(e, 5).get("related", [])
    sim = [r for r in rel if any("kondisi mirip" in w for w in r["why"])]
    if sim:
        yes = sum(1 for r in sim if r["ignited"])
        H.append({"hipotesis": f"uji berkondisi mirip: {yes}/{len(sim)} menyala",
                  "bukti": [f"{r['label']} → {'menyala' if r['ignited'] else 'tidak' if r['ignited'] is False else '?'}"
                            f" ({TIER_ID.get(r['ignited_tier'], '-')})" for r in sim],
                  "kekuatan": 0.35, "sumber": "tetangga kondisi"})
    H.sort(key=lambda h: -h["kekuatan"])
    return {"id": e, "label": d["label"], "hipotesis": H,
            "catatan": "Penjelasan ini dibangkitkan dari aturan, data, dan tautan — bukan dari model bahasa. "
                       "Kekuatan = bobot heuristik, bukan peluang."}


def provenance(mid):
    c = db()
    r = c.execute("SELECT * FROM measurement WHERE id=?", (mid,)).fetchone()
    if not r:
        return {"error": f"measurement {mid} tidak ada"}
    d = dict(r)
    art = c.execute("SELECT * FROM artifact WHERE id=?", (d["source_artifact"],)).fetchone() if d["source_artifact"] else None
    model = None
    if d["method"].startswith("model:"):
        mc = c.execute("SELECT * FROM model_card WHERE id=?", (d["method"][6:],)).fetchone()
        model = dict(mc) if mc else None
    return {"measurement": d, "tier": TIER_ID[d["tier"]], "artifact": dict(art) if art else None,
            "model_card": model,
            "rules": [dict(x) for x in c.execute("SELECT rule_id, detail FROM rule_hit WHERE measurement=?", (mid,))]}


def coverage():
    c = db()
    rows = c.execute("""SELECT e.accession, m.tier, count(*) n FROM measurement m JOIN entity e ON e.id=m.entity
                        GROUP BY 1,2""").fetchall()
    out = defaultdict(dict)
    for acc, tier, n in rows:
        out[acc][tier] = n
    tests = dict(c.execute("SELECT accession, count(*) FROM entity WHERE kind='test' GROUP BY 1").fetchall())
    outcome = dict(c.execute("""SELECT e.accession, count(DISTINCT m.entity) FROM measurement m JOIN entity e ON e.id=m.entity
                                WHERE m.quantity IN ('outcome','ignited','burn_time','visible_flame_duration','burn_duration')
                                GROUP BY 1""").fetchall())
    return {acc: {"tests": tests.get(acc, 0), "tests_with_any_outcome": outcome.get(acc, 0), "by_tier": v}
            for acc, v in sorted(out.items())}


def search(q, k=10):
    g = sqlite3.connect(f"file:{GOLD}?mode=ro", uri=True)
    try:
        papers = g.execute("""SELECT title, page, snippet(paper_search, -1, '[', ']', '…', 12)
                              FROM paper_search WHERE paper_search MATCH ? LIMIT ?""", (q, k)).fetchall()
        cols = None
    except sqlite3.OperationalError as e:
        papers, cols = [], str(e)
    c = db()
    tests = [dict(r) for r in c.execute("""SELECT DISTINCT entity, quantity, value_text FROM measurement
                      WHERE value_text LIKE ? LIMIT ?""", (f"%{q}%", k))]
    return {"q": q, "papers": [{"title": t, "page": p, "snippet": s} for t, p, s in papers],
            "tests_text_match": tests, "error": cols}


# ------------------------------------------------------------------ server JSON
# ------------------------------------------------------------------ peristiwa server + siklus belajar (tahap D)
EVENTS = []                       # {seq, t, type, data}; dibaca klien lewat /events?since=
_EV_LOCK = threading.Lock()
_JOB = {"running": False, "pending": False, "last": None}


def push_event(kind, data=None):
    from datetime import datetime, timezone
    with _EV_LOCK:
        ev = {"seq": (EVENTS[-1]["seq"] + 1) if EVENTS else 1, "t": datetime.now(timezone.utc).isoformat(),
              "type": kind, "data": data}
        EVENTS.append(ev)
        del EVENTS[:-500]
    return ev


def events(since=0):
    with _EV_LOCK:
        return {"events": [e for e in EVENTS if e["seq"] > since], "last": EVENTS[-1]["seq"] if EVENTS else 0}


def trigger_learning(reason):
    """Jalankan learn.run di thread latar. Bila sedang jalan, tandai 'pending' supaya diulang sekali lagi
    (beberapa anotasi cepat beruntun = satu-dua putaran, bukan satu putaran per klik)."""
    if _JOB["running"]:
        _JOB["pending"] = True
        return {"queued": True}

    def work():
        import learn
        _JOB["running"] = True
        try:
            while True:
                _JOB["pending"] = False
                push_event("pipeline.started", {"reason": reason})
                steps = []

                def log(msg):
                    steps.append(msg.strip())
                    push_event("pipeline.step", {"msg": msg.strip()})

                def before(name):
                    if name == "build_brain":                    # tahan koneksi baru, lepaskan yang lama
                        _OPEN.clear()
                        close_all()

                def after(name):
                    if name == "build_brain":
                        close_all()                              # generasi naik -> semua thread buka otak baru
                        _OPEN.set()
                try:
                    res = learn.run(trigger=reason, log=log, before=before, after=after)
                finally:
                    _OPEN.set()
                close_all()
                _JOB["last"] = res
                summ = learn.history(1)[-1]["summary"] if res["ran"] else None
                push_event("pipeline.done", {**res, "summary": summ})
                if not _JOB["pending"]:
                    break
        except Exception as e:  # noqa: BLE001
            push_event("pipeline.failed", {"error": repr(e)[:500]})
        finally:
            _JOB["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"started": True}


# ---------------------------------------------------------------- mode publik (hosting)
# FIF_PUBLIC=1 -> server boleh dibuka ke internet: hanya jalur BACA + POST /ask.
# Jalur tulis (/note, /annotate, /rebuild, /feedback) ditutup: tanpa ini siapa pun bisa mengubah
# data, memicu latih ulang, atau menyuntikkan teks ke memori kasus asisten (yang masuk ke prompt).
import os  # noqa: E402
import time  # noqa: E402

PUBLIC = os.environ.get("FIF_PUBLIC", "") not in ("", "0", "false")
ASK_PER_IP = int(os.environ.get("ASK_PER_IP", "8"))            # pertanyaan per IP ...
ASK_WINDOW_S = int(os.environ.get("ASK_WINDOW_S", "600"))      # ... per jendela 10 menit
ASK_DAILY_CLAUDE = int(os.environ.get("ASK_DAILY_CLAUDE", "200"))  # panggilan Claude per hari (UTC); lebih -> luring
CORS_ORIGIN = os.environ.get("CORS_ORIGIN", "*")
_RL_LOCK = threading.Lock()
_RL = {"ip": defaultdict(list), "day": "", "claude": 0}


def _client_ip(h):
    # Di belakang proksi hosting, IP asli ada di X-Forwarded-For. Bisa dipalsukan, jadi batas per IP
    # hanya rem pertama; batas harian global (ASK_DAILY_CLAUDE) yang benar-benar membatasi biaya.
    fwd = h.headers.get("X-Forwarded-For", "")
    return (fwd.split(",")[0].strip() if fwd else h.client_address[0]) or "?"


def ask_gate(ip, mode):
    """(boleh?, mode_dipakai, catatan). Dipanggil sebelum assistant.ask."""
    now = time.time()
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    with _RL_LOCK:
        if _RL["day"] != day:
            _RL.update(day=day, claude=0)
        hits = [t for t in _RL["ip"][ip] if now - t < ASK_WINDOW_S]
        if len(hits) >= ASK_PER_IP:
            _RL["ip"][ip] = hits
            wait = int(ASK_WINDOW_S - (now - hits[0])) + 1
            return False, mode, f"terlalu banyak pertanyaan; coba lagi dalam {wait} detik"
        hits.append(now)
        _RL["ip"][ip] = hits
        if len(_RL["ip"]) > 5000:                     # jangan biarkan tabel IP tumbuh tanpa batas
            for k in [k for k, v in _RL["ip"].items() if not v or now - v[-1] > ASK_WINDOW_S]:
                del _RL["ip"][k]
        if mode != "offline":
            if _RL["claude"] >= ASK_DAILY_CLAUDE:
                return True, "offline", f"kuota harian model bahasa ({ASK_DAILY_CLAUDE}) habis; dijawab luring"
            _RL["claude"] += 1
    return True, mode, None


def clean_history(hist):
    """Riwayat dikirim klien -> batasi jumlah & panjang supaya tidak bisa membengkakkan biaya."""
    out = []
    for h in (hist if isinstance(hist, list) else [])[-6:]:
        if isinstance(h, dict) and isinstance(h.get("q"), str) and isinstance(h.get("a"), str):
            out.append({"q": h["q"][:2000], "a": h["a"][:4000]})
    return out


APP = ROOT / "app" / "nerve"
INSIGHT = ROOT / "app" / "insight"
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
        ".png": "image/png", ".svg": "image/svg+xml"}


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", CORS_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self._send(204, b"")

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = min(int(self.headers.get("Content-Length", 0)), 200000)
            data = json.loads(self.rfile.read(n) or b"{}")
            path = u.path.rstrip("/")
            if PUBLIC and path != "/ask":
                return self._send(403, json.dumps({"error": f"{path} ditutup di mode publik (FIF_PUBLIC=1)"}).encode())
            if path == "/ask":
                ok, mode, gate_note = ask_gate(_client_ip(self), str(data.get("mode", "auto")))
                if not ok:
                    return self._send(429, json.dumps({"error": gate_note, "answer": gate_note, "mode": "dibatasi",
                                                       "tool_calls": []}, ensure_ascii=False).encode("utf-8"))
                import assistant
                res = assistant.ask(str(data.get("question", ""))[:4000], clean_history(data.get("history")),
                                    data.get("state") if isinstance(data.get("state"), dict) else {}, mode)
                if gate_note:
                    res["note"] = gate_note
                push_event("assistant.answered", {"q": str(data.get("question", ""))[:200], "mode": res["mode"],
                                                  "tools": [c["name"] for c in res["tool_calls"]]})
            elif path == "/note":
                res = add_note(data.get("entity"), data.get("text", ""), data.get("author", "anonim"))
            elif path == "/annotate":                              # tahap D: putusan manusia
                import learn
                rec = learn.annotate(entity=data.get("entity"), quantity=data.get("quantity"),
                                     measurement=data.get("measurement"), artifact=data.get("artifact"),
                                     verdict=data.get("verdict"), value_text=data.get("value_text"),
                                     note=data.get("note", ""), author=data.get("author", "anonim"), source="ui")
                push_event("annotation.added", rec)
                res = {"annotation": rec, "learning": trigger_learning(f"anotasi {rec['id']}")}
            elif path == "/rebuild":
                res = trigger_learning("manual")
            elif path == "/feedback":
                import assistant
                res = assistant.feedback(data.get("question", ""), data.get("answer", ""), data.get("rating"),
                                         data.get("mode", ""), data.get("tool_calls"), data.get("note", ""))
            else:
                res = {"error": "POST: /note, /annotate, /rebuild, /ask, /feedback"}
            self._send(200, json.dumps(res, ensure_ascii=False, default=str).encode("utf-8"))
        except Exception as e:  # noqa: BLE001
            # di mode publik jangan bocorkan detail internal (path, isi exception) ke pengunjung
            self._send(500, json.dumps({"error": "galat server" if PUBLIC else repr(e)}).encode())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/app"):                            # alihkan supaya ./nerve.js -> /app/nerve.js
            self.send_response(302)
            self.send_header("Location", "/app/" + (("?" + u.query) if u.query else ""))
            self.end_headers()
            return
        if u.path == "/insight":
            self.send_response(302)
            self.send_header("Location", "/insight/")
            self.end_headers()
            return
        if u.path.startswith("/app/") or u.path.startswith("/insight/"):   # halaman statis: /app/ = mode peneliti, /insight/ = tampilan juri
            base = INSIGHT if u.path.startswith("/insight/") else APP
            rel = u.path[len("/insight/") if base is INSIGHT else len("/app/"):]
            f = (base / (rel or "index.html")).resolve()
            if base.resolve() in f.parents and f.is_file():
                return self._send(200, f.read_bytes(), MIME.get(f.suffix, "application/octet-stream"))
            return self._send(404, b"tidak ada", "text/plain")
        parts = [unquote(p) for p in u.path.strip("/").split("/", 1)]
        qs = parse_qs(u.query)
        q1 = lambda k, d=None: qs.get(k, [d])[0]
        try:
            fn = parts[0]
            arg = parts[1] if len(parts) > 1 else ""
            if fn == "events":
                res = events(int(q1("since", 0)))
            elif fn == "queue":
                import learn
                res = learn.queue(int(q1("k", 20)))
            elif fn == "history":
                import learn
                res = {"history": learn.history(int(q1("n", 20)))}
            elif fn == "pipeline":
                import learn
                res = {"steps": learn.status(), "job": {k: v for k, v in _JOB.items()}}
            elif fn == "model_cards":
                c = db()
                res = {"cards": [{**dict(r), "metrics": json.loads(r["metrics"])} for r in c.execute("SELECT * FROM model_card")]}
            elif fn == "assistant_status":
                import assistant
                ok, why = assistant.claude_available()
                res = {"claude": ok, "llm": ok, "provider": assistant.provider(), "why": why,
                       "model": assistant.llm_model(), "tools": [t["name"] for t in assistant.TOOLS]}
            elif fn == "insight_data":                              # lapis investigasi + skenario (satu muatan)
                import investigations
                res = investigations.build()
            elif fn == "investigations":
                import investigations
                res = investigations.card(arg) if arg else {"investigations": investigations.build()["investigations"]}
            elif fn == "rank":
                import investigations
                res = investigations.rank(arg or "cabin", q1("pillar"), int(q1("limit", 24)))
            elif fn == "scenario":
                import investigations
                res = investigations.evidence(arg or "surface")
            elif fn == "tests":
                res = tests(q1("acc"), q1("q"))
            elif fn == "alerts":
                res = alerts(q1("entity"), q1("min", "info"))
            elif fn == "whatif":
                res = whatif(arg or "cfig", **{k: v[0] for k, v in qs.items()})
            elif fn == "notes":
                res = notes(q1("entity"))
            elif fn == "entity":
                res = entity(arg)
            elif fn == "explain":
                res = explain(arg)
            elif fn == "relevance":
                res = relevance(arg, int(qs.get("k", [15])[0]))
            elif fn == "provenance":
                res = provenance(arg)
            elif fn == "coverage":
                res = coverage()
            elif fn == "search":
                res = search(qs.get("q", [""])[0])
            else:
                res = {"endpoints": ["/tests?acc=&q=", "/entity/<PSI-159:21106G8>", "/explain/<id>",
                                     "/relevance/<id>?k=15", "/provenance/<measurement id>", "/alerts?entity=&min=",
                                     "/whatif/cfig?config=&fuel=&o2=&x_fuel=", "/whatif/flex?fuel=&o2=&pressure_kpa=&he=",
                                     "/notes?entity=", "POST /note", "/coverage", "/search?q=", "/events?since=", "/queue?k=", "/history", "/pipeline", "/model_cards", "/assistant_status", "/insight_data", "/investigations/<PSI-69>", "/rank/<cabin|surface|suit|earth>?pillar=", "/scenario/<id>", "/insight/ (tampilan juri)", "POST /annotate", "POST /rebuild", "POST /ask", "POST /feedback", "/app/ (kerangka)"]}
            body, code = json.dumps(res, ensure_ascii=False, default=str).encode("utf-8"), 200
        except Exception as e:  # noqa: BLE001
            body, code = json.dumps({"error": "galat server" if PUBLIC else repr(e)}).encode(), 500
        self._send(code, body)

    def log_message(self, *a):
        pass


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "serve":
        # PORT/HOST dari lingkungan supaya jalan apa adanya di layanan hosting (Render, Fly, Railway, ...)
        port = int(argv[argv.index("--port") + 1]) if "--port" in argv else int(os.environ.get("PORT", 8765))
        host = argv[argv.index("--host") + 1] if "--host" in argv else os.environ.get("HOST", "127.0.0.1")
        if host not in ("127.0.0.1", "localhost") and not PUBLIC:
            print("PERINGATAN: melayani di luar localhost tanpa FIF_PUBLIC=1 — jalur tulis terbuka untuk siapa pun")
        print(f"otak melayani di http://{host}:{port}/  (mode publik: {'ya' if PUBLIC else 'tidak'}; "
              f"/ask: {ASK_PER_IP}/IP/{ASK_WINDOW_S}s, Claude {ASK_DAILY_CLAUDE}/hari)")
        ThreadingHTTPServer((host, port), H).serve_forever()
        return 0
    fn = {"entity": entity, "explain": explain, "relevance": relevance, "provenance": provenance,
          "coverage": lambda *_: coverage(), "search": search, "alerts": alerts,
          "tests": lambda *a: tests(*a), "whatif": whatif}[cmd]
    print(json.dumps(fn(*argv[1:2]) if len(argv) > 1 else fn(), ensure_ascii=False, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
