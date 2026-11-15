/**
 * Burn Replay: laboratorium virtual Open FLEX (proyek terpisah, dist/open_flex_lab.html)
 * disajikan di /flare/openflex/ dan disematkan di sini. Karena origin-nya sama, FLARE+
 * bisa membuka langsung uji tertentu lewat OF.selectTest(id) di dalam iframe.
 *
 * Fokus yang diterima (go("Replay", ...)):
 *   "test:PSI-69:181F001"  -> dipetakan lewat cir_map.json (cir_identifier Tabel IX -> FLEX-035)
 *   "flex:FLEX-035"        -> langsung
 */
import React, { useEffect, useRef, useState } from "react";
import { PageTitle, Panel, go, useFocus, useJSON } from "./ui";

export function flexIdFor(testId: string | null, map: Record<string, string> | null): string | null {
  if (!testId || !map) return null;
  if (testId.startsWith("flex:")) return testId.slice(5);
  const label = testId.split(":").pop() ?? "";
  return map[label] ?? null;
}

export function Replay() {
  const focus = useFocus("Replay");
  const map = useJSON<Record<string, string>>("openflex/cir_map.json");
  const frame = useRef<HTMLIFrameElement>(null);
  const [ready, setReady] = useState(false);
  const [shown, setShown] = useState<string | null>(null);
  const target = flexIdFor(focus, map.data);

  // Saat lab siap: tema gelap (menyatu dengan FLARE+) dan langsung ke tab Experiment
  // (tampilan 3D + timeline), lalu pilih uji yang diminta bila ada.
  useEffect(() => {
    if (!ready) return;
    let tries = 0;
    const t = setInterval(() => {
      const w = frame.current?.contentWindow as any;
      if (!w?.OF?.selectTest) {
        if (++tries > 60) clearInterval(t);
        return;
      }
      clearInterval(t);
      const d = w.document;
      if (d.documentElement.getAttribute("data-theme") !== "dark" && w.OF.toggleTheme) w.OF.toggleTheme();
      const tab = d.getElementById("tabbtn-lab");
      if (tab && w.OF.switchTab) w.OF.switchTab("lab", tab);
      // adegan 3D langsung terlihat: gulir isi lab ke tabnya, dan halaman ke bingkai lab
      setTimeout(() => {
        d.getElementById("tabbtn-lab")?.scrollIntoView({ block: "start" });
        frame.current?.scrollIntoView({ block: "start", behavior: "smooth" });
      }, 300);
      if (target) {
        w.OF.selectTest(target);
        setShown(target);
      } else {
        setShown(d.getElementById("test-select")?.value ?? null);
      }
    }, 200);
    return () => clearInterval(t);
  }, [ready, target]);

  const backTo = focus?.startsWith("test:") ? focus : null;

  return (
    <div className="page">
      <PageTitle
        index="07"
        overline="FLEX BURN REPLAY"
        title="Burn Replay"
        description="Watch any of the 276 FLEX droplet tests burn in 3D, in real time, from NASA's Table IX. Thirteen tests follow droplet and flame sizes digitized from the report's figures; the rest are reconstructed from the printed initial diameter and burning rate, and the lab says which on every frame."
      />
      <Panel
        title={shown ? `Open FLEX lab · ${shown}` : "Open FLEX lab"}
        meta="NASA/TP-2015-216046 · TABLE IX"
        className="replay-panel"
      >
        <div className="replay-bar">
          {backTo && (
            <button className="text-button" onClick={() => go("Tests", backTo)}>
              ← BACK TO TEST {backTo.split(":").pop()}
            </button>
          )}
          {focus?.startsWith("test:") && map.data && !target && (
            <span className="sim-flag">This test is not in Table IX of the FLEX report, so it cannot be replayed.</span>
          )}
          <span className="muted">
            Pick any test in the lab’s own selector, press play, scrub through the procedure, and open “Transparency” to see where each
            value comes from.
          </span>
          <a className="text-button" href="openflex/index.html" target="_blank" rel="noreferrer">
            OPEN FULL SCREEN ↗
          </a>
        </div>
        <iframe
          ref={frame}
          className="replay-frame"
          src="openflex/index.html"
          title="Open FLEX burn replay"
          onLoad={() => setReady(true)}
        />
        <p className="panel-footnote">
          Open FLEX is an independent, evidence-traceable lab built on NASA/TP-2015-216046 (NTRS 20150023456). Its drawing is a playback
          of reported data, not a combustion simulation; its optional D²-law “Explore” runs are labelled as simulations and never as the test
          itself. Not a NASA product.
        </p>
      </Panel>
    </div>
  );
}
