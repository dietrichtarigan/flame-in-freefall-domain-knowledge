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
export function useInsight() {
  const [data, setData] = useState<InsightData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    insight(ac.signal)
      .then(setData)
      .catch((e: unknown) => {
        if ((e as Error).name !== "AbortError") setError(String(e));
      });
    return () => ac.abort();
  }, []);

  return { data, error, loading: !data && !error };
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
