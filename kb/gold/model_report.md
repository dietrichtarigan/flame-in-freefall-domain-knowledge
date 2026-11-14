---
noteId: "0ff42e50dd0211f193e215b85abd30c6"
tags: []

---

# Laporan validasi model — Flame in Freefall

Sumber: `kb/gold/tests.csv` (1990 baris, sha256 aba44b192e3e08cb). Validasi silang 5 lipatan, pembagian acak dengan benih tetap.

## Penilaian keseluruhan: bagikan dengan catatan

## Regresi

| Model | n | R² | RMSE fit | RMSE CV | RMSE tanpa model |
|---|---|---|---|---|---|
| FLEX K (mm²/s) | 257 | 0.637 | 0.0829 | 0.0856 | 0.1375 |

## Klasifikasi

| Model | n | laju positif | akurasi CV | akurasi tebak mayoritas | Brier CV | Brier dasar | AUC CV |
|---|---|---|---|---|---|---|---|
| FLEX padam | 206 | 0.869 | 0.893 | 0.869 | 0.0815 | 0.1139 | 0.826 |
| CFI-G menyala | 325 | 0.809 | 0.818 | 0.809 | 0.13 | 0.1544 | 0.782 |
| CFI-G padam sendiri | 263 | 0.665 | 0.776 | 0.665 | 0.1764 | 0.2226 | 0.726 |

## Koefisien

**flex_K** — d^2-law burning-rate constant K (mm^2/s): d^2 = d0^2 - K t

- `1`: 0.12543
- `heptane`: 0.04386
- `o2`: 1.78706
- `x_co2`: -0.17057
- `x_he`: 0.56976
- `ln(p/101.325)`: 0.07674

**flex_ext** — P(flame extinguishes before droplet is consumed); disrupted tests excluded

- `1`: 4.16453
- `heptane`: -2.01699
- `o2`: -28.16463
- `x_co2`: 3.06996
- `x_he`: 4.62038
- `ln(p/101.325)`: 1.8493
- `d0_mm`: 1.43528

**gas_ign** — P(hot ignition), ACME CFI-G

- `1`: 0.45898
- `inverse`: 0.26602
- `propane`: -1.67747
- `butane`: -2.02608
- `o2`: 5.93064
- `x_fuel`: 0.67547
- `ln(p/101.325)`: 0.67171

**gas_selfext** — P(self-extinguished | ignited); otherwise ended by flow termination

- `1`: 1.29917
- `inverse`: -2.57709
- `propane`: 0.49522
- `butane`: -0.25554
- `o2`: 1.79264
- `x_fuel`: -1.61302
- `ln(p/101.325)`: 1.4963

## Cek satuan K

Waktu bakar dibagi d0²/K: median 0.75, persentil-90 1.01 (n = 256). Rasio yang berkumpul di bawah 1 konsisten dengan hukum d² bila K bersatuan mm²/s. Tabel sumber hanya menulis "mm".

## Catatan wajib untuk pengguna

- Uji FLEX yang berakhir "Disruption" dikeluarkan dari model padam; itu gangguan droplet, bukan hasil pembakaran.
- Model hanya berlaku di dalam rentang data (lihat `range` di model_params.json). Di luar itu simulator menandai ekstrapolasi.
- Semua data adalah mikrogravitasi. Model tidak mengandung variabel gravitasi.
- Hubungan ini korelasi dalam matriks uji yang dirancang, bukan bukti sebab-akibat di luar rancangan itu.
- Bahan padat: 264 uji, hanya 9 dengan hasil dan 2 dengan laju rambat. Tidak dimodelkan.
