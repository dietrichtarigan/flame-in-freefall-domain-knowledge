---
noteId: "6c2c1670e0e411f1871fa33237f5b37b"
tags: []

---

> **Catatan kejujuran.** Set ini dibekukan sebelum perbaikan apa pun (SHA-1 di `assistant_eval_flare_holdout.sha1`) dan dijalankan SATU KALI dengan DeepSeek setelah instruksi sistem diperbaiki pada set dev: **7 dari 8 lulus (87,5 %)**. Satu-satunya kegagalan, g07, ternyata kesalahan pemeriksa, bukan model: alat mencetak ukuran sampel ".33 cm", model menulis "0.33 cm", dan pola angka pemeriksa tidak mengenali desimal tanpa nol di depan. Pola itu diperbaiki SESUDAH melihat set ini, jadi set ini sudah terpakai; angka hold-out yang sah tetap 87,5 %.
>
> Riwayat set dev (`assistant_eval_flare.jsonl`, 16 soal, DeepSeek): baseline 62,5 % -> 93,8 % setelah instruksi sitasi/angka diperbaiki (penanda [[inv:]] wajib, judul paper bukan id, tanpa penanda model karangan, tanpa pemisah ribuan, eksponen hanya dari find_equations). Sisa kegagalan dev (f10) juga kesalahan pemeriksa: "90%" berasal dari kunci PI90_mm; alat kini mencetak interval_level_pct.
