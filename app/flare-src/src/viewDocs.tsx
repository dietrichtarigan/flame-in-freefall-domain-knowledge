/**
 * Documentation: video tur (direkam dari dashboard sungguhan oleh scripts/record_tour.mjs)
 * + panduan singkat tiap view + cara membaca angka + sumber data & keterbatasan.
 */
import React, { useEffect, useRef, useState } from "react";
import { PageTitle, Panel, go, type View } from "./ui";
import { TEX, Tex } from "./math";

type Chapter = { t: number; title: string };

const GUIDE: { view: View; title: string; answers: string; steps: string[] }[] = [
  {
    view: "Overview",
    title: "Mission Overview",
    answers: "What is in the archive, and where are the biggest holes?",
    steps: ["Click a count to see where it comes from.", "Click a pillar to list its investigations.", "Click a gap to open it in Gaps Analysis."],
  },
  {
    view: "Scenario",
    title: "Scenario Explorer",
    answers: "Which investigations matter for a cabin, a Moon/Mars base or rover, a spacesuit, or Earth?",
    steps: [
      "Pick the habitat at the top.",
      "Move the three weights to see whether the order holds; the stability line says how often each rank survives 2,000 random weightings.",
      "Open “Why this score” for the arithmetic, and click a dot in the scatter to open that test.",
    ],
  },
  {
    view: "Gaps",
    title: "Gaps Analysis",
    answers: "What can the data not answer for this habitat, and which test would teach the most?",
    steps: ["Pick the habitat.", "Read the critical findings first.", "Use “Try these conditions in What-if” on a proposed test."],
  },
  {
    view: "Investigations",
    title: "Investigations",
    answers: "What did each experiment burn, under which conditions, and how do two of them differ?",
    steps: ["Filter by hardware or pillar.", "Open a card for objective, impact and links.", "Switch to Compare: rows marked ≠ are where the investigations differ."],
  },
  {
    view: "Tests",
    title: "Test Explorer",
    answers: "What exactly happened in one test, and can I trust its numbers?",
    steps: ["Filter by investigation, ignition or flag; search by test id or fuel.", "Open a test, then click any value to see its source file and method.", "Read “Why is it flagged?” and jump to similar tests."],
  },
  {
    view: "WhatIf",
    title: "What-if Simulator",
    answers: "What would happen at conditions NASA did not test exactly?",
    steps: ["Move the sliders; results update with an uncertainty band.", "Compare with the closest real ISS tests listed underneath.", "Outside the tested range the models refuse to answer instead of guessing."],
  },
  {
    view: "Map",
    title: "Research Map",
    answers: "Which papers stand behind each investigation, and what are their intellectual roots?",
    steps: ["In the citation network, search a paper and click it to trace what it cites.", "Isolate a k-means cluster from the list.", "In the network below, click an investigation or topic to light up its papers."],
  },
  {
    view: "Quality",
    title: "Quality & Verification",
    answers: "Where might the numbers be wrong, and how good are the models?",
    steps: ["Switch between critical, warning and info alerts; click a test id to open it.", "Read the verification queue: what a human still has to check.", "Open a model card for its validation metrics and caveats."],
  },
  {
    view: "Assistant",
    title: "AI Assistant",
    answers: "Ask anything in plain language and get an answer built from the data, with sources.",
    steps: ["Browse “See what it can do” for real recorded answers.", "Ask your own question: it searches papers, shows figures and equations, runs the models and plots data.", "Numbers that no tool produced are listed as unsupported."],
  },
];

const TIERS: [string, string][] = [
  ["NASA table", "Recorded by NASA in the PSI test tables."],
  ["NASA calibrated", "A NASA raw signal converted with a validated NASA formula (e.g. chamber pressure)."],
  ["Derived automatically", "Produced by our scripts from NASA files (telemetry, video); not yet checked by a person."],
  ["Human verified", "Checked by a person on the proof sheet or telemetry curve."],
  ["Paper claim", "A value stated in a publication."],
  ["Model prediction", "Output of a model; always shown with its range, and refused outside the tested conditions."],
];

export function Docs() {
  const video = useRef<HTMLVideoElement>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [cur, setCur] = useState(0);
  const [hasVideo, setHasVideo] = useState(true);
  useEffect(() => {
    fetch("docs/tour_chapters.json")
      .then((r) => (r.ok ? r.json() : []))
      .then(setChapters)
      .catch(() => setChapters([]));
  }, []);
  const seek = (t: number) => {
    if (video.current) {
      video.current.currentTime = t;
      video.current.play().catch(() => {});
    }
  };
  return (
    <div className="page">
      <PageTitle
        index="10"
        overline="DOCUMENTATION"
        title="How to use FLARE+"
        description="A recorded walkthrough of every view, a one-minute guide to each, how to read the numbers, and what the data can and cannot tell you."
      />
      <Panel title="Video walkthrough" meta="FEATURE TOUR">
        {hasVideo ? (
          <video
            ref={video}
            className="doc-video"
            src="docs/tour.mp4"
            poster="docs/tour_poster.jpg"
            controls
            preload="metadata"
            onError={() => setHasVideo(false)}
            onTimeUpdate={(e) => {
              const t = e.currentTarget.currentTime;
              const i = chapters.reduce((a, c, j) => (t >= c.t ? j : a), 0);
              if (i !== cur) setCur(i);
            }}
          />
        ) : (
          <p className="chart-note">The walkthrough video is not available on this server.</p>
        )}
        {chapters.length > 0 && (
          <div className="doc-chapters">
            {chapters.map((c, i) => (
              <button key={c.t} className={i === cur ? "active" : ""} onClick={() => seek(c.t)}>
                {new Date(c.t * 1000).toISOString().slice(15, 19)} · {c.title}
              </button>
            ))}
          </div>
        )}
      </Panel>

      <Panel title="Each view in one minute" meta="CLICK OPEN TO GO THERE">
        <div className="doc-grid">
          {GUIDE.map((g) => (
            <article key={g.view} className="doc-card">
              <h3>{g.title}</h3>
              <p>
                <b>Answers:</b> {g.answers}
              </p>
              <ol>
                {g.steps.map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
              <button className="text-button" onClick={() => go(g.view)}>
                OPEN {g.title.toUpperCase()} →
              </button>
            </article>
          ))}
        </div>
      </Panel>

      <div className="doc-grid">
        <Panel title="How to read the numbers" meta="EVIDENCE LEVELS">
          <div className="doc-card">
            <p>Every number carries the level of evidence behind it. You see it when you open a value’s source (Test Explorer) and in the model cards.</p>
            <ul>
              {TIERS.map(([k, v]) => (
                <li key={k}>
                  <b>{k}:</b> {v}
                </li>
              ))}
            </ul>
            <p>Empty means “not reported”, never zero. Thermocouple telemetry is raw volts, never converted to a temperature.</p>
          </div>
        </Panel>
        <Panel title="How the ranking works" meta="TRANSPARENT SCORE">
          <div className="doc-card">
            <Tex src={TEX.score} caption="Default weights 0.40 / 0.35 / 0.25; you can change them in Scenario Explorer." />
            <p>
              <b>Direct link</b>: how directly the investigation addresses spacecraft fire safety (from the challenge statement and the PSI
              sub-area). <b>Conditions</b>: how many of its tests fall inside the habitat’s oxygen and pressure band. <b>Evidence</b>: how many
              result values it recorded.
            </p>
            <p>The score orders investigations for one habitat. It is not a probability and not a NASA judgement.</p>
          </div>
        </Panel>
        <Panel title="Data sources" meta="ALL PUBLIC">
          <div className="doc-card">
            <ul>
              <li>NASA Physical Sciences Informatics (PSI): 24 combustion investigations, 1,990 test rows, raw files (CC0).</li>
              <li>NASA Technical Reports Server (NTRS) and journal papers: 438 papers with full text indexed for the assistant.</li>
              <li>Mined by us from raw NASA files: ACME telemetry (943 tests), BASS video (139 flame episodes), Saffire flame spread, SPICE smoke points.</li>
              <li>Crossref open metadata: reference lists for the citation network.</li>
            </ul>
            <p>
              Independent project, not an official NASA product.{" "}
              <a href="https://github.com/dietrichtarigan/flame-in-freefall-domain-knowledge" target="_blank" rel="noreferrer">
                Code and data ↗
              </a>
            </p>
          </div>
        </Panel>
        <Panel title="What the data cannot tell you" meta="KNOWN LIMITS">
          <div className="doc-card">
            <ul>
              <li>There is no partial-gravity combustion data in PSI. Moon and Mars answers are bounded by microgravity and Earth data and a buoyancy-scaling model.</li>
              <li>No solid material was tested in microgravity above 22% oxygen, while a Moon base will run at about 30%.</li>
              <li>The gravity bridge is fitted for a PMMA rod near 1 atm; at 70 kPa it is flagged as extrapolation.</li>
              <li>Automatically derived numbers (video, telemetry) still await human verification; the Quality view lists them.</li>
              <li>Only 222 of 438 indexed papers have an open reference list, so the citation network is incomplete.</li>
            </ul>
          </div>
        </Panel>
      </div>
    </div>
  );
}
