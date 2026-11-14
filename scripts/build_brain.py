#!/usr/bin/env python3
"""Tahap A + B(v1) rencana dashboard: bangun "otak" — graf pengetahuan dengan tingkat kebenaran.

Lihat docs/rencana_dashboard_cerdas.md, lapis L1 (Ingatan) dan L2 (Penalaran, deduktif).

Masukan (semuanya sudah ada; skrip ini hanya MENYATUKAN, tidak menghitung ulang analisis):
  kb/gold/freefall.sqlite                     tabel uji NASA, investigasi, berkas, paper
  analysis/telemetry/telemetry_joined.csv     hasil tambang telemetri
  analysis/telemetry/telemetry_calibrated.csv tekanan ruang terkalibrasi (kPa)
  analysis/telemetry/corridor/anomaly_scores.csv
  analysis/video_full/measurements.csv (atau measurements_verified.csv bila ada)
  analysis/ml/telemetry_predictions_gpu_w32.csv, *_results*.json, boundary/, symreg_flex.json, quantile_burn.json

Keluaran: kb/gold/brain.sqlite  (terpisah dari freefall.sqlite supaya build_kb.py tidak menghapusnya)

Tingkat kebenaran (tier) — wajib di setiap angka:
  1 nasa_table        tercatat NASA di tabel uji
  2 nasa_calibrated   sinyal mentah NASA + rumus NASA yang tervalidasi
  3 derived_auto      diturunkan skrip kita, belum dilihat manusia
  4 human_verified    derived_auto yang lolos lembar bukti
  5 paper_claim       dari teks paper, dengan halaman
  6 model_prediction  keluaran model, selalu dengan selang

  python scripts/build_brain.py
"""
import csv
import hashlib
import json
import math
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GOLD = ROOT / "kb" / "gold"
A = ROOT / "analysis"
DB = GOLD / "brain.sqlite"

SCHEMA = """
CREATE TABLE entity(id TEXT PRIMARY KEY, kind TEXT, accession TEXT, label TEXT, attrs TEXT);
CREATE TABLE artifact(id TEXT PRIMARY KEY, kind TEXT, accession TEXT, path TEXT, note TEXT);
CREATE TABLE measurement(
  id TEXT PRIMARY KEY, entity TEXT, quantity TEXT, value REAL, value_text TEXT, unit TEXT,
  lo REAL, hi REAL, unc_kind TEXT, tier TEXT, method TEXT,
  source_artifact TEXT, source_locator TEXT, flags TEXT DEFAULT '[]', verified_by TEXT);
CREATE TABLE link(src TEXT, dst TEXT, rel TEXT, weight REAL DEFAULT 1.0);
CREATE TABLE rule(id TEXT PRIMARY KEY, condition TEXT, effect TEXT, reason TEXT, origin TEXT);
CREATE TABLE rule_hit(rule_id TEXT, entity TEXT, measurement TEXT, detail TEXT);
CREATE TABLE model_card(id TEXT PRIMARY KEY, target TEXT, method TEXT, metrics TEXT, validity TEXT,
                        caveats TEXT, files TEXT);
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
CREATE INDEX m_ent ON measurement(entity);
CREATE INDEX m_q ON measurement(quantity);
CREATE INDEX l_src ON link(src);
CREATE INDEX l_dst ON link(dst);
CREATE INDEX rh_ent ON rule_hit(entity);
"""

TIERS = ["nasa_table", "nasa_calibrated", "derived_auto", "human_verified", "paper_claim", "model_prediction"]


def norm(tid):
    return re.sub(r"\s+", "", str(tid or "")).upper()


def tid(acc, test):
    return f"test:{acc}:{norm(test)}"


def fnum(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def git_sha():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, timeout=5).stdout.strip() or "tanpa-git"
    except Exception:  # noqa: BLE001
        return "tanpa-git"


class Brain:
    """Dibangun di berkas sementara lalu ditukar atomik (os.replace) — pembaca lama tidak melihat
    otak setengah jadi, dan di Windows berkas yang sedang dibaca tidak perlu dihapus."""
    def __init__(self, path):
        self.final = path
        self.tmp = path.with_name(path.stem + ".building.sqlite")
        if self.tmp.exists():
            self.tmp.unlink()
        self.c = sqlite3.connect(self.tmp)
        self.c.executescript(SCHEMA)
        self.n = defaultdict(int)

    def entity(self, id_, kind, acc, label, **attrs):
        self.c.execute("INSERT OR IGNORE INTO entity VALUES (?,?,?,?,?)",
                       (id_, kind, acc, label, json.dumps(attrs, ensure_ascii=False)))

    def artifact(self, id_, kind, acc, path, note=""):
        self.c.execute("INSERT OR IGNORE INTO artifact VALUES (?,?,?,?,?)", (id_, kind, acc, path, note))

    def m(self, entity, quantity, value=None, unit="", tier="nasa_table", method="", src="", loc="",
          text=None, lo=None, hi=None, unc="", flags=(), key=None):
        assert tier in TIERS, tier
        if value is None and text in (None, ""):
            return None
        mid = f"m:{entity[5:]}:{quantity}:{key or tier}"
        self.c.execute("INSERT OR REPLACE INTO measurement VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (mid, entity, quantity, value, text, unit, lo, hi, unc, tier, method, src, loc,
                        json.dumps(list(flags), ensure_ascii=False), None))
        self.n[tier] += 1
        return mid

    def link(self, s, d, rel, w=1.0):
        self.c.execute("INSERT INTO link VALUES (?,?,?,?)", (s, d, rel, w))


# ------------------------------------------------------------------ pemasukan
def ingest_nasa(b):
    g = sqlite3.connect(GOLD / "freefall.sqlite")
    g.row_factory = sqlite3.Row
    for r in g.execute("SELECT accession, acronym, title FROM investigations"):
        b.entity(f"inv:{r['accession']}", "investigation", r["accession"], r["acronym"] or r["accession"],
                 title=r["title"])
    for r in g.execute("SELECT * FROM tests"):
        e = tid(r["accession"], r["test_id"])
        b.entity(e, "test", r["accession"], norm(r["test_id"]), granularity=r["granularity"],
                 fuel=r["fuel"], configuration=r["configuration"], fuel_phase=r["fuel_phase"],
                 table=r["table_name"], date=r["date"])
        b.link(e, f"inv:{r['accession']}", "part_of")
        src, loc = r["source_file"], f"baris {r['source_row']}"
        meth = "tabel uji NASA (PSI), dirapikan build_kb.py"
        for q, col, unit in (("o2_mole_frac", "o2_mole_frac", "fraksi mol"),
                             ("o2_final_mole_frac", "o2_final_mole_frac", "fraksi mol"),
                             ("pressure", "pressure_kpa", "kPa"), ("flow", "flow_cm_s", "cm/s"),
                             ("burn_time", "burn_time_s", "s"), ("size", "size_mm", "mm")):
            b.m(e, q, fnum(r[col]), unit, "nasa_table", meth, src, loc)
        for q, col in (("ignited", "ignited"), ("outcome", "outcome"), ("fuel", "fuel"),
                       ("configuration", "configuration"), ("operator_note", "notes")):
            if r[col]:
                b.m(e, q, None, "", "nasa_table", meth, src, loc, text=str(r[col]))
        if r["metric_name"] and fnum(r["metric_value"]) is not None:
            b.m(e, r["metric_name"], fnum(r["metric_value"]), r["metric_unit"] or "", "nasa_table", meth, src, loc)
    for r in g.execute("SELECT * FROM papers"):
        cols = r.keys()
        pid = f"paper:ntrs:{r['id'] if 'id' in cols else r[cols[0]]}"
        b.entity(pid, "paper", "", (r["title"] if "title" in cols else "")[:200],
                 tags=(r["tags"] if "tags" in cols else ""))
    g.close()


def ingest_telemetry(b, sha):
    tel = list(csv.DictReader(open(A / "telemetry" / "telemetry_joined.csv", encoding="utf-8")))
    cal = {r["file"]: r for r in csv.DictReader(open(A / "telemetry" / "telemetry_calibrated.csv", encoding="utf-8"))}
    an = {(r["accession"], r["test_point"]): r for r in
          csv.DictReader(open(A / "telemetry" / "corridor" / "anomaly_scores.csv", encoding="utf-8"))}
    meth_tel = f"telemetry_mine.py@{sha}: ambang termokopel burner 0,0006 V (validasi 93,8 % vs kolom ignited NASA)"
    meth_cal = (f"telemetry_calibrate.py@{sha}: PTA3, kPa = (V-0,5)*145,038/4*6,8948; "
                "tervalidasi vs tabel NASA, MAE 2,2 kPa (PSI-10), 6,7 kPa (PSI-159)")
    from collections import Counter
    dup = Counter((t["accession"], t["test_point"]) for t in tel)
    seen = set()
    for t in tel:
        acc = t["accession"]
        e = tid(acc, t["test_point"])
        # satu uji bisa punya dua berkas telemetri (3 kasus): berkas kedua dapat kunci sendiri
        sfx = "" if e not in seen else "_" + hashlib.sha1(t["file"].encode()).hexdigest()[:6]
        seen.add(e)
        dflag = ["rekaman_ganda"] if dup[(acc, t["test_point"])] > 1 else []
        if t["match"] == "tidak ada":
            b.entity(e, "test", acc, norm(t["test_point"]), granularity="telemetri_saja",
                     note="tidak ada di tabel uji NASA")
            b.link(e, f"inv:{acc}", "part_of")
        if t["match"] == "hari":
            b.entity(e, "test", acc, norm(t["test_point"]), granularity="telemetri_saja",
                     note="tabel NASA hanya punya ringkasan harian")
            b.link(e, f"inv:{acc}", "part_of")
            b.link(e, tid(acc, t["table_row"]), "summarized_by")
        art = f"art:telemetry:{t['file']}"
        b.artifact(art, "telemetry_csv", acc, f"kb/raw/psi/files/{acc}/Raw Data/{t['file']}")
        b.link(e, art, "has_artifact")
        flags = []
        tc = fnum(t["tc_burner_rise_v"])
        b.m(e, "ignited", None, "", "derived_auto", meth_tel, art, "", text=t["ignited_tel"], key="tel" + sfx, flags=dflag)
        b.m(e, "tc_burner_rise", tc, "V (mentah, BUKAN suhu)", "derived_auto", meth_tel, art, "", key="tel" + sfx,
            flags=["bukan_suhu"] + dflag)
        b.m(e, "burn_duration", fnum(t["burn_duration_s"]), "s", "derived_auto", meth_tel, art, "",
            key="tel" + sfx, flags=["jeda_termal_cenderung_berlebih"] + dflag)
        b.m(e, "t_ignite", fnum(t["t_ignite_s"]), "s sejak awal rekaman", "derived_auto", meth_tel, art, "", key="tel" + sfx)
        b.m(e, "fuel_flow_signal", fnum(t["fuel_flow_mean"]), "V (mentah)", "derived_auto", meth_tel, art, "", key="tel" + sfx)
        c = cal.get(t["file"])
        if c:
            p0, p1, dp = fnum(c.get("PTA3_kpa_start")), fnum(c.get("PTA3_kpa_end")), fnum(c.get("PTA3_kpa_max_rise"))
            b.m(e, "chamber_pressure_start", p0, "kPa", "nasa_calibrated", meth_cal, art, "2 s pertama", key="cal" + sfx)
            b.m(e, "chamber_pressure_end", p1, "kPa", "nasa_calibrated", meth_cal, art, "2 s terakhir", key="cal" + sfx)
            b.m(e, "chamber_pressure_max_rise", dp, "kPa", "nasa_calibrated", meth_cal, art, "", key="cal" + sfx)
        a = an.get((acc, t["test_point"]))
        if a and a["anomaly"]:
            b.m(e, "corridor_anomaly", fnum(a["anomaly"]), "skor |z| robust", "derived_auto",
                f"telemetry_corridor.py@{sha}: leave-one-out vs koridor {a['group']}", art, a["group"], key="cor",
                flags=(["keluar_koridor"] if a["outlier"] == "True" else []))


def ingest_video(b, sha):
    # Selalu turunan otomatis; putusan manusia (annotations.jsonl) yang menaikkan tier — lihat learn.py
    src, tier = A / "video_full" / "measurements.csv", "derived_auto"
    for r in csv.DictReader(open(src, encoding="utf-8")):
        e = tid(r["accession"], r["test_id"])
        art = f"art:video:{r['source_video']}"
        b.artifact(art, "video", r["accession"], f"kb/raw/psi/files/{r['accession']}/Raw Data/{r['source_video']}")
        b.link(e, art, "has_artifact")
        flags = [] if tier == "human_verified" else ["belum_diverifikasi_manusia"]
        b.m(e, "visible_flame_duration", fnum(r["burn_duration_s"]), "s", tier,
            f"video_analyze.py@{sha}: ambang kecerahan + komponen terhubung", art,
            f"episode {r['episode']}, {r['t_start_s']}–{r['t_end_s']} s",
            # sidik video di kunci: satu uji bisa punya beberapa video (mis. T16 asli + 'shifted');
            # tanpa ini episode video kedua menimpa yang pertama (27 episode hilang sebelum diperbaiki)
            key=f"vid{hashlib.sha1(r['source_video'].encode()).hexdigest()[:6]}_{r['episode']}", flags=flags)


def ingest_models(b, sha):
    g = A / "ml" / "telemetry_gb_predictions.csv"           # dilatih ulang dari label NASA + manusia (learn.py)
    gc = A / "ml" / "telemetry_gb_card.json"
    if g.exists():
        for r in csv.DictReader(open(g, encoding="utf-8")):
            if r["label_source"] == "nasa":
                continue                                    # sudah ada label NASA; prediksi tak perlu ditampilkan
            e = tid(r["accession"], r["test_point"])
            b.m(e, "p_ignite", fnum(r["p_ignite"]), "peluang", "model_prediction", "model:gb_telemetry_labels",
                "", f"label: {r['label_source'] or 'tidak ada'}", key="gb",
                flags=["dilatih_dengan_label_manusia"] if r["label_source"] == "manusia" else [])
    if gc.exists():
        card = json.loads(gc.read_text(encoding="utf-8"))
        b.c.execute("INSERT OR REPLACE INTO model_card VALUES (?,?,?,?,?,?,?)",
                    ("gb_telemetry_labels", "menyala dari telemetri (latih ulang otomatis)",
                     "HistGradientBoosting pada fitur ringkasan 18 kanal; label NASA + label manusia",
                     json.dumps({**card["metrics_vs_nasa"], "n_label_manusia": card["n_label_manusia"]}, ensure_ascii=False),
                     json.dumps({"validasi": card["validasi"]}, ensure_ascii=False),
                     json.dumps(["dilatih ulang setiap ada putusan manusia baru (scripts/learn.py)"], ensure_ascii=False),
                     json.dumps(["analysis/ml/telemetry_gb_predictions.csv"])))
    p = A / "ml" / "telemetry_predictions_gpu_w32.csv"
    if p.exists():
        for r in csv.DictReader(open(p, encoding="utf-8")):
            e = tid(r["accession"], r["test_point"])
            mu, sd = fnum(r["p_ignite"]), fnum(r["p_ignite_sd"]) or 0.0
            b.m(e, "p_ignite", mu, "peluang", "model_prediction", "model:cnn_telemetry_w32", "", "",
                lo=max(0.0, mu - 2 * sd), hi=min(1.0, mu + 2 * sd), unc="±2 sd antar-model ansambel",
                key="cnn", flags=["ekstrapolasi_ke_investigasi_lain"])
    cards = []
    dl = A / "ml" / "telemetry_dl_results_gpu_w32.json"
    if dl.exists():
        r = json.loads(dl.read_text(encoding="utf-8"))
        cards.append(("cnn_telemetry_w32", "menyala / padam-sendiri / waktu bakar dari telemetri 18 kanal",
                      "ResNet-1D, ansambel 5 lipatan x 5 benih, GPU RTX 3080", r.get("CNN"),
                      {"dilatih_pada": "PSI-159 CFI-G (320 uji berlabel)", "validasi": "GroupKFold per hari"},
                      ["pra-latih swa-awasan TIDAK membantu (diuji 3 kali)",
                       "PSI-10/PSI-23 = ekstrapolasi ke investigasi lain"], ["analysis/ml/telemetry_cnn_ensemble_gpu_w32.pt"]))
    bd = A / "ml" / "boundary" / "boundary.json"
    if bd.exists():
        r = json.loads(bd.read_text(encoding="utf-8"))
        for k, v in r.items():
            cards.append((f"gp_boundary_{k}", v["what"], "proses Gaussian klasifikasi + fungsi-U (active learning)",
                          v["cv_per_hari"], {"fitur": v["features"]},
                          ["kandidat uji hanya di sekitar kondisi yang pernah diuji"], ["analysis/ml/boundary/boundary.json"]))
    sr = A / "ml" / "symreg_flex.json"
    if sr.exists():
        r = json.loads(sr.read_text(encoding="utf-8"))
        cards.append(("symreg_flex_K", "laju bakar droplet K (mm²/s)", "regresi simbolik, pencarian menyeluruh 1-SE",
                      {"formula": r["formula"], "rmse_per_hari": r["cv_rmse_per_hari"], "baseline": r["baseline_mean_rmse"]},
                      {"rentang": "kondisi FLEX yang diuji"}, ["empiris, bukan hukum universal"], ["analysis/ml/symreg_flex.json"]))
    qb = A / "ml" / "quantile_burn.json"
    if qb.exists():
        r = json.loads(qb.read_text(encoding="utf-8"))
        cards.append(("quantile_burn_cfig", "waktu bakar CFI-G sebagai rentang P10–P90",
                      "gradient boosting kuantil + conformal per hari", r.get("model_conformal"),
                      {"n": r["n"], "hari": r["days"]}, ["bimodal: padam sendiri vs dihentikan aliran"],
                      ["analysis/ml/quantile_burn.json"]))
    for c in cards:
        b.c.execute("INSERT OR REPLACE INTO model_card VALUES (?,?,?,?,?,?,?)",
                    (c[0], c[1], c[2], json.dumps(c[3], ensure_ascii=False), json.dumps(c[4], ensure_ascii=False),
                     json.dumps(c[5], ensure_ascii=False), json.dumps(c[6])))


SAFFIRE_TEST = {"PSI-98": "S1", "PSI-100": "S1"}     # S1 = uji concurrent (rekaman S1C1/S1C2)
PAPER_SPREAD = "Flame spread: Effects of microgravity and scale"


def ingest_saffire(b, sha):
    """Laju rambat Saffire dari citra (scripts/saffire_spread.py) + angka pembanding dari paper (tier paper_claim)."""
    p = A / "saffire" / "spread_rates.json"
    if not p.exists():
        return
    for s in json.loads(p.read_text(encoding="utf-8")):
        e = tid(s["acc"], SAFFIRE_TEST[s["acc"]])
        cam = s["id"].split("_")[-1]
        for z in s["zip"].split("; "):
            art = f"art:images:{z}"
            b.artifact(art, "image_series", s["acc"], f"kb/raw/psi/files/{s['acc']}/Raw Data/{z}",
                       "deret citra terpetakan NASA (Mapped)")
            b.link(e, art, "has_artifact")
        meth = (f"saffire_spread.py@{sha}: Theil-Sen posisi vs waktu (10-90 % lintasan), bootstrap blok; "
                f"skala {s['scale_source']}")
        for q, key in (("flame_spread_rate", "flame_rate"), ("char_front_rate", "char_rate")):
            r = s.get(key)
            if not r:
                continue
            flags = ["belum_diverifikasi_manusia"] + ([] if r["quality"] == "lolos" else ["gagal_gerbang_mutu"])
            b.m(e, q, r["mm_per_s"], "mm/s", "derived_auto", meth, f"art:images:{s['zip'].split('; ')[0]}",
                f"{s['label']}; {r['n']} frame; t {r['t_range_s'][0]}-{r['t_range_s'][1]} s; resid {r['resid_mm_rms']} mm",
                lo=r["ci95_mm_per_s"][0], hi=r["ci95_mm_per_s"][1], unc="ci95 bootstrap blok waktu",
                key=f"img_{cam}", flags=flags)
        # angka publikasi: laju concurrent (hlm. 13) dan aliran masuk terowongan (hlm. 6)
        b.m(e, "flame_spread_rate", s["published_mm_s"], "mm/s", "paper_claim",
            f"{PAPER_SPREAD} (papers_doi), laju rambat concurrent, sampel 40,6 cm", "", "hlm. 13", key="paper")
        b.m(e, "flow_speed_paper", s["flow_cm_s"], "cm/s", "paper_claim",
            f"{PAPER_SPREAD} (papers_doi), aliran masuk terowongan", "", "hlm. 6", key="paper")


def build_links(b):
    """Tautan antar-uji: hari sama, seri sama (hari + huruf)."""
    rows = b.c.execute("SELECT id, accession, label FROM entity WHERE kind='test'").fetchall()
    by_day, by_series = defaultdict(list), defaultdict(list)
    for e, acc, lab in rows:
        m = re.match(r"(\d{5})([A-Z])(\d+)", lab)
        if m:
            by_day[(acc, m.group(1))].append(e)
            by_series[(acc, m.group(1) + m.group(2))].append((int(m.group(3)), e))
    for grp in by_series.values():
        grp.sort()
        for (n1, e1), (n2, e2) in zip(grp, grp[1:]):
            b.link(e1, e2, "next_in_series", 1.0)
            b.link(e2, e1, "prev_in_series", 1.0)
    for grp in by_day.values():
        if len(grp) <= 60:
            for i, e1 in enumerate(grp):
                for e2 in grp[i + 1:]:
                    b.link(e1, e2, "same_day", 0.4)
                    b.link(e2, e1, "same_day", 0.4)


# ------------------------------------------------------------------ aturan (deduktif)
RULES = []


def rule(id_, condition, effect, reason, origin):
    def deco(fn):
        RULES.append((id_, condition, effect, reason, origin, fn))
        return fn
    return deco


def flag(b, mid, f):
    cur = json.loads(b.c.execute("SELECT flags FROM measurement WHERE id=?", (mid,)).fetchone()[0])
    if f not in cur:
        cur.append(f)
        b.c.execute("UPDATE measurement SET flags=? WHERE id=?", (json.dumps(cur, ensure_ascii=False), mid))


@rule("R1_sinyal_lemah", "telemetri menyala DAN kenaikan termokopel < 0,002 V",
      "tandai 'sinyal_lemah' (tetap ditampilkan)",
      "117 uji; dari 35 berlabel NASA, 31 memang menyala (89 %) — nyala dingin wajar lemah",
      "analysis/telemetry/README.md")
def r1(b):
    out = []
    for e, mid, v in b.c.execute("""SELECT m.entity, m.id, m.value FROM measurement m
            WHERE m.quantity='tc_burner_rise' AND m.value < 0.002 AND EXISTS (
              SELECT 1 FROM measurement x WHERE x.entity=m.entity AND x.quantity='ignited'
              AND x.tier='derived_auto' AND x.value_text='ya')""").fetchall():
        flag(b, mid, "sinyal_lemah")
        out.append((e, mid, f"kenaikan {v:.5f} V"))
    return out


@rule("R2_percobaan_ulang", "uji hanya di telemetri, tidak menyala, DAN uji berikutnya di seri yang sama ada",
      "tandai 'kemungkinan_percobaan_ulang'",
      "catatan NASA 21242 F2: 'F1 was aborted, and F2 did not ignite' — percobaan batal tidak diberi baris",
      "analysis/telemetry/README.md")
def r2(b):
    out = []
    for e, in b.c.execute("""SELECT e.id FROM entity e WHERE e.kind='test'
            AND json_extract(e.attrs,'$.granularity')='telemetri_saja'
            AND json_extract(e.attrs,'$.note')='tidak ada di tabel uji NASA'""").fetchall():
        ig = b.c.execute("SELECT value_text, id FROM measurement WHERE entity=? AND quantity='ignited' AND tier='derived_auto'",
                         (e,)).fetchone()
        nxt = b.c.execute("SELECT dst FROM link WHERE src=? AND rel='next_in_series'", (e,)).fetchone()
        if ig and ig[0] == "tidak" and nxt:
            flag(b, ig[1], "kemungkinan_percobaan_ulang")
            out.append((e, ig[1], f"dilanjutkan oleh {nxt[0].split(':')[-1]}"))
    return out


@rule("R3_tanpa_konsumsi_o2", "uji hanya di telemetri dinyatakan menyala, TAPI O2 akhir uji sebelumnya = O2 awal uji "
      "sesudahnya di tabel NASA (persis)", "tandai 'kemungkinan_positif_palsu'",
      "21106 G8: G7 akhir = G9 awal = 0,207473561; uji normal yang menyala menurunkan O2 median 0,0018",
      "analysis/telemetry/README.md")
def r3(b):
    out = []
    for e, in b.c.execute("""SELECT e.id FROM entity e WHERE e.kind='test' AND e.accession='PSI-159'
            AND json_extract(e.attrs,'$.note')='tidak ada di tabel uji NASA'""").fetchall():
        ig = b.c.execute("SELECT value_text, id FROM measurement WHERE entity=? AND quantity='ignited' AND tier='derived_auto'",
                         (e,)).fetchone()
        if not ig or ig[0] != "ya":
            continue
        prev = b.c.execute("SELECT dst FROM link WHERE src=? AND rel='prev_in_series'", (e,)).fetchone()
        nxt = b.c.execute("SELECT dst FROM link WHERE src=? AND rel='next_in_series'", (e,)).fetchone()
        if not (prev and nxt):
            continue
        fin = b.c.execute("SELECT value FROM measurement WHERE entity=? AND quantity='o2_final_mole_frac' AND tier='nasa_table'",
                          (prev[0],)).fetchone()
        ini = b.c.execute("SELECT value FROM measurement WHERE entity=? AND quantity='o2_mole_frac' AND tier='nasa_table'",
                          (nxt[0],)).fetchone()
        if fin and ini and fin[0] is not None and abs(fin[0] - ini[0]) < 1e-9:
            flag(b, ig[1], "kemungkinan_positif_palsu")
            out.append((e, ig[1], f"O2 {prev[0].split(':')[-1]} akhir = {nxt[0].split(':')[-1]} awal = {fin[0]}"))
    return out


@rule("R4_kanal_aliran_inverse", "sinyal aliran bahan bakar pada konfigurasi inverse",
      "tandai 'kanal_tak_informatif' — jangan dipakai sebagai bukti tidak ada api",
      "kanal ≈ 0 pada 119/119 PSI-10 dan 129/129 PSI-159 inverse, termasuk 126 uji yang menyala",
      "analysis/telemetry/README.md")
def r4(b):
    out = []
    for e, mid in b.c.execute("""SELECT m.entity, m.id FROM measurement m JOIN measurement c
            ON c.entity=m.entity AND c.quantity='configuration' AND lower(c.value_text) LIKE 'inverse%'
            WHERE m.quantity='fuel_flow_signal'""").fetchall():
        flag(b, mid, "kanal_tak_informatif")
        out.append((e, mid, "konfigurasi inverse"))
    return out


@rule("R5_ada_catatan_operator", "uji punya catatan operator NASA",
      "tautkan sebagai bukti untuk penjelasan 'kenapa'",
      "uji berkomentar punya skor anomali koridor lebih tinggi (p permutasi 0,001)", "analysis/stats/uq_report.md")
def r5(b):
    return [(e, mid, t[:80]) for e, mid, t in b.c.execute(
        "SELECT entity, id, value_text FROM measurement WHERE quantity='operator_note'").fetchall()]


@rule("R6_beda_sumber", "nilai yang sama dari tabel NASA dan paper berbeda lebih dari 10 %",
      "tandai 'sumber_bertentangan' pada kedua angka; tampilkan sebagai peringatan",
      "Saffire-III: tabel NASA mencatat aliran 30 cm/s, paper mencatat 25 cm/s",
      "analysis/saffire/, Flame spread: Effects of microgravity and scale hlm. 6")
def r6(b):
    out = []
    for e, mt, vt, mp, vp in b.c.execute("""SELECT t.entity, t.id, t.value, p.id, p.value FROM measurement t
            JOIN measurement p ON p.entity=t.entity AND p.quantity='flow_speed_paper'
            WHERE t.quantity='flow' AND t.tier='nasa_table'""").fetchall():
        if vt and vp and abs(vt - vp) / vp > 0.10:
            flag(b, mt, "sumber_bertentangan")
            flag(b, mp, "sumber_bertentangan")
            out.append((e, mt, f"aliran: tabel NASA {vt:g} cm/s vs paper {vp:g} cm/s"))
    return out


def run_rules(b):
    for id_, cond, eff, why, origin, fn in RULES:
        b.c.execute("INSERT INTO rule VALUES (?,?,?,?,?)", (id_, cond, eff, why, origin))
        hits = fn(b)
        b.c.executemany("INSERT INTO rule_hit VALUES (?,?,?,?)", [(id_, e, m, d) for e, m, d in hits])
        print(f"  {id_:28s} {len(hits):4d} kena")


def main():
    sha = git_sha()
    b = Brain(DB)
    print("Memasukkan tabel NASA ...");      ingest_nasa(b)
    print("Memasukkan telemetri ...");       ingest_telemetry(b, sha)
    print("Memasukkan video ...");           ingest_video(b, sha)
    print("Memasukkan model ...");           ingest_models(b, sha)
    print("Memasukkan Saffire ...");         ingest_saffire(b, sha)
    print("Membangun tautan ...");           build_links(b)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import learn                                          # noqa: E402  (log anotasi = sumber kebenaran manusia)
    st = learn.apply_annotations(b.c)
    print("Menerapkan anotasi manusia:", st)
    b.c.execute("INSERT INTO meta VALUES ('annotations', ?)", (json.dumps(st),))
    print("Menjalankan aturan:");            run_rules(b)
    b.c.execute("INSERT INTO meta VALUES ('built', ?)", (datetime.now(timezone.utc).isoformat(),))
    b.c.execute("INSERT INTO meta VALUES ('code', ?)", (sha,))
    b.c.commit()
    b.c.close()
    import os
    import time as _t
    for i in range(20):                                 # pembaca bisa sedang memegang berkas lama
        try:
            os.replace(b.tmp, b.final)
            break
        except PermissionError:
            if i == 19:
                raise SystemExit("brain.sqlite masih dipegang proses lain (server?). "
                                 "Picu pembangunan ulang lewat server: POST /rebuild")
            _t.sleep(0.5)
    b.c = sqlite3.connect(b.final)
    q = lambda s: b.c.execute(s).fetchone()[0]
    print(f"\nEntitas {q('SELECT count(*) FROM entity')}, measurement {q('SELECT count(*) FROM measurement')}, "
          f"tautan {q('SELECT count(*) FROM link')}, kartu model {q('SELECT count(*) FROM model_card')}")
    counts = dict(b.c.execute("SELECT tier, count(*) FROM measurement GROUP BY 1").fetchall())
    for t in TIERS:
        print(f"  {t:18s} {counts.get(t, 0)}")
    print("Ditulis:", DB)
    return 0


if __name__ == "__main__":
    sys.exit(main())
