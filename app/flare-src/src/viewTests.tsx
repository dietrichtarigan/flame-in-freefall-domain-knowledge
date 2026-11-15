/**
 * Tests: penjelajah uji (dari mode peneliti /app/), sekarang di FLARE+.
 * Daftar dari /tests, dosir dari /entity, penjelasan dari /explain, uji terkait
 * dari /relevance, peringatan dari /alerts?entity=, asal-usul angka dari
 * /provenance. Semua baca-saja: aman di mode publik.
 */
import React, { useEffect, useMemo, useState } from "react";
import { API } from "./api";
import { EvidenceBadge, PageTitle, Panel, displayValue, go, pct, useFocus, useJSON } from "./ui";
import { FLAG_EN, GRANULARITY_EN, LEVEL_EN, RULE_EN, en } from "./i18n";
import { useInsight } from "./useData";

type TestRow = {
  id: string;
  accession: string;
  label: string;
  granularity: string;
  fuel: string | null;
  config: string | null;
  o2: number | null;
  p_kpa: number | null;
  ignited: boolean | null;
  ignited_tier?: string;
  flags: string[];
  rules: string[];
};

const PAGE = 120;

export function Tests() {
  const focusFromNav = useFocus("Tests");
  const { data: insight } = useInsight();
  const all = useJSON<{ n: number; tests: TestRow[] }>(`${API}/tests`);
  const [acc, setAcc] = useState("");
  const [ign, setIgn] = useState("any");
  const [flag, setFlag] = useState("");
  const [q, setQ] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [focus, setFocus] = useState<string | null>(null);

  useEffect(() => {
    if (!focusFromNav) return;
    if (focusFromNav.startsWith("acc:")) {
      // dari kartu investigasi: saring daftar ke investigasi itu
      setAcc(focusFromNav.slice(4));
      setFocus(null);
      return;
    }
    setFocus(focusFromNav);
    const a = focusFromNav.split(":")[1];
    if (a) setAcc(a);
  }, [focusFromNav]);

  const names = useMemo(() => {
    const m: Record<string, string> = {};
    for (const i of insight?.investigations ?? []) m[i.accession] = i.name;
    return m;
  }, [insight]);

  const rows = useMemo(() => {
    const t = all.data?.tests ?? [];
    const ql = q.trim().toLowerCase();
    return t.filter(
      (r) =>
        (!acc || r.accession === acc) &&
        (ign === "any" || (ign === "yes" ? r.ignited === true : ign === "no" ? r.ignited === false : r.ignited == null)) &&
        (!flag || r.flags.includes(flag)) &&
        (!ql || `${r.label} ${r.fuel ?? ""} ${r.config ?? ""}`.toLowerCase().includes(ql)),
    );
  }, [all.data, acc, ign, flag, q]);

  useEffect(() => setShown(PAGE), [acc, ign, flag, q]);

  const accs = useMemo(
    () => Array.from(new Set((all.data?.tests ?? []).map((t) => t.accession))).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
    [all.data],
  );
  const flagCounts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of all.data?.tests ?? []) for (const f of t.flags) c[f] = (c[f] || 0) + 1;
    return c;
  }, [all.data]);

  const clear = () => {
    setAcc("");
    setIgn("any");
    setFlag("");
    setQ("");
  };

  return (
    <div className="page">
      <PageTitle
        index="05"
        overline="TEST-LEVEL EVIDENCE"
        title="Test Explorer"
        description="Every test row NASA tabulated, plus telemetry-only runs we mined. Open a test to see its measurements, where each number came from, why it is flagged, and which tests resemble it."
      />
      <div className="tests-layout">
        <Panel title="Tests" meta={all.data ? `${rows.length.toLocaleString("en-US")} OF ${all.data.n.toLocaleString("en-US")}` : "LOADING"}>
          <div className="filter-row">
            <label>
              Investigation
              <select value={acc} onChange={(e) => setAcc(e.target.value)}>
                <option value="">All ({accs.length})</option>
                {accs.map((a) => (
                  <option key={a} value={a}>
                    {names[a] ? `${names[a]} · ${a}` : a}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Ignited
              <select value={ign} onChange={(e) => setIgn(e.target.value)}>
                <option value="any">Any</option>
                <option value="yes">Yes</option>
                <option value="no">No</option>
                <option value="unknown">Not reported</option>
              </select>
            </label>
            <label>
              Flag
              <select value={flag} onChange={(e) => setFlag(e.target.value)}>
                <option value="">Any</option>
                {Object.entries(flagCounts)
                  .sort((a, b) => b[1] - a[1])
                  .map(([f, n]) => (
                    <option key={f} value={f}>
                      {FLAG_EN[f] ?? f} ({n})
                    </option>
                  ))}
              </select>
            </label>
            <label className="grow">
              Search
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="test id or fuel, e.g. 21106 or heptane" />
            </label>
            <button className="text-button" onClick={clear} disabled={!acc && ign === "any" && !flag && !q}>
              CLEAR
            </button>
          </div>
          {all.error && <p className="chart-note">Tests unavailable ({all.error}).</p>}
          {all.loading && <p className="chart-note">Loading tests…</p>}
          {all.data && (
            <div className="table-scroll tests-table-wrap">
              <table className="data-table tests-table">
                <thead>
                  <tr>
                    <th>Test</th>
                    <th>Investigation</th>
                    <th>Fuel</th>
                    <th className="num">O₂</th>
                    <th className="num">kPa</th>
                    <th>Ignited</th>
                    <th>Flags</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, shown).map((r) => (
                    <tr
                      key={r.id}
                      className={focus === r.id ? "selected" : ""}
                      onClick={() => setFocus(r.id)}
                      tabIndex={0}
                      onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setFocus(r.id)}
                      aria-label={`Open test ${r.label}`}
                    >
                      <td>
                        <b>{r.label}</b>
                        {r.granularity !== "test" && <small className="muted"> {GRANULARITY_EN[r.granularity] ?? r.granularity}</small>}
                      </td>
                      <td>{names[r.accession] ?? r.accession}</td>
                      <td>{[r.fuel, r.config].filter(Boolean).join(" · ") || "—"}</td>
                      <td className="num">{pct(r.o2, 1)}</td>
                      <td className="num">{r.p_kpa != null ? r.p_kpa.toFixed(1) : "—"}</td>
                      <td>{r.ignited == null ? "—" : r.ignited ? "yes" : "no"}</td>
                      <td className="muted">{r.flags.length ? r.flags.length : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > shown && (
                <button className="text-button more" onClick={() => setShown((s) => s + PAGE)}>
                  SHOW {Math.min(PAGE, rows.length - shown)} MORE ({rows.length - shown} left)
                </button>
              )}
              {!rows.length && <p className="chart-note">No test matches these filters.</p>}
            </div>
          )}
        </Panel>
        <div className="dossier-col">
          {focus ? <Dossier id={focus} names={names} onOpen={setFocus} /> : (
            <Panel title="Test dossier" meta="SELECT A TEST">
              <p className="chart-note">
                Pick a row to open its dossier: every measurement with its evidence tier and source file, the rule-based
                explanation of any flag, and the tests most like it.
              </p>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function Dossier({ id, names, onOpen }: { id: string; names: Record<string, string>; onOpen: (id: string) => void }) {
  const ent = useJSON<any>(`${API}/entity/${encodeURIComponent(id)}`);
  const why = useJSON<any>(`${API}/explain/${encodeURIComponent(id)}`);
  const rel = useJSON<any>(`${API}/relevance/${encodeURIComponent(id)}?k=8`);
  const al = useJSON<any>(`${API}/alerts?entity=${encodeURIComponent(id)}&min=info`);
  const [prov, setProv] = useState<string | null>(null);
  const e = ent.data;
  const label = e?.label ?? id.split(":").pop();
  const acc = e?.accession ?? id.split(":")[1];

  return (
    <>
      <Panel title={`Test ${label}`} meta={names[acc] ? `${names[acc]} · ${acc}` : acc}>
        {ent.loading && <p className="chart-note">Loading…</p>}
        {ent.error && <p className="chart-note">Unavailable ({ent.error}).</p>}
        {e && (
          <>
            <div className="dossier-attrs">
              {Object.entries(e.attrs ?? {})
                .filter(([, v]) => v !== null && v !== "" && typeof v !== "object")
                .slice(0, 12)
                .map(([k, v]) => (
                  <div key={k}>
                    <span>{k.replaceAll("_", " ")}</span>
                    <b>{k === "granularity" ? GRANULARITY_EN[String(v)] ?? displayValue(v) : en(displayValue(v))}</b>
                  </div>
                ))}
            </div>
            <h4 className="sub">Measurements · click a value for its source</h4>
            <div className="measure-list">
              {Object.entries(e.measurements ?? {}).map(([q, ms]: [string, any]) =>
                (ms as any[]).map((m) => (
                  <button key={m.id} className={`measure ${prov === m.id ? "active" : ""}`} onClick={() => setProv(prov === m.id ? null : m.id)}>
                    <span>{q.replaceAll("_", " ")}</span>
                    <b>
                      {displayValue(m.value ?? m.value_text)} {m.unit ?? ""}
                    </b>
                    <EvidenceBadge tier={m.tier} />
                  </button>
                )),
              )}
              {!Object.keys(e.measurements ?? {}).length && <p className="chart-note">No measurement recorded for this test.</p>}
            </div>
            {prov && <Provenance mid={prov} />}
            {(e.rule_hits ?? []).length > 0 && (
              <>
                <h4 className="sub">Rules that fired</h4>
                <ul className="hypotheses">
                  {(e.rule_hits as any[]).map((r, i) => (
                    <li key={i}>
                      <b>{RULE_EN[r.rule_id] ?? en(r.rule_id)}</b>
                      {r.detail && <small>{en(r.detail)}</small>}
                      {r.effect && <small>effect: {en(r.effect)}</small>}
                      {r.reason && <small className="muted">why the rule exists: {en(r.reason)}</small>}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </Panel>

      <Panel title="Why is it flagged?" meta="RULE-BASED, NOT A LANGUAGE MODEL">
        {why.data?.hipotesis?.length ? (
          <ul className="hypotheses">
            {why.data.hipotesis.map((h: any, i: number) => (
              <li key={i}>
                <div className="hyp-head">
                  <b>{en(h.hipotesis)}</b>
                  <i style={{ width: `${Math.round((h.kekuatan ?? 0) * 100)}%` }} title={`strength ${h.kekuatan}`} />
                </div>
                {(h.bukti ?? []).map((b: string, j: number) => (
                  <small key={j}>{en(b)}</small>
                ))}
                <small className="muted">source: {en(h.sumber)}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chart-note">{why.loading ? "Loading…" : "No rule fires for this test."}</p>
        )}
        <p className="panel-footnote">Strength is a heuristic weight, not a probability.</p>
      </Panel>

      <Panel title="Alerts on this test" meta={al.data ? `${al.data.alerts?.length ?? 0}` : ""}>
        {al.data?.alerts?.length ? (
          <ul className="alert-list">
            {al.data.alerts.map((a: any) => (
              <li key={a.id} className={`lvl-${a.level}`}>
                <span className="lvl">{LEVEL_EN[a.level] ?? a.level}</span>
                <div>
                  <b>{en(a.title)}</b>
                  <small>{(a.evidence ?? []).map(en).join(" · ")}</small>
                  <small className="muted">next step: {en(a.action)}</small>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chart-note">{al.loading ? "Loading…" : "No alert for this test."}</p>
        )}
      </Panel>

      <Panel title="Most similar tests" meta="SERIES · SAME DAY · CONDITIONS">
        {rel.data?.related?.length ? (
          <ul className="related-list">
            {rel.data.related.map((r: any) => (
              <li key={r.id}>
                <button className="link-button" onClick={() => onOpen(r.id)}>
                  {r.label}
                </button>
                <small>{(r.why ?? []).map(en).join(" · ")}</small>
                <span className="muted">{r.ignited == null ? "" : r.ignited ? "ignited" : "no ignition"}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="chart-note">{rel.loading ? "Loading…" : "No related test found."}</p>
        )}
        <button className="text-button" onClick={() => go("Investigations", acc)}>
          OPEN {names[acc] ?? acc} INVESTIGATION →
        </button>
      </Panel>
    </>
  );
}

function Provenance({ mid }: { mid: string }) {
  const p = useJSON<any>(`${API}/provenance/${encodeURIComponent(mid)}`);
  const m = p.data?.measurement;
  if (p.loading) return <p className="chart-note">Loading provenance…</p>;
  if (!m) return <p className="chart-note">No provenance record.</p>;
  return (
    <dl className="prov-box">
      <div>
        <dt>Value</dt>
        <dd>
          {m.value ?? m.value_text} {m.unit}
          {m.lo != null && m.hi != null ? ` (range ${m.lo}–${m.hi})` : ""}
        </dd>
      </div>
      <div>
        <dt>Tier</dt>
        <dd>
          <EvidenceBadge tier={m.tier} />
        </dd>
      </div>
      <div>
        <dt>Method</dt>
        <dd>{en(m.method)}</dd>
      </div>
      {p.data.artifact && (
        <div>
          <dt>Source file</dt>
          <dd className="mono">{p.data.artifact.path}</dd>
        </div>
      )}
      {p.data.model_card && (
        <div>
          <dt>Model</dt>
          <dd>{p.data.model_card.id ?? p.data.model_card}</dd>
        </div>
      )}
      {m.verified_by && (
        <div>
          <dt>Verified by</dt>
          <dd>{m.verified_by}</dd>
        </div>
      )}
    </dl>
  );
}
