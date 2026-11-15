/**
 * Investigations: katalog (dari tab "Investigations" di /insight/) + pembanding.
 * Saring menurut fasilitas, pilar dan jenis; buka kartu untuk tujuan, dampak,
 * data yang kami tambang, dan tautan ke NASA PSI; centang hingga 4 untuk
 * dibandingkan berdampingan pada atribut yang diminta brief tantangan.
 */
import React, { useEffect, useMemo, useState } from "react";
import { EvidenceBadge, PageTitle, Panel, go, pct, useFocus } from "./ui";
import { useInsight } from "./useData";

const named = (xs: any, total?: number) => {
  if (!Array.isArray(xs) || !xs.length) return null;
  const head = xs.slice(0, 4).map((x: any) => (x?.name ? `${x.name} (${x.n})` : String(x)));
  const rest = (total ?? xs.length) - head.length;
  return head.join(", ") + (rest > 0 ? ` +${rest}` : "");
};

/** Variabel yang diubah vs dijaga tetap: "how did tests from the same investigation differ?" */
const varied = (v: any) => {
  if (!v || typeof v !== "object") return null;
  const on = Object.entries(v).filter(([, k]) => k === "varied").map(([k]) => k);
  const off = Object.entries(v).filter(([, k]) => k === "constant").map(([k]) => k);
  const parts = [];
  if (on.length) parts.push("varied: " + on.join(", "));
  if (off.length) parts.push("constant: " + off.join(", "));
  return parts.join(" · ") || null;
};

const range = (r: any, f: (x: number) => string) => (Array.isArray(r) && r.length === 2 ? `${f(r[0])}–${f(r[1])}` : null);

const ROWS: [string, (c: any) => any][] = [
  ["Full title", (c) => c.title],
  ["Pillars", (c) => (c.pillars || []).join(" / ")],
  ["Facility", (c) => c.facility || c.hardware],
  ["Platform", (c) => c.platform],
  ["Years", (c) => (Array.isArray(c.years) ? c.years.join("–") : c.years)],
  ["Fuel phases", (c) => (c.phases || []).join(", ")],
  ["Fuels", (c) => named(c.fuels, c.n_fuels)],
  ["Samples / burners", (c) => named(c.samples)],
  ["Sample size", (c) => (Array.isArray(c.size_mm) ? `${c.size_mm[0]}–${c.size_mm[1]} mm` : c.size_mm)],
  ["Variables", (c) => varied(c.variables)],
  ["Oxygen", (c) => range(c.o2, (x) => pct(x, 0)) ?? (c.o2_listed?.length ? `listed per day: ${c.o2_listed.map((x: number) => pct(x, 0)).join(", ")}` : null)],
  ["Pressure", (c) => range(c.p_kpa, (x) => `${x}`) && `${range(c.p_kpa, (x) => `${x}`)} kPa`],
  ["Air flow", (c) => range(c.flow_cm_s, (x) => `${x}`) && `${range(c.flow_cm_s, (x) => `${x}`)} cm/s`],
  ["Diluents", (c) => (c.diluents || []).join(", ")],
  ["Measurements recorded", (c) => (c.columns || []).slice(0, 8).join(", ") + ((c.columns || []).length > 8 ? ` +${c.columns.length - 8}` : "")],
  ["Tests in NASA table", (c) => c.n_tests || c.n_rows],
  ["Result values", (c) => c.n_results],
  ["Publications", (c) => c.n_publications],
  ["Raw data we mined", (c) => (c.own_data || []).join("; ")],
];

export function Investigations() {
  const focus = useFocus("Investigations");
  const { data } = useInsight();
  const [fac, setFac] = useState("");
  const [pillar, setPillar] = useState("");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [cmp, setCmp] = useState<string[]>([]);

  const cards: any[] = data?.investigations ?? [];
  useEffect(() => {
    if (focus?.startsWith("pillar:")) {
      setPillar(focus.slice(7));
      setOpen(null);
      return;
    }
    if (focus) {
      setOpen(focus);
      setCmp((c) => (c.includes(focus) ? c : [...c, focus].slice(-4)));
    }
  }, [focus]);
  useEffect(() => {
    if (!cmp.length && cards.length) setCmp(cards.slice(0, 3).map((c) => c.accession));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cards.length]);

  const facilities = useMemo(() => Array.from(new Set(cards.map((c) => c.facility).filter(Boolean))).sort(), [cards]);
  const list = cards.filter(
    (c) =>
      (!fac || c.facility === fac) &&
      (!pillar || (c.pillars || []).includes(pillar)) &&
      (!q || `${c.name} ${c.title} ${c.accession} ${c.sub_area}`.toLowerCase().includes(q.toLowerCase())),
  );
  const chosen = cmp.map((a) => cards.find((c) => c.accession === a)).filter(Boolean);
  const toggle = (acc: string) => setCmp((c) => (c.includes(acc) ? c.filter((x) => x !== acc) : [...c, acc].slice(-4)));
  const card = open ? cards.find((c) => c.accession === open) : null;

  return (
    <div className="page">
      <PageTitle
        index="04"
        overline="INVESTIGATION CATALOG"
        title="Investigations"
        description="All 24 PSI combustion investigations: what each set out to learn, what it burned, under which conditions, and how much evidence it left. Tick up to four to compare them side by side."
      />
      <Panel title="Catalog" meta={`${list.length} OF ${cards.length}`}>
        <div className="filter-row">
          <label>
            Facility
            <select value={fac} onChange={(e) => setFac(e.target.value)}>
              <option value="">All hardware</option>
              {facilities.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
          </label>
          <label>
            Pillar
            <select value={pillar} onChange={(e) => setPillar(e.target.value)}>
              <option value="">All pillars</option>
              {Object.entries(data?.pillars ?? {}).map(([k]) => (
                <option key={k} value={k}>
                  {k}
                </option>
              ))}
            </select>
          </label>
          <label className="grow">
            Search
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="name, title or PSI number" />
          </label>
        </div>
        <div className="inv-grid">
          {list.map((c) => (
            <article key={c.accession} className={`inv-card ${open === c.accession ? "open" : ""}`}>
              <button className="inv-main" onClick={() => setOpen(open === c.accession ? null : c.accession)}>
                <strong>{c.name}</strong>
                <small>
                  {c.accession} · {(c.pillars || []).join(" / ")} · {c.kind}
                </small>
                <span>{c.facility}</span>
                <span className="muted">
                  {c.n_tests || c.n_rows || 0} tests · {c.n_publications} publications
                </span>
              </button>
              <label className="cmp-check">
                <input type="checkbox" checked={cmp.includes(c.accession)} onChange={() => toggle(c.accession)} /> compare
              </label>
            </article>
          ))}
        </div>
      </Panel>

      {card && (
        <Panel title={card.name} meta={`${card.accession} · ${card.sub_area ?? ""}`}>
          <div className="inv-detail">
            <div>
              <h4 className="sub">Objective</h4>
              <p>{card.objective}</p>
              {card.impacts && (
                <>
                  <h4 className="sub">Why it matters</h4>
                  <p>{card.impacts}</p>
                </>
              )}
              {(card.highlights || []).length > 0 && (
                <>
                  <h4 className="sub">Highlights</h4>
                  <ul>
                    {card.highlights.slice(0, 5).map((h: any, i: number) => (
                      <li key={i}>{typeof h === "string" ? h : h.text ?? JSON.stringify(h)}</li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div>
              <h4 className="sub">Fire-safety link</h4>
              <p>
                <b>{Math.round((card.direct ?? 0) * 100)}%</b> direct · {card.direct_basis}
              </p>
              <h4 className="sub">Evidence we hold</h4>
              <ul className="tier-list">
                {Object.entries(card.tiers ?? {}).map(([t, n]) => (
                  <li key={t}>
                    <EvidenceBadge tier={t} /> {String(n)}
                  </li>
                ))}
              </ul>
              <div className="inv-actions">
                <button className="primary-button" onClick={() => go("Tests", `acc:${card.accession}`)}>
                  OPEN ITS TESTS →
                </button>
                <button className="text-button" onClick={() => go("Assistant", `Summarize ${card.name} (${card.accession}) for fire safety.`)}>
                  ASK THE ASSISTANT
                </button>
                {card.psi_url && (
                  <a className="text-button" href={card.psi_url} target="_blank" rel="noreferrer">
                    NASA PSI RECORD ↗
                  </a>
                )}
              </div>
            </div>
          </div>
        </Panel>
      )}

      <Panel title="Side by side" meta={`${chosen.length} SELECTED · MAX 4`}>
        {chosen.length ? (
          <div className="cmp-wrap">
            <table className="cmp">
              <thead>
                <tr>
                  <th />
                  {chosen.map((c: any) => (
                    <th key={c.accession}>
                      {c.name}
                      <small>{c.accession}</small>
                      <button className="link-button" onClick={() => toggle(c.accession)} aria-label={`Remove ${c.name}`}>
                        remove
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ROWS.map(([label, get]) => (
                  <tr key={label}>
                    <th>{label}</th>
                    {chosen.map((c: any) => {
                      const v = get(c);
                      const empty = v === null || v === undefined || v === "" || v === "–";
                      return (
                        <td key={c.accession} className={empty ? "na" : ""}>
                          {empty ? "not tabulated" : String(v)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="chart-note">Tick “compare” on up to four investigations above.</p>
        )}
        <p className="panel-footnote">“not tabulated” means NASA did not record that field. It is never a zero.</p>
      </Panel>
    </div>
  );
}
