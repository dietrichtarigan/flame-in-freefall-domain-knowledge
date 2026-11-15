"""Graf sitasi ilmiah: paper yang kita indeks (teks penuh) -> paper yang mereka sitasi -> akar bersama.

Basis data kita tidak memuat daftar pustaka, jadi daftar referensi diambil dari
Crossref (metadata terbuka, tanpa kunci API). Yang dikirim hanya DOI dan judul
paper; tidak ada data pengguna. (OpenAlex sempat dicoba lebih dulu, tetapi kuota
anonim hariannya per IP habis setelah ~100 permintaan; kunci gratisnya butuh email.)

Lapisan:
  seed  paper di paper_chunks (yang dipakai asisten). Yang ber-DOI dicari langsung;
        sisanya (PDF lokal, laporan NTRS) dicocokkan lewat judul bila hampir identik
  ref   karya yang disitasi seed (lapis 1). Referensi tanpa DOI tetap masuk,
        dikenali dari judul + tahun
  root  "akar": karya yang disitasi oleh banyak ref bersama (lapis 2). Ditelusuri
        hanya dari ref ber-DOI yang disitasi >= 2 seed, supaya ukurannya terkendali

Klaster: TF-IDF (judul + jurnal; untuk seed + abstrak/teks halaman awal) -> SVD
-> k-means, k dipilih dengan silhouette. Tata letak dihitung di sini.

  python scripts/citation_graph.py fetch      # unduh/cache Crossref (bisa dilanjutkan)
  python scripts/citation_graph.py build      # graf + klaster + tata letak -> JSON
  python scripts/citation_graph.py all
Keluaran: analysis/citations/citation_graph.json (+ salinan untuk FLARE+)
"""
from __future__ import annotations

import difflib
import hashlib
import json
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "kb" / "gold" / "freefall.sqlite"
OUT = ROOT / "analysis" / "citations"
CACHE = OUT / "crossref"
API = "https://api.crossref.org"
UA = "flame-in-freefall-citation-graph/1.0 (research prototype)"

ROOT_MIN_SEEDS = 2      # ref ber-DOI yang disitasi >= 2 seed ditelusuri referensinya (lapis akar)
ROOT_MIN_REFS = 3       # karya lapis 2 masuk graf bila disitasi >= 3 ref tersebut


# ------------------------------------------------------------------ Crossref
def _get(url, tries=4):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return {"_missing": True}
            if e.code == 429:
                time.sleep(5 * (i + 1))
                continue
            if i == tries - 1:
                print("  gagal:", url[:110], e)
                return None
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                print("  gagal:", url[:110], e)
                return None
        time.sleep(1.5 * (i + 1))
    return None


def _cache_get(name, url):
    f = CACHE / (re.sub(r"[^A-Za-z0-9._-]", "_", name)[:150] + ".json")
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    d = _get(url)
    if d is not None:
        f.write_text(json.dumps(d), encoding="utf-8")
        time.sleep(0.22)                      # di bawah batas kolam publik Crossref (5 permintaan/detik)
    return d


def _norm(t):
    return re.sub(r"[^a-z0-9 ]", " ", (t or "").lower()).split()


def _year(m):
    for k in ("published", "published-print", "published-online", "issued"):
        dp = (m.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            return dp[0][0]
    return None


def _work(m):
    """Ringkas satu karya Crossref; referensi diubah ke kunci simpul."""
    refs = []
    for r in m.get("reference") or []:
        if r.get("DOI"):
            refs.append({"key": "doi:" + r["DOI"].lower(), "doi": r["DOI"].lower(),
                         "title": r.get("article-title") or r.get("volume-title") or r.get("series-title") or "",
                         "year": int(r["year"][:4]) if str(r.get("year", ""))[:4].isdigit() else None,
                         "journal": r.get("journal-title") or ""})
        else:
            t = r.get("article-title") or r.get("volume-title") or r.get("series-title") or ""
            if len(_norm(t)) >= 3:
                y = int(r["year"][:4]) if str(r.get("year", ""))[:4].isdigit() else None
                key = "t:" + hashlib.sha1((" ".join(_norm(t)) + f"|{y}").encode()).hexdigest()[:14]
                refs.append({"key": key, "doi": None, "title": t, "year": y, "journal": r.get("journal-title") or ""})
    return {"doi": (m.get("DOI") or "").lower() or None, "title": (m.get("title") or [""])[0],
            "year": _year(m), "journal": (m.get("container-title") or [""])[0],
            "cited_by": m.get("is-referenced-by-count"), "refs": refs, "n_refs_listed": m.get("reference-count")}


def _by_doi(doi):
    d = _cache_get("w_" + doi, f"{API}/works/{urllib.parse.quote(doi, safe='/')}")
    if not d or d.get("_missing") or "message" not in d:
        return None
    return _work(d["message"])


def seeds_from_db():
    c = sqlite3.connect(GOLD)
    uids = [r[0] for r in c.execute("SELECT DISTINCT paper_uid FROM paper_chunks")]
    doi_meta = {r[0].lower(): (r[1], r[2]) for r in c.execute("SELECT doi, title, year FROM papers_doi")}
    ntrs = {str(r[0]): (r[1], r[2]) for r in c.execute("SELECT id, title, year FROM papers")}
    out = []
    for u in uids:
        kind, _, key = u.partition(":")
        local = key.startswith("local/")
        doi = key.lower() if kind == "doi" and not local else None
        title, year = (doi_meta.get(doi) if doi else None) or ntrs.get(key) or ntrs.get(u) or (None, None)
        if not title:
            r = c.execute("SELECT text FROM paper_chunks WHERE paper_uid=? ORDER BY page LIMIT 1", (u,)).fetchone()
            title = (r[0] or "").strip().split("\n")[0][:200] if r else ""
        out.append({"uid": u, "doi": doi, "title": title or "", "year": year, "source": "local" if local else kind})
    return out


def fetch():
    CACHE.mkdir(parents=True, exist_ok=True)
    seeds = seeds_from_db()
    print(f"{len(seeds)} paper berteks penuh di indeks")
    matched = {}
    for i, s in enumerate(seeds):
        w = None
        if s["doi"]:
            w = _by_doi(s["doi"])
            if w:
                w["match"] = "doi"
        if not w and len(_norm(s["title"])) >= 4:
            q = urllib.parse.quote(" ".join(_norm(s["title"])[:25]))
            d = _cache_get("q_" + s["uid"], f"{API}/works?query.bibliographic={q}&rows=3&select=DOI,title")
            best, score = None, 0.0
            for it in ((d or {}).get("message") or {}).get("items", []):
                r = difflib.SequenceMatcher(None, " ".join(_norm(s["title"])), " ".join(_norm((it.get("title") or [""])[0]))).ratio()
                if r > score:
                    best, score = it, r
            if best and score >= 0.9:
                w = _by_doi(best["DOI"].lower())
                if w:
                    w["match"] = f"title {score:.2f}"
        if w:
            matched[s["uid"]] = w
        if i % 50 == 0:
            print(f"  seed {i}/{len(seeds)}, cocok {len(matched)}")
    with_refs = sum(1 for w in matched.values() if w["refs"])
    print(f"cocok ke Crossref: {len(matched)} dari {len(seeds)}; {with_refs} punya daftar referensi terbuka")
    # lapis akar: referensi dari ref ber-DOI yang disitasi >= ROOT_MIN_SEEDS seed
    cnt = Counter(r["key"] for w in matched.values() for r in w["refs"])
    hub = sorted(k for k, n in cnt.items() if n >= ROOT_MIN_SEEDS and k.startswith("doi:"))
    print(f"lapis 1: {len(cnt)} karya disitasi; {len(hub)} ref ber-DOI disitasi >= {ROOT_MIN_SEEDS} seed -> ditelusuri")
    hubs = {}
    for i, k in enumerate(hub):
        w = _by_doi(k[4:])
        if w:
            hubs[k] = w
        if i % 100 == 0:
            print(f"  akar {i}/{len(hub)}")
    # judul untuk ref ber-DOI yang tak berjudul di daftar referensi (batch 40 per permintaan)
    titles = {}
    need = sorted({r["doi"] for w in list(matched.values()) + list(hubs.values()) for r in w["refs"] if r["doi"] and not r["title"]})
    for i in range(0, len(need), 40):
        chunk = need[i:i + 40]
        url = (f"{API}/works?filter={','.join('doi:' + urllib.parse.quote(x, safe='/') for x in chunk)}"
               f"&rows=40&select=DOI,title,container-title,published,is-referenced-by-count")
        d = _cache_get(f"meta_{i}_{hashlib.sha1('|'.join(chunk).encode()).hexdigest()[:10]}", url)
        for it in ((d or {}).get("message") or {}).get("items", []):
            titles[it["DOI"].lower()] = {"title": (it.get("title") or [""])[0], "journal": (it.get("container-title") or [""])[0],
                                         "year": _year(it), "cited_by": it.get("is-referenced-by-count")}
        if i // 40 % 10 == 0:
            print(f"  judul {min(i + 40, len(need))}/{len(need)}")
    (OUT / "crossref.json").write_text(json.dumps({"seeds": seeds, "matched": matched, "hubs": hubs, "titles": titles},
                                                  ensure_ascii=False), encoding="utf-8")
    print("tersimpan:", OUT / "crossref.json")


# ------------------------------------------------------------------ graf
def build():
    import numpy as np
    import networkx as nx
    from sklearn.cluster import KMeans
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics import silhouette_score

    d = json.loads((OUT / "crossref.json").read_text(encoding="utf-8"))
    seeds, matched, hubs, titles = d["seeds"], d["matched"], d["hubs"], d["titles"]
    nodes, edges = {}, set()

    def key_of(w):
        return "doi:" + w["doi"] if w.get("doi") else None

    def add(key, layer, title, year, doi, journal, cited_by=None, extra=None):
        if key in nodes:
            n = nodes[key]                     # lengkapi metadata yang kosong
            n["title"] = n["title"] or title
            n["year"] = n["year"] or year
            n["journal"] = n["journal"] or journal
            if cited_by is not None and n["cited_by"] is None:
                n["cited_by"] = cited_by
            return
        nodes[key] = {"id": key, "layer": layer, "title": title or "", "year": year, "doi": doi,
                      "journal": journal or "", "cited_by": cited_by, **(extra or {})}

    seed_keys = {}
    for uid, w in matched.items():
        k = key_of(w) or "seed:" + uid
        seed_keys[uid] = k
        add(k, "seed", w["title"], w["year"], w["doi"], w["journal"], w["cited_by"],
            {"uid": uid, "match": w["match"], "n_refs_listed": w.get("n_refs_listed"), "n_refs_open": len(w["refs"])})
    n_seed = Counter()
    for uid, w in matched.items():
        for r in {r["key"]: r for r in w["refs"]}.values():
            n_seed[r["key"]] += 1
    for uid, w in matched.items():
        for r in w["refs"]:
            t = titles.get(r["doi"] or "", {})
            add(r["key"], "ref", r["title"] or t.get("title", ""), r["year"] or t.get("year"), r["doi"],
                r["journal"] or t.get("journal", ""), t.get("cited_by"))
            if r["key"] != seed_keys[uid]:
                edges.add((seed_keys[uid], r["key"]))
    n_hub = Counter()
    for k, w in hubs.items():
        for r in {r["key"]: r for r in w["refs"]}.values():
            n_hub[r["key"]] += 1
    for k, w in hubs.items():
        if k in nodes and w.get("cited_by") is not None:
            nodes[k]["cited_by"] = w["cited_by"]
        for r in w["refs"]:
            if r["key"] in nodes or n_hub[r["key"]] >= ROOT_MIN_REFS:
                t = titles.get(r["doi"] or "", {})
                add(r["key"], "root", r["title"] or t.get("title", ""), r["year"] or t.get("year"), r["doi"],
                    r["journal"] or t.get("journal", ""), t.get("cited_by"))
                if r["key"] != k:
                    edges.add((k, r["key"]))
    for k, n in nodes.items():
        if n["layer"] == "ref":
            n["n_seeds"] = n_seed[k]
        if n["layer"] == "root":
            n["n_refs"] = n_hub[k]
    # buang simpul tanpa judul sama sekali (tidak bisa dibaca atau diklaster)
    drop = {k for k, n in nodes.items() if not n["title"] and n["layer"] != "seed"}
    nodes = {k: n for k, n in nodes.items() if k not in drop}
    edges = sorted((a, b) for a, b in edges if a in nodes and b in nodes)

    # --- klaster
    c = sqlite3.connect(GOLD)
    abstracts = {r[0].lower(): r[1] or "" for r in c.execute("SELECT doi, abstract FROM papers_doi")}
    ids = list(nodes)
    # Nama jurnal TIDAK dipakai: versi pertama mengelompokkan menurut singkatan
    # jurnal ("Combust. Flame" vs "Combustion and Flame" jadi klaster terpisah).
    # Sebagai gantinya tiap karya membawa judul karya yang menyitasinya (konteks
    # sitasi), sehingga klaster mengikuti topik dan struktur sitasi sekaligus.
    citers = {}
    for a, b in edges:
        citers.setdefault(b, []).append(a)
    docs = []
    for i in ids:
        n = nodes[i]
        ctx = " ".join(nodes[a]["title"] for a in citers.get(i, [])[:8] if a in nodes)
        t = f"{n['title']} {n['title']} {ctx}"
        if n["layer"] == "seed":
            a = abstracts.get((n["doi"] or "").lower(), "")
            if not a:
                r = c.execute("SELECT group_concat(text, ' ') FROM (SELECT text FROM paper_chunks WHERE paper_uid=? ORDER BY page LIMIT 2)",
                              (n["uid"],)).fetchone()
                a = (r[0] or "")[:3000] if r else ""
            t += " " + a[:3000]
        docs.append(t)
    from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
    stop = list(ENGLISH_STOP_WORDS | {"study", "studies", "effect", "effects", "using", "based", "analysis", "new",
                                      "proc", "combust", "inst", "sci", "technol", "journal", "international",
                                      "symposium", "proceedings", "institute", "conference", "paper", "nasa", "report"})
    tf = TfidfVectorizer(stop_words=stop, min_df=3, max_df=0.3, ngram_range=(1, 2), sublinear_tf=True,
                         token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z-]{2,}\b")
    X = tf.fit_transform(docs)
    Z = TruncatedSVD(n_components=min(80, X.shape[1] - 1), random_state=0).fit_transform(X)
    Z = Z / (np.linalg.norm(Z, axis=1, keepdims=True) + 1e-9)
    sample = np.random.RandomState(0).choice(len(ids), min(4000, len(ids)), replace=False)
    best = None
    for k in range(6, 15):
        km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(Z)
        s = silhouette_score(Z[sample], km.labels_[sample])
        print(f"  k={k} silhouette={s:.3f}")
        if best is None or s > best[0]:
            best = (s, k, km)
    sil, k, km = best
    terms = np.array(tf.get_feature_names_out())
    clusters = []
    for ci in range(k):
        members = [j for j, l in enumerate(km.labels_) if l == ci]
        mean = np.asarray(X[members].mean(axis=0)).ravel()
        top = []
        for t in terms[mean.argsort()[::-1]]:     # hindari istilah yang tumpang tindih ("flame", "flame spread")
            if not any(t in x or x in t for x in top):
                top.append(t)
            if len(top) == 4:
                break
        journals = Counter(nodes[ids[j]]["journal"] for j in members if nodes[ids[j]]["journal"]).most_common(2)
        clusters.append({"id": ci, "label": " · ".join(top[:3]), "terms": top, "journals": [j for j, _ in journals],
                         "n": len(members), "n_seed": sum(1 for j in members if nodes[ids[j]]["layer"] == "seed")})
    for j, i in enumerate(ids):
        nodes[i]["cluster"] = int(km.labels_[j])

    # --- tata letak: titik awal di sekitar pusat klaster, lalu pegas pada graf sitasi
    G = nx.Graph()
    G.add_nodes_from(ids)
    G.add_edges_from(edges, weight=1.0)
    ang = {ci: 2 * np.pi * ci / k for ci in range(k)}
    rng = np.random.RandomState(1)
    init = {i: (np.cos(ang[nodes[i]["cluster"]]) + rng.normal(0, 0.3), np.sin(ang[nodes[i]["cluster"]]) + rng.normal(0, 0.3)) for i in ids}
    for ci in range(k):
        G.add_node(f"_c{ci}")
        init[f"_c{ci}"] = (np.cos(ang[ci]), np.sin(ang[ci]))
    for i in ids:
        G.add_edge(i, f"_c{nodes[i]['cluster']}", weight=0.25)
    t0 = time.time()
    pos = nx.spring_layout(G, pos=init, iterations=50, seed=2, k=1.2 / np.sqrt(len(ids)), weight="weight", method="energy"
                           if len(ids) < 3000 else "auto")
    print(f"  tata letak {len(ids)} simpul: {time.time() - t0:.0f} s")
    xs = np.array([pos[i][0] for i in ids])
    ys = np.array([pos[i][1] for i in ids])
    lo_x, hi_x = np.percentile(xs, [0.5, 99.5])
    lo_y, hi_y = np.percentile(ys, [0.5, 99.5])
    xs = np.clip((xs - lo_x) / (hi_x - lo_x), -0.02, 1.02)
    ys = np.clip((ys - lo_y) / (hi_y - lo_y), -0.02, 1.02)
    for j, i in enumerate(ids):
        nodes[i]["x"], nodes[i]["y"] = round(float(xs[j]), 4), round(float(ys[j]), 4)

    lay = Counter(n["layer"] for n in nodes.values())
    index = {i: j for j, i in enumerate(ids)}
    seeds_with_refs = sum(1 for w in matched.values() if w["refs"])
    out = {
        "built": time.strftime("%Y-%m-%d"),
        "stats": {"seeds_indexed": len(seeds), "seeds_matched": len(matched), "seeds_with_refs": seeds_with_refs,
                  "seeds_match_doi": sum(1 for w in matched.values() if w["match"] == "doi"),
                  "refs": lay["ref"], "roots": lay["root"], "edges": len(edges), "k": k, "silhouette": round(float(sil), 3)},
        "method": {
            "source": "Reference lists come from Crossref open metadata",
            "seed": "papers with full text in the assistant's search index, found in Crossref by DOI or by near-identical title (similarity >= 0.9)",
            "ref": "works in a seed's reference list (with or without DOI; without DOI they are matched by title and year)",
            "root": f"works cited by >= {ROOT_MIN_REFS} of the DOI references that >= {ROOT_MIN_SEEDS} seeds share (common intellectual roots)",
            "cluster": f"TF-IDF of each title plus the titles of the works citing it (abstract or first pages for indexed papers), SVD, then k-means; k = {k} chosen by silhouette ({sil:.3f}, i.e. topics overlap)",
            "layout": "force layout on the citation graph with a weak pull to each cluster centre",
            "caveat": f"Only {seeds_with_refs} of {len(seeds)} indexed papers have an open reference list (NASA reports and some publishers deposit none), so a missing link means not catalogued, not not cited"},
        "clusters": clusters,
        "nodes": [nodes[i] for i in ids],
        "edges": [[index[a], index[b]] for a, b in edges],
    }
    p = OUT / "citation_graph.json"
    p.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    for dst in (ROOT / "app" / "flare-src" / "public" / "citation_graph.json", ROOT / "app" / "flare" / "citation_graph.json"):
        if dst.parent.exists():
            dst.write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
    print(json.dumps(out["stats"]), f"-> {p} ({p.stat().st_size // 1024} KB)")
    for cl in clusters:
        print(f"  klaster {cl['id']}: {cl['n']} karya ({cl['n_seed']} seed) - {cl['label']}  [{', '.join(cl['journals'])}]")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("fetch", "all"):
        fetch()
    if cmd in ("build", "all"):
        build()
