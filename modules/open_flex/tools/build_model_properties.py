#!/usr/bin/env python3
"""Build the property table used by the D²-law educational baseline (Phase B M6).

Output: data/model/d2law_properties.json (deterministic; values rounded to 6 significant figures).

Where each number comes from
  * Fluid properties: CoolProp (source S42; Bell et al. 2014), version pinned below. The script refuses to
    run with a different CoolProp version, so the table cannot drift silently.
      - fuels: normal boiling point, latent heat at the boiling point and at 298.15 K, liquid density at 298.15 K
        and at the boiling point. Fuel-vapour properties are NOT tabulated: the CoolProp equations for methanol
        and n-heptane are valid only to 620 K and 600 K, far below flame temperatures.
      - ambient species N2, O2, CO2, He: cp, thermal conductivity, viscosity at 1 atm, 300-2000 K (the
        equations' upper limit is 2000 K for all four).
      - water: latent heat at 298.15 K (to convert higher to lower heating value).
  * Standard enthalpy of combustion of the liquid fuels (liquid water product): cited web sources S43-S45,
    with the spread between sources kept as a range (see DSC-027).
  * Molar masses of the ambient species and stoichiometry: from CoolProp molar masses and the reaction formula.

Nothing here comes from the NASA TP; the TP states only "ambient temperature" (S01 §1, Abstract), so the
ambient temperature 298.15 K is an assumption recorded in the output.

Usage: python3 -I tools/build_model_properties.py [repo-root]
"""
import json
import os
import sys

COOLPROP_VERSION = "8.0.0"
P_ATM = 101325.0
T_GRID = list(range(300, 2001, 50))
T_REF = 298.15


def sig(x, n=6):
    return float(f"{x:.{n}g}")


def main(root):
    import CoolProp
    import CoolProp.CoolProp as CP
    if CoolProp.__version__ != COOLPROP_VERSION:
        sys.exit(f"CoolProp {COOLPROP_VERSION} required (found {CoolProp.__version__}); the property table is pinned to it.")

    species = {}
    for key, name in (("N2", "Nitrogen"), ("O2", "Oxygen"), ("CO2", "CarbonDioxide"), ("He", "Helium")):
        assert CP.PropsSI("Tmax", name) >= T_GRID[-1]
        species[key] = {
            "coolprop_fluid": name,
            "M_kg_mol": sig(CP.PropsSI("M", name)),
            "cp_J_kgK": [sig(CP.PropsSI("C", "T", T, "P", P_ATM, name)) for T in T_GRID],
            "k_W_mK": [sig(CP.PropsSI("L", "T", T, "P", P_ATM, name)) for T in T_GRID],
            "mu_Pa_s": [sig(CP.PropsSI("V", "T", T, "P", P_ATM, name)) for T in T_GRID],
        }

    def hfg_T(name, T):
        return CP.PropsSI("H", "T", T, "Q", 1, name) - CP.PropsSI("H", "T", T, "Q", 0, name)

    hfg_w_298 = hfg_T("Water", T_REF) * CP.PropsSI("M", "Water")  # J/mol

    fuels_in = {
        "methanol": dict(fluid="Methanol", formula="CH3OH", C=1, H=4, O=1,
                         dcH=dict(nominal_kJ_mol=-726.1, range_kJ_mol=[-727.0, -715.0],
                                  sources=[{"source_id": "S44", "locator": "methanol page: -726.1 kJ/mol (computed there from formation enthalpies), -727 kJ/mol (liquid)"},
                                           {"source_id": "S45", "locator": "liquid properties: enthalpy of combustion -715.0 kJ/mol"}],
                                  note="Nominal -726.1 kJ/mol; the -715.0 kJ/mol value differs by 1.5 % (DSC-027) and bounds the sensitivity range.")),
        "heptane": dict(fluid="n-Heptane", formula="C7H16", C=7, H=16, O=0,
                        dcH=dict(nominal_kJ_mol=-4817.0, range_kJ_mol=[-4825.0, -4809.0],
                                 sources=[{"source_id": "S43", "locator": "infobox, Thermochemistry: std enthalpy of combustion -4.825 to -4.809 MJ/mol"}],
                                 note="Nominal is the midpoint of the published range.")),
    }
    M_O2 = CP.PropsSI("M", "Oxygen")
    fuels = {}
    for key, f in fuels_in.items():
        name = f["fluid"]
        M = CP.PropsSI("M", name)
        Tb = CP.PropsSI("T", "P", P_ATM, "Q", 0, name)
        n_O2 = f["C"] + f["H"] / 4 - f["O"] / 2
        n_w = f["H"] / 2
        hfg_f_298 = hfg_T(name, T_REF)

        def Q_of(dcH_kJ_mol):
            # lower heating value of the fuel VAPOUR at 298.15 K (J/kg): |dcH(liquid fuel, liquid water)|
            # minus the latent heat of the product water, plus the fuel's own latent heat at 298.15 K
            return (-dcH_kJ_mol * 1e3 - n_w * hfg_w_298) / M + hfg_f_298

        fuels[key] = {
            "coolprop_fluid": name, "formula": f["formula"], "M_kg_mol": sig(M),
            "T_boil_K": sig(Tb),
            "L_v_at_boil_J_kg": sig(hfg_T(name, Tb)),
            "L_v_298_J_kg": sig(hfg_f_298),
            "rho_l_at_boil_kg_m3": sig(CP.PropsSI("D", "P", P_ATM, "Q", 0, name)),
            "rho_l_298_kg_m3": sig(CP.PropsSI("D", "T", T_REF, "P", P_ATM, name)),
            "nu_O2_per_fuel_mass": sig(n_O2 * M_O2 / M),
            "stoichiometry": f"{f['formula']} + {n_O2:g} O2 -> {f['C']} CO2 + {n_w:g} H2O",
            "dcH_liquid": f["dcH"],
            "Q_lhv_vapour_J_kg": sig(Q_of(f["dcH"]["nominal_kJ_mol"])),
            "Q_lhv_vapour_range_J_kg": sorted(sig(Q_of(v)) for v in f["dcH"]["range_kJ_mol"]),
        }

    out = {
        "record_type": "ModelPropertyTable",
        "model": "d2law-educational-baseline",
        "table_version": "1.0.0",
        "generator": "tools/build_model_properties.py",
        "coolprop_version": COOLPROP_VERSION,
        "evidence_class": "DERIVED",
        "sources": [{"source_id": "S42", "locator": f"CoolProp {COOLPROP_VERSION} PropsSI (reference equations of state and transport correlations)"}],
        "pressure_Pa": P_ATM,
        "T_grid_K": T_GRID,
        "species": species,
        "fuels": fuels,
        "water_L_v_298_J_mol": sig(hfg_w_298),
        "assumptions": [
            "Ambient temperature 298.15 K: the TP says only 'ambient temperature' (S01 Abstract, §1).",
            "Gas properties are those of the ambient gas mixture (fuel vapour and products are not represented); ideal-gas cp and conductivity are taken at 1 atm and treated as pressure-independent.",
            "Droplet surface at the normal boiling point; latent heat and liquid density at the boiling point by default.",
            "Lower heating value of the fuel vapour at 298.15 K; complete combustion to CO2 and H2O.",
        ],
    }
    path = os.path.join(root, "data", "model", "d2law_properties.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write("\n")
    print(path)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
