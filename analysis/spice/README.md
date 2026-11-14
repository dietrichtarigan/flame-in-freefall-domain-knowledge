# SPICE — titik asap nyala jet tanpa gaya apung (PSI-107)

Skrip: `scripts/spice_smoke_point.py`. Keluaran di folder ini:

| Berkas | Isi |
|---|---|
| `smoke_points.csv` | 55 titik asap, diekstrak dari berkas NASA (tiap baris membawa baris sumbernya) |
| `spice_model.json` | eksponen + selang, validasi 5 model, uji klaim terbitan, rentang berlaku |
| `table_crosscheck.csv` | tiap titik asap dicocokkan ke tabel uji PSI |
| `spice_smoke_points.png` | data + hukum pangkat · validasi per hari · korelasi panjang nyala |

## Kenapa perlu berkas mentah

Tabel uji PSI untuk SPICE (469 baris) **tidak menandai titik asap**. Isinya kondisi nyala
(laju bahan bakar + coflow), bukan "di sini nyala mulai berasap". Label itu ada di
`Raw Data/PSI-107_Raw Data_SmokePointReview-0g-3.xlsx`, lembar *Smoke Point Datasheet*:
55 titik asap dengan panjang nyala luminous di titik asap (L_SP, mm).

Berkas ini dan 6 berkas pendamping (tesis Dotson 2009, laporan akhir SPICE, lembar data
terbang, kalibrasi panjang nyala; total ±3,5 MB) diambil 14 Nov 2026 dengan `download()` dari
`psi_fetch.py`. Sha256 ketujuhnya cocok dengan manifest. Berkas mentah tidak masuk git
(`kb/raw/`), jadi `smoke_points.csv` disimpan supaya skrip tetap jalan tanpa unduhan.

Pencocokan ke tabel PSI: 53 dari 55 penyalaan titik asap ada di tabel. Untuk tiap penyalaan,
baris tabel yang lajunya paling dekat ke laju titik asap selisihnya median 4,3 %, tapi 14 titik
selisihnya lebih dari 10 % (contoh E16-2: titik asap 2,41 mg/s, tabel 1,97 mg/s). **Jangan
memakai tabel PSI sebagai data titik asap.**

Mutu tabel PSI yang perlu diketahui: 8 baris coflow negatif (−0,28 dan −5,92 cm/s), 25 tanpa
coflow, 12 tanpa laju bahan bakar, 14 baris kembar berurutan, dua ejaan "75 % Propylene" /
"75% Propylene", dan 36 baris 75 % propilena yang fraksi massa hidrokarbonnya bukan 0,818.

## Pedoman metode

Ihme, Chung & Mishra (2022), *Combustion machine learning: Principles, progress and prospects*,
Prog. Energy Combust. Sci. 91:101010, bagian 5:

| Bagian paper | Diterapkan sebagai |
|---|---|
| 5.2 interpretabilitas (kebakaran = keselamatan) | model utama hukum pangkat; tiap koefisien bermakna fisik |
| 5.3 ketidakpastian | selang prediksi 90 % + bootstrap cluster per hari (4000×) |
| 5.4 luar distribusi | prediksi di luar rentang uji dikembalikan sebagai `ekstrapolasi` |
| 5.5 pengetahuan domain | GP hanya mengoreksi sisa hukum pangkat (hibrida), bukan model kotak hitam |

## Hasil

### Validasi tinggalkan-satu-hari (11 hari, 55 titik asap)

| Model | galat tipikal | MAE | cakupan selang 90 % |
|---|---|---|---|
| rerata per bahan bakar (tanpa fisika) | 49 % | 11,3 mm | 0,93 |
| eksponen terbitan NASA tetap | 24 % | 6,2 mm | 0,87 |
| hukum pangkat dipasang | 24 % | 5,7 mm | 0,93 |
| hukum pangkat + (ln d)² | 21 % | 6,0 mm | 0,91 |
| **hibrida: hukum pangkat + GP pada sisa** | **16 %** | **4,0 mm** | 0,87 |

Galat tipikal = exp(RMSE ln L) − 1. Uji kepekaan:
- Tanpa 4 titik propilena 0,41 mm (lihat efek hari di bawah), hibrida 12,8 % vs hukum pangkat 17,0 %:
  keunggulan hibrida bertahan. Suku (ln d)² tidak lagi membantu, jadi "efek diameter tak linear"
  hanya ditopang 4 titik itu.
- Grid hiperparameter GP yang lebih lebar menurunkan galat ke 15,3 %, tapi cakupan selang 90 %
  jatuh ke 0,82 (terlalu yakin). Grid awal dipertahankan.

### Klaim terbitan yang diuji

**1. L_SP ∝ d^−0,91 · u^0,41 (SPICE Final Report).**

| Eksponen | data ini | CI95 cluster per hari | terbitan |
|---|---|---|---|
| coflow u | +0,41 | [+0,30, +0,59] | +0,41 ✔ |
| diameter d | −0,76 | [−0,90, −0,63] | −0,91 — tepat di luar selang |

Arah keduanya terkonfirmasi: coflow lebih cepat dan nosel lebih kecil memberi titik asap lebih
panjang. Eksponen diameter dari data ini lebih lemah daripada angka terbitan. Laporan akhir menyebut
52 titik asap, lembar NASA berisi 55, jadi sebagian selisih mungkin dari himpunan data yang berbeda.

**2. Urutan kecenderungan berjelaga (Dotson 2009): propana < etilena < 50 % < 75 % < propilena.**
L_SP pada d = 1,6 mm, u = 30 cm/s (makin pendek = makin berjelaga):

| Bahan bakar | L_SP (mm) | CI95 cluster per hari |
|---|---|---|
| propana | 53,5 | 48,4–56,7 |
| etilena | 54,6 | 51,8–55,2 |
| 50 % propilena | 36,5 | 34,0–38,0 |
| 75 % propilena | 21,3 | 17,6–24,1 |
| propilena | 17,8 | 16,8–18,9 |

Tiga pasangan bertahan di bootstrap (≥ 97 %). **Propana vs etilena tidak terpisahkan** (urutan
terbitan bertahan di 45 % ulangan), jadi bagian itu belum didukung data ini. Dotson sendiri
mencatat urutannya terbalik pada nosel 0,76 mm.

**3. L_SP ∝ ṁ/Zst.** Garis lewat titik asal: kemiringan 1,61 mm per mg/s, R² = 0,95.
Efek orde kedua yang dilaporkan Dotson (nyala lebih panjang bila u_a/u_f < 0,08) juga terlihat:
8 nyala itu rata-rata 19 % lebih panjang dari garis, sisanya 1 %.

### Efek hari (alasan validasi per hari)

- Propilena 0,41 mm: sisa terbesar justru di sini (P4-3 hari 174: +83 %, P4-4 hari 58: +51 %).
  Ini cocok dengan tesis Dotson: saluran buang tersumbat jelaga pada hari-hari awal dan titik asap
  tertinggi muncul setelah saluran dibersihkan.
- 75 % propilena: rata-rata sisa hari 136 −16 %, hari 173 +14 %. Efek hari serupa yang belum
  dijelaskan sumber mana pun.
- Pada data sekecil ini, lipatan acak tidak selalu lebih optimistis (untuk hukum pangkat malah lebih
  buruk), tapi per hari tetap angka utama karena itulah cara model akan dipakai: kondisi hari baru.

## Prediksi dan rentang berlaku

```bash
python scripts/spice_smoke_point.py predict --fuel propylene --d 0.762 --u 30
# L_SP 24,0 mm, PI90 22,0–26,2 mm, status dalam_rentang, tier model_prediction
```

Model menandai `ekstrapolasi` bila kombinasi bahan bakar–nosel tidak pernah diuji, coflow di luar
rentang uji kombinasi itu, diameter di luar 0,41–1,6 mm, atau prediksi lebih panjang dari 105 mm
(nyala terpanjang yang teramati; nyala lebih panjang bisa menabrak pelat ujung duct). Metana
ditolak: menurut Dotson 2009, nyalanya menabrak pelat sebelum mencapai titik asap.

## Batasan

- n = 55, 11 hari, dan sebagian besar bahan bakar hanya diuji pada 1–3 hari. Etilena 0,76 mm
  hanya 1 titik.
- L_SP adalah satu-satunya label; ketidakpastian pengukuran panjang (piksel → mm) tidak tersedia di
  lembar NASA. Untuk etilena dan propana 1,6 mm, Dotson menulis titik asapnya mungkin sedikit lebih
  tinggi karena transisinya tidak dilewati jauh.
- Data gravitasi normal (tesis Dotson bab 4.2) dan data tanpa coflow (STS-83/94, KC-135) ada di
  lembar yang sama tapi belum dipakai.
