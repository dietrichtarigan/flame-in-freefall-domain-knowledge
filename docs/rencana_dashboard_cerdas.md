---
noteId: "0d11ea50ddd011f1b2bcb51f1ae91165"
tags: []

---

# Rencana: tulang & saraf dashboard cerdas "Flame in Freefall"

Status: draf 1 · 11 Nov 2026 · desain visual SENGAJA belum dibahas.

Sumber gagasan (bab yang dibaca, bukan dikutip panjang):
Kuznetsov, *Intelligent Systems* bab 1 (blok penyusun) & 5 (perumusan masalah) ·
Ware, *Information Visualization* bab 10–11 & Lampiran D ·
Wexler dkk., *Big Book of Dashboards* bab 1, 4, 9, 18, 32, 33, 36 ·
Schmidt (ed.) bab 9.4 · Neuer bab 6 · Zuev bab 6, 10.4 · *Scientific ML* bab 10.2.

---

## 0. Satu kalimat

Dashboard ini bukan kumpulan grafik, melainkan **sistem cerdas kecil**: ia *mengindra* data NASA
baru, *mengingat* setiap angka beserta asal-usul dan ketidakpastiannya, *bernalar* (aturan,
model, penjelasan), *belajar* dari verifikasi manusia, dan *menunjuk* uji ISS berikutnya yang
paling berharga. Grafik hanyalah ujung saraf.

## 1. Tiga pertanyaan yang harus dijawab di hari-H

| # | Pertanyaan juri | Jawaban sistem | Sudah ada |
|---|---|---|---|
| 1 | Apa yang terjadi di ISS? | uji, telemetri, video, paper — saling tertaut | sebagian |
| 2 | Seberapa yakin kita? | selang bootstrap per hari, tingkat kebenaran tiap angka | ya (`analysis/stats`) |
| 3 | Uji apa berikutnya? | peta batas + fungsi-U + simulator what-if | ya (`analysis/ml/boundary`) |

Pertanyaan keempat yang membedakan kita: **"Kenapa?"** — penjelasan abduktif untuk satu uji
(Big Book bab 36: setiap dashboard tidak lengkap; harus ada jalan untuk bertanya kenapa).

## 2. Kerangka: lima lapis (blok penyusun Kuznetsov bab 1.3)

```
 L5 Antarmuka        tampilan tipis + asisten bahasa alami  (keduanya klien API yang SAMA)
        ▲  │
 L4 Saraf            bus keadaan: fokus · seleksi · filter · what-if · peringatan · jejak
        ▲  │
 L3 Belajar          active learning · retrain saat data terverifikasi · ingatan kasus
        ▲  │
 L2 Penalaran        deduktif (aturan) · induktif (model) · abduktif (penjelasan)
        ▲  │
 L1 Ingatan          graf pengetahuan: entitas + tautan + asal-usul + ketidakpastian
        ▲
 L0 Persepsi         pengunduh & penambang: PSI, NTRS, DOI, telemetri, video, citra
```

Aturan emas: **tidak ada lapis yang melompati lapis di bawahnya.** Tampilan tidak membaca CSV;
asisten tidak membaca PDF langsung. Semua lewat L1/L2. Dengan begitu satu perbaikan (mis.
kalibrasi tekanan) otomatis mengalir ke grafik, angka, dan jawaban asisten sekaligus.

### L0 Persepsi — indera

Sudah ada: `psi_fetch`, `ntrs_fetch`, `papers_fetch`, `telemetry_mine`, `telemetry_calibrate`,
`video_analyze`, `inventory_zips`. Kontrak tiap penambang:

- keluaran **selalu** membawa: sumber (berkas + baris/halaman/frame), sha256 berkas asal,
  versi skrip, waktu jalan;
- tidak pernah menimpa data mentah; hasil turunan ditulis terpisah;
- gagal dicatat sebagai status (`failed`, `not_on_server`), bukan dibuang diam-diam.

Indera baru yang direncanakan (urut nilai): penambang laju rambat Saffire-I/III (~112 ribu frame,
citra sudah dipetakan), kalibrasi aliran MFC (rumus sudah ada, validasi ke kolom mHC), indeks
dokumen PSI-23 (214 PDF referensi).

### L1 Ingatan — graf pengetahuan

Satu basis data (`freefall.sqlite` dikembangkan), dengan **entitas**:

| Entitas | Contoh | Kunci |
|---|---|---|
| Investigation | PSI-159 ACME CFI-G | accession |
| Test | 21106 G8 | accession + test_id |
| Artifact | berkas telemetri, video, deret citra, potongan paper | path + sha256 |
| Measurement | waktu bakar 24,1 s | id unik |
| Claim | "laju rambat 1,8 cm/s" di paper X hlm. 7 | paper + halaman |
| Prediction | P(menyala)=0,63 dari model GP v3 | model + versi + input |
| Annotation | putusan manusia "OK/Salah/Ragu" + catatan | pengguna + waktu |

dan **tautan**: Test–Artifact, Test–Measurement, Measurement–Claim (saling dukung/bantah),
Test–Test (seri ulang, hari sama, tetangga kondisi), Test–Anomaly.

**Setiap angka adalah Measurement**, bukan sel tabel. Medan wajib:

```json
{
  "id": "m:PSI-159:21106G8:burn_s:tel",
  "entity": "test:PSI-159:21106G8",
  "quantity": "burn_duration", "value": 24.11, "unit": "s",
  "uncertainty": {"kind": "ci95_cluster_day", "lo": null, "hi": null, "note": "jeda termal → cenderung berlebih"},
  "tier": "derived_auto",
  "method": "telemetry_mine.py@<git-sha> ambang TC 0,0006 V",
  "source": {"artifact": "PSI-159_Raw Data_21106G8_data.csv", "sha256": "…", "rows": "3100–6100"},
  "flags": ["sinyal_lemah", "kemungkinan_positif_palsu"],
  "verified_by": null
}
```

**Tingkat kebenaran (tier)** — tulang punggung kejujuran sistem:

1. `nasa_table` — tercatat NASA di tabel uji
2. `nasa_calibrated` — sinyal mentah NASA + rumus NASA, tervalidasi (mis. tekanan, MAE 2 kPa)
3. `derived_auto` — diturunkan skrip kita, belum dilihat manusia
4. `human_verified` — `derived_auto` yang lolos lembar bukti
5. `paper_claim` — dari teks paper, dengan halaman
6. `model_prediction` — keluaran model, selalu dengan selang

Tampilan dan asisten **wajib** menyebut tier. Aturan: tier 3 tidak boleh tampil sebagai fakta
tanpa label; tier 6 tidak boleh tampil tanpa selang.

### L2 Penalaran — tiga mesin (Kuznetsov 1.2.2)

**Deduktif (aturan, eksplisit, bisa dibaca juri).** Contoh aturan yang sudah kita temukan:

- `tc_rise < 0.002 V` → flag `sinyal_lemah` (89 % tetap nyala nyata, jadi bukan dibuang)
- uji tidak ada di tabel ∧ seri huruf yang sama berlanjut ∧ tidak menyala → `percobaan_ulang`
- satuan termokopel = volt → larang konversi ke °C
- video belum diverifikasi → larang masuk agregat dashboard
- kanal aliran bahan bakar ≈ 0 pada nyala inverse → jangan dipakai sebagai bukti "tak ada api"

Aturan disimpan sebagai data (tabel `rules`: kondisi, akibat, alasan, sumber temuan), dijalankan
*forward chaining* setiap kali data baru masuk. Ini juga dokumentasi hidup.

**Induktif (model).** Layanan model dengan **kartu model** masing-masing:

| Layanan | Model | Metrik jujur (validasi per hari) |
|---|---|---|
| P(menyala) CFI-G | proses Gaussian | AUC 0,845 (logistik lama 0,658) |
| P(padam) FLEX | GP / logistik | AUC 0,82 / Brier 0,083 |
| menyala & padam-sendiri dari telemetri | CNN 1D ansambel | akurasi 0,969, AUC padam-sendiri 0,983 |
| waktu bakar CFI-G | GB kuantil + konformal | cakupan 86 % (target 80 %) |
| laju bakar FLEX | rumus jarang K ≈ 0,111 + 1,80·O₂ + 0,611·He | RMSE 0,090 |
| anomali telemetri | koridor proses | cocok komentar NASA, p = 0,001 |

Kartu model = data: input, rentang berlaku (*domain of validity*), metrik, tanggal latih, dan
**kapan model menolak menjawab** (input di luar rentang uji → kembalikan "ekstrapolasi").

**Abduktif (penjelasan "kenapa").** Untuk satu uji, kumpulkan hipotesis lalu urutkan:

1. kanal mana yang keluar koridor, kapan (dari skor koridor per kanal)
2. catatan operator NASA pada uji itu / uji sehari
3. pola seri (gagal-lalu-ulang, uji terakhir sebelum ganti kondisi)
4. tetangga terdekat dalam ruang kondisi: apa hasil uji serupa
5. klaim paper yang menyebut kondisi serupa (pencarian teks)

Keluaran: daftar hipotesis + bukti + tier. Ini "Five Whys" (Big Book bab 36) yang dijalankan mesin.

### L3 Belajar

- **Active learning** (Schmidt 9.4): fungsi-U menunjuk kondisi paling tidak pasti, kandidat
  hanya di sekitar kondisi yang pernah diuji (alat nyata). Dirumuskan sebagai masalah pencarian
  P = (S, A, T, G, C) (Kuznetsov 5.1): S = ruang kondisi, A = pilih uji, T = tambah data & latih
  ulang, G = ketidakpastian batas di bawah ambang, C = waktu kru ISS per uji. Rekomendasi
  dalam batch yang beragam (tidak 10 titik berdempet).
- **Retrain berbasis peristiwa**: putusan manusia baru (lembar bukti) → Measurement naik tier →
  model terkait dijadwalkan latih ulang → kartu model diperbarui → selisih prediksi dicatat.
- **Ingatan kasus**: setiap pertanyaan + jawaban yang dinilai benar disimpan sebagai kasus;
  pertanyaan serupa berikutnya dimulai dari kasus itu.

### L4 Saraf — bus keadaan bersama

Ini bagian paling penting dan paling sering dilupakan. Satu objek keadaan global, dan semua
tampilan + asisten **berlangganan** padanya:

```
state = {
  focus:      entitas yang sedang dibahas (mis. test:PSI-159:21106G8)
  selection:  himpunan entitas terpilih            → brushing (Ware A5)
  filters:    rentang per dimensi                  → dynamic queries (Ware A9)
  whatif:     {o2, x_fuel, p, fuel, config}        → simulator (Big Book bab 4)
  relevance:  skor relevansi semua entitas thd fokus (Ware A7)
  alerts:     antrean peringatan bertingkat        → pemantauan (Ware A10)
  trail:      jejak langkah pengguna & asisten     → bisa diputar ulang, dibagikan
  notes:      catatan yang diekspresikan pengguna  → externalizing (Ware bab 11)
}
```

Peristiwa yang mengalir di bus: `focus.changed`, `selection.changed`, `filter.changed`,
`whatif.changed`, `data.ingested`, `measurement.verified`, `model.retrained`, `alert.raised`.

**Relevansi** (Ware A7, "degree of relevance") dihitung, bukan ditebak:
skor(entitas | fokus) = gabungan berbobot dari tautan graf (seri, hari, artefak), kedekatan
kondisi (jarak dalam ruang O₂/x_fuel/p), kemiripan kurva telemetri (embedding CNN), dan
kemiripan teks (paper). Entitas relevan disorot di semua tampilan; sisanya diredupkan, tidak
disembunyikan (Ware memperingatkan bahaya menyembunyikan informasi).

**Peringatan** punya tingkat dan biaya: kontradiksi antar-sumber (paper vs tabel), anomali
koridor di atas p95, prediksi di luar rentang berlaku, data baru masuk. Sistem yang memanggil
perhatian, bukan pengguna yang harus ingat memeriksa (Ware A10).

### L5 Antarmuka — klien tipis

Semua tampilan dan asisten memanggil API yang sama. Modul (isi, bukan rupa):

1. **Pantau** — ringkasan + peringatan; setiap angka bisa dibongkar sampai ke uji individual
   (anti dead-end, Big Book bab 32/36).
2. **Dosir uji** — satu uji, semua lapisan: kondisi, telemetri + koridor, video + lembar bukti,
   paper yang relevan, penjelasan abduktif, tetangga.
3. **Batas & what-if** — peta P(menyala)/P(padam) + ketidakpastian, penggeser kondisi,
   rekomendasi uji berikutnya.
4. **Koridor telemetri** — kurva satu uji di atas pita normalnya.
5. **Bukti** — pencarian paper dengan kutipan + halaman; kontradiksi ditandai.
6. **Peta yang belum diketahui** — cakupan data: kondisi mana belum pernah diuji, investigasi
   mana tanpa hasil, tier tiap kolom. Ini *known unknowns* yang dijadikan fitur.
7. **Asisten** — bahasa alami → panggilan alat ke API → jawaban dengan sitasi + tier. Asisten
   juga menulis ke bus (mis. mengubah fokus), jadi percakapan dan grafik selalu sinkron.

## 3. API (kontrak antara tulang dan saraf)

| Endpoint | Keluaran |
|---|---|
| `GET /entity/{id}` | dosir lengkap + tautan + tier tiap angka |
| `GET /search?q=` | hibrida: FTS paper + uji + catatan |
| `GET /relevance?focus=` | skor relevansi semua entitas |
| `POST /predict/{model}` | prediksi + selang + status rentang berlaku |
| `GET /boundary/{exp}` | grid P & σ + titik uji |
| `GET /recommend/{exp}?k=` | batch uji berikutnya + alasan |
| `GET /corridor/{group}` · `/anomalies` | pita + skor |
| `GET /explain/{test}` | hipotesis abduktif berperingkat |
| `GET /provenance/{measurement}` | rantai asal-usul sampai berkas/halaman/frame |
| `POST /annotate` | putusan/catatan manusia → peristiwa `measurement.verified` |
| `GET /coverage` | peta yang belum diketahui |

Untuk hari-H yang mungkin tanpa internet stabil: semua `GET` bisa dihitung di muka menjadi
**paket data JSON statis** (yang sudah kita punya: `boundary.json`, `corridors.json`,
`uq.json`, …); hanya asisten dan `predict` yang butuh server kecil.

## 4. Asisten: alat, bukan pengetahuan umum

Model bahasa diberi **alat** (memanggil endpoint di atas), bukan teks mentah. Aturan sistem:

- setiap angka dalam jawaban harus berasal dari panggilan alat, dengan tier dan sumber;
- bila alat mengembalikan "ekstrapolasi" atau tier 3, asisten wajib mengatakannya;
- pertanyaan "kenapa" → `/explain`; "bagaimana kalau" → `/predict` + `/boundary`;
  "apa berikutnya" → `/recommend`.
- jawaban yang dinilai benar oleh pengguna → disimpan sebagai kasus (L3).

## 5a. Status (11 Nov 2026, malam)

Tahap A dan sebagian B **sudah berjalan**:

- `scripts/build_brain.py` → `kb/gold/brain.sqlite`: 2.647 entitas, ±18 ribu Measurement
  bertier, ±19,7 ribu tautan, 5 kartu model. Dipisah dari `freefall.sqlite` supaya
  `build_kb.py` tidak menghapusnya.
- Lima aturan deduktif (R1–R5) dijalankan otomatis dan **mereproduksi temuan manual**:
  117 sinyal lemah, 9 percobaan ulang (persis A1–A3, G1–G5, 21242 F1), 1 kemungkinan
  positif palsu (persis 21106 G8).
- `scripts/brain.py`: `entity`, `explain` (abduktif), `relevance`, `provenance`,
  `coverage`, `search`, plus server JSON (`serve --port 8765`, pustaka standar saja).
  `explain 21106G8` menemukan sendiri catatan NASA pada G7 ("the igniter stayed in the
  flame longer") sebagai konteks panas sisa di burner.
- Indeks paper disaring dari dokumen NTRS di luar topik (`scripts/ntrs_relevance.py`).

Tahap C **selesai sebagai kerangka** (`app/nerve/`, lihat README di sana):
`nerve.js` (keadaan bersama: fokus, seleksi, filter, what-if, relevansi, peringatan, catatan,
jejak; undo; tautan berbagi), endpoint baru `/tests`, `/alerts` (20 kritis · 60 perhatian ·
118 info), `/whatif/{cfig,flex}`, `/notes` + `POST /note`, relevansi lintas uji/paper/artefak.
Diuji: uji unit Node, uji ujung-ke-ujung terhadap server, dan tangkapan layar Edge headless.

Tahap D dan E **selesai sebagai kerangka teruji** (12 Nov 2026 dini hari):

- D: `scripts/learn.py` — log anotasi append-only, pipeline bergaya make dengan sidik jari masukan
  DAN keluaran, latih ulang GB dari label NASA + manusia (`scripts/ml_labels.py`), antrean
  verifikasi, riwayat model; server menjalankan siklus di latar dan menukar otak secara atomik
  (146 permintaan selama penukaran, 0 galat).
- E: `scripts/assistant.py` — 15 alat (tanpa alat anotasi), mode Claude `claude-opus-5-5` +
  fallback sisi server, mode luring deterministik, sitasi bertier, cek grounding angka, memori
  kasus; evaluasi 20 soal (luring 100 %) + 8 soal hold-out (luring 75 %, tidak disetel).
- Bug nyata yang tertangkap uji: 27 episode video dan 3 rekaman telemetri ganda saling menimpa
  (ID bertabrakan); keluaran pipeline yang ditimpa diam-diam dianggap segar.

Belum: desain (F); mode Claude belum pernah dijalankan (SDK & kredensial belum ada di laptop).

## 5. Urutan pembangunan

| Tahap | Isi | Selesai bila |
|---|---|---|
| A. Tulang data | skema Measurement + tier + provenance; migrasi semua hasil analisis yang ada ke sana | `/entity` untuk 21106G8 menampilkan semua lapisan dengan tier |
| B. Penalaran | tabel aturan + forward chaining; kartu model; `/explain` versi 1 | penjelasan G8 muncul otomatis dari aturan + koridor + O₂ |
| C. Saraf | bus keadaan + relevansi + peringatan | klik satu uji menyorot seri, tetangga, paper di semua modul |
| D. Belajar | `/annotate` → retrain → kartu model berubah; rekomendasi batch | satu putusan lembar bukti mengubah angka dashboard tanpa langkah manual |
| E. Asisten | alat-alat + aturan sitasi | 20 pertanyaan uji juri dijawab dengan sitasi & tier yang benar |
| F. Rupa | desain visual (ditunda sesuai permintaan) | — |

Pembagian 5 orang (usul): 1 orang tahap A (data), 1 orang B+D (penalaran & belajar), 1 orang C
(saraf/front-end state), 1 orang E (asisten), 1 orang L0 (Saffire + verifikasi lembar bukti).

## 6. Risiko & cara menjaga kejujuran

- **Angka turunan tampil sebagai fakta** → tier wajib di skema, bukan di desain.
- **Model tampak lebih pintar dari datanya** → kartu model memuat metrik per hari, bukan acak;
  kita sudah melihat AUC acak 0,79 jatuh ke 0,65 per hari.
- **Rekomendasi aneh** (kombinasi yang tak pernah diuji) → kandidat hanya di sekitar uji nyata.
- **Asisten berhalusinasi** → tanpa alat, tanpa angka.
- **Dashboard buntu** → setiap agregat punya jalan ke uji individual dan ke "kenapa".
