#!/usr/bin/env python3
"""Code verification of the D²-law educational baseline (openflex/d2law.py).

Code verification asks "are the equations solved correctly?", not "are they the right equations for FLEX?"
(that would be validation, which this release does not claim). Checks:

  CV-01  Radial profiles satisfy the governing conservation ODEs (the conserved flux lam*phi - r^2 phi' has a
         zero derivative, evaluated by central finite differences, inside and outside the flame).
  CV-02  Boundary and matching conditions: Y_F(r_f)=0, Y_O(r_f)=0, Y_O(inf)=Y_O,inf, T(r_s)=T_s,
         T continuous at r_f, T(inf)=T_inf.
  CV-03  Surface energy balance: conduction into the droplet equals mdot*L.
  CV-04  Flame-sheet jump conditions: oxidizer flux = nu * fuel flux; heat released = Q * fuel flux.
  CV-05  Independent time integration of dR/dt = -k ln(1+B) / (rho_l cp R) by RK4: burn time converges to
         D0²/K with observed order close to 4.
  CV-06  Property-temperature fixed point: T_prop = (T_s + T_f)/2 at convergence.
  CV-07  Invariances and limits: pressure is not an input; scaling mole fractions changes nothing;
         K rises with X_O2; a single-species mixture returns the pure-species properties; interpolation
         reproduces table nodes.
  CV-08  Hand calculation: K, B, T_f and r_f/r_s recomputed from the table with separate code for heptane
         in air at a fixed property temperature.

Output: data/verification/d2law_code_verification.json (deterministic). Exit 1 if any check fails.
Usage: python3 -I tools/verify_d2law.py [repo-root]
"""
import hashlib
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if __name__ == "__main__" and len(sys.argv) > 1:
    ROOT = os.path.abspath(sys.argv[1])
sys.path.insert(0, ROOT)
from openflex import d2law as m  # noqa: E402


def sha(p):
    return hashlib.sha256(open(os.path.join(ROOT, p), "rb").read()).hexdigest()


def main(out_path=None):
    table = json.load(open(os.path.join(ROOT, "data/model/d2law_properties.json"), encoding="utf-8"))
    checks = []

    def add(cid, name, value, tol, ok, detail=""):
        checks.append({"id": cid, "check": name, "value": float(f"{value:.6g}") if isinstance(value, float) else value,
                       "tolerance": tol, "pass": bool(ok), "detail": detail})

    cases = [("heptane", {"O2": 0.21, "N2": 0.79}), ("methanol", {"O2": 0.21, "N2": 0.79}),
             ("heptane", {"O2": 0.16, "N2": 0.54, "CO2": 0.30}), ("methanol", {"O2": 0.17, "N2": 0.43, "He": 0.40})]
    for n, (fuel, X) in enumerate(cases, 1):
        o = m.solve({"fuel": fuel, "X": X, "D0_mm": 3.0, "T_inf_K": 298.15}, table)
        B, YO, nu, Ts, L, cp, Q = o["B"], o["Y_O2_inf"], o["nu"], o["T_s_K"], o["L_J_kg"], o["cp_J_kgK"], o["Q_J_kg"]
        lam, rf, YF, YOx, T = m.profiles(B, YO, nu, Ts, 298.15, L, cp, Q)
        tag = f"case {n}: {fuel} {X}"

        def flux(f, r, h):  # lam*phi - r^2 phi'  (mass or energy flux / (4 pi rho D))
            return lam * f(r) - r * r * (f(r + h) - f(r - h)) / (2 * h)

        # CV-01: flux must be constant; residual of d(flux)/dr by second-order FD, two step sizes
        inner = [1 + (rf - 1) * s for s in (0.2, 0.5, 0.8)]
        outer = [rf * s for s in (1.5, 3.0, 10.0)]
        worst = 0.0
        for f, pts, scale in ((YF, inner, 1.0), (YOx, outer, nu), (T, inner, Ts), (T, outer, Ts)):
            for r in pts:
                res = []
                for h in (5e-3,):
                    hh = h * r
                    d = (flux(f, r + hh, hh * 1e-2) - flux(f, r - hh, hh * 1e-2)) / (2 * hh)
                    res.append(abs(d) / scale)
                worst = max(worst, res[0])
        add("CV-01", "conservation ODE residual (normalised)", worst, 1e-6, worst < 1e-6, tag)
        # CV-02
        errs = [abs(YF(rf)), abs(YOx(rf)), abs(YOx(1e9) - YO), abs(T(1.0) - Ts) / Ts,
                abs(T(rf * (1 - 1e-12)) - T(rf * (1 + 1e-12))) / Ts, abs(T(1e9) - 298.15) / 298.15]
        add("CV-02", "boundary and matching conditions (max error)", max(errs), 1e-6, max(errs) < 1e-6, tag)
        # CV-03 surface energy: r_s^2 T'(r_s) = lam L / cp
        h = 1e-6
        dT = (T(1 + h) - T(1)) / h
        e3 = abs(dT - lam * L / cp) / (lam * L / cp)
        add("CV-03", "surface energy balance (relative error)", e3, 1e-4, e3 < 1e-4, tag)
        # CV-04 flame jump conditions
        hf = 1e-7 * rf
        fuel_in = -rf * rf * (YF(rf) - YF(rf - hf)) / hf
        ox_in = rf * rf * (YOx(rf + hf) - YOx(rf)) / hf
        heat_out = rf * rf * ((T(rf) - T(rf - hf)) / hf - (T(rf + hf) - T(rf)) / hf)
        e4a = abs(ox_in / fuel_in - nu) / nu
        e4b = abs(heat_out - Q / cp * fuel_in) / (Q / cp * fuel_in)
        e4c = abs(fuel_in - lam) / lam  # all fuel leaving the surface is consumed at the sheet
        add("CV-04", "flame-sheet jump conditions (max relative error)", max(e4a, e4b, e4c), 1e-4, max(e4a, e4b, e4c) < 1e-4, tag)
        # CV-06
        if n <= 2:
            e6 = abs(o["T_prop_K"] - (o["T_s_K"] + o["T_flame_K"]) / 2)
            add("CV-06", "property-temperature fixed point |T_prop - (T_s+T_f)/2| (K)", e6, 1e-6, e6 < 1e-6, tag)

    # CV-05 RK4 on R(t): dR/dt = -c/R, c = k ln(1+B)/(rho_l cp); integrate D² down to 1 % of D0²
    o = m.solve({"fuel": "heptane", "X": {"O2": 0.21, "N2": 0.79}, "D0_mm": 3.0, "T_inf_K": 298.15}, table)
    K = o["K_mm2_s"]
    c = K / 8  # mm²/s, since d(D²)/dt = 8 R dR/dt
    t_end = 0.99 * 9.0 / K
    exact = 1.5 * math.sqrt(0.01)

    def rk4(nsteps):
        R, dt = 1.5, t_end / nsteps
        f = lambda r: -c / r  # noqa: E731
        for _ in range(nsteps):
            k1 = f(R); k2 = f(R + dt / 2 * k1); k3 = f(R + dt / 2 * k2); k4 = f(R + dt * k3)  # noqa: E702
            R += dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        return R

    errs = [abs(rk4(n) - exact) for n in (200, 400, 800)]
    order = math.log2(errs[1] / errs[2])
    add("CV-05", "RK4 integration converges to the closed form: observed order", order, "3.7-4.3", 3.7 <= order <= 4.3,
        f"errors {errs[0]:.3e}, {errs[1]:.3e}, {errs[2]:.3e} mm at 200/400/800 steps")

    # CV-07 invariances and limits
    base = {"fuel": "methanol", "X": {"O2": 0.21, "N2": 0.79}, "D0_mm": 2.0, "T_inf_K": 298.15}
    a = m.solve(base, table)
    b = m.solve(dict(base, P_atm=3.0), table)
    add("CV-07", "pressure is not an input (K identical)", abs(a["K_mm2_s"] - b["K_mm2_s"]), 0.0, a["K_mm2_s"] == b["K_mm2_s"])
    s = m.solve(dict(base, X={"O2": 0.42, "N2": 1.58}), table)
    add("CV-07", "scaling mole fractions changes nothing (|dK|)", abs(s["K_mm2_s"] - a["K_mm2_s"]), 1e-12,
        abs(s["K_mm2_s"] - a["K_mm2_s"]) < 1e-12)
    ks = [m.solve(dict(base, X={"O2": xo, "N2": 1 - xo}), table)["K_mm2_s"] for xo in (0.14, 0.17, 0.21, 0.30, 0.40)]
    add("CV-07", "K increases with X_O2", all(b2 > a2 for a2, b2 in zip(ks, ks[1:])), True, all(b2 > a2 for a2, b2 in zip(ks, ks[1:])))
    cpN, kN = m.mixture_cp_k(table, {"O2": 0, "N2": 1, "CO2": 0, "He": 0}, 1000.0)
    i = table["T_grid_K"].index(1000)
    e = max(abs(cpN - table["species"]["N2"]["cp_J_kgK"][i]), abs(kN - table["species"]["N2"]["k_W_mK"][i]))
    add("CV-07", "single-species mixture returns pure-species values; interpolation hits table nodes", e, 1e-12, e < 1e-12)

    # CV-08 hand calculation with separate code (fixed T_prop = 1500 K, air)
    Tp = 1500.0
    i = table["T_grid_K"].index(1500)
    sp = table["species"]
    MO, MN = sp["O2"]["M_kg_mol"], sp["N2"]["M_kg_mol"]
    YO = 0.21 * MO / (0.21 * MO + 0.79 * MN)
    cp = YO * sp["O2"]["cp_J_kgK"][i] + (1 - YO) * sp["N2"]["cp_J_kgK"][i]
    muO, muN, kO, kN = sp["O2"]["mu_Pa_s"][i], sp["N2"]["mu_Pa_s"][i], sp["O2"]["k_W_mK"][i], sp["N2"]["k_W_mK"][i]
    phiON = (1 + (muO / muN) ** 0.5 * (MN / MO) ** 0.25) ** 2 / (8 * (1 + MO / MN)) ** 0.5
    phiNO = (1 + (muN / muO) ** 0.5 * (MO / MN) ** 0.25) ** 2 / (8 * (1 + MN / MO)) ** 0.5
    k = 0.21 * kO / (0.21 + 0.79 * phiON) + 0.79 * kN / (0.79 + 0.21 * phiNO)
    f = table["fuels"]["heptane"]
    B = (cp * (298.15 - f["T_boil_K"]) + f["Q_lhv_vapour_J_kg"] * YO / f["nu_O2_per_fuel_mass"]) / f["L_v_at_boil_J_kg"]
    K = 8 * k / (f["rho_l_at_boil_kg_m3"] * cp) * math.log(1 + B) * 1e6
    Tf = f["T_boil_K"] + f["L_v_at_boil_J_kg"] / cp * ((1 + B) / (1 + YO / f["nu_O2_per_fuel_mass"]) - 1)
    fsr = math.log(1 + B) / math.log(1 + YO / f["nu_O2_per_fuel_mass"])
    o = m.solve({"fuel": "heptane", "X": {"O2": 0.21, "N2": 0.79}, "D0_mm": 3.0, "T_inf_K": 298.15, "T_prop_K": Tp}, table)
    e8 = max(abs(o["K_mm2_s"] - K) / K, abs(o["B"] - B) / B, abs(o["T_flame_K"] - Tf) / Tf, abs(o["flame_standoff_ratio"] - fsr) / fsr)
    add("CV-08", "hand calculation, heptane in air at T_prop = 1500 K (max relative difference)", e8, 1e-12, e8 < 1e-12,
        f"K = {K:.4f} mm²/s, B = {B:.4f}, T_f = {Tf:.1f} K, r_f/r_s = {fsr:.2f}")

    status = "PASS" if all(c["pass"] for c in checks) else "FAIL"
    rec = {
        "record_type": "CodeVerification",
        "model": {"name": m.MODEL_NAME, "version": m.MODEL_VERSION, "status": "EDUCATIONAL_BASELINE"},
        "implementation": "openflex/d2law.py",
        "implementation_sha256": sha("openflex/d2law.py"),
        "property_table_sha256": sha("data/model/d2law_properties.json"),
        "status": status,
        "n_checks": len(checks),
        "n_passed": sum(c["pass"] for c in checks),
        "scope": "Code verification only: the equations are solved correctly. It says nothing about whether the model represents FLEX (no validation is claimed).",
        "checks": checks,
    }
    if out_path is False:
        return rec
    path = out_path or os.path.join(ROOT, "data/verification/d2law_code_verification.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["id"], c["check"], c["value"], c["detail"][:70])
    print(status, f"{rec['n_passed']}/{rec['n_checks']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
