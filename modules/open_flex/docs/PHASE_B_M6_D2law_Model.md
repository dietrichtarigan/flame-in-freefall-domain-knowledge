# D²-law educational baseline — model, properties, code verification

Model version 1.0.0 (`openflex/d2law.py`; browser port `app/src/js/60_model.js`). Status: **EDUCATIONAL_BASELINE**.
It is code-verified, **not validated** against FLEX, and nothing it outputs is a FLEX measurement. Prepared by Claude
(AI assistant), 15 Nov 2026. Not a NASA product.

## 1. Why this model

The TP introduces spherically symmetric droplet burning as the classical problem of Godsave, Hall and Diederichsen,
and Spalding (CLM-051). It gives no model equations itself. The quasi-steady flame-sheet theory is the simplest
model that can be set from the printed conditions with no adjustable parameters. Comparing it with the printed
values shows how far classical theory is from FLEX. That is its teaching purpose.

## 2. Equations

Assumptions:
- spherical symmetry and quasi-steady gas phase;
- constant gas properties and unity Lewis number;
- infinitely fast chemistry, so the flame is a sheet;
- droplet surface at the normal boiling point;
- no radiation, soot or droplet heating;
- ambient at 298.15 K (CLM-052).

Symbols: ṁ is the evaporation rate; λ = ṁ/(4πρD) = ṁc_p/(4πk).

| Quantity | Expression |
|---|---|
| Ambient O₂ mass fraction | Y_O∞ = X_O₂ M_O₂ / Σ X_i M_i (printed mole fractions, normalised if they do not sum to 1) |
| Transfer number | B = [c_p (T∞ − T_s) + Q Y_O∞ / ν] / L |
| Burning-rate constant | K = 8 k ln(1 + B) / (ρ_l c_p), so d(D²)/dt = −K |
| Flame standoff ratio | r_f / r_s = ln(1 + B) / ln(1 + Y_O∞ / ν) |
| Flame temperature | T_f = T_s + (L / c_p) [(1 + B)/(1 + Y_O∞/ν) − 1] |
| Fuel, r_s ≤ r ≤ r_f | Y_F = 1 − exp(λ/r_f − λ/r) |
| Oxidizer, r ≥ r_f | Y_O = −ν + (Y_O∞ + ν) exp(−λ/r) |
| Temperature, inside | T = T_s + (L/c_p)[exp(λ/r_s − λ/r) − 1] |
| Temperature, outside | T = T_s + (Q − L)/c_p + [T∞ − T_s + (L − Q)/c_p] exp(−λ/r) |

**Derivation in brief.** Each scalar φ obeys ṁφ − 4πr²ρD dφ/dr = constant, so φ = C₁ + C₂ exp(−λ/r). Six
conditions fix B, r_f and the constants:
- fuel flux equals ṁ inside the flame, and oxidizer flux equals −νṁ outside;
- Y_F(r_f) = Y_O(r_f) = 0;
- T(r_s) = T_s and T(∞) = T∞;
- T is continuous at r_f.

The surface energy balance (conduction in = ṁL) and the flame jump conditions then follow. Code-verification
checks CV-01 to CV-04 test exactly these.

**Gas properties** are those of the *ambient* mixture (O₂, N₂, CO₂, He) at a property temperature T_prop:
- c_p is mass-weighted;
- k uses the Wassiljewa equation with Mason–Saxena/Wilke interaction parameters from viscosities (S46, S47).

By default T_prop = (T_s + T_f)/2, found by fixed-point iteration (CV-06) and limited to the table range 300–2000 K;
the limit is flagged. Fuel-vapour properties are not used, because CoolProp's methanol and n-heptane equations
stop at 620 K and 600 K. Pressure is not an input: with ideal-gas k and c_p the model has no pressure dependence.

## 3. Property table (`data/model/d2law_properties.json`, DS-MODEL-D2LAW-PROPS)

| Item | Source | Notes |
|---|---|---|
| T_boil, L at T_boil and at 298.15 K, ρ_l at T_boil and at 298.15 K | CoolProp 8.0.0 (S42) | 1 atm; CLM-053 |
| c_p, k, μ of N₂, O₂, CO₂, He, 300–2000 K | CoolProp 8.0.0 (S42) | 50 K grid, linear interpolation |
| ΔcH° (liquid fuel, liquid water) | n-heptane −4825 to −4809 kJ/mol (S43); methanol −726.1 kJ/mol (S44), −715.0 kJ/mol in S45 | tertiary sources; DSC-027; the range sets the low/high heating-value option |
| Q (lower heating value of the fuel vapour at 298.15 K) | computed: (−ΔcH − n_H₂O L_w,298)/M + L_fuel,298 | water latent heat from CoolProp |
| ν (O₂ to fuel mass ratio) | stoichiometry | CH₃OH + 1.5 O₂; C₇H₁₆ + 11 O₂ |

The generator `tools/build_model_properties.py` refuses any CoolProp version other than 8.0.0. A unit test
regenerates the table and compares it byte for byte.

## 4. Code verification (`tools/verify_d2law.py`, DS-VER-D2LAW-CODE): 24/24 PASS

| ID | What is checked | Result |
|---|---|---|
| CV-01 | Conserved fluxes have zero derivative (finite differences), inside and outside the flame; 4 fuel/atmosphere cases | residual ≤ 2.5·10⁻⁸ |
| CV-02 | Y_F(r_f)=0, Y_O(r_f)=0, Y_O(∞), T(r_s), T continuous at r_f, T(∞) | ≤ 2.9·10⁻⁷ |
| CV-03 | Surface energy balance | ≤ 3.2·10⁻⁷ relative |
| CV-04 | Flame jump: oxidizer flux = ν × fuel flux; heat released = Q × fuel flux; all fuel consumed | ≤ 2.0·10⁻⁷ relative |
| CV-05 | RK4 integration of dR/dt = −k ln(1+B)/(ρ_l c_p R) converges to the closed form | observed order 3.88 (fourth-order method) |
| CV-06 | Property-temperature fixed point | ≤ 10⁻¹⁰ K |
| CV-07 | Pressure not an input; scaling mole fractions has no effect; K rises with X_O₂; single-species mixture and table nodes reproduced | exact |
| CV-08 | Hand calculation with separate code (heptane in air, T_prop = 1500 K): K = 2.2264 mm²/s, B = 9.118, T_f = 2575.8 K, r_f/r_s = 36.05 | agreement 1.6·10⁻¹⁵ |

**The checks can fail.** Unit tests inject three defects into the model and confirm that the record turns to FAIL:
- a 1 % conductivity error;
- a wrong outer temperature profile;
- 7 instead of 8 in K.

**The browser port matches.** It reproduces the Python outputs (relative difference < 10⁻⁵, the 6-figure storage
precision) and the run identifiers for all 276 Table IX tests.

## 5. Comparison with Table IX (DS-ANA-D2LAW-VS-IX) — a comparison, not validation

At each test's printed conditions, the model K exceeds the printed K for **every** test with both values (CLM-057):

| Fuel | Tests with both values | Model/printed: min · median · max |
|---|---|---|
| Methanol | 151 | 1.46 · 2.1 · 3.9 |
| n-heptane | 109 | 1.7 · 4.3 · 30.9 |

The largest ratio is FLEX-130, with a printed K of .05 mm²/s. The model's flame standoff ratio for heptane in air
(≈ 36) is far above the digitized flame-to-droplet diameter ratios for FLEX-035 between 1 and 8.5 s:
- LLUV: 5.0–11.1, median 8.2;
- colour camera: 3.6–8.9, median 6.7.

These ratios use the DIGITIZED series with the droplet D² median within ±0.25 s; they are not printed values.
The gap is a comparison only; its causes are not quantified here.

**Model-form sensitivity** (heptane and methanol in air, D₀ = 3 mm; not an uncertainty interval):

| Changed choice | Heptane K | Methanol K |
|---|---|---|
| Property temperature fixed at 600 K | −41 % | −40 % |
| Property temperature fixed at 2000 K | +22 % | +24 % |
| Heating value at the ends of the source range | ±0.1 % | −1.7 % / +0.1 % |
| Liquid density at 298.15 K instead of T_boil | −9.6 % | −4.8 % |

The property-evaluation choice dominates. The heats of combustion matter least.

## 6. What the model cannot do

- extinction (radiative or diffusive), and therefore the FLEX extinction diameters;
- cool-flame burning (FLEX-035's caption reports it);
- soot, radiation, unsteady gas phase, droplet heating;
- fuel-vapour and product properties;
- water uptake by methanol;
- pressure effects;
- the ignition transient.

The model's time axis starts at t = 0 with D = D₀; the digitized data use igniter ON as t = 0.
