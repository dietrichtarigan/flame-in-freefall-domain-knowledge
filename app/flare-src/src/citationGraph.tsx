/**
 * Jaringan keilmuan: paper yang diindeks asisten (seed) -> karya yang mereka
 * sitasi (ref) -> akar bersama (root), dengan klaster k-means.
 * Data: citation_graph.json dari scripts/citation_graph.py (daftar referensi Crossref).
 *
 * Digambar di <canvas> (ribuan simpul; SVG terlalu berat). Tata letak sudah
 * dihitung di Python, jadi peramban hanya menggambar, memperbesar, dan menyorot.
 */
import React, { useEffect, useMemo, useRef, useState } from "react";

type GNode = {
  id: string;
  layer: "seed" | "ref" | "root";
  title: string;
  year: number | null;
  doi: string | null;
  cited_by: number;
  topic: string | null;
  field: string | null;
  cluster: number;
  x: number;
  y: number;
  uid?: string;
  match?: string;
  n_seeds?: number;
  n_refs?: number;
};
type Cluster = { id: number; label: string; terms: string[]; topic: string | null; n: number; n_seed: number };
type Graph = {
  built: string;
  stats: Record<string, number>;
  method: Record<string, string>;
  clusters: Cluster[];
  nodes: GNode[];
  edges: [number, number][];
};

// Palet kategorikal yang tetap terbaca di latar gelap (urutan = nomor klaster).
const PAL = ["#e0894f", "#5fb8c4", "#a6b86a", "#b38be0", "#e2b84a", "#e06f6f", "#4fa889", "#d58fb8",
  "#8aa0e0", "#c79a6a", "#7fc4a0", "#d0d07a", "#9a8fd0", "#e09a4f"];

const LAYER_LABEL = { seed: "indexed paper (we train on)", ref: "cited by an indexed paper", root: "common root (cited by many references)" };

export function CitationGraph() {
  const [g, setG] = useState<Graph | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [colorBy, setColorBy] = useState<"cluster" | "layer">("cluster");
  const [minSeeds, setMinSeeds] = useState(2);
  const [showRoots, setShowRoots] = useState(true);
  const [onlyCluster, setOnlyCluster] = useState<number | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [hover, setHover] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const view = useRef({ k: 1, tx: 0, ty: 0 });
  const [, force] = useState(0);

  useEffect(() => {
    fetch("citation_graph.json")
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then(setG)
      .catch((e) => setErr(String(e)));
  }, []);

  // tetangga keluar (yang disitasi) dan masuk (yang menyitasi)
  const adj = useMemo(() => {
    if (!g) return null;
    const out: number[][] = g.nodes.map(() => []);
    const inn: number[][] = g.nodes.map(() => []);
    for (const [a, b] of g.edges) {
      out[a].push(b);
      inn[b].push(a);
    }
    return { out, inn };
  }, [g]);

  const visible = useMemo(() => {
    if (!g) return [] as boolean[];
    return g.nodes.map(
      (n) =>
        (onlyCluster === null || n.cluster === onlyCluster) &&
        (n.layer === "seed" || (n.layer === "ref" && (n.n_seeds ?? 1) >= minSeeds) || (n.layer === "root" && showRoots)),
    );
  }, [g, minSeeds, showRoots, onlyCluster]);

  // "Menjalar seperti akar": dari simpul terpilih, ikuti sitasi keluar dua langkah.
  const trace = useMemo(() => {
    if (!g || !adj || sel === null) return null;
    const l1 = new Set(adj.out[sel]);
    const l2 = new Set<number>();
    for (const r of l1) for (const x of adj.out[r]) if (!l1.has(x) && x !== sel) l2.add(x);
    const citedBy = new Set(adj.inn[sel]);
    return { l1, l2, citedBy };
  }, [g, adj, sel]);

  const matches = useMemo(() => {
    if (!g || query.trim().length < 3) return [] as number[];
    const q = query.toLowerCase();
    return g.nodes.map((n, i) => (n.title.toLowerCase().includes(q) ? i : -1)).filter((i) => i >= 0).slice(0, 8);
  }, [g, query]);

  const color = (n: GNode) =>
    colorBy === "cluster" ? PAL[n.cluster % PAL.length] : n.layer === "seed" ? "#f0a35e" : n.layer === "root" ? "#8f6a4c" : "#6f8f96";
  const radius = (n: GNode) => (n.layer === "seed" ? 3.6 : n.layer === "root" ? 2.6 : 1.5 + Math.min(2.5, (n.n_seeds ?? 1) * 0.35));

  // ------------------------------------------------------------- gambar
  useEffect(() => {
    const c = canvas.current;
    if (!c || !g || !adj) return;
    const dpr = window.devicePixelRatio || 1;
    const W = c.clientWidth, H = c.clientHeight;
    if (c.width !== W * dpr) { c.width = W * dpr; c.height = H * dpr; }
    const ctx = c.getContext("2d")!;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const { k, tx, ty } = view.current;
    const pad = 24;
    const S = Math.min(W, H) - pad * 2;
    const ox = (W - S) / 2, oy = (H - S) / 2;
    const P = (n: GNode): [number, number] => [ox + (n.x * S) * k + tx, oy + (n.y * S) * k + ty];
    const vis = visible;
    const active = trace;

    // tepi: tipis untuk semua, terang untuk jejak dari simpul terpilih
    ctx.lineWidth = 0.5;
    ctx.strokeStyle = active ? "rgba(232,227,216,0.025)" : "rgba(232,227,216,0.06)";
    ctx.beginPath();
    for (const [a, b] of g.edges) {
      if (!vis[a] || !vis[b]) continue;
      const [x1, y1] = P(g.nodes[a]);
      const [x2, y2] = P(g.nodes[b]);
      ctx.moveTo(x1, y1);
      ctx.lineTo(x2, y2);
    }
    ctx.stroke();
    if (active && sel !== null) {
      const draw = (a: number, b: number, col: string, w: number) => {
        const [x1, y1] = P(g.nodes[a]);
        const [x2, y2] = P(g.nodes[b]);
        ctx.strokeStyle = col;
        ctx.lineWidth = w;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
        ctx.stroke();
      };
      for (const r of active.l1) for (const x of adj.out[r]) if (active.l2.has(x)) draw(r, x, "rgba(143,106,76,0.55)", 0.7);
      for (const r of active.l1) draw(sel, r, "rgba(240,163,94,0.75)", 1);
      for (const r of active.citedBy) draw(r, sel, "rgba(95,184,196,0.8)", 1);
    }
    // simpul: lapis ref dulu, lalu akar, lalu seed di atas
    for (const layer of ["ref", "root", "seed"] as const) {
      g.nodes.forEach((n, i) => {
        if (n.layer !== layer || !vis[i]) return;
        const dim = active && i !== sel && !active.l1.has(i) && !active.l2.has(i) && !active.citedBy.has(i);
        const [x, y] = P(n);
        if (x < -10 || y < -10 || x > W + 10 || y > H + 10) return;
        ctx.globalAlpha = dim ? 0.12 : layer === "ref" ? 0.7 : 0.95;
        ctx.fillStyle = color(n);
        ctx.beginPath();
        ctx.arc(x, y, radius(n) * Math.sqrt(k), 0, Math.PI * 2);
        ctx.fill();
        if (layer === "seed" && !dim) {
          ctx.globalAlpha = 0.9;
          ctx.strokeStyle = "#f6efe2";
          ctx.lineWidth = 0.8;
          ctx.stroke();
        }
      });
    }
    ctx.globalAlpha = 1;
    for (const i of [sel, hover, ...matches]) {
      if (i === null || i === undefined) continue;
      const [x, y] = P(g.nodes[i]);
      ctx.strokeStyle = "#ffffff";
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.arc(x, y, radius(g.nodes[i]) * Math.sqrt(k) + 4, 0, Math.PI * 2);
      ctx.stroke();
    }
  });

  // ------------------------------------------------------- interaksi
  const pick = (ev: React.MouseEvent) => {
    const c = canvas.current;
    if (!c || !g) return null;
    const r = c.getBoundingClientRect();
    const mx = ev.clientX - r.left, my = ev.clientY - r.top;
    const { k, tx, ty } = view.current;
    const pad = 24, S = Math.min(c.clientWidth, c.clientHeight) - pad * 2;
    const ox = (c.clientWidth - S) / 2, oy = (c.clientHeight - S) / 2;
    let best = -1, bd = 64;
    g.nodes.forEach((n, i) => {
      if (!visible[i]) return;
      const x = ox + n.x * S * k + tx, y = oy + n.y * S * k + ty;
      const d = (x - mx) ** 2 + (y - my) ** 2;
      if (d < bd) { bd = d; best = i; }
    });
    return best >= 0 ? best : null;
  };
  const drag = useRef<{ x: number; y: number; moved: boolean } | null>(null);
  const onWheel = (ev: React.WheelEvent) => {
    const c = canvas.current!;
    const r = c.getBoundingClientRect();
    const mx = ev.clientX - r.left, my = ev.clientY - r.top;
    const v = view.current;
    const f = ev.deltaY < 0 ? 1.18 : 1 / 1.18;
    const nk = Math.min(14, Math.max(0.6, v.k * f));
    const ff = nk / v.k;
    v.tx = mx - (mx - v.tx) * ff;
    v.ty = my - (my - v.ty) * ff;
    v.k = nk;
    force((x) => x + 1);
  };
  // gulir roda di dalam kanvas tidak boleh menggulir halaman
  useEffect(() => {
    const c = canvas.current;
    if (!c) return;
    const stop = (e: WheelEvent) => e.preventDefault();
    c.addEventListener("wheel", stop, { passive: false });
    return () => c.removeEventListener("wheel", stop);
  }, [g]);

  if (err) return <p className="chart-note">Citation graph unavailable ({err}). Run scripts/citation_graph.py.</p>;
  if (!g) return <p className="chart-note">Loading citation graph…</p>;

  const s = g.stats;
  const node = sel !== null ? g.nodes[sel] : null;
  const hov = hover !== null ? g.nodes[hover] : null;
  const shown = visible.filter(Boolean).length;
  const doiUrl = (n: GNode) => (n.doi ? `https://doi.org/${n.doi}` : `https://search.crossref.org/?q=${encodeURIComponent(n.title)}`);

  return (
    <div className="cite-graph">
      <div className="cite-toolbar">
        <div className="segmented">
          <button className={colorBy === "cluster" ? "active" : ""} onClick={() => setColorBy("cluster")}>color: cluster</button>
          <button className={colorBy === "layer" ? "active" : ""} onClick={() => setColorBy("layer")}>color: layer</button>
        </div>
        <label>
          references cited by ≥ <b>{minSeeds}</b> indexed paper{minSeeds > 1 ? "s" : ""}
          <input type="range" min={1} max={6} value={minSeeds} onChange={(e) => setMinSeeds(+e.target.value)} />
        </label>
        <label className="cite-check">
          <input type="checkbox" checked={showRoots} onChange={(e) => setShowRoots(e.target.checked)} /> roots
        </label>
        <div className="cite-search">
          <input placeholder="Find a paper…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {matches.length > 0 && (
            <div className="cite-results">
              {matches.map((i) => (
                <button key={i} onClick={() => { setSel(i); setQuery(""); }}>
                  {g.nodes[i].title.slice(0, 90)} <small>{g.nodes[i].year ?? ""} · {g.nodes[i].layer}</small>
                </button>
              ))}
            </div>
          )}
        </div>
        <button className="text-button" onClick={() => { view.current = { k: 1, tx: 0, ty: 0 }; setSel(null); setOnlyCluster(null); force((x) => x + 1); }}>
          RESET VIEW
        </button>
      </div>

      <div className="cite-body">
        <div className="cite-canvas-wrap">
          <canvas
            ref={canvas}
            className="cite-canvas"
            onWheel={onWheel}
            onMouseDown={(e) => (drag.current = { x: e.clientX, y: e.clientY, moved: false })}
            onMouseMove={(e) => {
              if (drag.current) {
                const dx = e.clientX - drag.current.x, dy = e.clientY - drag.current.y;
                if (Math.abs(dx) + Math.abs(dy) > 2) drag.current.moved = true;
                view.current.tx += dx;
                view.current.ty += dy;
                drag.current.x = e.clientX;
                drag.current.y = e.clientY;
                force((x) => x + 1);
              } else setHover(pick(e));
            }}
            onMouseUp={(e) => {
              if (drag.current && !drag.current.moved) setSel(pick(e));
              drag.current = null;
            }}
            onMouseLeave={() => { drag.current = null; setHover(null); }}
            aria-label={`Citation network: ${s.seeds_matched} indexed papers, ${s.refs} cited works, ${s.roots} roots`}
          />
          {hov && !drag.current && (
            <div className="cite-tip">
              <b>{hov.title}</b>
              <span>{hov.year ?? "n.d."} · {LAYER_LABEL[hov.layer]}</span>
              <span>cluster {hov.cluster}: {g.clusters[hov.cluster]?.label}</span>
            </div>
          )}
          <div className="cite-legend-layers">
            <span><i className="seed" /> indexed (seed)</span>
            <span><i className="ref" /> cited</span>
            <span><i className="root" /> root</span>
            <small>{shown.toLocaleString("en-US")} of {g.nodes.length.toLocaleString("en-US")} works shown · scroll to zoom, drag to pan, click to trace</small>
          </div>
        </div>

        <aside className="cite-side">
          {node ? (
            <div className="cite-detail">
              <span className="cite-layer">{LAYER_LABEL[node.layer]}</span>
              <h3>{node.title}</h3>
              <p>
                {node.year ?? "n.d."} · cited {node.cited_by.toLocaleString("en-US")}× worldwide
                {node.topic ? ` · ${node.topic}` : ""}
              </p>
              <p>
                <i style={{ background: PAL[node.cluster % PAL.length] }} className="cite-swatch" />
                Cluster {node.cluster}: {g.clusters[node.cluster]?.label}
              </p>
              {trace && (
                <ul className="cite-trace">
                  <li><b style={{ color: "#f0a35e" }}>{trace.l1.size}</b> works it cites (in this graph)</li>
                  <li><b style={{ color: "#c08a60" }}>{trace.l2.size}</b> roots reached through them</li>
                  <li><b style={{ color: "#5fb8c4" }}>{trace.citedBy.size}</b> works here that cite it</li>
                </ul>
              )}
              <a href={doiUrl(node)} target="_blank" rel="noreferrer">{node.doi ? `doi:${node.doi}` : "source record"} ↗</a>
              {node.match && node.match !== "doi" && <small>matched to Crossref by title ({node.match})</small>}
              <button className="text-button" onClick={() => setSel(null)}>CLEAR</button>
            </div>
          ) : (
            <div className="cite-stats">
              <div><strong>{s.seeds_matched}</strong><span>indexed papers matched ({s.seeds_match_doi} by DOI) of {s.seeds_indexed}</span></div>
              <div><strong>{s.refs.toLocaleString("en-US")}</strong><span>works they cite</span></div>
              <div><strong>{s.roots.toLocaleString("en-US")}</strong><span>common roots</span></div>
              <div><strong>{s.k}</strong><span>k-means clusters (silhouette {s.silhouette})</span></div>
            </div>
          )}
          <div className="cite-clusters">
            <span>CLUSTERS · click to isolate</span>
            {g.clusters.map((c) => (
              <button key={c.id} className={onlyCluster === c.id ? "active" : ""}
                onClick={() => setOnlyCluster(onlyCluster === c.id ? null : c.id)} title={c.topic ?? ""}>
                <i style={{ background: PAL[c.id % PAL.length] }} />
                <span>{c.label}</span>
                <small>{c.n_seed} / {c.n}</small>
              </button>
            ))}
          </div>
        </aside>
      </div>
      <p className="panel-footnote">
        {g.method.source}. {g.method.cluster}. {g.method.caveat}.
      </p>
    </div>
  );
}
