# Menyalakan asisten AI di internet

Dashboard (`app/insight/`) bisa dilayani dua cara:

| Cara | `/ask` | Catatan |
|---|---|---|
| Salinan statis (Netlify sekarang) | jawaban tersimpan saja | tanpa backend |
| Statis + backend | **pertanyaan bebas**, jawaban dari alat + sitasi | halaman memanggil backend langsung |

Backend = `python scripts/brain.py serve`. Mesinnya: `scripts/assistant.py`, 19 alat, dan
mode luring deterministik sebagai cadangan. Penyedia model bahasa dipilih dengan `LLM_PROVIDER`:

| `LLM_PROVIDER` | Model | Kunci | Catatan |
|---|---|---|---|
| `deepseek` | `deepseek-v4-pro` (ubah dengan `DEEPSEEK_MODEL`) | `DEEPSEEK_API_KEY` | lewat endpoint DeepSeek yang kompatibel Anthropic |
| `anthropic` (bawaan) | `claude-opus-5-5` | `ANTHROPIC_API_KEY` | + fallback penolakan di sisi server |

Keduanya memakai loop alat, sitasi, dan cek "setiap angka harus bersumber" yang sama.
Hasil evaluasi per penyedia ada di `eval/*_report.md` (luring) dan `eval/*_deepseek_report.md`.

## 1. Coba di laptop dulu

1. Salin `.env.example` jadi `.env` **di akar repo** (sudah di `.gitignore`, jangan di-commit) dan isi:
   ```
   LLM_PROVIDER=deepseek
   DEEPSEEK_API_KEY=sk-...
   ```
   Nama variabelnya harus `DEEPSEEK_API_KEY`. Kunci DeepSeek yang disimpan sebagai
   `ANTHROPIC_API_KEY` bisa terkirim ke `api.anthropic.com` oleh alat lain.
2. `pip install -r requirements-server.txt`
3. `python scripts/brain.py serve` lalu buka `http://127.0.0.1:8765/insight/`.
   `http://127.0.0.1:8765/assistant_status` harus menunjukkan `"llm": true, "provider": "deepseek"`.

## 2. Deploy backend (Render, paket gratis)

1. Push repo ini ke GitHub.
2. Render → **New → Blueprint** → pilih repo. `render.yaml` membuat layanan Docker
   (sudah diisi `LLM_PROVIDER=deepseek`).
3. Saat diminta, isi **DEEPSEEK_API_KEY** (rahasia; tidak masuk git atau image).
4. Setelah jalan, cek `https://<nama>.onrender.com/assistant_status`.

Paket gratis Render tidur setelah lama tidak dipakai; permintaan pertama sesudahnya lambat
(± 1 menit). Untuk hari penjurian, bangunkan beberapa menit sebelumnya atau pakai paket berbayar.
`Dockerfile` yang sama juga jalan di Fly.io, Railway, atau VPS.

## 3. Sambungkan Netlify

Isi `app/insight/config.js` di salinan yang di-deploy ke Netlify:

```js
window.FIF_API = "https://<nama>.onrender.com";
```

lalu deploy ulang Netlify. `CORS_ORIGIN` di backend harus sama dengan alamat Netlify
(sudah diisi di `render.yaml`). Tidak dipakai proxy `_redirects` Netlify: proxy itu punya batas
waktu, dan jawaban model dengan beberapa putaran alat bisa lebih lama.

## Pengaman mode publik (`FIF_PUBLIC=1`, aktif di Dockerfile)

| Pengaman | Bawaan | Variabel |
|---|---|---|
| Jalur tulis ditutup (`/note`, `/annotate`, `/rebuild`, `/feedback`) → 403 | selalu | — |
| Pertanyaan per IP | 8 per 10 menit → 429 | `ASK_PER_IP`, `ASK_WINDOW_S` |
| Panggilan model bahasa per hari (UTC) | 200; sisanya dijawab luring | `ASK_DAILY_CLAUDE` |
| Riwayat percakapan dari klien | maks 6 giliran, dipotong | — |
| Detail galat internal | disembunyikan | — |
| Asal yang boleh memanggil | `CORS_ORIGIN` | `CORS_ORIGIN` |

`/feedback` ditutup karena isinya masuk ke memori kasus yang disisipkan ke prompt asisten:
dibuka ke publik, siapa pun bisa menyuntikkan instruksi.

Batas per IP memakai `X-Forwarded-For` dan bisa dipalsukan; batas harian global yang benar-benar
membatasi biaya. Penghitung harian ada di memori, jadi ter-reset kalau server dimulai ulang.
**Pasang juga batas belanja / saldo terbatas di dasbor penyedia (DeepSeek atau Anthropic)**: itu satu-satunya batas biaya yang
tidak bisa ditembus dari sisi server ini.

## Yang perlu diketahui

- Mode luring tetap jadi cadangan (kunci salah, kuota habis, API galat), tapi pengurainya
  berbasis aturan: mis. "30% oxygen" terbaca sebagai O₂ bawaan 0,25, dan pertanyaan bebas soal
  paper dijawab seadanya. Jawaban luring diberi label `mode: rule-based planner`.
- Evaluasi per penyedia: `python scripts/assistant.py eval --mode deepseek` (atau `--mode claude`);
  memakai kredit API. Mode Claude belum pernah dijalankan.
