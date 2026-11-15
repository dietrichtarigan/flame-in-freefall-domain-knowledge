/**
 * Bagian Scenario yang dipindah dari /insight/:
 *  - rerank(): skor ulang dengan bobot pilihan pengguna + filter pilar
 *  - stability(): kestabilan peringkat SMAA (Lahdelma dkk. 1998), 2000 bobot acak
 *  - EvidenceScatter: setiap uji bertabel menurut O2 dan tekanan, pita skenario
 *  - FuelCoverage, InBandTests: tabel cakupan dan uji nyata di dalam pita
 */
import React, { useMemo, useState } from "react";
import { go, pct } from "./ui";

export type Weights = { direct: number; conditions: number; evidence: number };

export function rerank(rows: any[], w: Weights, pillar: string | null) {
  const sum = w.direct + w.conditions + w.evidence || 1;
  return rows
    .filter((r) => !pillar || (r.pillars || []).includes(pillar))
    .map((r) => ({
      ...r,
      score: (w.direct * r.components.direct + w.conditions * r.components.conditions + w.evidence * r.components.evidence) / sum,
    }))
    .sort((a, b) => b.score - a.score || a.accession.localeCompare(b.accession, undefined, { numeric: true }));
}

const STAB: Record<string, Record<string, { keep: (rank: number) => number; lo: number; hi: number }>> = {};

/** Seberapa sering tiap investigasi mempertahankan peringkatnya jika bobot diacak seragam di simpleks. */
export function stability(key: string, rows: any[]) {
  if (STAB[key]) return STAB[key];
  let seed = 20261114;
  const rnd = () => {
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const N = 2000;
  const ranks: Record<string, number[]> = Object.fromEntries(rows.map((r) => [r.accession, []]));
  for (let s = 0; s < N; s++) {
    const g = [0, 0, 0].map(() => -Math.log(1 - rnd()));
    const t = g[0] + g[1] + g[2];
    rows
      .map((r) => ({ a: r.accession, v: (g[0] * r.components.direct + g[1] * r.components.conditions + g[2] * r.components.evidence) / t }))
      .sort((x, y) => y.v - x.v || x.a.localeCompare(y.a, undefined, { numeric: true }))
      .forEach((x, i) => ranks[x.a].push(i + 1));
  }
  const out: Record<string, { keep: (rank: number) => number; lo: number; hi: number }> = {};
  for (const [a, rs] of Object.entries(ranks)) {
    rs.sort((x, y) => x - y);
    out[a] = { keep: (rank) => rs.filter((x) => x <= rank).length / rs.length, lo: rs[Math.floor(0.05 * (N - 1))], hi: rs[Math.ceil(0.95 * (N - 1))] };
  }
  return (STAB[key] = out);
}

const PH_LABEL: Record<string, string> = { gas: "gas flame", droplet: "droplet", solid: "solid material" };
const PH_COLOR: Record<string, string> = { gas: "#5fb8c4", droplet: "#e2b84a", solid: "#e0894f" };

/** Setiap uji bertabel menurut oksigen dan tekanan (log), dengan pita skenario. Klik titik -> dosir uji. */
export function EvidenceScatter({ points, band, label, names }: {
  points: any[];
  band: { o2: [number, number]; p: [number, number] };
  label: string;
  names: Record<string, string>;
}) {
  const [hover, setHover] = useState<any>(null);
  const [show, setShow] = useState<Record<string, boolean>>({ gas: true, droplet: true, solid: true });
  const W = 680, H = 400, ml = 54, mr = 14, mt = 14, mb = 74, lane = 30;
  const x0 = 0.1, x1 = 1.0, y0 = Math.log10(20), y1 = Math.log10(520), yb = H - mb;
  const X = (v: number) => ml + ((v - x0) / (x1 - x0)) * (W - ml - mr);
  const Y = (v: number) => yb - ((Math.log10(v) - y0) / (y1 - y0)) * (yb - mt);
  const bx0 = X(Math.max(x0, band.o2[0])), bx1 = X(Math.min(x1, band.o2[1]));
  const by0 = Y(Math.min(520, band.p[1])), by1 = Y(Math.max(20, band.p[0]));
  const pts = useMemo(() => {
    const order: Record<string, number> = { gas: 0, droplet: 1, solid: 2 };
    return [...points].filter((p) => PH_COLOR[p.ph] && p.o2 != null).sort((a, b) => order[a.ph] - order[b.ph]);
  }, [points]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const p of pts) c[p.ph] = (c[p.ph] || 0) + 1;
    return c;
  }, [pts]);
  return (
    <div className="scatter-wrap">
      <div className="scatter-legend">
        {Object.keys(PH_COLOR).map((ph) => (
          <label key={ph}>
            <input type="checkbox" checked={show[ph]} onChange={() => setShow((s) => ({ ...s, [ph]: !s[ph] }))} />
            <i style={{ background: PH_COLOR[ph] }} /> {PH_LABEL[ph]} ({counts[ph] ?? 0})
          </label>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="scatter" role="img" aria-label={`Every tabulated test by oxygen and pressure, with the ${label} band`}>
        {[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0].map((v) => (
          <g key={v}>
            <line x1={X(v)} x2={X(v)} y1={mt} y2={yb} className="grid" />
            <text x={X(v)} y={yb + lane + 24} textAnchor="middle">{Math.round(v * 100)}%</text>
          </g>
        ))}
        {[20, 50, 100, 200, 500].map((k) => (
          <g key={k}>
            <line x1={ml} x2={W - mr} y1={Y(k)} y2={Y(k)} className="grid" />
            <text x={ml - 6} y={Y(k) + 4} textAnchor="end">{k}</text>
          </g>
        ))}
        <rect x={bx0} y={by0} width={Math.max(0, bx1 - bx0)} height={Math.max(0, by1 - by0)} className="band" />
        <text x={(bx0 + bx1) / 2} y={by0 - 6} textAnchor="middle" className="band-label">{label}</text>
        <rect x={bx0} y={yb + 8} width={Math.max(0, bx1 - bx0)} height={lane - 6} className="band" />
        <line x1={ml} x2={W - mr} y1={yb} y2={yb} className="axis" />
        <text x={ml - 6} y={yb + 22} textAnchor="end">no kPa</text>
        <text x={(ml + W - mr) / 2} y={H - 8} textAnchor="middle">oxygen (mole fraction of the oxidizer)</text>
        <text x={14} y={(mt + yb) / 2} textAnchor="middle" transform={`rotate(-90 14 ${(mt + yb) / 2})`}>pressure (kPa, log)</text>
        {pts.map((p, i) => {
          if (!show[p.ph]) return null;
          const x = X(Math.min(x1, Math.max(x0, p.o2)));
          const y = p.p == null ? yb + 12 + ((i * 7) % (lane - 10)) : Y(Math.max(20, Math.min(520, p.p)));
          return (
            <circle key={p.id ?? i} cx={x} cy={y} r={3.4} fill={PH_COLOR[p.ph]} className="pt"
              onMouseEnter={() => setHover({ ...p, x, y })} onMouseLeave={() => setHover(null)}
              onClick={() => p.id && go("Tests", p.id)} />
          );
        })}
      </svg>
      {hover && (
        <div className="scatter-tip" style={{ left: `${(hover.x / W) * 100}%`, top: `${(hover.y / H) * 100}%` }}>
          <b>{names[hover.acc] ?? hover.acc}</b> · test {hover.t}
          <br />
          {PH_LABEL[hover.ph]}: {hover.fuel || "n/a"}
          <br />
          O₂ {pct(hover.o2, 1)} · {hover.p == null ? "pressure not recorded" : `${hover.p} kPa`}
          {hover.out && (
            <>
              <br />
              {hover.out}
            </>
          )}
          <br />
          <small>click to open the test</small>
        </div>
      )}
    </div>
  );
}

export function FuelCoverage({ phase }: { phase: Record<string, any> }) {
  return (
    <div className="table-scroll">
    <table className="data-table">
      <thead>
        <tr>
          <th>Fuel type</th>
          <th className="num">Tests</th>
          <th className="num">With O₂</th>
          <th className="num">In band</th>
          <th className="num">O₂ only</th>
          <th className="num">Highest O₂</th>
        </tr>
      </thead>
      <tbody>
        {Object.entries(phase).map(([k, v]: [string, any]) => (
          <tr key={k} className={v.n_in_band === 0 ? "gap-row" : ""}>
            <td>{PH_LABEL[k] ?? k}</td>
            <td className="num">{v.n_tests}</td>
            <td className="num">{v.n_with_o2}</td>
            <td className="num">
              <b>{v.n_in_band}</b>
            </td>
            <td className="num">{v.n_o2_only}</td>
            <td className="num">{pct(v.o2_max_per_test, 1)}</td>
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

export function InBandTests({ near, total, names }: { near: any[]; total: number; names: Record<string, string> }) {
  const [n, setN] = useState(25);
  if (!near.length) return <p className="chart-note">No tabulated test matches this atmosphere. That absence is itself the finding.</p>;
  return (
    <>
      <div className="table-scroll">
        <table className="data-table">
          <thead>
            <tr>
              <th>Investigation</th>
              <th>Test</th>
              <th>Fuel</th>
              <th className="num">O₂</th>
              <th className="num">kPa</th>
              <th>Outcome</th>
              <th>Match</th>
            </tr>
          </thead>
          <tbody>
            {near.slice(0, n).map((p) => (
              <tr key={p.id ?? p.t}>
                <td>{names[p.acc] ?? p.acc}</td>
                <td>
                  {p.id ? (
                    <button className="link-button" onClick={() => go("Tests", p.id)}>
                      {p.t}
                    </button>
                  ) : (
                    p.t
                  )}
                </td>
                <td>{p.fuel || "—"}</td>
                <td className="num">{pct(p.o2, 1)}</td>
                <td className="num">{p.p ?? "—"}</td>
                <td>{p.out || "—"}</td>
                <td>{p.match === "full" ? "O₂ + pressure" : "O₂ only"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {near.length > n && (
        <button className="text-button more" onClick={() => setN((x) => x + 25)}>
          SHOW MORE ({Math.min(near.length, total) - n} left)
        </button>
      )}
    </>
  );
}
