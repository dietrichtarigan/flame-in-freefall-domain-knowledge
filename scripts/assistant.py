#!/usr/bin/env python3
"""Tahap E — asisten yang menjawab LEWAT ALAT, bukan dari ingatan model.

Dua mesin, satu set alat (docs/rencana_dashboard_cerdas.md, bagian 4):
  claude   claude-opus-5-5 dengan tool use (loop manual), bila SDK `anthropic` + kredensial ada
  deepseek loop yang SAMA lewat endpoint DeepSeek yang kompatibel Anthropic (LLM_PROVIDER=deepseek,
           DEEPSEEK_API_KEY, DEEPSEEK_MODEL); dipilih dengan LLM_PROVIDER di .env atau lingkungan
  offline  perencana deterministik berbasis pola pertanyaan — tetap jalan tanpa internet di hari-H,
           dan menjadi pembanding saat evaluasi

Aturan yang ditegakkan KODE, bukan hanya prompt:
  - setiap angka di jawaban diperiksa: harus muncul di keluaran alat (grounding); yang tidak
    ditemukan dilaporkan ke UI sebagai 'angka tanpa sumber'
  - sitasi [[m:...]] [[test:...]] [[paper:judul|hlm]] [[model:id]] diubah jadi daftar terstruktur
    lengkap dengan tingkat kebenaran
  - asisten TIDAK punya alat anotasi: verifikasi adalah pekerjaan manusia
  - aksi UI (fokus, pilih, filter, what-if) dikembalikan ke dashboard dan dijalankan lewat
    nerve.dispatch(..., "assistant") — pintu yang sama dengan manusia

  python scripts/assistant.py ask "kenapa 21106G8 dicurigai?"
  python scripts/assistant.py eval [--mode offline|claude|deepseek|both]
"""
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import brain  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CASES = Path(os.environ.get("FREEFALL_CASES", ROOT / "kb" / "gold" / "cases.jsonl"))
MODEL = "claude-opus-5-5"
# Penyedia model bahasa: "anthropic" (bawaan) atau "deepseek". DeepSeek dipanggil lewat endpoint-nya yang
# kompatibel dengan Messages API Anthropic (api-docs.deepseek.com/guides/anthropic_api), jadi loop alat,
# sitasi dan cek grounding yang SAMA dipakai untuk keduanya. Dibaca ulang dari .env saat dipakai.
DEEPSEEK_BASE_URL = "https://api.deepseek.com/anthropic"


def provider():
    _load_env()
    p = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()
    return p if p in ("anthropic", "deepseek") else "anthropic"


def llm_model():
    return os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro") if provider() == "deepseek" else MODEL

# ================================================================ alat
S = lambda: {"type": "string"}
NS = lambda: {"type": ["string", "null"]}
I = lambda: {"type": "integer"}
N = lambda: {"type": "number"}


def tool(name, desc, props):
    return {"name": name, "description": desc, "strict": True,
            "input_schema": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}}


TOOLS = [
    tool("find_tests", "List tests matching filters. Returns compact rows (id, label, investigation, ignited + tier, O2, "
         "pressure, rules hit). Use null for filters you don't need.",
         {"accession": NS(), "ignited": {"type": ["string", "null"], "enum": ["ya", "tidak", None]},
          "rule_or_flag": NS(), "text": NS(), "limit": I()}),
    tool("get_test", "Full dossier of one test: every value with its truth tier (nasa_table, nasa_calibrated, "
         "derived_auto, human_verified, model_prediction), source file, flags, rule hits and contradictions. "
         "Accepts 'PSI-159:21106G8' or just '21106G8'.", {"test": S()}),
    tool("explain_test", "Abductive explanation: ranked hypotheses for why a test looks the way it does, each with "
         "evidence and source (rules, corridor anomaly, series neighbours, operator notes).", {"test": S()}),
    tool("related", "Tests, papers and files most relevant to a test (series, same day, similar conditions).",
         {"test": S(), "k": I()}),
    tool("provenance", "Full provenance chain of one measurement id (m:...): method, source file, model card, rules.",
         {"measurement_id": S()}),
    tool("list_alerts", "Tiered alerts the system raises: kritis (sources disagree), perhatian (likely false "
         "positive, off-corridor), info (weak signal, unverified).",
         {"level": {"type": ["string", "null"], "enum": ["kritis", "perhatian", "info", None]}, "test": NS(), "limit": I()}),
    tool("whatif_cfig", "Model prediction P(ignition) for ACME CFI-G gaseous flames at given conditions, with "
         "uncertainty, nearest real tests and validity range. Refuses outside the tested range.",
         {"config": {"type": "string", "enum": ["normal", "inverse"]},
          "fuel": {"type": "string", "enum": ["ethane", "propane", "butane"]}, "o2": N(), "x_fuel": N()}),
    tool("whatif_flex", "Model prediction P(extinction before burnout) and burning-rate K for FLEX droplets.",
         {"fuel": {"type": "string", "enum": ["heptane", "methanol"]}, "o2": N(), "pressure_kpa": N(), "he": N()}),
    tool("recommend_next_tests", "Active-learning recommendation: most informative next ISS test conditions "
         "(smallest U = |mu|/sigma), only near conditions the hardware has actually run.",
         {"experiment": {"type": "string", "enum": ["cfig", "flex"]}, "k": I()}),
    tool("coverage", "What is NOT known: per investigation, number of tests, tests with any outcome, values by tier.", {}),
    tool("search_papers", "Full-text search in NASA NTRS reports and papers. Returns title, page and snippet.",
         {"query": S(), "k": I()}),
    tool("find_figures", "Original figures (apparatus diagrams, flame photographs, data plots) cropped from NASA reports "
         "and papers, found by their caption and the sentences that cite them. Returns label, caption, page, paper, DOI or "
         "link and an image the dashboard shows under your answer. Use it whenever the question is about an experiment, "
         "its hardware or setup, what a flame looks like, or a plotted trend. Use English keywords.", {"query": S(), "k": I()}),
    tool("model_cards", "All models with per-day validated metrics, validity notes and caveats.", {}),
    tool("uncertainty_stats", "Day-clustered bootstrap confidence intervals and permutation tests.",
         {"topic": {"type": "string", "enum": ["cfig_ign_rate", "cfig_selfext_rate", "flex_K", "telemetry_burn",
                                                "video_duration", "inverse_vs_normal", "corridor_validation", "all"]}}),
    tool("review_queue", "Items whose human verification would change the dashboard most (uncertainty x impact).",
         {"k": I()}),
    # ---- lapis investigasi + lensa skenario (scripts/investigations.py)
    tool("rank_investigations", "Rank the 24 PSI combustion investigations by fire-safety relevance for a habitat scenario. "
         "Returns score with its three components (direct fire-safety link, condition proximity, evidence depth) and the "
         "reason for each. scenario: cabin (21% O2, 101 kPa), surface (Moon/Mars base and rover: >=30% O2, <=70 kPa), "
         "suit (100% O2, 30 kPa), earth. pillar filters to prevention, detection or suppression; null for all.",
         {"scenario": {"type": "string", "enum": ["cabin", "surface", "suit", "earth"]},
          "pillar": {"type": ["string", "null"], "enum": ["prevention", "detection", "suppression", "fundamentals", None]},
          "limit": I()}),
    tool("get_investigation", "Summary card of one investigation: objective, fire-safety pillar, hardware, fuels and sample "
         "geometry, oxygen/pressure/flow ranges, which variables were varied, measured columns, tests and result counts, "
         "and what our own analysis added. Accepts 'PSI-69' or a name such as 'FLEX', 'BASS-II', 'Saffire-III'.",
         {"investigation": S()}),
    tool("compare_investigations", "Side-by-side comparison of two investigations (hardware, fuels, conditions, variables, "
         "evidence) with what is the same and what differs.", {"a": S(), "b": S()}),
    tool("scenario_evidence", "What NASA's microgravity data says for one habitat atmosphere: tests inside the O2 x pressure "
         "band by fuel type, nearest real tests, model predictions at the band centre, knowledge gaps, and the most "
         "informative next tests.", {"scenario": {"type": "string", "enum": ["cabin", "surface", "suit", "earth"]}}),
    tool("ui_action", "Move the dashboard the user is looking at. action: focus (payload: test), select (payload: "
         "list of tests), filter (payload: {dim, value}; dim in accession|ignited|flag|q), whatif (payload: fields), "
         "clearFilters. payload_json is a JSON string.",
         {"action": {"type": "string", "enum": ["focus", "select", "filter", "whatif", "clearFilters"]},
          "payload_json": S()}),
]


def resolve(test):
    """'21106G8' / 'PSI-159 21106 G8' / 'test:PSI-159:21106G8' -> id kanonik, atau galat dengan kandidat."""
    t = (test or "").strip()
    if t.startswith("test:"):
        return t, None
    m = re.match(r"(PSI-\d+)\s*[: ]\s*(.+)", t, re.I)
    if m:
        return brain.canon(f"{m.group(1)}:{m.group(2)}"), None
    lab = re.sub(r"\s+", "", t).upper()
    cands = [r["id"] for r in brain._table().values() if r["label"] == lab]
    if len(cands) == 1:
        return cands[0], None
    return None, {"error": f"uji '{test}' {'ambigu' if cands else 'tidak ditemukan'}", "candidates": cands[:10]}


def _slim_entity(d):
    if "error" in d:
        return d
    ms = []
    for q, lst in d["measurements"].items():
        for m in lst:
            ms.append({"id": m["id"], "quantity": q, "value": m["value"] if m["value"] is not None else m["value_text"],
                       "unit": m["unit"], "tier": m["tier"], "flags": m["flags"], "source": m["source_artifact"] or m["method"][:80]})
    return {"id": d["id"], "label": d["label"], "accession": d["accession"], "attrs": d["attrs"], "measurements": ms,
            "rule_hits": [{"rule": h["rule_id"], "detail": h["detail"]} for h in d["rule_hits"]],
            "contradictions": d["contradictions"]}


def run_tool(name, args, ctx):
    """Satu-satunya jalan asisten menyentuh data. ctx['ui'] mengumpulkan aksi untuk dashboard."""
    a = args or {}
    if name == "find_figures":
        import paper_figures
        res = paper_figures.search(str(a.get("query") or ""), a.get("k") or 4)
        have = {f["id"] for f in ctx.setdefault("figures", [])}
        ctx["figures"] += [f for f in res if f["id"] not in have]
        return {"figures": [{k: f[k] for k in ("label", "page", "caption", "paper", "doi", "url", "score")} for f in res],
                "note": "these figures are shown to the user under your answer; refer to them by label and paper"
                        if res else "no figure caption matches; do not describe figures"}
    if name in ("get_test", "explain_test", "related"):
        e, err = resolve(a.get("test"))
        if err:
            return err
        if name == "get_test":
            return _slim_entity(brain.entity(e))
        if name == "explain_test":
            return brain.explain(e)
        r = brain.relevance(e, max(1, min(int(a.get("k") or 10), 30)))
        if "related" in r:
            r["papers"] = [{k: p[k] for k in ("title", "page", "snippet")} for p in r["papers"]]
        return r
    if name in ("rank_investigations", "get_investigation", "compare_investigations", "scenario_evidence"):
        import investigations as inv
        if name == "rank_investigations":
            return inv.rank(a.get("scenario") or "cabin", a.get("pillar"), a.get("limit") or 8)
        if name == "get_investigation":
            return inv.card(a.get("investigation", ""))
        if name == "compare_investigations":
            return inv.compare(a.get("a", ""), a.get("b", ""))
        return inv.evidence(a.get("scenario") or "surface")
    if name == "find_tests":
        rows = brain.tests(a.get("accession"), a.get("text"))["tests"]
        ig = a.get("ignited")
        if ig:
            rows = [r for r in rows if r["ignited"] is (ig == "ya")]
        f = a.get("rule_or_flag")
        if f:
            rows = [r for r in rows if f in r["rules"] or f in r["flags"] or any(f in x for x in r["rules"])]
        lim = max(1, min(int(a.get("limit") or 20), 100))
        return {"n": len(rows), "tests": [{"id": r["id"], "label": r["label"], "accession": r["accession"],
                                            "ignited": r["ignited"], "ignited_tier": r["ignited_tier"], "o2": r["o2"],
                                            "p_kpa": None if r["p_kpa"] is None else round(r["p_kpa"], 1),
                                            "rules": r["rules"]} for r in rows[:lim]]}
    if name == "provenance":
        return brain.provenance(a.get("measurement_id", ""))
    if name == "list_alerts":
        e = None
        if a.get("test"):
            e, err = resolve(a["test"])
            if err:
                return err
        r = brain.alerts(e, a.get("level") or "info")
        if a.get("level"):
            r["alerts"] = [x for x in r["alerts"] if x["level"] == a["level"]]
        r["alerts"] = r["alerts"][:max(1, min(int(a.get("limit") or 15), 60))]
        return r
    if name == "whatif_cfig":
        return brain.whatif("cfig", config=a["config"], fuel=a["fuel"], o2=a["o2"], x_fuel=a["x_fuel"])
    if name == "whatif_flex":
        return brain.whatif("flex", fuel=a["fuel"], o2=a["o2"], pressure_kpa=a["pressure_kpa"], he=a["he"])
    if name == "recommend_next_tests":
        B = json.loads((ROOT / "analysis/ml/boundary/boundary.json").read_text(encoding="utf-8"))
        key = "cfig_ign" if a["experiment"] == "cfig" else "flex_ext"
        return {"experiment": a["experiment"], "model": f"gp_boundary_{key}", "metrics": B[key]["cv_per_hari"],
                "how": "U = |mu|/sigma kecil = paling tidak pasti; kandidat hanya di sekitar uji nyata",
                "recommendations": B[key]["recommend"][:max(1, min(int(a.get("k") or 5), 12))]}
    if name == "coverage":
        return brain.coverage()
    if name == "search_papers":
        r = brain.search(a["query"], max(1, min(int(a.get("k") or 6), 15)))
        return {"query": a["query"], "papers": r["papers"], "error": r.get("error")}
    if name == "model_cards":
        c = brain.db()
        return {"cards": [{"id": r["id"], "target": r["target"], "method": r["method"], "metrics": json.loads(r["metrics"]),
                           "validity": json.loads(r["validity"]), "caveats": json.loads(r["caveats"])}
                          for r in c.execute("SELECT * FROM model_card")]}
    if name == "uncertainty_stats":
        U = json.loads((ROOT / "analysis/stats/uq.json").read_text(encoding="utf-8"))
        m = {"cfig_ign_rate": ["cfig_ign_rate"], "cfig_selfext_rate": ["cfig_selfext_rate"],
             "flex_K": ["flex_K", "flex_K_heptane_minus_methanol", "flex_K_he_effect_heptane"],
             "telemetry_burn": ["telemetry_burn_median"], "video_duration": ["video_duration_median"],
             "inverse_vs_normal": ["cfig_inverse_minus_normal"], "corridor_validation": ["corridor_vs_nasa_comments"]}
        keys = sum(m.values(), []) if a["topic"] == "all" else m[a["topic"]]
        return {"method": "selang kepercayaan 95 % dari bootstrap cluster per hari uji (4000x); uji permutasi", **{k: U.get(k) for k in keys}}
    if name == "review_queue":
        import learn
        return learn.queue(max(1, min(int(a.get("k") or 10), 40)))
    if name == "ui_action":
        try:
            payload = json.loads(a.get("payload_json") or "null")
        except json.JSONDecodeError:
            return {"error": "payload_json bukan JSON"}
        act = a["action"]
        if act == "focus":
            e, err = resolve(payload if isinstance(payload, str) else (payload or {}).get("test", ""))
            if err:
                return err
            payload = e
        elif act == "select":
            ids = []
            for t in (payload or []):
                e, err = resolve(t)
                if e:
                    ids.append(e)
            payload = {"ids": ids, "mode": "replace"}
        ctx["ui"].append({"action": act, "args": payload})
        return {"ok": True, "queued": {"action": act, "args": payload}}
    return {"error": f"alat tidak dikenal: {name}"}


# ================================================================ sitasi & grounding
CITE = re.compile(r"\[\[(m:[^\]]+|test:[^\]]+|paper:[^\]]+|model:[^\]]+|inv:[^\]]+)\]\]")
NUM = re.compile(r"(?<![\w.])[-−]?\d+(?:[.,]\d+)?(?![\w])")


def _paper_link(title):
    """DOI / tautan sumber untuk judul paper yang disitasi (papers_doi lalu papers NTRS); kosong bila tak dikenal."""
    if not title:
        return {}
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{brain.GOLD.as_posix()}?mode=ro", uri=True)
        t = title.lower()
        r = con.execute("SELECT doi, doi_url FROM papers_doi WHERE lower(title)=? LIMIT 1", (t,)).fetchone()
        if r:
            return {"doi": r[0], "url": r[1] or f"https://doi.org/{r[0]}"}
        r = con.execute("SELECT record_url FROM papers WHERE lower(title)=? LIMIT 1", (t,)).fetchone()
        if r and r[0]:
            return {"url": r[0]}
    except sqlite3.Error:
        pass
    return {}


def citations(text):
    out, seen = [], set()
    c = brain.db()
    for raw in CITE.findall(text):
        if raw in seen:
            continue
        seen.add(raw)
        item = {"ref": raw}
        if raw.startswith("m:"):
            r = c.execute("SELECT entity, quantity, tier, value, value_text, unit FROM measurement WHERE id=?", (raw,)).fetchone()
            item.update({"kind": "measurement", "exists": bool(r)})
            if r:
                item.update({"entity": r["entity"], "quantity": r["quantity"], "tier": r["tier"],
                             "tier_label": brain.TIER_ID[r["tier"]], "value": r["value"] if r["value"] is not None else r["value_text"],
                             "unit": r["unit"]})
        elif raw.startswith("test:"):
            item.update({"kind": "test", "exists": raw in brain._table()})
        elif raw.startswith("model:"):
            r = c.execute("SELECT target FROM model_card WHERE id=?", (raw[6:],)).fetchone()
            item.update({"kind": "model", "exists": bool(r), "target": r["target"] if r else None, "tier": "model_prediction"})
        elif raw.startswith("inv:"):
            r = c.execute("SELECT label FROM entity WHERE id=? AND kind='investigation'", (raw,)).fetchone()
            item.update({"kind": "investigation", "exists": bool(r), "label": r["label"] if r else None})
        else:
            title, _, page = raw[6:].partition("|")
            item.update({"kind": "paper", "title": title.strip(), "page": page.strip() or None, "tier": "paper_claim"})
            item.update(_paper_link(title.strip()))
        out.append(item)
    return out


def _nums(s):
    out = set()
    for x in NUM.findall(s):
        try:
            out.add(float(x.replace("−", "-").replace(",", ".")))
        except ValueError:
            pass
    return out


def grounding(answer, tool_outputs, question=""):
    """Setiap angka di jawaban harus ada (dengan pembulatan yang ditampilkan) di keluaran alat atau pertanyaan.
    Angka di dalam penanda sitasi dan bilangan bulat kecil (<= 10, mis. 'tiga uji') dikecualikan."""
    body = CITE.sub("", answer)
    src = _nums(" ".join(tool_outputs) + " " + question)
    pct_src = {round(v * 100, 6) for v in src}
    bad = []
    for x in NUM.findall(body):
        try:
            v = float(x.replace("−", "-").replace(",", "."))
        except ValueError:
            continue
        if v.is_integer() and abs(v) <= 10:
            continue
        dec = len(x.replace(",", ".").split(".")[1]) if "." in x.replace(",", ".") else 0
        tol = 0.5 * 10 ** (-dec) + 1e-9
        if not any(abs(v - s) <= tol for s in src) and not any(abs(v - s) <= tol for s in pct_src):
            bad.append(x)
    return {"numbers_checked": len(NUM.findall(body)), "ungrounded": bad, "ok": not bad}


# ================================================================ memori kasus
def _tok(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def similar_cases(q, k=2, min_sim=0.35):
    if not CASES.exists():
        return []
    qs = _tok(q)
    out = []
    for l in CASES.read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        c = json.loads(l)
        if c.get("rating") != "baik":
            continue
        t = _tok(c["question"])
        sim = len(qs & t) / max(1, len(qs | t))
        if sim >= min_sim:
            out.append((sim, c))
    out.sort(key=lambda x: -x[0])
    return [c for _, c in out[:k]]


def feedback(question, answer, rating, mode="", tool_calls=None, note=""):
    rec = {"t": datetime.now(timezone.utc).isoformat(), "question": question[:2000], "answer": answer[:6000],
           "rating": "baik" if rating in ("baik", "good", "up", True, 1) else "buruk", "mode": mode,
           "tool_calls": [t["name"] for t in (tool_calls or [])], "note": str(note)[:500]}
    with open(CASES, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ================================================================ mesin Claude
SYSTEM = """You are the analysis assistant of "Flame in Freefall", a dashboard over NASA's microgravity combustion experiments on the ISS (PSI investigations: ACME CFI-G, Flame Design, s-Flame, FLEX droplets, BASS solids, Saffire, ...).

How you work:
- Every fact and every number in your answer must come from a tool result in this conversation. If no tool returned it, do not state it. Do not use background knowledge for numbers.
- Every value has a truth tier. Say it in words when it matters: nasa_table (recorded by NASA), nasa_calibrated (NASA raw signal + validated NASA formula), derived_auto (our script, not yet checked by a human), human_verified, paper_claim, model_prediction (always give its uncertainty). Never present derived_auto or model_prediction as established fact.
- Thermocouple values are raw volts, not temperatures. Never convert them to degrees.
- If a what-if tool says the input is outside the tested range, say the model does not answer there; do not guess.
- When the question is about an experiment, its hardware or setup, how a flame looks, or a plotted trend, also call find_figures and name the figures you rely on (label and paper). Never describe a figure you did not get from find_figures.
- Cite inline with these markers, exactly as the ids appear in tool results: [[m:<measurement id>]] for a value, [[test:<id>]] for a test, [[paper:<title>|<page>]] for a paper, [[model:<card id>]] for a model, [[inv:<PSI accession>]] for an investigation.
- For questions about whole investigations or about a habitat (cabin, Moon/Mars base, rover, spacesuit, Earth) use rank_investigations, get_investigation, compare_investigations and scenario_evidence. Explain a ranking through its three score components; never present the score as a NASA judgement.
- When the user asks to look at, show, open or compare something, also call ui_action so the dashboard moves with you (focus a test, select several, filter, set what-if sliders).
- You cannot verify or annotate data. If something needs a human decision, say so and point to the review queue.
- Write the whole answer in the language of the user's question (English question -> English answer, Indonesian question -> Indonesian answer), even when tool results are in another language. Be concise: a direct answer first, then the evidence. No headings for short answers."""


ENV_FILE = ROOT / ".env"
_AUTH = {"t": 0.0, "ok": None, "why": "", "src": ""}


def _load_env():
    """Baca HANYA baris ANTHROPIC_*, DEEPSEEK_* dan LLM_PROVIDER dari .env di akar repo (tidak menimpa variabel yang sudah ada).
    Nilai kunci tidak pernah dicetak atau dikirim ke log/peristiwa."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if (k.startswith(("ANTHROPIC_", "DEEPSEEK_")) or k == "LLM_PROVIDER") and v and k not in os.environ:
            os.environ[k] = v


def _cred_source():
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "ANTHROPIC_API_KEY"
    if os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return "ANTHROPIC_AUTH_TOKEN"
    if os.environ.get("ANTHROPIC_PROFILE") or (Path.home() / ".config" / "anthropic").exists():
        return "profil ant"
    return ""


def claude_available(verify=True, max_age=600):
    """(siap?, alasan) untuk penyedia yang aktif. Anthropic + verify: panggil models.list() — memverifikasi
    kunci & jaringan TANPA memakai token; hasilnya di-cache max_age detik. DeepSeek: cukup cek kuncinya ada;
    kunci yang salah tertangkap saat bertanya (AuthenticationError -> dijawab luring)."""
    try:
        import anthropic
    except ImportError:
        return False, "paket anthropic belum terpasang (pip install anthropic)"
    if provider() == "deepseek":
        if not os.environ.get("DEEPSEEK_API_KEY"):
            return False, "LLM_PROVIDER=deepseek tapi DEEPSEEK_API_KEY kosong — isi di .env repo atau variabel lingkungan"
        return True, ""
    src = _cred_source()
    if not src:
        return False, f"tidak ada kredensial — isi ANTHROPIC_API_KEY di {ENV_FILE} atau variabel lingkungan"
    if not verify:
        return True, ""
    if _AUTH["ok"] is not None and _AUTH["src"] == src and time.time() - _AUTH["t"] < max_age:
        return _AUTH["ok"], _AUTH["why"]
    try:
        anthropic.Anthropic(max_retries=1, timeout=15.0).models.list(limit=1)
        ok, why = True, ""
    except anthropic.AuthenticationError:
        ok, why = False, f"kredensial dari {src} ditolak (401) — periksa kuncinya"
    except anthropic.PermissionDeniedError:
        ok, why = False, f"kredensial dari {src} tidak punya izin (403)"
    except anthropic.APIConnectionError:
        ok, why = False, "tidak bisa menghubungi API Anthropic (jaringan/proxy)"
    except anthropic.APIStatusError as e:
        ok, why = False, f"API menjawab {e.status_code}"
    except Exception as e:  # noqa: BLE001 — konfigurasi profil rusak, dsb.
        ok, why = False, f"gagal memeriksa kredensial: {type(e).__name__}"
    _AUTH.update(t=time.time(), ok=ok, why=why, src=src)
    return ok, why


def _llm_call():
    """Fungsi pemanggil satu putaran Messages API untuk penyedia aktif (dipakai loop alat di ask_claude)."""
    import anthropic
    if provider() == "deepseek":
        # Kunci & base_url diberikan eksplisit supaya kunci DeepSeek tidak pernah terkirim ke api.anthropic.com
        # (dan ANTHROPIC_BASE_URL/ANTHROPIC_API_KEY di lingkungan tidak ikut terpakai).
        client = anthropic.Anthropic(api_key=os.environ["DEEPSEEK_API_KEY"], base_url=DEEPSEEK_BASE_URL,
                                     max_retries=1, timeout=180.0)
        # Field yang diabaikan/tidak tercantum di endpoint DeepSeek dibuang: strict (alat), cache_control,
        # betas, fallbacks. Kualitas jalur ini diukur dengan evaluasi yang sama, bukan diasumsikan.
        tools = [{k: v for k, v in t.items() if k != "strict"} for t in TOOLS]
        model = llm_model()
        return lambda messages: client.messages.create(
            model=model, max_tokens=16000, system=SYSTEM, tools=tools, messages=messages)
    client = anthropic.Anthropic()
    return lambda messages: client.beta.messages.create(
        model=MODEL, max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",   # rescue on refusal (see claude-api skill)
        output_config={"effort": "medium"},
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        tools=TOOLS, messages=messages)


def ask_claude(question, history, state):
    call = _llm_call()
    ctx = {"ui": []}
    calls, outputs = [], []
    hint = ""
    sc = similar_cases(question)
    if sc:
        hint = "\n\nSimilar past questions the user rated good (reuse the approach, not the numbers):\n" + "\n".join(
            f"- Q: {c['question']}\n  tools used: {', '.join(c['tool_calls'])}" for c in sc)
    st = {k: state.get(k) for k in ("focus", "selection", "filters", "whatif")} if state else {}
    messages = []
    for h in (history or [])[-6:]:
        messages.append({"role": "user", "content": h["q"]})
        messages.append({"role": "assistant", "content": h["a"]})
    messages.append({"role": "user", "content": [
        {"type": "text", "text": f"Dashboard state now: {json.dumps(st, ensure_ascii=False)}{hint}"},
        {"type": "text", "text": question}]})
    final, note = None, None
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    served, fell_back = set(), False
    for _ in range(10):
        resp = call(messages)
        for k in usage:
            usage[k] += getattr(resp.usage, k, 0) or 0
        served.add(resp.model)
        fell_back |= any(b.type == "fallback" for b in resp.content)
        if resp.stop_reason == "refusal":            # seluruh rantai (termasuk fallback) menolak
            return {"answer": "Permintaan ini ditolak oleh model (refusal).", "ui_actions": ctx["ui"], "figures": ctx.get("figures", []), "tool_calls": calls,
                    "outputs": outputs, "model": resp.model, "usage": usage, "note": "refusal"}
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason == "max_tokens":         # jangan jalankan pemanggilan alat yang terpotong
            final, note = resp, "jawaban terpotong (max_tokens)"
            break
        uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not uses:
            final = resp
            break
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for u in uses:                                     # semua hasil dalam SATU pesan user
            t0 = time.time()
            try:
                out = run_tool(u.name, u.input, ctx)
                err = "error" in out if isinstance(out, dict) else False
            except Exception as e:  # noqa: BLE001
                out, err = {"error": repr(e)}, True
            s = json.dumps(out, ensure_ascii=False, default=str)[:14000]
            outputs.append(s)
            calls.append({"name": u.name, "input": u.input, "ms": int((time.time() - t0) * 1000), "error": err})
            results.append({"type": "tool_result", "tool_use_id": u.id, "content": s, **({"is_error": True} if err else {})})
        messages.append({"role": "user", "content": results})
    if final is None:
        note = "berhenti setelah 10 putaran alat tanpa jawaban akhir"
    text = "".join(b.text for b in (final.content if final else []) if b.type == "text")
    if fell_back:
        note = ((note + "; ") if note else "") + f"dijawab model fallback ({', '.join(sorted(served))})"
    return {"answer": text or "(tidak ada jawaban teks)", "ui_actions": ctx["ui"], "figures": ctx.get("figures", []), "tool_calls": calls,
            "outputs": outputs, "model": ", ".join(sorted(served)) or llm_model(), "usage": usage, "note": note}


# ================================================================ mesin luring (deterministik)
FUEL = {"etana": "ethane", "ethane": "ethane", "propana": "propane", "propane": "propane", "butana": "butane",
        "butane": "butane", "heptana": "heptane", "heptane": "heptane", "metanol": "methanol", "methanol": "methanol"}
TEST_RE = re.compile(r"\b(\d{5}\s?[A-Z]\d+[a-z]?)\b")


def _num_after(q, words, pct_ok=True):
    for w in words:
        # akhiran boleh menempel: "oksigennya 35%", "O2-nya 0.3"; frasa Inggris "at", "of"
        m = re.search(rf"{w}[\w-]*\s*(?:=|:|sebesar|of|at)?\s*(\d+(?:[.,]\d+)?)\s*(%)?", q, re.I)
        if m:
            v = float(m.group(1).replace(",", "."))
            return v / 100 if (m.group(2) and pct_ok) or (pct_ok and v > 1 and w.lower() not in ("tekanan", "pressure", "kpa")) else v
    return None


INTENTS = [  # (maksud, pola) — diperiksa berurutan; yang pertama cocok menang
    ("whatif", r"bagaimana (jika|kalau)|what if|seandainya|andaikan|misalkan|simulasi|\bprediksi\b.*\b(o2|oksigen|oxygen|tekanan|kpa|helium|\d)|"
               r"peluang\b.*\b(padam|menyala|nyala)|apakah\b.*\b(menyala|padam)\b.*\b(o2|oksigen|tekanan|kpa)|"
               r"\b(kalau|jika)\b.*\b(o2|oksigen|oxygen)\b"),
    ("recommend", r"berikutnya|selanjutnya|\bnext\b|rekomendasi|layak diuji|paling berguna|sebaiknya (di)?uji|"
                  r"sebaiknya dilakukan|perlu diuji|uji apa lagi"),
    ("conflict", r"bertentangan|kontradiksi|tidak (cocok|sepakat|konsisten|sama)|berbeda (pendapat|hasil)|"
                 r"\bconflict|inconsisten|mismatch|disagree"),
    ("queue", r"verifikasi|antrean|antrian|perlu dicek|periksa dulu|cek dulu|harus (saya|kami|kita) periksa|"
              r"sebagai manusia|\breview\b|perlu diperiksa"),
    ("uncertainty", r"yakin|selang|kepercayaan|confidence|interval|ketidakpastian|signifikan|bootstrap|ci95|margin"),
    ("coverage", r"cakupan|belum (kita )?(di)?ketahui|tidak (kita )?(di)?ketahui|coverage|kosong|celah|\bgap\b|unknown|"
                 r"paling sedikit (hasil|data)|tanpa hasil|kurang data|minim data|belum ada hasil"),
    ("models", r"\bmodel\b|akura(t|si)|\bauc\b|performa|seberapa (bagus|baik|andal)|kartu"),
    ("alerts", r"peringatan|alert|anomali|masalah|kritis"),
]
TEST_EXPLAIN = r"kenapa|mengapa|\bwhy\b|jelaskan|dicurigai|curiga|alasan|janggal|aneh|apa yang terjadi|ada apa"
TEST_RELATED = r"mirip|serupa|similar|relevan|terkait|sejenis|lain yang"


def classify(ql, tests):
    """Maksud pertanyaan. Kode uji mengalahkan kata kunci umum, kecuali pertanyaan what-if."""
    if tests and not re.search(INTENTS[0][1], ql):
        return "test"
    for name, pat in INTENTS:
        if re.search(pat, ql):
            return name
    return "test" if tests else "papers"


def _fmt(v, d=3):
    return "?" if v is None else (f"{v:.{d}f}".rstrip("0").rstrip(".") if isinstance(v, float) else str(v))


def ask_offline(question, history=None, state=None):
    q = question.strip()
    ql = q.lower()
    ctx = {"ui": []}
    calls, outputs = [], []

    def T(name, **args):
        t0 = time.time()
        out = run_tool(name, args, ctx)
        calls.append({"name": name, "input": args, "ms": int((time.time() - t0) * 1000),
                      "error": isinstance(out, dict) and "error" in out})
        outputs.append(json.dumps(out, ensure_ascii=False, default=str))
        return out

    tests = [re.sub(r"\s+", "", t) for t in TEST_RE.findall(q)]
    m = re.search(r"\b(?:uji|test)\s+([A-Z]{1,2}\d{1,3}[a-z]?)\b", q)
    if m:
        tests.append(m.group(1))
    if not tests and state and state.get("focus") and re.search(r"\b(ini|itu|this|tersebut|fokus)\b", ql):
        tests = [state["focus"]]
    parts = []

    intent = classify(ql, tests)

    # --- tingkat investigasi / skenario habitat (lapis baru; menjawab dalam bahasa penanya)
    import investigations as inv
    hi = None if tests else inv.answer(q, T)
    if hi:
        parts += hi["parts"]
        return {"answer": "\n".join(parts), "ui_actions": ctx["ui"], "figures": ctx.get("figures", []), "tool_calls": calls, "outputs": outputs, "model": "offline-planner"}

    # --- what-if
    if intent == "whatif":
        fuel = next((FUEL[w] for w in FUEL if w in ql), None)
        o2 = _num_after(q, ["o2", "oksigen", "oxygen"])
        if fuel in ("heptane", "methanol") or re.search(r"droplet|flex|tetes", ql):
            p = _num_after(q, ["tekanan", "pressure"], pct_ok=False) or 101.3
            he = _num_after(q, ["he", "helium"]) or 0.0
            r = T("whatif_flex", fuel=fuel or "heptane", o2=o2 or 0.21, pressure_kpa=p, he=he)
            if r.get("valid"):
                parts.append(f"Prediksi model untuk droplet {r['input']['fuel']} (O₂ {_fmt(o2 or 0.21)}, {_fmt(p,1)} kPa, He {_fmt(he)}): "
                             f"P(padam sebelum habis) = {_fmt(r['p_extinction'])} (σ laten {_fmt(r['sigma_latent'])}) [[model:gp_boundary_flex_ext]]. "
                             + (f"Laju bakar K ≈ {_fmt(r['K_mm2_s']['value'],4)} mm²/s dari rumus {r['K_mm2_s']['formula']} [[model:symreg_flex_K]]. " if r.get("K_mm2_s") else "")
                             + "Ini prediksi model, bukan pengukuran.")
            else:
                parts.append(f"Model tidak menjawab: {r.get('warning') or r.get('error')} Rentang yang pernah diuji: {json.dumps(r.get('range'))}.")
            T("ui_action", action="whatif", payload_json=json.dumps({"exp": "flex", "fuel": fuel or "heptane", "o2": o2 or 0.21, "pressure_kpa": p, "he": he}))
        else:
            cfg = "inverse" if "inverse" in ql else "normal"
            xf = _num_after(q, ["x_fuel", "xf", "fraksi bahan bakar", "fuel fraction", "bahan bakar"]) or 0.3
            r = T("whatif_cfig", config=cfg, fuel=fuel or "butane", o2=o2 or 0.25, x_fuel=xf)
            if r.get("valid"):
                near = r.get("nearest_tests", [])[:3]
                parts.append(f"Prediksi model untuk nyala {cfg} {fuel or 'butane'} (O₂ {_fmt(o2 or 0.25)}, x_fuel {_fmt(xf)}): "
                             f"P(menyala) = {_fmt(r['p_ignite'])} (σ laten {_fmt(r['sigma_latent'])}) [[model:gp_boundary_cfig_ign]]; "
                             f"AUC model per hari {r['metrics']['gp']['auc']}. Uji nyata terdekat: "
                             + "; ".join(f"O₂ {_fmt(t['o2'])}, x_fuel {_fmt(t['x_fuel'])} → {'menyala' if t['ignited'] else 'tidak'}" for t in near)
                             + ". Ini prediksi model, bukan pengukuran.")
            else:
                parts.append(f"Model tidak menjawab: {r.get('warning') or r.get('error')} Rentang yang pernah diuji: {json.dumps(r.get('range'))}.")
            T("ui_action", action="whatif", payload_json=json.dumps({"exp": "cfig", "config": cfg, "fuel": fuel or "butane", "o2": o2 or 0.25, "x_fuel": xf}))

    # --- rekomendasi uji berikutnya
    elif intent == "recommend":
        exp = "flex" if re.search(r"flex|droplet|tetes|heptan|metanol", ql) else "cfig"
        r = T("recommend_next_tests", experiment=exp, k=5)
        rows = r["recommendations"]
        parts.append(f"Lima kondisi uji ISS berikutnya yang paling informatif untuk {'FLEX' if exp == 'flex' else 'CFI-G'} "
                     f"[[model:gp_boundary_{'flex_ext' if exp == 'flex' else 'cfig_ign'}]] — di sinilah model paling tidak pasti (U kecil), "
                     "dan semuanya dekat kondisi yang pernah dijalankan alat:")
        for x in rows:
            desc = ", ".join(f"{k} {_fmt(v)}" for k, v in x.items() if k not in ("U", "sigma"))
            parts.append(f"- {desc} (U {_fmt(x['U'])}, σ {_fmt(x['sigma'])})")

    # --- peringatan
    elif intent in ("alerts", "conflict"):
        r = T("list_alerts", level="kritis" if intent == "conflict" else None, test=None, limit=8)
        c = r["counts"]
        if intent == "conflict":
            parts.append(f"Ada {c.get('kritis', 0)} peringatan kritis: uji yang tabel NASA-nya berkata lain dari "
                         "hasil telemetri kita. Yang teratas:")
        else:
            parts.append(f"Sistem saat ini memunculkan {c.get('kritis', 0)} peringatan kritis, {c.get('perhatian', 0)} perhatian, "
                         f"dan {c.get('info', 0)} info. Yang teratas:")
        for x in r["alerts"][:6]:
            parts.append(f"- [{x['level']}] {x['label'] or '—'}: {x['title']} — {'; '.join(x['evidence'])}"
                         + (f" [[{x['entity']}]]" if x["entity"] else ""))
        if r["alerts"] and r["alerts"][0]["entity"]:
            T("ui_action", action="focus", payload_json=json.dumps(r["alerts"][0]["entity"]))

    # --- verifikasi
    elif intent == "queue":
        r = T("review_queue", k=6)
        parts.append(f"{r['n']} item menunggu putusan manusia. Yang paling mengubah dashboard bila diputuskan:")
        for x in r["items"]:
            parts.append(f"- {x.get('entity') or x.get('artifact')}: {x['why']} (nilai {x['value']}) — {x['action']}")
        parts.append("Asisten tidak bisa memverifikasi; putusan diberikan lewat tombol OK/Salah/Ragu di dosir.")

    # --- seberapa yakin
    elif intent == "uncertainty":
        topic = ("inverse_vs_normal" if "inverse" in ql else "flex_K" if re.search(r"flex|droplet|laju bakar|\bk\b|heptan|metanol", ql)
                 else "video_duration" if "video" in ql else "cfig_ign_rate")
        r = T("uncertainty_stats", topic=topic)
        if topic == "inverse_vs_normal":
            x = r["cfig_inverse_minus_normal"]
            parts.append(f"Selisih laju menyala inverse − normal = {x['diff']:+.3f}. Uji permutasi biasa memberi p = {x['p_perm']}, "
                         f"tetapi selang bootstrap per hari [{x['ci95_cluster'][0]:+.3f}, {x['ci95_cluster'][1]:+.3f}] masih mencakup nol — "
                         "karena konfigurasi hampir selalu tetap sepanjang satu hari. Kesimpulan jujur: inverse cenderung lebih mudah menyala, belum terbukti.")
        else:
            key = {"flex_K": "flex_K", "video_duration": "video_duration_median", "cfig_ign_rate": "cfig_ign_rate"}[topic]
            d = r[key]
            d = d.get("groups", d) if isinstance(d, dict) else d
            parts.append(f"Selang kepercayaan dari bootstrap per hari uji ({r['method']}):")
            for k, v in list(d.items())[:8]:
                if isinstance(v, dict) and "ci95" in v:
                    parts.append(f"- {k}: {_fmt(v['est'],4)} [{_fmt(v['ci95'][0],4)}, {_fmt(v['ci95'][1],4)}], n {v['n']}, {v['days']} hari")

    # --- cakupan
    elif intent == "coverage":
        r = T("coverage")
        rows = sorted(r.items(), key=lambda kv: kv[1]["tests"] - kv[1]["tests_with_any_outcome"], reverse=True)
        parts.append("Investigasi dengan uji terbanyak yang belum punya hasil apa pun (yang belum kita ketahui):")
        for acc, v in rows[:6]:
            parts.append(f"- {acc}: {v['tests']} uji, {v['tests_with_any_outcome']} punya hasil")

    # --- model
    elif intent == "models":
        r = T("model_cards")
        parts.append("Model yang dipakai dashboard, dengan metrik validasi per hari uji:")
        for cd in r["cards"]:
            parts.append(f"- [[model:{cd['id']}]] {cd['target']}: {json.dumps(cd['metrics'], ensure_ascii=False)}")

    # --- uji tertentu
    elif intent == "test":
        e, err = resolve(tests[0])
        if err:
            T("get_test", test=tests[0])                    # tercatat sebagai pemanggilan alat yang gagal
            parts.append(f"{err['error']}. Kandidat: {', '.join(err['candidates']) or '—'}.")
        else:
            T("ui_action", action="focus", payload_json=json.dumps(e))
            if re.search(TEST_EXPLAIN, ql):
                x = T("explain_test", test=e)
                parts.append(f"Penjelasan untuk [[{e}]] (hipotesis berperingkat, dari aturan dan data — bukan dari model bahasa):")
                for h in x["hipotesis"][:5]:
                    parts.append(f"- {h['hipotesis']} ({h['sumber']}): {'; '.join(h['bukti'][:2])}")
            elif re.search(TEST_RELATED, ql):
                x = T("related", test=e, k=8)
                parts.append(f"Uji paling relevan dengan [[{e}]]:")
                for o in x["related"][:8]:
                    parts.append(f"- [[{o['id']}]] skor {o['score']} ({', '.join(o['why'])})")
            else:
                d = T("get_test", test=e)
                # besaran yang ditanyakan didahulukan
                want = [q_ for kw, q_ in ((r"suhu|temperatur|termokopel|panas", "tc_burner_rise"), (r"tekanan|pressure", "pressure"),
                                          (r"durasi|lama|waktu bakar|burn", "burn"), (r"menyala|ignit", "ignited"),
                                          (r"o2|oksigen", "o2")) if re.search(kw, ql)]
                ms_ = sorted(d["measurements"], key=lambda m_: (not any(w in m_["quantity"] for w in want), brain.TIER_RANK[m_["tier"]]))
                if any("tc_burner_rise" == w for w in want):
                    parts.append("Catatan: termokopel burner hanya tersedia sebagai kenaikan TEGANGAN mentah (volt), BUKAN suhu — "
                                 "kurva kalibrasi NASA untuk kanal ini tidak ada, jadi tidak boleh dikonversi ke derajat.")
                parts.append(f"Ringkasan [[{e}]] ({d['accession']}):")
                for m_ in ms_[:14]:
                    v = m_["value"]
                    parts.append(f"- {m_['quantity']}: {_fmt(v) if isinstance(v, float) else v} {m_['unit']} — {brain.TIER_ID[m_['tier']]} [[{m_['id']}]]"
                                 + (f" ({', '.join(m_['flags'])})" if m_["flags"] else ""))
                for cdx in d["contradictions"]:
                    parts.insert(0, f"Ada kontradiksi antar-sumber: {cdx['detail']}.")

    # --- paper
    else:
        qq = " OR ".join(f'"{w}"' for w in re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}", q) if w.lower() not in
                         ("yang", "apakah", "bagaimana", "tentang", "menurut", "dengan", "untuk", "what", "does", "about", "paper"))[:300]
        r = T("search_papers", query=qq or q, k=5) if qq else {"papers": []}
        if r.get("papers"):
            parts.append("Saya tidak punya alat yang menjawab ini secara langsung; yang paling dekat dari laporan NASA/paper:")
            for p in r["papers"][:5]:
                parts.append(f"- [[paper:{p['title']}|{p['page'] or '-'}]] … {p['snippet']} …")
        else:
            parts.append("Saya tidak menemukan data atau dokumen yang menjawab ini. Coba sebut kode uji (mis. 21106G8), "
                         "investigasi, atau tanyakan 'bagaimana jika O2 … pada butana …', 'uji berikutnya', 'peringatan', 'seberapa yakin'.")
    return {"answer": "\n".join(parts), "ui_actions": ctx["ui"], "figures": ctx.get("figures", []), "tool_calls": calls, "outputs": outputs, "model": "offline-planner"}


# ================================================================ pintu masuk
FIG_Q = re.compile(r"figure|gambar|foto|photo|picture|image|diagram|setup|apparatus|hardware|perangkat|look like|seperti apa|"
                   r"tampilan|plot|grafik|chart", re.I)


def ask(question, history=None, state=None, mode="auto"):
    t0 = time.time()
    avail, why = claude_available()
    # "claude" / "deepseek" / "llm" = pakai model bahasa penyedia aktif (LLM_PROVIDER); label mode = nama penyedia
    want_llm = mode in ("claude", "deepseek", "llm") or (mode == "auto" and avail)
    use = ("deepseek" if provider() == "deepseek" else "claude") if want_llm else "offline"
    note = None
    if use != "offline" and not avail:
        use, note = "offline", f"mode {provider()} tidak tersedia: {why}"
    if use == "offline":
        r = ask_offline(question, history, state)
    else:
        import anthropic
        try:
            r = ask_claude(question, history, state)
        except anthropic.AuthenticationError:
            _AUTH.update(ok=None)
            r, use, note = ask_offline(question, history, state), "offline", "kredensial ditolak saat bertanya; dijawab luring"
        except anthropic.RateLimitError as e:
            ra = e.response.headers.get("retry-after", "?")
            r, use, note = ask_offline(question, history, state), "offline", f"batas laju API (coba lagi {ra} s); dijawab luring"
        except anthropic.APIStatusError as e:
            r, use, note = ask_offline(question, history, state), "offline", f"API galat {e.status_code}; dijawab luring"
        except anthropic.APIConnectionError:
            _AUTH.update(ok=None)
            r, use, note = ask_offline(question, history, state), "offline", "koneksi ke API putus; dijawab luring"
        if use != "offline" and r.get("note"):
            note = r["note"]
    if use == "offline" and not r.get("figures") and FIG_Q.search(question):   # perencana luring: gambar dari caption
        import paper_figures
        figs = paper_figures.search(question, 4)
        if figs:
            r["figures"] = figs
            r["tool_calls"].append({"name": "find_figures", "input": {"query": question}, "ms": 0, "error": False})
    figs = r.setdefault("figures", [])
    if len(figs) > 6:                                  # panel chat: maks 6, utamakan gambar yang disebut di jawaban
        said = lambda f: re.search(rf"\b{re.escape(f['label'])}\b(?![.\d])", r["answer"]) is not None
        r["figures"] = sorted(figs, key=lambda f: (not said(f), -f.get("score", 0)))[:6]
    r["mode"] = use
    r["note"] = note or (None if avail else f"luring: {why}")
    r["citations"] = citations(r["answer"])
    r["grounding"] = grounding(r["answer"], r.pop("outputs", []), question)
    r["ms"] = int((time.time() - t0) * 1000)
    return r


# ================================================================ evaluasi
def run_eval(mode="offline", path="eval/assistant_eval.jsonl"):
    qs = [json.loads(l) for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if l.strip()]
    rows = []
    for q in qs:
        r = ask(q["q"], state=q.get("state"), mode=mode)
        tools = [c["name"] for c in r["tool_calls"]]
        ans = r["answer"].lower()
        res = {"id": q["id"], "q": q["q"], "mode": r["mode"], "ms": r["ms"],
               "tool_ok": any(t in tools for t in q["expect_tools"]),
               "contain_ok": all(s.lower() in ans for s in q.get("must_contain", [])),
               "forbid_ok": not any(s.lower() in ans for s in q.get("must_not_contain", []))
                            and not any(re.search(p, r["answer"], re.I) for p in q.get("must_not_match", [])),
               "ui_ok": (not q.get("expect_ui")) or any(u["action"] == q["expect_ui"] for u in r["ui_actions"]),
               "grounded": r["grounding"]["ok"], "ungrounded": r["grounding"]["ungrounded"],
               "cites_ok": all(c.get("exists", True) for c in r["citations"]), "tools": tools}
        res["pass"] = all(res[k] for k in ("tool_ok", "contain_ok", "forbid_ok", "ui_ok", "grounded", "cites_ok"))
        rows.append(res)
    n = len(rows)
    agg = {k: round(sum(r[k] for r in rows) / n, 3) for k in ("pass", "tool_ok", "contain_ok", "forbid_ok", "ui_ok", "grounded", "cites_ok")}
    agg["ms_median"] = sorted(r["ms"] for r in rows)[n // 2]
    return {"mode": mode, "n": n, "aggregate": agg, "rows": rows}


def main(argv):
    if not argv:
        print(__doc__)
        return 0
    if argv[0] == "ask":
        mode = "auto"
        if "--mode" in argv:
            mode = argv[argv.index("--mode") + 1]
        r = ask(argv[1], mode=mode)
        print(r["answer"])
        print("\n--- mode:", r["mode"], "|", r.get("note") or "", "| alat:", [c["name"] for c in r["tool_calls"]],
              "| UI:", r["ui_actions"], "| grounding:", r["grounding"], "|", r["ms"], "ms")
        return 0
    if argv[0] == "eval":
        modes = ["offline"] if "--mode" not in argv else (["offline", "claude"] if argv[argv.index("--mode") + 1] == "both"
                                                          else [argv[argv.index("--mode") + 1]])
        path = argv[argv.index("--set") + 1] if "--set" in argv else "eval/assistant_eval.jsonl"
        tag = Path(path).stem
        rep = [f"# Evaluasi asisten — {path}", ""]
        out = {}
        for m in modes:
            r = run_eval(m, path)
            out[m] = r
            rep += [f"## mode {m} — {r['n']} pertanyaan", "", "| metrik | nilai |", "|---|---|"]
            rep += [f"| {k} | {v} |" for k, v in r["aggregate"].items()]
            rep += ["", "| id | lulus | alat | isi | UI | grounded | ms | angka tanpa sumber |", "|---|---|---|---|---|---|---|---|"]
            rep += [f"| {x['id']} | {'✔' if x['pass'] else '✘'} | {'✔' if x['tool_ok'] else '✘'} | "
                    f"{'✔' if x['contain_ok'] and x['forbid_ok'] else '✘'} | {'✔' if x['ui_ok'] else '✘'} | "
                    f"{'✔' if x['grounded'] else '✘'} | {x['ms']} | {' '.join(x['ungrounded'])} |" for x in r["rows"]]
            rep.append("")
            print(m, json.dumps(r["aggregate"], ensure_ascii=False))
            for x in r["rows"]:
                if not x["pass"]:
                    print("  GAGAL", x["id"], {k: x[k] for k in ("tool_ok", "contain_ok", "forbid_ok", "ui_ok", "grounded", "cites_ok")},
                          x["ungrounded"], x["tools"])
        note = ROOT / "eval" / f"{tag}_catatan.md"      # catatan kejujuran (mis. hold-out yang sudah terpakai)
        if note.exists():
            txt = note.read_text(encoding="utf-8").strip()
            txt = re.sub(r"\A---\n.*?\n---\s*", "", txt, flags=re.S)   # buang frontmatter yang ditambahkan editor
            rep += ["", txt]
        (ROOT / "eval" / f"{tag}_report.md").write_text("\n".join(rep) + "\n", encoding="utf-8")
        (ROOT / "eval" / f"{tag}_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
