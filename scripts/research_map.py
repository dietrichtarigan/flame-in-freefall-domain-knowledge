#!/usr/bin/env python3
"""Peta riset untuk halaman utama: paper <-> investigasi <-> topik, dengan asal setiap tautan.

Tiga jenis tautan, dipisah jelas karena kekuatan buktinya berbeda:
  listed   NASA PSI mencantumkan paper itu sebagai publikasi investigasi (tabel publications)
  tag      dokumen NTRS diberi tag eksperimen/topik (kolom papers.tags), mis. "BASS", "Droplet"
  similar  paper TANPA tautan di atas dihubungkan ke investigasi yang paling mirip isinya:
           kosinus vektor LSA (rata-rata potongan teksnya, scripts/retrieval.py) terhadap
           rata-rata paper 'listed' investigasi itu; hanya bila kosinus >= SIM_MIN.
           Ini KEMIRIPAN TOPIK, bukan sitasi.

Basis data tidak memuat daftar referensi antar-paper, jadi jaringan sitasi (siapa mengutip siapa)
belum bisa dibuat; peta ini tidak berpura-pura sebaliknya.

Tata letak dihitung sekali (Fruchterman-Reingold, benih tetap) supaya halaman ringan dan bisa
di-host statis.  python scripts/research_map.py  -> app/insight/research_map.json
"""
import json
import math
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kbpaths import gold_db  # noqa: E402
import investigations as inv  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "insight" / "research_map.json"
SIM_MIN = 0.55
TAG_INV = {"BASS": ["PSI-25", "PSI-26"], "Saffire": ["PSI-98", "PSI-99", "PSI-100"], "ACME CLD": ["PSI-21"],
           "SPICE": ["PSI-107"], "FLEX": ["PSI-69", "PSI-68"], "SAME": ["PSI-101", "PSI-102"], "CFI": ["PSI-39"]}
SKIP_TAG = {"CIR", "MSG combustion", "Drop tower"}            # perangkat/fasilitas, bukan topik


def norm_tag(t):
    return t.replace("(short)", "").strip()


def layout(n, edges, seed=7, iters=400):
    rng = np.random.default_rng(seed)
    P = rng.uniform(-1, 1, (n, 2))
    k = 2.2 * math.sqrt(4.0 / n)                     # jarak ideal (luas awal 2x2)
    E = np.array(edges, dtype=int) if edges else np.zeros((0, 2), int)
    W = np.array([w for _, _, w in [(0, 0, 1)]] if False else [1.0] * len(edges))
    t = 0.25
    for it in range(iters):
        d = P[:, None, :] - P[None, :, :]
        dist = np.sqrt((d ** 2).sum(-1)) + 1e-6
        rep = (k * k / dist ** 2)[:, :, None] * d                          # tolak-menolak
        disp = rep.sum(1)
        if len(E):
            de = P[E[:, 0]] - P[E[:, 1]]
            dl = np.sqrt((de ** 2).sum(1)) + 1e-6
            f = (dl / k)[:, None] * de * W[:, None]                        # tarik-menarik sepanjang tautan
            np.add.at(disp, E[:, 0], -f)
            np.add.at(disp, E[:, 1], f)
        disp -= 0.12 * P * np.sqrt((P ** 2).sum(1, keepdims=True))         # tarikan ke pusat: komponen kecil tidak hanyut
        ln = np.sqrt((disp ** 2).sum(1)) + 1e-9
        P += disp / ln[:, None] * np.minimum(ln, t)[:, None]
        t = max(0.003, t * 0.988)
    lo, hi = np.percentile(P, 1, 0), np.percentile(P, 99, 0)       # pencilan tidak boleh menyusutkan seluruh peta
    P = np.clip((P - lo) / (hi - lo + 1e-9), 0, 1)
    return P


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    con = sqlite3.connect(f"file:{gold_db().as_posix()}?mode=ro", uri=True)
    data = inv.build()
    cards = {c["accession"]: c for c in data["investigations"]}
    nodes, idx, edges = [], {}, []

    def add(nid, **kw):
        if nid not in idx:
            idx[nid] = len(nodes)
            nodes.append({"id": nid, **kw})
        return idx[nid]

    for acc, c in cards.items():
        add(f"inv:{acc}", kind="investigation", label=c["name"], acc=acc, pillars=c["pillars"], n_tests=c["n_tests"],
            kind2=c["kind"], url=c["psi_url"])
    # paper ber-DOI
    doi_meta = {d.lower(): (d, t, y, j, u) for d, t, y, j, u in con.execute("SELECT doi, title, year, journal, doi_url FROM papers_doi")}
    has_text = {u for (u,) in con.execute("SELECT DISTINCT paper_uid FROM paper_chunks")}
    for acc, doi in con.execute("SELECT accession, doi FROM publications WHERE doi != ''"):
        m = doi_meta.get(doi.lower())
        if not m or f"inv:{acc}" not in idx:
            continue
        d, t, y, j, u = m
        pi = add(f"doi:{d}", kind="paper", label=t or d, year=y, journal=j, url=u or f"https://doi.org/{d}", doi=d,
                 full_text=f"doi:{d}" in has_text)
        edges.append((pi, idx[f"inv:{acc}"], "listed"))
    for d, (dd, t, y, j, u) in doi_meta.items():                         # paper ber-DOI tanpa tautan PSI
        add(f"doi:{dd}", kind="paper", label=t or dd, year=y, journal=j, url=u or f"https://doi.org/{dd}", doi=dd,
            full_text=f"doi:{dd}" in has_text)
    # dokumen NTRS yang punya teks penuh + tag
    for pid, title, year, tags, url in con.execute("SELECT id, title, year, tags, record_url FROM papers"):
        uid = f"ntrs:{pid}"
        if uid not in has_text:
            continue
        pi = add(uid, kind="paper", label=title or uid, year=year, journal="NASA NTRS", url=url, doi=None, full_text=True)
        for raw in (tags or "").split("|"):
            tg = norm_tag(raw)
            if not tg or tg in SKIP_TAG:
                continue
            if tg in TAG_INV:
                for acc in TAG_INV[tg]:
                    if f"inv:{acc}" in idx:
                        edges.append((pi, idx[f"inv:{acc}"], "tag"))
            elif tg != "SoFIE":
                ti = add(f"topic:{tg}", kind="topic", label=tg)
                edges.append((pi, ti, "tag"))
    # kemiripan topik (LSA) untuk paper yang belum punya tautan
    import retrieval
    st = retrieval._lsa()
    owner = dict(con.execute("SELECT rowid, paper_uid FROM paper_search").fetchall())
    acc_vec = defaultdict(list)
    for rid, i in st["pos"].items():
        acc_vec[owner.get(rid)].append(st["D"][i])
    pvec = {u: (np.mean(v, 0) / (np.linalg.norm(np.mean(v, 0)) + 1e-9)) for u, v in acc_vec.items() if u}
    linked = {a for a, _, _ in edges} | {b for _, b, _ in edges}
    inv_vec = {}
    for a, b, kind in edges:
        if kind == "listed" and nodes[a]["id"] in pvec:
            inv_vec.setdefault(b, []).append(pvec[nodes[a]["id"]])
    inv_vec = {b: np.mean(v, 0) / (np.linalg.norm(np.mean(v, 0)) + 1e-9) for b, v in inv_vec.items() if len(v) >= 2}
    n_sim = 0
    for i, nd in enumerate(nodes):
        if nd["kind"] != "paper" or i in linked or nd["id"] not in pvec or not inv_vec:
            continue
        best = max(inv_vec.items(), key=lambda kv: float(kv[1] @ pvec[nd["id"]]))
        cs = float(best[1] @ pvec[nd["id"]])
        if cs >= SIM_MIN:
            edges.append((i, best[0], "similar"))
            nd["similarity"] = round(cs, 3)
            n_sim += 1
    # buang paper yang tetap tanpa tautan apa pun (tidak bisa ditempatkan dengan jujur)
    deg = defaultdict(int)
    for a, b, _ in edges:
        deg[a] += 1
        deg[b] += 1
    keep = [i for i, nd in enumerate(nodes) if nd["kind"] != "paper" or deg[i] > 0]
    remap = {o: n for n, o in enumerate(keep)}
    nodes2 = [nodes[i] for i in keep]
    edges2 = [(remap[a], remap[b], k) for a, b, k in edges if a in remap and b in remap]
    P = layout(len(nodes2), [(a, b) for a, b, _ in edges2])
    for nd, (x, y) in zip(nodes2, P):
        nd["x"], nd["y"] = round(float(x), 4), round(float(y), 4)
        nd["degree"] = sum(1 for a, b, _ in edges2 if remap.get(idx[nd["id"]]) in (a, b)) if False else None
    deg2 = defaultdict(int)
    for a, b, _ in edges2:
        deg2[a] += 1
        deg2[b] += 1
    for i, nd in enumerate(nodes2):
        nd["degree"] = deg2[i]
    counts = defaultdict(int)
    for _, _, k in edges2:
        counts[k] += 1
    out = {"nodes": nodes2, "edges": [{"s": a, "t": b, "k": k} for a, b, k in edges2],
           "stats": {"papers": sum(1 for n in nodes2 if n["kind"] == "paper"),
                     "papers_without_any_link_dropped": sum(1 for n in nodes if n["kind"] == "paper") - sum(1 for n in nodes2 if n["kind"] == "paper"),
                     "investigations": len(cards), "topics": sum(1 for n in nodes2 if n["kind"] == "topic"),
                     "edges": dict(counts), "similarity_threshold": SIM_MIN},
           "method": {"listed": "NASA PSI lists the paper as a publication of the investigation",
                      "tag": "NASA NTRS record carries this experiment or topic tag",
                      "similar": f"topic similarity only (LSA cosine >= {SIM_MIN} to the investigation's listed papers); not a citation",
                      "not_available": "Reference lists between papers are not in the database, so a citation network is not drawn"}}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(out["stats"], indent=1), "->", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
