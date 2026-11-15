# Flame in Freefall — domain knowledge

Lapisan hasil dari data pembakaran mikrogravitasi NASA (Physical Sciences
Informatics / PSI, NTRS, dan paper jurnal). Repo ini berisi **data siap analisis
dan skrip pembuatnya** — bukan arsip mentahnya.

Lisensi data PSI: **CC0**. Repo ini proyek independen, tidak didukung NASA.

## Mulai dari mana

Satu berkas yang paling berguna: **`kb/gold/freefall.sqlite`** (9 tabel).

Yang tersimpan di repo adalah versi terkompresi **`freefall.sqlite.gz`** (34 MB),
karena berkas aslinya 101 MB dan melewati batas keras GitHub (100 MiB).
Buka dulu satu kali:

```bash
gunzip -k kb/gold/freefall.sqlite.gz      # -k menyimpan berkas .gz-nya
# Windows tanpa gunzip:
python -c "import gzip,shutil; shutil.copyfileobj(gzip.open(r'kb/gold/freefall.sqlite.gz','rb'), open(r'kb/gold/freefall.sqlite','wb'))"
```

Setelah itu buka dengan DB Browser for SQLite, DuckDB, atau Python:

```python
import sqlite3, pandas as pd
con = sqlite3.connect("kb/gold/freefall.sqlite")
pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", con)
```

| Tabel | Baris | Isi |
|---|---|---|
| `tests` | 1.990 | Uji dari tabel PSI, skema seragam lintas 24 investigasi; `raw_json` menyimpan seluruh kolom asli |
| `telemetry` | 943 | Uji ACME hasil tambang telemetri sensor 125 Hz — **tidak ada di tabel NASA** |
| `video_episodes` | 139 | Episode nyala BASS/BASS-II hasil analisis video — **tidak ada di tabel NASA** |
| `investigations` | 24 | Katalog: tujuan, hipotesis, perangkat, DOI |
| `publications` | 352 | Publikasi yang didaftarkan NASA per investigasi |
| `papers`, `papers_doi` | 695 / 295 | Dokumen NTRS dan paper ber-DOI |
| `paper_chunks` + `paper_search` | 7.924 | Teks paper per halaman + indeks pencarian **FTS5** |
| `files` | 16.372 | Manifest seluruh berkas PSI, checksum sha256 |

Contoh pencarian teks penuh:

```sql
SELECT paper_uid, page, snippet(paper_search, 2, '[', ']', '...', 12)
FROM paper_search WHERE paper_search MATCH 'PMMA AND spread' LIMIT 10;
```

## Isi folder

| Folder | Isi |
|---|---|
| `kb/gold/` | Basis data + CSV siap pakai + `data_dictionary.md` |
| `kb/clean/` | Tabel uji per investigasi, kolom asli dipertahankan |
| `kb/manifest/` | Manifest unduhan + checksum (dipakai untuk mengambil ulang data mentah) |
| `analysis/telemetry/` | Hasil tambang telemetri ACME + catatan metode |
| `analysis/video_full/` | Episode nyala dari video + **lembar bukti PNG** |
| `analysis/saffire/`, `analysis/ml/` | Analisis Saffire dan model |
| `scripts/` | Seluruh pipeline, dari pengambilan sampai pembangunan basis data |
| `app/` | Dashboard (buka lewat server lokal, lihat di bawah) |
| `modules/open_flex/` | **Open FLEX**: lab virtual FLEX asli (3D, bukti per angka, baseline hukum D²), proyek mandiri dengan build & ujinya sendiri |
| `docs/` | Spesifikasi, termasuk pipeline model 3D |

## Mengambil ulang data mentah (opsional, ~15,6 GB)

Tidak disertakan di repo. Semua bisa diunduh ulang:

```bash
python scripts/psi_fetch.py --dry-run   # metadata + manifest dulu
python scripts/psi_fetch.py             # berkas <= 10 MB (~6,8 GB)
python scripts/ntrs_fetch.py            # paper NTRS
python scripts/build_kb.py              # bangun ulang freefall.sqlite
```

Butuh Python 3.9+. `build_kb.py` memakai `pymupdf` bila ada (untuk teks PDF);
tanpa itu teks paper dilewati dan sisanya tetap jalan.

## Menjalankan dashboard

Berkas di `app/` memuat `data.json` lewat `fetch`, jadi perlu server lokal:

```bash
cd app && python -m http.server 8000
```

Lalu buka `http://localhost:8000/insight/index.html`.

Lewat server otak (`python scripts/brain.py serve --port 8765`) tersedia juga:

- `http://127.0.0.1:8765/openflex/` — lab Open FLEX. Bisa langsung ke satu uji:
  `/openflex/#test=FLEX-035&tab=lab` (tab: `overview`, `lab`, `physics`, `uq`, `evidence`).
- Dosir uji PSI-69 di mode peneliti (`/app/`) dan kartu FLEX di `/insight/` menautkan ke uji yang sama di lab.
- `GET /openflex_links/test:PSI-69:20CAL08` → uji Open FLEX padanannya.

## Modul Open FLEX (`modules/open_flex/`)

Dibuat terpisah (Phase B, sampai M6.1); detail lengkap di `modules/open_flex/README.md`.
Sumber datanya Tabel IX laporan NASA/TP-2015-216046 (276 uji), bukan tabel PSI-69.

```bash
python3 -I modules/open_flex/tools/build_app.py        # bangun ulang dist/open_flex_lab.html (deterministik)
python3 -m openflex info                               # dijalankan dari dalam modules/open_flex/
```

- **Pencocokan uji memakai CIR identifier, bukan nomor uji.** Nomor uji di tabel PSI-69 bergeser
  dari nomor Tabel IX mulai FLEX-156 (119 dari 274 baris), mis. `C05M101` = FLEX-158 di laporan
  tetapi 157 di PSI-69. CIR `193F001` tercetak untuk dua uji (FLEX-070 dan FLEX-073); keduanya
  ditampilkan. Dua uji Tabel IX tidak ada di PSI-69: FLEX-216 (`N03H201`) dan FLEX-230 (`H01H103`).
- PDF laporan NASA tidak ikut di repo. Tanpa PDF, build memakai checksum terdaftar di
  `SOURCE_CHECKSUMS.sha256`; uji yang membaca PDF (ekstraktor, kutipan halaman) butuh PDF-nya di
  `modules/open_flex/sources/original/NASA-TP-2015-216046.pdf` (NTRS 20150023456).

## Yang perlu diketahui sebelum memakai angkanya

1. **Telemetri adalah tegangan mentah, bukan satuan SI.** `tc_burner_rise_v`
   adalah kenaikan tegangan termokopel dalam **volt**, bukan derajat Celsius.
   Sah untuk membandingkan antar-uji; tidak sah ditampilkan sebagai suhu.
2. **Deteksi nyala telemetri tervalidasi 93,8%** terhadap kolom `ignited` NASA
   pada 320 uji CFI-G (tebak-mayoritas 81,9%). Kolom `signal_strength = lemah`
   menandai 117 uji bersinyal tipis yang perlu dilihat manual.
3. **Durasi dari video belum terkuantifikasi ketelitiannya.** Hanya satu uji
   (T16) yang benar-benar terekam ulang. Periksa `analysis/video_full/proof/`
   sebelum memakai angkanya.
4. **Nilai kosong berarti tidak dilaporkan, bukan nol.**
5. **Semua data mikrogravitasi.** PSI belum memuat data gravitasi parsial.

Rincian metode dan kegagalan yang tercatat ada di `analysis/*/README.md` —
termasuk pendekatan yang dicoba lalu dibuang beserta alasannya.
