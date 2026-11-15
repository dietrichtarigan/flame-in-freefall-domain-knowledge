/**
 * Gaps Analysis: apa yang tidak bisa dijawab arsip untuk satu habitat, dan uji mana yang
 * paling informatif berikutnya. Ditulis ulang dengan kelas sendiri: tata letak lama memakai
 * .quality-panel (grid 3 kolom dari desain awal) sehingga temuan terjepit di sepertiga lebar.
 */
import React, { useEffect, useState } from "react";
import { PageTitle, Panel, go, pct, useFocus } from "./ui";
import { useInsight } from "./useData";

const LEVELS = ["critical", "warning", "info"] as const;
type Level = (typeof LEVELS)[number];
const LEVEL_TEXT: Record<Level, string> = {
  critical: "cannot be answered from PSI data",
  warning: "answerable only with caveats",
  info: "context worth knowing",
};

export function Gaps() {
  const { data, error, retry } = useInsight();
  const [sid, setSid] = useState<string>("surface");
  const [only, setOnly] = useState<Level | null>(null);
  const focusSid = useFocus("Gaps");
  useEffect(() => {
    if (focusSid) setSid(focusSid);
  }, [focusSid]);

  if (error && !data)
    return (
      <div className="page">
        <p className="chart-note">
          Gap analysis unavailable ({error}).{" "}
          <button className="text-button" onClick={retry}>
            RETRY
          </button>
        </p>
      </div>
    );
  if (!data) return <div className="page"><p className="chart-note">Reading the evidence model…</p></div>;

  const sc: any = data.scenario[sid];
  const gaps = ((sc?.gaps ?? []) as { level: string; title: string; text: string }[])
    .slice()
    .sort((a, b) => LEVELS.indexOf(a.level as Level) - LEVELS.indexOf(b.level as Level));
  const count = (l: Level) => gaps.filter((g) => g.level === l).length;
  const shown = only ? gaps.filter((g) => g.level === only) : gaps;
  const next = (sc?.next_tests ?? []) as any[];

  return (
    <div className="page">
      <PageTitle
        index="03"
        overline="EVIDENCE COVERAGE"
        title="Gaps Analysis"
        description="What the archive cannot answer for this habitat, and which experiment would teach the most."
      />
      <div className="segmented objective-switch">
        {data.scenarios.map((id) => (
          <button key={id} className={id === sid ? "active" : ""} onClick={() => { setSid(id); setOnly(null); }} aria-pressed={id === sid}>
            {data.scenario[id]?.short || id}
          </button>
        ))}
      </div>

      <div className="gap-summary">
        {LEVELS.map((l) => (
          <button
            key={l}
            className={`gap-tile ${l} ${only === l ? "active" : ""}`}
            onClick={() => setOnly(only === l ? null : l)}
            aria-pressed={only === l}
            disabled={!count(l)}
          >
            <strong>{count(l)}</strong>
            <span>{l}</span>
            <small>{LEVEL_TEXT[l]}</small>
          </button>
        ))}
        <div className="gap-band">
          <span>Habitat band</span>
          <b>
            {pct(sc.o2?.[0])}–{pct(sc.o2?.[1])} O₂ · {sc.p_kpa?.[0]}–{sc.p_kpa?.[1]} kPa
          </b>
          <small>{sc.gravity}</small>
        </div>
      </div>

      <div className="gaps-layout">
        <Panel
          title="What is not known here"
          meta={only ? `${shown.length} ${only.toUpperCase()} · CLICK THE TILE AGAIN FOR ALL` : `${gaps.length} FINDINGS`}
        >
          <div className="gap-cards">
            {shown.map((g, i) => (
              <article key={i} className={`gap-card ${g.level}`}>
                <span className="gap-chip">{g.level}</span>
                <h3>{g.title}</h3>
                <p>{g.text}</p>
              </article>
            ))}
            {!shown.length && <p className="chart-note">No finding at this level for this habitat.</p>}
          </div>
        </Panel>

        <div className="side-stack">
          <Panel title="Gravity" meta="KNOWN LIMIT">
            <ul className="gap-bullets">
              {(data.partial_gravity ?? []).map((t: string, i: number) => (
                <li key={i}>{t}</li>
              ))}
            </ul>
            <button className="text-button" onClick={() => go("WhatIf")}>
              BOUND IT WITH THE GRAVITY BRIDGE →
            </button>
          </Panel>
          <Panel title="Back on Earth" meta="SPINOFF">
            <div className="earth-list">
              {(data.earth ?? []).map((e: any, i: number) => {
                const invs = (data.investigations ?? []).filter((c: any) => c.direct >= 0.8 && (c.pillars ?? []).includes(e.pillar));
                return (
                  <article key={i}>
                    <h3>{e.title || e.name}</h3>
                    <p>{e.text || e.detail}</p>
                    {invs.length > 0 && (
                      <small>
                        Related in PSI:{" "}
                        {invs.map((c: any, j: number) => (
                          <React.Fragment key={c.accession}>
                            {j > 0 && ", "}
                            <button className="link-button" onClick={() => go("Investigations", c.accession)}>
                              {c.name}
                            </button>
                          </React.Fragment>
                        ))}
                      </small>
                    )}
                  </article>
                );
              })}
            </div>
          </Panel>
        </div>
      </div>

      <Panel title="Most informative next tests" meta="ACTIVE LEARNING · GAUSSIAN-PROCESS BOUNDARY">
        <p className="gap-intro">
          Where one more ISS test would teach the boundary models the most: a lower <b>U</b> means the model is least sure whether the flame
          ignites or goes out there. Candidates stay close to conditions that were actually flown.
        </p>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Experiment</th>
                <th className="num">O₂</th>
                <th className="num">Pressure</th>
                <th>Conditions</th>
                <th className="num">U</th>
                <th>Inside this habitat band</th>
              </tr>
            </thead>
            <tbody>
              {next.map((n, i) => (
                <tr key={i}>
                  <td className="muted">{i + 1}</td>
                  <td>{n.exp}</td>
                  <td className="num">{pct(n.o2, 1)}</td>
                  <td className="num">{n.p_kpa} kPa</td>
                  <td>{n.detail}</td>
                  <td className="num">{n.U}</td>
                  <td>{n.in_band ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!next.some((n) => n.in_band) && next.length > 0 && (
          <p className="panel-footnote">
            None of the candidates falls inside this habitat band: the boundary models only cover gas flames and droplets. For solid materials
            the gap is the absence of data itself.
          </p>
        )}
        <button className="text-button" onClick={() => go("WhatIf")}>
          TRY THESE CONDITIONS IN WHAT-IF →
        </button>
      </Panel>
    </div>
  );
}
