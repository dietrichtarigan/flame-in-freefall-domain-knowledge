/**
 * Research Map, bagian dari /insight/:
 *  - ResearchNetwork: investigasi <-> paper <-> topik (research_map.json), klik
 *    simpul untuk menyorot tetangganya; jenis tautan dibedakan (terdaftar di PSI,
 *    tag NTRS, kemiripan topik -- yang terakhir BUKAN sitasi).
 *  - EvidenceMatrix: investigasi x skenario, berapa uji yang jatuh di pita tiap
 *    habitat, plus paper terdaftar dan jumlah uji.
 */
import React, { useMemo, useState } from "react";
import { go } from "./ui";

const KIND_LABEL: Record<string, string> = {
  listed: "PSI lists the paper",
  tag: "NTRS topic tag",
  similar: "topic similarity (not a citation)",
};

export function ResearchNetwork({ map }: { map: any }) {
  const [sel, setSel] = useState<number | null>(null);
  const [sim, setSim] = useState(false);
  const nodes: any[] = map?.nodes ?? [];
  const edges: any[] = (map?.edges ?? []).filter((e: any) => sim || e.k !== "similar");
  const W = 1000, H = 600, m = 24;
  const X = (n: any) => m + n.x * (W - 2 * m);
  const Y = (n: any) => m + n.y * (H - 2 * m);
  const nb = useMemo(() => {
    const s = new Set<number>();
    if (sel === null) return s;
    s.add(sel);
    for (const e of edges) if (e.s === sel || e.t === sel) {
      s.add(e.s);
      s.add(e.t);
    }
    return s;
  }, [sel, edges]);
  const years = nodes.filter((n) => n.kind === "paper" && +n.year).map((n) => +n.year);
  const y0 = Math.min(...years), y1 = Math.max(...years);
  const labels = useMemo(() => {
    const boxes: number[][] = [];
    const out: { i: number; x: number; y: number; t: string; left: boolean }[] = [];
    const order = nodes
      .map((_, i) => i)
      .filter((i) => nodes[i].kind !== "paper" || i === sel)
      .sort((a, b) => Number(b === sel) - Number(a === sel) || Number(nodes[b].kind === "investigation") - Number(nodes[a].kind === "investigation") || nodes[b].degree - nodes[a].degree);
    for (const i of order) {
      const n = nodes[i];
      const t = n.label.length > 28 ? n.label.slice(0, 27) + "…" : n.label;
      const w = t.length * 6.4, x = X(n) + 9, y = Y(n) + 4;
      const left = x + w > W - 4;
      const bx = left ? X(n) - 9 - w : x;
      const box = [bx - 2, y - 11, bx + w + 2, y + 3];
      if (i !== sel && boxes.some((b) => box[0] < b[2] && box[2] > b[0] && box[1] < b[3] && box[3] > b[1])) continue;
      boxes.push(box);
      out.push({ i, x: left ? X(n) - 9 : x, y, t, left });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, sel]);

  const node = sel !== null ? nodes[sel] : null;
  const links = node
    ? edges.filter((e) => e.s === sel || e.t === sel).map((e) => ({ o: nodes[e.s === sel ? e.t : e.s], k: e.k }))
    : [];

  return (
    <div className="net-wrap">
      <div className="net-toolbar">
        <label className="cite-check">
          <input type="checkbox" checked={sim} onChange={(e) => setSim(e.target.checked)} /> show topic-similarity links
        </label>
        {Object.entries(KIND_LABEL).map(([k, l]) => (
          <span key={k} className={`net-key ${k}`}>
            <i /> {l} ({map?.stats?.edges?.[k] ?? 0})
          </span>
        ))}
        <button className="text-button" onClick={() => setSel(null)} disabled={sel === null}>
          CLEAR SELECTION
        </button>
      </div>
      <div className="net-body">
        <svg viewBox={`0 0 ${W} ${H}`} className="net-svg" role="img" aria-label="Investigations, papers and topics">
          {edges.map((e, k) => {
            const a = nodes[e.s], b = nodes[e.t];
            const on = sel !== null && (e.s === sel || e.t === sel);
            return <line key={k} className={`e ${e.k}${on ? " on" : ""}${sel !== null && !on ? " dim" : ""}`} x1={X(a)} y1={Y(a)} x2={X(b)} y2={Y(b)} />;
          })}
          {nodes.map((n, i) => {
            const dim = sel !== null && !nb.has(i) ? " dim" : "";
            const click = () => setSel(sel === i ? null : i);
            if (n.kind === "investigation")
              return (
                <circle key={i} className={`n inv${dim}`} cx={X(n)} cy={Y(n)} r={6 + Math.sqrt(n.degree) * 1.6} onClick={click}>
                  <title>{`${n.label} · ${n.degree} links`}</title>
                </circle>
              );
            if (n.kind === "topic")
              return (
                <rect key={i} className={`n topic${dim}`} x={X(n) - 6} y={Y(n) - 6} width={12} height={12} onClick={click}>
                  <title>{`Topic: ${n.label}`}</title>
                </rect>
              );
            const t = +n.year ? (+n.year - y0) / (y1 - y0 || 1) : 0.5;
            return (
              <circle key={i} className={`n paper${dim}`} cx={X(n)} cy={Y(n)} r={n.full_text ? 3.2 : 2.4} style={{ fillOpacity: 0.25 + 0.6 * t }} onClick={click}>
                <title>{`${n.label}${n.year ? ` (${n.year})` : ""}`}</title>
              </circle>
            );
          })}
          {labels.map((l) => (
            <text key={l.i} className="lbl" x={l.x} y={l.y} textAnchor={l.left ? "end" : "start"} opacity={sel !== null && !nb.has(l.i) ? 0.2 : 1}>
              {l.t}
            </text>
          ))}
        </svg>
        <aside className="net-info">
          {node ? (
            <>
              <span className="cite-layer">{node.kind}</span>
              <h3>{node.label}</h3>
              <p className="muted">
                {node.kind === "paper"
                  ? [node.year, node.journal].filter(Boolean).join(" · ")
                  : node.kind === "investigation"
                    ? `${node.acc} · ${(node.pillars || []).join(", ")}`
                    : "topic tag"}
              </p>
              {node.url && (
                <a href={node.url} target="_blank" rel="noreferrer">
                  {node.doi ? `doi:${node.doi}` : "open source"} ↗
                </a>
              )}
              {node.kind === "investigation" && (
                <button className="text-button" onClick={() => go("Investigations", node.acc)}>
                  OPEN INVESTIGATION →
                </button>
              )}
              {node.kind === "topic" && (
                <button className="text-button" onClick={() => go("Assistant", `What do the papers say about ${node.label.toLowerCase()} in microgravity?`)}>
                  ASK THE ASSISTANT ABOUT THIS TOPIC →
                </button>
              )}
              <ul className="net-links">
                {links.slice(0, 40).map((l, j) => (
                  <li key={j}>
                    {l.o.label.slice(0, 90)} <small className="muted">· {KIND_LABEL[l.k]}</small>
                  </li>
                ))}
              </ul>
              {links.length > 40 && <p className="muted">and {links.length - 40} more</p>}
            </>
          ) : (
            <p className="chart-note">
              Click an investigation (large dot), a topic (square) or a paper (small dot; darker = more recent, larger = full text indexed)
              to highlight what it is linked to. {map?.stats?.papers} papers shown; {map?.stats?.papers_without_any_link_dropped} with no link are
              left out rather than placed arbitrarily.
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

export function EvidenceMatrix({ data, map }: { data: any; map: any }) {
  const scs: string[] = data.scenarios;
  const byAcc: Record<string, Record<string, any>> = {};
  for (const k of scs) for (const r of data.scenario[k].ranking) (byAcc[r.accession] ||= {})[k] = r;
  const listed: Record<string, number> = {};
  for (const e of map?.edges ?? []) if (e.k === "listed") {
    const n = map.nodes[e.t];
    if (n?.acc) listed[n.acc] = (listed[n.acc] || 0) + 1;
  }
  const cond = (c: any) => scs.reduce((t, k) => t + (byAcc[c.accession]?.[k]?.components.conditions || 0), 0);
  const rows = [...data.investigations].sort((a, b) => cond(b) - cond(a) || a.accession.localeCompare(b.accession, undefined, { numeric: true }));
  return (
    <div className="table-scroll">
      <table className="data-table matrix">
        <thead>
          <tr>
            <th>Investigation</th>
            {scs.map((k) => (
              <th key={k}>{data.scenario[k].short}</th>
            ))}
            <th className="num">Papers listed</th>
            <th className="num">Tests</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.accession} onClick={() => go("Investigations", c.accession)} className="clickable" tabIndex={0}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && go("Investigations", c.accession)}>
              <td>
                <b>{c.name}</b> <small className="muted">{c.accession}</small>
              </td>
              {scs.map((k) => {
                const r = byAcc[c.accession]?.[k];
                const v = r ? r.components.conditions : 0;
                const n = r ? r.n_full || r.n_o2_only : 0;
                return (
                  <td key={k} className={n ? "" : "c0"} style={{ background: `rgba(224,137,79,${(v * 0.5).toFixed(2)})` }} title={r?.why?.conditions ?? ""}>
                    {n ? `${n}${r.n_full ? "" : " O₂ only"}` : "–"}
                  </td>
                );
              })}
              <td className="num">{listed[c.accession] ?? 0}</td>
              <td className="num">{c.n_tests || c.n_rows || 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
