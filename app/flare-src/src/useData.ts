import { useEffect, useState } from "react";
import { insight, status, type InsightData } from "./api";

/**
 * Memuat paket data tampilan sekali, lalu dibagikan ke semua view.
 *
 * Sengaja tanpa nilai cadangan karangan: selama `data` masih null, tampilan
 * menampilkan keadaan memuat atau galat, bukan angka contoh. Mockup FLARE+
 * aslinya menuliskan angka sebagai teks keras -- itu berbahaya untuk dashboard
 * yang dinilai juri, karena angka salah tetap terlihat meyakinkan.
 */
// Satu permintaan untuk seluruh halaman: beberapa komponen (StatStrip, Overview,
// footer, view lain) memakai paket yang sama (~360 KB), jadi janji-nya dibagi.
// Bila gagal, janji dibuang supaya kunjungan view berikutnya mencoba lagi.
let insightPromise: Promise<InsightData> | null = null;
function loadInsight() {
  if (!insightPromise) {
    insightPromise = insight().catch((e) => {
      insightPromise = null;
      throw e;
    });
  }
  return insightPromise;
}

export function useInsight() {
  const [data, setData] = useState<InsightData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    loadInsight()
      .then((d) => alive && setData(d))
      .catch((e: unknown) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, []);

  return { data, error, loading: !data && !error };
}

/** Peta riset statis (scripts/research_map.py), disajikan di samping index.html. */
let mapPromise: Promise<any> | null = null;
export function useResearchMap() {
  const [map, setMap] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    if (!mapPromise) {
      mapPromise = fetch("research_map.json")
        .then((r) => (r.ok ? r.json() : Promise.reject(new Error("HTTP " + r.status))))
        .catch((e) => {
          mapPromise = null;
          throw e;
        });
    }
    mapPromise
      .then((m) => alive && setMap(m))
      .catch((e: unknown) => alive && setError(String(e)));
    return () => {
      alive = false;
    };
  }, []);
  return { map, error };
}

/** Status backend: dipakai untuk menandai apakah asisten memakai model atau mode luring. */
export function useStatus() {
  const [s, setS] = useState<{ llm: boolean; provider: string; model?: string } | null>(null);
  useEffect(() => {
    const ac = new AbortController();
    status(ac.signal)
      .then(setS)
      .catch(() => setS(null));
    return () => ac.abort();
  }, []);
  return s;
}

export const fmt = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : n.toLocaleString("en-US");
