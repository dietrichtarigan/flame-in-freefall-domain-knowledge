// Rekam tur FLARE+ dari dashboard sungguhan (tanpa dependensi tambahan).
//
// Edge headless dikendalikan lewat Chrome DevTools Protocol (WebSocket bawaan Node 22+),
// frame diambil ~8 per detik, lalu ffmpeg menyusunnya menjadi MP4. Narasi tampil sebagai
// teks di layar, kursor tiruan menunjukkan apa yang diklik.
//
//   node scripts/record_tour.mjs shots  <url>   -> analysis/ui_shots/*.jpg (pemeriksaan visual)
//   node scripts/record_tour.mjs tour   <url>   -> app/flare-src/public/docs/tour.mp4 (+ bab, poster)
//
// <url> default http://127.0.0.1:8799/flare/ (jalankan: FIF_PUBLIC=1 python scripts/brain.py serve --port 8799)
import { spawn, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1")), "..");
const EDGE = process.env.EDGE || "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const FFMPEG = process.env.FFMPEG || "ffmpeg";
const [, , mode = "shots", BASE = "http://127.0.0.1:8799/flare/"] = process.argv;
const W = 1440, H = 900;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function launch() {
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "flare-edge-"));
  const port = 9300 + Math.floor(Math.random() * 500);
  const proc = spawn(EDGE, [
    "--headless=new", `--remote-debugging-port=${port}`, `--user-data-dir=${profile}`,
    `--window-size=${W},${H}`, "--hide-scrollbars", "--mute-audio", "--no-first-run", "about:blank",
  ], { stdio: "ignore" });
  let ws;
  for (let i = 0; i < 50 && !ws; i++) {
    await sleep(200);
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const pg = list.find((t) => t.type === "page");
      if (pg) ws = pg.webSocketDebuggerUrl;
    } catch { /* belum siap */ }
  }
  if (!ws) throw new Error("Edge DevTools tidak bisa dihubungi");
  const sock = new WebSocket(ws);
  await new Promise((r, j) => { sock.onopen = r; sock.onerror = j; });
  let id = 0;
  const pending = new Map();
  sock.onmessage = (m) => {
    const d = JSON.parse(m.data);
    if (d.id && pending.has(d.id)) {
      const { res, rej } = pending.get(d.id);
      pending.delete(d.id);
      d.error ? rej(new Error(d.error.message)) : res(d.result);
    }
  };
  const send = (method, params = {}) => new Promise((res, rej) => {
    const i = ++id;
    pending.set(i, { res, rej });
    sock.send(JSON.stringify({ id: i, method, params }));
  });
  await send("Page.enable");
  await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width: W, height: H, deviceScaleFactor: 1, mobile: false });
  const evaluate = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description || "evaluate gagal");
    return r.result.value;
  };
  const shot = async (file, quality = 72) => {
    const r = await send("Page.captureScreenshot", { format: "jpeg", quality });
    fs.writeFileSync(file, Buffer.from(r.data, "base64"));
  };
  const goto = async (url) => { await send("Page.navigate", { url }); await sleep(2500); };
  const close = () => { try { sock.close(); } catch {} ; proc.kill(); };
  return { send, evaluate, shot, goto, close };
}

// pembantu di halaman: kursor tiruan, teks narasi, klik berdasarkan teks, geser slider pelan
const HELPERS = `
window.__t = (() => {
  const cur = document.createElement('div');
  cur.style.cssText = 'position:fixed;z-index:99999;width:22px;height:22px;border-radius:50%;border:2px solid #fff;background:rgba(240,163,94,.55);box-shadow:0 0 12px rgba(240,163,94,.9);left:700px;top:450px;transition:left .55s ease,top .55s ease,transform .15s;pointer-events:none';
  const cap = document.createElement('div');
  cap.style.cssText = 'position:fixed;z-index:99998;left:50%;bottom:58px;transform:translateX(-50%);max-width:880px;padding:12px 20px;background:rgba(12,12,10,.92);border:1px solid rgba(240,163,94,.7);color:#f2ece0;font:500 17px/1.45 Poppins,system-ui,sans-serif;text-align:center;border-radius:4px;pointer-events:none';
  const chap = document.createElement('div');
  chap.style.cssText = 'position:fixed;z-index:99998;left:250px;top:84px;padding:5px 12px;background:#e0894f;color:#171713;font:600 13px Poppins,system-ui,sans-serif;letter-spacing:.06em;text-transform:uppercase;pointer-events:none';
  document.body.append(cur, cap, chap);
  const wait = (ms) => new Promise(r => setTimeout(r, ms));
  const find = (sel, text) => [...document.querySelectorAll(sel)].find(e => e.offsetParent !== null && (!text || e.innerText.trim().toLowerCase().includes(text.toLowerCase())));
  const moveTo = async (el) => { el.scrollIntoView({block:'center', behavior:'smooth'}); await wait(700); const b = el.getBoundingClientRect(); cur.style.left = (b.left + b.width/2 - 11) + 'px'; cur.style.top = (b.top + b.height/2 - 11) + 'px'; await wait(650); };
  return {
    say: (t) => { cap.textContent = t; cap.style.display = t ? 'block' : 'none'; },
    chapter: (t) => { chap.textContent = t; },
    wait,
    async click(sel, text) { const el = find(sel, text); if (!el) return false; await moveTo(el); cur.style.transform = 'scale(.7)'; await wait(150); el.click(); cur.style.transform = 'scale(1)'; await wait(500); return true; },
    async slide(sel, idx, to, steps = 14) {
      const el = [...document.querySelectorAll(sel)].filter(e => e.offsetParent !== null)[idx]; if (!el) return false;
      await moveTo(el); const from = +el.value; const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;
      for (let i = 1; i <= steps; i++) { set.call(el, String(from + (to - from) * i / steps)); el.dispatchEvent(new Event('input', {bubbles:true})); await wait(110); }
      return true;
    },
    async select(sel, value) { const el = find(sel); if (!el) return false; await moveTo(el); const set = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,'value').set; set.call(el, value); el.dispatchEvent(new Event('change', {bubbles:true})); await wait(600); return true; },
    async type(sel, text) { const el = find(sel); if (!el) return false; await moveTo(el); el.focus(); const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set; for (let i = 1; i <= text.length; i++) { set.call(el, text.slice(0, i)); el.dispatchEvent(new Event('input', {bubbles:true})); await wait(70); } await wait(500); return true; },
    async scroll(y) { window.scrollTo({top: y, behavior: 'smooth'}); await wait(1100); },
    async scrollTo(sel, text) { const el = find(sel, text); if (el) { el.scrollIntoView({block:'start', behavior:'smooth'}); await wait(1100); window.scrollBy(0, -90); await wait(300); } },
    async view(v) { location.hash = v; window.scrollTo(0, 0); await wait(2200); },
  };
})(); true`;

async function shots() {
  const b = await launch();
  const out = path.join(ROOT, "analysis", "ui_shots");
  fs.mkdirSync(out, { recursive: true });
  await b.goto(BASE + "#Overview");
  await b.evaluate("localStorage.setItem('flare.notice','closed'); true");
  const views = (process.env.VIEWS || "Overview,Scenario,Gaps,Investigations,Tests,WhatIf,Map,Quality,Assistant,Docs").split(",");
  for (const v of views) {
    await b.evaluate(`location.hash='${v}'; window.scrollTo(0,0); true`);
    await sleep(3500);
    const hgt = await b.evaluate("document.documentElement.scrollHeight");
    for (let y = 0, k = 0; y < Math.min(hgt, 9000); y += H - 120, k++) {
      await b.evaluate(`window.scrollTo(0, ${y}); true`);
      await sleep(600);
      await b.shot(path.join(out, `${v}_${k}.jpg`));
    }
  }
  b.close();
  console.log("shots ->", out);
}

async function tour() {
  const b = await launch();
  const frames = fs.mkdtempSync(path.join(os.tmpdir(), "flare-frames-"));
  await b.goto(BASE + "#Overview");
  await b.evaluate("localStorage.setItem('flare.notice','closed'); true");
  await b.goto(BASE + "#Overview");
  await b.evaluate(HELPERS);
  let n = 0, rec = true;
  const FPS = 8;
  const t0 = Date.now();
  const grab = (async () => {
    while (rec) {
      const t = Date.now();
      try { await b.shot(path.join(frames, `f_${String(n).padStart(5, "0")}.jpg`), 70); n++; } catch {}
      const dt = 1000 / FPS - (Date.now() - t);
      if (dt > 0) await sleep(dt);
    }
  })();
  const chapters = [];
  const chapter = async (title) => { chapters.push({ t: Math.round((Date.now() - t0) / 100) / 10, title }); await b.evaluate(`__t.chapter(${JSON.stringify(title)}); true`); };
  const say = (t) => b.evaluate(`__t.say(${JSON.stringify(t)}); true`);
  const run = (js) => b.evaluate(`(async () => { ${js}; return true })()`);

  await chapter("Overview");
  await say("FLARE+ turns NASA's microgravity combustion archive into fire-safety answers for crewed habitats.");
  await sleep(3500);
  await run("await __t.scrollTo('.stat-strip')");
  await say("Every count is live from the knowledge base. Click one to see where it comes from.");
  await sleep(3000);
  await run("await __t.scrollTo('.panel', 'Biggest open gaps')");
  await say("The biggest open gaps across all habitats, one click from the full analysis.");
  await sleep(3000);

  await chapter("Scenario Explorer");
  await run("await __t.view('Scenario')");
  await say("Pick a habitat. A Moon base will run at 30% oxygen and about 70 kPa.");
  await run("await __t.click('.objective-segmented button', 'Surface')");
  await sleep(2500);
  await run("await __t.scrollTo('.rank-controls')");
  await say("Investigations are ranked by fire-safety link, condition match and evidence. Change the weights to test the order.");
  await run("await __t.slide('.weight-sliders input', 1, 100); await __t.slide('.weight-sliders input', 0, 10)");
  await sleep(1500);
  await say("Each rank shows how often it survives 2,000 random weightings, and the arithmetic behind the score.");
  await run("await __t.click('.rank-card .text-button', 'why')");
  await sleep(3000);
  await run("await __t.click('.weight-sliders .text-button', 'reset')");
  await run("await __t.scrollTo('.panel', 'Every tabulated test')");
  await say("Every NASA test by oxygen and pressure. The dashed box is the habitat; no solid material was tested inside it.");
  await sleep(4500);

  await chapter("Gaps");
  await run("await __t.view('Gaps')");
  await say("Gaps Analysis says what the data cannot answer, and which next experiment would teach the most.");
  await sleep(4000);
  await run("await __t.scrollTo('.panel', 'Most informative next tests')");
  await sleep(2500);

  await chapter("Investigations");
  await run("await __t.view('Investigations')");
  await say("All 24 investigations. Open one for its objective, its link to fire safety and the NASA record.");
  await run("await __t.click('.inv-main', 'FLEX')");
  await sleep(3000);
  await say("Compare up to four side by side. Rows marked ≠ are where they differ.");
  await run("await __t.click('.view-tabs button', 'Compare')");
  await sleep(4500);

  await chapter("Test Explorer");
  await run("await __t.view('Tests')");
  await say("Every test row, traced. Search one test to open its dossier.");
  await run("await __t.type('.filter-row input', '21106G8')");
  await run("await __t.click('.tests-table tbody tr')");
  await sleep(2500);
  await say("Click a value to see the raw NASA file and method behind it; flags are explained by rules, not by a language model.");
  await run("await __t.click('.measure')");
  await sleep(3500);

  await chapter("What-if");
  await run("await __t.view('WhatIf')");
  await say("What-if: move the conditions and see what models trained on ISS tests predict, with uncertainty.");
  await run("await __t.click('.sim-panel .segmented button', 'Mars')");
  await run("await __t.slide('.sim-panel input[type=range]', 0, 18)");
  await sleep(2500);
  await say("Outside the tested range the models say so, instead of guessing.");
  await run("await __t.scrollTo('.sim-panel', 'Droplet flame suppression')");
  await run("await __t.slide('.sim-panel:last-child input[type=range]', 2, 0.35)");
  await sleep(2500);

  await chapter("Research Map");
  await run("await __t.view('Map')");
  await say("The citation network: papers we index, the works they cite, and their shared roots, clustered by topic.");
  await run("await __t.type('.cite-search input', 'flame spread')");
  await run("await __t.click('.cite-results button')");
  await sleep(4000);
  await run("await __t.scrollTo('.panel', 'Investigations, papers and topics')");
  await say("Click an investigation to light up the papers NASA lists for it.");
  await run("(() => { const n = document.querySelector('.net-svg .n.inv'); n && n.dispatchEvent(new MouseEvent('click', {bubbles:true})); })()");
  await sleep(3500);

  await chapter("Quality");
  await run("await __t.view('Quality')");
  await say("Quality: where numbers might be wrong, what a human still has to check, and how good each model is.");
  await run("await __t.click('.quality-grid .segmented button', 'warning')");
  await sleep(2500);
  await run("await __t.scrollTo('.panel', 'Model cards')");
  await run("await __t.click('.model-card summary')");
  await sleep(3500);

  await chapter("AI Assistant");
  await run("await __t.view('Assistant')");
  await say("The assistant answers from the data with tools: it cites papers, shows figures and equations, runs models and plots.");
  await sleep(3500);
  for (const label of ["Formula from a paper", "Figures from papers", "Moon base"]) {
    await run(`await __t.click('.demo-tabs button', ${JSON.stringify(label)})`);
    await sleep(1500);
    await run("await __t.scrollTo('.demo-q')");
    await sleep(2500);
  }
  await say("Every number in an answer is checked against the tool output that produced it.");
  await sleep(3000);
  await say("");
  rec = false;
  await grab;
  b.close();

  const docs = path.join(ROOT, "app", "flare-src", "public", "docs");
  fs.mkdirSync(docs, { recursive: true });
  const secs = (Date.now() - t0) / 1000;
  const fps = Math.max(4, Math.round((n / secs) * 10) / 10);
  execFileSync(FFMPEG, ["-y", "-loglevel", "error", "-framerate", String(fps), "-i", path.join(frames, "f_%05d.jpg"),
    "-vf", "scale=1280:-2", "-c:v", "libx264", "-preset", "slow", "-crf", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
    path.join(docs, "tour.mp4")]);
  fs.copyFileSync(path.join(frames, `f_${String(Math.min(n - 1, 40)).padStart(5, "0")}.jpg`), path.join(docs, "tour_poster.jpg"));
  fs.writeFileSync(path.join(docs, "tour_chapters.json"), JSON.stringify(chapters, null, 1));
  console.log(`tour: ${n} frames in ${secs.toFixed(0)} s (${fps} fps) -> ${docs}/tour.mp4`);
}

(mode === "tour" ? tour() : shots()).catch((e) => { console.error(e); process.exit(1); });
