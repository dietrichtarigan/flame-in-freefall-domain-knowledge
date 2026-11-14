# Ketidakpastian angka utama

Selang 95 % dari **bootstrap cluster per hari uji** (4000 ulangan). Kolom 'naif' = bootstrap per uji, ditampilkan untuk menunjukkan seberapa terlalu sempit selang bila korelasi antar-uji sehari diabaikan.

## CFI-G: peluang menyala

| Kelompok | n | hari | laju | CI95 cluster | CI95 naif |
|---|---|---|---|---|---|
| normal ethane | 41 | 3 | 0.976 | 0.923–1.000 | 0.927–1.000 |
| normal propane | 56 | 3 | 0.714 | 0.625–1.000 | 0.589–0.821 |
| normal butane | 82 | 5 | 0.634 | 0.398–0.929 | 0.524–0.732 |
| inverse ethane | 45 | 4 | 0.911 | 0.821–0.979 | 0.822–0.978 |
| inverse propane | 43 | 4 | 0.861 | 0.536–0.984 | 0.744–0.954 |
| inverse butane | 58 | 4 | 0.914 | 0.827–1.000 | 0.844–0.983 |

Inverse − normal: selisih laju menyala +0.160, p permutasi = 0.0012, CI95 cluster [-0.021, +0.321].

**Perhatikan:** uji permutasi biasa menganggap tiap uji independen sehingga p tampak sangat kecil, tetapi selang bootstrap per hari masih mencakup nol. Konfigurasi biasanya tetap sepanjang satu hari, jadi efektifnya hanya ada ~8 hari per kelompok. Kesimpulan yang jujur: inverse *cenderung* lebih mudah menyala, belum terbukti.

## CFI-G: peluang padam sendiri (setelah menyala)

| Konfigurasi | n | hari | laju | CI95 cluster |
|---|---|---|---|---|
| normal | 132 | 11 | 0.773 | 0.700–0.857 |
| inverse | 131 | 12 | 0.557 | 0.299–0.766 |

## FLEX: laju bakar K (mm²/s)

| Kelompok | n | hari | rerata K | CI95 cluster | CI95 naif |
|---|---|---|---|---|---|
| heptana | 107 | 41 | 0.5448 | 0.5045–0.5857 | 0.5138–0.5750 |
| metanol | 150 | 48 | 0.4719 | 0.4400–0.5050 | 0.4553–0.4907 |
| heptana + He | 21 | 8 | 0.6505 | 0.5794–0.7383 | 0.5919–0.7138 |
| heptana tanpa He | 86 | 34 | 0.5190 | 0.4775–0.5606 | 0.4857–0.5522 |

Heptana − metanol: +0.0729 mm²/s, p = 0.0002, CI95 cluster [+0.0199, +0.1263].
Efek He (heptana): +0.1315 mm²/s, p = 0.0007, CI95 cluster [+0.0443, +0.2313]. Catatan: He biasanya diuji bersama O₂ dan tekanan yang berbeda, jadi ini asosiasi, bukan efek sebab-akibat murni.

## Telemetri ACME: durasi bakar (s, termokopel; cenderung berlebih karena jeda termal)

| Investigasi | n | hari | median | CI95 cluster |
|---|---|---|---|---|
| PSI-10 | 313 | 22 | 44.6 | 37.9–53.5 |
| PSI-23 | 272 | 18 | 26.3 | 23.6–30.3 |
| PSI-159 | 258 | 23 | 51.7 | 44.3–59.9 |

## Video BASS: durasi nyala per episode (s) — **BELUM diverifikasi manusia**

| Material | episode | uji | median | CI95 cluster per uji |
|---|---|---|---|---|
| 1/4" clear rod | 18 | 9 | 39.5 | 22.2–90.2 |
| 2 cm SIBAL | 17 | 12 | 8.0 | 6.0–15.8 |
| 1/4" black rod | 16 | 6 | 70.0 | 9.0–159.0 |
| 3/8" clear rod | 9 | 2 | 66.5 | 52.5–103.8 |
| 1 cm SIBAL | 9 | 7 | 7.5 | 5.5–9.0 |
| 4 cm spherical section | 8 | 2 | 51.2 | 26.5–65.0 |
| 1/2" clear PMMA rod | 6 | 3 | 134.5 | 57.0–212.0 |
| 1/4 black rod | 5 | 2 | 17.0 | 11.0–47.5 |

## Validasi skor anomali koridor

Uji PSI-159 yang diberi komentar operator NASA (n = 82 dari 328) punya skor anomali median lebih tinggi +0.22; p permutasi = 0.001. Skor dihitung tanpa pernah melihat komentar.

