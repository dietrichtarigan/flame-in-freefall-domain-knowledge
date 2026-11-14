---
noteId: "6c1feaf0dcd211f193e215b85abd30c6"
tags: []

---

# Kamus data — knowledge base Flame in Freefall

Dibangun oleh `scripts/build_kb.py` dari 22 tabel uji PSI (Combustion Science), 24 metadata
investigasi, dan manifest unduhan. Jalankan ulang skrip itu kapan saja; hasilnya ditimpa.

## Tiga lapis

| Lapis | Lokasi | Isi | Boleh diubah? |
|---|---|---|---|
| Mentah | `kb/raw/` | File asli NASA | Tidak |
| Bersih | `kb/clean/tables/*.csv` | Satu CSV per tabel uji, kolom asli, baris kosong dibuang | Dibangun ulang |
| Siap pakai | `kb/gold/` | Skema seragam + `freefall.sqlite` | Dibangun ulang |

## `kb/gold/freefall.sqlite`

Delapan tabel: `tests`, `investigations`, `publications`, `files`, `papers`, `papers_doi`,
`paper_chunks`, dan indeks pencarian teks penuh `paper_search` (FTS5).

```sql
-- uji bahan padat dengan oksigen di bawah 18%
SELECT test_uid, fuel, o2_mole_frac FROM tests
WHERE fuel_phase = 'solid' AND o2_mole_frac < 0.18;

-- laju bakar rata-rata droplet per bahan bakar dan pengencer
SELECT fuel, diluent, COUNT(*), ROUND(AVG(metric_value), 2) FROM tests
WHERE accession = 'PSI-69' AND metric_value IS NOT NULL GROUP BY 1, 2;

-- cari di dalam isi semua paper (NTRS + DOI), dapat judul & nomor halaman
SELECT paper_uid, title, page, snippet(paper_search, 2, '[', ']', '...', 12)
FROM paper_search WHERE paper_search MATCH 'PMMA AND spread' LIMIT 10;
```

## Tabel `tests` (1.990 baris)

Satu baris per uji (`granularity = 'test'`, 1.871 baris) atau per ringkasan hari/bahan bakar
(`granularity = 'campaign'`, 119 baris). **Nilai kosong berarti tidak dilaporkan di tabel sumber,
bukan nol.**

| Kolom | Arti | Satuan / nilai |
|---|---|---|
| `test_uid` | Kunci unik: `accession:tabel:baris` | teks |
| `accession`, `acronym` | Investigasi PSI | mis. `PSI-69`, `FLEX` |
| `table_name`, `source_file`, `source_row` | Jejak ke sumber: file dan baris data ke-n (1 = baris pertama setelah header) | |
| `granularity` | `test` atau `campaign` | |
| `test_id` | ID uji menurut NASA | teks |
| `date` | Tanggal seperti tertulis di sumber | teks, format bervariasi |
| `fuel_phase` | `solid`, `droplet`, `gas`, `smoke` | |
| `fuel` | Bahan bakar atau material sampel, seperti tertulis | teks |
| `configuration` | Konfigurasi uji (nyala normal/inversi, serat, ukuran sampel) | teks |
| `o2_mole_frac` | Fraksi mol oksigen awal | 0–1 |
| `o2_final_mole_frac` | Fraksi mol oksigen akhir | 0–1 |
| `pressure_kpa` | Tekanan | kPa (dikonversi dari mmHg, atm, atau bar) |
| `diluent`, `diluent_mole_frac` | Gas pengencer utama dan fraksinya | `N2`, `CO2`, `He` |
| `flow_cm_s`, `flow_direction` | Kecepatan dan arah aliran | cm/s; `concurrent`, `opposed`, `co-flow` |
| `gravity` | Dari jenis proyek PSI | semua `microgravity` di tabel ini |
| `ignited` | Apakah menyala (bila dilaporkan) | `yes` / `no` |
| `outcome` | Akhir uji seperti dilaporkan | teks |
| `burn_time_s` | Lama pembakaran | s |
| `size_mm` | Diameter awal droplet | mm |
| `metric_name`, `metric_value`, `metric_unit` | Satu besaran hasil utama per tabel | lihat di bawah |
| `notes` | Catatan dan peringatan | teks |
| `raw_json` | Seluruh kolom asli baris itu | JSON |

## Ketersediaan kolom per tabel

| Investigasi | Baris | O₂ | Tekanan | Aliran | Hasil | Besaran utama |
|---|---|---|---|---|---|---|
| FLEX (PSI-69) | 274 | ya | ya | – | akhir uji | laju bakar |
| CFI (PSI-39) | 87 | ya | ya | – | – | – |
| BASS-II (PSI-25) | 129 | ya (awal, akhir) | – | setelan kipas saja | – | – |
| BASS (PSI-26) | 122 | – | – | – | – | – |
| Saffire-I/II/III (PSI-98/99/100) | 2 / 9 / 2 | ya / ya / – | – | ya | panjang terbakar (II) | laju rambat (2 sampel) |
| ACME Flame Design (PSI-10) | 327 | ya | ya | – | – | suhu nyala adiabatik |
| ACME CFI-G (PSI-159) | 333 | ya | ya | – | padam sendiri / aliran dihentikan | suhu nyala adiabatik |
| SPICE (PSI-107) | 469 | – | – | ya | – | laju bahan bakar |
| SAME-R / SAME (PSI-101/102) | 109 / 8 | – | – | ya | – | waktu aging / laju susut massa |
| BRE, CLD, E-FIELD, s-Flame, SLICE, FLEX-2, DAFT, PSI-142 | 119 | – | – | – | – | ringkasan; lihat `raw_json` |

## Peringatan yang harus diketahui tim

1. **Laju bakar FLEX tanpa satuan waktu.** Header sumbernya "Burning rate; mm". Nilai disimpan
   apa adanya; cek paper FLEX sebelum menulis satuan di dashboard.
2. **Kolom CO₂ FLEX bertuliskan "CO" di sumber.** Ditafsirkan sebagai CO₂ (pengencer pemadam).
3. **BASS dan BASS-II tidak mentabulasikan laju rambat api.** Datanya hanya ada di video dan paper.
4. **Aliran BASS-II berupa setelan kipas ("Fan display"), bukan cm/s.** Tidak dikonversi.
5. **Tekanan bahan padat tidak tercantum** (uji dilakukan di udara kabin ISS). Jangan diisi asumsi.
6. **Nilai rentang dirata-rata.** "21.5 - 21.7" disimpan 21.6; teks aslinya ada di `raw_json`/`notes`.
7. **Teks bukan angka dikosongkan.** "RAMPED", "LOW O2", "Insignificant" menjadi kosong di kolom angka.
8. **Semua data penerbangan adalah mikrogravitasi.** Tidak ada data gravitasi Bulan atau Mars.

## Tabel lain

- `investigations` (24 baris): akronim, judul, DOI, platform, perangkat, orang, lisensi, jumlah
  file terdaftar vs yang ada di disk, serta teks `objective`, `hypothesis`, `approach`, `impacts`.
- `publications` (352 baris, 235 DOI unik): paper yang didaftarkan NASA untuk tiap investigasi.
- `files` (16.372 baris): manifest semua file PSI, status unduh, sha256, path lokal.
- `papers`: dokumen NTRS (353 baris) dengan tag eksperimen, path PDF dan `.txt` polos.
- `papers_doi`: paper lewat DOI (295 baris) — judul, jurnal, tahun, abstrak (dari OpenAlex),
  status akses (`oa_status`), dan `pdf_status`/`pdf_path` (`downloaded` = PDF akses-terbuka
  otomatis, `downloaded_manual` = kamu unduh sendiri lewat akses institusi, `manual*` = belum ada
  PDF sama sekali). Lihat `kb/manifest/paid_papers.csv` untuk yang masih perlu diambil manual.
- `paper_chunks`: isi teks tiap paper, dipotong per halaman asli (paper DOI yang ada PDF-nya,
  lewat pymupdf — `page` terisi) atau per ~3000 karakter (paper NTRS, dari `.txt`, `page` kosong
  karena tidak ada info halaman asli di sumbernya). Tanpa PDF sama sekali, isinya abstrak saja
  (1 baris per paper). Kolom: `paper_uid` (`ntrs:<id>` atau `doi:<doi>`), `source`, `title`,
  `page`, `chunk_index`, `text`.
- `paper_search` (virtual table FTS5): salinan `paper_chunks` yang bisa dicari teksnya
  (`MATCH`), dengan `snippet()`/`highlight()` untuk kutipan. Ini yang dipakai asisten AI di
  hari-H untuk "cari dulu, lalu sebut paper dan halamannya" — bukan `paper_chunks` langsung.
- Belum lengkap: dari 295 paper DOI, baru **52 punya teks PDF asli** (sisanya cuma abstrak atau
  kosong total bila `oa_status` closed dan belum diunduh manual). Dari 353 paper NTRS, **202
  punya teks** (sisanya tak ada `.txt` dari NTRS). Jalankan ulang `build_kb.py` setelah menambah
  PDF ke `kb/raw/papers/pdf/` (lewat `scripts/integrate_manual_papers.py` atau manual) untuk
  menambah cakupan teks ini.
