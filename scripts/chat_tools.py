#!/usr/bin/env python3
"""Alat simulasi & plot untuk asisten chat. Semua keluaran dari model/data repo ini, bertier, dengan selang.

  gravity_flammability  batas O2 batang PMMA pada gravitasi benda langit (scripts/gbridge.py,
                        fit Olson & Ferkul 2017 atas BASS-II + aliran apung ~ g^(1/3)); berlaku hanya
                        sekitar 1 atm dan 13,5-22 % O2 -> di luar itu ditandai EKSTRAPOLASI
  predict_smoke_point   panjang titik asap nyala jet SPICE (scripts/spice_smoke_point.py)
  make_plot             data untuk grafik yang digambar dashboard (bukan gambar rekaan):
                        smoke_point | gravity_loc | tests_o2_pressure
"""
import math
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

BODIES = {"iss": ("ISS (microgravity)", 1e-6), "moon": ("Moon", 1.62 / 9.80665), "mars": ("Mars", 3.71 / 9.80665),
          "earth": ("Earth", 1.0)}


def gravity_flammability(body="moon", o2_pct=21.0, p_kpa=101.3, u_forced_cm_s=0.0):
    import gbridge as gb
    body = str(body or "moon").lower()
    if body not in BODIES:
        return {"error": f"body must be one of {list(BODIES)}"}
    name, g = BODIES[body]
    mid, lo, hi = gb.loc_of_g(g, float(u_forced_cm_s or 0), float(p_kpa), "pmma_rod")
    m = gb.PARAMS["materials"]["pmma_rod"]
    v = m["valid"]
    flags = []
    if not (v["p_kpa"][0] <= p_kpa <= v["p_kpa"][1]):
        flags.append(f"pressure {p_kpa} kPa is outside the fitted range {v['p_kpa'][0]}-{v['p_kpa'][1]} kPa: extrapolation")
    if not (v["o2_pct"][0] <= o2_pct <= v["o2_pct"][1] + 10):
        flags.append(f"oxygen {o2_pct}% is far from the tested {v['o2_pct'][0]}-{v['o2_pct'][1]}%: extrapolation")
    if body in ("moon", "mars"):
        flags.append("no partial-gravity combustion data exist in PSI; gravity enters only through the buoyant-flow scaling")
    verdict = ("burns (oxygen above the whole limit band)" if o2_pct > hi else
               "does not burn (oxygen below the whole limit band)" if o2_pct < lo else "uncertain (oxygen inside the limit band)")
    return {"material": m["label"].replace("Batang", "rod,").strip(), "body": name, "gravity_g": g, "o2_pct": o2_pct, "p_kpa": p_kpa,
            "forced_flow_cm_s": u_forced_cm_s, "limiting_o2_pct": round(mid, 2), "limiting_o2_band_pct": [round(lo, 2), round(hi, 2)],
            "buoyant_flow_cm_s": round(gb.u_buoy(g, p_kpa), 2), "verdict": verdict, "tier": "model_prediction",
            "model": "gbridge_pmma", "formula": "X_lim(a) = X0 + A exp(-a/a_q) + B a, U = U_forced + U_b1 (g/gE)^n (p0/p)^n",
            "parameters_source": m["source"], "band_from": "U_b1 10-30 cm/s and exponent n = 1/3 or 1/2", "flags": flags}


def predict_smoke_point(fuel="propylene", d_mm=1.6, u_cm_s=30.0):
    import spice_smoke_point as sp
    pts, _ = sp.load_points()
    r = sp.predict(pts, str(fuel), float(d_mm), float(u_cm_s))
    r["source"] = "SPICE smoke-point data (SmokePointReview-0g-3.xlsx, 55 points); model validated leave-one-day-out"
    return r


def make_plot(kind="smoke_point", accession=None, fuel=None):
    kind = str(kind or "").lower()
    if kind == "smoke_point":
        import spice_smoke_point as sp
        pts, _ = sp.load_points()
        series = {}
        for p in pts:
            if fuel and sp.fuel_key(fuel) != p["fuel"]:
                continue
            en = {"propane": "propane", "ethylene": "ethylene", "propylene": "propylene",
                  "propylene75": "75% propylene", "propylene50": "50% propylene"}
            key = f"{en.get(p['fuel'], p['fuel'])}, {p['d_mm']:.2f} mm nozzle"
            series.setdefault(key, []).append([round(p["u_air_cm_s"], 2), round(p["L_sp_mm"], 1)])
        summary = {k: {"n": len(v), "coflow_cm_s": [min(q[0] for q in v), max(q[0] for q in v)],
                       "L_sp_mm": [min(q[1] for q in v), max(q[1] for q in v)]} for k, v in series.items()}
        return {"summary": summary, "plot": {"title": "Smoke-point flame length vs coflow (SPICE, ISS)", "x": "coflow velocity (cm/s)",
                         "y": "smoke-point length L_SP (mm)", "series": [{"name": k, "type": "scatter", "points": sorted(v)}
                                                                         for k, v in series.items()],
                         "source": "PSI-107 SmokePointReview-0g-3.xlsx", "tier": "nasa_table"}}
    if kind == "gravity_loc":
        import gbridge as gb
        xs = [10 ** (e / 10) for e in range(-40, 1)]
        mid, lo, hi = [], [], []
        for g in xs:
            m_, l_, h_ = gb.loc_of_g(g, 0.0, gb.P0, "pmma_rod")
            mid.append([g, round(m_, 2)]), lo.append([g, round(l_, 2)]), hi.append([g, round(h_, 2)])
        marks = [[BODIES[b][1], round(gb.loc_of_g(BODIES[b][1], 0.0, gb.P0, "pmma_rod")[0], 2), BODIES[b][0]]
                 for b in ("moon", "mars", "earth")]
        at = {BODIES[b][0]: round(gb.loc_of_g(BODIES[b][1], 0.0, gb.P0, "pmma_rod")[0], 2) for b in ("iss", "moon", "mars", "earth")}
        gmin, vmin = min(mid, key=lambda q: q[1])
        summary = {"limiting_o2_pct_at": at, "minimum": {"g": round(gmin, 4), "limiting_o2_pct": vmin},
                   "shape": "highest in microgravity (radiative quench: too little flow), falls to a minimum near "
                            f"g={gmin:.3g}, then rises slowly toward Earth gravity (blowoff branch)"}
        return {"summary": summary, "plot": {"title": "Limiting O2 for a PMMA rod vs gravity (quiescent air, 1 atm)", "x": "gravity (g / g_Earth)",
                         "y": "limiting oxygen (%)", "log_x": True,
                         "series": [{"name": "band (U_b1 10-30 cm/s, n 1/3-1/2)", "type": "band", "lo": lo, "hi": hi},
                                    {"name": "model", "type": "line", "points": mid},
                                    {"name": "bodies", "type": "labels", "points": marks}],
                         "source": "scripts/gbridge.py (Olson & Ferkul 2017 fit to BASS-II)", "tier": "model_prediction"}}
    if kind == "tests_o2_pressure":
        from kbpaths import gold_db
        c = sqlite3.connect(f"file:{gold_db().as_posix()}?mode=ro", uri=True)
        q = "SELECT accession, o2_mole_frac, pressure_kpa, ignited, outcome FROM tests WHERE o2_mole_frac IS NOT NULL AND pressure_kpa IS NOT NULL"
        args = ()
        if accession:
            q += " AND accession = ?"
            args = (str(accession).upper(),)
        series = {}
        for acc, o2, p, ign, out in c.execute(q, args):
            lab = {"yes": "ignited", "no": "did not ignite"}.get(ign) or (out or "outcome not recorded")
            series.setdefault(lab, []).append([round(o2 * 100, 2), round(p, 1)])
        if not series:
            return {"error": "no tests with both oxygen and pressure for that investigation"}
        summary = {k: {"n": len(v), "o2_pct": [min(q[0] for q in v), max(q[0] for q in v)],
                       "p_kpa": [min(q[1] for q in v), max(q[1] for q in v)]} for k, v in series.items()}
        return {"summary": summary, "plot": {"title": f"Tests by oxygen and pressure{' (' + str(accession).upper() + ')' if accession else ''}",
                         "x": "oxygen (%)", "y": "pressure (kPa)",
                         "series": [{"name": k, "type": "scatter", "points": v[:1500]} for k, v in series.items()],
                         "source": "PSI test tables (freefall.sqlite)", "tier": "nasa_table"}}
    return {"error": "kind must be smoke_point, gravity_loc or tests_o2_pressure"}


if __name__ == "__main__":
    import json
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(gravity_flammability("moon", 30, 70.3), indent=1, ensure_ascii=False))
    print(json.dumps(predict_smoke_point("propylene", 0.762, 30), indent=1, ensure_ascii=False))
    for k in ("smoke_point", "gravity_loc", "tests_o2_pressure"):
        p = make_plot(k)
        print(k, p.get("error") or [(s["name"], len(s.get("points") or s.get("lo") or [])) for s in p["plot"]["series"]][:6])
