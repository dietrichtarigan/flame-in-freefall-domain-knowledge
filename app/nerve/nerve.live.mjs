// Uji ujung-ke-ujung terhadap server otak sungguhan:
//   python scripts/brain.py serve --port 8765   (terminal lain)
//   node app/nerve/nerve.live.mjs
import assert from "node:assert/strict";
import { createNerve } from "./nerve.js";

const N = createNerve({ api: "http://127.0.0.1:8765", debounceMs: 5 });
const wait = (ev) => new Promise((r) => { const off = N.on(ev, (p) => { off(); r(p); }); });
const t0 = Date.now();
await N.start({});
console.log(`muat: ${N.state.tests.length} uji, peringatan ${JSON.stringify(N.state.alerts.counts)} (${Date.now() - t0} ms)`);

// 1. sistem memanggil perhatian: ambil peringatan "perhatian" pertama, fokus ke sana
const al = N.state.alerts.alerts.find((a) => a.title.startsWith("kemungkinan positif palsu"));
assert.ok(al, "peringatan positif palsu (G8) harus ada");
const rel = wait("relevance.changed");
N.dispatch("focus", al.entity);
await rel; await new Promise((r) => setTimeout(r, 300));
console.log(`fokus ${N.state.focus}: hipotesis teratas = "${N.state.explanation.hipotesis[0].hipotesis}"`);
console.log(`  relevan: ${N.state.relevance.related.slice(0, 5).map((o) => o.label + "(" + o.score + ")").join(", ")}`);
assert.ok(N.relevanceOf("test:PSI-159:21106G7") > 0, "G7 harus relevan dengan G8 (seri)");

// 2. dynamic query: hanya uji yang kena aturan percobaan ulang
N.dispatch("filter", { dim: "flag", value: "R2_percobaan_ulang" });
console.log(`filter R2: ${N.state.visible.map((t) => t.label).join(" ")}`);
assert.equal(N.state.visible.length, 9);

// 3. brushing: pilih semuanya, lalu reset filter -> pilihan tetap
N.dispatch("select", { ids: N.state.visible.map((t) => t.id) });
N.dispatch("clearFilters");
assert.equal(N.state.selection.length, 9);

// 4. what-if: di dalam dan di luar rentang
let r = wait("whatif.result"); N.dispatch("whatif", { exp: "cfig", config: "normal", fuel: "butane", o2: 0.3, x_fuel: 0.4 });
let w = await r; console.log(`what-if butana normal O2=0,30 xf=0,40: P(menyala)=${w.p_ignite}, valid=${w.valid}`);
r = wait("whatif.result"); N.dispatch("whatif", { o2: 0.7 });
w = await r; console.log(`what-if O2=0,70: valid=${w.valid} -> "${w.warning}"`);
assert.equal(w.valid, false);

// 5. asisten memakai pintu yang sama
N.dispatch("focus", "test:PSI-159:21106G7", "assistant");
await wait("explain.changed");
assert.equal(N.state.trail.at(-1).actor, "assistant");

// 6. undo kembali ke G8, lalu tautan berbagi memulihkan keadaan di "browser" lain
N.dispatch("undo");
assert.equal(N.state.focus, al.entity);
const M = createNerve({ api: "http://127.0.0.1:8765", debounceMs: 5 });
await M.start({ hash: N.toHash() });
assert.equal(M.state.focus, N.state.focus);
assert.equal(M.state.selection.length, 9);
console.log(`UJI UJUNG-KE-UJUNG LULUS (${Date.now() - t0} ms, ${N.state.trail.length} langkah jejak)`);
process.exit(0);
