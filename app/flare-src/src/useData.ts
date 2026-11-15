import { useEffect, useState, useSyncExternalStore } from "react";
import { insight, status, type InsightData } from "./api";

/**
 * Memuat paket data tampilan sekali, lalu dibagikan ke semua view.
 *
 * Sengaja tanpa nilai cadangan karangan: selama `data` masih null, tampilan
 * menampilkan keadaan memuat atau galat, bukan angka contoh. Mockup FLARE+
 * aslinya menuliskan angka sebagai teks keras -- itu berbahaya untuk dashboard
 * yang dinilai juri, karena angka salah tetap terlihat meyakinkan.
 */
// Satu sumber bersama untuk seluruh halaman (pola dari referensi mobile nasa3):
// beberapa komponen memakai paket yang sama (~360 KB), jadi dimuat sekali dan
// dibagikan lewat useSyncExternalStore. retry() memuat ulang setelah koneksi
// putus; data yang sudah termuat tetap tampil selama mencoba lagi.
type LoadState<T> = { data: T | null; loading: boolean; error: string | null };

function createResource<T>(loader: (signal?: AbortSignal) => Promise<T>) {
  let state: LoadState<T> = { data: null, loading: false, error: null };
  let controller: AbortController | null = null;
  const listeners = new Set<() => void>();
  const emit = () => listeners.forEach((l) => l());
  const load = () => {
    controller?.abort();
    controller = new AbortController();
    state = { ...state, loading: true, error: null };
    emit();
    loader(controller.signal)
      .then((data) => {
        state = { data, loading: false, error: null };
        emit();
      })
      .catch((e: unknown) => {
        if ((e as Error)?.name === "AbortError") return;
        state = { ...state, loading: false, error: String(e) };
        emit();
      });
  };
  return {
    subscribe: (l: () => void) => {
      listeners.add(l);
      return () => {
        listeners.delete(l);
      };
    },
    snapshot: () => state,
    load,
    ensure: () => {
      if (!state.data && !state.loading && !state.error) load();
    },
  };
}

const insightResource = createResource<InsightData>(insight);

export function useInsight() {
  const st = useSyncExternalStore(insightResource.subscribe, insightResource.snapshot, insightResource.snapshot);
  useEffect(insightResource.ensure, []);
  return { data: st.data, error: st.error, loading: st.loading || (!st.data && !st.error), retry: insightResource.load };
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
  const [s, setS] = useState<{ llm: boolean; provider: string; model?: string; public?: boolean } | null>(null);
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
