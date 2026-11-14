# Evaluasi asisten — eval/assistant_eval_holdout2.jsonl

## mode offline — 12 pertanyaan

| metrik | nilai |
|---|---|
| pass | 1.0 |
| tool_ok | 1.0 |
| contain_ok | 1.0 |
| forbid_ok | 1.0 |
| ui_ok | 1.0 |
| grounded | 1.0 |
| cites_ok | 1.0 |
| ms_median | 8 |

| id | lulus | alat | isi | UI | grounded | ms | angka tanpa sumber |
|---|---|---|---|---|---|---|---|
| k01 | ✔ | ✔ | ✔ | ✔ | ✔ | 4153 |  |
| k02 | ✔ | ✔ | ✔ | ✔ | ✔ | 7 |  |
| k03 | ✔ | ✔ | ✔ | ✔ | ✔ | 6 |  |
| k04 | ✔ | ✔ | ✔ | ✔ | ✔ | 1 |  |
| k05 | ✔ | ✔ | ✔ | ✔ | ✔ | 5 |  |
| k06 | ✔ | ✔ | ✔ | ✔ | ✔ | 17 |  |
| k07 | ✔ | ✔ | ✔ | ✔ | ✔ | 29 |  |
| k08 | ✔ | ✔ | ✔ | ✔ | ✔ | 1 |  |
| k09 | ✔ | ✔ | ✔ | ✔ | ✔ | 0 |  |
| k10 | ✔ | ✔ | ✔ | ✔ | ✔ | 8 |  |
| k11 | ✔ | ✔ | ✔ | ✔ | ✔ | 92 |  |
| k12 | ✔ | ✔ | ✔ | ✔ | ✔ | 15 |  |


> **Catatan kejujuran.** Hold-out 2 dibekukan lebih dulu (SHA-1 tersimpan di `assistant_eval_holdout2.sha1`), lalu dijalankan SATU KALI sebelum ada perbaikan: **11 dari 12 lulus (91,7 %)**. Satu-satunya kegagalan, k08, terjadi karena kata "prediksi" tertangkap sebagai permintaan what-if. Pola itu kemudian diperbaiki (kata "prediksi" kini harus diikuti parameter). Karena perbaikan dibuat setelah melihat set ini, set ini sudah terpakai. Angka di atas adalah hasil SESUDAH perbaikan dan tidak boleh dilaporkan sebagai angka hold-out; angka hold-out yang sah tetap 91,7 %.
