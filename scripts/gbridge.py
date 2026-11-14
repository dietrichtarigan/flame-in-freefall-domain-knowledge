#!/usr/bin/env python3
"""Jembatan-g: model tereduksi batas nyala bahan padat sebagai fungsi (O2, aliran, g, p).

Gagasan (analog micromagnetics): bentuk persamaan universal, parameter bahan di-fit dari
eksperimen. Gravitasi TIDAK masuk ke kinetika; ia hanya menghasilkan aliran apung

    U_b(g, p) = U_b1 * (g/g_E)^n * (p0/p)^n          n = 1/3  (skala tepi-depan nyala)

yang dijumlahkan dengan aliran paksa (superposisi linear, seperti Olson & Ferkul 2017):

    U = U_paksa + U_b

Batas nyala bahan ditulis dalam laju regangan a (1/s):

    X_lim(a) = X0 + A*exp(-a/a_q) + B*a              [% O2]
               ^      ^ cabang padam radiatif  ^ cabang blowoff

Parameter bahan {X0, A, a_q, B} = "A_ex, K_u"-nya pembakaran. Untuk batang PMMA nilainya
diambil dari fit terbitan atas data BASS-II (PSI-25), lalu DIPERIKSA ULANG terhadap titik
yang kita urai sendiri dari kolom "Air display" tabel NASA.

Semua keluaran model bertier `model_prediction` dan selalu membawa selang.

Pakai:
  python scripts/gbridge.py            # urai, periksa, tulis analysis/gbridge + app/gbridge/data.json
  python scripts/gbridge.py --selftest # cek angka jangkar saja
"""
import argparse
import csv
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "kb" / "gold" / "freefall.sqlite"
OUT = ROOT / "analysis" / "gbridge"
APP = ROOT / "app" / "gbridge"

G_E = 9.80665
P0 = 101.325

# ---------------------------------------------------------------- parameter (dengan sumber)
PARAMS = {
    "ub1_cm_s": 20.0,        # aliran apung di dasar nyala pada 1 g
    "ub1_range": [10.0, 30.0],
    "ub1_source": "Olson & Ferkul 2017 (doi:10.1016/j.combustflame.2017.03.001) memakai 20 cm/s; "
                  "skala (g*alpha*dT/T)^(1/3) memberi 10 cm/s (alpha di suhu ruang) sampai 22 cm/s "
                  "(alpha di suhu film)",
    "n": 1.0 / 3.0,
    "n_alt": 0.5,            # (g*L*dT/T)^(1/2): panjang sampel tetap, rambat ke atas
    "p0_kpa": P0,
    "r0_cm": 0.318,
    "materials": {
        "pmma_rod": {
            "label": "Batang PMMA (BASS-II)",
            "X0": 13.4, "A": 6.0, "a_q": 2.0, "B": 0.0167,
            "tier": "paper_claim",
            "source": "Olson & Ferkul 2017, pers. (1): X_O2 = 6 exp(-0.5 a) + 0.0167 a + 13.4; "
                      "a = 3/2 U/r (r/r0)^(1/2), r0 = 0.318 cm",
            "valid": {"o2_pct": [13.5, 22.2], "u_cm_s": [0.0, 55.0], "p_kpa": [99.0, 103.0]},
        }
    },
}

BODIES = [
    {"id": "iss", "label": "ISS (mikrogravitasi)", "g_rel": 1e-6},
    {"id": "moon", "label": "Bulan", "g_rel": 1.62 / G_E},
    {"id": "mars", "label": "Mars", "g_rel": 3.71 / G_E},
    {"id": "earth", "label": "Bumi", "g_rel": 1.0},
]

ATMOSPHERES = [
    {"id": "iss", "label": "ISS / permukaan laut", "o2_pct": 21.0, "p_kpa": 101.3},
    {"id": "shuttle", "label": "Pra-EVA Shuttle (30 %, 10,2 psia)", "o2_pct": 30.0, "p_kpa": 70.3},
    {"id": "explore", "label": "Atmosfer eksplorasi (34 %, 8,2 psia)", "o2_pct": 34.0, "p_kpa": 56.5},
]


# ---------------------------------------------------------------- fisika
def u_buoy(g_rel, p_kpa=P0, ub1=None, n=None):
    """Aliran apung karakteristik (cm/s)."""
    ub1 = PARAMS["ub1_cm_s"] if ub1 is None else ub1
    n = PARAMS["n"] if n is None else n
    return ub1 * (g_rel ** n) * ((P0 / p_kpa) ** n)


def u_buoy_theory(g_rel=1.0, t_flame=1900.0, t_inf=300.0, t_alpha=None, p_kpa=P0):
    """(g*alpha*dT/T)^(1/3) dari sifat udara; untuk cek orde besaran U_b1."""
    t_alpha = t_inf if t_alpha is None else t_alpha
    alpha = 2.2e-5 * (t_alpha / 300.0) ** 1.7 * (P0 / p_kpa)      # m2/s
    return 100.0 * (g_rel * G_E * alpha * (t_flame - t_inf) / t_inf) ** (1.0 / 3.0)


def stretch(u_cm_s, r_cm=None):
    """Laju regangan paksa ternormalisasi ke r0 (1/s)."""
    r0 = PARAMS["r0_cm"]
    r = r0 if r_cm is None else r_cm
    return 1.5 * u_cm_s / r * math.sqrt(r / r0)


def u_equiv(u_cm_s, r_cm):
    """Aliran pada batang r0 yang memberi regangan sama (sumbu-x bersama peta)."""
    return stretch(u_cm_s, r_cm) / (1.5 / PARAMS["r0_cm"])


def x_lim(u_cm_s, mat="pmma_rod", r_cm=None):
    """Batas O2 (%) pada aliran total u; di bawahnya nyala tidak bertahan."""
    m = PARAMS["materials"][mat]
    a = stretch(u_cm_s, r_cm)
    return m["X0"] + m["A"] * math.exp(-a / m["a_q"]) + m["B"] * a


def loc_of_g(g_rel, u_forced=0.0, p_kpa=P0, mat="pmma_rod", r_cm=None):
    """Batas O2 pada gravitasi g: nilai tengah + selang dari ketidakpastian U_b1 dan eksponen."""
    mid = x_lim(u_forced + u_buoy(g_rel, p_kpa), mat, r_cm)
    alts = [mid]
    for ub1 in PARAMS["ub1_range"]:
        for n in (PARAMS["n"], PARAMS["n_alt"]):
            alts.append(x_lim(u_forced + u_buoy(g_rel, p_kpa, ub1, n), mat, r_cm))
    return mid, min(alts), max(alts)


# ---------------------------------------------------------------- urai tabel BASS-II
NUM = r"(?<![\w.])(\d+(?:\.\d+)?|\.\d+)"
INCH = {'1/4': 0.25, '3/8': 0.375, '1/2': 0.5, '0.5': 0.5}


def classify(fuel):
    f = fuel.lower()
    if "rod" in f:
        m = re.search(r"(1/4|3/8|1/2|0\.5)", f)
        r = INCH[m.group(1)] * 2.54 / 2 if m else None
        return "pmma_rod", r, ("black" if "bla" in f else "clear")
    if "sibal" in f:
        return "sibal", None, ""
    if "nomex" in f:
        return "nomex", None, ""
    if "pmma" in f or "film" in f or "micron" in f or "slab" in f:
        return "pmma_flat", None, ""
    return "other", None, ""


def parse_air(s):
    """'Air display' = bacaan anemometer (cm/s). Kembalikan (aliran[], ada_aliran_di_bawah_ambang)."""
    if not s or s.strip().lower() in ("none", "see fan"):
        return [], False
    low = bool(re.search(r"<\s*1|\blow|\bext\b|down to|decr", s.lower()))
    main = re.sub(r"\([^)]*\)", " ", s)
    paren = " ".join(re.findall(r"\(([^)]*)\)", s))

    def nums(part):
        part = re.split(r"\bpots?\b", part.lower())[0]          # angka setelah 'pot' = potensiometer
        out = []
        for m in re.finditer(NUM, part):
            v = float(m.group(1))
            pre = part[max(0, m.start() - 12):m.start()]
            if v > 40 and "max" not in pre:                     # >40 tanpa 'max' = tampilan kipas
                continue
            out.append(v)
        return out

    raw_main = [float(x) for x in re.findall(NUM, re.split(r"\bpots?\b", main.lower())[0])]
    vals = nums(main)
    if raw_main and sorted(raw_main)[len(raw_main) // 2] > 40 and paren and "pot" not in paren.lower():
        vals = nums(paren)                                      # kolom utama berisi tampilan kipas
    if any(v == 0 for v in vals):
        low = True
    return [v for v in vals if v > 0], low


def outcome_of(air, fan):
    t = f"{air or ''} | {fan or ''}".lower()
    if "no ign" in t:
        return "tidak_menyala"
    if "blowoff" in t:
        return "blowoff"
    if re.search(r"\bext\b|extinguish|\bout\b|\boff\b|would not stay lit", t):
        return "padam_aliran_rendah"
    return "tidak_tercatat"


def o2_final(ini, fin):
    try:
        f = float(fin)
    except (TypeError, ValueError):
        return ini, False
    if 10.0 < f <= ini + 0.3:
        return f, True
    return ini, False                                           # 1.6, 39.1 dst. = salah ketik sensor


def bass2_points(con):
    pts, tests = [], []
    for uid, raw in con.execute(
            "select test_uid, raw_json from tests where acronym='BASS-II' order by source_row"):
        d = json.loads(raw)
        try:
            ini = float(d["Calibrated initial O2 % by vol"])
        except (KeyError, ValueError):
            continue
        fin, fin_ok = o2_final(ini, d.get("Calibrated final O2 % by vol"))
        mat, r, colour = classify(d["Fuel Sample Material"])
        flows, low = parse_air(d.get("Air display"))
        out = outcome_of(d.get("Air display"), d.get("Fan display"))
        base = {"test": d["Test #"], "pi": d["PI"], "fuel": d["Fuel Sample Material"].strip(),
                "mat": mat, "r_cm": round(r, 4) if r else None, "colour": colour,
                "src": f"PSI-25 tabel uji, baris {d['Test #']}: Air display = {d.get('Air display')!r}"}
        tests.append({**base, "o2_ini": ini, "o2_fin": fin, "flows": flows, "outcome": out})

        def add(u, o2, kind, censored=False):
            ue = u_equiv(u, r) if r else u
            pts.append({**base, "u": u, "u_eq": round(ue, 3), "o2": o2, "kind": kind,
                        "censored": censored})

        for i, u in enumerate(flows):                            # nyala bertahan di tiap langkah aliran
            frac = i / max(1, len(flows) - 1) if len(flows) > 1 else 0.0
            add(u, round(ini + (fin - ini) * frac, 2), "nyala")
        if out == "padam_aliran_rendah":
            add(0.5, fin, "padam", censored=True)                # di bawah ambang anemometer (<1 cm/s)
        elif out == "blowoff":
            m = re.search(r"incr to\s+(?:max\s+)?" + NUM, (d.get("Air display") or "").lower())
            if m:
                add(float(m.group(1)), fin, "blowoff")
            elif flows:
                add(max(flows), fin, "blowoff", censored=True)   # blowoff di ATAS nilai ini
        elif out == "tidak_menyala":
            add(5.0, ini, "tidak_menyala", censored=True)        # 'no ign at any flow'
    return pts, tests


def saffire_points(con):
    pts = []
    for acr, tid, fuel, o2, u, d, outc, mv in con.execute(
            "select acronym,test_id,fuel,o2_mole_frac,flow_cm_s,flow_direction,outcome,metric_value "
            "from tests where acronym like 'SAFFIRE%' and flow_cm_s is not null"):
        burned = None
        if outc:
            burned = not re.search(r"~\s*0\b", outc)
        elif acr in ("SAFFIRE-I", "SAFFIRE-III"):
            burned = True                                        # laju rambat terukur (analysis/saffire)
        pts.append({"test": f"{acr} {tid}", "fuel": (fuel or "").strip() or "?", "mat": "saffire",
                    "u": u, "u_eq": u, "o2": round(o2 * 100, 2) if o2 else None, "dir": d,
                    "kind": "nyala" if burned else "tidak_merambat", "censored": False,
                    "src": f"{acr} tabel uji, baris {tid}: {outc or 'laju rambat dari citra'}"})
    return pts


# ---------------------------------------------------------------- pemeriksaan
def check_rods(pts):
    """Apakah titik urai-sendiri konsisten dengan batas terbitan?"""
    rod = [p for p in pts if p["mat"] == "pmma_rod" and p["r_cm"]]
    flame = [p for p in rod if p["kind"] == "nyala"]
    margin = [p["o2"] - x_lim(p["u"], r_cm=p["r_cm"]) for p in flame]
    inside = sum(1 for m in margin if m >= 0)
    blow = [p for p in rod if p["kind"] == "blowoff" and not p["censored"]]
    blow_res = [{"test": p["test"], "u": p["u"], "o2_obs": p["o2"],
                 "o2_model": round(x_lim(p["u"], r_cm=p["r_cm"]), 2)} for p in blow]
    ext = [p for p in rod if p["kind"] == "padam"]
    m = PARAMS["materials"]["pmma_rod"]
    x_min = min(x_lim(u / 100.0) for u in range(1, 3000))
    x_zero = m["X0"] + m["A"]
    ext_in_band = sum(1 for p in ext if x_min - 0.3 <= p["o2"] <= x_zero + 0.3)
    worst = sorted(margin)[:5]
    return {
        "n_rod_tests_points": len(rod), "n_flame": len(flame), "n_flame_above_boundary": inside,
        "flame_margin_min_pct_o2": round(min(margin), 2) if margin else None,
        "flame_margin_worst5": [round(w, 2) for w in worst],
        "blowoff_points": blow_res,
        "n_quench": len(ext), "n_quench_within_branch_range": ext_in_band,
        "quench_branch_range_pct_o2": [round(x_min, 2), round(x_zero, 2)],
        "quench_o2_obs_range": [min(p["o2"] for p in ext), max(p["o2"] for p in ext)] if ext else None,
        "note": "Cabang padam tidak bisa di-fit ulang dari tabel: aliran saat padam di bawah ambang "
                "anemometer (<1 cm/s); perlu kalibrasi potensiometer kipas -> cm/s.",
    }


def anchors():
    """Titik jangkar di luar mikrogravitasi."""
    x1g = x_lim(PARAMS["ub1_cm_s"] + 4.0)
    return [{
        "what": "Batas O2 rambat ke atas PMMA pada 1 g + 4 cm/s paksa",
        "observed": 15.4, "model": round(x1g, 2), "unit": "% O2",
        "source": "Olson & Ferkul 2017, bag. 4.5 (mengutip ref. [23]); U_b = 20 cm/s dari ref. [32]",
        "caveat": "Satu titik. U_b1 = 20 cm/s adalah masukan, jadi ini cek konsistensi, bukan validasi bebas.",
    }]


def coverage(pts):
    """Berapa titik PSI jatuh pada aliran setara tiap benda langit (+-25 %)."""
    out = []
    for b in BODIES:
        ub = u_buoy(b["g_rel"])
        lo, hi = ub * 0.75, ub * 1.25
        near = [p for p in pts if lo <= p["u"] <= hi and not p["censored"]]
        by = {}
        for p in near:
            by[p["mat"]] = by.get(p["mat"], 0) + 1
        out.append({**b, "u_b": round(ub, 2), "window": [round(lo, 2), round(hi, 2)],
                    "n_points": len(near), "by_material": by,
                    "loc": [round(v, 2) for v in loc_of_g(b["g_rel"])]})
    return out


def selftest():
    ok = True

    def chk(name, got, want, tol):
        nonlocal ok
        good = abs(got - want) <= tol
        ok &= good
        print(f"  {'OK ' if good else 'GAGAL'} {name}: {got:.3f} (harap {want} +- {tol})")

    chk("(g_Bulan/g_E)^(1/3)", (1.62 / G_E) ** (1 / 3), 0.55, 0.01)
    chk("(g_Mars/g_E)^(1/3)", (3.71 / G_E) ** (1 / 3), 0.72, 0.01)
    chk("U_b teori, alpha suhu ruang (cm/s)", u_buoy_theory(), 10.5, 1.0)
    chk("U_b teori, alpha suhu film 1100 K (cm/s)", u_buoy_theory(t_alpha=1100), 22.0, 2.0)
    chk("8,2 psia dalam kPa", 8.2 * 6.894757, 56.5, 0.1)
    chk("X_lim minimum batang PMMA (% O2)", min(x_lim(u / 100) for u in range(1, 3000)), 13.5, 0.15)
    chk("X_lim 1 g + 4 cm/s (% O2)", x_lim(24.0), 15.4, 0.2)
    chk("blowoff O22: batang 1/2 in., 26,5 cm/s (% O2)", x_lim(26.5, r_cm=0.635), 14.9, 0.1)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)

    con = sqlite3.connect(DB)
    pts, tests = bass2_points(con)
    saf = saffire_points(con)
    allpts = pts + saf
    OUT.mkdir(parents=True, exist_ok=True)
    APP.mkdir(parents=True, exist_ok=True)

    cols = ["test", "mat", "fuel", "r_cm", "u", "u_eq", "o2", "kind", "censored", "src"]
    with open(OUT / "points.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(allpts)

    chk = check_rods(pts)
    grid = [10 ** (-6 + 6.3 * i / 125) for i in range(126)]
    curve = [{"g": g, "loc": [round(v, 3) for v in loc_of_g(g)]} for g in grid]
    outcomes = {}
    for t in tests:
        outcomes[t["outcome"]] = outcomes.get(t["outcome"], 0) + 1
    data = {
        "params": PARAMS, "bodies": BODIES, "atmospheres": ATMOSPHERES,
        "points": [{k: p.get(k) for k in cols + ["dir"]} for p in allpts],
        "check": chk, "anchors": anchors(), "coverage": coverage(allpts), "curve": curve,
        "counts": {"bass2_tests_parsed": len(tests), "points": len(allpts),
                   "outcomes": outcomes,
                   "by_material": {m: sum(1 for p in allpts if p["mat"] == m)
                                   for m in sorted({p["mat"] for p in allpts})}},
        "ub_theory": {"alpha_ambient": round(u_buoy_theory(), 1),
                      "alpha_film_1100K": round(u_buoy_theory(t_alpha=1100), 1)},
    }
    (APP / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: data[k] for k in ("counts", "check", "anchors", "coverage", "ub_theory")},
                     ensure_ascii=False, indent=1))
    selftest()


if __name__ == "__main__":
    main()
