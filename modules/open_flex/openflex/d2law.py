"""D²-law educational baseline: classical quasi-steady, spherically symmetric droplet burning.

This is the textbook flame-sheet model of Godsave (1953) and Spalding (1953), the classical theory the TP
cites in its introduction (S01 §1). It is an EDUCATIONAL BASELINE, not a FLEX model:
  * no extinction, radiation, soot, finite-rate chemistry, unsteady gas phase, droplet heating,
    variable properties or water absorption by methanol;
  * it is code-verified (tools/verify_d2law.py) but NOT validated against FLEX, and nothing it outputs
    is a FLEX measurement.

Model (constant properties, unity Lewis number, flame sheet, surface at the normal boiling point):
    Y_O,inf = X_O2 M_O2 / sum(X_i M_i)
    B       = [cp (T_inf - T_s) + Q Y_O,inf / nu] / L
    K       = 8 k / (rho_l cp) * ln(1 + B)                    d(D²)/dt = -K
    r_f/r_s = ln(1 + B) / ln(1 + Y_O,inf / nu)
    T_f     = T_s + (L / cp) [(1 + B) / (1 + Y_O,inf / nu) - 1]
Gas cp and k are those of the ambient mixture at T_prop. By default T_prop = (T_s + T_f)/2 found by
fixed-point iteration; T_prop is limited to the property table (300–2000 K) and the limit is flagged.
The derivation, with the profiles the verification checks, is in docs/PHASE_B_M6_D2law_Model.md.
"""
import bisect
import math

MODEL_NAME = "d2law-educational-baseline"
MODEL_VERSION = "1.0.0"
SPECIES = ("O2", "N2", "CO2", "He")


def interp(grid, values, T):
    """Linear interpolation on an ascending grid; T must lie inside the grid."""
    if not grid[0] <= T <= grid[-1]:
        raise ValueError(f"T={T} outside property table {grid[0]}–{grid[-1]} K")
    i = min(max(bisect.bisect_right(grid, T) - 1, 0), len(grid) - 2)
    w = (T - grid[i]) / (grid[i + 1] - grid[i])
    return values[i] + w * (values[i + 1] - values[i])


def mole_fractions(X):
    """Normalise the printed mole fractions (O2, N2, CO2, He); returns (x, sum_before_normalising)."""
    s = sum(X.get(k) or 0.0 for k in SPECIES)
    if s <= 0:
        raise ValueError("no ambient composition")
    return {k: (X.get(k) or 0.0) / s for k in SPECIES}, s


def ambient_mass_fractions(table, x):
    Mi = {k: table["species"][k]["M_kg_mol"] for k in SPECIES}
    Mmix = sum(x[k] * Mi[k] for k in SPECIES)
    return {k: x[k] * Mi[k] / Mmix for k in SPECIES}


def mixture_cp_k(table, x, T):
    """Ideal-gas mixture cp (mass-fraction weighted) and conductivity (Wassiljewa equation with the
    Mason–Saxena interaction parameters built from the pure-species viscosities; S46, S47)."""
    grid = table["T_grid_K"]
    sp = [k for k in SPECIES if x[k] > 0]
    M = {k: table["species"][k]["M_kg_mol"] for k in sp}
    cp = {k: interp(grid, table["species"][k]["cp_J_kgK"], T) for k in sp}
    kk = {k: interp(grid, table["species"][k]["k_W_mK"], T) for k in sp}
    mu = {k: interp(grid, table["species"][k]["mu_Pa_s"], T) for k in sp}
    Y = ambient_mass_fractions(table, {k: x[k] for k in SPECIES})
    cp_mix = sum(Y[k] * cp[k] for k in sp)
    k_mix = 0.0
    for i in sp:
        den = 0.0
        for j in sp:
            phi = (1 + math.sqrt(mu[i] / mu[j]) * (M[j] / M[i]) ** 0.25) ** 2 / math.sqrt(8 * (1 + M[i] / M[j]))
            den += x[j] * phi
        k_mix += x[i] * kk[i] / den
    return cp_mix, k_mix


def solve(inputs, table, tol=1e-9, max_iter=200):
    """Evaluate the model. inputs: fuel ('methanol'|'heptane'), X {O2,N2,CO2,He}, D0_mm (or None),
    T_inf_K, optional T_prop_K (fixed property temperature), rho_l_at ('boil'|'298'), Q_variant
    ('nominal'|'low'|'high'). Returns a dict of outputs and flags."""
    f = table["fuels"][inputs["fuel"]]
    flags = []
    x, xsum = mole_fractions(inputs["X"])
    if abs(xsum - 1) > 1e-6:
        flags.append(f"mole fractions summed to {xsum:.4f}; normalised")
    Y = ambient_mass_fractions(table, x)
    YO = Y["O2"]
    nu = f["nu_O2_per_fuel_mass"]
    Ts, L = f["T_boil_K"], f["L_v_at_boil_J_kg"]
    rho_l = f["rho_l_at_boil_kg_m3"] if inputs.get("rho_l_at", "boil") == "boil" else f["rho_l_298_kg_m3"]
    qv = inputs.get("Q_variant", "nominal")
    Q = {"nominal": f["Q_lhv_vapour_J_kg"], "low": f["Q_lhv_vapour_range_J_kg"][0], "high": f["Q_lhv_vapour_range_J_kg"][1]}[qv]
    Tinf = inputs["T_inf_K"]
    grid = table["T_grid_K"]
    lo, hi = grid[0], grid[-1]

    def at(Tp):
        cp, k = mixture_cp_k(table, x, Tp)
        B = (cp * (Tinf - Ts) + Q * YO / nu) / L
        Tf = Ts + (L / cp) * ((1 + B) / (1 + YO / nu) - 1) if B > 0 else None
        return cp, k, B, Tf

    fixed = inputs.get("T_prop_K")
    it = 0
    if fixed is not None:
        Tp = float(fixed)
        cp, k, B, Tf = at(Tp)
    else:
        Tp = 1000.0
        while True:
            it += 1
            cp, k, B, Tf = at(Tp)
            target = (Ts + Tf) / 2 if Tf is not None else lo
            new = min(max(target, lo), hi)
            if abs(new - Tp) < tol or it >= max_iter:
                Tp = new
                cp, k, B, Tf = at(Tp)
                break
            Tp = new
        if it >= max_iter:
            flags.append("property-temperature iteration did not converge")
        if Tf is not None and not lo <= (Ts + Tf) / 2 <= hi:
            flags.append("property temperature limited to the table range")
    out = {"Y_O2_inf": YO, "x_normalised": x, "nu": nu, "T_s_K": Ts, "L_J_kg": L, "rho_l_kg_m3": rho_l, "Q_J_kg": Q,
           "T_prop_K": Tp, "cp_J_kgK": cp, "k_W_mK": k, "B": B, "iterations": it, "flags": flags}
    if B <= 0:
        flags.append("B <= 0: no burning in this model (outside scope)")
        out.update(K_mm2_s=None, flame_standoff_ratio=None, T_flame_K=None, t_burn_s=None)
        return out
    K = 8 * k / (rho_l * cp) * math.log1p(B) * 1e6
    out.update(K_mm2_s=K, ln1pB=math.log1p(B), T_flame_K=Tf,
               flame_standoff_ratio=math.log1p(B) / math.log1p(YO / nu) if YO > 0 else None)
    D0 = inputs.get("D0_mm")
    out["t_burn_s"] = D0 * D0 / K if D0 else None
    return out


def d2_curve(D0_mm, K_mm2_s, t):
    """D²(t) = D0² - K t, floored at zero (closed form of the model)."""
    return [max(D0_mm * D0_mm - K_mm2_s * ti, 0.0) for ti in t]


def profiles(B, YO, nu, Ts, Tinf, L, cp, Q, r_s=1.0):
    """Closed-form radial profiles of the flame-sheet solution (used by the code verification).
    Lengths are in units of r_s; lam = mdot/(4 pi rho D) = r_s ln(1+B)."""
    lam = r_s * math.log1p(B)
    r_f = lam / math.log1p(YO / nu)

    def YF(r):  # fuel, r_s <= r <= r_f
        return 1 - math.exp(lam / r_f - lam / r)

    def YOx(r):  # oxidizer, r >= r_f
        return -nu + (YO + nu) * math.exp(-lam / r)

    def T(r):
        if r <= r_f:
            return Ts + (L / cp) * (math.exp(lam / r_s - lam / r) - 1)
        return Ts - L / cp + Q / cp + (Tinf - Ts + (L - Q) / cp) * math.exp(-lam / r)

    return lam, r_f, YF, YOx, T
