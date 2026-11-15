/**
 * Tampilan jawaban asisten ala "jawaban bersumber": teks berformat, sitasi yang
 * bisa diklik, grafik dari alat make_plot, dan gambar/rumus asli dari paper.
 *
 * Dipindahkan dari chat /insight/ (fmtAnswer, plotSVG, figStrip di
 * app/insight/index.html). Sebelumnya FLARE+ menampilkan jawaban sebagai teks
 * mentah: penanda [[paper:...]] dan **tebal** terlihat apa adanya, dan plot yang
 * dikirim backend tidak pernah digambar.
 */
import React, { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { figureUrl, type AskReply } from "./api";
import { plainFormulaToTex, texToHtml } from "./math";

type Citation = {
  ref: string;
  kind: string;
  exists?: boolean;
  url?: string;
  doi?: string;
  title?: string;
  page?: string | null;
  tier?: string;
  tier_label?: string;
  value?: unknown;
  unit?: string;
  label?: string | null;
  target?: string | null;
  entity?: string;
  quantity?: string;
};

const CITE = /\[\[(m:[^\]]+|test:[^\]]+|paper:[^\]]+|model:[^\]]+|inv:[^\]]+)\]\]/g;

function isBareFormula(text: string) {
  const value = text.trim();
  return (
    value.length <= 240 &&
    /^[A-Za-z][A-Za-z0-9_]*(?:\([^)]*\))?\s*(?:=|≈|≤|≥)\s*.+/.test(value) &&
    !/^(?:Note|Warning|Result|Answer|Source|Model)\s*:/i.test(value)
  );
}

/** **tebal** dan `kode` di dalam satu potong teks biasa. */
function inline(text: string, key: string): React.ReactNode[] {
  const out: React.ReactNode[] = [];
  if (isBareFormula(text)) {
    out.push(
      <span
        key={`${key}bare-math`}
        className="katex-block"
        role="math"
        dangerouslySetInnerHTML={{ __html: texToHtml(plainFormulaToTex(text.trim()), true) }}
      />,
    );
    return out;
  }
  // **tebal**, `kode`, dan rumus LaTeX: $$...$$ atau \[...\] (blok), $...$ atau \(...\) (sebaris)
  const re = /\$\$([^$]+)\$\$|\\\[([\s\S]+?)\\\]|\$([^$\n]+?)\$|\\\(([\s\S]+?)\\\)|\*\*([^*\n]+)\*\*|`([^`\n]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const block = m[1] ?? m[2];
    const inl = m[3] ?? m[4];
    if (block !== undefined)
      out.push(<span key={`${key}m${i++}`} className="katex-block" dangerouslySetInnerHTML={{ __html: texToHtml(block.trim(), true) }} />);
    else if (inl !== undefined && /[\\^_{}=]/.test(inl))
      out.push(<span key={`${key}m${i++}`} dangerouslySetInnerHTML={{ __html: texToHtml(inl.trim(), false) }} />);
    else if (inl !== undefined) out.push(m[0]); // "$5 and $6": bukan rumus
    else out.push(m[5] ? <b key={`${key}b${i++}`}>{m[5]}</b> : <code key={`${key}c${i++}`}>{m[6]}</code>);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function CiteChip({ raw, cite }: { raw: string; cite?: Citation }) {
  const [kind, ...rest] = raw.split(":");
  const body = rest.join(":");
  if (kind === "paper") {
    const [title, page] = body.split("|");
    const label = `${title.trim()}${page && page.trim() !== "-" ? ` · p. ${page.trim()}` : ""}`;
    return cite?.url ? (
      <a className="cite-chip paper" href={cite.url} target="_blank" rel="noreferrer"
        title={cite.doi ? `doi:${cite.doi}` : cite.url}>
        {label}
      </a>
    ) : (
      <span className="cite-chip paper" title="paper claim · no link found">{label}</span>
    );
  }
  if (kind === "inv") {
    return (
      <a className="cite-chip inv" href={`https://psi.nasa.gov/physci/repo/data/investigations/${body}`}
        target="_blank" rel="noreferrer" title={cite?.label || body}>
        {body}
      </a>
    );
  }
  const missing = cite && cite.exists === false;
  const title =
    kind === "m" && cite?.quantity
      ? `${cite.entity} · ${cite.quantity} = ${cite.value ?? "?"}${cite.unit ? " " + cite.unit : ""} · ${cite.tier_label}`
      : kind === "model"
        ? `model prediction${cite?.target ? " · " + cite.target : ""}`
        : raw;
  return (
    <span className={`cite-chip ${kind}${missing ? " missing" : ""}`} title={missing ? "reference not found in the knowledge base" : title}>
      {kind === "model" ? "model: " : ""}
      {kind === "m" ? "measurement" : body}
    </span>
  );
}

/** Jawaban dengan sitasi menjadi chip/tautan; baris "- " menjadi butir. */
export function AnswerText({ text, citations }: { text: string; citations?: Citation[] }) {
  const byRef = new Map((citations || []).map((c) => [c.ref, c]));
  const renderLine = (line: string, li: number) => {
    const parts: React.ReactNode[] = [];
    let last = 0;
    let m: RegExpExecArray | null;
    CITE.lastIndex = 0;
    let k = 0;
    while ((m = CITE.exec(line))) {
      if (m.index > last) parts.push(...inline(line.slice(last, m.index), `${li}-${k++}`));
      parts.push(<CiteChip key={`${li}-c${k++}`} raw={m[1]} cite={byRef.get(m[1])} />);
      last = CITE.lastIndex;
    }
    if (last < line.length) parts.push(...inline(line.slice(last), `${li}-${k++}`));
    return parts;
  };
  const lines = text.split("\n");
  const blocks: React.ReactNode[] = [];
  let list: React.ReactNode[] = [];
  const flush = () => {
    if (list.length) blocks.push(<ul key={`ul${blocks.length}`}>{list}</ul>);
    list = [];
  };
  lines.forEach((line, i) => {
    const bullet = /^\s*[-•*]\s+(.*)$/.exec(line);
    if (bullet) {
      list.push(<li key={i}>{renderLine(bullet[1], i)}</li>);
      return;
    }
    flush();
    if (line.trim()) blocks.push(<p key={i}>{renderLine(line, i)}</p>);
  });
  flush();
  return <div className="answer-text">{blocks}</div>;
}

/* ------------------------------------------------------------------ plot */

type Series = {
  name: string;
  type?: "band" | "line" | "labels" | "points" | string;
  points?: [number, number, string?][];
  lo?: [number, number][];
  hi?: [number, number][];
};
type Plot = { title: string; x: string; y: string; log_x?: boolean; series: Series[]; source: string; tier: string };

const PAL = ["#d4874d", "#65c6d1", "#a4b093", "#8b6cc9", "#c99a22", "#c0392b", "#3aa3a3", "#9a6b4b"];
const SUP: Record<string, string> = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };

function nice(a: number, b: number, n: number) {
  const st = Math.pow(10, Math.floor(Math.log10((b - a) / n || 1)));
  const m = ([1, 2, 5, 10].find((k) => (b - a) / (st * k) <= n) ?? 10) * st;
  const o: number[] = [];
  for (let v = Math.ceil(a / m) * m; v <= b + 1e-9; v += m) o.push(+v.toFixed(6));
  return o;
}

/** Grafik dari alat make_plot: sumbu berlabel, legenda, sumber + tier di bawahnya. */
export function PlotView({ plot }: { plot: Plot }) {
  const W = 400, H = 250, ml = 46, mr = 10, mt = 10, mb = 38;
  const all: [number, number][] = [];
  for (const s of plot.series) for (const q of [...(s.points || []), ...(s.lo || []), ...(s.hi || [])]) all.push([q[0], q[1]]);
  if (!all.length) return null;
  const fx = (v: number) => (plot.log_x ? Math.log10(v) : v);
  let x0 = Math.min(...all.map((q) => fx(q[0]))), x1 = Math.max(...all.map((q) => fx(q[0])));
  let y0 = Math.min(...all.map((q) => q[1])), y1 = Math.max(...all.map((q) => q[1]));
  const px = (x1 - x0) * 0.05 || 1, py = (y1 - y0) * 0.08 || 1;
  x0 -= px; x1 += px;
  y0 -= py;
  y1 += py;
  const X = (v: number) => ml + ((fx(v) - x0) / (x1 - x0)) * (W - ml - mr);
  const Y = (v: number) => H - mb - ((v - y0) / (y1 - y0)) * (H - mt - mb);
  const xt = plot.log_x ? nice(x0, x1, 5).filter(Number.isInteger).map((e) => 10 ** e) : nice(x0, x1, 6);
  const xLabel = (v: number) =>
    !plot.log_x || v >= 1 ? String(v) : "10" + String(Math.round(Math.log10(v))).split("").map((c) => SUP[c]).join("");
  let ci = 0;
  const marks: React.ReactNode[] = [];
  const legend: React.ReactNode[] = [];
  plot.series.forEach((s, si) => {
    if (s.type === "band" && s.lo && s.hi) {
      const pts = [...s.lo.map((q) => `${X(q[0])},${Y(q[1])}`), ...s.hi.slice().reverse().map((q) => `${X(q[0])},${Y(q[1])}`)];
      marks.push(<polygon key={si} points={pts.join(" ")} className="plot-band" />);
      legend.push(<span key={si}><i className="plot-band-key" />{s.name}</span>);
      return;
    }
    if (s.type === "labels") {
      for (const [j, q] of (s.points || []).entries()) {
        const right = X(q[0]) > W - 60;
        marks.push(
          <g key={`${si}-${j}`}>
            <circle cx={X(q[0])} cy={Y(q[1])} r={3.5} className="plot-label-dot" />
            <text x={X(q[0]) + (right ? -5 : 5)} y={Y(q[1]) - 6} textAnchor={right ? "end" : "start"} className="plot-label">{q[2]}</text>
          </g>,
        );
      }
      return;
    }
    const col = PAL[ci++ % PAL.length];
    if (s.type === "line") {
      marks.push(<polyline key={si} points={(s.points || []).map((q) => `${X(q[0])},${Y(q[1])}`).join(" ")} fill="none" stroke={col} strokeWidth={2} />);
    } else {
      for (const [j, q] of (s.points || []).entries())
        marks.push(
          <circle key={`${si}-${j}`} cx={X(q[0])} cy={Y(q[1])} r={2.6} fill={col} fillOpacity={0.8}>
            <title>{`${s.name}: ${q[0]}, ${q[1]}`}</title>
          </circle>,
        );
    }
    legend.push(<span key={si}><i style={{ background: col }} />{s.name}</span>);
  });
  return (
    <figure className="chat-plot">
      <figcaption className="chat-plot-title">{plot.title}</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={plot.title}>
        {xt.map((v) => (
          <g key={`x${v}`}>
            <line x1={X(v)} x2={X(v)} y1={mt} y2={H - mb} className="plot-grid" />
            <text x={X(v)} y={H - mb + 13} textAnchor="middle">{xLabel(v)}</text>
          </g>
        ))}
        {nice(y0, y1, 5).map((v) => (
          <g key={`y${v}`}>
            <line x1={ml} x2={W - mr} y1={Y(v)} y2={Y(v)} className="plot-grid" />
            <text x={ml - 5} y={Y(v) + 3} textAnchor="end">{v}</text>
          </g>
        ))}
        {marks}
        <line x1={ml} x2={W - mr} y1={H - mb} y2={H - mb} className="plot-axis" />
        <text x={(ml + W - mr) / 2} y={H - 6} textAnchor="middle">{plot.x}</text>
        <text transform={`translate(11 ${(mt + H - mb) / 2}) rotate(-90)`} textAnchor="middle">{plot.y}</text>
      </svg>
      <div className="chat-plot-legend">{legend}</div>
      <div className="chat-plot-source">
        {plot.source} · {plot.tier === "model_prediction" ? "model prediction" : "NASA data"}
      </div>
    </figure>
  );
}

/* --------------------------------------------------------------- gambar */

type Fig = NonNullable<AskReply["figures"]>[number];

/** Semua gambar/rumus dari paper; klik membuka ukuran penuh di dalam halaman. */
export function FigureStrip({ figures, compact = false }: { figures: Fig[]; compact?: boolean }) {
  const [open, setOpen] = useState<Fig | null>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(null);
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, [open]);
  if (!figures.length) return null;
  const caption = (f: Fig) => f.caption.replace(/^\s*(fig(ure)?\.?|gambar)\s*[\d.]+[a-z]?\.?\s*/i, "");
  return (
    <>
      <div className={`figure-strip${compact ? " compact" : ""}`}>
        {figures.map((f) => (
          <figure key={f.id} className={f.kind === "equation" || /^Equation/i.test(f.label) ? "is-equation" : ""}>
            <button className="figure-open" onClick={() => setOpen(f)} aria-label={`Enlarge ${f.label}`}>
              <img src={figureUrl(f.image)} alt={`${f.label}: ${f.caption}`} loading="lazy" />
            </button>
            <figcaption>
              <b>{f.label}</b> · p. {f.page}
              {!compact && <span title={f.caption}>{caption(f)}</span>}
              {f.url || f.doi ? (
                <a href={f.url || `https://doi.org/${f.doi}`} target="_blank" rel="noreferrer">
                  {f.paper.slice(0, 70)}
                  {f.doi ? " · doi" : ""}
                </a>
              ) : (
                <i>{f.paper.slice(0, 70)}</i>
              )}
            </figcaption>
          </figure>
        ))}
      </div>
      {open && createPortal(
        <div className="figure-lightbox" onClick={() => setOpen(null)} role="dialog" aria-label={open.label}>
          <figure onClick={(e) => e.stopPropagation()}>
            <img src={figureUrl(open.image)} alt={`${open.label}: ${open.caption}`} />
            <figcaption>
              <b>{open.label}</b> · p. {open.page} · {open.paper}
              <span>{open.caption}</span>
              {(open.url || open.doi) && (
                <a href={open.url || `https://doi.org/${open.doi}`} target="_blank" rel="noreferrer">
                  Open source {open.doi ? `(doi:${open.doi})` : ""}
                </a>
              )}
            </figcaption>
            <button onClick={() => setOpen(null)} aria-label="Close">×</button>
          </figure>
        </div>,
        document.body,
      )}
    </>
  );
}

/** Plot + gambar di bawah satu jawaban (dipakai asisten penuh dan panel mengambang). */
export function ReplyMedia({ reply, compact = false }: { reply: AskReply; compact?: boolean }) {
  const plots = (reply.plots || []) as Plot[];
  return (
    <>
      {plots.map((p, i) => (
        <PlotView key={i} plot={p} />
      ))}
      <FigureStrip figures={reply.figures || []} compact={compact} />
    </>
  );
}
