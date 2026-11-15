/**
 * Backend (scripts/brain.py, learn.py) menulis bendera, peringatan, hipotesis
 * dan alasan antrean dalam bahasa Indonesia, karena itu bahasa kerja peneliti.
 * FLARE+ dibaca juri dalam bahasa Inggris, jadi teks itu diterjemahkan di sini
 * dengan aturan berpola (angka dan id uji tetap apa adanya). Teks yang tidak
 * cocok aturan mana pun ditampilkan asli, bukan disembunyikan.
 */

export const FLAG_EN: Record<string, string> = {
  bukan_suhu: "raw volts, not a temperature",
  jeda_termal_cenderung_berlebih: "thermal lag tends to overestimate duration",
  ekstrapolasi_ke_investigasi_lain: "model extrapolated to another investigation",
  kanal_tak_informatif: "uninformative channel (not evidence of no flame)",
  sinyal_lemah: "weak signal",
  belum_diverifikasi_manusia: "not yet human-verified",
  keluar_koridor: "outside the normal sensor corridor",
  kemungkinan_percobaan_ulang: "probable retry",
  rekaman_ganda: "duplicate recording",
  gagal_gerbang_mutu: "failed the quality gate",
  sumber_bertentangan: "sources disagree",
  kemungkinan_positif_palsu: "possible false positive",
};

export const RULE_EN: Record<string, string> = {
  R1_sinyal_lemah: "R1 weak signal",
  R2_percobaan_ulang: "R2 retry",
  R3_tanpa_konsumsi_o2: "R3 no oxygen consumed",
  R4_kanal_aliran_inverse: "R4 inverse-flame flow channel",
  R5_ada_catatan_operator: "R5 operator note present",
  R6_beda_sumber: "R6 sources differ",
};

export const GRANULARITY_EN: Record<string, string> = {
  test: "test (NASA table row)",
  telemetri_saja: "telemetry only (not in NASA table)",
  campaign: "campaign summary",
};

const RULES: [RegExp, string][] = [
  [/(\d+) angka video belum diverifikasi manusia/, "$1 video numbers not yet human-verified"],
  [/kemungkinan positif palsu \(tanpa konsumsi O2\)/, "possible false positive (no oxygen consumed)"],
  [/kurva sensor keluar koridor normal/, "sensor curve outside the normal corridor"],
  [/percobaan ulang yang tidak ditabulasi NASA/, "retry that NASA did not tabulate"],
  [/sinyal termokopel lemah/, "weak thermocouple signal"],
  [/tabel NASA dan paper mencatat nilai berbeda/, "NASA table and paper record different values"],
  [/tabel NASA dan telemetri tidak sepakat soal menyala/, "NASA table and telemetry disagree on ignition"],
  [/buka koridor telemetri/, "open the telemetry corridor"],
  [/jalankan pemeriksaan lembar bukti/, "run the proof-sheet review"],
  [/lihat aturan (R\d\w*)/, "see rule $1"],
  [/periksa koridor & catatan operator; tabel NASA diutamakan/, "check the corridor and operator notes; the NASA table takes precedence"],
  [/kenaikan ([\d.,]+) V/, "rise $1 V"],
  [/skor ([\d.,]+) di atas p(\d+) kelompok ([^|]+)\|([^|]+)\|ya/, "score $1 above p$2 of group $3 / $4 / ignited"],
  [/skor ([\d.,]+) di atas p(\d+) kelompok ([^|]+)\|([^|]+)\|tidak/, "score $1 above p$2 of group $3 / $4 / not ignited"],
  [/tabel NASA: yes/, "NASA table: yes"],
  [/tabel NASA: no/, "NASA table: no"],
  [/telemetri \(turunan\): ya/, "telemetry (derived): yes"],
  [/telemetri \(turunan\): tidak/, "telemetry (derived): no"],
  [/dilanjutkan oleh (\S+)/, "followed by $1"],
  [/aliran: tabel NASA ([\d.,]+) cm\/s vs paper ([\d.,]+) cm\/s/, "flow: NASA table $1 cm/s vs paper $2 cm/s"],
  [/O2 (\S+) akhir = (\S+) awal = ([\d.,]+)/, "O2 at end of $1 = start of $2 = $3"],
  [/(\d+) episode \(([\d.,]+) s nyala\) belum diverifikasi/, "$1 episodes ($2 s of flame) not yet verified"],
  [/model ragu: P\(menyala\) ([\d.,]+)/, "model unsure: P(ignites) $1"],
  [/tabel NASA 'no' vs telemetri 'ya'/, "NASA table 'no' vs telemetry 'yes'"],
  [/tabel NASA 'yes' vs telemetri 'tidak'/, "NASA table 'yes' vs telemetry 'no'"],
  [/beri label ya\/tidak — langsung dipakai saat latih ulang/, "label yes/no; used directly at the next retrain"],
  [/buka lembar bukti video; OK \/ Salah \/ Ragu/, "open the video proof sheet; OK / wrong / unsure"],
  [/lihat kurva termokopel & koridor; beri putusan ya\/tidak/, "look at the thermocouple curve and corridor; decide yes/no"],
  [/putuskan apakah uji ini benar menyala/, "decide whether this test really ignited"],
  [/kurva sensor sesuai uji sejenis/, "sensor curve matches similar tests"],
  [/kurva sensor menyimpang dari uji sejenis/, "sensor curve deviates from similar tests"],
  [/tautkan sebagai bukti untuk penjelasan 'kenapa'/, "linked as evidence for the explanation"],
  [/uji berkondisi mirip: (\d+)\/(\d+) menyala/, "tests with similar conditions: $1 of $2 ignited"],
  [/tandai '([a-z_]+)'(.*)/, "flag '$1'$2"],
  [/— jangan dipakai sebagai bukti tidak ada api/, "— do not use as evidence of no flame"],
  [/\(tetap ditampilkan\)/, "(still shown)"],
  [/uji tidak ditabulasi NASA \(dibatalkan\/uji coba\/terlewat\)/, "test not tabulated by NASA (aborted, trial or missed)"],
  [/hanya ada berkas telemetri; tidak ada baris di tabel uji PSI/, "only a telemetry file exists; no row in the PSI test table"],
  [/sumber saling bertentangan/, "sources contradict each other"],
  [/konteks seri: sesudah = (\S+)/, "series context: next = $1"],
  [/konteks seri: sebelum = (\S+)/, "series context: previous = $1"],
  [/kondisi mirip \(jarak ([\d.,]+)\)/, "similar conditions (distance $1)"],
  [/ekstrapolasi: coflow di luar ([\d.,\-–]+) cm\/s yang diuji untuk kombinasi ini/, "extrapolation: coflow outside the $1 cm/s tested for this fuel and nozzle"],
  [/^ekstrapolasi:?/, "extrapolation:"],
  [/^dalam_rentang$/, "inside the tested range"],
  [/^ekstrapolasi$/, "extrapolation"],
  [/kombinasi konfigurasi\/bahan bakar tidak ada di data/, "this burner configuration and fuel combination was never tested"],
  [/Penjelasan ini dibangkitkan dari aturan, data, dan tautan — bukan dari model bahasa\. Kekuatan = bobot heuristik, bukan peluang\./, "This explanation is generated from rules, data and links, not from a language model. Strength is a heuristic weight, not a probability."],
  [/dasar aturan:/, "rule basis:"],
  [/struktur data/, "data structure"],
  [/aturan /, "rule "],
  [/uji normal yang menyala menurunkan O2 median/, "normal tests that ignite lower O2 by a median of"],
  [/ambang termokopel burner/, "burner thermocouple threshold"],
  [/validasi/, "validated"],
  [/kolom ignited NASA/, "NASA ignited column"],
  [/tidak ada di tabel uji NASA/, "not in the NASA test table"],
  [/\buji\b/g, "tests"],
  [/\bmemang menyala\b/, "did ignite"],
  [/\bdari\b/g, "of"],
  [/\bberlabel\b/g, "labelled"],
];

const WHY_EN: Record<string, string> = {
  same_day: "same day",
  prev_in_series: "previous in series",
  next_in_series: "next in series",
  summarized_by: "summarized by",
};

/** Terjemahkan satu kalimat backend; kembalikan apa adanya bila tak ada aturan yang cocok. */
export function en(text: unknown): string {
  if (text === null || text === undefined) return "";
  let s = String(text);
  if (FLAG_EN[s]) return FLAG_EN[s];
  if (RULE_EN[s]) return RULE_EN[s];
  if (WHY_EN[s]) return WHY_EN[s];
  // nama bendera di dalam kalimat ("tandai 'sinyal_lemah'") -> label bahasa Inggris
  s = s.replace(/tandai '([a-z_]+)'/g, (_m, f: string) => `flag “${FLAG_EN[f] ?? f}”`);
  s = s.replace(/(R\d_[a-z0-9_]+)/g, (_m, r: string) => RULE_EN[r] ?? r);
  for (const [re, rep] of RULES) s = s.replace(re, rep);
  return s;
}

export const LEVEL_EN: Record<string, string> = { kritis: "critical", perhatian: "warning", info: "info" };
