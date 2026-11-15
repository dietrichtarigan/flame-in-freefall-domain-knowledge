/**
 * Jembatan ke backend otak (scripts/brain.py).
 *
 * Desain FLARE+ datang sebagai mockup dengan angka yang ditulis keras. Berkas ini
 * menggantinya dengan data nyata, dan sengaja TIDAK menyediakan nilai cadangan
 * yang dikarang: bila backend mati, tampilan menunjukkan keadaan "tidak tersedia",
 * bukan angka contoh yang bisa disalahartikan juri sebagai hasil pengukuran.
 *
 * Aturan proyek yang ikut dijaga di sini:
 *  - setiap angka membawa tier (nasa_table, derived_auto, human_verified, ...)
 *  - prediksi model selalu dengan selang + penanda ekstrapolasi
 *  - jawaban asisten membawa grounding; angka tanpa sumber ditandai
 */

declare global {
  interface Window {
    FIF_API?: string;
  }
}

/** Alamat backend: window.FIF_API (diisi config.js untuk salinan statis) atau host yang sama. */
export const API =
  (typeof window !== "undefined" && window.FIF_API) || "";

export type Tier =
  | "nasa_table"
  | "nasa_calibrated"
  | "human_verified"
  | "derived_auto"
  | "paper_claim"
  | "model_prediction";

export const TIER_LABEL: Record<Tier, string> = {
  nasa_table: "recorded value",
  nasa_calibrated: "nasa calibrated",
  human_verified: "human verified",
  derived_auto: "automated result",
  paper_claim: "paper claim",
  model_prediction: "model prediction",
};

async function get<T>(path: string, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`${API}${path}`, { signal });
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
  return (await r.json()) as T;
}

export async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) throw new Error(`${path} -> HTTP ${r.status}`);
  return (await r.json()) as T;
}

/* ------------------------------------------------------------------ tipe */

export type ScenarioId = "cabin" | "surface" | "suit" | "earth";

export interface RankRow {
  accession: string;
  name: string;
  score: number;
  components: { direct: number; conditions: number; evidence: number };
  pillars: string[];
  n_full: number;
  n_o2_only: number;
  why: { direct: string; conditions: string; evidence: string };
  stability?: { keep: number; lo: number; hi: number };
}

export interface InsightData {
  built: string;
  weights: Record<string, number>;
  scenarios: ScenarioId[];
  scenario: Record<string, any>;
  investigations: any[];
  points: any[];
  earth: any[];
  partial_gravity: string[];
  suggested: string[];
  canned?: { q: string; a: string; grounding: any; mode: string; tools: string[] }[];
  tiers?: Record<string, string>;
  pillars?: Record<string, string>;
  totals?: any[];
  corpus?: { chunks: number | null; papers_full_text: number | null; publications?: number | null };
  method?: Record<string, string>;
}

export interface AskReply {
  answer: string;
  mode: string;
  tool_calls: { name: string; input?: unknown; error?: boolean }[];
  citations?: any[];
  grounding?: { numbers_checked: number; ungrounded: string[]; ok: boolean };
  figures?: {
    id: string;
    label: string;
    page: number;
    caption: string;
    image: string;
    paper: string;
    doi?: string;
    url?: string;
    kind?: string;
  }[];
  plots?: unknown[];
}

/* ----------------------------------------------------------------- panggilan */

/** Paket data tampilan: peringkat, kartu investigasi, titik uji, celah. */
export const insight = (signal?: AbortSignal) =>
  get<InsightData>("/insight_data", signal);

/** Status backend: apakah model bahasa hidup, penyedia apa, alat apa saja. */
export const status = (signal?: AbortSignal) =>
  get<{ llm: boolean; provider: string; model?: string; tools: string[]; public?: boolean }>(
    "/assistant_status",
    signal,
  );

export const ask = (question: string, history: { q: string; a: string }[] = [], signal?: AbortSignal) =>
  post<AskReply>("/ask", { question, history }, signal);

/** Penilaian manusia atas satu jawaban (ditutup di mode publik FIF_PUBLIC=1). */
export const feedback = (body: {
  question: string;
  answer: string;
  rating: "baik" | "buruk";
  mode: string;
  tool_calls: AskReply["tool_calls"];
}) => post<unknown>("/feedback", body);

/** URL gambar paper; backend menyajikannya dari analysis/figures/. */
export const figureUrl = (image: string) =>
  image.startsWith("http") ? image : `${API}${image}`;
