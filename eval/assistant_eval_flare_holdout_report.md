---
noteId: "55828b20e0e411f1871fa33237f5b37b"
tags: []

---

# Evaluasi asisten — eval/assistant_eval_flare_holdout.jsonl

## mode deepseek — 8 pertanyaan

| metrik | nilai |
|---|---|
| pass | 0.875 |
| tool_ok | 1.0 |
| contain_ok | 1.0 |
| forbid_ok | 1.0 |
| ui_ok | 1.0 |
| grounded | 0.875 |
| cites_ok | 1.0 |
| media_ok | 1.0 |
| cite_ok | 1.0 |
| ms_median | 13955 |

| id | lulus | alat | isi | UI | grounded | media | sitasi | ms | angka tanpa sumber | alat dipakai |
|---|---|---|---|---|---|---|---|---|---|---|
| g01 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 13955 |  | find_figures |
| g02 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 28664 |  | gravity_flammability get_investigation make_plot |
| g03 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 10178 |  | rank_investigations scenario_evidence |
| g04 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 8045 |  | find_equations search_papers |
| g05 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 6980 |  | make_plot ui_action |
| g06 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 12803 |  | search_papers search_papers |
| g07 | ✘ | ✔ | ✔ | ✔ | ✘ | ✔ | ✔ | 22341 | 0.33 | compare_investigations get_investigation get_investigation |
| g08 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ | 29051 |  | get_investigation search_papers get_investigation find_tests find_tests get_test search_papers |


---
noteId: "6c2c1670e0e411f1871fa33237f5b37b"
tags: []

---

> **Catatan kejujuran.** Set ini dibekukan sebelum perbaikan apa pun (SHA-1 di `assistant_eval_flare_holdout.sha1`) dan dijalankan SATU KALI dengan DeepSeek setelah instruksi sistem diperbaiki pada set dev: **7 dari 8 lulus (87,5 %)**. Satu-satunya kegagalan, g07, ternyata kesalahan pemeriksa, bukan model: alat mencetak ukuran sampel ".33 cm", model menulis "0.33 cm", dan pola angka pemeriksa tidak mengenali desimal tanpa nol di depan. Pola itu diperbaiki SESUDAH melihat set ini, jadi set ini sudah terpakai; angka hold-out yang sah tetap 87,5 %.
>
> Riwayat set dev (`assistant_eval_flare.jsonl`, 16 soal, DeepSeek): baseline 62,5 % -> 93,8 % setelah instruksi sitasi/angka diperbaiki (penanda [[inv:]] wajib, judul paper bukan id, tanpa penanda model karangan, tanpa pemisah ribuan, eksponen hanya dari find_equations). Sisa kegagalan dev (f10) juga kesalahan pemeriksa: "90%" berasal dari kunci PI90_mm; alat kini mencetak interval_level_pct.
