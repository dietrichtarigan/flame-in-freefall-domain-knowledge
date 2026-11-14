---
noteId: "65678ff0dd6411f1b2bcb51f1ae91165"
tags: []

---

# Analisis video BASS / BASS-II — pilot

Mengukur nyala api dari rekaman eksperimen, karena angkanya tidak ada di tabel.

## Kenapa ini dikerjakan

Dari 264 uji bahan padat di seluruh basis data, **hanya 9 punya kolom hasil dan
2 punya laju rambat**. Tabel uji BASS-II berisi 129 baris tanpa satu pun kolom
hasil: NASA menabulasi material, sampel, dan setelan aliran, tetapi tidak
menabulasi apa yang terjadi pada apinya. Padahal bahan padat justru yang paling
relevan untuk keselamatan kabin. Yang tersisa adalah 243 video.

## Apa yang diukur, dan apa yang tidak

| Terukur | Cara |
|---|---|
| Durasi nyala tampak, per episode | ambang kecerahan + pelabelan komponen terhubung |
| Waktu mulai dan padam | batas episode |
| Luas tampak nyala (piksel) | jumlah piksel blob |
| Cara berakhir: padam bertahap vs mendadak | 3 frame terakhir dibanding puncak |
| Geser sentroid (piksel/detik) | perpindahan pusat blob |

**Tidak diklaim:**

- **Satuan fisis mutlak.** Tanpa penanda skala di bidang pandang, luas tetap
  piksel dan geseran tetap piksel/detik. Konversi ke mm butuh kalibrasi manual
  dari lebar sampel yang diketahui (mis. SIBAL 2 cm) — belum dikerjakan.
- **Laju rambat api.** Geseran sentroid bukan laju rambat: untuk sampel batang
  (seri P/O) apinya memang menetap di ujung batang, tidak merambat.
- **Bahwa setiap wilayah terang adalah api.** Lihat daftar kegagalan di bawah.

## Empat cara pendeteksi ini pernah salah

Semuanya ditemukan lewat lembar bukti, bukan lewat angka. Angkanya terlihat
masuk akal di keempat kasus — itulah sebabnya lembar bukti wajib diperiksa.

1. **Berkas `_2ND_VIEW` bukan rekaman api.** Itu kamera luar yang menyorot
   glovebox berikut astronotnya. Pendeteksi membaca pantulan terang di sana
   sebagai "api" selama 425–509 detik. → digerbang lewat median frame.
2. **Tepi sampel yang tersorot lampu** terbaca sebagai api memanjang.
   → disaring lewat rasio sisi (garis tipis ditolak).
3. **Potret layar LCD kamera Nikon** diselipkan di sebagian video; kotak
   histogramnya terbaca sebagai nyala. → disaring lewat rasio isi (rangka
   berongga ditolak).
4. **Dua episode digabung jadi satu.** Video P1 memuat dua segmen uji terpisah
   oleh jeda gelap 44 detik; melaporkannya sebagai satu pembakaran 174 detik
   menggambarkan kejadian yang tidak pernah ada. → dipisah per episode.

Ambang gerbang adegan (median frame > 8) bukan tebakan: frame nyala sejati
bermedian **0**, interior duct bersorot **30**, kamera luar **84–93**.

## Hasil pilot (30 video)

- 18 video dengan nyala terdeteksi, **37 episode pembakaran**.
- 12 video ditolak gerbang adegan — semuanya berkas `_2ND_VIEW` (kamera luar).
- **37 dari 37 episode cocok** ke baris tabel uji NASA lewat `test_id`.
- **0 dari 37** punya kolom hasil di tabel NASA. Jadi ke-37 durasi nyala itu
  seluruhnya data baru: tabel BASS/BASS-II memuat 251 baris uji dan **tidak
  satu pun** mencantumkan hasil.

### Ketelitian: BELUM dapat ditetapkan

Angka "± 12%" yang sempat ditulis di sini **salah dan sudah dicabut**. Setelah
dijalankan pada 96 video, ketahuan bahwa berkas-berkas yang saya anggap "rekaman
ulang uji yang sama" sebagian besar bukan:

| Pasangan | Sebenarnya |
|---|---|
| `First_Ignition_Attempts` vs `Second_Ignition_Attempts` | dua penyalaan berbeda |
| `Part-1` vs `Part-2` | dua potongan berurutan dari satu rekaman |
| `Flame-Blowoff-...` | klip cuplikan, bukan uji penuh |
| `vlc-record-...` | rekaman layar saat video diputar, hanya sepotong |

Membandingkannya berarti membandingkan kejadian berbeda. Setelah semuanya
dikeluarkan, **hanya uji T16** yang benar-benar terekam ulang (8,0 vs 8,5 detik
= 6%; 89,0 vs 73,5 detik = 17%). Satu uji terlalu sedikit untuk mengklaim angka
ketelitian metode. Jadi: durasi dari video sah sebagai pengukuran kasar, tetapi
**ketelitiannya belum terkuantifikasi**.

### Dugaan yang tidak terbukti

Dugaan awal: jumlah episode = jumlah setelan aliran di kolom `Air display`.
Hasilnya hanya 5 dari 16 cocok, dan itu memang **bukan validasi yang sah**.
Alasannya fisis: mengubah aliran di tengah pembakaran tidak memadamkan api,
jadi satu episode bisa mencakup beberapa setelan; sebaliknya penyalaan ulang
pada setelan yang sama menghasilkan beberapa episode dari satu nilai. Kolom itu
juga tidak selalu berisi setelan aliran — pada uji F4 isinya `3 ign`, yang
berarti tiga penyalaan, dan di situ pendeteksi memang menemukan 3 episode.

## Cara menjalankan

```
python scripts/video_analyze.py --limit 30 --proof   # ukur + lembar bukti
python scripts/video_join.py                         # gabung ke kondisi uji
```

Keluaran:

| Berkas | Isi |
|---|---|
| `summary.csv` | satu baris per video |
| `episodes.csv` | satu baris per episode pembakaran |
| `measurements.csv` | episode + kondisi uji NASA (material, O₂, aliran) |
| `traces/*.csv` | luas & sentroid per frame |
| `proof/*.png` | montase frame dengan kotak deteksi — **periksa ini dulu** |

## Verifikasi sebelum dipakai

Buka `proof/<uji>.png`. Setiap kotak putih harus melingkupi nyala, bukan
perangkat keras, bukan teks, bukan layar kamera. Angka dari video yang lembar
buktinya belum diperiksa manusia tidak boleh masuk ke dashboard.

Alur periksa untuk `video_full` (90 lembar):

```
python scripts/proof_review.py                 # -> analysis/video_full/review.html
:: buka review.html, nilai OK / Salah / Ragu, klik "Unduh review.csv",
:: simpan ke analysis/video_full/
python scripts/proof_review.py --apply analysis/video_full/review.csv
:: -> measurements_verified.csv  (hanya episode dari video berputusan OK)
```

Video yang berbendera (potongan VLC, 0 episode, episode > 200 s, banyak
episode, geser besar) tampil paling atas. Pilihan tersimpan di browser,
jadi pemeriksaan bisa dicicil. **Dashboard hanya boleh membaca
`measurements_verified.csv`.**
