import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";
import "./motion.css";

type View = "Overview" | "Scenario" | "Gaps" | "Compare" | "Map" | "Assistant";
type IconName = "orbit" | "target" | "grid" | "compare" | "spark" | "arrow" | "check";
type EvidenceTier =
  | "nasa_table"
  | "nasa_calibrated"
  | "derived_auto"
  | "human_verified"
  | "paper_claim"
  | "model_prediction";
type EvidenceRecord = {
  label: string;
  value: string;
  tier: EvidenceTier;
  source: string;
  path: string;
  note: string;
};

const iconPaths: Record<IconName, React.ReactNode> = {
  orbit: (
    <>
      <circle cx="12" cy="12" r="3" />
      <ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(35 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4.5" transform="rotate(-35 12 12)" />
    </>
  ),
  target: (
    <>
      <circle cx="12" cy="12" r="8" />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 2v3M22 12h-3" />
    </>
  ),
  grid: (
    <>
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
    </>
  ),
  compare: (
    <>
      <path d="M8 4 4 8l4 4M4 8h14M16 20l4-4-4-4M20 16H6" />
    </>
  ),
  spark: (
    <path d="m12 2 1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5L12 2ZM19 17l.6 2.4L22 20l-2.4.6L19 23l-.6-2.4L16 20l2.4-.6L19 17Z" />
  ),
  arrow: <path d="m9 5 7 7-7 7" />,
  check: <path d="m5 12 4 4L19 6" />,
};

function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {iconPaths[name]}
    </svg>
  );
}

const navigation: { id: View; label: string; sub: string; icon: IconName }[] = [
  { id: "Overview", label: "Mission Overview", sub: "Research landscape", icon: "orbit" },
  { id: "Scenario", label: "Scenario Explorer", sub: "Mission discovery", icon: "target" },
  { id: "Gaps", label: "Gaps Analysis", sub: "Evidence coverage", icon: "grid" },
  { id: "Compare", label: "Comparison", sub: "Scientific analysis", icon: "compare" },
  { id: "Map", label: "Research Map", sub: "Citation network", icon: "orbit" },
  { id: "Assistant", label: "AI Assistant", sub: "Knowledge query", icon: "spark" },
];

const investigations = [
  {
    name: "FLEX",
    objective: "Suppression",
    match: 96,
    tests: "indexed",
    note: "Droplet flame extinguishment through atmospheric dilution",
  },
  {
    name: "BASS-II",
    objective: "Flame spread",
    match: 94,
    tests: 288,
    note: "Solid fuel burning and extinction boundaries",
  },
  {
    name: "ACME / CFI-G",
    objective: "Ignition",
    match: 87,
    tests: 320,
    note: "Gaseous flame response and raw telemetry",
  },
  {
    name: "SPICE",
    objective: "Detection",
    match: 76,
    tests: 55,
    note: "Smoke particle generation and transport",
  },
  {
    name: "SAFFIRE",
    objective: "Suppression",
    match: 69,
    tests: 18,
    note: "Large-scale spacecraft fire behavior",
  },
];

const heatmap = [
  [1, 2, 3, 2, 1, 0],
  [2, 3, 4, 4, 2, 1],
  [1, 3, 5, 4, 3, 1],
  [0, 2, 4, 5, 4, 2],
  [0, 1, 2, 3, 3, 1],
];

import { ask as askApi, feedback as sendFeedback, TIER_LABEL, type AskReply, type RankRow } from "./api";
import { useInsight, useResearchMap, useStatus, fmt } from "./useData";
import { AnswerText, ReplyMedia } from "./chatRender";
import { CitationGraph } from "./citationGraph";
import { STUDY_BY_ACCESSION, STUDY_HTML } from "./motion";

/** Rute hash sederhana: #Scenario, #Assistant, ... supaya setiap tampilan bisa
 *  ditautkan langsung (berguna saat demo dan saat juri membuka ulang halaman). */
const VIEWS: View[] = ["Overview", "Scenario", "Gaps", "Compare", "Map", "Assistant"];
const viewFromHash = (): View => {
  const h = decodeURIComponent(location.hash.replace("#", "")) as View;
  return VIEWS.includes(h) ? h : "Overview";
};

function App() {
  const [view, setViewRaw] = useState<View>(viewFromHash);
  const setView = (v: View) => {
    setViewRaw(v);
    if (location.hash !== `#${v}`) history.replaceState(null, "", `#${v}`);
  };
  useEffect(() => {
    const onHash = () => setViewRaw(viewFromHash());
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);
  const [noticeOpen, setNoticeOpen] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to research workspace
      </a>
      <CombustionBackdrop />
      <div className="grain" aria-hidden="true" />
      <Header onDemo={() => setDemoOpen(true)} />
      <Sidebar view={view} setView={setView} />
      <main className="workspace" id="main-content" tabIndex={-1}>
        {noticeOpen && (
          <div className="data-notice">
            <span className="notice-mark">i</span>
            <p>
              <strong>Research dataset.</strong> NASA PSI and NTRS-derived records. Empty values
              mean “not reported,” never zero. Telemetry values are raw voltages unless explicitly
              calibrated.
            </p>
            <button onClick={() => setNoticeOpen(false)} aria-label="Dismiss data notice">
              ×
            </button>
          </div>
        )}
        {view === "Overview" && <Overview onNavigate={setView} onEvidence={setEvidence} />}
        {view === "Scenario" && <Scenario onEvidence={setEvidence} />}
        {view === "Gaps" && <Gaps />}
        {view === "Compare" && <Comparison />}
        {view === "Map" && <ResearchMap onEvidence={setEvidence} />}
        {view === "Assistant" && <Assistant />}
      </main>
      <Footer />
      <FloatingAssistant
        open={chatOpen}
        onToggle={() => setChatOpen((current) => !current)}
        onOpenFull={() => {
          setView("Assistant");
          setChatOpen(false);
        }}
      />
      {evidence && <ProvenanceDrawer record={evidence} onClose={() => setEvidence(null)} />}
      {demoOpen && (
        <DemoPanel
          onClose={() => setDemoOpen(false)}
          onNavigate={(next) => {
            setView(next);
            setDemoOpen(false);
          }}
        />
      )}
    </div>
  );
}

function CombustionBackdrop() {
  return (
    <div className="combustion-scene" aria-hidden="true">
      <svg
        className="combustion-backdrop"
        viewBox="0 0 1600 900"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <radialGradient id="blueFlame" cx="46%" cy="48%" r="52%">
            <stop offset="0" stopColor="#d6f7ff" stopOpacity=".82" />
            <stop offset=".16" stopColor="#79d8e8" stopOpacity=".64" />
            <stop offset=".42" stopColor="#29839a" stopOpacity=".34" />
            <stop offset=".72" stopColor="#123f52" stopOpacity=".13" />
            <stop offset="1" stopColor="#0b2330" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="warmCore" cx="50%" cy="62%" r="50%">
            <stop offset="0" stopColor="#f4d0a4" stopOpacity=".85" />
            <stop offset=".2" stopColor="#d27b43" stopOpacity=".55" />
            <stop offset=".55" stopColor="#7e3724" stopOpacity=".18" />
            <stop offset="1" stopColor="#321711" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="sphericalShell" cx="48%" cy="48%" r="52%">
            <stop offset="0" stopColor="#d7fbff" stopOpacity=".05" />
            <stop offset=".34" stopColor="#b9f4fb" stopOpacity=".12" />
            <stop offset=".56" stopColor="#67d4e5" stopOpacity=".42" />
            <stop offset=".7" stopColor="#277e9b" stopOpacity=".24" />
            <stop offset=".88" stopColor="#123e5c" stopOpacity=".08" />
            <stop offset="1" stopColor="#0a2035" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="reactionCore" cx="46%" cy="52%" r="50%">
            <stop offset="0" stopColor="#f8e5c8" stopOpacity=".7" />
            <stop offset=".13" stopColor="#e7a36f" stopOpacity=".48" />
            <stop offset=".3" stopColor="#70d9e5" stopOpacity=".42" />
            <stop offset=".58" stopColor="#27839e" stopOpacity=".16" />
            <stop offset="1" stopColor="#12364a" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="warmWisp" x1="0" y1="1" x2=".6" y2="0">
            <stop offset="0" stopColor="#d77b43" stopOpacity=".5" />
            <stop offset=".65" stopColor="#a34b31" stopOpacity=".15" />
            <stop offset="1" stopColor="#73301f" stopOpacity="0" />
          </linearGradient>
          <filter id="softBlur">
            <feGaussianBlur stdDeviation="18" />
          </filter>
          <filter id="wideBlur">
            <feGaussianBlur stdDeviation="42" />
          </filter>
          <filter id="flameTexture" x="-30%" y="-30%" width="160%" height="160%">
            <feTurbulence
              type="fractalNoise"
              baseFrequency=".012 .026"
              numOctaves="2"
              seed="7"
              result="noise"
            />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="12" />
            <feGaussianBlur stdDeviation="1.4" />
          </filter>
        </defs>

        <g className="blue-flame">
          <circle cx="1260" cy="370" r="228" fill="url(#blueFlame)" filter="url(#wideBlur)" />
          <circle cx="1260" cy="370" r="138" fill="none" stroke="#79d9e7" strokeOpacity=".12" />
          <circle cx="1260" cy="370" r="101" fill="url(#blueFlame)" />
          <ellipse
            cx="1247"
            cy="380"
            rx="52"
            ry="68"
            fill="url(#warmCore)"
            opacity=".42"
            filter="url(#softBlur)"
          />
          <path
            className="blue-wisp wisp-one"
            d="M1120 403c67-98 78-178 153-241-20 80 24 110 10 167-17 65-78 105-163 74Z"
            fill="#58bfd3"
            opacity=".09"
          />
          <path
            className="blue-wisp wisp-two"
            d="M1300 508c67-73 128-121 146-208 20 82-10 176-84 221-30 18-51 10-62-13Z"
            fill="#87e5ef"
            opacity=".07"
          />
        </g>

        <g className="micro-flame flame-a" filter="url(#flameTexture)">
          <circle cx="760" cy="710" r="106" fill="url(#sphericalShell)" />
          <ellipse cx="755" cy="714" rx="51" ry="58" fill="url(#reactionCore)" />
          <circle
            cx="760"
            cy="710"
            r="74"
            fill="none"
            stroke="#7bddea"
            strokeOpacity=".13"
            strokeWidth="3"
          />
          <ellipse
            cx="767"
            cy="715"
            rx="88"
            ry="76"
            fill="none"
            stroke="#9b6b4e"
            strokeOpacity=".09"
            strokeWidth="6"
            strokeDasharray="31 13"
          />
        </g>

        <g className="micro-flame flame-b" filter="url(#flameTexture)">
          <circle cx="1460" cy="690" r="78" fill="url(#sphericalShell)" />
          <ellipse cx="1456" cy="694" rx="38" ry="42" fill="url(#reactionCore)" />
          <circle
            cx="1460"
            cy="690"
            r="55"
            fill="none"
            stroke="#72d5e4"
            strokeOpacity=".14"
            strokeWidth="2"
          />
        </g>

        <g className="micro-flame flame-c" filter="url(#flameTexture)">
          <circle cx="1045" cy="205" r="53" fill="url(#sphericalShell)" />
          <ellipse cx="1042" cy="208" rx="24" ry="28" fill="url(#reactionCore)" />
        </g>
      </svg>

      <div className="ember-field">
        {Array.from({ length: 10 }, (_, index) => (
          <i key={index} />
        ))}
      </div>
      <span className="generated-visual-label">
        Generative microgravity flame study · decorative
      </span>
    </div>
  );
}

function Header({ onDemo }: { onDemo: () => void }) {
  return (
    <header className="topbar">
      <div className="brand">
        <img className="brand-mark" src="flare-logo.png" alt="Flame in Freefall" />
        <div>
          <strong>FLARE+</strong>
          <small>Freefall Laboratory Analysis, Ranking & Evidence</small>
        </div>
      </div>
      <div className="header-center">
        <div className="source-state">
          AI-assisted evidence navigation for microgravity combustion research.
        </div>
        <button className="demo-button" onClick={onDemo}>
          PRESENTATION MODE
        </button>
      </div>
      <HeaderMetrics />
    </header>
  );
}

/** Angka kepala dari /insight_data (sebelumnya 24 / 1,990 / 352 ditulis keras). */
function HeaderMetrics() {
  const { data } = useInsight();
  const total = (k: string) => (data?.totals || []).find((t: any) => t.key === k)?.value;
  return (
    <div className="header-metrics">
      <span>
        <b>{fmt(total("investigations"))}</b> Investigations
      </span>
      <span>
        <b>{fmt(total("tests"))}</b> Tests
      </span>
      <span>
        <b>{fmt(data?.corpus?.publications)}</b> Publications
      </span>
    </div>
  );
}

function Sidebar({ view, setView }: { view: View; setView: (view: View) => void }) {
  return (
    <aside className="sidebar" aria-label="Research workspace">
      <div className="side-caption">Workspace</div>
      <nav>
        {navigation.map((item, index) => (
          <button
            key={item.id}
            className={view === item.id ? "active" : ""}
            onClick={() => setView(item.id)}
          >
            <span className="nav-number">0{index + 1}</span>
            <span className="nav-icon">
              <Icon name={item.icon} size={17} />
            </span>
            <span className="nav-copy">
              <strong>{item.label}</strong>
              <small>{item.sub}</small>
            </span>
          </button>
        ))}
      </nav>
      <div className="source-card">
        <span>DATA CONNECTION</span>
        <strong>
          <i /> NASA PSI REPOSITORY
        </strong>
        <p>Layered research outputs with source traceability.</p>
        <a href="https://psi.nasa.gov/physci/repo" target="_blank" rel="noreferrer">
          OPEN SOURCE ↗
        </a>
      </div>
    </aside>
  );
}

function PageTitle({
  index,
  overline,
  title,
  description,
}: {
  index: string;
  overline: string;
  title: string;
  description: string;
}) {
  return (
    <div className="page-title">
      <span>
        {index} / {overline}
      </span>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}

function Panel({
  title,
  meta,
  className = "",
  children,
}: {
  title: string;
  meta?: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <header>
        <span>{title}</span>
        {meta && <small>{meta}</small>}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

function Overview({
  onNavigate,
  onEvidence,
}: {
  onNavigate: (view: View) => void;
  onEvidence: (record: EvidenceRecord) => void;
}) {
  return (
    <div className="page overview-page">
      <PageTitle
        index="01"
        overline="RESEARCH LANDSCAPE"
        title="From freefall flames to safer habitats."
        description="FLARE+ ranks investigations, traces evidence, and exposes uncertainty for spacecraft, lunar bases, Mars habitats, and pressurized rovers."
      />
      <div className="title-actions">
        <button className="primary-button" onClick={() => onNavigate("Scenario")}>
          START A SCENARIO <Icon name="arrow" size={13} />
        </button>
        <button className="text-button" onClick={() => onNavigate("Gaps")}>
          EXPLORE RESEARCH GAPS ↗
        </button>
      </div>

      <StatStrip onEvidence={onEvidence} />
      <div className="trust-strip">
        <span>AI-assisted</span>
        <span>Tool-grounded</span>
        <span>Source-traceable</span>
        <p>
          Independent project using public NASA PSI and NTRS data. Not an official NASA product.
        </p>
      </div>

      <div className="overview-grid">
        <Panel
          title="Research distribution"
          meta="FIRE-SAFETY PILLAR · LIVE"
          className="distribution-panel"
        >
          <PillarDistribution />
        </Panel>

        <Panel
          title="Publications over time"
          meta="RESEARCH MAP PAPERS · BY YEAR"
          className="timeline-panel"
        >
          <PaperTimeline />
        </Panel>

        <Panel title="Indexed themes" meta="NTRS TOPIC TAGS · LIVE" className="network-panel">
          <TopicLedger />
        </Panel>

        <Panel title="Research watchlist" meta="EVIDENCE INTERPRETATION" className="watch-panel">
          <Watch
            number="01"
            title="Microgravity alters transport"
            text="Review buoyancy, diffusion, and imposed ventilation separately."
          />
          <Watch
            number="02"
            title="Partial-gravity evidence is sparse"
            text="Do not treat microgravity data as validated lunar or Martian predictions."
          />
          <Watch
            number="03"
            title="Coverage is not validation"
            text="Track missing metadata and transferability apart from test counts."
          />
        </Panel>
      </div>
    </div>
  );
}

/** Peringkat investigasi per skenario habitat, dari /insight_data.
 *  Skor dan ketiga komponennya ditampilkan apa adanya, lengkap dengan alasannya --
 *  bukan angka "match" tanpa penjelasan seperti di mockup. */
function Scenario({ onEvidence }: { onEvidence: (record: EvidenceRecord) => void }) {
  const { data, error, retry } = useInsight();
  const [sid, setSid] = useState<string>("surface");

  if (error && !data) return <ViewError what="scenario ranking" detail={error} onRetry={retry} />;
  if (!data) return <ViewLoading />;

  const sc: any = data.scenario[sid];
  const ranking = (sc?.ranking ?? []) as RankRow[];
  const phase = (sc?.phase ?? {}) as Record<string, any>;

  return (
    <div className="page">
      <PageTitle
        index="02"
        overline="MISSION DISCOVERY"
        title="Scenario Explorer"
        description="Pick where the crew will live. Every investigation is re-ranked for that atmosphere, and each score says why."
      />
      {error && <ConnectionNotice onRetry={retry} />}

      <div className="segmented objective-segmented">
        {data.scenarios.map((id) => (
          <button key={id} className={id === sid ? "active" : ""} onClick={() => setSid(id)}>
            {data.scenario[id]?.short || data.scenario[id]?.name || id}
          </button>
        ))}
      </div>

      {sc?.headline && (
        <Panel title="What the data says" meta="SCENARIO HEADLINE">
          <div className="headline-with-stage">
            <div>
              <p className="score-heading">{sc.headline}</p>
              <p className="panel-footnote">{sc.basis}</p>
            </div>
            {/* aset motion kit Figma untuk habitat; sebelumnya tidak dipakai sama sekali */}
            <StudyStage study={SCENARIO_STUDY[sid]} label={(sc.name || sid) + " — conceptual illustration"} />
          </div>
        </Panel>
      )}

      <div className="scenario-layout">
        <Panel
          title="Investigations ranked for this atmosphere"
          meta={ranking.length + " RANKED"}
          className="result-panel"
        >
          <div className="results-stack">
            {ranking.slice(0, 10).map((r, i) => (
              <article key={r.accession} className="rank-card">
                <header>
                  <span className="rank-no">{String(i + 1).padStart(2, "0")}</span>
                  <StudyMark accession={r.accession} title={r.name} />
                  <div className="rank-id">
                    <strong>{r.name}</strong>
                    <small>{r.pillars.join(" / ") || "—"}</small>
                  </div>
                  <b className="rank-score">{r.score.toFixed(2)}</b>
                </header>
                <p className="rank-why">{r.why?.conditions}</p>
                <div className="rank-bars">
                  <Bar label="Direct link" value={r.components.direct} weight={data.weights.direct} />
                  <Bar label="Conditions" value={r.components.conditions} weight={data.weights.conditions} />
                  <Bar label="Evidence" value={r.components.evidence} weight={data.weights.evidence} />
                </div>
                {r.stability && (
                  <p className="rank-stability">
                    keeps rank {i + 1} in {Math.round(r.stability.keep * 100)}% of random weightings
                    {" "}(range {r.stability.lo}-{r.stability.hi})
                  </p>
                )}
                <button
                  className="text-button"
                  onClick={() =>
                    onEvidence({
                      label: r.name + " score " + r.score.toFixed(2),
                      value: r.score.toFixed(2),
                      tier: "derived_auto",
                      source: "Ranking computed from NASA PSI tables",
                      path: "insight_data -> scenario." + sid + ".ranking",
                      note:
                        (data.method?.score || "") +
                        " Direct: " + (r.why?.direct || "") +
                        " Evidence: " + (r.why?.evidence || ""),
                    })
                  }
                >
                  WHY THIS SCORE
                </button>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Atmosphere and coverage" meta="SCENARIO BAND" className="parameter-panel">
          <div className="preset-block">
            <Field label="Oxygen band">
              <b>
                {Math.round((sc.o2?.[0] ?? 0) * 100)}-{Math.round((sc.o2?.[1] ?? 0) * 100)}%
              </b>
            </Field>
            <Field label="Pressure band">
              <b>
                {sc.p_kpa?.[0]} - {sc.p_kpa?.[1]} kPa
              </b>
            </Field>
            <Field label="Gravity">
              <b>{sc.gravity}</b>
            </Field>
            <Field label="Tests inside the band">
              <b>{sc.n_near}</b>
            </Field>
          </div>
          <div className="compatibility">
            {Object.entries(phase).map(([k, v]: [string, any]) => (
              <Compat
                key={k}
                label={k}
                value={v.n_in_band + " of " + v.n_tests + " in band"}
                score={v.n_tests ? v.n_in_band / v.n_tests : 0}
              />
            ))}
          </div>
          <p className="panel-footnote">
            Empty means "not reported", never zero. A phase with 0 in band is a gap, not a safe result.
          </p>
        </Panel>
      </div>

      {Array.isArray(sc.models) && sc.models.length > 0 && (
        <Panel title="Model predictions at the band centre" meta="MODEL PREDICTION">
          <div className="preset-grid">
            {sc.models.map((m: any, i: number) => (
              <div key={i} className="prediction-card">
                <span>{m.what}</span>
                <EvidenceBadge tier="model_prediction" />
                {m.valid ? (
                  <>
                    <strong className="prediction-value">
                      {/* backend: p_extinction (FLEX) atau p_ignite (CFI-G); sebelumnya dibaca
                          sebagai p_ignition sehingga semua kartu CFI-G tampil "—" */}
                      {m.p_extinction != null
                        ? "P(goes out) " + m.p_extinction
                        : (m.p_ignite ?? m.p_ignition) != null
                          ? "P(ignites) " + (m.p_ignite ?? m.p_ignition)
                          : "—"}
                    </strong>
                    {m.K_mm2_s != null && <small>burning-rate constant K {m.K_mm2_s} mm²/s</small>}
                  </>
                ) : (
                  <strong className="prediction-value extrapolation-warning">
                    model does not answer - outside the tested range
                  </strong>
                )}
                <small>{m.input}</small>
              </div>
            ))}
          </div>
          <p className="panel-footnote">
            Model output, not a measurement. Models refuse to answer outside the conditions they were
            fitted on, and PSI holds no partial-gravity data at all.
          </p>
        </Panel>
      )}
    </div>
  );
}

/** Celah bukti dan uji berikutnya yang paling informatif, dari data yang sama. */
function Gaps() {
  const { data, error, retry } = useInsight();
  const [sid, setSid] = useState<string>("surface");
  if (error && !data) return <ViewError what="gap analysis" detail={error} onRetry={retry} />;
  if (!data) return <ViewLoading />;
  const sc: any = data.scenario[sid];
  const gaps = (sc?.gaps ?? []) as { level: string; title: string; text: string }[];
  const next = (sc?.next_tests ?? []) as any[];

  return (
    <div className="page">
      <PageTitle
        index="03"
        overline="EVIDENCE COVERAGE"
        title="Gaps Analysis"
        description="What the archive cannot answer for this habitat, and which experiment would teach the most."
      />
      {error && <ConnectionNotice onRetry={retry} />}
      <div className="segmented objective-switch">
        {data.scenarios.map((id) => (
          <button key={id} className={id === sid ? "active" : ""} onClick={() => setSid(id)}>
            {data.scenario[id]?.short || id}
          </button>
        ))}
      </div>

      <div className="gaps-grid">
        <Panel title="What is not known here" meta={gaps.length + " FINDINGS"} className="quality-panel">
          <div className="gap-list">
            {gaps.map((g, i) => (
              <article key={i} className="quality-facts">
                <span className={"gap-level " + g.level}>{g.level}</span>
                <strong>{g.title}</strong>
                <p>{g.text}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Most informative next tests" meta="ACTIVE LEARNING" className="heat-panel">
          <div className="table-scroll">
            <table className="next-tests">
              <thead>
                <tr>
                  <th>Experiment</th>
                  <th>O2</th>
                  <th>kPa</th>
                  <th>Conditions</th>
                  <th>U</th>
                  <th>In band</th>
                </tr>
              </thead>
              <tbody>
                {next.map((n, i) => (
                  <tr key={i}>
                    <td>{n.exp}</td>
                    <td>{(n.o2 * 100).toFixed(1)}%</td>
                    <td>{n.p_kpa}</td>
                    <td>{n.detail}</td>
                    <td>{n.U}</td>
                    <td>{n.in_band ? "yes" : "no"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="panel-footnote">
            Ranked by the U-function of a Gaussian-process boundary model: a small U means the model
            is least sure whether the flame ignites there, so one test teaches the most. Candidates
            stay close to conditions that were actually flown.
          </p>
        </Panel>
      </div>

      <div className="gaps-grid">
        <Panel title="Gravity" meta="KNOWN LIMIT" className="quality-panel">
          <ul className="gap-list">
            {(data.partial_gravity ?? []).map((t: string, i: number) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </Panel>
        <Panel title="Back on Earth" meta="SPINOFF" className="quality-panel">
          <div className="gap-list">
            {(data.earth ?? []).map((e: any, i: number) => (
              <article key={i} className="quality-facts">
                <strong>{e.title || e.name}</strong>
                <p>{e.text || e.detail}</p>
                {/* dihitung di sini seperti /insight/: backend tidak mengirim same_pillar,
                    jadi baris ini dulu tidak pernah tampil */}
                {(() => {
                  const invs = (data.investigations ?? [])
                    .filter((c: any) => c.direct >= 0.8 && (c.pillars ?? []).includes(e.pillar))
                    .map((c: any) => c.name);
                  return invs.length ? <small>Same pillar in PSI ({e.pillar}): {invs.join(", ")}</small> : null;
                })()}
              </article>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

/** Satu komponen skor: nilai 0-1, lebar bar = nilai, dan sumbangannya ke skor
 *  akhir (nilai x bobot) -- supaya pembaca melihat dari mana angka total berasal. */
function Bar({ label, value, weight }: { label: string; value: number; weight: number }) {
  return (
    <div className="rank-bar">
      <span>{label}</span>
      <i>
        <b style={{ width: Math.max(2, value * 100) + "%" }} />
      </i>
      <small>
        {value.toFixed(2)} x {weight} = {(value * weight).toFixed(3)}
      </small>
    </div>
  );
}

/** Penanda visual tiap investigasi: animasi konseptual, diberi label "concept"
 *  supaya tidak pernah disalahartikan sebagai rekaman eksperimen atau data. */
/** Habitat per skenario -> animasi motion kit (ilustrasi konseptual, bukan data). */
const SCENARIO_STUDY: Record<string, string> = {
  cabin: "iss-study",
  surface: "lunar-study",
  suit: "suit-study",
  earth: "mist-study",
};

/**
 * Panggung animasi motion kit dirancang pada ukuran tetap (~300 x 210 px).
 * Sebelumnya panggung diberi ukuran kotak kecil (54 x 40) LALU diperkecil lagi
 * scale(0.26), sehingga animasinya tergambar di area ~14 x 10 px dan tampak
 * sebagai kotak gelap kosong. Kini panggung tetap 300 x 210 dan diperkecil utuh.
 */
function StudyMark({ accession, title, size = "small" }: { accession: string; title?: string; size?: "small" | "large" }) {
  const key = STUDY_BY_ACCESSION[accession];
  const markup = key ? STUDY_HTML[key] : undefined;
  if (!markup) return null;
  return (
    <div className={`study-mark ${size}`} role="img" aria-label={(title || accession) + " — conceptual illustration"}>
      <div className={"stage " + key} dangerouslySetInnerHTML={{ __html: markup }} />
      <span className="study-tag">concept</span>
    </div>
  );
}

function StudyStage({ study, label }: { study?: string; label: string }) {
  const markup = study ? STUDY_HTML[study] : undefined;
  if (!markup) return null;
  return (
    <div className="study-stage" role="img" aria-label={label}>
      <div className={"stage " + study} dangerouslySetInnerHTML={{ __html: markup }} />
      <span className="study-tag">concept</span>
    </div>
  );
}

// Status muat/galat/kosong yang konsisten + tombol coba lagi (pola dari referensi mobile nasa3).
function ViewLoading() {
  return (
    <div className="page">
      <InlineState kind="loading" title="Reading the evidence model" />
    </div>
  );
}

function ViewError({ what, detail, onRetry }: { what: string; detail?: string; onRetry?: () => void }) {
  return (
    <div className="page">
      <InlineState
        kind="error"
        title={`${what} unavailable`}
        detail={`No example numbers have been substituted.${detail ? ` (${detail})` : ""}`}
        onRetry={onRetry}
      />
    </div>
  );
}

function InlineState({ kind, title, detail, onRetry }: {
  kind: "loading" | "error" | "empty";
  title: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <section className={`view-state ${kind}`} role={kind === "error" ? "alert" : "status"} aria-live="polite">
      <strong>{title}</strong>
      {detail && <p>{detail}</p>}
      {onRetry && (
        <button className="primary-button" onClick={onRetry}>
          RETRY CONNECTION
        </button>
      )}
    </section>
  );
}

/** Koneksi putus SETELAH data termuat: data lama tetap tampil, dengan peringatan + coba lagi. */
function ConnectionNotice({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="connection-notice" role="status">
      <span>Connection interrupted. Showing the last successfully loaded evidence.</span>
      <button className="text-button" onClick={onRetry}>
        RETRY
      </button>
    </div>
  );
}

/** Banding investigasi berdampingan, dari kartu /insight_data.
 *  Mockup membandingkan dua nama tetap; ini membiarkan pengguna memilih,
 *  dan menandai lapangan yang memang tidak ditabulasi NASA. */
const named = (xs: any, total?: number) => {
  if (!Array.isArray(xs) || !xs.length) return null;
  const head = xs.slice(0, 4).map((x: any) => (x?.name ? `${x.name} (${x.n})` : String(x)));
  const rest = (total ?? xs.length) - head.length;
  return head.join(", ") + (rest > 0 ? ` +${rest}` : "");
};

/** Variabel yang diubah-ubah vs dijaga tetap -- pertanyaan eksplisit di brief
 *  tantangan ("how did tests from the same investigation differ?"). */
const varied = (v: any) => {
  if (!v || typeof v !== "object") return null;
  const on = Object.entries(v).filter(([, k]) => k === "varied").map(([k]) => k);
  const off = Object.entries(v).filter(([, k]) => k === "constant").map(([k]) => k);
  const parts = [];
  if (on.length) parts.push("varied: " + on.join(", "));
  if (off.length) parts.push("constant: " + off.join(", "));
  return parts.join(" · ") || null;
};

function Comparison() {
  const { data, error, retry } = useInsight();
  const [sel, setSel] = useState<string[]>([]);
  if (error && !data) return <ViewError what="comparison" detail={error} onRetry={retry} />;
  if (!data) return <ViewLoading />;

  const cards: any[] = data.investigations;
  const picked = sel.length ? sel : cards.slice(0, 3).map((c) => c.accession);
  const chosen = picked.map((acc) => cards.find((c) => c.accession === acc)).filter(Boolean);

  const toggle = (acc: string) =>
    setSel((cur) => {
      const base = cur.length ? cur : cards.slice(0, 3).map((c) => c.accession);
      return base.includes(acc) ? base.filter((x) => x !== acc) : [...base, acc].slice(-4);
    });

  const rows: [string, (c: any) => any][] = [
    ["Full title", (c) => c.title],
    ["Pillars", (c) => (c.pillars || []).join(" / ")],
    ["Facility", (c) => c.facility || c.hardware],
    ["Platform", (c) => c.platform],
    ["Years", (c) => (Array.isArray(c.years) ? c.years.join("–") : c.years)],
    ["Fuel phases", (c) => (c.phases || []).join(", ")],
    // fuels/samples adalah [{name, n}], bukan string: tanpa .name hasilnya "[object Object]".
    ["Fuels", (c) => named(c.fuels, c.n_fuels)],
    ["Samples", (c) => named(c.samples)],
    ["Sample size", (c) => c.size_mm],
    ["Variables", (c) => varied(c.variables)],
    ["Oxygen range", (c) => (c.o2 ? `${(c.o2[0] * 100).toFixed(0)}–${(c.o2[1] * 100).toFixed(0)}%` : null)],
    ["Pressure range", (c) => (c.p_kpa ? `${c.p_kpa[0]}–${c.p_kpa[1]} kPa` : null)],
    ["Flow", (c) => (c.flow_cm_s ? `${c.flow_cm_s[0]}–${c.flow_cm_s[1]} cm/s` : null)],
    ["Diluents", (c) => (c.diluents || []).join(", ")],
    ["Rows in NASA table", (c) => c.n_rows],
    ["Result values", (c) => c.n_results],
    ["Publications", (c) => c.n_publications],
    ["Files listed / local", (c) => `${c.files_listed} / ${c.files_local}`],
  ];

  return (
    <div className="page">
      <PageTitle
        index="04"
        overline="SCIENTIFIC ANALYSIS"
        title="Comparison"
        description="Put investigations side by side on the attributes the challenge asks about: fuels, conditions, variables and sensors."
      />
      {error && <ConnectionNotice onRetry={retry} />}
      <Panel title="Pick investigations" meta={`${chosen.length} SELECTED`}>
        <div className="pick-grid">
          {cards.map((c) => (
            <button
              key={c.accession}
              className={picked.includes(c.accession) ? "pick on" : "pick"}
              onClick={() => toggle(c.accession)}
            >
              {c.name || c.accession}
            </button>
          ))}
        </div>
      </Panel>
      <Panel title="Side by side" meta="NASA TABLE + DERIVED">
        <div className="cmp-wrap">
          <table className="cmp">
            <thead>
              <tr>
                <th />
                {chosen.map((c: any) => (
                  <th key={c.accession}>
                    <StudyMark accession={c.accession} title={c.name} size="large" />
                    {c.name}
                    <small>{c.accession}</small>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map(([label, get]) => (
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
        <p className="panel-footnote">
          "not tabulated" means NASA did not record that field for the investigation. It is never a
          zero and never a judgement about the experiment.
        </p>
      </Panel>
    </div>
  );
}

/** Peta riset: 465 simpul, 516 tautan. Jenis tautan ditampilkan apa adanya --
 *  termasuk bahwa kemiripan topik BUKAN sitasi. */
function ResearchMap({ onEvidence }: { onEvidence: (record: EvidenceRecord) => void }) {
  const [map, setMap] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [kind, setKind] = useState<string>("all");

  useEffect(() => {
    const ac = new AbortController();
    fetch("research_map.json", { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
      .then(setMap)
      .catch((e) => {
        if (e.name !== "AbortError") setErr(String(e));
      });
    return () => ac.abort();
  }, []);

  if (err) return <ViewError what="research map" detail={err} />;
  if (!map) return <ViewLoading />;

  const nodes: any[] = map.nodes || [];
  const edges: any[] = (map.edges || []).filter((e: any) => kind === "all" || e.k === kind);
  const invs = nodes.filter((n) => n.kind === "investigation");
  const kinds = Array.from(new Set((map.edges || []).map((e: any) => e.k))) as string[];

  // Hitung tautan per investigasi untuk sorotan sederhana (tanpa grafik gaya pegas:
  // 465 simpul akan jadi bola benang yang tidak terbaca).
  const deg: Record<number, number> = {};
  edges.forEach((e: any) => {
    deg[e.s] = (deg[e.s] || 0) + 1;
    deg[e.t] = (deg[e.t] || 0) + 1;
  });

  return (
    <div className="page">
      <PageTitle
        index="05"
        overline="EVIDENCE NETWORK"
        title="Research Map"
        description="How investigations, papers and topics connect — and how that connection was established."
      />
      <Panel title="Citation network" meta="INDEXED PAPERS → WHAT THEY CITE → COMMON ROOTS" className="cite-panel">
        <CitationGraph />
      </Panel>

      <div className="segmented objective-switch">
        <button className={kind === "all" ? "active" : ""} onClick={() => setKind("all")}>
          all links
        </button>
        {kinds.map((k) => (
          <button key={k} className={kind === k ? "active" : ""} onClick={() => setKind(k)}>
            {k}
          </button>
        ))}
      </div>

      <div className="gaps-grid">
        <Panel title="Link types" meta="HOW THE EDGE WAS MADE" className="quality-panel">
          <div className="gap-list">
            {Object.entries(map.method || {}).map(([k, v]) => (
              <article key={k} className="quality-facts">
                <strong>{k}</strong>
                <p>{String(v)}</p>
              </article>
            ))}
          </div>
          <p className="panel-footnote">
            Topic similarity is not a citation. Real citations are in the citation network above
            (reference lists from OpenAlex).
          </p>
        </Panel>

        <Panel title="Investigations by evidence attached" meta={`${edges.length} LINKS SHOWN`} className="quality-panel">
          <div className="gap-list">
            {invs
              .map((n) => ({ n, d: deg[nodes.indexOf(n)] || 0 }))
              .sort((x, y) => y.d - x.d)
              .slice(0, 12)
              .map(({ n, d }) => (
                <div key={n.id} className="rank-bar">
                  <span>{n.label}</span>
                  <i>
                    <b style={{ width: Math.max(2, (d / Math.max(1, Math.max(...Object.values(deg)))) * 100) + "%" }} />
                  </i>
                  <small>{d} links</small>
                </div>
              ))}
          </div>
          <button
            className="text-button"
            onClick={() =>
              onEvidence({
                label: "Research map",
                value: `${nodes.length} nodes / ${map.edges.length} links`,
                tier: "derived_auto",
                source: "Built from PSI publication lists, NTRS tags and LSA topic similarity",
                path: "app/insight/research_map.json",
                note: JSON.stringify(map.stats),
              })
            }
          >
            HOW THIS MAP WAS BUILT
          </button>
        </Panel>
      </div>
    </div>
  );
}

function Assistant() {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const { data } = useInsight();
  const st = useStatus();
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      text:
        "Ask about investigations, experimental conditions, publications, or evidence gaps. " +
        "Every number in my answer is checked against the tool output that produced it.",
    },
  ]);

  const send = async (q: string) => {
    if (!q.trim() || busy) return;
    setQuestion("");
    setBusy(true);
    setMessages((c) => [...c, { role: "user", text: q }, { role: "assistant", text: "", pending: true }]);
    // Backend (brain.py clean_history) menerima pasangan {q, a}. Sebelumnya dikirim
    // {role, content}, yang dibuang seluruhnya: pertanyaan lanjutan kehilangan konteks.
    const history: { q: string; a: string }[] = [];
    messages.forEach((m, i) => {
      const next = messages[i + 1];
      if (m.role === "user" && next?.role === "assistant" && !next.pending && !next.failed)
        history.push({ q: m.text, a: next.text });
    });
    try {
      const reply = await askApi(q, history);
      setMessages((c) => [
        ...c.slice(0, -1),
        { role: "assistant", text: reply.answer, reply, q },
      ]);
    } catch (e) {
      setMessages((c) => [
        ...c.slice(0, -1),
        {
          role: "assistant",
          text:
            "The backend did not answer (" + String(e) + "). Nothing is shown rather than a guess; " +
            "the public deployment also limits questions per visitor.",
          failed: true,
        },
      ]);
    } finally {
      setBusy(false);
    }
  };

  const suggested: string[] = data?.suggested?.length
    ? data.suggested
    : ["Which investigations matter most for a Moon base?", "Compare FLEX and BASS-II"];

  return (
    <div className="page assistant-page">
      <PageTitle
        index="06"
        overline="KNOWLEDGE QUERY"
        title="Research Assistant"
        description="Interrogate the indexed NASA PSI and NTRS corpus while keeping source level, missing data, and scientific limitations visible."
      />
      <div className={`assistant-status ${st && !st.llm ? "offline" : ""}`}>
        <span>
          <i /> ASSISTANT MODE
        </span>
        <strong>
          {st === null
            ? "Checking backend…"
            : st.llm
              ? `Tool-grounded · ${st.provider}`
              : "Offline rule-based planner"}
        </strong>
        <b>
          {st && st.llm
            ? "Every numerical claim is checked against tool output before display"
            : "No language-model call · read-only tools available"}
        </b>
      </div>
      <div className="assistant-layout">
        <Panel
          title="Knowledge conversation"
          meta={st && st.llm ? "SOURCE-GROUNDED MODE" : "OFFLINE FALLBACK"}
          className="chat-panel"
        >
          <div className="messages">
            {messages.map((m, i) => (
              <div key={i} className={`message ${m.role}`}>
                <span>{m.role === "assistant" ? "FI" : "YOU"}</span>
                {m.pending ? (
                  <p className="thinking">Calling tools…</p>
                ) : m.role === "assistant" ? (
                  <AnswerText text={m.text} citations={m.reply?.citations} />
                ) : (
                  <p>{m.text}</p>
                )}
                {m.reply && <ReplyMeta reply={m.reply} question={m.q} />}
              </div>
            ))}
          </div>
          <div className="chat-input">
            <input
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send(question)}
              placeholder={busy ? "Waiting for the backend…" : "Ask a research question…"}
              disabled={busy}
            />
            <button onClick={() => send(question)} aria-label="Send question" disabled={busy}>
              <Icon name="arrow" size={16} />
            </button>
          </div>
        </Panel>
        <aside className="prompt-rail">
          <span>SUGGESTED QUERIES</span>
          {suggested.slice(0, 6).map((item) => (
            <button key={item} onClick={() => send(item)} disabled={busy}>
              {item}
              <Icon name="arrow" size={12} />
            </button>
          ))}
          <div className="assistant-note">
            <strong>Evidence policy</strong>
            <p>
              Answers separate source facts, derived analysis, and interpretation. Numbers that no
              tool produced are listed as unsupported rather than quietly shown.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

/** Grounding, jejak alat, dan gambar asli paper di bawah satu jawaban. */
type Msg = { role: "user" | "assistant"; text: string; pending?: boolean; failed?: boolean; reply?: AskReply; q?: string };

/** Umpan balik 👍/👎 -> POST /feedback -> kb/gold/cases.jsonl. Jawaban berlabel "baik"
 *  dipakai asisten sebagai contoh pendekatan untuk pertanyaan serupa (similar_cases). */
function FeedbackButtons({ reply, question }: { reply: AskReply; question?: string }) {
  const [sent, setSent] = useState<"up" | "down" | "error" | null>(null);
  if (!question) return null;
  const rate = async (r: "up" | "down") => {
    try {
      await sendFeedback({ question, answer: reply.answer, rating: r === "up" ? "baik" : "buruk", mode: reply.mode, tool_calls: reply.tool_calls });
      setSent(r);
    } catch {
      setSent("error");
    }
  };
  if (sent === "error") return <small className="feedback-note">Feedback is closed on the public deployment.</small>;
  if (sent) return <small className="feedback-note">{sent === "up" ? "Thanks: kept as a good example." : "Thanks: noted as a bad answer."}</small>;
  return (
    <div className="feedback-row">
      <span>WAS THIS ANSWER GOOD?</span>
      <button onClick={() => rate("up")} aria-label="Good answer">👍</button>
      <button onClick={() => rate("down")} aria-label="Bad answer">👎</button>
    </div>
  );
}

function ReplyMeta({ reply, question }: { reply: AskReply; question?: string }) {
  const g = reply.grounding;
  const bad = g?.ungrounded?.length ?? 0;
  return (
    <div className="grounding-report">
      {g && (
        <div>
          <span>NUMERICAL CLAIMS</span>
          <strong className={bad ? "warn" : ""}>
            {g.numbers_checked} checked · {g.numbers_checked - bad} grounded · {bad} unsupported
          </strong>
          {bad > 0 && <small className="warn">Unsupported: {g.ungrounded.join(", ")}</small>}
        </div>
      )}
      {reply.tool_calls?.length > 0 && (
        <div className="tool-trace">
          <span>TOOL TRACE</span>
          <code>{reply.tool_calls.map((t) => t.name).join(" → ")}</code>
        </div>
      )}
      <ReplyMedia reply={reply} />
      <FeedbackButtons reply={reply} question={question} />
      <small>mode: {reply.mode}</small>
    </div>
  );
}

function FloatingAssistant({
  open,
  onToggle,
  onOpenFull,
}: {
  open: boolean;
  onToggle: () => void;
  onOpenFull: () => void;
}) {
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [exchange, setExchange] = useState<{ question: string; answer: string; reply?: AskReply } | null>(null);

  // Panel kecil ini memanggil backend yang SAMA dengan asisten penuh; sebelumnya
  // ia selalu membalas kalimat tetap, sehingga terlihat berfungsi padahal tidak.
  const submit = async () => {
    const q = question.trim();
    if (!q || busy) return;
    setQuestion("");
    setBusy(true);
    setExchange({ question: q, answer: "Calling tools…" });
    try {
      const r = await askApi(q, []);
      const g = r.grounding;
      const flag = g && g.ungrounded.length ? ` [${g.ungrounded.length} number(s) unsupported]` : "";
      setExchange({ question: q, answer: (r.answer || "(empty answer)") + flag, reply: r });
    } catch (e) {
      setExchange({ question: q, answer: "Backend did not answer (" + String(e) + ")." });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={`floating-assistant ${open ? "open" : ""}`}>
      {open && (
        <section className="assistant-popover" aria-label="FLARE+ quick assistant">
          <header>
            <div className="popover-orb" aria-hidden="true">
              <i />
              <i />
            </div>
            <div>
              <strong>Ask FLARE+</strong>
              <small>
                <i /> Tool-grounded preview
              </small>
            </div>
            <button onClick={onToggle} aria-label="Close quick assistant">
              ×
            </button>
          </header>
          <div className="popover-body">
            {!exchange ? (
              <>
                <p>Ask about an investigation, habitat condition, evidence gap, or source.</p>
                <div className="quick-prompts">
                  {[
                    "Best evidence for a lunar base?",
                    "Where is partial-gravity data missing?",
                  ].map((prompt) => (
                    <button key={prompt} onClick={() => setQuestion(prompt)}>
                      {prompt}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <div className="mini-exchange">
                <span>YOU</span>
                <p>{exchange.question}</p>
                <span>FLARE+</span>
                <div className="mini-answer">
                  {busy ? <p className="thinking">{exchange.answer}</p> : <AnswerText text={exchange.answer} citations={exchange.reply?.citations} />}
                  {exchange.reply && <ReplyMedia reply={exchange.reply} compact />}
                </div>
                <small>
                  {exchange.reply
                    ? `mode: ${exchange.reply.mode} · ${exchange.reply.tool_calls.map((t) => t.name).join(" → ") || "no tools"}`
                    : ""}
                </small>
              </div>
            )}
          </div>
          <div className="popover-input">
            <input
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && submit()}
              placeholder="Ask the evidence…"
              aria-label="Quick assistant question"
            />
            <button onClick={submit} aria-label="Send question">
              <Icon name="arrow" size={15} />
            </button>
          </div>
          <button className="open-full-assistant" onClick={onOpenFull}>
            Open full research assistant <Icon name="arrow" size={13} />
          </button>
        </section>
      )}
      <button
        className="assistant-orb-button"
        onClick={onToggle}
        aria-label={open ? "Close FLARE assistant" : "Open FLARE assistant"}
        aria-expanded={open}
      >
        <span className="orb-envelope">
          <i />
          <i />
          <i />
        </span>
        <span className="orb-label">{open ? "CLOSE" : "ASK FLARE+"}</span>
      </button>
    </div>
  );
}

function EvidenceBadge({ tier }: { tier: EvidenceTier }) {
  return <span className={`evidence-badge tier-${tier}`}>{tier.replaceAll("_", " ")}</span>;
}

/** Angka ringkas dari backend. Tidak ada nilai cadangan karangan: bila backend
 *  mati, yang tampil "—" dan catatan, bukan angka contoh. */
function StatStrip({ onEvidence }: { onEvidence: (r: EvidenceRecord) => void }) {
  const { data, error, retry } = useInsight();
  const totals = data?.totals as
    | { key: string; label: string; note: string; value: number | null; tier: EvidenceTier; path: string; caveat?: string }[]
    | undefined;
  if (error) {
    return (
      <div className="stat-strip">
        <p className="stat-error">Backend unavailable — live counts not shown.</p>
      </div>
    );
  }
  if (!totals) {
    return (
      <div className="stat-strip">
        {[0, 1, 2, 3].map((i) => (
          <Stat key={i} value="…" label="Loading" note="reading knowledge base" tier="nasa_table" />
        ))}
      </div>
    );
  }
  return (
    <div className="stat-strip">
      {totals.map((t) => (
        <Stat
          key={t.key}
          value={fmt(t.value)}
          label={t.label}
          note={t.note}
          tier={t.tier}
          onInspect={() =>
            onEvidence({
              label: t.label,
              value: fmt(t.value),
              tier: t.tier,
              source: "NASA Physical Sciences Informatics / derived",
              path: t.path,
              note: t.caveat || "Counted directly from the knowledge base at page load.",
            })
          }
        />
      ))}
    </div>
  );
}

function Stat({
  value,
  label,
  note,
  tier,
  onInspect,
}: {
  value: string;
  label: string;
  note: string;
  tier?: EvidenceTier;
  onInspect?: () => void;
}) {
  return (
    <button className="stat" onClick={onInspect} disabled={!onInspect}>
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{note}</small>
      {tier && <EvidenceBadge tier={tier} />}
    </button>
  );
}
const PILLAR_ORDER = ["prevention", "detection", "suppression", "fundamentals"];

/** Jumlah investigasi per pilar dari /insight_data (bukan angka mockup 9/7/8). */
function PillarDistribution() {
  const { data, error, retry } = useInsight();
  if (error) return <p className="chart-note">Backend unavailable — distribution not shown.</p>;
  if (!data) return <p className="chart-note">Loading…</p>;
  const inv = data.investigations || [];
  const counts: Record<string, number> = {};
  for (const i of inv) for (const p of i.pillars || []) counts[p] = (counts[p] || 0) + 1;
  const keys = [...PILLAR_ORDER.filter((k) => k in counts), ...Object.keys(counts).filter((k) => !PILLAR_ORDER.includes(k))];
  const tagged = Object.values(counts).reduce((a, b) => a + b, 0);
  return (
    <>
      <div className="distribution-summary">
        <div className="distribution-total">
          <span>Indexed investigations</span>
          <strong>{inv.length}</strong>
          <small
            title="Fundamentals = flame physics that fire-safety models are validated against."
          >
            {tagged > inv.length
              ? `by fire-safety pillar · ${tagged} tags, some investigations have two`
              : "by fire-safety pillar"}
          </small>
        </div>
        <div className="distribution-rows">
          {keys.map((k) => (
            <DistributionRow
              key={k}
              label={k[0].toUpperCase() + k.slice(1)}
              value={counts[k]}
              total={inv.length}
            />
          ))}
        </div>
      </div>
    </>
  );
}

/** Jumlah paper per tahun terbit di peta riset (metadata paper, bukan kurva hias). */
function PaperTimeline() {
  const { map, error } = useResearchMap();
  if (error) return <p className="chart-note">Research map unavailable ({error}).</p>;
  if (!map) return <p className="chart-note">Loading…</p>;
  const papers = (map.nodes || []).filter((n: any) => n.kind === "paper");
  const byYear = new Map<number, number>();
  let undated = 0;
  for (const p of papers) {
    const y = parseInt(p.year, 10);
    if (Number.isFinite(y) && y > 1900) byYear.set(y, (byYear.get(y) || 0) + 1);
    else undated++;
  }
  if (!byYear.size) return <p className="chart-note">No dated papers in the research map.</p>;
  const years = [...byYear.keys()];
  const y0 = Math.min(...years);
  const y1 = Math.max(...years);
  const span = y1 - y0 + 1;
  const peak = Math.max(...byYear.values());
  const W = 600;
  const H = 180;
  const bw = W / span;
  const ticks = [y0, ...[1990, 2000, 2010, 2020].filter((t) => t > y0 + 2 && t < y1 - 2), y1];
  return (
    <>
      <div className="line-chart">
        <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
          aria-label={`Papers per year, ${y0} to ${y1}, peak ${peak}`}>
          <path className="chart-grid" d={`M0 ${H * 0.25}H${W}M0 ${H * 0.5}H${W}M0 ${H * 0.75}H${W}`} />
          {[...byYear.entries()].map(([y, n]) => {
            const h = (n / peak) * (H - 12);
            return (
              <rect key={y} className="chart-bar" x={(y - y0) * bw + bw * 0.12} y={H - h}
                width={bw * 0.76} height={h}>
                <title>{`${y}: ${n} paper${n === 1 ? "" : "s"}`}</title>
              </rect>
            );
          })}
        </svg>
        <div className="chart-years chart-years--placed">
          {ticks.map((t) => (
            <span key={t} style={{ left: `${(((t - y0) + 0.5) / span) * 100}%` }}>
              {t}
            </span>
          ))}
        </div>
      </div>
      <p className="chart-note">
        {papers.length} papers linked to the 24 investigations; peak {peak} per year
        {undated ? `; ${undated} without a year are not plotted` : ""}. The last year may be
        incomplete.
      </p>
    </>
  );
}

/** Topik NTRS dengan jumlah paper yang tertaut, dari peta riset. */
function TopicLedger() {
  const { map, error } = useResearchMap();
  if (error) return <p className="chart-note">Research map unavailable ({error}).</p>;
  if (!map) return <p className="chart-note">Loading…</p>;
  const nodes: any[] = map.nodes || [];
  // Topik di peta hanya tertaut ke paper (tag NTRS), bukan langsung ke investigasi.
  const rows = nodes
    .map((n, i) => ({ n, i }))
    .filter(({ n }) => n.kind === "topic")
    .map(({ n, i }) => {
      const papers = new Set<number>();
      for (const e of map.edges || []) {
        const o = e.s === i ? e.t : e.t === i ? e.s : -1;
        if (o >= 0 && nodes[o]?.kind === "paper") papers.add(o);
      }
      const full = [...papers].filter((o) => nodes[o].full_text).length;
      return { label: n.label, papers: papers.size, full };
    })
    .sort((a, b) => b.papers - a.papers)
    .slice(0, 5);
  return (
    <div className="topic-ledger">
      <div className="topic-head">
        <span>Theme</span>
        <span>Papers</span>
        <span>Full text indexed</span>
      </div>
      {rows.map((r) => (
        <TopicRow key={r.label} label={r.label} count={fmt(r.papers)} layer={`${r.full} of ${r.papers} searchable`} />
      ))}
      <p className="chart-note">Top {rows.length} of the NTRS topic tags in the research map, by tagged papers.</p>
    </div>
  );
}

function DistributionRow({ label, value, total }: { label: string; value: number; total: number }) {
  return (
    <div className="distribution-row">
      <span>{label}</span>
      <i>
        <em style={{ width: `${(value / total) * 100}%` }} />
      </i>
      <strong>{String(value).padStart(2, "0")}</strong>
    </div>
  );
}

function TopicRow({ label, count, layer }: { label: string; count: string; layer: string }) {
  return (
    <div className="topic-row">
      <strong>{label}</strong>
      <span>{count}</span>
      <small>{layer}</small>
    </div>
  );
}
function Watch({ number, title, text }: { number: string; title: string; text: string }) {
  return (
    <div className="watch">
      <span>{number}</span>
      <div>
        <strong>{title}</strong>
        <p>{text}</p>
      </div>
    </div>
  );
}
function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}
function Range({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (value: number) => void;
}) {
  const setBoundedValue = (next: number) => {
    if (Number.isNaN(next)) return;
    const bounded = Math.min(max, Math.max(min, next));
    const decimals = String(step).includes(".") ? String(step).split(".")[1].length : 0;
    onChange(Number((Math.round(bounded / step) * step).toFixed(decimals)));
  };

  return (
    <label className="range-field">
      <span>{label}</span>
      <div className="number-control">
        <button
          type="button"
          onClick={() => setBoundedValue(value - step)}
          aria-label={`Decrease ${label}`}
        >
          −
        </button>
        <div>
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(event) => setBoundedValue(Number(event.target.value))}
            aria-label={`${label} value`}
          />
          <span>{suffix.trim()}</span>
        </div>
        <button
          type="button"
          onClick={() => setBoundedValue(value + step)}
          aria-label={`Increase ${label}`}
        >
          +
        </button>
      </div>
      <input
        className="parameter-slider"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      <small className="range-limits">
        <span>
          {min}
          {suffix}
        </span>
        <span>
          {max}
          {suffix}
        </span>
      </small>
    </label>
  );
}

function HabitatAsset({ type }: { type: string }) {
  const className = type.toLowerCase().replaceAll(" ", "-");
  return (
    <span className={`habitat-asset ${className}`} aria-hidden="true">
      <i />
      <i />
      <i />
    </span>
  );
}

function MaterialSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const materials = [
    { name: "Any material", className: "mixed" },
    { name: "Solid polymer", className: "polymer" },
    { name: "Fabric / textile", className: "fabric" },
    { name: "Liquid fuel", className: "liquid" },
    { name: "Smoke / aerosol", className: "smoke" },
  ];
  return (
    <div className="material-selector">
      {materials.map((material) => (
        <button
          type="button"
          key={material.name}
          className={value === material.name ? "active" : ""}
          onClick={() => onChange(material.name)}
        >
          <span className={`material-asset ${material.className}`} aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>{material.name}</span>
        </button>
      ))}
    </div>
  );
}

function GravitySelector({
  gravity,
  gravityG,
  onChange,
}: {
  gravity: string;
  gravityG: number;
  onChange: (name: string, value: number) => void;
}) {
  const bodies = [
    { name: "Microgravity", value: 0, className: "zero-g" },
    { name: "Moon", value: 0.166, className: "moon" },
    { name: "Mars", value: 0.378, className: "mars" },
    { name: "Earth", value: 1, className: "earth" },
  ];
  return (
    <div className="gravity-selector">
      <div className="gravity-bodies">
        {bodies.map((body) => (
          <button
            type="button"
            key={body.name}
            className={gravity === body.name ? "active" : ""}
            onClick={() => onChange(body.name, body.value)}
          >
            <span className={`celestial-body ${body.className}`}>
              <i />
              <i />
              {body.className === "zero-g" && <i />}
            </span>
            <strong>{body.name}</strong>
            <small>{body.value.toFixed(body.value === 0 ? 2 : 3)} g</small>
          </button>
        ))}
      </div>
      <div className="gravity-current">
        <span>Current field</span>
        <strong>{gravity === "Custom" ? "Custom gravity" : gravity}</strong>
        <b>{gravityG.toFixed(3)} g</b>
      </div>
    </div>
  );
}

function AtmosphereModel({
  oxygen,
  pressure,
  velocity,
  gravity,
  gravityG,
}: {
  oxygen: number;
  pressure: number;
  velocity: number;
  gravity: string;
  gravityG: number;
}) {
  const oxygenScale = Math.min(1, Math.max(0.2, oxygen / 40));
  const pressureScale = Math.min(1, Math.max(0.3, pressure / 15));
  const normalizedGravity = Math.min(1, gravityG);
  const gravityX = 1 - normalizedGravity * 0.2;
  const gravityY = 1 + normalizedGravity * 0.42;
  const flameBase = 0.82 + oxygenScale * 0.22;
  return (
    <div
      className="atmosphere-model"
      style={
        {
          "--oxygen-scale": oxygenScale,
          "--pressure-scale": pressureScale,
          "--flow-angle": `${Math.min(24, velocity) * 2.4}deg`,
          "--gravity-x": gravityX,
          "--gravity-y": gravityY,
          "--flame-x": flameBase * gravityX,
          "--flame-y": flameBase * gravityY,
        } as React.CSSProperties
      }
    >
      <div className="model-heading">
        <span>Atmosphere preview</span>
        <small>3D PARAMETER VIEW · NOT MODEL OUTPUT</small>
      </div>
      <div className="model-stage">
        <div className="model-grid" />
        <div className="model-orbit orbit-x">
          <i />
        </div>
        <div className="model-orbit orbit-y">
          <i />
        </div>
        <div className="model-orbit orbit-z">
          <i />
        </div>
        <div className="model-flame">
          <span className="flame-shell" />
          <span className="flame-core" />
        </div>
        <div className="flow-vector">
          <i />
          <span>FLOW</span>
        </div>
      </div>
      <div className="model-readout">
        <span>
          <b>{oxygen}%</b> O₂
        </span>
        <span>
          <b>{pressure}</b> psi
        </span>
        <span>
          <b>{velocity}</b> cm/s
        </span>
        <span>
          <b>{gravityG.toFixed(3)} g</b> {gravity}
        </span>
      </div>
    </div>
  );
}
function Compat({ label, value, score }: { label: string; value: string; score: number }) {
  return (
    <div className="compat">
      <span>{label}</span>
      <strong>{value}</strong>
      <i>
        <em style={{ width: `${score}%` }} />
      </i>
    </div>
  );
}

function ScoreLine({
  label,
  weight,
  score,
  contribution,
}: {
  label: string;
  weight: string;
  score: string;
  contribution: string;
}) {
  return (
    <div className="score-line">
      <span>{label}</span>
      <small>
        {weight} × {score}
      </small>
      <strong>{contribution}</strong>
    </div>
  );
}

function ProvenanceDrawer({ record, onClose }: { record: EvidenceRecord; onClose: () => void }) {
  return (
    <div className="drawer-scrim" onClick={onClose}>
      <aside className="provenance-drawer" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span>EVIDENCE PROVENANCE</span>
            <strong>{record.label}</strong>
          </div>
          <button onClick={onClose} aria-label="Close provenance drawer">
            ×
          </button>
        </header>
        <div className="provenance-value">
          <strong>{record.value}</strong>
          <EvidenceBadge tier={record.tier} />
        </div>
        <dl>
          <div>
            <dt>Source</dt>
            <dd>{record.source}</dd>
          </div>
          <div>
            <dt>Trace</dt>
            <dd>{record.path}</dd>
          </div>
          <div>
            <dt>Interpretation</dt>
            <dd>{record.note}</dd>
          </div>
        </dl>
        <div className="provenance-chain">
          <span>01 · SOURCE</span>
          <i />
          <span>02 · TRANSFORM</span>
          <i />
          <span>03 · DISPLAY</span>
        </div>
        <p>
          Frontend prototype. Connect this drawer to the backend provenance record and source URL
          during integration.
        </p>
      </aside>
    </div>
  );
}

function DemoPanel({
  onClose,
  onNavigate,
}: {
  onClose: () => void;
  onNavigate: (view: View) => void;
}) {
  const steps: { id: View; number: string; title: string; copy: string }[] = [
    {
      id: "Scenario",
      number: "01",
      title: "Set Lunar Base",
      copy: "30% O₂ · 10.2 psi · Moon gravity target",
    },
    {
      id: "Scenario",
      number: "02",
      title: "Inspect ranking",
      copy: "Score decomposition and rank stability",
    },
    {
      id: "Assistant",
      number: "03",
      title: "Ask the evidence",
      copy: "Tool trace and grounded numerical claims",
    },
    {
      id: "Map",
      number: "04",
      title: "Trace the source",
      copy: "Paper relations, figures, and provenance",
    },
  ];
  return (
    <div className="demo-scrim" onClick={onClose}>
      <section className="demo-panel" onClick={(event) => event.stopPropagation()}>
        <header>
          <span>3-MINUTE JURY WALKTHROUGH</span>
          <button onClick={onClose}>×</button>
        </header>
        <h2>
          Show the evidence,
          <br />
          not just the answer.
        </h2>
        <p>Use this guided path to demonstrate why FLARE+ is trustworthy.</p>
        <div className="demo-steps">
          {steps.map((step) => (
            <button key={`${step.number}-${step.title}`} onClick={() => onNavigate(step.id)}>
              <span>{step.number}</span>
              <div>
                <strong>{step.title}</strong>
                <small>{step.copy}</small>
              </div>
              <Icon name="arrow" size={14} />
            </button>
          ))}
        </div>
        <div className="demo-disclaimer">
          Independent project · Public NASA PSI/NTRS data · Not an official NASA product
        </div>
      </section>
    </div>
  );
}
function Gauge({ value, label }: { value: number; label: string }) {
  return (
    <div className="gauge">
      <div style={{ "--gauge": `${value * 3.6}deg` } as React.CSSProperties}>
        <span>{value}%</span>
      </div>
      <p>{label}</p>
    </div>
  );
}
/** Bilah status dari backend sungguhan; sebelumnya "NOMINAL" dan "7,924 CHUNKS" ditulis keras. */
function Footer() {
  const { data, error, retry } = useInsight();
  const st = useStatus();
  const backend = error ? "OFFLINE" : data ? "ONLINE" : "CHECKING…";
  const chunks = data?.corpus?.chunks;
  const built = data?.built ? String(data.built).slice(0, 10) : "—";
  // hanya penyedia di bilah (nama model panjang membuat bilah meluap); nama model di tooltip
  const assistant = !st ? "—" : st.llm ? st.provider : "OFFLINE PLANNER";
  const assistantTitle = st?.llm && st.model ? `${st.provider} · ${st.model}` : undefined;
  return (
    <footer className="statusbar">
      <span>
        <i className={error ? "is-offline" : undefined} /> BACKEND <b>{backend}</b>
        {error && (
          <button className="statusbar-retry" onClick={retry}>
            RETRY
          </button>
        )}
      </span>
      <span>
        KB BUILT <b>{built}</b>
      </span>
      <span>
        SEARCH INDEX <b>{chunks != null ? `${fmt(chunks)} CHUNKS` : "—"}</b>
      </span>
      <span title={assistantTitle}>
        ASSISTANT <b>{assistant.toUpperCase()}</b>
      </span>
      <em className="visual-credit">DESERT ANALOG · RYAN GREWELL / UNSPLASH</em>
      <em>FLARE+ · UI 1.0</em>
    </footer>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
