#!/usr/bin/env python3
"""Lembar periksa manusia untuk bukti video BASS.

  python scripts/proof_review.py              # -> analysis/video_full/review.html
  python scripts/proof_review.py --apply F    # F = review.csv hasil ekspor
                                              # -> measurements_verified.csv

Buka review.html di browser (dari foldernya, supaya gambar proof/ terbaca),
nilai tiap video OK / Salah / Ragu, lalu klik "Unduh review.csv" dan simpan
ke analysis/video_full/. Pilihan tersimpan di browser selama pemeriksaan.

Video diurutkan menurut prioritas: yang paling mungkin salah tampil duluan.
Bendera prioritas hanya petunjuk, bukan putusan.
"""
import argparse
import csv
import html
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VF = ROOT / "analysis" / "video_full"


def flags(r, eps):
    f = []
    name = r["file"].lower()
    if "vlc-record" in name:
        f.append("rekaman layar VLC (potongan)")
    if "blowoff" in name:
        f.append("klip cuplikan")
    if "part-" in name or "part_" in name:
        f.append("potongan Part-n")
    n = int(r["n_episodes"] or 0)
    if n == 0:
        f.append("0 episode: periksa nyala yang terlewat")
    if n >= 4:
        f.append(f"{n} episode: periksa pemisahan")
    lon = float(r["longest_episode_s"] or 0)
    if lon >= 200:
        f.append(f"episode {lon:.0f} s: cek benda terang statis")
    if float(r["lit_frac"] or 0) >= 0.6:
        f.append(f"menyala di {float(r['lit_frac']):.0%} frame")
    if eps and any(float(e["drift_px_per_s"] or 0) > 5 for e in eps):
        f.append("geser sentroid besar")
    return f


def build():
    summ = list(csv.DictReader(open(VF / "summary.csv", encoding="utf-8")))
    eps = defaultdict(list)
    for e in csv.DictReader(open(VF / "episodes.csv", encoding="utf-8")):
        eps[e["file"]].append(e)
    items = []
    for r in summ:
        if not r["proof_png"] or not (VF / r["proof_png"]).exists():
            continue
        e = eps.get(r["file"], [])
        items.append({
            "file": r["file"], "test": r["test_id"], "proof": r["proof_png"],
            "dur": r["duration_s"], "n": r["n_episodes"],
            "burn": r["total_burn_s"], "lit": r["lit_frac"],
            "eps": [[x["t_start_s"], x["t_end_s"], x["duration_s"], x["ending"]]
                    for x in e],
            "flags": flags(r, e),
        })
    items.sort(key=lambda i: (-len(i["flags"]), i["test"]))
    data = json.dumps(items, ensure_ascii=False)
    page = TEMPLATE.replace("/*DATA*/[]", data)
    dest = VF / "review.html"
    dest.write_text(page, encoding="utf-8")
    nf = sum(1 for i in items if i["flags"])
    print(f"{len(items)} lembar bukti, {nf} berbendera. Ditulis: {dest}")


def apply(path):
    rev = {r["file"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}
    meas = list(csv.DictReader(open(VF / "measurements.csv", encoding="utf-8")))
    out, cnt = [], defaultdict(int)
    for m in meas:
        v = rev.get(m["source_video"], {}).get("verdict", "")
        cnt[v or "belum"] += 1
        if v == "ok":
            m["review_note"] = rev[m["source_video"]].get("note", "")
            out.append(m)
    dest = VF / "measurements_verified.csv"
    if out:
        with open(dest, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
            w.writeheader()
            w.writerows(out)
    print("Episode menurut putusan:", dict(cnt))
    print(f"{len(out)} episode lolos -> {dest}" if out else "Tidak ada yang OK.")
    unrev = {m["source_video"] for m in meas} - set(rev)
    if unrev:
        print(f"PERINGATAN: {len(unrev)} video di measurements.csv belum direview.")


TEMPLATE = r"""<!doctype html>
<html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Periksa Bukti Video</title>
<style>
:root{--bg:#f6f6f4;--card:#fff;--ink:#1d1d1b;--mute:#6b6b66;--line:#ddd;
--ok:#1f7a3a;--bad:#b3261e;--maybe:#9a6700;--flag:#fff4d6}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--card:#21211f;--ink:#ecece8;
--mute:#9a9a94;--line:#3a3a37;--ok:#5cc27a;--bad:#ff8a80;--maybe:#e6b450;--flag:#3a3222}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.45 system-ui,sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);
padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:16px;margin:0}#prog{color:var(--mute)}
button{font:inherit;padding:6px 12px;border:1px solid var(--line);background:var(--card);
color:var(--ink);border-radius:6px;cursor:pointer}
main{max-width:1180px;margin:0 auto;padding:16px}
.help{color:var(--mute);margin:0 0 16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin-bottom:14px}
.card.ok{border-left:5px solid var(--ok)}.card.bad{border-left:5px solid var(--bad)}
.card.maybe{border-left:5px solid var(--maybe)}
.top{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}
.name{font-weight:600}.file{color:var(--mute);font-size:12px;word-break:break-all}
img{width:100%;height:auto;display:block;margin:8px 0;background:#000;image-rendering:pixelated;cursor:zoom-in}
img.big{cursor:zoom-out}
.flags span{display:inline-block;background:var(--flag);border-radius:4px;padding:1px 6px;margin:2px 4px 2px 0;font-size:12px}
table{border-collapse:collapse;font-size:12px;margin:4px 0}td,th{padding:2px 8px;text-align:right}
th{color:var(--mute);font-weight:500}
.v{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
.v button.on[data-v=ok]{background:var(--ok);color:#fff}.v button.on[data-v=bad]{background:var(--bad);color:#fff}
.v button.on[data-v=maybe]{background:var(--maybe);color:#fff}
.v input{flex:1;min-width:160px;font:inherit;padding:6px;border:1px solid var(--line);border-radius:6px;
background:var(--bg);color:var(--ink)}
</style></head><body>
<header><h1>Periksa bukti video BASS</h1><span id="prog"></span>
<label><input type="checkbox" id="todo"> hanya yang belum</label>
<button id="dl">Unduh review.csv</button></header>
<main>
<p class="help">Setiap <b>kotak putih</b> harus melingkupi nyala, bukan perangkat keras, teks, pantulan,
atau layar kamera. <b>OK</b> berarti semua kotak benar dan episodenya masuk akal. <b>Salah</b> berarti
ada kotak yang bukan api. <b>Ragu</b> berarti perlu dilihat di videonya. Klik gambar untuk memperbesar.
Urutan: yang paling berbendera tampil duluan.</p>
<div id="list"></div></main>
<script>
const ITEMS=/*DATA*/[];
const KEY="bass-proof-review-v1";
let st={};try{st=JSON.parse(localStorage.getItem(KEY)||"{}")}catch(e){}
const save=()=>{try{localStorage.setItem(KEY,JSON.stringify(st))}catch(e){}};
const esc=s=>String(s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
function render(){
 const only=document.getElementById("todo").checked;
 const L=document.getElementById("list");L.innerHTML="";
 ITEMS.forEach((it,i)=>{
  const s=st[it.file]||{};if(only&&s.v)return;
  const c=document.createElement("div");c.className="card "+(s.v||"");
  const rows=it.eps.map((e,k)=>`<tr><td>${k+1}</td><td>${e[0]}</td><td>${e[1]}</td><td>${e[2]}</td><td style="text-align:left">${esc(e[3])}</td></tr>`).join("");
  c.innerHTML=`<div class="top"><div><div class="name">#${i+1} · uji ${esc(it.test)} · ${it.n} episode · nyala ${it.burn} s dari ${it.dur} s</div>
  <div class="file">${esc(it.file)}</div></div></div>
  <div class="flags">${it.flags.map(f=>`<span>${esc(f)}</span>`).join("")}</div>
  <img loading="lazy" src="${esc(it.proof)}" alt="lembar bukti ${esc(it.test)}">
  ${rows?`<table><tr><th>#</th><th>mulai s</th><th>akhir s</th><th>durasi s</th><th style="text-align:left">akhir</th></tr>${rows}</table>`:""}
  <div class="v">${[["ok","OK"],["bad","Salah"],["maybe","Ragu"]].map(([v,l])=>`<button data-v="${v}" class="${s.v===v?"on":""}">${l}</button>`).join("")}
  <input placeholder="catatan (opsional)" value="${esc(s.note||"")}"></div>`;
  c.querySelector("img").onclick=e=>e.target.classList.toggle("big");
  c.querySelectorAll(".v button").forEach(b=>b.onclick=()=>{
   const cur=st[it.file]||{};cur.v=cur.v===b.dataset.v?"":b.dataset.v;st[it.file]=cur;save();render();});
  c.querySelector("input").onchange=e=>{const cur=st[it.file]||{};cur.note=e.target.value;st[it.file]=cur;save();prog();};
  L.appendChild(c);});
 prog();}
function prog(){const n=ITEMS.filter(i=>(st[i.file]||{}).v).length;
 const b=ITEMS.filter(i=>(st[i.file]||{}).v==="bad").length;
 document.getElementById("prog").textContent=`${n}/${ITEMS.length} diperiksa · ${b} salah`;}
document.getElementById("todo").onchange=render;
document.getElementById("dl").onclick=()=>{
 const q=s=>'"'+String(s??"").replace(/"/g,'""')+'"';
 const lines=["file,test_id,verdict,note"].concat(ITEMS.map(i=>{const s=st[i.file]||{};
  return [i.file,i.test,s.v||"",s.note||""].map(q).join(",")}));
 const a=document.createElement("a");a.href=URL.createObjectURL(new Blob([lines.join("\n")],{type:"text/csv"}));
 a.download="review.csv";a.click();};
render();
</script></body></html>
"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", metavar="REVIEW_CSV")
    a = ap.parse_args()
    sys.exit(apply(a.apply) if a.apply else build())
