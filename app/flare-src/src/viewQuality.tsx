/**
 * Quality: semua yang di mode peneliti (/app/) menyangkut kepercayaan pada angka.
 * Peringatan (/alerts), antrean verifikasi manusia (/queue), kartu model
 * (/model_cards), siklus belajar (/history, /pipeline), jejak peristiwa
 * (/events) dan catatan bersama (/notes). Tombol tulis (putusan, catatan,
 * latih ulang) hanya muncul bila backend tidak berjalan di mode publik,
 * karena di sana jalur itu memang ditutup (FIF_PUBLIC=1).
 */
import React, { useMemo, useState } from "react";
import { API, post } from "./api";
import { EvidenceBadge, PageTitle, Panel, go, useJSON } from "./ui";
import { LEVEL_EN, en } from "./i18n";
import { useStatus } from "./useData";
import { TEX, Tex, plainFormulaToTex } from "./math";

/** Ringkasan kartu model dalam bahasa Inggris, setia pada catatan asli di model_card (brain.sqlite). */
const MODEL_EN: Record<string, { target: string; method: string; validity: string; caveats: string[]; tex?: string }> = {
  gb_telemetry_labels: {
    target: "Ignition from telemetry (retrained automatically)",
    method: "Histogram gradient boosting on summary features of 18 sensor channels; NASA labels plus human labels",
    validity: "Grouped by test day (GroupKFold) on NASA-labelled tests",
    caveats: ["Retrained whenever a new human verdict arrives"],
  },
  cnn_telemetry_w32: {
    target: "Ignition, self-extinction and burn time from 18-channel telemetry",
    method: "1-D ResNet, ensemble of 5 folds x 5 seeds (GPU)",
    validity: "Trained on 320 labelled ACME CFI-G tests; grouped by test day",
    caveats: ["Self-supervised pre-training did not help (tested 3 times)", "Use on PSI-10 / PSI-23 is extrapolation to another investigation"],
  },
  gp_boundary_cfig_ign: {
    tex: TEX.gpBoundary,
    target: "P(ignites), ACME CFI-G gas flames",
    method: "Gaussian-process classifier with U-function active learning",
    validity: "Features: burner configuration, fuel, O₂, fuel fraction, ln pressure, fuel flow",
    caveats: ["Next-test candidates only near conditions already tested"],
  },
  gp_boundary_flex_ext: {
    tex: TEX.gpBoundary,
    target: "P(flame goes out before the droplet burns up), FLEX",
    method: "Gaussian-process classifier with U-function active learning",
    validity: "Features: fuel, O₂, CO₂, helium, ln pressure, initial droplet diameter",
    caveats: ["Next-test candidates only near conditions already tested"],
  },
  symreg_flex_K: {
    tex: plainFormulaToTex("K ≈ 0.111 + 1.8·O2 + 0.611·He"),
    target: "Droplet burning-rate constant K (mm²/s)",
    method: "Symbolic regression, exhaustive search with the 1-SE rule",
    validity: "FLEX conditions that were tested",
    caveats: ["Empirical, not a universal law"],
  },
  quantile_burn_cfig: {
    tex: TEX.quantile,
    target: "CFI-G burn time as a P10–P90 range",
    method: "Quantile gradient boosting with per-day conformal calibration",
    validity: "263 tests over 23 test days",
    caveats: ["Bimodal: self-extinction vs. flow shut-off"],
  },
  spice_smoke_point_hybrid: {
    tex: TEX.smoke,
    target: "Smoke-point flame length L_SP (mm), SPICE jet flames",
    method: "Power law ln L = a + b ln u + c ln d, plus a Gaussian process on the residual (physics + data hybrid)",
    validity: "55 points over 11 days; validated leave-one-day-out",
    caveats: [
      "PSI test tables do not mark the smoke point; labels from SmokePointReview-0g-3.xlsx",
      "Diameter exponent −0.76; the published −0.91 lies just outside our 95% CI",
      "Propane and ethylene cannot be separated",
      "New fuel and nozzle combinations are extrapolation",
    ],
  },
  gbridge_pmma: {
    tex: TEX.gravity,
    target: "Limiting O₂ of a PMMA rod versus gravity (Moon, Mars, ISS, Earth)",
    method: "X_lim(a) = X0 + A exp(−a/a_q) + B a; buoyant flow U_b1 (g/gE)^n (p0/p)^n plus forced flow",
    validity: "Fitted for 13.5–22.2% O₂, 0–55 cm/s flow, 99–103 kPa",
    caveats: [
      "No partial-gravity combustion data in PSI: gravity enters only through buoyant-flow scaling",
      "Outside 99–103 kPa is extrapolation (e.g. a Moon base at 70 kPa)",
    ],
  },
};

const METRIC_EN: Record<string, string> = {
  auc: "AUC",
  brier: "Brier",
  acc: "accuracy",
  n_label_manusia: "human labels",
  burn_mae_s: "burn-time MAE (s)",
  burn_medae_s: "burn-time median error (s)",
  rmse_per_hari: "RMSE per day",
  baseline: "baseline RMSE",
  coverage_P10_P90: "P10–P90 coverage",
  median_width_s: "median interval width (s)",
  mae_P50_s: "P50 MAE (s)",
  mayoritas_brier: "majority-class Brier",
  galat_tipikal_pct: "typical error %",
  mae_mm: "MAE (mm)",
  cakupan_PI90: "90% interval coverage",
};

function flatMetrics(m: any): [string, string][] {
  const out: [string, string][] = [];
  const walk = (o: any, prefix: string) => {
    for (const [k, v] of Object.entries(o ?? {})) {
      if (/oklusi|eksponen|hukum_pangkat|n_dinilai|n_dilewati|lebar|rmse_ln|parameter|selang/.test(k)) continue;
      if (v && typeof v === "object" && !Array.isArray(v)) walk(v, k === "per_hari" ? "" : `${k} `);
      else if (typeof v === "number" || (typeof v === "string" && k === "formula"))
        out.push([`${prefix}${METRIC_EN[k] ?? k}`.replace("gp ", "GP ").replace("logistik ", "logistic ").replace("ign ", "ignition ").replace("selfext ", "self-ext. "), String(v)]);
    }
  };
  walk(m, "");
  return out.slice(0, 8);
}

export function Quality() {
  const st = useStatus();
  const writable = st ? st.public === false : false;
  const counts = useJSON<any>(`${API}/alerts?min=info`);
  const [level, setLevel] = useState<"kritis" | "perhatian" | "info">("kritis");
  const [bump, setBump] = useState(0);
  const queue = useJSON<any>(`${API}/queue?k=25&_=${bump}`);
  const cards = useJSON<any>(`${API}/model_cards`);
  const hist = useJSON<any>(`${API}/history?n=8&_=${bump}`);
  const pipe = useJSON<any>(`${API}/pipeline?_=${bump}`);
  const events = useJSON<any>(`${API}/events?since=0&_=${bump}`);
  const notes = useJSON<any>(`${API}/notes?_=${bump}`);

  const alerts = useMemo(() => (counts.data?.alerts ?? []).filter((a: any) => a.level === level), [counts.data, level]);
  const c = counts.data?.counts ?? {};

  return (
    <div className="page">
      <PageTitle
        index="06"
        overline="DATA QUALITY"
        title="Quality & Verification"
        description="Where the numbers might be wrong, what a human still has to check, and how good each model is. Nothing here is hidden from the other views: a flagged test keeps its flag everywhere it appears."
      />
      <div className="quality-grid">
        <Panel title="Alerts" meta={`${(counts.data?.alerts ?? []).length} TOTAL`} className="span-2">
          <div className="segmented">
            {(["kritis", "perhatian", "info"] as const).map((l) => (
              <button key={l} className={l === level ? "active" : ""} onClick={() => setLevel(l)} aria-pressed={l === level}>
                {LEVEL_EN[l]} ({c[l] ?? 0})
              </button>
            ))}
          </div>
          <ul className="alert-list">
            {alerts.slice(0, 40).map((a: any) => (
              <li key={a.id} className={`lvl-${a.level}`}>
                <span className="lvl">{LEVEL_EN[a.level]}</span>
                <div>
                  <b>{en(a.title)}</b>
                  <small>{(a.evidence ?? []).map(en).join(" · ")}</small>
                  <small className="muted">next step: {en(a.action)}</small>
                </div>
                {a.entity?.startsWith("test:") && (
                  <button className="link-button" onClick={() => go("Tests", a.entity)}>
                    {a.label ?? "open"} →
                  </button>
                )}
              </li>
            ))}
            {alerts.length > 40 && <li className="muted">{alerts.length - 40} more of this level.</li>}
            {!alerts.length && !counts.loading && <li className="muted">No alert at this level.</li>}
          </ul>
        </Panel>

        <Panel title="Human verification queue" meta={queue.data ? `${queue.data.n} WAITING · MOST INFORMATIVE FIRST` : ""}>
          <ol className="queue-list">
            {(queue.data?.items ?? []).map((it: any, i: number) => (
              <QueueItem key={it.entity + it.quantity + i} it={it} writable={writable} onDone={() => setBump((b) => b + 1)} />
            ))}
          </ol>
          <p className="panel-footnote">
            Ordered by uncertainty × impact.{" "}
            {writable
              ? "Verdicts are stored and trigger a retrain of the telemetry model."
              : "Verdicts are recorded in the researcher deployment; this public site is read-only."}
          </p>
        </Panel>

        <Panel title="Model cards" meta={`${cards.data?.cards?.length ?? 0} MODELS`}>
          <div className="model-cards">
            {(cards.data?.cards ?? []).map((m: any) => {
              const e = MODEL_EN[m.id];
              return (
                <details key={m.id} className="model-card">
                  <summary>
                    <b>{e?.target ?? en(m.target)}</b>
                    <EvidenceBadge tier="model_prediction" />
                  </summary>
                  <p>{e?.method ?? en(m.method)}</p>
                  {e?.tex && <Tex src={e.tex} />}
                  <dl>
                    {flatMetrics(m.metrics).map(([k, v]) => (
                      <div key={k}>
                        <dt>{k}</dt>
                        <dd>{v}</dd>
                      </div>
                    ))}
                  </dl>
                  {e && <p className="muted">Validation: {e.validity}</p>}
                  {e?.caveats.map((x) => (
                    <p key={x} className="sim-flag">⚠ {x}</p>
                  ))}
                  <small className="muted mono">{m.id}</small>
                </details>
              );
            })}
          </div>
        </Panel>

        <Panel title="Learning cycle" meta="RETRAIN HISTORY">
          <ul className="pipe-steps">
            {(pipe.data?.steps ?? []).map((s: any) => (
              <li key={s.step} className={s.stale ? "stale" : "fresh"}>
                <b>{s.step.replaceAll("_", " ")}</b>
                <span>{s.stale ? "inputs changed since last run" : "up to date"}</span>
              </li>
            ))}
          </ul>
          {writable && (
            <button className="primary-button" onClick={async () => { await post("/rebuild", {}); setBump((b) => b + 1); }}>
              RUN THE PIPELINE NOW
            </button>
          )}
          <table className="data-table">
            <thead>
              <tr>
                <th>When (UTC)</th>
                <th>Trigger</th>
                <th>Steps run</th>
                <th className="num">Critical alerts</th>
              </tr>
            </thead>
            <tbody>
              {(hist.data?.history ?? []).map((h: any, i: number) => (
                <tr key={i}>
                  <td>{String(h.t).slice(0, 16).replace("T", " ")}</td>
                  <td>{h.trigger === "manual" ? "manual" : en(h.trigger)}</td>
                  <td>{(h.ran ?? []).length}</td>
                  <td className="num">{h.alerts?.kritis ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Activity" meta="EVENTS ON THIS SERVER">
          <ul className="event-list">
            {(events.data?.events ?? []).slice(-12).reverse().map((e: any) => (
              <li key={e.seq}>
                <small>{String(e.t).slice(11, 16)}</small>
                <span>
                  {e.type === "assistant.answered"
                    ? `Assistant answered “${e.data?.q ?? ""}” with ${(e.data?.tools ?? []).join(", ") || "no tools"}`
                    : e.type === "annotation.added"
                      ? `Human verdict on ${e.data?.entity ?? ""}`
                      : e.type}
                </span>
              </li>
            ))}
            {!(events.data?.events ?? []).length && <li className="muted">No activity since the server started.</li>}
          </ul>
        </Panel>

        <Panel title="Shared notes" meta={`${notes.data?.notes?.length ?? 0} NOTES`}>
          <ul className="event-list">
            {(notes.data?.notes ?? []).map((n: any, i: number) => (
              <li key={i}>
                <small>{n.author ?? "anonymous"}</small>
                <span>
                  {n.entity && <b>{String(n.entity).split(":").pop()}: </b>}
                  {n.text}
                </span>
              </li>
            ))}
            {!(notes.data?.notes ?? []).length && <li className="muted">No notes yet.</li>}
          </ul>
          {writable ? <NoteForm onDone={() => setBump((b) => b + 1)} /> : (
            <p className="panel-footnote">Adding notes is available in the researcher deployment; this public site is read-only.</p>
          )}
        </Panel>
      </div>
    </div>
  );
}

function QueueItem({ it, writable, onDone }: { it: any; writable: boolean; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const label = String(it.entity).split(":").pop();
  const verdict = async (v: string) => {
    setBusy(true);
    try {
      await post("/annotate", { entity: String(it.entity).replace(/^test:/, ""), quantity: it.quantity, verdict: v, author: "flare" });
      onDone();
    } finally {
      setBusy(false);
    }
  };
  return (
    <li>
      <div>
        {String(it.entity).startsWith("test:") ? (
          <button className="link-button" onClick={() => go("Tests", it.entity)}>
            {label}
          </button>
        ) : (
          <b>{label}</b>
        )}{" "}
        <span className="muted">{it.quantity === "ignited" ? "did it ignite?" : "video flame duration"}</span>
      </div>
      <small>{en(it.why)}</small>
      <small className="muted">{en(it.action)}</small>
      {writable && it.quantity === "ignited" && (
        <div className="verdict-row">
          <button disabled={busy} onClick={() => verdict("ya")}>ignited</button>
          <button disabled={busy} onClick={() => verdict("tidak")}>no flame</button>
          <button disabled={busy} onClick={() => verdict("ragu")}>unsure</button>
        </div>
      )}
    </li>
  );
}

function NoteForm({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState("");
  const [entity, setEntity] = useState("");
  const save = async () => {
    if (!text.trim()) return;
    await post("/note", { entity: entity.trim() || null, text, author: "flare" });
    setText("");
    onDone();
  };
  return (
    <div className="note-form">
      <input value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="test or investigation id (optional)" />
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="Write a note for the team…" />
      <button className="primary-button" onClick={save} disabled={!text.trim()}>
        SAVE NOTE
      </button>
    </div>
  );
}
