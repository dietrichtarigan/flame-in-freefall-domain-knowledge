/**
 * What-if: simulator dari mode peneliti (/app/) dan jembatan-g (/gbridge/),
 * kini di FLARE+. Semua angka adalah prediksi model bertier, dengan selang dan
 * penanda ekstrapolasi; uji nyata terdekat selalu ditampilkan di sebelahnya.
 *   CFI-G  -> /whatif/cfig   (P menyala, nyala gas ACME)
 *   FLEX   -> /whatif/flex   (P padam + konstanta laju bakar K, droplet)
 *   Gravity-> /gravity       (batas O2 batang PMMA di ISS/Bulan/Mars/Bumi)
 *   SPICE  -> /smokepoint    (panjang titik asap nyala jet)
 */
import React, { useEffect, useState } from "react";
import { API } from "./api";
import { EvidenceBadge, PageTitle, Panel, pct, useJSON } from "./ui";
import { en } from "./i18n";
import { PlotView } from "./chatRender";
import { TEX, Tex, plainFormulaToTex } from "./math";

function useDebounced<T>(value: T, ms = 250) {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function Slider({ label, value, min, max, step, onChange, fmt }: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  fmt?: (v: number) => string;
}) {
  return (
    <label className="sim-slider">
      <span>
        {label} <b>{fmt ? fmt(value) : value}</b>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </label>
  );
}

function Choice<T extends string>({ label, value, options, onChange }: {
  label: string;
  value: T;
  options: [T, string][];
  onChange: (v: any) => void;
}) {
  return (
    <div className="sim-choice" role="group" aria-label={label}>
      <span>{label}</span>
      <div className="segmented">
        {options.map(([k, l]) => (
          <button key={k} className={k === value ? "active" : ""} onClick={() => onChange(k)} aria-pressed={k === value}>
            {l}
          </button>
        ))}
      </div>
    </div>
  );
}

function Prob({ label, p, valid, sigma }: { label: string; p: number | null | undefined; valid: boolean; sigma?: number | null }) {
  if (!valid || p == null)
    return (
      <div className="sim-result warn">
        <strong>Model does not answer here</strong>
        <small>These inputs are outside the range NASA tested, so no number is shown.</small>
      </div>
    );
  return (
    <div className="sim-result">
      <span>{label}</span>
      <strong>{p.toFixed(2)}</strong>
      <i className="prob-bar">
        <em style={{ width: `${p * 100}%` }} />
      </i>
      {sigma != null && <small>latent uncertainty σ = {sigma}</small>}
      <EvidenceBadge tier="model_prediction" />
    </div>
  );
}

export function WhatIf() {
  return (
    <div className="page">
      <PageTitle
        index="06"
        overline="PREDICTIVE MODELLING"
        title="What-if Simulator"
        description="Move the conditions and see what models trained on NASA's ISS tests predict, with uncertainty, the tested range, and the real tests closest to your inputs. Outside the tested range the models refuse to answer."
      />
      <div className="sim-grid">
        <GravitySim />
        <SmokeSim />
        <CfigSim />
        <FlexSim />
      </div>
    </div>
  );
}

function GravitySim() {
  const [body, setBody] = useState<"iss" | "moon" | "mars" | "earth">("moon");
  const [o2, setO2] = useState(30);
  const [p, setP] = useState(70.3);
  const [u, setU] = useState(0);
  const q = useDebounced(`${API}/gravity?body=${body}&o2=${o2}&p_kpa=${p}&u=${u}`);
  const r = useJSON<any>(q);
  const curve = useJSON<any>(`${API}/plot/gravity_loc`);
  const d = r.data;
  return (
    <Panel title="Gravity bridge · will a solid burn?" meta="PMMA ROD · BASS-II FIT" className="sim-panel wide">
      <div className="sim-body">
        <div className="sim-controls">
          <Choice label="Where" value={body} onChange={setBody}
            options={[["iss", "ISS"], ["moon", "Moon"], ["mars", "Mars"], ["earth", "Earth"]]} />
          <Slider label="Oxygen" value={o2} min={14} max={40} step={0.5} onChange={setO2} fmt={(v) => `${v}%`} />
          <Slider label="Pressure" value={p} min={20} max={105} step={0.5} onChange={setP} fmt={(v) => `${v} kPa`} />
          <Slider label="Forced air flow" value={u} min={0} max={30} step={1} onChange={setU} fmt={(v) => `${v} cm/s`} />
          <p className="chart-note">Moon/Mars base design point: 30% O₂ at 70.3 kPa (10.2 psi), from the challenge brief.</p>
        </div>
        <div className="sim-out">
          {d && !d.error ? (
            <>
              <div className={`sim-result ${/does not/.test(d.verdict) ? "ok" : /burns/.test(d.verdict) ? "bad" : "warn"}`}>
                <span>Verdict at {d.o2_pct}% O₂ on {d.body}</span>
                <strong>{d.verdict}</strong>
                <small>
                  Limiting oxygen {d.limiting_o2_pct}% (band {d.limiting_o2_band_pct[0]}–{d.limiting_o2_band_pct[1]}%) ·
                  buoyant flow {d.buoyant_flow_cm_s} cm/s
                </small>
                <EvidenceBadge tier="model_prediction" />
              </div>
              {(d.flags ?? []).map((f: string, i: number) => (
                <p key={i} className="sim-flag">⚠ {en(f)}</p>
              ))}
              <Tex src={TEX.gravity} caption="Limiting oxygen as a function of the effective flow a past the sample; the buoyant part of that flow scales with gravity and pressure. Parameters: Olson & Ferkul (2017) fit to BASS-II. Uncertainty band: buoyant flow 10–30 cm/s at 1 g, exponent n = 1/3 or 1/2." />
            </>
          ) : (
            <p className="chart-note">{r.loading ? "Computing…" : r.error || d?.error}</p>
          )}
          {curve.data?.plot && <PlotView plot={curve.data.plot} />}
        </div>
      </div>
    </Panel>
  );
}

function SmokeSim() {
  const [fuel, setFuel] = useState("propylene");
  const [dmm, setD] = useState(1.6);
  const [u, setU] = useState(30);
  const r = useJSON<any>(useDebounced(`${API}/smokepoint?fuel=${fuel}&d_mm=${dmm}&u=${u}`));
  const plot = useJSON<any>(`${API}/plot/smoke_point`);
  const d = r.data;
  return (
    <Panel title="Smoke point of a jet flame" meta="SPICE · ISS" className="sim-panel wide">
      <div className="sim-body">
        <div className="sim-controls">
          <label className="sim-select">
            Fuel
            <select value={fuel} onChange={(e) => setFuel(e.target.value)}>
              <option value="ethylene">ethylene</option>
              <option value="propane">propane</option>
              <option value="propylene">propylene</option>
              <option value="propylene75">75% propylene</option>
              <option value="propylene50">50% propylene</option>
            </select>
          </label>
          <Choice label="Nozzle" value={String(dmm)} onChange={(v) => setD(+v)}
            options={[["0.41", "0.41 mm"], ["0.76", "0.76 mm"], ["1.6", "1.6 mm"]]} />
          <Slider label="Co-flow air speed" value={u} min={5} max={65} step={1} onChange={setU} fmt={(v) => `${v} cm/s`} />
          <p className="chart-note">The smoke point is the flame length at which soot starts to escape: a detector-relevant property.</p>
        </div>
        <div className="sim-out">
          {d && !d.error ? (
            <>
              <div className={`sim-result ${d.status === "ekstrapolasi" ? "warn" : ""}`}>
                <span>Smoke-point flame length · {d.status === "ekstrapolasi" ? "extrapolation" : "inside the tested range"}</span>
                <strong>{d.L_sp_mm} mm</strong>
                <small>{d.interval_level_pct ?? 90}% interval {d.PI90_mm?.[0]}–{d.PI90_mm?.[1]} mm</small>
                <EvidenceBadge tier="model_prediction" />
              </div>
              {(d.flags ?? []).map((f: string, i: number) => (
                <p key={i} className="sim-flag">⚠ {en(f)}</p>
              ))}
              <Tex src={TEX.smoke} caption="Power law fitted to 55 SPICE smoke points (ISS), with a Gaussian-process correction on the residual; validated leaving one test day out." />
            </>
          ) : (
            <p className="chart-note">{r.loading ? "Computing…" : r.error || d?.error}</p>
          )}
          {plot.data?.plot && <PlotView plot={plot.data.plot} />}
        </div>
      </div>
    </Panel>
  );
}

function Nearest({ rows, xKey, xLabel, outKey }: { rows: any[]; xKey: string; xLabel: string; outKey: string }) {
  if (!rows?.length) return null;
  return (
    <div className="nearest">
      <span>Closest real ISS tests</span>
      <table className="data-table">
        <thead>
          <tr>
            <th className="num">O₂</th>
            <th className="num">{xLabel}</th>
            <th>Outcome</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t, i) => (
            <tr key={i}>
              <td className="num">{pct(t.o2, 1)}</td>
              <td className="num">{typeof t[xKey] === "number" ? (+t[xKey]).toFixed(xKey === "x_fuel" ? 2 : 1) : "—"}</td>
              <td>{t[outKey] ? (outKey === "ignited" ? "ignited" : "went out") : outKey === "ignited" ? "no ignition" : "burned out"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <EvidenceBadge tier="nasa_table" />
    </div>
  );
}

function CfigSim() {
  const [config, setConfig] = useState<"normal" | "inverse">("normal");
  const [fuel, setFuel] = useState<"ethane" | "propane" | "butane">("propane");
  const [o2, setO2] = useState(0.3);
  const [xf, setXf] = useState(0.3);
  const r = useJSON<any>(useDebounced(`${API}/whatif/cfig?config=${config}&fuel=${fuel}&o2=${o2}&x_fuel=${xf}`));
  const d = r.data;
  return (
    <Panel title="Gas flame ignition · ACME CFI-G" meta="P(IGNITES)" className="sim-panel">
      <div className="sim-controls">
        <Choice label="Burner" value={config} onChange={setConfig} options={[["normal", "normal"], ["inverse", "inside-out"]]} />
        <Choice label="Fuel" value={fuel} onChange={setFuel} options={[["ethane", "ethane"], ["propane", "propane"], ["butane", "butane"]]} />
        <Slider label="Oxygen in the oxidizer" value={o2} min={0.1} max={0.9} step={0.005} onChange={setO2} fmt={(v) => pct(v, 1)} />
        <Slider label="Fuel fraction" value={xf} min={0} max={1} step={0.01} onChange={setXf} fmt={(v) => v.toFixed(2)} />
      </div>
      {d ? (
        <>
          <Prob label="Probability the flame ignites" p={d.p_ignite} valid={d.valid} sigma={d.sigma_latent} />
          {d.error && <p className="sim-flag">⚠ {en(d.error)}</p>}
          {d.range && (
            <p className="chart-note">
              Tested range: O₂ {pct(d.range.o2[0], 1)}–{pct(d.range.o2[1], 1)}, fuel fraction {d.range.x_fuel[0]}–{d.range.x_fuel[1]} ·
              pressure held at {d.fixed?.pressure_kpa} kPa · per-day AUC {d.metrics?.gp?.auc}
            </p>
          )}
          <Nearest rows={d.nearest_tests} xKey="x_fuel" xLabel="fuel frac." outKey="ignited" />
        </>
      ) : (
        <p className="chart-note">{r.loading ? "Computing…" : r.error}</p>
      )}
    </Panel>
  );
}

function FlexSim() {
  const [fuel, setFuel] = useState<"heptane" | "methanol">("heptane");
  const [o2, setO2] = useState(0.21);
  const [p, setP] = useState(101.3);
  const [he, setHe] = useState(0);
  const r = useJSON<any>(useDebounced(`${API}/whatif/flex?fuel=${fuel}&o2=${o2}&pressure_kpa=${p}&he=${he}`));
  const d = r.data;
  return (
    <Panel title="Droplet flame suppression · FLEX" meta="P(GOES OUT EARLY)" className="sim-panel">
      <div className="sim-controls">
        <Choice label="Fuel" value={fuel} onChange={setFuel} options={[["heptane", "heptane"], ["methanol", "methanol"]]} />
        <Slider label="Oxygen" value={o2} min={0.1} max={0.4} step={0.005} onChange={setO2} fmt={(v) => pct(v, 1)} />
        <Slider label="Pressure" value={p} min={50} max={320} step={1} onChange={setP} fmt={(v) => `${v} kPa`} />
        <Slider label="Helium (suppressant)" value={he} min={0} max={0.6} step={0.01} onChange={setHe} fmt={(v) => pct(v, 0)} />
      </div>
      {d ? (
        <>
          <Prob label="Probability the flame goes out before the droplet burns up" p={d.p_extinction} valid={d.valid} sigma={d.sigma_latent} />
          {d.K_mm2_s?.value != null && (
            <>
              <p className="chart-note">
                Burning-rate constant K ≈ <b>{d.K_mm2_s.value} mm²/s</b> from a sparse symbolic fit (RMSE per test day {d.K_mm2_s.rmse_per_hari}):
              </p>
              <Tex src={plainFormulaToTex(d.K_mm2_s.formula)} />
            </>
          )}
          {d.range && (
            <p className="chart-note">
              Tested range: O₂ {pct(d.range.o2[0], 1)}–{pct(d.range.o2[1], 1)}, {d.range.pressure_kpa[0]}–{d.range.pressure_kpa[1]} kPa ·
              per-day AUC {d.metrics?.gp?.auc}
            </p>
          )}
          <Nearest rows={d.nearest_tests} xKey="pressure_kpa" xLabel="kPa" outKey="extinction" />
        </>
      ) : (
        <p className="chart-note">{r.loading ? "Computing…" : r.error}</p>
      )}
    </Panel>
  );
}
