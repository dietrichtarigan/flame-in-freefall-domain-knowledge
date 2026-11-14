---
noteId: "3c723840dddf11f1b2bcb51f1ae91165"
tags: []

---

# Model ML tabular — perbandingan (validasi per hari = angka utama)

Sumber: `analysis/ml/tabular_*.log` (dijalankan di quasi09). Stacking dihentikan karena beban cluster bersama; semua model lain selesai. 'Acak' = 5×5 lipat acak, ditampilkan untuk menunjukkan seberapa optimistis validasi acak.

## cfig_ign — P(menyala) CFI-G

cfig_ign: n=325, hari=23

| Model | AUC per-hari | Brier per-hari | Akurasi per-hari | AUC acak |
|---|---|---|---|---|
| logistik (fitur lama) | 0.649 | 0.1610 | 0.785 | 0.787 |
| logistik (fitur penuh) | 0.785 | 0.1260 | 0.831 | 0.841 |
| random forest | 0.839 | 0.1260 | 0.809 | 0.906 |
| extra trees | 0.821 | 0.1330 | 0.806 | 0.880 |
| gradient boosting | 0.829 | 0.1400 | 0.809 | 0.904 |
| SVM RBF | 0.773 | 0.1430 | 0.809 | 0.874 |
| **proses Gaussian** | 0.858 | 0.1100 | 0.849 | 0.885 |
| MLP (jaringan saraf) | 0.814 | 0.1660 | 0.791 | 0.878 |

Terbaik (Brier per-hari): **proses Gaussian**. Model lama: AUC 0.649 → terbaik AUC 0.858.

## cfig_selfext — P(padam sendiri | menyala) CFI-G

cfig_selfext: n=263, hari=23

| Model | AUC per-hari | Brier per-hari | Akurasi per-hari | AUC acak |
|---|---|---|---|---|
| logistik (fitur lama) | 0.690 | 0.2000 | 0.707 | 0.753 |
| logistik (fitur penuh) | 0.854 | 0.1390 | 0.825 | 0.869 |
| random forest | 0.870 | 0.1300 | 0.852 | 0.923 |
| extra trees | 0.877 | 0.1530 | 0.753 | 0.924 |
| **gradient boosting** | 0.889 | 0.1280 | 0.840 | 0.926 |
| SVM RBF | 0.845 | 0.1510 | 0.783 | 0.906 |
| proses Gaussian | 0.832 | 0.1480 | 0.768 | 0.922 |
| MLP (jaringan saraf) | 0.867 | 0.1420 | 0.795 | 0.928 |

Terbaik (Brier per-hari): **gradient boosting**. Model lama: AUC 0.690 → terbaik AUC 0.889.

## flex_ext — P(padam sebelum droplet habis) FLEX

flex_ext: n=206, hari=73

| Model | AUC per-hari | Brier per-hari | Akurasi per-hari | AUC acak |
|---|---|---|---|---|
| **logistik (fitur lama)** | 0.820 | 0.0890 | 0.888 | 0.810 |
| logistik (fitur penuh) | 0.820 | 0.0890 | 0.888 | 0.810 |
| random forest | 0.813 | 0.0960 | 0.869 | 0.789 |
| extra trees | 0.840 | 0.0940 | 0.864 | 0.827 |
| gradient boosting | 0.810 | 0.1120 | 0.850 | 0.766 |
| SVM RBF | 0.761 | 0.0980 | 0.864 | 0.810 |
| proses Gaussian | 0.802 | 0.0960 | 0.869 | 0.740 |
| MLP (jaringan saraf) | 0.865 | 0.0900 | 0.888 | 0.866 |

Terbaik (Brier per-hari): **logistik (fitur lama)**. Model lama: AUC 0.820 → terbaik AUC 0.820.

## flex_K — laju bakar K FLEX (mm²/s)

flex_K: n=257, hari=80

| Model | R² per-hari | RMSE per-hari | R² acak |
|---|---|---|---|
| **ridge (fitur lama)** | 0.579 | 0.0890 | 0.610 |
| random forest | 0.484 | 0.0990 | 0.580 |
| extra trees | 0.459 | 0.1010 | 0.574 |
| gradient boosting | 0.427 | 0.1040 | 0.544 |
| proses Gaussian | 0.466 | 0.1000 | 0.595 |
| MLP (jaringan saraf) | -0.013 | 0.1380 | 0.193 |

Terbaik: **ridge (fitur lama)**. Pembanding rumus jarang (`symreg_flex.md`): RMSE per-hari 0,090 dengan 2 suku.

## Pelajaran

- **CFI-G (23 hari, banyak uji per hari):** validasi acak jauh terlalu optimistis (logistik lama: AUC acak 0,787 vs per hari 0,649). Uji sehari mirip satu sama lain, jadi angka acak tidak boleh dipakai di dashboard.
- **FLEX (73–80 hari, sedikit uji per hari):** selisih acak vs per hari kecil, kadang terbalik. Efek "hari" lemah di sini.
- **CFI-G butuh model nonlinear:** proses Gaussian (menyala, AUC 0,858) dan gradient boosting (padam sendiri, AUC 0,889) jauh mengungguli logistik lama.
- **FLEX tidak:** model linear lama tetap terbaik untuk K (RMSE 0,089) dan setara terbaik untuk padam (Brier 0,089). Rumus jarang 2 suku (RMSE 0,090) praktis sama baiknya dengan ridge 5 fitur — jadi rumus yang sederhana itu yang dipakai di dashboard.
- **MLP tidak unggul di data tabel sekecil ini** (paling buruk untuk K). Deep learning baru menang ketika inputnya sinyal mentah: CNN telemetri mengalahkan aturan dan fitur buatan tangan.
