---
noteId: "626ff370dd6711f193e215b85abd30c6"
tags: []

---

# Telemetri ACME — 943 uji dari rekaman sensor mentah

Menambang `*_data.csv` (3,5 GB, ~125 Hz) dari tiga investigasi ACME menjadi satu
tabel hasil per uji.

## Kenapa ini berharga

Tabel uji PSI hanya memuat kondisi yang **direncanakan**. Berkas telemetri memuat
apa yang benar-benar **terjadi**: suhu burner, aliran aktual, arus ion, tekanan,
dalam resolusi milidetik. Belum satu pun masuk basis data kita sebelumnya.

| Investigasi | Berkas telemetri | Baris di tabel uji |
|---|---|---|
| PSI-159 CFI-G | 338 | 333 |
| PSI-10 Flame Design | 317 | 327 |
| **PSI-23 s-Flame** | **288** | **18 (hanya ringkasan kampanye)** |

PSI-23 adalah keuntungan terbesar: 288 uji nyata yang di tabel hanya terwakili
18 baris ringkasan.

## Detektor nyala: termokopel, bukan arus ion

Percobaan pertama memakai **arus ion** — nyala hidrokarbon menghasilkan ion,
jadi terdengar masuk akal, dan satu berkas contoh memang memperlihatkan arus
melonjak bersamaan dengan aliran bahan bakar. Diuji terhadap kolom `ignited`
NASA pada 320 uji CFI-G, hasilnya **45,6%** — jauh di bawah tebak-mayoritas
81,9%, artinya lebih buruk daripada menebak.

Sebabnya terlihat begitu datanya dipilah:

| Konfigurasi | NASA | n | kenaikan arus ion (median) |
|---|---|---|---|
| inverse | menyala | 130 | 0,04 V |
| inverse | tidak | 14 | 0,06 V |
| normal | menyala | 131 | 2,31 V |
| normal | tidak | 44 | 2,29 V |

Nilainya praktis **sama** antara menyala dan tidak: kanal itu sebenarnya
mengikuti aliran bahan bakar, bukan keberadaan api. Masuk akal secara fisika —
CFI-G adalah investigasi **nyala dingin** (~500 K), yang hampir tidak
menghasilkan ionisasi maupun cahaya tampak.

Termokopel burner memisahkan dengan tajam, karena api memanaskan burner baik
pada nyala normal, inverse, maupun nyala dingin:

| NASA | kenaikan suhu burner |
|---|---|
| tidak menyala | median 0,00001–0,00003 V, p90 = **0,00053 V** |
| menyala | median 0,00392–0,00606 V, p10 = **0,00062 V** |

Ambang **0,0006 V** diambil di celah antara keduanya.

## Hasil validasi

Diuji terhadap kolom `ignited` NASA, 320 uji CFI-G berpasangan:

|  | NASA: menyala | NASA: tidak |
|---|---|---|
| **termokopel: nyala** | 247 | 5 |
| **termokopel: tidak** | 15 | 53 |

**Kecocokan 93,8%** (300/320), dibanding tebak-mayoritas 81,9%. Kedua sisi
dihasilkan independen — skrip tidak pernah melihat kolom `ignited`.

## PERINGATAN SATUAN

Semua kanal adalah **tegangan mentah**, bukan satuan fisis terkalibrasi.
`tc_burner_rise_v` adalah kenaikan tegangan termokopel dalam **volt**, BUKAN
derajat Celsius. Angka ini sah untuk membandingkan antar-uji dan untuk
penentuan waktu, tetapi **tidak boleh ditampilkan sebagai suhu dalam satuan SI**
tanpa kurva kalibrasi NASA yang belum kita miliki.

Catatan kedua: termokopel punya **jeda termal**. Burner masih panas beberapa
saat setelah api padam, jadi `t_extinct_s` cenderung **lebih lambat** dari waktu
padam sebenarnya, dan `burn_duration_s` cenderung sedikit berlebih.

## Cara menjalankan

```
python scripts/telemetry_mine.py              # semua 943 berkas (~10 menit)
python scripts/telemetry_mine.py --acc PSI-23 # satu investigasi
python scripts/telemetry_validate.py          # uji silang ke kolom ignited NASA
```

Keluaran: `acme_telemetry.csv` — satu baris per uji, dengan `test_point` yang
cocok ke kolom `test_id` di basis data.

## Gabung ke tabel uji (`telemetry_join.py`)

```
python scripts/telemetry_join.py    # -> telemetry_joined.csv
```

Tiap uji telemetri dipasangkan ke baris tabel NASA di `kb/gold/freefall.sqlite`:

| Cara terpasang | Uji | Arti |
|---|---|---|
| `uji` | 635 | `test_point` = `test_id` persis (PSI-10, PSI-159) |
| `hari` | 288 | PSI-23: dipasang ke baris ringkasan hari lewat 5 digit awal kode uji |
| `tidak ada` | 20 | tidak ada baris tabel yang cocok |

| Investigasi | Uji telemetri | Baris tabel | Menyala (telemetri) | Durasi median |
|---|---|---|---|---|
| PSI-10 | 317 | 327 | 313 | 44,6 s |
| PSI-23 | 288 | 18 | 272 | 26,4 s |
| PSI-159 | 338 | 333 | 258 | 52,0 s |

**PSI-23: 288 uji individual dipulihkan dari 18 baris ringkasan (16× lipat).**
Kondisi (bahan bakar, O₂, tekanan) untuk uji-uji ini diwarisi dari baris
harian, jadi itu kondisi **kampanye**, bukan setelan per uji. Kolom
`table_granularity = campaign` menandainya.

### 20 uji yang tidak ada di tabel NASA

Sudah diperiksa terhadap CSV sumber di `kb/raw/psi/files/`: kode-kode ini memang
**tidak ada di berkas NASA**. Ini bukan kehilangan saat pengolahan. NTRS tidak
menyebut satu pun kode uji ini.

Dugaan awal bahwa "hari 21106 = hari uji coba yang tidak ditabulasi" **salah**.
Hari 21106 punya 14 baris di tabel. Yang hilang hanya percobaan tertentu di
dalamnya.

| Kelompok | Uji | Telemetri | Penilaian |
|---|---|---|---|
| Gagal lalu diulang | 21106 A1–A3 (lalu A4), G1–G5 (lalu G6), 21242 F1 | tidak menyala | **Kuat.** Catatan NASA pada 21242 F2: *"F1 was aborted, and F2 did not ignite."* Percobaan yang dibatalkan tidak diberi baris sendiri. |
| Tidak menyala, tunggal | 19115 H1, 19123 H1, 19123 L8, 19196 N2 | tidak menyala | Polanya sama, tetapi tanpa bukti langsung. |
| Menyala, sinyal kuat | 22024 M1 | menyala, kenaikan 0,0154 V | Mungkin pembakaran nyata yang tidak ditabulasi. Kenaikannya sama dengan M2 (0,0153 V), yang ada di tabel. |
| **Kemungkinan positif palsu** | 21106 G8 | "menyala", kenaikan 0,00087 V | Kenaikannya baru sedikit di atas ambang 0,0006 V, sedangkan tetangganya 0,004–0,007 V. O₂ akhir G7 = O₂ awal G9 = 0,207473561, persis sama: tidak ada oksigen terpakai di antara keduanya. Uji normal yang menyala di berkas ini menurunkan O₂ dengan median 0,0018. |
| Ragu | 19115 C1, D1, P1, 19142 B1, 19175 B2 | "menyala", kenaikan lemah 0,0011–0,0026 V | Belum bisa diputuskan, lihat di bawah. |

Dua jalan buntu yang dicatat supaya tidak diulang:

- **Kanal aliran bahan bakar bukan bukti tidak ada api.** Nilainya hampir nol
  pada *semua* uji inverse (119/119 PSI-10, 129/129 PSI-159), termasuk 126 uji
  yang menurut NASA menyala. Pada nyala inverse, bahan bakar ada di ruang uji,
  tidak dialirkan lewat kanal itu.
- **Uji kesinambungan O₂ tidak sahih untuk PSI-10.** Urutan baris di CSV-nya
  tidak mengikuti urutan kode uji, jadi "baris sebelum" dan "baris sesudah"
  belum tentu berurutan waktu. Uji ini hanya dipakai untuk PSI-159 G7→G9, yang
  barisnya berurutan (baris 41–43).

**Akibatnya bagi detektor:** G8 menunjukkan bahwa kenaikan tipis di atas ambang
bisa berupa panas sisa atau panas pemantik, bukan api. Ambang 0,0006 V tetap
sah sebagai pemisah pada validasi (93,8%). Ada 117 uji "menyala" dengan
kenaikan < 0,002 V (PSI-23: 60, PSI-159: 39, PSI-10: 18). Dari 35 di antaranya
yang punya label NASA, 31 memang menyala dan 4 tidak (89%). Nyala dingin wajar
bersinyal lemah. Jadi uji-uji ini sebaiknya ditampilkan dengan tanda **sinyal
lemah**, bukan dibuang.
