# Catatan evaluasi mode DeepSeek (14 Nov 2026)

Model: `deepseek-v4-pro` lewat endpoint DeepSeek yang kompatibel Anthropic, loop alat yang sama
dengan mode Claude. Dijalankan SATU KALI pada 28 soal utama dan 12 soal hold-out 2.

| Set | lulus | alat benar | isi wajib | grounded | sitasi valid | median waktu |
|---|---|---|---|---|---|---|
| utama (28) | 46,4 % | 100 % | 71,4 % | 78,6 % | 89,3 % | 9,0 s |
| hold-out 2 (12) | 41,7 % | 91,7 % | 83,3 % | 75,0 % | 91,7 % | 10,7 s |

Pembanding: mode luring 96,4 % dan 100 % pada set yang sama. Tapi pengurai luring dibangun untuk
soal-soal ini, dan kriteria `must_contain` banyak memakai frasa persis dari templat luring.

**Pembacaan ulang 6 soal yang gagal** (dijalankan ulang; jawaban model tidak deterministik):

- Isi jawaban benar dan bersumber, tapi frasa wajib tidak persis sama: `positif_palsu` vs
  "positif palsu", "belum terbukti" vs "belum kuat", "P(padam" vs "peluang padam ≈ 0,96".
- "Angka tanpa sumber" yang ternyata hasil hitungan dari angka bersumber: 200 = 20 + 61 + 119
  peringatan, −0,07 = 0,911 − 0,976. Pemeriksa grounding sengaja ketat dan menandai aritmetika.
- Positif palsu pemeriksa: "159" dari contoh format ID `PSI-159:...`.
- Pilihan alat tidak selalu sama antar-jalan: k04 sekali tanpa `whatif_flex`, sekali benar.
- Sitasi tidak valid (4 soal pada jalan pertama) tidak muncul lagi saat diulang; belum diselidiki.

Jadi angka lulus di atas meremehkan mutu jawaban, tapi tanpa penilaian ulang yang adil
tidak ada angka pengganti yang sah. Kriteria evaluasi yang tidak bergantung pada frasa templat
belum dibuat.

**Perbaikan sesudah evaluasi:** prompt sistem semula berbunyi "Answer in the user's language
(usually Indonesian)", sehingga pertanyaan berbahasa Inggris (h02) dijawab dalam bahasa Indonesia.
Diganti agar bahasa jawaban mengikuti bahasa pertanyaan; dicek manual dengan 3 pertanyaan.
Karena dibuat sesudah melihat hasil, angka di atas adalah angka SEBELUM perbaikan itu.
