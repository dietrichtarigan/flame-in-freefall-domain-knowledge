# Flame in Freefall — domain knowledge

Lapisan hasil dari data pembakaran mikrogravitasi NASA (Physical Sciences
Informatics / PSI, NTRS, dan paper jurnal). Repo ini berisi **data siap analisis
dan skrip pembuatnya** — bukan arsip mentahnya.

Lisensi data PSI: **CC0**. Repo ini proyek independen, tidak didukung NASA.

## Mulai dari mana

Satu berkas yang paling berguna: **`kb/gold/freefall.sqlite`** (83 MB, 9 tabel).
Buka dengan DB Browser for SQLite, DuckDB, atau Python:

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
