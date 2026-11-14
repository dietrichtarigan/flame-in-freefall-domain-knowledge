// nerve.js — sistem saraf dashboard (docs/rencana_dashboard_cerdas.md, lapis L4).
//
// Satu keadaan bersama. Semua tampilan DAN asisten hanya:
//   1. memanggil nerve.dispatch(aksi, argumen, pelaku)   -> mengubah keadaan
//   2. berlangganan nerve.on(peristiwa, fn)              -> bereaksi
// Tidak ada tampilan yang memanggil server sendiri. Dengan begitu klik di peta, kalimat
// asisten, dan tautan yang dibagikan semuanya menghasilkan keadaan yang SAMA.
//
// Konsep (Ware, Information Visualization, bab 11):
//   focus      degree-of-relevance (A7): fokus -> skor relevansi semua entitas
//   selection  brushing (A5): pilih di satu tampilan, sorot di semua tampilan
//   filters    dynamic queries (A9): rentang per dimensi
//   alerts     visual monitoring (A10): sistem yang memanggil perhatian
//   notes      externalizing: catatan disimpan bersama di server
//   trail      jejak langkah (siapa melakukan apa) -> bisa diputar ulang & dibagikan
// dan Big Book of Dashboards bab 4: what-if dengan penggeser.

const SNAP_KEYS = ["focus", "selection", "filters", "whatif"];

export function createNerve({ api = "", fetchImpl = globalThis.fetch?.bind(globalThis), debounceMs = 150 } = {}) {
  const state = {
    tests: [],            // semua uji (ringkas) dari /tests
    visible: [],          // hasil filter
    focus: null,          // id entitas, mis. "test:PSI-159:21106G8"
    selection: [],        // id terpilih (brushing)
    filters: {},          // {dim: nilai}; dim: accession | ignited | flag | o2 | p_kpa | q
    whatif: { exp: "cfig", config: "normal", fuel: "butane", o2: 0.25, x_fuel: 0.3 },
    whatifResult: null,
    dossier: null, explanation: null, relevance: null, relevanceMap: new Map(),
    alerts: { counts: {}, alerts: [] }, focusAlerts: [],
    notes: [], trail: [], loading: new Set(), error: null,
    // tahap D/E
    chat: [],             // [{q, a, mode, citations, tool_calls, grounding, ui_actions, rating}]
    queue: { n: 0, items: [] }, history: [], learning: { running: false, last: null, log: [] },
    assistant: null, serverSeq: 0,
  };
  const listeners = new Map();
  const undoStack = [];
  const tokens = {};                       // penjaga respons basi per jenis efek
  let whatifTimer = null;

  // ---------------------------------------------------------------- peristiwa
  function on(evt, fn) {
    if (!listeners.has(evt)) listeners.set(evt, new Set());
    listeners.get(evt).add(fn);
    return () => listeners.get(evt).delete(fn);
  }
  function emit(evt, payload) {
    for (const key of [evt, "*"]) {
      for (const fn of listeners.get(key) || []) {
        try { fn(payload, evt, state); } catch (e) { console.error("pendengar gagal", evt, e); }
      }
    }
  }

  // ---------------------------------------------------------------- server
  async function get(path, kind) {
    const my = (tokens[kind] = (tokens[kind] || 0) + 1);
    state.loading.add(kind); emit("loading.changed", [...state.loading]);
    try {
      const r = await fetchImpl(api + path);
      const j = await r.json();
      if (my !== tokens[kind]) return undefined;            // ada permintaan yang lebih baru: buang
      if (j && j.error) throw new Error(j.error);
      return j;
    } catch (e) {
      if (my === tokens[kind]) { state.error = String(e.message || e); emit("error", { kind, message: state.error }); }
      return undefined;
    } finally {
      if (my === tokens[kind]) { state.loading.delete(kind); emit("loading.changed", [...state.loading]); }
    }
  }

  async function post(path, body) {
    try {
      const r = await fetchImpl(api + path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const j = await r.json();
      if (j && j.error) { state.error = j.error; emit("error", { kind: path, message: j.error }); }
      return j;
    } catch (e) {
      state.error = String(e.message || e); emit("error", { kind: path, message: state.error });
      return null;
    }
  }

  // ---------------------------------------------------------------- peristiwa server (siklus belajar)
  let pollTimer = null;
  async function reloadData() {
    const [t, a] = await Promise.all([get("/tests", "tests"), get("/alerts", "alerts")]);
    if (t) { state.tests = t.tests; emit("tests.loaded", t.tests); recomputeVisible(); }
    if (a) { state.alerts = a; emit("alerts.changed", a); }
    if (state.focus) onFocus(state.focus);                  // dosir/penjelasan memakai otak baru
    ACTIONS.refreshQueue();
  }
  async function poll() {
    const r = await get(`/events?since=${state.serverSeq}`, "events");
    if (r) {
      for (const ev of r.events) {
        state.serverSeq = Math.max(state.serverSeq, ev.seq);
        emit("server." + ev.type, ev.data);
        if (ev.type === "pipeline.started") { state.learning = { running: true, last: null, log: [] }; emit("learning.changed", state.learning); }
        if (ev.type === "pipeline.step") { state.learning.log.push(ev.data.msg); emit("learning.changed", state.learning); }
        if (ev.type === "pipeline.done" || ev.type === "pipeline.failed") {
          state.learning.running = false; state.learning.last = ev.data; emit("learning.changed", state.learning);
          if (ev.type === "pipeline.done") { emit("data.changed", ev.data); await reloadData(); }
        }
      }
    }
  }
  function startPolling(ms = 3000) { clearInterval(pollTimer); pollTimer = setInterval(poll, ms); return () => clearInterval(pollTimer); }

  // ---------------------------------------------------------------- turunan
  const NUM_DIMS = ["o2", "p_kpa"];
  function passes(t, f) {
    if (f.accession && t.accession !== f.accession) return false;
    if (f.ignited !== undefined && f.ignited !== null && t.ignited !== f.ignited) return false;
    if (f.flag && !(t.flags || []).includes(f.flag) && !(t.rules || []).includes(f.flag)) return false;
    if (f.q && !(t.label + " " + (t.fuel || "")).toLowerCase().includes(String(f.q).toLowerCase())) return false;
    for (const d of NUM_DIMS) {
      const r = f[d];
      if (r && (t[d] == null || t[d] < r[0] || t[d] > r[1])) return false;
    }
    return true;
  }
  function recomputeVisible() {
    state.visible = state.tests.filter((t) => passes(t, state.filters));
    emit("visible.changed", { n: state.visible.length, of: state.tests.length });
  }

  // ---------------------------------------------------------------- efek
  async function onFocus(id) {
    state.dossier = state.explanation = state.relevance = null;
    state.relevanceMap = new Map();
    emit("dossier.changed", null); emit("relevance.changed", null); emit("explain.changed", null);
    if (!id) return;
    const enc = encodeURIComponent(id.replace(/^test:/, ""));
    const [d, x, r, a, n] = await Promise.all([
      get(`/entity/${enc}`, "dossier"), get(`/explain/${enc}`, "explain"), get(`/relevance/${enc}?k=50`, "relevance"),
      get(`/alerts?entity=${enc}`, "focusAlerts"), get(`/notes?entity=${enc}`, "notes"),
    ]);
    if (state.focus !== id) return;                          // fokus sudah pindah saat menunggu
    if (d) { state.dossier = d; emit("dossier.changed", d); }
    if (x) { state.explanation = x; emit("explain.changed", x); }
    if (r) {
      state.relevance = r;
      state.relevanceMap = new Map((r.related || []).map((o) => [o.id, o.score]));
      state.relevanceMap.set(id, Infinity);
      emit("relevance.changed", r);
    }
    if (a) { state.focusAlerts = a.alerts; emit("focusAlerts.changed", a.alerts); }
    if (n) { state.notes = n.notes; emit("notes.changed", n.notes); }
  }
  function scheduleWhatif() {
    clearTimeout(whatifTimer);
    whatifTimer = setTimeout(async () => {
      const w = state.whatif;
      const qs = new URLSearchParams(Object.entries(w).filter(([k, v]) => k !== "exp" && v !== "" && v != null));
      const res = await get(`/whatif/${w.exp}?${qs}`, "whatif");
      if (res) { state.whatifResult = res; emit("whatif.result", res); }
    }, debounceMs);
  }

  // ---------------------------------------------------------------- aksi
  const snapshot = () => JSON.parse(JSON.stringify(Object.fromEntries(SNAP_KEYS.map((k) => [k, state[k]]))));
  const ACTIONS = {
    focus(id) { state.focus = id || null; emit("focus.changed", state.focus); onFocus(state.focus); },
    select({ ids = [], mode = "replace" } = {}) {
      const cur = new Set(state.selection);
      if (mode === "replace") cur.clear();
      for (const id of ids) {
        if (mode === "toggle" && cur.has(id)) cur.delete(id); else if (mode !== "remove") cur.add(id); else cur.delete(id);
      }
      state.selection = [...cur];
      emit("selection.changed", state.selection);
    },
    filter({ dim, value }) {
      if (value === undefined || value === null || value === "") delete state.filters[dim];
      else state.filters[dim] = value;
      emit("filters.changed", { ...state.filters }); recomputeVisible();
    },
    clearFilters() { state.filters = {}; emit("filters.changed", {}); recomputeVisible(); },
    whatif(patch) { Object.assign(state.whatif, patch); emit("whatif.changed", { ...state.whatif }); scheduleWhatif(); },
    // ---- tahap D: putusan manusia -> server menulis log anotasi & memicu siklus belajar
    async annotate({ entity, quantity, measurement, artifact, verdict, value_text, note = "", author = "anonim" }) {
      const body = { entity: entity && entity.replace(/^test:/, ""), quantity, measurement, artifact, verdict, value_text, note, author };
      const r = await post("/annotate", body);
      if (r && !r.error) emit("annotation.added", r.annotation);
      return r;
    },
    async refreshQueue() {
      const [q, h] = await Promise.all([get("/queue?k=30", "queue"), get("/history?n=10", "history")]);
      if (q) { state.queue = q; emit("queue.changed", q); }
      if (h) { state.history = h.history; emit("history.changed", h.history); }
    },
    // ---- tahap E: asisten memakai pintu yang sama; aksi UI-nya dijalankan sebagai pelaku "assistant"
    async ask({ question, mode = "auto" }) {
      const history = state.chat.slice(-6).map((c) => ({ q: c.q, a: c.a }));
      const turn = { q: question, a: null, pending: true };
      state.chat.push(turn); emit("chat.changed", state.chat);
      const r = await post("/ask", { question, mode, history, state: snapshot() });
      Object.assign(turn, r && !r.error
        ? { a: r.answer, mode: r.mode, note: r.note, citations: r.citations, tool_calls: r.tool_calls,
            grounding: r.grounding, ui_actions: r.ui_actions, ms: r.ms, pending: false }
        : { a: "(gagal: " + (r?.error || "tidak ada respons") + ")", pending: false, failed: true });
      emit("chat.changed", state.chat);
      for (const u of (r && r.ui_actions) || []) dispatch(u.action, u.args, "assistant");
      return turn;
    },
    async feedback({ index, rating, note = "" }) {
      const c = state.chat[index]; if (!c || c.pending) return;
      c.rating = rating; emit("chat.changed", state.chat);
      await post("/feedback", { question: c.q, answer: c.a, rating, mode: c.mode, tool_calls: c.tool_calls, note });
    },
    async note({ text, author = "anonim" }) {
      if (!state.focus || !text) return;
      const r = await fetchImpl(api + "/note", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity: state.focus.replace(/^test:/, ""), text, author }) }).then((x) => x.json()).catch(() => null);
      if (r && !r.error) { state.notes = [...state.notes, r]; emit("notes.changed", state.notes); }
    },
  };
  const UNDOABLE = new Set(["focus", "select", "filter", "clearFilters", "whatif"]);

  function dispatch(action, args, actor = "user") {
    if (action === "undo") return undo();
    const fn = ACTIONS[action];
    if (!fn) throw new Error(`aksi tidak dikenal: ${action}`);
    if (UNDOABLE.has(action)) { undoStack.push(snapshot()); if (undoStack.length > 100) undoStack.shift(); }
    const entry = { t: new Date().toISOString(), actor, action, args };
    state.trail.push(entry); if (state.trail.length > 500) state.trail.shift();
    emit("trail.changed", entry);
    return fn(args);
  }
  function restore(s) {
    const prevFocus = state.focus;
    Object.assign(state, JSON.parse(JSON.stringify(s)));
    emit("selection.changed", state.selection); emit("filters.changed", { ...state.filters }); recomputeVisible();
    emit("whatif.changed", { ...state.whatif }); scheduleWhatif();
    if (state.focus !== prevFocus) { emit("focus.changed", state.focus); onFocus(state.focus); }
  }
  function undo() {
    const s = undoStack.pop();
    if (!s) return false;
    restore(s);
    const entry = { t: new Date().toISOString(), actor: "user", action: "undo", args: null };
    state.trail.push(entry); emit("trail.changed", entry);
    return true;
  }

  // ---------------------------------------------------------------- berbagi keadaan lewat URL
  function toHash() { return "#s=" + encodeURIComponent(JSON.stringify(snapshot())); }
  function fromHash(hash) {
    const m = /#s=(.*)$/.exec(hash || "");
    if (!m) return false;
    try {
      const s = JSON.parse(decodeURIComponent(m[1]));
      restore({ ...snapshot(), ...s });
      const entry = { t: new Date().toISOString(), actor: "link", action: "restore", args: s };
      state.trail.push(entry); emit("trail.changed", entry);
      return true;
    } catch { return false; }
  }

  // ---------------------------------------------------------------- mulai
  async function start({ hash, poll: doPoll = false } = {}) {
    const [t, a, ev, as] = await Promise.all([get("/tests", "tests"), get("/alerts", "alerts"),
      get("/events?since=0", "events"), get("/assistant_status", "assistant")]);
    if (t) { state.tests = t.tests; emit("tests.loaded", t.tests); recomputeVisible(); }
    if (a) { state.alerts = a; emit("alerts.changed", a); }
    if (ev) state.serverSeq = ev.last;                       // hanya peristiwa BARU yang diproses
    if (as) { state.assistant = as; emit("assistant.status", as); }
    ACTIONS.refreshQueue();
    if (!fromHash(hash)) scheduleWhatif();
    if (doPoll) startPolling();
  }

  return {
    state, on, emit, dispatch, start, undo, toHash, fromHash, poll, startPolling,
    relevanceOf: (id) => state.relevanceMap.get(id) || 0,
    isSelected: (id) => state.selection.includes(id),
    // daftar aksi untuk asisten (tahap E): asisten memakai pintu yang sama dengan manusia
    actions: Object.keys(ACTIONS).concat("undo"),
  };
}
