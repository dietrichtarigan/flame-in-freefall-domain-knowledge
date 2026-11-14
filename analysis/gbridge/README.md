# Jembatan-g: membaca uji mikrogravitasi sebagai gravitasi setara

Dibuat 14 Nov 2026. Skrip: `scripts/gbridge.py`. Tampilan: `app/gbridge/index.html`.
Pencuplik data TB: `scripts/psi_range.py`.

## Gagasan

Analog micromagnetics: bentuk persamaan universal, parameter bahan di-fit dari eksperimen.
Gravitasi tidak masuk ke kinetika. Ia hanya menghasilkan aliran apung, lalu aliran itulah yang
menentukan apakah nyala bertahan.

```
U_b(g, p) = U_b1 (g/g_E)^(1/3) (p0/p)^(1/3)        U = U_paksa + U_b
a = (3/2)(U/r)(r/r0)^(1/2)                          X_lim(a) = X0 + A exp(-a/a_q) + B a
```

| Parameter | Nilai | Asal | Tier |
|---|---|---|---|
| `U_b1` | 20 cm/s (selang 10–30) | Olson & Ferkul 2017 mengutip 20 cm/s; skala `(g α ΔT/T)^(1/3)` memberi 10,5 (α suhu ruang) sampai 21,9 cm/s (α suhu film) | paper_claim |
| `X0, A, a_q, B` batang PMMA | 13,4 %; 6 %; 2 s⁻¹; 0,0167 % s | Olson & Ferkul 2017 pers. (1), fit atas uji BASS-II (PSI-25) | paper_claim |
| eksponen | 1/3 (alternatif 1/2) | 1/3: panjang difusi swa-konsisten di tepi depan nyala. 1/2: panjang sampel tetap, rambat ke atas | asumsi |

Keluaran model bertier `model_prediction` dan selalu membawa selang (rentang `U_b1` × dua eksponen).

## Yang diurai dari tabel NASA

Kolom `Air display` di tabel BASS-II adalah **bacaan anemometer dalam cm/s**, dengan catatan
operator `ext`, `blowoff`, `no ign`. Dari 129 uji diurai 291 titik (O₂, aliran), ditambah 13 titik
Saffire: `analysis/gbridge/points.csv`. Jadi peta (O₂, aliran) bahan padat **tidak kosong**; ia
tersimpan sebagai teks bebas di `raw_json`.

Aturan urai, supaya bisa diperiksa:

- angka setelah kata `pot` = potensiometer kipas, dibuang;
- angka > 40 tanpa kata `max` = tampilan kipas, dibuang;
- `0`, `<1`, `low`, `ext` = di bawah ambang anemometer, ditulis 0,5 cm/s dan ditandai `censored`;
- O₂ akhir dipakai untuk titik padam bila masuk akal (10 % < akhir ≤ awal + 0,3); nilai seperti
  1,6 atau 39,1 dianggap salah catat dan O₂ awal dipakai.

## Pemeriksaan

| Cek | Hasil |
|---|---|
| Titik nyala batang PMMA di atas batas terbitan | 91 dari 92 (terburuk −0,54 % O₂) |
| Uji blowoff O22, batang 1/2 in., 26,5 cm/s | teramati 14,9 % O₂, batas 14,88 % |
| Uji O12 "no ign at any flow" pada 13,6 % | tepat di bawah minimum batas (13,6 %) |
| Jangkar 1 g: batas rambat ke atas PMMA + 4 cm/s | teramati 15,4 %, model 15,29 % |
| Padam aliran rendah dalam rentang cabang padam | 13 dari 17 |

Jangkar 1 g hanya cek konsistensi: `U_b1` = 20 cm/s adalah masukan dan titiknya satu.

## Hasil

| Benda | g/g_E | U_b (cm/s) | Batas O₂ batang PMMA (selang) | Titik PSI ±25 % |
|---|---|---|---|---|
| ISS, tanpa ventilasi | 1e-6 | 0,2 | 17,2 % (16,4–19,3) | 0 |
| Bulan | 0,165 | 11,0 | 14,3 % (13,7–14,7) | 51 |
| Mars | 0,378 | 14,5 | 14,5 % (13,9–15,1) | 24 |
| Bumi | 1 | 20,0 | 15,0 % (14,2–15,8) | 29 |

Minimum batas (13,6 %) ada pada aliran sekitar 2 cm/s, setara 10⁻³ g, bukan pada gravitasi
Bulan atau Mars. Bulan dan Mars berada di cabang blowoff: lebih mudah terbakar daripada Bumi
sekitar 0,5–0,7 poin O₂, tetapi bukan titik terburuk. Titik terburuk adalah kabin bergravitasi
mikro dengan ventilasi lemah.

## Batas model

- Aliran apung berakselerasi sepanjang nyala dan selalu ke atas; aliran paksa seragam.
- Tekanan hanya menskala aliran apung. Ketergantungan kinetika pada tekanan tidak dimodelkan,
  jadi 56,5 kPa (atmosfer eksplorasi) adalah ekstrapolasi.
- O₂ di atas 22,2 % di luar rentang uji BASS-II.
- Cabang padam tidak bisa di-fit ulang dari tabel: aliran saat padam di bawah ambang anemometer.
  Yang dibutuhkan: kalibrasi potensiometer kipas → cm/s.
- PSI tidak bisa memvalidasi sumbu g. Jangkar gravitasi parsial harus dari literatur pesawat
  parabola dan sentrifus (Sacksteder & T'ien 1994; Feier dkk. 2005; Kleinhenz 2006).
- Bahan lain (SIBAL, film PMMA, Nomex) belum punya parameter. Titiknya sudah ada di peta.

## Mengambil satu berkas dari zip berukuran TB

Server PSI mengembalikan URL S3 bertanda tangan dan S3 menerima `Range` (balasan 206). Terbukti
14 Nov 2026 pada zip terbesar di manifest:

```
python scripts/psi_range.py list PSI-10 "PSI-10_Raw Data_21301J4_ACME_Converted.zip"
  zip 32.911 MB, 8.842 anggota; daftar isi dibaca dengan 1.430 kB dalam 7 permintaan (12 s)
python scripts/psi_range.py get  PSI-10 "...Converted.zip" "20211029_004204.493_ACME_21301J4_00004.tif"
  8.364.184 B, unduh total 7,8 MB = 0,024 % dari zip
```

`sample --every N --ext tif` mencuplik tiap frame ke-N. Bila server suatu saat membalas 200,
skrip berhenti sebelum membaca badan respons.

## Menjalankan

```
python scripts/gbridge.py             # tulis points.csv dan app/gbridge/data.json
python scripts/gbridge.py --selftest  # 8 angka jangkar
cd app && python -m http.server 8000  # buka http://localhost:8000/gbridge/index.html
```
