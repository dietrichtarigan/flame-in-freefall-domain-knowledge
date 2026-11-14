#!/usr/bin/env python3
"""Inventaris seluruh workspace: setiap berkas dipetakan ke kategori, isi, dan skrip pembuatnya.

Tujuannya pertanggungjawaban: tidak boleh ada berkas yang tidak diketahui asal dan gunanya.
Berkas yang tidak cocok dengan aturan mana pun dilaporkan sebagai TIDAK TERDOKUMENTASI dan
skrip keluar dengan kode 1, sehingga celah dokumentasi langsung ketahuan.

Data mentah NASA (kb/raw/, ribuan berkas) tidak dicantumkan satu per satu; ringkasannya dihitung
dari manifest (kb/manifest/psi_files.csv) dan dari isi folder.

Keluaran (dipakai docs/laporan/workspace.tex):
  docs/laporan/data/inventaris.csv      satu baris per berkas
  docs/laporan/data/tab_inventaris.tex  tabel longtable, dikelompokkan per folder
  docs/laporan/data/tab_psi.tex         ringkasan data mentah PSI per investigasi
  docs/laporan/data/angka.tex           makro angka kunci yang dihitung langsung dari data

  py -3 scripts/workspace_inventory.py
"""
import csv
import fnmatch
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "laporan" / "data"

# Bagian yang diringkas, bukan didaftar per berkas.
SUMMARIZED = ["kb/raw/psi/files/", "kb/raw/ntrs/", "kb/raw/papers/", "arsip/", "docs/laporan/build/"]
SKIP_PARTS = {"__pycache__", ".claude", ".git"}

# (pola glob, kategori, isi, pembuat, kelompokkan?)  -- aturan pertama yang cocok dipakai.
R = [
    # ---------- akar & konfigurasi
    ("README.md", "dokumentasi", "Pengantar workspace dan cara menjalankan pipeline", "ditulis tangan", 0),
    (".gitignore", "konfigurasi", "Daftar berkas yang tidak boleh masuk git (mis. .env berisi kunci API)", "ditulis tangan", 0),
    (".env.example", "konfigurasi", "Contoh isi .env untuk mode Claude (tanpa kunci asli)", "ditulis tangan", 0),
    (".env", "konfigurasi", "Kunci API pribadi; tidak pernah dibaca selain baris ANTHROPIC_*", "pengguna", 0),
    # ---------- data mentah: metadata
    ("kb/raw/psi/catalog.json", "data mentah", "Katalog seluruh investigasi PSI (133 investigasi, semua bidang)", "psi_fetch.py", 0),
    ("kb/raw/psi/investigations/*.json", "data mentah", "Metadata lengkap satu investigasi PSI: tujuan, hipotesis, daftar berkas, publikasi", "psi_fetch.py", 1),
    # ---------- manifest
    ("kb/manifest/psi_files.csv", "manifest", "Semua berkas PSI terdaftar + status unduh + sha256 + path lokal", "psi_fetch.py", 0),
    ("kb/manifest/psi_publications.json", "manifest", "Publikasi dan DOI per investigasi PSI", "psi_fetch.py", 0),
    ("kb/manifest/ntrs_papers.csv", "manifest", "Dokumen NTRS yang diunduh, dengan tag eksperimen dan status PDF/teks", "ntrs_fetch.py", 0),
    ("kb/manifest/ntrs_offtopic.csv", "manifest", "Dokumen NTRS yang dikeluarkan karena tidak membahas pembakaran (filter kepadatan istilah)", "ntrs_relevance.py", 0),
    ("kb/manifest/doi_list.csv", "manifest", "Daftar DOI masukan untuk pengambil paper (dari publikasi PSI dan NTRS)", "build_kb.py / disusun tangan", 0),
    ("kb/manifest/papers_doi.csv", "manifest", "Metadata paper ber-DOI dari OpenAlex: judul, abstrak, status akses dan PDF", "papers_fetch.py, integrate_*_papers.py", 0),
    ("kb/manifest/paid_papers.csv", "manifest", "Paper berbayar yang masih harus diambil lewat akses institusi", "papers_fetch.py", 0),
    ("kb/manifest/zip_contents.csv", "manifest", "Isi setiap zip Raw Data (jumlah anggota, ekstensi dominan, ukuran) tanpa mengekstrak", "inventory_zips.py", 0),
    # ---------- lapis bersih & siap pakai
    ("kb/clean/tables/*.csv", "data bersih", "Satu tabel uji PSI per berkas, kolom asli, baris kosong dibuang", "build_kb.py", 1),
    ("kb/clean/PSI-*_Experimental_table_*.csv", "data bersih", "Salinan tabel uji PSI apa adanya dari zip/CSV NASA (sebelum pembersihan)", "build_kb.py", 1),
    ("kb/gold/freefall.sqlite", "data siap pakai", "Basis data utama: tests, investigations, publications, files, papers, paper_chunks, indeks FTS5", "build_kb.py", 0),
    ("kb/gold/tests.csv", "data siap pakai", "Tabel uji berskema seragam (1 baris per uji atau per kampanye)", "build_kb.py", 0),
    ("kb/gold/investigations.csv", "data siap pakai", "Satu baris per investigasi: judul, DOI, platform, tujuan, hipotesis", "build_kb.py", 0),
    ("kb/gold/publications.csv", "data siap pakai", "Publikasi yang didaftarkan NASA per investigasi", "build_kb.py", 0),
    ("kb/gold/paper_chunks.csv", "data siap pakai", "Teks paper dipotong per halaman (DOI) atau per ~3000 karakter (NTRS)", "build_kb.py", 0),
    ("kb/gold/data_dictionary.md", "dokumentasi", "Kamus data lapis gold: arti tiap kolom dan peringatan", "ditulis tangan bersama build_kb.py", 0),
    ("kb/gold/model_params.json", "model", "Koefisien model linear/logistik awal (FLEX K, padam; CFI-G menyala, padam sendiri)", "build_model.py", 0),
    ("kb/gold/model_report.md", "model", "Laporan validasi model awal (validasi acak 5 lipat)", "build_model.py", 0),
    ("kb/gold/sim_data.json", "model", "Data ringkas untuk simulator Freefall Lab", "build_model.py", 0),
    ("kb/gold/brain.sqlite", "data siap pakai", "Graf pengetahuan 'otak': entitas, artefak, pengukuran bertingkat kebenaran, tautan, aturan, kartu model", "build_brain.py", 0),
    ("kb/gold/brain.sqlite.building*", "data siap pakai", "Berkas sementara saat otak dibangun ulang (ditukar atomik)", "build_brain.py", 0),
    ("kb/gold/pipeline_state.json", "status pipeline", "Sidik jari masukan & keluaran tiap langkah pipeline (untuk menentukan langkah basi)", "learn.py", 0),
    ("kb/gold/model_history.jsonl", "status pipeline", "Riwayat ringkasan model setiap siklus belajar", "learn.py", 0),
    ("kb/gold/annotations.jsonl", "anotasi manusia", "Log putusan manusia (event-sourced, hanya ditambah)", "learn.py / dashboard", 0),
    ("kb/gold/cases.jsonl", "anotasi manusia", "Ingatan kasus asisten: pertanyaan, jawaban, penilaian pengguna", "assistant.py", 0),
    ("kb/gold/notes.json*", "anotasi manusia", "Catatan bersama dari dashboard", "brain.py", 0),
    # ---------- analisis: telemetri
    ("analysis/telemetry/acme_telemetry.csv", "analisis turunan", "Satu baris per uji ACME dari 943 rekaman sensor: menyala, waktu nyala/padam, kenaikan termokopel", "telemetry_mine.py", 0),
    ("analysis/telemetry/telemetry_joined.csv", "analisis turunan", "Telemetri yang dipasangkan ke baris tabel NASA (per uji / per hari / tidak ada)", "telemetry_join.py", 0),
    ("analysis/telemetry/telemetry_calibrated.csv", "analisis turunan", "Tekanan PTA dikalibrasi ke kPa dan aliran MFC ke slpm", "telemetry_calibrate.py", 0),
    ("analysis/telemetry/README.md", "dokumentasi", "Metode dan validasi penambangan telemetri ACME", "ditulis tangan", 0),
    ("analysis/telemetry/corridor/corridors.json", "analisis turunan", "Koridor proses (pita persentil per kanal per kelompok uji)", "telemetry_corridor.py", 0),
    ("analysis/telemetry/corridor/anomaly_scores.csv", "analisis turunan", "Skor anomali tiap uji terhadap koridornya", "telemetry_corridor.py", 0),
    ("analysis/telemetry/corridor/top_anomalies.png", "bukti visual", "Kanal uji paling anomali di atas koridornya", "telemetry_corridor.py", 0),
    # ---------- analisis: video BASS
    ("analysis/video_*/summary.csv", "analisis turunan", "Satu baris per video BASS: episode nyala, gerbang adegan", "video_analyze.py", 0),
    ("analysis/video_*/episodes.csv", "analisis turunan", "Satu baris per episode pembakaran dalam video", "video_analyze.py", 0),
    ("analysis/video_*/measurements.csv", "analisis turunan", "Episode video digabung dengan kondisi uji NASA", "video_join.py", 0),
    ("analysis/video_*/measurements_verified.csv", "analisis turunan", "Hanya episode dari video yang lembar buktinya diputus OK oleh manusia", "proof_review.py --apply", 0),
    ("analysis/video_*/review.csv", "anotasi manusia", "Putusan manusia atas lembar bukti video (OK/Salah/Ragu)", "review.html (manusia)", 0),
    ("analysis/video_*/traces/*.csv", "analisis turunan", "Luas dan sentroid nyala per frame untuk satu video", "video_analyze.py", 1),
    ("analysis/video_*/proof/*.png", "bukti visual", "Lembar bukti: montase frame dengan kotak deteksi", "video_analyze.py --proof", 1),
    ("analysis/video_full/review.html", "aplikasi", "Halaman pemeriksaan lembar bukti oleh manusia", "proof_review.py", 0),
    ("analysis/video_pilot/README.md", "dokumentasi", "Metode, kegagalan, dan batas analisis video BASS", "ditulis tangan", 0),
    # ---------- analisis: Saffire
    ("analysis/saffire/spread_rates.json", "analisis turunan", "Laju rambat api Saffire-I/III per kamera: skala, regresi Theil-Sen, selang bootstrap, gerbang mutu", "saffire_spread.py", 0),
    ("analysis/saffire/spread_rates.csv", "analisis turunan", "Ringkasan laju rambat (ujung api & front hangus) + pembanding publikasi", "saffire_spread.py", 0),
    ("analysis/saffire/traces/*.csv", "analisis turunan", "Posisi ujung api / front hangus per frame", "saffire_spread.py", 1),
    ("analysis/saffire/proof/*.png", "bukti visual", "Lembar bukti Saffire: frame berlabel + garis regresi posisi-waktu", "saffire_spread.py", 1),
    # ---------- analisis: statistik
    ("analysis/stats/uq.json", "analisis turunan", "Selang bootstrap cluster per hari dan uji permutasi untuk angka utama", "stats_uq.py", 0),
    ("analysis/stats/uq_report.md", "dokumentasi", "Laporan ketidakpastian angka utama", "stats_uq.py", 0),
    # ---------- analisis: ML
    ("analysis/ml/tabular_results.json", "model", "Metrik semua model tabular (validasi per hari & acak)", "ml_tabular.py", 0),
    ("analysis/ml/tabular_report.md", "dokumentasi", "Perbandingan model tabular dan pelajarannya", "ml_tabular.py", 0),
    ("analysis/ml/tabular_*.log", "log", "Log mentah pelatihan model tabular (cluster quasi09)", "ml_tabular.py", 1),
    ("analysis/ml/telemetry_tensors.npz", "analisis turunan", "Deret telemetri yang diseragamkan menjadi tensor untuk CNN", "ml_telemetry_prep.py", 0),
    ("analysis/ml/telemetry_cnn_ensemble*.pt", "model", "Bobot ansambel CNN 1-D (ResNet) telemetri", "ml_telemetry_dl.py", 1),
    ("analysis/ml/telemetry_dl_results*.json", "model", "Metrik CNN vs aturan vs fitur+GB, oklusi kanal, transfer ke PSI-10/23", "ml_telemetry_dl.py", 1),
    ("analysis/ml/telemetry_predictions*.csv", "model", "Prediksi CNN per uji (menyala, padam sendiri, durasi) + simpangan ansambel", "ml_telemetry_dl.py", 1),
    ("analysis/ml/telemetry_dl.log", "log", "Log pelatihan CNN (CPU)", "ml_telemetry_dl.py", 0),
    ("analysis/ml/dl_gpu_*.log", "log", "Log pelatihan CNN di GPU RTX 3080 (quasi08/09)", "ml_telemetry_dl.py", 1),
    ("analysis/ml/telemetry_gb_predictions.csv", "model", "Prediksi gradient boosting atas fitur telemetri, dilatih ulang dengan label manusia", "ml_labels.py", 0),
    ("analysis/ml/telemetry_gb_card.json", "model", "Kartu model gradient boosting telemetri", "ml_labels.py", 0),
    ("analysis/ml/boundary/boundary.json", "model", "Peta batas menyala/padam (proses Gaussian) + rekomendasi uji berikutnya (fungsi-U)", "ml_boundary.py", 0),
    ("analysis/ml/boundary/*.png", "bukti visual", "Peta peluang dengan titik uji nyata dan kandidat uji berikutnya", "ml_boundary.py", 1),
    ("analysis/ml/symreg_flex.json", "model", "Rumus jarang laju bakar FLEX + front Pareto", "symreg_flex.py", 0),
    ("analysis/ml/symreg_flex.md", "dokumentasi", "Laporan regresi simbolik laju bakar droplet", "symreg_flex.py", 0),
    ("analysis/ml/quantile_burn.json", "model", "Regresi kuantil waktu bakar CFI-G + kalibrasi konformal", "ml_quantile.py", 0),
    # ---------- aplikasi
    ("app/nerve/index.html", "aplikasi", "Dashboard cerdas (tahap F: desain visual di atas tulang & saraf)", "ditulis tangan", 0),
    ("app/nerve/nerve.js", "aplikasi", "Sistem saraf dashboard: satu keadaan bersama, aksi, undo, tautan, polling peristiwa", "ditulis tangan", 0),
    ("app/nerve/nerve.test.mjs", "uji perangkat lunak", "Uji unit sistem saraf (tanpa server)", "ditulis tangan", 0),
    ("app/nerve/nerve.live.mjs", "uji perangkat lunak", "Uji ujung-ke-ujung terhadap server otak sungguhan", "ditulis tangan", 0),
    ("app/nerve/nerve.learn.live.mjs", "uji perangkat lunak", "Uji siklus belajar: anotasi, bangun ulang, ratusan permintaan selama penukaran basis data", "ditulis tangan", 0),
    ("app/nerve/README.md", "dokumentasi", "Kontrak sistem saraf: keadaan, aksi, peristiwa", "ditulis tangan", 0),
    ("app/freefall_lab.html", "aplikasi", "Simulator Freefall Lab generasi pertama (satu berkas, data tertanam)", "build_model.py + lab_template.html", 0),
    ("app/hardware_lab.html", "aplikasi", "Penampil 3D perangkat eksperimen (placeholder skematik)", "ditulis tangan", 0),
    ("app/vendor/*.js", "pustaka pihak ketiga", "three.js (rilis 2022, MIT) beserta pemuat glTF dan OrbitControls untuk hardware_lab.html", "disalin dari three.js (MIT)", 1),
    # ---------- evaluasi
    ("eval/assistant_eval.jsonl", "evaluasi", "Set pengembangan asisten (28 pertanyaan + kriteria lulus)", "ditulis tangan", 0),
    ("eval/assistant_eval_holdout2.jsonl", "evaluasi", "Set hold-out 2 (12 pertanyaan), dibekukan sebelum dijalankan", "ditulis tangan", 0),
    ("eval/assistant_eval_holdout2.sha1", "evaluasi", "Sidik SHA-1 hold-out 2 sebagai bukti tidak diubah", "sha1sum", 0),
    ("eval/*_catatan.md", "evaluasi", "Catatan kejujuran yang ikut ditempel ke laporan evaluasi", "ditulis tangan", 1),
    ("eval/*_report.md", "evaluasi", "Laporan evaluasi asisten per set", "assistant.py eval", 1),
    ("eval/*_results.json", "evaluasi", "Hasil evaluasi rinci per pertanyaan", "assistant.py eval", 1),
    # ---------- dokumentasi
    ("docs/rencana_dashboard_cerdas.md", "dokumentasi", "Rencana arsitektur dashboard cerdas (lapis L0-L5) dan statusnya", "ditulis tangan", 0),
    ("docs/blender_3d_spec.md", "dokumentasi", "Spesifikasi model 3D perangkat eksperimen untuk pemodel", "ditulis tangan", 0),
    ("docs/laporan/workspace.tex", "dokumentasi", "Sumber LaTeX dokumen penjelasan workspace ini", "ditulis tangan", 0),
    ("docs/laporan/workspace.pdf", "dokumentasi", "Dokumen penjelasan workspace (hasil pdflatex)", "pdflatex", 0),
    ("docs/laporan/*.aux", "log", "Berkas bantu pdflatex (dibuat ulang setiap kompilasi)", "pdflatex", 1),
    ("docs/laporan/*.toc", "log", "Berkas bantu pdflatex (dibuat ulang setiap kompilasi)", "pdflatex", 1),
    ("docs/laporan/*.out", "log", "Berkas bantu pdflatex (dibuat ulang setiap kompilasi)", "pdflatex", 1),
    ("docs/laporan/*.log", "log", "Log kompilasi pdflatex", "pdflatex", 1),
    ("docs/laporan/data/*", "dokumentasi", "Tabel dan angka untuk dokumen LaTeX, dihitung dari data", "workspace_inventory.py", 1),
    ("docs/laporan/gambar/*", "bukti visual", "Gambar untuk dokumen LaTeX (salinan bukti visual & tangkapan layar dashboard)", "workspace_inventory.py / tangkapan layar", 1),
    # ---------- log
    ("logs/*.log", "log", "Log jalannya pengunduhan, server, dan pipeline", "berbagai skrip", 1),
    ("logs/*.txt", "log", "Keluaran uji sementara", "berbagai skrip", 1),
    # ---------- rujukan bacaan
    ("supplement/*.pdf", "rujukan bacaan", "Buku rujukan metode (visualisasi, ML ilmiah, statistik, sistem cerdas)", "diberikan pengguna", 1),
    ("arsip/README.md", "dokumentasi", "Daftar isi arsip dan alasan tiap berkas diarsipkan", "ditulis tangan", 0),
    (".notebook/*", "konfigurasi", "Folder kerja ekstensi editor catatan (bukan bagian proyek; dibiarkan)", "ekstensi editor", 1),
]

# Skrip: isi diambil dari baris pertama docstring masing-masing.
SCRIPT_GLOBS = ["scripts/*.py", "scripts/*.html"]


def first_doc_line(p):
    try:
        txt = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if p.suffix == ".html":
        return "Templat HTML simulator Freefall Lab (diisi build_model.py)"
    for q in ('"""', "'''"):
        i = txt.find(q)
        if i >= 0 and i < 400:
            body = txt[i + 3:txt.find(q, i + 3)].strip()
            return body.splitlines()[0].strip() if body else ""
    return ""


def rel(p):
    return p.relative_to(ROOT).as_posix()


def sha(p, n=12):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:n]


def walk():
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or SKIP_PARTS & set(p.parts):
            continue
        r = rel(p)
        if any(r.startswith(s) for s in SUMMARIZED) and r != "arsip/README.md":
            continue
        yield p, r


def classify(r):
    for pat in SCRIPT_GLOBS:
        if fnmatch.fnmatch(r, pat):
            return "skrip", None, "ditulis tangan", 0
    for pat, cat, isi, maker, grp in R:
        if fnmatch.fnmatch(r, pat):
            return cat, isi, maker, (pat if grp else 0)
    return None


def tex(s):
    """Escape LaTeX, dan beri titik putus setelah / _ - . supaya path panjang bisa terlipat."""
    rep = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "%": r"\%", "$": r"\$", "&": r"\&",
           "#": r"\#", "_": r"\_", "^": r"\^{}", "~": r"\~{}"}
    out = []
    for ch in str(s):
        out.append(rep.get(ch, ch))
    return "".join(out)


def tex_path(s):
    t = tex(s)
    for a in ("/", r"\_", "-", "."):
        t = t.replace(a, a + r"\allowbreak{}")
    return r"\texttt{" + t + "}"


def fmt(n):
    return f"{n:,}".replace(",", ".")


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}".replace(".", ",")
        n /= 1024


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, missing = [], []
    for p, r in walk():
        c = classify(r)
        if c is None:
            missing.append(r)
            continue
        cat, isi, maker, grp = c
        if cat == "skrip":
            isi = first_doc_line(p) or "(tanpa docstring)"
        st = p.stat()
        rows.append({"path": r, "bytes": st.st_size, "sha256_12": sha(p) if st.st_size < 3 << 30 else "",
                     "kategori": cat, "isi": isi, "pembuat": maker, "grp": grp})

    with open(OUT / "inventaris.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["path", "bytes", "sha256_12", "kategori", "isi", "pembuat"])
        for x in rows:
            w.writerow([x[k] for k in ("path", "bytes", "sha256_12", "kategori", "isi", "pembuat")])

    # ---- tabel LaTeX: kelompokkan berkas sejenis (traces/proof/log) menjadi satu baris
    groups = defaultdict(list)
    order = []
    for x in rows:
        key = (str(Path(x["path"]).parent.as_posix()), x["grp"]) if x["grp"] else (x["path"], None)
        if key not in groups:
            order.append(key)
        groups[key].append(x)
    by_top = defaultdict(list)
    for key in order:
        g = groups[key]
        top = g[0]["path"].split("/")[0] if "/" in g[0]["path"] else "(akar)"
        by_top[top].append(g)
    lines = []
    for top in sorted(by_top, key=lambda t: (t != "(akar)", t)):
        lines.append(r"\multicolumn{4}{l}{\rule{0pt}{3ex}\textbf{" + tex(top) + r"/}}\\*")
        for g in by_top[top]:
            x = g[0]
            if len(g) > 1:
                pat = Path(x["path"]).parent.as_posix() + "/" + x["grp"].split("/")[-1]
                name = tex_path(pat) + rf" \newline{{\footnotesize ({len(g)} berkas)}}"
            else:
                name = tex_path(x["path"])
            size = human(sum(y["bytes"] for y in g))
            lines.append(f"{name} & {tex(x['kategori'])} & {tex(x['isi'])} \\newline{{\\footnotesize\\itshape {tex(x['pembuat'])}}} & {size}\\\\")
    # Tabel ditulis utuh (bukan hanya baris): \multicolumn tidak boleh jadi token pertama setelah \input di longtable.
    head = (r"\begin{longtable}{@{}>{\raggedright\arraybackslash}p{0.29\linewidth} >{\raggedright\arraybackslash}p{0.14\linewidth} "
            r">{\raggedright\arraybackslash}p{0.40\linewidth} >{\raggedleft\arraybackslash}p{0.08\linewidth}@{}}" "\n"
            r"\toprule Berkas & Kategori & Isi \textit{(pembuat)} & Ukuran\\ \midrule \endfirsthead" "\n"
            r"\toprule Berkas & Kategori & Isi \textit{(pembuat)} & Ukuran\\ \midrule \endhead" "\n"
            r"\bottomrule \endfoot")
    (OUT / "tab_inventaris.tex").write_text(head + "\n" + "\n".join(lines) + "\n\\end{longtable}\n", encoding="utf-8")

    # ---- ringkasan data mentah PSI per investigasi
    man = list(csv.DictReader(open(ROOT / "kb/manifest/psi_files.csv", encoding="utf-8")))
    per = defaultdict(lambda: {"acr": "", "n": 0, "n_disk": 0, "b": 0, "b_disk": 0, "cat": Counter()})
    for m in man:
        d = per[m["accession"]]
        d["acr"] = m["acronym"]
        d["n"] += 1
        d["b"] += int(m["size_bytes"] or 0)
        lp = ROOT / "kb" / Path(m["local_path"].replace("\\", "/")) if m["local_path"] else None
        if lp and lp.exists():
            d["n_disk"] += 1
            d["b_disk"] += lp.stat().st_size
            d["cat"][m["category"]] += 1
    # berkas di disk yang tidak tercatat di manifest (mis. unduhan Saffire bertahap)
    listed = {(ROOT / "kb" / Path(m["local_path"].replace("\\", "/"))).resolve() for m in man if m["local_path"]}
    extra = Counter()
    for p in (ROOT / "kb/raw/psi/files").rglob("*"):
        if p.is_file() and p.resolve() not in listed:
            extra[p.relative_to(ROOT / "kb/raw/psi/files").parts[0]] += 1
    short = {"Raw Data": "mentah", "Analyzed Data": "olahan", "Engineering Documents": "rekayasa", "Reference Data": "rujukan",
             "Presentations": "presentasi", "Science Documents": "sains", "Experimental table": "tabel uji", "Reports": "laporan",
             "Representative Image(s)": "citra", "metadata": "metadata"}
    titles = {r["accession"]: r["title"] for r in csv.DictReader(open(ROOT / "kb/gold/investigations.csv", encoding="utf-8"))}
    psi_lines = []
    tot = Counter()
    for acc in sorted(per, key=lambda a: int(a.split("-")[1])):
        d = per[acc]
        cats = ", ".join(f"{short.get(k, k)} {v}" for k, v in d["cat"].most_common())
        ex = f" (+{extra[acc]} di luar manifest)" if extra.get(acc) else ""
        name = d["acr"] or (titles.get(acc, "")[:34].rstrip() + "...")
        psi_lines.append(f"{acc} & {tex(name)} & {fmt(d['n'])} & {fmt(d['n_disk'])}{ex} & {human(d['b_disk'])} & {tex(cats) or '--'}\\\\")
        tot["n"] += d["n"]; tot["n_disk"] += d["n_disk"]; tot["b_disk"] += d["b_disk"]; tot["b"] += d["b"]
    psi_lines.append(r"\midrule")
    psi_lines.append(f"\\multicolumn{{2}}{{l}}{{\\textbf{{Total}}}} & {fmt(tot['n'])} & {fmt(tot['n_disk'])} & {human(tot['b_disk'])} & terdaftar {human(tot['b'])}\\\\")
    head = (r"\begin{longtable}{@{}l >{\raggedright\arraybackslash}p{0.2\linewidth} r r r >{\raggedright\arraybackslash}p{0.33\linewidth}@{}}" "\n"
            r"\toprule PSI & Investigasi & Terdaftar & Di disk & Ukuran & Kategori di disk\\ \midrule \endfirsthead" "\n"
            r"\toprule PSI & Investigasi & Terdaftar & Di disk & Ukuran & Kategori di disk\\ \midrule \endhead" "\n"
            r"\bottomrule \endfoot")
    (OUT / "tab_psi.tex").write_text(head + "\n" + "\n".join(psi_lines) + "\n\\end{longtable}\n", encoding="utf-8")

    # ---- angka kunci, dihitung dari sumbernya
    A = {}
    st = Counter(m["status"] for m in man)
    A["psiListed"] = tot["n"]; A["psiOnDisk"] = tot["n_disk"]; A["psiOnDiskGB"] = human(tot["b_disk"])
    A["psiInv"] = len(per); A["psiSkippedSel"] = st.get("skipped_not_selected", 0); A["psiTooLarge"] = st.get("skipped_too_large", 0)
    A["psiFailed"] = sum(v for k, v in st.items() if k.startswith("fail") or k in ("not_on_server", "error"))
    A["psiExtra"] = sum(extra.values())
    A["ntrsPdf"] = len(list((ROOT / "kb/raw/ntrs/pdf").glob("*")))
    A["ntrsTxt"] = len(list((ROOT / "kb/raw/ntrs/txt").glob("*")))
    A["ntrsCit"] = len(list((ROOT / "kb/raw/ntrs/citations").glob("*")))
    A["ntrsOff"] = sum(1 for _ in open(ROOT / "kb/manifest/ntrs_offtopic.csv", encoding="utf-8")) - 1
    A["doiPdf"] = len(list((ROOT / "kb/raw/papers/pdf").glob("*.pdf")))
    con = sqlite3.connect(ROOT / "kb/gold/freefall.sqlite")
    q = lambda s: con.execute(s).fetchone()[0]
    A["nTests"] = q("select count(*) from tests"); A["nTestRows"] = q("select count(*) from tests where granularity='test'")
    A["nCampaign"] = q("select count(*) from tests where granularity='campaign'")
    A["nInvGold"] = q("select count(*) from investigations"); A["nPub"] = q("select count(*) from publications")
    A["nPapersNtrs"] = q("select count(*) from papers"); A["nPapersDoi"] = q("select count(*) from papers_doi")
    A["nChunks"] = q("select count(*) from paper_chunks"); A["nTables"] = q("select count(distinct table_name) from tests")
    con.close()
    con = sqlite3.connect(ROOT / "kb/gold/brain.sqlite")
    A["bEntity"] = q("select count(*) from entity"); A["bArtifact"] = q("select count(*) from artifact")
    A["bMeas"] = q("select count(*) from measurement"); A["bLink"] = q("select count(*) from link")
    A["bRule"] = q("select count(*) from rule"); A["bRuleHit"] = q("select count(*) from rule_hit")
    A["bCard"] = q("select count(*) from model_card")
    tiers = dict(con.execute("select tier, count(*) from measurement group by tier").fetchall())
    for k, v in tiers.items():
        A["tier" + "".join(w.capitalize() for w in k.split("_"))] = v
    rule_hits = dict(con.execute("select rule_id, count(*) from rule_hit group by rule_id").fetchall())
    con.close()
    arc = [p for p in (ROOT / "arsip").rglob("*") if p.is_file()]
    A["arsipFiles"] = len(arc); A["arsipSize"] = human(sum(p.stat().st_size for p in arc))
    A["nFiles"] = len(rows); A["nScripts"] = sum(1 for x in rows if x["kategori"] == "skrip")
    with open(OUT / "angka.tex", "w", encoding="utf-8") as f:
        f.write("% Dihasilkan oleh scripts/workspace_inventory.py. Jangan disunting tangan.\n")
        for k, v in A.items():
            v = f"{v:,}".replace(",", ".") if isinstance(v, int) else tex(v)
            f.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")
    (OUT / "rule_hits.json").write_text(json.dumps(rule_hits, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "status_psi.json").write_text(json.dumps(dict(st), ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{len(rows)} berkas terdokumentasi, {len(missing)} TIDAK TERDOKUMENTASI")
    print(json.dumps(A, ensure_ascii=False))
    print("hit aturan:", rule_hits)
    for m in missing:
        print("  TIDAK TERDOKUMENTASI:", m)
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
