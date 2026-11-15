#!/usr/bin/env python3
"""Lapis investigasi + lensa skenario: merangkum, MEMERINGKAT, dan menafsirkan investigasi PSI.

Tantangan "Flame in Freefall" meminta dashboard yang bekerja pada tingkat INVESTIGASI dan pada
kebutuhan keselamatan api habitat berawak. Modul ini menambahkan tiga hal di atas otak yang ada:

1. KARTU INVESTIGASI (24 buah): tujuan, pilar keselamatan (prevention/detection/suppression),
   bahan bakar & geometri sampel, rentang kondisi, variabel yang divariasikan, sensor/kolom ukur,
   perangkat (CIR-ACME, CIR-MDCA, MSG, Saffire), kedalaman bukti, dan angka baru dari analisis kita.
2. LENSA SKENARIO: atmosfer habitat (kabin, pangkalan Bulan/Mars & rover, baju antariksa, Bumi).
   Untuk tiap skenario: peringkat investigasi dengan skor yang terurai dan bisa dijelaskan,
   uji-uji nyata di dalam pita atmosfer itu, prediksi model di titik tengahnya, dan celah data.
3. JAWABAN TINGKAT INVESTIGASI untuk asisten (Inggris/Indonesia), semuanya dari angka alat.

Skor relevansi = w_d * keterkaitan langsung + w_c * kedekatan kondisi + w_e * kedalaman bukti.
  keterkaitan langsung : rubrik dari teks tantangan + sub-area PSI (lihat DIRECT; alasan ikut ditampilkan)
  kedekatan kondisi    : banyaknya uji di dalam pita O2 x tekanan skenario (jenuh pada 10 uji);
                         bila tekanan tidak dicatat nilainya dikali 0,5; bila hanya daftar kampanye 0,3
  kedalaman bukti      : log jumlah angka HASIL (menyala, akhir uji, waktu/laju bakar, laju rambat, ...)
Bobot bawaan 0,40 / 0,35 / 0,25; komponen diekspor terpisah supaya antarmuka bisa menimbang ulang.

Tidak ada model bahasa di sini. Kalimat tafsir dirakit dari angka, dan asal tiap klasifikasi disebut.

  py -3 scripts/investigations.py export      # -> app/insight/data.json (untuk hosting statis)
  py -3 scripts/investigations.py rank surface
  py -3 scripts/investigations.py card PSI-69
"""
import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbpaths import gold_db  # noqa: E402
GOLD = gold_db()
BRAIN = ROOT / "kb" / "gold" / "brain.sqlite"
OUT = ROOT / "app" / "insight" / "data.json"
CHALLENGE = "Space Apps 2026 challenge statement 'Flame in Freefall'"

PILLARS = {
    "prevention": "Prevention: material flammability and ignition limits",
    "detection": "Detection: smoke and aerosol sensing",
    "suppression": "Suppression: extinguishing agents and limits",
    "fundamentals": "Fundamentals: flame physics that models are validated against",
}

# Keterkaitan langsung dengan keselamatan api. Sumber tiap nilai ditulis, supaya bisa diperdebatkan.
#   1.0  disebut teks tantangan sebagai studi keselamatan api (prevention/detection/suppression)
#   0.8  disebut teks tantangan sebagai studi terkait langsung
#   0.6  disebut teks tantangan untuk data khusus (O2 tertinggi, tiruan gravitasi parsial), atau
#        sub-area PSI-nya 'Spacecraft Fire Safety' / 'Fire Safety'
#   0.4  investigasi pembakaran lain: "still relevant to fire safety, just not as strongly or directly"
DIRECT = {
    "PSI-25": (1.0, ["prevention", "suppression"], f"named in the {CHALLENGE} as a solid-material flammability study"),
    "PSI-26": (1.0, ["prevention", "suppression"], f"named in the {CHALLENGE} as a solid-material flammability study"),
    "PSI-98": (1.0, ["prevention"], f"named in the {CHALLENGE} as a large-scale material flammability demonstration"),
    "PSI-99": (1.0, ["prevention"], f"named in the {CHALLENGE} as a large-scale material flammability demonstration"),
    "PSI-100": (1.0, ["prevention"], f"named in the {CHALLENGE} as a large-scale material flammability demonstration"),
    "PSI-101": (1.0, ["detection"], f"named in the {CHALLENGE} as a fire-detection (smoke aerosol) study"),
    "PSI-102": (1.0, ["detection"], f"named in the {CHALLENGE} as a fire-detection (smoke aerosol) study"),
    "PSI-69": (1.0, ["suppression"], f"named in the {CHALLENGE} as the suppression study (CO2 and helium dilution)"),
    "PSI-20": (0.8, ["prevention"], f"named in the {CHALLENGE}: gaseous burner that emulates material flammability in still atmospheres"),
    "PSI-47": (0.8, ["detection"], f"named in the {CHALLENGE}: same aerosol instrument as SAME, used for dust"),
    "PSI-159": (0.6, ["fundamentals", "prevention"], f"named in the {CHALLENGE} for the highest-oxygen microgravity tests (up to 85% O2 from the burner)"),
    "PSI-22": (0.6, ["fundamentals"], f"named in the {CHALLENGE}: electric field mimics partial gravity"),
    "PSI-68": (0.6, ["suppression", "fundamentals"], "PSI sub-area 'Spacecraft Fire Safety'; continuation of FLEX"),
    "PSI-107": (0.6, ["detection", "fundamentals"], "PSI sub-area 'Fire Safety'; smoke-point (soot) limits in co-flow"),
    "PSI-62": (0.6, ["prevention"], "PSI sub-area 'Spacecraft Fire Safety'; ground modelling of flame spread against BASS"),
    "PSI-142": (0.6, ["fundamentals"], "PSI sub-area 'Spacecraft Fire Safety'; ground study of cool-flame extinction"),
    "PSI-115": (0.6, ["detection"], "ground modelling of smoke generation using SAME data"),
    "PSI-117": (0.6, ["suppression", "fundamentals"], "ground CFD of cool-flame extinction using FLEX data"),
}
DEFAULT_DIRECT = (0.4, ["fundamentals"], f"other combustion investigation; the {CHALLENGE} calls these 'still relevant to fire safety, just not as strongly or directly'")

# Kelompok perangkat menurut teks tantangan (bagian Hardware) + metadata PSI.
FACILITY = {
    "PSI-10": "CIR · ACME insert", "PSI-20": "CIR · ACME insert", "PSI-21": "CIR · ACME insert",
    "PSI-22": "CIR · ACME insert", "PSI-23": "CIR · ACME insert", "PSI-159": "CIR · ACME insert",
    "PSI-69": "CIR · MDCA (droplets)", "PSI-68": "CIR · MDCA (droplets)", "PSI-39": "CIR · MDCA (droplets)",
    "PSI-25": "MSG · SPICE flow duct", "PSI-26": "MSG · SPICE flow duct", "PSI-107": "MSG · SPICE flow duct",
    "PSI-106": "MSG · SPICE flow duct",
    "PSI-98": "Saffire enclosure in Cygnus", "PSI-99": "Saffire enclosure in Cygnus", "PSI-100": "Saffire enclosure in Cygnus",
    "PSI-101": "Smoke aerosol hardware (SAME)", "PSI-102": "Smoke aerosol hardware (SAME)", "PSI-47": "TSI P-Trak particle counter",
}
SHORT = {"PSI-60": "SPICE data analysis (ground)", "PSI-62": "Flame-spread modelling vs BASS (ground)",
         "PSI-115": "SAME smoke modelling (ground)", "PSI-117": "Cool-flame CFD from FLEX (ground)",
         "PSI-142": "Cool-flame counterflow study (ground)"}

SCENARIOS = [
    {"id": "cabin", "name": "Spacecraft / space station cabin", "short": "Cabin",
     "o2": [0.19, 0.235], "p_kpa": [90.0, 110.0], "center": {"o2": 0.21, "p_kpa": 101.3},
     "gravity": "microgravity", "gravity_data": "matches: all PSI flight data are microgravity",
     "basis": "Sea-level air (about 21% O2 at 14.7 psi = 101.3 kPa), as on the ISS."},
    {"id": "surface", "name": "Moon / Mars base and pressurized rover", "short": "Surface base",
     "o2": [0.28, 0.40], "p_kpa": [50.0, 72.0], "center": {"o2": 0.30, "p_kpa": 70.3},
     "gravity": "partial gravity (Moon 1/6 g, Mars 3/8 g)",
     "gravity_data": "no partial-gravity combustion data in PSI yet; microgravity and normal gravity can only bound it",
     "basis": f"{CHALLENGE}: O2 will likely be 30% or greater at 10.2 psi (70.3 kPa) or less. Band shown: 28-40% O2, 50-72 kPa (our tolerance)."},
    {"id": "suit", "name": "Spacesuit", "short": "Spacesuit",
     "o2": [0.85, 1.0], "p_kpa": [20.0, 40.0], "center": {"o2": 1.0, "p_kpa": 29.6},
     "gravity": "microgravity or partial gravity", "gravity_data": "microgravity data only",
     "basis": f"{CHALLENGE}: suits are filled with 100% O2 at 4.3 psi (29.6 kPa)."},
    {"id": "earth", "name": "Earth (terrestrial fire safety)", "short": "Earth",
     "o2": [0.19, 0.235], "p_kpa": [90.0, 110.0], "center": {"o2": 0.21, "p_kpa": 101.3},
     "gravity": "normal gravity (1 g)",
     "gravity_data": "flight data are microgravity; they isolate diffusion and radiation effects that buoyancy hides on Earth",
     "basis": "Sea-level air. Relevance is through technology transfer and model validation, not matching gravity."},
]
WEIGHTS = {"direct": 0.40, "conditions": 0.35, "evidence": 0.25}
RESULT_Q = {"ignited", "outcome", "burn_time", "burn_duration", "burning_rate", "flame_spread_rate", "char_front_rate",
            "visible_flame_duration", "spread_rate", "net_aging_time", "weight_loss_rate", "t_ignite"}
EARTH = [  # hanya yang tertulis di teks tantangan
    {"title": "Fine-water-mist extinguishers", "text": "Developed for use on the ISS, with practical applications on Earth.", "pillar": "suppression"},
    {"title": "Smoke detection", "text": "NASA technology has led to improvements in terrestrial smoke detection.", "pillar": "detection"},
    {"title": "Firefighter gear", "text": "Protective clothing and air tanks improved through NASA technology.", "pillar": "prevention"},
]
PARTIAL_G = [
    "There is currently no partial-gravity combustion data in PSI.",
    "Expected later: the Lunar-g Combustion Investigation (LUCI) and Flammability of Materials on the Moon (FM2).",
    "ACME E-FIELD Flames mimicked partial gravity through the effect of an electric field on flame ions.",
    "Microgravity and normal-gravity results can bound what happens at intermediate gravity.",
]

SUGGESTED = ["Which investigations matter most for a Moon base?", "What do we know about fire safety in a lunar rover?",
             "Compare FLEX and BASS-II", "Tell me about Saffire-III",
             "Which investigations matter for detection in a spacecraft cabin?", "What do we know about a spacesuit atmosphere?"]

_CACHE = {"key": None, "data": None}


def _num_list(text):
    return [float(x) for x in re.findall(r"\d+(?:\.\d+)?", str(text or ""))]


def _campaign_o2(raw):
    """O2 yang hanya tertulis sebagai daftar/rentang di baris ringkasan (mis. BRE '21; 26.5; 40')."""
    out = []
    for k, v in raw.items():
        if re.search(r"oxygen|\bXO2\b|percent o2", k, re.I) and v:
            for x in _num_list(v):
                out.append(x / 100 if x > 1 else x)
    return [x for x in out if 0.05 <= x <= 1.0]


def _campaign_p(raw):
    out = []
    for k, v in raw.items():
        if re.search(r"pressure", k, re.I) and v:
            unit = 101.325 if re.search(r"atm", k + str(v), re.I) else (100.0 if re.search(r"bar", k + str(v), re.I) else None)
            if unit:
                out += [x * unit for x in _num_list(v) if x < 20]
    return out


def _rng(vals, d=3):
    vals = [v for v in vals if v is not None]
    return [round(min(vals), d), round(max(vals), d)] if vals else None


def _first_sentences(text, n=320):
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(t) <= n:
        return t
    cut = t[:n]
    i = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[:i + 1] if i > n * 0.5 else cut.rsplit(" ", 1)[0] + " ...")


def in_band(sc, o2, p):
    """'full' bila O2 dan tekanan di dalam pita; 'o2_only' bila O2 di dalam pita tetapi tekanan tidak dicatat."""
    if o2 is None or not (sc["o2"][0] <= o2 <= sc["o2"][1]):
        return None
    if p is None:
        return "o2_only"
    return "full" if sc["p_kpa"][0] <= p <= sc["p_kpa"][1] else None


def _count(g, sql):
    try:
        return g.execute(sql).fetchone()[0]
    except Exception:          # noqa: BLE001 — tabel belum ada di basis data lama
        return None


def _totals(g):
    """Angka ringkas + tier masing-masing. Tier bukan hiasan: ia menentukan
    bagaimana angka itu boleh dibaca.

    Catatan tier video: `derived_auto`, BUKAN `human_verified`. Durasi nyala dari
    video diukur otomatis dan ketelitiannya belum terkuantifikasi -- hanya satu uji
    (T16) yang benar-benar terekam dua kali. Lembar bukti PNG-nya ada, tetapi
    pemeriksaan manusia menyeluruh belum dilakukan.
    """
    return [
        {"key": "investigations", "label": "Investigation profiles", "note": "NASA PSI catalog",
         "value": _count(g, "SELECT COUNT(*) FROM investigations"), "tier": "nasa_table",
         "path": "freefall.sqlite -> investigations"},
        {"key": "tests", "label": "Experimental tests", "note": "Standardized records",
         "value": _count(g, "SELECT COUNT(*) FROM tests"), "tier": "nasa_table",
         "path": "freefall.sqlite -> tests"},
        {"key": "telemetry", "label": "Telemetry records", "note": "ACME sensor mining",
         "value": _count(g, "SELECT COUNT(*) FROM telemetry"), "tier": "derived_auto",
         "path": "freefall.sqlite -> telemetry"},
        {"key": "video", "label": "Video episodes", "note": "BASS / BASS-II",
         "value": _count(g, "SELECT COUNT(*) FROM video_episodes"), "tier": "derived_auto",
         "path": "freefall.sqlite -> video_episodes",
         "caveat": "burn durations are automatic; precision not yet quantified"},
    ]


def build():
    key = (GOLD.stat().st_mtime_ns, BRAIN.stat().st_mtime_ns)
    if _CACHE["key"] == key:
        return _CACHE["data"]
    g = sqlite3.connect(GOLD)
    g.row_factory = sqlite3.Row
    b = sqlite3.connect(BRAIN)
    b.row_factory = sqlite3.Row

    invs = [dict(r) for r in g.execute("SELECT * FROM investigations")]
    trows = defaultdict(list)
    for r in g.execute("SELECT * FROM tests"):
        trows[r["accession"]].append(dict(r))
    pubs = dict(g.execute("SELECT accession, COUNT(*) FROM publications GROUP BY 1").fetchall())
    ent_acc = dict(b.execute("SELECT id, accession FROM entity WHERE kind='test'").fetchall())
    tiers, results = defaultdict(Counter), Counter()
    for r in b.execute("SELECT entity, quantity, tier FROM measurement"):
        acc = ent_acc.get(r["entity"])
        if acc:
            tiers[acc][r["tier"]] += 1
            if r["quantity"] in RESULT_Q:
                results[acc] += 1
    arts = defaultdict(Counter)
    for r in b.execute("SELECT accession, kind, COUNT(*) n FROM artifact GROUP BY 1, 2"):
        arts[r["accession"]][r["kind"]] = r["n"]
    n_entities = Counter(ent_acc.values())
    max_res = max(results.values() or [1])

    cards, points = [], []
    for iv in sorted(invs, key=lambda x: int(x["accession"].split("-")[1])):
        acc = iv["accession"]
        rows = trows.get(acc, [])
        tests = [r for r in rows if r["granularity"] == "test"]
        raws = [json.loads(r["raw_json"] or "{}") for r in rows]
        direct, pillars, basis = DIRECT.get(acc, DEFAULT_DIRECT)
        o2_vals = [r["o2_mole_frac"] for r in rows if r["o2_mole_frac"] is not None]
        p_vals = [r["pressure_kpa"] for r in rows if r["pressure_kpa"] is not None]
        camp_o2 = sorted({round(x, 3) for raw in raws for x in _campaign_o2(raw)}) if not o2_vals else []
        camp_p = sorted({round(x, 1) for raw in raws for x in _campaign_p(raw)}) if not p_vals else []
        flows = [r["flow_cm_s"] for r in rows if r["flow_cm_s"] is not None]
        sizes = [r["size_mm"] for r in rows if r["size_mm"] is not None]
        fuels = Counter(r["fuel"] for r in rows if r["fuel"])
        cfgs = Counter(r["configuration"] for r in rows if r["configuration"])
        dil = Counter(r["diluent"] for r in rows if r["diluent"])
        phases = Counter(r["fuel_phase"] for r in rows if r["fuel_phase"])

        def varied(field):
            vals = {r[field] for r in rows if r[field] not in (None, "")}
            return "varied" if len(vals) > 1 else ("constant" if len(vals) == 1 else "not recorded")
        variables = {"fuel": varied("fuel"), "configuration": varied("configuration"), "oxygen": varied("o2_mole_frac"),
                     "pressure": varied("pressure_kpa"), "diluent": varied("diluent"), "flow": varied("flow_cm_s"),
                     "sample size": varied("size_mm")}
        if camp_o2 and variables["oxygen"] == "not recorded":
            variables["oxygen"] = "varied (listed per day, not per test)" if len(camp_o2) > 1 else "constant"
        cols = []
        for raw in raws[:60]:
            for k in raw:
                if k not in cols:
                    cols.append(k)
        a = arts.get(acc, Counter())
        own = []
        if a.get("telemetry_csv"):
            own.append(f"{a['telemetry_csv']} raw sensor recordings (~125 Hz, 18 shared channels)")
        if a.get("video"):
            own.append(f"{a['video']} videos analysed for visible-flame duration")
        if a.get("image_series"):
            own.append(f"{a['image_series']} mapped image series (flame tip and char front tracked)")
        t = tiers.get(acc, Counter())
        derived = t.get("derived_auto", 0) + t.get("nasa_calibrated", 0) + t.get("human_verified", 0)
        highlights = []
        if a.get("telemetry_csv") and n_entities.get(acc, 0) > len(tests):
            highlights.append(f"{n_entities[acc]} individual tests reconstructed from telemetry; the NASA table lists {len(rows)} rows")
        if derived:
            highlights.append(f"{derived} values added by our analysis that are not in the NASA test table "
                              f"({t.get('nasa_calibrated', 0)} calibrated, {t.get('derived_auto', 0)} derived and awaiting human review)")
        card = {
            "accession": acc, "name": iv["acronym"] or SHORT.get(acc, acc), "title": iv["title"],
            "kind": "ground" if "Ground" in (iv["project_type"] or "") else "flight",
            "platform": iv["platform"] or "", "hardware": iv["hardware"] or "", "facility": FACILITY.get(acc, "laboratory / computation"),
            "sub_area": iv["sub_area"] or "", "years": [iv["start"][-4:] if iv["start"] else None, iv["end"][-4:] if iv["end"] else None],
            "pillars": pillars, "direct": direct, "direct_basis": basis,
            "phases": [p for p, _ in phases.most_common()],
            "fuels": [{"name": k, "n": v} for k, v in fuels.most_common(6)], "n_fuels": len(fuels),
            "samples": [{"name": k, "n": v} for k, v in cfgs.most_common(4)],
            "size_mm": _rng(sizes, 2),
            "o2": _rng(o2_vals), "o2_listed": camp_o2, "o2_level": "per test" if o2_vals else ("per day (listed)" if camp_o2 else "not recorded"),
            "p_kpa": _rng(p_vals, 1), "p_listed": camp_p, "flow_cm_s": _rng(flows, 1), "diluents": [k for k, _ in dil.most_common()],
            "n_rows": len(rows), "n_tests": len(tests), "n_brain_tests": n_entities.get(acc, 0),
            "variables": variables, "columns": cols[:24],
            "own_data": own, "tiers": dict(t), "n_results": results.get(acc, 0),
            "evidence": round(math.log10(1 + results.get(acc, 0)) / math.log10(1 + max_res), 3),
            "n_publications": pubs.get(acc, 0), "files_listed": int(iv["n_files_listed"] or 0), "files_local": int(iv["n_files_local"] or 0),
            "objective": _first_sentences(iv["objective"]), "impacts": _first_sentences(iv["impacts"], 260),
            "psi_url": iv["psi_url"], "highlights": highlights,
        }
        cards.append(card)
        for r in tests:
            if r["o2_mole_frac"] is None:
                continue
            tid = f"test:{acc}:{r['test_id']}"
            points.append({"id": tid if tid in ent_acc else None, "acc": acc, "t": r["test_id"], "ph": r["fuel_phase"], "fuel": r["fuel"],
                           "o2": round(r["o2_mole_frac"], 4), "p": None if r["pressure_kpa"] is None else round(r["pressure_kpa"], 1),
                           "out": r["outcome"] or ({"yes": "ignited", "no": "did not ignite"}.get(r["ignited"]) if r["ignited"] else None)})
    by_acc = {c["accession"]: c for c in cards}

    # ---------------- skenario
    import brain
    boundary = json.loads((ROOT / "analysis" / "ml" / "boundary" / "boundary.json").read_text(encoding="utf-8"))
    scen = {}
    for sc in SCENARIOS:
        near = defaultdict(lambda: {"full": 0, "o2_only": 0})
        rows_near = []
        for p in points:
            kind = in_band(sc, p["o2"], p["p"])
            if kind:
                near[p["acc"]][kind] += 1
                rows_near.append({**p, "match": kind})
        ranking = []
        for c in cards:
            n = near.get(c["accession"], {"full": 0, "o2_only": 0})
            listed = [x for x in c["o2_listed"] if sc["o2"][0] <= x <= sc["o2"][1]]
            if n["full"]:
                cond = min(1.0, n["full"] / 10)
                why = f"{n['full']} tests inside the O2 and pressure band"
            elif n["o2_only"]:
                cond = 0.5 * min(1.0, n["o2_only"] / 10)
                why = f"{n['o2_only']} tests inside the O2 band, but pressure was not recorded"
            elif listed:
                cond = 0.3
                why = "O2 levels inside the band are listed per day (" + ", ".join(f"{x:.0%}" for x in listed) + "), not per test"
            elif c["o2"] or c["o2_listed"]:
                cond = 0.0
                lo, hi = (c["o2"] or [min(c["o2_listed"]), max(c["o2_listed"])])
                why = (f"tested at {lo:.0%} O2" if round(lo, 2) == round(hi, 2) else f"tested at {lo:.0%} to {hi:.0%} O2") + ", outside this band"
            else:
                cond = 0.0
                why = "oxygen level not tabulated"
            comp = {"direct": c["direct"], "conditions": round(cond, 3), "evidence": c["evidence"]}
            score = sum(WEIGHTS[k] * comp[k] for k in WEIGHTS)
            ranking.append({"accession": c["accession"], "name": c["name"], "pillars": c["pillars"], "score": round(score, 3),
                            "components": comp, "n_full": n["full"], "n_o2_only": n["o2_only"],
                            "why": {"direct": c["direct_basis"], "conditions": why,
                                    "evidence": f"{c['n_results']} result values (ignition, outcome, burn time or rate, spread rate)"}})
        ranking.sort(key=lambda r: (-r["score"], r["accession"]))
        # tabel fase
        phase = {}
        for ph in ("solid", "droplet", "gas", "smoke"):
            accs = [c for c in cards if ph in c["phases"]]
            pts = [p for p in points if p["ph"] == ph]
            o2s = [p["o2"] for p in pts] + [x for c in accs for x in c["o2_listed"]]
            phase[ph] = {"n_tests": sum(c["n_tests"] for c in accs), "n_with_o2": len(pts),
                         "n_in_band": sum(1 for p in pts if in_band(sc, p["o2"], p["p"]) == "full"),
                         "n_o2_only": sum(1 for p in pts if in_band(sc, p["o2"], p["p"]) == "o2_only"),
                         "o2_max_per_test": max((p["o2"] for p in pts), default=None), "o2_max_any": max(o2s, default=None),
                         "pressure_recorded": sum(1 for p in pts if p["p"] is not None)}
        # prediksi model di titik tengah
        models = []
        o2c, pc = sc["center"]["o2"], sc["center"]["p_kpa"]
        for fuel in ("heptane", "methanol"):
            r = brain.whatif("flex", fuel=fuel, o2=o2c, pressure_kpa=pc, he=0)
            models.append({"what": f"FLEX {fuel} droplet", "input": f"O2 {o2c:.0%}, {pc:g} kPa, no helium", "valid": bool(r.get("valid")),
                           "p_extinction": r.get("p_extinction"), "K_mm2_s": (r.get("K_mm2_s") or {}).get("value") if r.get("valid") else None,
                           "auc_per_day": r["metrics"]["gp"]["auc"], "range": r.get("range"), "card": "gp_boundary_flex_ext",
                           "caveat": "burning liquid droplet, not a solid material; model prediction, not a measurement"})
        for fuel in ("ethane", "propane", "butane"):
            r = brain.whatif("cfig", config="normal", fuel=fuel, o2=o2c, x_fuel=0.3)
            models.append({"what": f"CFI-G {fuel} gas flame (normal)", "input": f"O2 {o2c:.0%}, fuel fraction 0.3, about {r.get('fixed', {}).get('pressure_kpa', '?')} kPa (held fixed)",
                           "valid": bool(r.get("valid")), "p_ignite": r.get("p_ignite"), "auc_per_day": r["metrics"]["gp"]["auc"],
                           "range": r.get("range"), "card": "gp_boundary_cfig_ign",
                           "caveat": "gas burner flame; pressure is held at the map value, not the scenario pressure"})
        # uji berikutnya
        nxt = []
        for r in boundary["flex_ext"]["recommend"]:
            nxt.append({"exp": "FLEX droplet", "o2": r["o2"], "p_kpa": r["pressure_kpa"], "detail": f"{r['fuel']}, He {r['x_he']}, CO2 {r['x_co2']}, d0 {r['d0_mm']} mm",
                        "U": r["U"], "in_band": in_band(sc, r["o2"], r["pressure_kpa"]) == "full"})
        for r in boundary["cfig_ign"]["recommend"]:
            nxt.append({"exp": "CFI-G gas flame", "o2": r["o2"], "p_kpa": r["pressure_kpa"], "detail": f"{r['config']} {r['fuel']}, fuel fraction {r['x_fuel']}",
                        "U": r["U"], "in_band": in_band(sc, r["o2"], r["pressure_kpa"]) == "full"})
        nxt.sort(key=lambda x: (not x["in_band"], x["U"]))
        # celah
        gaps = []
        s, d, gph = phase["solid"], phase["droplet"], phase["gas"]
        if s["n_in_band"] == 0:
            msg = f"No solid-material test falls inside this band. Of {s['n_tests']} solid-fuel tests in PSI tables, {s['n_with_o2']} record oxygen"
            if s["o2_max_per_test"] is not None:
                msg += f" (highest {s['o2_max_per_test']:.1%})"
            msg += f" and {s['pressure_recorded']} record pressure."
            if s["n_o2_only"]:
                msg += f" {s['n_o2_only']} match the oxygen band only."
            gaps.append({"level": "critical", "title": "Solid materials", "text": msg})
        if sc["id"] in ("surface",):
            gaps.append({"level": "critical", "title": "Gravity", "text": PARTIAL_G[0] + " " + PARTIAL_G[3]})
        total_in = sum(v["n_in_band"] for v in phase.values())
        gaps.append({"level": "info" if total_in >= 20 else "warning", "title": "Tests inside the band",
                     "text": f"{total_in} tests with both oxygen and pressure inside the band: {d['n_in_band']} droplet, {gph['n_in_band']} gas, {s['n_in_band']} solid."})
        if phase["smoke"]["n_with_o2"] == 0:
            gaps.append({"level": "warning", "title": "Smoke detection",
                         "text": f"The {phase['smoke']['n_tests']} smoke-aerosol tests (SAME, SAME-R, DAFT) tabulate air flow and material, but no oxygen or pressure, so they cannot be placed in any atmosphere band."})
        listed = [c for c in cards if any(sc["o2"][0] <= x <= sc["o2"][1] for x in c["o2_listed"])]
        for c in listed:
            gaps.append({"level": "info", "title": f"{c['name']} (per-day listing)",
                         "text": f"{c['name']} lists oxygen levels of " + ", ".join(f"{x:.1%}" for x in c["o2_listed"]) + " per test day; per-test conditions and pressures are not in the summary table."})
        if sc["id"] == "suit":
            gaps.append({"level": "warning", "title": "Reading CFI-G oxygen", "text": "In ACME CFI-G the high-oxygen mixture (up to 85% O2) flows from the burner into a fuel and nitrogen atmosphere (inverse flame); it is not the ambient atmosphere."})
        rows_near.sort(key=lambda p: (p["match"] != "full", abs(p["o2"] - o2c)))
        scen[sc["id"]] = {**sc, "ranking": ranking, "phase": phase, "near": rows_near[:400], "n_near": len(rows_near),
                          "models": models, "next_tests": nxt[:8], "gaps": gaps,
                          "headline": _headline(sc, phase, total_in)}
    data = {"built": brain.db().execute("SELECT value FROM meta WHERE key='built'").fetchone()[0],
            "weights": WEIGHTS, "pillars": PILLARS, "scenarios": [s["id"] for s in SCENARIOS], "scenario": scen,
            "investigations": cards, "points": points, "earth": EARTH, "partial_gravity": PARTIAL_G, "suggested": SUGGESTED,
            # Angka ringkas untuk kepala halaman, masing-masing DENGAN tier-nya, supaya
            # tampilan tidak perlu menuliskannya sebagai teks keras (mockup FLARE+ sempat
            # menandai episode video "human_verified"; itu salah -- ketelitiannya belum
            # terkuantifikasi, hanya satu uji yang benar-benar terekam ulang).
            "totals": _totals(g),
            # Ukuran indeks pencarian paper, untuk bilah status FLARE+ (sebelumnya
            # ditulis keras "7,924 CHUNKS" dan usang setelah paper baru masuk).
            "corpus": {"chunks": _count(g, "SELECT COUNT(*) FROM paper_chunks"),
                       "papers_full_text": _count(g, "SELECT COUNT(DISTINCT paper_uid) FROM paper_chunks"),
                       "publications": _count(g, "SELECT COUNT(*) FROM publications")},
            "tiers": {"nasa_table": "NASA table", "nasa_calibrated": "calibrated NASA signal", "derived_auto": "derived, not yet human-checked",
                      "human_verified": "human-verified", "paper_claim": "paper claim", "model_prediction": "model prediction"},
            "method": {"score": "score = 0.40 x direct fire-safety link + 0.35 x condition proximity + 0.25 x evidence depth (weights adjustable)",
                       "direct": "rubric from the challenge statement and PSI sub-area; the reason is shown for every investigation",
                       "conditions": "tests inside the scenario's O2 and pressure band, saturating at 10; halved when pressure is not recorded; 0.3 when only listed per day",
                       "evidence": "log-scaled count of result values (ignition, outcome, burn time, burning rate, spread rate, aerosol results)"}}
    g.close()
    b.close()
    _CACHE.update(key=key, data=data)
    return data


def _headline(sc, phase, total_in):
    s = phase["solid"]
    top = f"{s['o2_max_per_test']:.0%}" if s["o2_max_per_test"] is not None else "n/a"
    if sc["id"] == "surface":
        return (f"A surface base will hold at least {sc['center']['o2']:.0%} oxygen. Microgravity tests of solid materials in PSI stop at {top}. "
                f"{total_in} tests sit inside the band, and none of them burns a solid.")
    if sc["id"] == "cabin":
        return (f"{total_in} tests sit inside the cabin band. Solid-material tests reach {top} oxygen but do not record pressure; "
                f"{s['n_o2_only']} of them match on oxygen alone.")
    if sc["id"] == "suit":
        return f"{total_in} tests match a pure-oxygen, low-pressure suit atmosphere. PSI holds no flammability data for this condition."
    return (f"{total_in} microgravity tests were run in Earth-like air. Without buoyancy they isolate diffusion and radiation, "
            f"which is what terrestrial fire models need for validation.")


# ================================================================ antarmuka untuk asisten
ALIASES = {"flex-2": "PSI-68", "flex2": "PSI-68", "flex": "PSI-69", "bass-ii": "PSI-25", "bass ii": "PSI-25", "bass2": "PSI-25", "bass": "PSI-26",
           "saffire-iii": "PSI-100", "saffire iii": "PSI-100", "saffire 3": "PSI-100", "saffire-ii": "PSI-99", "saffire ii": "PSI-99",
           "saffire 2": "PSI-99", "saffire-i": "PSI-98", "saffire i": "PSI-98", "saffire 1": "PSI-98", "saffire": "PSI-98",
           "same-r": "PSI-101", "same": "PSI-102", "daft": "PSI-47", "spice": "PSI-107", "slice": "PSI-106",
           "cfi-g": "PSI-159", "cfig": "PSI-159", "cfi": "PSI-39", "bre": "PSI-20", "cld": "PSI-21", "e-field": "PSI-22", "efield": "PSI-22",
           "s-flame": "PSI-23", "flame design": "PSI-10"}


def find_investigations(text):
    """Investigasi yang disebut dalam teks, urut kemunculan. Nama terpanjang dicocokkan dulu (FLEX-2 sebelum FLEX)."""
    t = " " + str(text) + " "
    blank = lambda m: " " * len(m.group(0))
    hits = []
    for m in re.finditer(r"psi-\d+", t, re.I):
        hits.append((m.start(), m.group(0).upper()))
    t = re.sub(r"psi-\d+", blank, t, flags=re.I)
    for alias in sorted(ALIASES, key=len, reverse=True):
        # 'same' juga kata Inggris biasa: hanya dihitung bila ditulis kapital (SAME)
        pat, flags = (r"(?<![\w-])SAME(?![\w-])", 0) if alias == "same" else (r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", re.I)
        for m in re.finditer(pat, t, flags):
            hits.append((m.start(), ALIASES[alias]))
        t = re.sub(pat, blank, t, flags=flags)
    out = []
    for h in sorted(hits):
        if h[1] not in out:
            out.append(h[1])
    return out


def resolve(name):
    d = build()
    key = str(name).strip().lower()
    accs = [ALIASES[key]] if key in ALIASES else find_investigations(str(name))
    c = next((c for c in d["investigations"] if accs and c["accession"] == accs[0]), None)
    return c or {"error": f"investigation not found: {name}", "known": [c["name"] for c in d["investigations"]]}


def scenario_id(text):
    t = text.lower()
    if re.search(r"moon|lunar|bulan|mars|rover|surface|base\b|pangkalan|habitat permukaan|30\s?%", t):
        return "surface"
    if re.search(r"suit|baju|eva\b|pure oxygen|oksigen murni", t):
        return "suit"
    if re.search(r"earth|bumi|terrestrial|firefighter|pemadam kebakaran", t):
        return "earth"
    if re.search(r"iss\b|station|stasiun|cabin|kabin|spacecraft|wahana|orion|capsule", t):
        return "cabin"
    return None


def rank(scenario="cabin", pillar=None, limit=8):
    d = build()
    sc = d["scenario"].get(scenario) or d["scenario"]["cabin"]
    rows = [r for r in sc["ranking"] if not pillar or pillar in r["pillars"]]
    return {"scenario": {k: sc[k] for k in ("id", "name", "o2", "p_kpa", "gravity", "basis")}, "weights": d["weights"],
            "method": d["method"]["score"], "ranking": rows[:max(1, min(int(limit or 8), 24))]}


def card(name):
    c = resolve(name)
    if "error" in c:
        return c
    return {k: c[k] for k in ("accession", "name", "title", "kind", "platform", "facility", "pillars", "direct", "direct_basis", "phases",
                               "fuels", "samples", "size_mm", "o2", "o2_listed", "o2_level", "p_kpa", "flow_cm_s", "diluents", "n_rows",
                               "n_tests", "variables", "columns", "own_data", "tiers", "n_results", "n_publications", "objective", "highlights")}


def compare(a, b):
    ca, cb = resolve(a), resolve(b)
    for c in (ca, cb):
        if "error" in c:
            return c
    keys = ("name", "accession", "facility", "pillars", "phases", "fuels", "samples", "o2", "o2_listed", "p_kpa", "flow_cm_s",
            "diluents", "n_tests", "variables", "n_results", "own_data")
    same, diff = [], []
    for k in ("facility", "pillars", "phases"):
        (same if ca[k] == cb[k] else diff).append(k)
    return {"a": {k: ca[k] for k in keys}, "b": {k: cb[k] for k in keys}, "same": same, "different": diff,
            "shared_fuels": sorted({f["name"] for f in ca["fuels"]} & {f["name"] for f in cb["fuels"]})}


def evidence(scenario="surface"):
    d = build()
    sc = d["scenario"].get(scenario) or d["scenario"]["surface"]
    return {"scenario": {k: sc[k] for k in ("id", "name", "o2", "p_kpa", "gravity", "gravity_data", "basis")},
            "headline": sc["headline"], "phase": sc["phase"], "n_near": sc["n_near"], "nearest_tests": sc["near"][:8],
            "models": sc["models"], "gaps": sc["gaps"], "next_tests": sc["next_tests"][:4]}


# ---------------------------------------------------------------- jawaban luring (Inggris / Indonesia)
INTENT = [
    ("compare", r"compare|bandingkan|perbandingan|difference|differ|beda(nya)?\b|\bvs\b|versus"),
    ("rank", r"which investigations?|most relevant|\brank|peringkat|priorit|investigasi (mana|apa)|paling relevan|paling penting|"
             r"relevant (to|for)|studies (matter|are relevant)"),
    ("evidence", r"what (do we|is) know|what does nasa know|evidence|bukti|apa yang (sudah )?(kita )?(di)?ketahui|is .* safe|apakah .* aman|"
                 r"\bgaps?\b|missing|celah|kekurangan data|how flammable|fire[- ]safe"),
    ("card", r"what (is|was|did)|tell me about|describe|summari[sz]e|apa itu|ceritakan|ringkas|rangkum|jelaskan|objective|tujuan|"
             r"what fuels|bahan bakar apa|which sensors|sensor apa|what hardware|perangkat apa"),
]


def match(q, has_test_code=False):
    """Maksud tingkat investigasi, atau None bila pertanyaan itu urusan perencana lama (tingkat uji)."""
    if has_test_code:
        return None
    ql = q.lower()
    invs = find_investigations(q)
    sc = scenario_id(ql)
    for name, pat in INTENT:
        if not re.search(pat, ql):
            continue
        if name == "compare" and len(invs) >= 2:
            return name
        if name == "rank" and re.search(r"investigat|investigasi|stud(y|ies)|experiment|eksperimen|penelitian", ql):
            return name
        if name == "evidence" and sc:
            return name
        if name == "card" and len(invs) == 1 and not re.search(r"\d{5}", ql):
            return name
    return None


def english(q):
    ql = " " + q.lower() + " "
    en = len(re.findall(r" (what|which|how|the|is|are|does|do|compare|tell|show|about|for|and|most|should) ", ql))
    idn = len(re.findall(r" (apa|yang|bagaimana|mana|bandingkan|ceritakan|untuk|dan|paling|jelaskan|apakah|kita|uji) ", ql))
    return en > idn


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}".rstrip("0").rstrip(".") + "%"


def answer(question, T):
    """Susun jawaban tingkat investigasi. T(nama_alat, **arg) adalah pemanggil alat milik asisten.
    Mengembalikan None bila bukan urusan lapis ini."""
    ql = question.lower()
    intent = match(question, bool(re.search(r"\b\d{5}\s?[A-Z]\d+", question)))
    if not intent:
        return None
    en = english(question)
    L = lambda e, i: e if en else i
    sc = scenario_id(ql)
    invs = find_investigations(question)
    parts = []
    if intent == "rank":
        pillar = next((p for p in ("prevention", "detection", "suppression") if p in ql or
                       {"prevention": "pencegahan", "detection": "deteksi", "suppression": "pemadaman"}[p] in ql), None)
        r = T("rank_investigations", scenario=sc or "cabin", pillar=pillar, limit=5)
        s = r["scenario"]
        parts.append(L(f"For {s['name']} ({_pct(s['o2'][0])} to {_pct(s['o2'][1])} O2, {s['p_kpa'][0]:g} to {s['p_kpa'][1]:g} kPa), the investigations rank as follows",
                       f"Untuk {s['name']} (O2 {_pct(s['o2'][0])} sampai {_pct(s['o2'][1])}, {s['p_kpa'][0]:g} sampai {s['p_kpa'][1]:g} kPa), peringkat investigasinya")
                     + (L(f", {pillar} only", f", khusus {pillar}") if pillar else "") + ":")
        for i, x in enumerate(r["ranking"], 1):
            c = x["components"]
            parts.append(f"{i}. {x['name']} [[inv:{x['accession']}]]: " + L("score", "skor") + f" {x['score']:.2f} "
                         f"(direct {c['direct']}, conditions {c['conditions']}, evidence {c['evidence']}). {x['why']['conditions'][0].upper() + x['why']['conditions'][1:]}.")
        parts.append(L(f"How the score is built: {r['method']}.", f"Cara skor dihitung: {r['method']}."))
    elif intent == "compare":
        r = T("compare_investigations", a=invs[0], b=invs[1])
        if "error" in r:
            return {"parts": [r["error"]]}
        a, b = r["a"], r["b"]

        def line(c):
            o2 = (f"{_pct(c['o2'][0])} to {_pct(c['o2'][1])} O2" if c["o2"] else
                  ("O2 listed per day: " + ", ".join(_pct(x) for x in c["o2_listed"]) if c["o2_listed"] else L("O2 not tabulated", "O2 tidak ditabulasi")))
            pr = f"{c['p_kpa'][0]:g} to {c['p_kpa'][1]:g} kPa" if c["p_kpa"] else L("pressure not tabulated", "tekanan tidak ditabulasi")
            fuels = ", ".join(f["name"] for f in c["fuels"][:3]) or "n/a"
            varied = ", ".join(k for k, v in c["variables"].items() if v.startswith("varied")) or "n/a"
            return (f"{c['name']} [[inv:{c['accession']}]]: {c['facility']}; {', '.join(c['phases']) or 'n/a'}; " + L("fuels", "bahan bakar") + f" {fuels}; {o2}; {pr}; "
                    f"{c['n_tests']} " + L("tests", "uji") + f", {c['n_results']} " + L("result values", "angka hasil") + "; "
                    + L("varied", "divariasikan") + f": {varied}.")
        parts += [line(a), line(b)]
        if r["same"]:
            parts.append(L("Same: ", "Sama: ") + ", ".join(r["same"]) + ".")
        if r["different"]:
            parts.append(L("Different: ", "Berbeda: ") + ", ".join(r["different"]) + ".")
        if r["shared_fuels"]:
            parts.append(L("Shared fuels: ", "Bahan bakar yang sama: ") + ", ".join(r["shared_fuels"]) + ".")
    elif intent == "evidence":
        r = T("scenario_evidence", scenario=sc)
        parts.append(r["headline"])
        ph = r["phase"]
        parts.append(L("Tests inside the band, by fuel type: ", "Uji di dalam pita, per jenis bahan bakar: ")
                     + "; ".join(f"{k} {v['n_in_band']}" + (f" (+{v['n_o2_only']} " + L("oxygen only", "hanya cocok O2") + ")" if v["n_o2_only"] else "")
                                 for k, v in ph.items()) + ".")
        ok = [m for m in r["models"] if m["valid"]]
        if ok:
            parts.append(L("Model predictions at the band centre (predictions, not measurements): ", "Prediksi model di titik tengah pita (prediksi, bukan pengukuran): ")
                         + "; ".join(f"{m['what']}: " + (f"P(extinction) {m['p_extinction']}" if "p_extinction" in m else f"P(ignition) {m['p_ignite']}")
                                     + f" [[model:{m['card']}]]" for m in ok) + ".")
        else:
            parts.append(L("No model answers here: the band is outside every tested range, so the models refuse to extrapolate.",
                           "Tidak ada model yang menjawab: pita ini di luar semua rentang uji, jadi model menolak mengekstrapolasi."))
        for gp in r["gaps"][:3]:
            parts.append(f"{L('Gap', 'Celah')} ({gp['title']}): {gp['text']}")
    else:
        r = T("get_investigation", investigation=invs[0])
        if "error" in r:
            return {"parts": [r["error"]]}
        o2 = (f"{_pct(r['o2'][0])} to {_pct(r['o2'][1])}" if r["o2"] else
              (", ".join(_pct(x) for x in r["o2_listed"]) + L(" (listed per day)", " (tertulis per hari)") if r["o2_listed"] else L("not tabulated", "tidak ditabulasi")))
        parts.append(f"{r['name']} [[inv:{r['accession']}]] ({r['title']}), {r['facility']}. " + L("Fire-safety role: ", "Peran keselamatan api: ")
                     + ", ".join(r["pillars"]) + f" ({r['direct_basis']}).")
        parts.append(L("Objective: ", "Tujuan: ") + r["objective"])
        parts.append(L("Fuels: ", "Bahan bakar: ") + (", ".join(f"{f['name']} ({f['n']})" for f in r["fuels"][:4]) or "n/a")
                     + L(". Oxygen: ", ". Oksigen: ") + o2
                     + L(". Pressure: ", ". Tekanan: ") + (f"{r['p_kpa'][0]:g} to {r['p_kpa'][1]:g} kPa" if r["p_kpa"] else L("not tabulated", "tidak ditabulasi"))
                     + f". {r['n_tests']} " + L("tests", "uji") + f", {r['n_results']} " + L("result values.", "angka hasil."))
        varied = [k for k, v in r["variables"].items() if v.startswith("varied")]
        if varied:
            parts.append(L("Varied between tests: ", "Divariasikan antar-uji: ") + ", ".join(varied) + ".")
        for h in r["own_data"] + r["highlights"]:
            parts.append(L("Our analysis: ", "Analisis kami: ") + h + ".")
    return {"parts": parts, "scenario": sc, "investigations": invs, "intent": intent}


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = argv[0] if argv else "export"
    if cmd == "export":
        d = dict(build())
        import assistant                      # jawaban tersimpan untuk salinan statis (tanpa server)
        d["canned"] = []
        for q in SUGGESTED:
            r = assistant.ask(q, mode="offline")
            d["canned"].append({"q": q, "a": r["answer"], "grounding": r["grounding"], "mode": r["mode"],
                                "tools": [c["name"] for c in r["tool_calls"]]})
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        s = d["scenario"]["surface"]
        print(f"{OUT.relative_to(ROOT)}: {len(d['investigations'])} investigasi, {len(d['points'])} titik uji, {OUT.stat().st_size // 1024} KB")
        print("surface:", s["headline"])
        for r in s["ranking"][:6]:
            print(f"  {r['score']:.3f} {r['name']:22s} {r['components']}")
    elif cmd == "rank":
        print(json.dumps(rank(argv[1] if len(argv) > 1 else "cabin"), ensure_ascii=False, indent=1))
    elif cmd == "card":
        print(json.dumps(card(argv[1]), ensure_ascii=False, indent=1))
    elif cmd == "evidence":
        print(json.dumps(evidence(argv[1] if len(argv) > 1 else "surface"), ensure_ascii=False, indent=1)[:6000])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
