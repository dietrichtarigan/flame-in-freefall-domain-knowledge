# Evaluasi asisten — eval/assistant_eval_holdout2.jsonl

## mode deepseek — 12 pertanyaan

| metrik | nilai |
|---|---|
| pass | 0.417 |
| tool_ok | 0.917 |
| contain_ok | 0.833 |
| forbid_ok | 1.0 |
| ui_ok | 1.0 |
| grounded | 0.75 |
| cites_ok | 0.917 |
| ms_median | 10697 |

| id | lulus | alat | isi | UI | grounded | ms | angka tanpa sumber |
|---|---|---|---|---|---|---|---|
| k01 | ✘ | ✔ | ✔ | ✔ | ✘ | 18534 | 95 |
| k02 | ✔ | ✔ | ✔ | ✔ | ✔ | 8536 |  |
| k03 | ✘ | ✔ | ✘ | ✔ | ✔ | 14222 |  |
| k04 | ✘ | ✘ | ✔ | ✔ | ✔ | 17375 |  |
| k05 | ✔ | ✔ | ✔ | ✔ | ✔ | 6367 |  |
| k06 | ✔ | ✔ | ✔ | ✔ | ✔ | 12141 |  |
| k07 | ✘ | ✔ | ✔ | ✔ | ✘ | 9315 | 41 66 |
| k08 | ✔ | ✔ | ✔ | ✔ | ✔ | 10741 |  |
| k09 | ✘ | ✔ | ✔ | ✔ | ✔ | 6420 |  |
| k10 | ✘ | ✔ | ✘ | ✔ | ✔ | 10697 |  |
| k11 | ✔ | ✔ | ✔ | ✔ | ✔ | 6293 |  |
| k12 | ✘ | ✔ | ✔ | ✔ | ✘ | 9377 | 24 |


> **Catatan kejujuran.** Hold-out 2 dibekukan lebih dulu (SHA-1 tersimpan di `assistant_eval_holdout2.sha1`), lalu dijalankan SATU KALI sebelum ada perbaikan: **11 dari 12 lulus (91,7 %)**. Satu-satunya kegagalan, k08, terjadi karena kata "prediksi" tertangkap sebagai permintaan what-if. Pola itu kemudian diperbaiki (kata "prediksi" kini harus diikuti parameter). Karena perbaikan dibuat setelah melihat set ini, set ini sudah terpakai. Angka di atas adalah hasil SESUDAH perbaikan dan tidak boleh dilaporkan sebagai angka hold-out; angka hold-out yang sah tetap 91,7 %.
