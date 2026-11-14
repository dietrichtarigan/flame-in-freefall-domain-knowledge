// Uji unit nerve.js tanpa browser:  node app/nerve/nerve.test.mjs
import assert from "node:assert/strict";
import { createNerve } from "./nerve.js";

const TESTS = [
  { id: "test:PSI-159:21106G7", accession: "PSI-159", label: "21106G7", o2: 0.2086, p_kpa: 50.6, ignited: true, flags: [], rules: [] },
  { id: "test:PSI-159:21106G8", accession: "PSI-159", label: "21106G8", o2: null, p_kpa: 51.0, ignited: true, flags: ["sinyal_lemah"], rules: ["R3_tanpa_konsumsi_o2"] },
  { id: "test:PSI-10:19115A1", accession: "PSI-10", label: "19115A1", o2: 0.207, p_kpa: 103, ignited: true, flags: [], rules: [] },
  { id: "test:PSI-159:21106A1", accession: "PSI-159", label: "21106A1", o2: null, p_kpa: 50, ignited: false, flags: [], rules: ["R2_percobaan_ulang"] },
];
const calls = [];
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
async function fakeFetch(url, opt) {
  calls.push(url);
  const path = url.replace(/^http:\/\/x/, "");
  if (path.startsWith("/entity/PSI-159%3A21106G7")) await delay(40);   // G7 lambat -> harus dibuang bila fokus pindah
  const body = path.startsWith("/tests") ? { n: TESTS.length, tests: TESTS }
    : path.startsWith("/alerts") ? { counts: { kritis: 0 }, alerts: [] }
    : path.startsWith("/entity/") ? { id: "test:" + decodeURIComponent(path.split("/")[2]), label: path }
    : path.startsWith("/explain/") ? { hipotesis: [] }
    : path.startsWith("/relevance/") ? { related: [{ id: "test:PSI-159:21106G7", score: 2.4 }] }
    : path.startsWith("/notes") ? { notes: [] }
    : path.startsWith("/whatif/") ? { valid: true, p_ignite: 0.5, input: path }
    : path === "/note" ? { entity: "x", text: JSON.parse(opt.body).text }
    : { error: "?" };
  return { json: async () => body };
}

const n = createNerve({ api: "http://x", fetchImpl: fakeFetch, debounceMs: 10 });
const seen = [];
n.on("*", (_p, evt) => seen.push(evt));
await n.start({});
assert.equal(n.state.tests.length, 4);
assert.equal(n.state.visible.length, 4);

// dynamic query
n.dispatch("filter", { dim: "accession", value: "PSI-159" });
assert.equal(n.state.visible.length, 3);
n.dispatch("filter", { dim: "flag", value: "R2_percobaan_ulang" });
assert.deepEqual(n.state.visible.map((t) => t.label), ["21106A1"]);
n.dispatch("filter", { dim: "o2", value: [0.2, 0.21] });
assert.equal(n.state.visible.length, 0, "o2 null tidak lolos filter rentang");
n.dispatch("clearFilters");
assert.equal(n.state.visible.length, 4);

// brushing
n.dispatch("select", { ids: ["test:PSI-159:21106G7"] });
n.dispatch("select", { ids: ["test:PSI-159:21106G8"], mode: "toggle" });
assert.deepEqual(n.state.selection.sort(), ["test:PSI-159:21106G7", "test:PSI-159:21106G8"]);
n.dispatch("select", { ids: ["test:PSI-159:21106G7"], mode: "toggle" });
assert.deepEqual(n.state.selection, ["test:PSI-159:21106G8"]);

// fokus cepat beruntun: respons lambat G7 tidak boleh menimpa G8
n.dispatch("focus", "test:PSI-159:21106G7");
n.dispatch("focus", "test:PSI-159:21106G8", "assistant");
await delay(80);
assert.equal(n.state.focus, "test:PSI-159:21106G8");
assert.ok(n.state.dossier.id.endsWith("21106G8"), "dosir basi tertimpa: " + n.state.dossier.id);
assert.equal(n.relevanceOf("test:PSI-159:21106G7"), 2.4);
assert.equal(n.state.trail.at(-1).actor, "assistant");

// undo
n.dispatch("undo");
assert.equal(n.state.focus, "test:PSI-159:21106G7");

// what-if dengan debounce: 3 geseran cepat -> 1 permintaan
const before = calls.filter((c) => c.includes("/whatif/")).length;
n.dispatch("whatif", { o2: 0.22 }); n.dispatch("whatif", { o2: 0.23 }); n.dispatch("whatif", { o2: 0.24 });
await delay(40);
const after = calls.filter((c) => c.includes("/whatif/")).length;
assert.equal(after - before, 1, "debounce gagal");
assert.ok(n.state.whatifResult.input.includes("o2=0.24"));

// berbagi lewat URL
const h = n.toHash();
const m = createNerve({ api: "http://x", fetchImpl: fakeFetch, debounceMs: 10 });
await m.start({ hash: h });
assert.equal(m.state.focus, n.state.focus);
assert.deepEqual(m.state.selection, n.state.selection);
assert.equal(m.state.whatif.o2, 0.24);

// catatan
await n.dispatch("note", { text: "cek panas sisa pemantik" });
assert.equal(n.state.notes.at(-1).text, "cek panas sisa pemantik");

for (const evt of ["tests.loaded", "visible.changed", "selection.changed", "focus.changed", "dossier.changed",
  "relevance.changed", "whatif.result", "trail.changed", "notes.changed"]) assert.ok(seen.includes(evt), "tidak terpancar: " + evt);
console.log("SEMUA UJI LULUS —", n.state.trail.length, "langkah jejak,", seen.length, "peristiwa");
