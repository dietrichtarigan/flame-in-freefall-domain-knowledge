#!/usr/bin/env python3
"""Pencarian paper hibrida untuk asisten: BM25 (leksikal) + LSA (semantik) digabung RRF.

  BM25  SQLite FTS5 atas potongan teks paper, kata kueri digabung OR, DIURUTKAN dengan bm25()
        (Robertson & Zaragoza 2009). Versi lama memakai MATCH tanpa ORDER BY: hasilnya tidak
        berperingkat, dan kata-kata digabung AND sehingga kueri panjang sering kosong.
  LSA   TF-IDF (tf sublinear) -> SVD terpotong k komponen -> kosinus (Deerwester dkk. 1990).
        Menangkap kedekatan makna (sinonim, istilah yang sering muncul bersama) tanpa model
        yang perlu diunduh. Dihitung sekali lalu disimpan di cache (kb/cache/, tidak ikut git).
  RRF   skor(d) = sum_i 1 / (60 + rank_i(d))  (Cormack, Clarke & Büttcher 2009).

Evaluasi (`python scripts/retrieval.py eval`): kueri = judul paper, dicari HANYA di isi teks
(kolom judul tidak dipakai), relevan = potongan mana pun dari paper itu. Ini tolok ukur proksi
"known-item", bukan penilaian relevansi manusia; gunakan untuk membandingkan metode, bukan
sebagai angka mutu mutlak.

  python scripts/retrieval.py build            # bangun ulang cache LSA
  python scripts/retrieval.py search "smoke point coflow microgravity"
  python scripts/retrieval.py eval [--n 300]
"""
import json
import math
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbpaths import gold_db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "kb" / "cache"
K_SVD = 200
RRF_K = 60
STOP = set("""a about above after again against all am an and any are as at be because been before being below between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his how i if in into is it
its itself just me more most my no nor not now of off on once only or other our out over own same she should so some such than that
the their them then there these they this those through to too under until up very was we were what when where which while who whom
why will with you your yang dan di ke dari untuk dengan pada adalah ini itu atau dalam tidak apa bagaimana kenapa mengapa""".split())
_STATE = {}


def toks(s):
    return [w for w in re.findall(r"[a-z][a-z0-9]+", (s or "").lower()) if w not in STOP and len(w) > 2]


def _con():
    return sqlite3.connect(f"file:{gold_db().as_posix()}?mode=ro", uri=True)


def _chunks():
    c = _con()
    rows = c.execute("SELECT rowid, paper_uid, title, page, text FROM paper_search").fetchall()
    return rows


def _links():
    """paper_uid -> (doi, url). DOI dari papers_doi; NTRS -> halaman rekamannya."""
    c = _con()
    out = {}
    for doi, url in c.execute("SELECT doi, doi_url FROM papers_doi"):
        out[f"doi:{doi}"] = (doi, url or f"https://doi.org/{doi}")
    for pid, url in c.execute("SELECT id, record_url FROM papers"):
        out[f"ntrs:{pid}"] = (None, url)
    return out


# ---------------------------------------------------------------- LSA
def build(verbose=True):
    from scipy.sparse import csr_matrix
    from scipy.sparse.linalg import svds
    rows = _chunks()
    docs = [toks(r[4]) for r in rows]
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    n = len(docs)
    vocab = sorted(w for w, c in df.items() if 2 <= c <= 0.5 * n)          # buang kata langka & terlalu umum
    vid = {w: i for i, w in enumerate(vocab)}
    idf = np.array([math.log(n / df[w]) for w in vocab], dtype=np.float32)
    data, ri, ci = [], [], []
    for i, d in enumerate(docs):
        tf = {}
        for w in d:
            if w in vid:
                tf[vid[w]] = tf.get(vid[w], 0) + 1
        for j, c in tf.items():
            ri.append(i), ci.append(j), data.append((1 + math.log(c)) * idf[j])
    X = csr_matrix((np.array(data, dtype=np.float32), (ri, ci)), shape=(n, len(vocab)))
    norms = np.sqrt(X.multiply(X).sum(1)).A1 + 1e-9
    X = csr_matrix(X.multiply(1 / norms[:, None]))
    k = min(K_SVD, min(X.shape) - 1)
    U, S, Vt = svds(X, k=k, random_state=0)
    D = (U * S).astype(np.float32)
    D /= np.linalg.norm(D, axis=1, keepdims=True) + 1e-9
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(CACHE / "lsa_docs.npy", D)
    np.save(CACHE / "lsa_vt.npy", Vt.astype(np.float32))
    np.save(CACHE / "lsa_idf.npy", idf)
    (CACHE / "lsa_meta.json").write_text(json.dumps({"vocab": vocab, "rowids": [r[0] for r in rows], "k": int(k),
                                                     "db_mtime": gold_db().stat().st_mtime}), encoding="utf-8")
    if verbose:
        print(f"LSA: {n} potongan, kosakata {len(vocab)}, k={k} -> {CACHE.relative_to(ROOT)}")


def _lsa():
    meta_p = CACHE / "lsa_meta.json"
    if "lsa" in _STATE:
        return _STATE["lsa"]
    if not meta_p.exists() or json.loads(meta_p.read_text(encoding="utf-8"))["db_mtime"] < gold_db().stat().st_mtime:
        build(verbose=False)
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    st = {"D": np.load(CACHE / "lsa_docs.npy"), "Vt": np.load(CACHE / "lsa_vt.npy"), "idf": np.load(CACHE / "lsa_idf.npy"),
          "vid": {w: i for i, w in enumerate(meta["vocab"])}, "rowids": meta["rowids"]}
    st["pos"] = {r: i for i, r in enumerate(st["rowids"])}
    _STATE["lsa"] = st
    return st


def lsa_rank(query, n=100):
    st = _lsa()
    q = np.zeros(len(st["vid"]), dtype=np.float32)
    tf = {}
    for w in toks(query):
        if w in st["vid"]:
            tf[st["vid"][w]] = tf.get(st["vid"][w], 0) + 1
    if not tf:
        return []
    for j, c in tf.items():
        q[j] = (1 + math.log(c)) * st["idf"][j]
    qv = st["Vt"] @ (q / (np.linalg.norm(q) + 1e-9))
    qv /= np.linalg.norm(qv) + 1e-9
    sims = st["D"] @ qv
    top = np.argsort(-sims)[:n]
    return [(st["rowids"][i], float(sims[i])) for i in top]


# ---------------------------------------------------------------- BM25 (FTS5)
def bm25_rank(query, n=100, text_only=False):
    words = list(dict.fromkeys(toks(query)))[:24]
    if not words:
        return []
    col = "text : " if text_only else ""
    expr = " OR ".join(f'{col}"{w}"' for w in words)
    c = _con()
    try:
        rows = c.execute("SELECT rowid, bm25(paper_search) FROM paper_search WHERE paper_search MATCH ? "
                         "ORDER BY bm25(paper_search) LIMIT ?", (expr, n)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [(r, -s) for r, s in rows]                    # bm25() FTS5: makin kecil makin relevan


def rrf(*rankings, k=RRF_K):
    sc = {}
    for rk in rankings:
        for pos, (rid, _) in enumerate(rk, 1):
            sc[rid] = sc.get(rid, 0.0) + 1.0 / (k + pos)
    return sorted(sc.items(), key=lambda x: -x[1])


# Bawaan BM25: pada evaluasi proksi (analysis/retrieval/eval.json) BM25 berperingkat MRR@10 0,786 vs hibrida 0,667
# vs LSA 0,528 vs cara lama 0,499. Hibrida tetap tersedia (method="hybrid") untuk kueri parafrase.
def search(query, k=8, method="bm25", per_paper=2):
    """Potongan teks berperingkat, maks per_paper potongan per paper. Tiap hasil membawa
    paper_uid, judul, halaman, cuplikan, DOI/tautan, dan skor tiap metode (transparan)."""
    b = bm25_rank(query)
    l = lsa_rank(query) if method in ("hybrid", "lsa") else []
    fused = rrf(b, l) if method == "hybrid" else (b if method == "bm25" else l)
    br = {r: i + 1 for i, (r, _) in enumerate(b)}
    lr = {r: i + 1 for i, (r, _) in enumerate(l)}
    c, links = _con(), _STATE.setdefault("links", _links())
    out, count = [], {}
    qw = set(toks(query))
    for rid, s in fused:
        row = c.execute("SELECT paper_uid, title, page, text FROM paper_search WHERE rowid=?", (rid,)).fetchone()
        if not row:
            continue
        uid, title, page, text = row
        if count.get(uid, 0) >= per_paper:
            continue
        count[uid] = count.get(uid, 0) + 1
        sents = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
        best = max(sents, key=lambda x: len(qw & set(toks(x))), default=text[:300])
        doi, url = links.get(uid, (None, None))
        out.append({"paper_uid": uid, "title": title, "page": page, "snippet": best[:420], "doi": doi, "url": url,
                    "score_rrf": round(s, 4), "rank_bm25": br.get(rid), "rank_lsa": lr.get(rid)})
        if len(out) >= k:
            break
    return out


# ---------------------------------------------------------------- evaluasi proksi
def evaluate(n=300, seed=0):
    import random
    c = _con()
    papers = c.execute("SELECT DISTINCT paper_uid, title FROM paper_search WHERE length(title) > 25").fetchall()
    random.Random(seed).shuffle(papers)
    papers = papers[:n]
    owner = dict(c.execute("SELECT rowid, paper_uid FROM paper_search").fetchall())

    def paper_ranks(rk):
        seen, out = set(), []
        for rid, _ in rk:
            u = owner.get(rid)
            if u not in seen:
                seen.add(u), out.append(u)
        return out

    res = {m: {"mrr10": 0.0, "r1": 0, "r10": 0} for m in ("bm25", "lsa", "hybrid", "fts_lama")}
    for uid, title in papers:
        b = bm25_rank(title, 200, text_only=True)
        l = lsa_rank(title, 200)
        try:                                              # perilaku lama: MATCH apa adanya (AND), tanpa urutan
            words = " ".join(f'text : "{w}"' for w in toks(title)[:12])
            old = [(r[0], 0) for r in c.execute("SELECT rowid FROM paper_search WHERE paper_search MATCH ? LIMIT 200", (words,))]
        except sqlite3.OperationalError:
            old = []
        for m, rk in (("bm25", b), ("lsa", l), ("hybrid", rrf(b, l)), ("fts_lama", old)):
            pr = paper_ranks(rk)[:10]
            if uid in pr:
                p = pr.index(uid) + 1
                res[m]["mrr10"] += 1 / p
                res[m]["r1"] += p == 1
                res[m]["r10"] += 1
    for m in res:
        res[m] = {"MRR@10": round(res[m]["mrr10"] / len(papers), 3), "Recall@1": round(res[m]["r1"] / len(papers), 3),
                  "Recall@10": round(res[m]["r10"] / len(papers), 3)}
    return {"n_queries": len(papers), "protocol": "query = paper title; searched in chunk text only; relevant = any chunk of that paper",
            "results": res}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "build":
        build()
    elif cmd == "search":
        for r in search(" ".join(sys.argv[2:])):
            print(f"{r['score_rrf']:.4f} bm25#{r['rank_bm25']} lsa#{r['rank_lsa']} | {r['title'][:70]} p{r['page']} | {r['doi'] or r['url']}")
    elif cmd == "eval":
        n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 300
        r = evaluate(n)
        out = ROOT / "analysis" / "retrieval"
        out.mkdir(parents=True, exist_ok=True)
        (out / "eval.json").write_text(json.dumps(r, indent=1), encoding="utf-8")
        print(json.dumps(r, indent=1))
    else:
        print(__doc__)
