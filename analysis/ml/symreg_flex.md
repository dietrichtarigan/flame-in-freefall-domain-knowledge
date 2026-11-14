# Rumus laju bakar droplet FLEX dari data ISS (regresi simbolik)

n = 257 uji, 80 hari. Semua angka galat = RMSE validasi per hari (GroupKFold 5).

**K ≈ 0.111 + 1.8·O2 + 0.611·He**

K dalam mm²/s; O2, He, CO2 fraksi mol; p0 = 101,325 kPa. R² pada data latih = 0.551. Dipilih dengan aturan 1-SE: model tersederhana yang galatnya tidak lebih buruk dari model terbaik + 1 galat baku.

| Model | RMSE per-hari |
|---|---|
| rata-rata saja | 0.1386 |
| linear, 5 fitur mentah | 0.0832 |
| STLS pada pustaka penuh (GAGAL, lihat bawah) | 0.0907 |
| terbaik dari pencarian menyeluruh | 0.0823 |
| **rumus terpilih (2 suku)** | **0.0899** |

Bentuk ketergantungan O2 (model intersep + satu suku O2), dari yang paling cocok:

| bentuk | RMSE |
|---|---|
| O2 | 0.1133 |
| ln(1+2·O2) | 0.1133 |
| sqrt(O2) | 0.1133 |
| ln(1+5·O2) | 0.1134 |
| ln(1+10·O2) | 0.1135 |
| ln(1+20·O2) | 0.1136 |
| O2^2 | 0.1142 |

Front Pareto:

| suku | RMSE | suku |
|---|---|---|
| 0 | 0.1386 |  |
| 1 | 0.1133 | O2 |
| 2 | 0.0899 | O2, He |
| 3 | 0.0865 | ln(1+2·O2), He, CO2 |
| 4 | 0.0843 | O2, He, CO2, heptana·O2 |
| 5 | 0.0823 | O2, He, CO2, heptana·O2, ln(p/p0)·O2 |

**Percobaan yang gagal, dicatat supaya tidak diulang:** STLS (SINDy) pada pustaka penuh mempertahankan semua bentuk O2 sekaligus dengan koefisien sampai 1.0e+06 yang saling meniadakan, karena suku-suku itu hampir kolinear. Rumus seperti itu tidak bermakna fisika. Solusinya: batasi satu bentuk O2 per model dan cari menyeluruh (pustaka kecil, murah).

Rumus ini empiris dalam rentang kondisi FLEX yang diuji, bukan hukum universal. Bila bentuk ln(1+k·O2) terpilih, ia dapat dibaca sebagai suku ln(1+B) dari hukum d².
