---
noteId: "1ab33bd0dde111f1b2bcb51f1ae91165"
tags: []

---

# Saraf dashboard (tahap C)

Kerangka, **bukan desain**. Membuktikan bahwa semua tampilan dan asisten berbagi satu keadaan.

```
python scripts/brain.py serve --port 8765      # lalu buka http://127.0.0.1:8765/
node app/nerve/nerve.test.mjs                  # uji unit (server tiruan)
node app/nerve/nerve.live.mjs                  # uji ujung-ke-ujung (butuh server menyala)
```

## Aturan main

1. Tampilan **tidak pernah** memanggil server sendiri. Hanya `nerve.dispatch(...)` dan `nerve.on(...)`.
2. Kontrol mengikuti keadaan, bukan sebaliknya (dengarkan `filters.changed`, `whatif.changed`).
   Keadaan bisa datang dari klik, undo, tautan, atau asisten.
3. Asisten (tahap E) memakai pintu yang sama: `nerve.dispatch(aksi, arg, "assistant")`.

## Aksi

| Aksi | Argumen | Bisa di-undo |
|---|---|---|
| `focus` | id entitas, mis. `test:PSI-159:21106G8` | ya |
| `select` | `{ids, mode: replace\|add\|toggle\|remove}` | ya |
| `filter` | `{dim, value}`; dim: `accession`, `ignited`, `flag`, `q`, `o2` `[a,b]`, `p_kpa` `[a,b]` | ya |
| `clearFilters` | — | ya |
| `whatif` | patch, mis. `{o2: 0.3}`; `exp`: `cfig` / `flex` | ya |
| `note` | `{text, author}` → disimpan di server (`kb/gold/notes.jsonl`) | tidak |
| `undo` | — | — |

## Peristiwa

`tests.loaded` · `visible.changed` · `filters.changed` · `selection.changed` · `focus.changed` ·
`dossier.changed` · `explain.changed` · `relevance.changed` · `focusAlerts.changed` ·
`alerts.changed` · `whatif.changed` · `whatif.result` · `notes.changed` · `trail.changed` ·
`loading.changed` · `error` · `*` (semua)

## Tahap D — belajar (`scripts/learn.py`)

| Aksi / endpoint | Isi |
|---|---|
| `annotate` → `POST /annotate` | putusan manusia `ok`/`salah`/`ragu` pada angka, artefak (video), atau `ignited` dengan nilai `ya`/`tidak` |
| otomatis | server menjalankan siklus belajar di latar: verifikasi video → latih ulang GB dari label NASA + manusia → statistik → otak baru → riwayat |
| `refreshQueue` → `/queue`, `/history` | antrean verifikasi (ketidakpastian × dampak), riwayat model |
| peristiwa server | `/events?since=` dipoll; `pipeline.done` → `data.changed` → semua panel memuat ulang |

Log anotasi `kb/gold/annotations.jsonl` hanya ditambah (event sourcing); otak selalu dibangun ulang darinya.
Uji: `python scripts/test_learning.py` (log sementara, tidak mencemari log asli).

## Tahap E — asisten (`scripts/assistant.py`)

| Aksi / endpoint | Isi |
|---|---|
| `ask` → `POST /ask` | jawaban + sitasi bertier + daftar alat + cek grounding; aksi UI dijalankan sebagai pelaku `assistant` |
| `feedback` → `POST /feedback` | 👍/👎 → memori kasus `kb/gold/cases.jsonl` (dipakai mode Claude sebagai contoh) |
| `/assistant_status` | mode aktif: Claude (`claude-opus-5-5`) atau luring |

Mode Claude aktif otomatis setelah `pip install anthropic` dan kredensial (`ANTHROPIC_API_KEY` atau `ant auth login`).
Evaluasi: `python scripts/assistant.py eval [--mode offline|claude|both] [--set eval/assistant_eval_holdout.jsonl]`.

Uji ujung-ke-ujung D+E lewat server (log sementara):
```
FREEFALL_ANN=/tmp/a.jsonl FREEFALL_HISTORY=/tmp/h.jsonl FREEFALL_STATE=/tmp/s.json FREEFALL_CASES=/tmp/c.jsonl \
  python scripts/brain.py serve --port 8766
node app/nerve/nerve.learn.live.mjs 8766
```

Tangkapan layar headless: tambahkan `?nopoll` (waktu virtual browser melompati timer polling).

## Jaminan yang diuji

- respons lambat untuk fokus lama dibuang (fokus G7 lalu G8 cepat → dosir tetap G8)
- what-if di-debounce (3 geseran cepat → 1 permintaan)
- undo memulihkan fokus, seleksi, filter, what-if
- `toHash()` → tautan yang memulihkan keadaan yang sama di browser lain
- what-if di luar rentang uji → model menolak menjawab (ekstrapolasi)
