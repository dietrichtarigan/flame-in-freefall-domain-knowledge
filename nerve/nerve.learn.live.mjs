// Uji ujung-ke-ujung tahap D + E lewat server sungguhan.
// Server HARUS dijalankan dengan log sementara (lihat scripts/test_live_de.sh / langkah uji), mis.:
//   FREEFALL_ANN=... FREEFALL_HISTORY=... FREEFALL_STATE=... FREEFALL_CASES=... python scripts/brain.py serve --port 8766
//   node app/nerve/nerve.learn.live.mjs 8766
import assert from "node:assert/strict";
import { createNerve } from "./nerve.js";

const port = process.argv[2] || "8766";
const api = `http://127.0.0.1:${port}`;
const N = createNerve({ api, debounceMs: 5 });
const once = (ev, ms = 180000) => new Promise((res, rej) => {
  const t = setTimeout(() => rej(new Error("timeout menunggu " + ev)), ms);
  const off = N.on(ev, (p) => { clearTimeout(t); off(); res(p); });
});
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const t0 = Date.now();
await N.start({ poll: false });
await N.dispatch("refreshQueue");
const before = { ...N.state.alerts.counts };
assert.ok(N.state.queue.n > 0, "antrean verifikasi harus terisi sebelum uji");
const qAll = await (await fetch(`${api}/queue?k=500`)).json();
assert.ok(qAll.items.some((x) => x.entity === "test:PSI-159:21106G8"), "G8 harus ada di antrean SEBELUM putusan");
console.log("awal:", before, "| antrean", N.state.queue.n, "| asisten", N.state.assistant?.claude ? "claude" : "luring");

// E1: asisten menjawab lewat alat dan menggerakkan dashboard
const t1 = await N.dispatch("ask", { question: "Kenapa uji 21106G8 dicurigai?" });
assert.ok(t1.a.includes("positif_palsu"), "jawaban harus menyebut aturan positif palsu");
assert.ok(t1.grounding.ok, "semua angka harus bersumber: " + t1.grounding.ungrounded);
assert.equal(N.state.focus, "test:PSI-159:21106G8", "asisten harus memfokuskan dashboard");
assert.ok(N.state.trail.some((x) => x.actor === "assistant" && x.action === "focus"), "jejak harus mencatat aksi asisten");
console.log(`E1 asisten: mode ${t1.mode}, alat ${t1.tool_calls.map((c) => c.name)}, ${t1.ms} ms, sitasi ${t1.citations.length}`);

// E2: what-if lewat asisten menggerakkan penggeser
const t2 = await N.dispatch("ask", { question: "Bagaimana jika O2 0.30 dan bahan bakar 0.4 pada butana normal?" });
assert.equal(N.state.whatif.o2, 0.3); assert.equal(N.state.whatif.x_fuel, 0.4);
console.log("E2 what-if: penggeser ikut bergerak ->", JSON.stringify(N.state.whatif));

// E3: umpan balik masuk memori kasus
await N.dispatch("feedback", { index: 0, rating: "baik" });
assert.equal(N.state.chat[0].rating, "baik");

// D1: putusan manusia -> siklus belajar -> data berubah
N.startPolling(1000);
const done = once("data.changed");
const r = await N.dispatch("annotate", { entity: "test:PSI-159:21106G8", quantity: "ignited", verdict: "ok",
  value_text: "tidak", note: "UJI LIVE: panas sisa pemantik", author: "uji-live" });
assert.ok(r.annotation?.id, "anotasi harus tercatat");
// D2: server tetap melayani selama belajar (termasuk saat otak ditukar)
let okReq = 0, errReq = 0, finished = false;
const hammer = (async () => {
  while (!finished) {
    try { const j = await (await fetch(`${api}/entity/PSI-159:21106G7`)).json(); j.error ? errReq++ : okReq++; } catch { errReq++; }
    await sleep(100);
  }
})();
const res = await done;
finished = true;
await hammer;
console.log(`D1 belajar selesai: ${JSON.stringify(res.ran)} dalam ${res.seconds} s | permintaan selama belajar: ${okReq} ok, ${errReq} galat`);
assert.equal(errReq, 0, "server harus tetap melayani tanpa galat selama otak ditukar");
await sleep(500);
const after = N.state.alerts.counts;
assert.ok(after.perhatian < before.perhatian, `peringatan perhatian harus turun (${before.perhatian} -> ${after.perhatian})`);
const qAfter = await (await fetch(`${api}/queue?k=500`)).json();
assert.ok(!qAfter.items.some((x) => x.entity === "test:PSI-159:21106G8"), "G8 harus keluar dari antrean");
assert.ok(qAfter.n < qAll.n, `antrean harus menyusut (${qAll.n} -> ${qAfter.n})`);
console.log(`   antrean ${qAll.n} -> ${qAfter.n}`);
const ig = N.state.dossier?.measurements?.ignited || [];
assert.ok(ig.some((m) => m.tier === "human_verified" && m.value_text === "tidak"), "dosir G8 harus memuat putusan manusia");
assert.ok(N.state.history.length >= 1, "riwayat belajar harus terisi");
console.log("D2 sesudah:", after, "| riwayat:", N.state.history.at(-1).summary);
console.log(`UJI D+E LULUS (${((Date.now() - t0) / 1000).toFixed(1)} s)`);
setTimeout(() => process.exit(0), 50);
