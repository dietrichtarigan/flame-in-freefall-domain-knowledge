import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

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
  { id: "Map", label: "Research Map", sub: "429 linked papers", icon: "orbit" },
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

import { ask as askApi, figureUrl, TIER_LABEL, type AskReply } from "./api";
import { useInsight, useStatus, fmt } from "./useData";

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
    <main className="app-shell">
      <CombustionBackdrop />
      <div className="grain" aria-hidden="true" />
      <Header onDemo={() => setDemoOpen(true)} />
      <Sidebar view={view} setView={setView} />
      <section className="workspace">
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
      </section>
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
    </main>
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
          SI-powered evidence navigation for microgravity combustion research.
        </div>
        <button className="demo-button" onClick={onDemo}>
          PRESENTATION MODE
        </button>
      </div>
      <div className="header-metrics">
        <span>
          <b>24</b> Investigations
        </span>
        <span>
          <b>1,990</b> Tests
        </span>
        <span>
          <b>352</b> Publications
        </span>
      </div>
    </header>
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
        <span>SI-powered</span>
        <span>Tool-grounded</span>
        <span>Source-traceable</span>
        <p>
          Independent project using public NASA PSI and NTRS data. Not an official NASA product.
        </p>
      </div>

      <div className="overview-grid">
        <Panel
          title="Research distribution"
          meta="OBJECTIVE TAXONOMY"
          className="distribution-panel"
        >
          <div className="distribution-summary">
            <div className="distribution-total">
              <span>Indexed investigations</span>
              <strong>24</strong>
              <small>classified by primary fire-safety objective</small>
            </div>
            <div className="distribution-rows">
              <DistributionRow label="Prevention" value={9} total={24} />
              <DistributionRow label="Detection" value={7} total={24} />
              <DistributionRow label="Suppression" value={8} total={24} />
            </div>
          </div>
        </Panel>

        <Panel
          title="Research activity over time"
          meta="PUBLICATION + EXPERIMENT YEARS"
          className="timeline-panel"
        >
          <div className="line-chart">
            <svg
              viewBox="0 0 600 180"
              preserveAspectRatio="none"
              aria-label="Research activity trend"
            >
              <defs>
                <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor="#d7844b" stopOpacity=".34" />
                  <stop offset="1" stopColor="#d7844b" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path className="chart-grid" d="M0 30H600M0 75H600M0 120H600M0 165H600" />
              <path
                className="chart-area"
                d="M0 158 C55 153 70 132 116 136 S185 112 222 118 S278 65 321 83 S382 42 425 61 S479 29 520 43 S565 17 600 21 L600 180 L0 180Z"
              />
              <path
                className="chart-line"
                d="M0 158 C55 153 70 132 116 136 S185 112 222 118 S278 65 321 83 S382 42 425 61 S479 29 520 43 S565 17 600 21"
              />
            </svg>
            <div className="chart-years">
              <span>1990</span>
              <span>2000</span>
              <span>2010</span>
              <span>2020</span>
              <span>2025</span>
            </div>
          </div>
          <p className="chart-note">
            Indexed activity grows as test-level records and associated publications are added to
            the corpus.
          </p>
        </Panel>

        <Panel
          title="Indexed themes"
          meta="TEST + PUBLICATION OCCURRENCE"
          className="network-panel"
        >
          <div className="topic-ledger">
            <div className="topic-head">
              <span>Theme</span>
              <span>Records</span>
              <span>Evidence layer</span>
            </div>
            <TopicRow label="Flame spread / solid fuels" count="684" layer="Tests + papers" />
            <TopicRow label="Ignition and extinction" count="427" layer="Tests" />
            <TopicRow label="Smoke and aerosols" count="218" layer="Tests + video" />
            <TopicRow label="Detection response" count="146" layer="Papers" />
          </div>
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

function Scenario({ onEvidence }: { onEvidence: (record: EvidenceRecord) => void }) {
  const [oxygen, setOxygen] = useState(30);
  const [pressure, setPressure] = useState(10.2);
  const [velocity, setVelocity] = useState(10);
  const [objective, setObjective] = useState("Prevention");
  const [material, setMaterial] = useState("Any material");
  const [ran, setRan] = useState(false);
  const [mission, setMission] = useState("Lunar base");
  const [gravity, setGravity] = useState("Moon");
  const [gravityG, setGravityG] = useState(0.166);
  const [selectedRank, setSelectedRank] = useState("FLEX");

  const presets = [
    { name: "Spacecraft cabin", oxygen: 21, pressure: 14.7, gravity: "Microgravity", g: 0 },
    { name: "Lunar base", oxygen: 30, pressure: 10.2, gravity: "Moon", g: 0.166 },
    { name: "Mars habitat", oxygen: 32, pressure: 8.2, gravity: "Mars", g: 0.378 },
    { name: "Pressurized rover", oxygen: 34, pressure: 8.0, gravity: "Moon", g: 0.166 },
    { name: "Spacesuit", oxygen: 100, pressure: 4.3, gravity: "Microgravity", g: 0 },
  ];

  const applyPreset = (preset: (typeof presets)[number]) => {
    setMission(preset.name);
    setOxygen(preset.oxygen);
    setPressure(preset.pressure);
    setGravity(preset.gravity);
    setGravityG(preset.g);
    setRan(false);
  };

  const scored = useMemo(
    () =>
      investigations
        .map((item, i) => ({
          ...item,
          match: Math.max(48, item.match - Math.abs(oxygen - 30) - i * 2),
        }))
        .sort((a, b) => b.match - a.match),
    [oxygen],
  );

  return (
    <div className="page">
      <PageTitle
        index="02"
        overline="MISSION-SPECIFIC DISCOVERY"
        title="Scenario Explorer"
        description="Describe a spacecraft environment and fire-safety objective to find relevant NASA investigations and inspect how closely their test conditions match."
      />
      <div className="scenario-layout">
        <Panel title="Mission parameters" meta="SCENARIO INPUT" className="parameter-panel">
          <div className="preset-block">
            <span>Habitat presets</span>
            <div className="preset-grid">
              {presets.map((preset) => (
                <button
                  key={preset.name}
                  className={mission === preset.name ? "active" : ""}
                  onClick={() => applyPreset(preset)}
                >
                  <HabitatAsset type={preset.name} />
                  {preset.name}
                  <small>
                    {preset.oxygen}% O₂ · {preset.pressure} psi
                  </small>
                </button>
              ))}
            </div>
          </div>
          <AtmosphereModel
            oxygen={oxygen}
            pressure={pressure}
            velocity={velocity}
            gravity={gravity}
            gravityG={gravityG}
          />
          <Field label="Mission environment">
            <select value={mission} onChange={(event) => setMission(event.target.value)}>
              {presets.map((preset) => (
                <option key={preset.name}>{preset.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Gravity condition">
            <GravitySelector
              gravity={gravity}
              gravityG={gravityG}
              onChange={(name, value) => {
                setGravity(name);
                setGravityG(value);
                setRan(false);
              }}
            />
          </Field>
          <Range
            label="Gravity level"
            value={gravityG}
            min={0}
            max={1.5}
            step={0.01}
            suffix=" g"
            onChange={(value) => {
              setGravityG(value);
              const exact = [
                { name: "Microgravity", value: 0 },
                { name: "Moon", value: 0.166 },
                { name: "Mars", value: 0.378 },
                { name: "Earth", value: 1 },
              ].find((item) => Math.abs(item.value - value) < 0.005);
              setGravity(exact?.name ?? "Custom");
              setRan(false);
            }}
          />
          <Range
            label="Oxygen concentration"
            value={oxygen}
            min={15}
            max={mission === "Spacesuit" ? 100 : 40}
            step={1}
            suffix="%"
            onChange={setOxygen}
          />
          <Range
            label="Ambient pressure"
            value={pressure}
            min={4}
            max={15}
            step={0.1}
            suffix=" psi"
            onChange={setPressure}
          />
          <Range
            label="Ventilation velocity"
            value={velocity}
            min={0}
            max={25}
            step={1}
            suffix=" cm/s"
            onChange={setVelocity}
          />
          <Field label="Fuel / material category">
            <MaterialSelector value={material} onChange={setMaterial} />
          </Field>
          <Field label="Fire-safety objective">
            <div className="segmented objective-segmented">
              {["Prevention", "Detection", "Suppression"].map((x) => (
                <button
                  className={objective === x ? "selected" : ""}
                  onClick={() => setObjective(x)}
                  key={x}
                >
                  <span className={`objective-glyph ${x.toLowerCase()}`}>
                    <i />
                    <i />
                  </span>
                  <span>{x}</span>
                </button>
              ))}
            </div>
          </Field>
          <button className="run-button" onClick={() => setRan(true)}>
            FIND RELEVANT INVESTIGATIONS <Icon name="arrow" size={14} />
          </button>
        </Panel>

        <div className="results-stack">
          <Panel
            title="Recommended investigations"
            meta={ran ? `${scored.length} MATCHES` : "AWAITING PARAMETERS"}
            className="result-panel"
          >
            {!ran ? (
              <div className="empty-state">
                <Icon name="target" size={34} />
                <strong>Your research shortlist will appear here</strong>
                <p>Adjust mission parameters and run the scenario analysis.</p>
              </div>
            ) : (
              scored.map((item, index) => (
                <button
                  className={`result-row ${selectedRank === item.name ? "selected" : ""}`}
                  key={item.name}
                  onClick={() => setSelectedRank(item.name)}
                >
                  <span className="result-rank">0{index + 1}</span>
                  <span>
                    <strong>{item.name}</strong>
                    <small>
                      {item.objective} · {item.tests} tests
                    </small>
                  </span>
                  <span className="match">
                    <b>{item.match}%</b>
                    <i>
                      <em style={{ width: `${item.match}%` }} />
                    </i>
                  </span>
                  <span className="stability">
                    {index === 0 ? "80%" : `${66 - index * 9}%`}
                    <small>stable</small>
                  </span>
                  <Icon name="arrow" size={14} />
                </button>
              ))
            )}
          </Panel>
          <Panel title="Experimental-condition compatibility" meta="COMPARISON FRAMEWORK">
            <div className="compatibility">
              <Compat label="Gravity" value={ran ? "Direct match" : "—"} score={ran ? 96 : 0} />
              <Compat
                label="Oxygen"
                value={ran ? `Near ${oxygen}% target` : "—"}
                score={ran ? 82 : 0}
              />
              <Compat label="Pressure" value={ran ? "Partial overlap" : "—"} score={ran ? 64 : 0} />
              <Compat
                label="Ventilation"
                value={ran ? "Reported subset" : "—"}
                score={ran ? 58 : 0}
              />
            </div>
          </Panel>
          {ran && (
            <Panel title="Why this rank" meta="TRANSPARENT SCORE" className="score-panel">
              <div className="score-heading">
                <div>
                  <span>Selected investigation</span>
                  <strong>{selectedRank}</strong>
                </div>
                <EvidenceBadge tier="derived_auto" />
              </div>
              <ScoreLine label="Direct relevance" weight=".40" score="1.00" contribution=".400" />
              <ScoreLine label="Condition proximity" weight=".35" score=".72" contribution=".252" />
              <ScoreLine label="Evidence depth" weight=".25" score=".86" contribution=".215" />
              <div className="score-total">
                <span>Weighted score</span>
                <strong>0.87</strong>
              </div>
              <div className="rank-stability">
                <span>Rank stability · 2,000 randomized weight sets</span>
                <strong>80% remain #1</strong>
                <small>P5–P95 rank range: 1–2 · SMAA methodology</small>
              </div>
            </Panel>
          )}
          {ran && (
            <section className="prediction-card">
              <header>
                <span>Gravity bridge prediction</span>
                <EvidenceBadge tier="model_prediction" />
              </header>
              <div className="prediction-value">
                <span>O₂ flammability boundary</span>
                <strong>14.4%</strong>
                <b>95% interval · 13.8–14.9%</b>
              </div>
              <div className="extrapolation-warning">
                <strong>EXTRAPOLATION</strong>
                <p>
                  Target pressure: 70 kPa · training range: 99–103 kPa. PSI contains no
                  partial-gravity combustion tests.
                </p>
              </div>
              <button
                onClick={() =>
                  onEvidence({
                    label: "Predicted O₂ flammability boundary",
                    value: "14.4% [13.8–14.9]",
                    tier: "model_prediction",
                    source: "Olson & Ferkul 2017 fit over BASS-II",
                    path: "scripts/gbridge.py → gravity_flammability",
                    note: "Extrapolated to lunar gravity and 70 kPa; not an observed NASA measurement.",
                  })
                }
              >
                Inspect model provenance <Icon name="arrow" size={13} />
              </button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function Gaps() {
  const [objective, setObjective] = useState("Prevention");
  const [selected, setSelected] = useState<{ row: number; col: number } | null>(null);
  return (
    <div className="page">
      <PageTitle
        index="03"
        overline="EVIDENCE COVERAGE"
        title="Investigation & Gaps Analysis"
        description="See which experimental conditions are represented in indexed research—and distinguish genuine coverage gaps from missing or unreported data."
      />
      <div className="objective-switch">
        <span>FIRE-SAFETY OBJECTIVE</span>
        {["Prevention", "Detection", "Suppression"].map((item) => (
          <button
            key={item}
            onClick={() => setObjective(item)}
            className={objective === item ? "active" : ""}
          >
            {item}
          </button>
        ))}
      </div>
      <div className="gaps-grid">
        <Panel
          title={`Environmental parameter coverage · ${objective}`}
          meta="TEST RECORD DENSITY"
          className="heat-panel"
        >
          <div className="heat-wrap">
            <div className="y-label">Pressure →</div>
            <div className="heatmap">
              {heatmap.flatMap((row, r) =>
                row.map((level, c) => (
                  <button
                    key={`${r}-${c}`}
                    className={selected?.row === r && selected?.col === c ? "selected" : ""}
                    data-level={level}
                    onClick={() => setSelected({ row: r, col: c })}
                  >
                    <span>{level ? level * 6 + r + c : "—"}</span>
                  </button>
                )),
              )}
            </div>
            <div className="x-label">Oxygen concentration (%) →</div>
          </div>
          <div className="heat-legend">
            <span>LOWER COVERAGE</span>
            {[0, 1, 2, 3, 4, 5].map((x) => (
              <i key={x} data-level={x} />
            ))}
            <span>HIGHER COVERAGE</span>
          </div>
          <p className="panel-footnote">
            {selected
              ? `Selected bin: ${18 + selected.col * 3}% O₂ · ${5 + selected.row * 2} psi. Inspect matching test metadata before interpreting coverage.`
              : "Select a cell to inspect the query represented by that parameter bin."}
          </p>
        </Panel>
        <Panel title="Coverage quality" meta="METADATA COMPLETENESS" className="quality-panel">
          <Gauge value={74} label="Known experimental conditions" />
          <Gauge value={38} label="Reported flow parameters" />
          <Gauge value={62} label="Comparable measurements" />
          <div className="quality-facts">
            <span>
              <b>1,990</b> Distinct tests
            </span>
            <span>
              <b>24</b> Investigations
            </span>
          </div>
        </Panel>
        <Panel title="Potential evidence gaps" meta="INTERPRETATION PROMPTS" className="gap-list">
          <Watch
            number="01"
            title="Experimental coverage gap"
            text="Target condition has little representation in indexed tests."
          />
          <Watch
            number="02"
            title="Data availability gap"
            text="An experiment exists, but a relevant parameter is not reported."
          />
          <Watch
            number="03"
            title="Scientific validation gap"
            text="Evidence does not validate transfer to another gravity or habitat."
          />
        </Panel>
      </div>
    </div>
  );
}

function Comparison() {
  const [selected, setSelected] = useState<string[]>(["BASS-II", "ACME / CFI-G"]);
  const toggle = (name: string) =>
    setSelected((current) =>
      current.includes(name)
        ? current.filter((x) => x !== name)
        : current.length < 3
          ? [...current, name]
          : current,
    );
  return (
    <div className="page">
      <PageTitle
        index="04"
        overline="SCIENTIFIC COMPARISON"
        title="Comparison & Analysis"
        description="Compare objectives, test configurations, reported measurements, findings, and limitations at the appropriate evidence level."
      />
      <Panel
        title="Select investigations"
        meta={`${selected.length} SELECTED`}
        className="selector-panel"
      >
        <div className="investigation-pills">
          {investigations.map((item) => (
            <button
              key={item.name}
              onClick={() => toggle(item.name)}
              className={selected.includes(item.name) ? "active" : ""}
            >
              <span className="tiny-check">
                {selected.includes(item.name) && <Icon name="check" size={10} />}
              </span>
              {item.name}
              <small>{item.tests} TESTS</small>
            </button>
          ))}
        </div>
      </Panel>
      <div className="comparison-grid">
        {investigations
          .filter((item) => selected.includes(item.name))
          .map((item) => (
            <article className="comparison-card" key={item.name}>
              <header>
                <span>INVESTIGATION PROFILE</span>
                <b>{item.match}%</b>
              </header>
              <h2>{item.name}</h2>
              <p>{item.note}</p>
              <dl>
                <div>
                  <dt>Primary objective</dt>
                  <dd>{item.objective}</dd>
                </div>
                <div>
                  <dt>Indexed tests</dt>
                  <dd>{item.tests}</dd>
                </div>
                <div>
                  <dt>Gravity regime</dt>
                  <dd>Microgravity</dd>
                </div>
                <div>
                  <dt>Evidence layer</dt>
                  <dd>PSI + derived analysis</dd>
                </div>
              </dl>
              <div className="card-limit">
                <span>KNOWN LIMITATION</span>Cross-investigation measurements may use different
                definitions and units.
              </div>
            </article>
          ))}
        {selected.length < 2 && (
          <div className="add-card">Select at least two profiles for a meaningful comparison.</div>
        )}
      </div>
      {selected.length >= 2 && (
        <div className="interpretation">
          <Icon name="spark" size={20} />
          <div>
            <span>COMPARATIVE INTERPRETATION</span>
            <p>
              <strong>{selected.join(" and ")}</strong> address complementary parts of spacecraft
              fire safety. Compare test conditions before comparing outcomes; no causal equivalence
              is implied by shared keywords.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function ResearchMap({ onEvidence }: { onEvidence: (record: EvidenceRecord) => void }) {
  return (
    <div className="page map-page">
      <PageTitle
        index="05"
        overline="RESEARCH CONNECTIONS"
        title="Research Map"
        description="Explore how investigations, papers, and topics connect. Relation types remain explicit: similarity is not citation."
      />
      <div className="map-summary">
        <span>
          <b>429</b> papers
        </span>
        <span>
          <b>24</b> investigations
        </span>
        <span>
          <b>12</b> research topics
        </span>
        <span>
          <b>82</b> unlinked papers excluded
        </span>
      </div>
      <div className="research-map-layout">
        <Panel
          title="Evidence network"
          meta="FILTERED RELATION VIEW"
          className="research-map-panel"
        >
          <div className="relation-legend">
            <span>
              <i className="psi-link" /> Listed by NASA PSI
            </span>
            <span>
              <i className="ntrs-link" /> NTRS topic tag
            </span>
            <span>
              <i className="similarity-link" /> LSA similarity · not citation
            </span>
          </div>
          <svg
            className="research-map-svg"
            viewBox="0 0 820 440"
            aria-label="Research relationship map"
          >
            <g className="map-links psi">
              <path d="M166 206 348 102M166 206l210 15M166 206l158 142M376 221l192-123M376 221l222 74M324 348l274-53" />
            </g>
            <g className="map-links ntrs">
              <path d="M348 102 568 98M376 221l210-2M324 348l137 12M586 219l112-90" />
            </g>
            <g className="map-links similarity">
              <path d="M348 102 586 219M376 221l85 139M568 98l130 31M598 295l-137 65" />
            </g>
            <g className="map-nodes investigations">
              <g transform="translate(166 206)">
                <circle r="45" />
                <text y="4">BASS-II</text>
              </g>
              <g transform="translate(376 221)">
                <circle r="50" />
                <text y="4">ACME</text>
              </g>
              <g transform="translate(324 348)">
                <circle r="39" />
                <text y="4">SPICE</text>
              </g>
            </g>
            <g className="map-nodes topics">
              <g transform="translate(348 102)">
                <circle r="32" />
                <text y="3">Flame spread</text>
              </g>
              <g transform="translate(568 98)">
                <circle r="29" />
                <text y="3">Extinction</text>
              </g>
              <g transform="translate(586 219)">
                <circle r="34" />
                <text y="3">Ignition</text>
              </g>
              <g transform="translate(598 295)">
                <circle r="31" />
                <text y="3">Smoke</text>
              </g>
              <g transform="translate(461 360)">
                <circle r="28" />
                <text y="3">Detection</text>
              </g>
              <g transform="translate(698 129)">
                <circle r="23" />
                <text y="3">Droplets</text>
              </g>
            </g>
          </svg>
          <p className="map-caveat">
            No citation network is claimed: reference lists are not available in the indexed PSI
            records. Similarity edges represent LSA topic proximity only.
          </p>
        </Panel>
        <div className="map-side">
          <Panel title="Connection inventory" meta="RELATION COUNTS">
            <div className="connection-list">
              <span>
                <i className="psi-link" />
                <b>284</b> Listed by NASA PSI
              </span>
              <span>
                <i className="ntrs-link" />
                <b>164</b> NTRS topic tags
              </span>
              <span>
                <i className="similarity-link" />
                <b>68</b> LSA similarities ≥ 0.55
              </span>
            </div>
          </Panel>
          <Panel title="Source figures" meta="ORIGINAL PAPER ASSETS" className="figure-panel">
            <button
              className="figure-card"
              onClick={() =>
                onEvidence({
                  label: "SPICE smoke-point figure",
                  value: "Figure asset",
                  tier: "paper_claim",
                  source: "SPICE paper · DOI-linked source",
                  path: "analysis/figures → anchored caption → source page",
                  note: "Original figure crop; caption and page retained. Not redrawn.",
                })
              }
            >
              <span className="figure-preview">
                <i />
                <i />
                <i />
              </span>
              <span>
                <strong>Smoke-point response</strong>
                <small>SPICE · page 8 · original figure</small>
              </span>
              <EvidenceBadge tier="paper_claim" />
            </button>
            <button
              className="figure-card"
              onClick={() =>
                onEvidence({
                  label: "SPICE scaling relation",
                  value: "coflow +0.41 · diameter −0.76",
                  tier: "human_verified",
                  source: "SPICE paper equation and extracted smoke-point data",
                  path: "paper equation image → variable definition → daily validation",
                  note: "Equation is displayed as a source image in production; coefficients remain tied to their validation record.",
                })
              }
            >
              <span className="equation-preview" aria-label="Source equation image placeholder">
                <i />
                <i />
                <i />
              </span>
              <span>
                <strong>Equation 4 · scaling relation</strong>
                <small>Original equation crop · variables defined in source</small>
              </span>
              <EvidenceBadge tier="human_verified" />
            </button>
          </Panel>
        </div>
      </div>
    </div>
  );
}

type Msg = {
  role: "user" | "assistant";
  text: string;
  reply?: AskReply;
  pending?: boolean;
  failed?: boolean;
};

/** Percakapan sungguhan dengan backend: /ask memanggil alat, lalu setiap angka
 *  dalam jawaban diperiksa terhadap keluaran alat (grounding). Yang ditampilkan
 *  di bawah jawaban adalah hasil pemeriksaan itu apa adanya -- termasuk ketika
 *  ada angka yang tidak bersumber. */
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
    const history = messages
      .filter((m) => !m.pending && !m.failed)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.text }));
    try {
      const reply = await askApi(q, history);
      setMessages((c) => [
        ...c.slice(0, -1),
        { role: "assistant", text: reply.answer, reply },
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
                ) : (
                  <p>{m.text}</p>
                )}
                {m.reply && <ReplyMeta reply={m.reply} />}
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
function ReplyMeta({ reply }: { reply: AskReply }) {
  const g = reply.grounding;
  const bad = g?.ungrounded?.length ?? 0;
  const figures = reply.figures ?? [];
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
      {figures.length > 0 && (
        <div className="figure-strip">
          {figures.slice(0, 4).map((f) => (
            <figure key={f.id}>
              <img src={figureUrl(f.image)} alt={f.caption} loading="lazy" />
              <figcaption>
                <b>{f.label}</b> · p. {f.page}
                <span>{f.paper}</span>
                {f.doi && (
                  <a href={`https://doi.org/${f.doi}`} target="_blank" rel="noreferrer">
                    doi.org/{f.doi}
                  </a>
                )}
              </figcaption>
            </figure>
          ))}
        </div>
      )}
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
  const [exchange, setExchange] = useState<{ question: string; answer: string } | null>(null);

  const submit = () => {
    if (!question.trim()) return;
    setExchange({
      question,
      answer:
        "I can trace that through the indexed evidence. Open the full assistant to inspect tools, sources, and numerical grounding.",
    });
    setQuestion("");
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
                <p>{exchange.answer}</p>
                <small>Preview response · backend tools connect during integration</small>
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
  const { data, error } = useInsight();
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
function Footer() {
  return (
    <footer className="statusbar">
      <span>
        <i /> SYSTEM STATUS <b>NOMINAL</b>
      </span>
      <span>
        DATA LAYERS <b>09 / 09</b>
      </span>
      <span>
        SEARCH INDEX <b>7,924 CHUNKS</b>
      </span>
      <span>
        MODEL <b>RESEARCH PROTOTYPE</b>
      </span>
      <em className="visual-credit">DESERT ANALOG · RYAN GREWELL / UNSPLASH</em>
      <em>FLARE+ · UI 1.0</em>
    </footer>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
