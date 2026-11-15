/** Komponen bersama dan navigasi antar-view FLARE+. */
import React, { useEffect, useState } from "react";

export type EvidenceTier =
  | "nasa_table"
  | "nasa_calibrated"
  | "derived_auto"
  | "human_verified"
  | "paper_claim"
  | "model_prediction";

export type EvidenceRecord = {
  label: string;
  value: string;
  tier: EvidenceTier;
  source: string;
  path: string;
  note: string;
};

export type View =
  | "Overview"
  | "Scenario"
  | "Gaps"
  | "Investigations"
  | "Tests"
  | "WhatIf"
  | "Replay"
  | "Map"
  | "Quality"
  | "Assistant"
  | "Docs";

export function PageTitle({ index, overline, title, description }: {
  index: string;
  overline: string;
  title: string;
  description: string;
}) {
  return (
    <div className="page-title">
      <span>
        {index} / {overline}
      </span>
      <h1>{title}</h1>
      <p>{description}</p>
    </div>
  );
}

export function Panel({ title, meta, className = "", children, actions }: {
  title: string;
  meta?: string;
  className?: string;
  children: React.ReactNode;
  actions?: React.ReactNode;
}) {
  return (
    <section className={`panel ${className}`}>
      <header>
        <span>{title}</span>
        {meta && <small>{meta}</small>}
        {actions}
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}

/** Label tier (nasa table, derived auto, ...) sengaja tidak lagi ditampilkan sebagai
 *  lencana di setiap angka: terlalu ramai. Tier tetap ada di data dan di laci provenance. */
export function EvidenceBadge(_props: { tier: EvidenceTier | string }) {
  return null;
}

export function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (Array.isArray(value)) return value.map((item) => displayValue(item)).join(", ");
  if (typeof value === "object") {
    const record = value as Record<string, unknown>;
    if (typeof record.name === "string") {
      const count = record.n ?? record.count;
      return count === undefined ? record.name : `${record.name} (${displayValue(count)})`;
    }
    return Object.entries(record)
      .map(([key, item]) => `${key}: ${displayValue(item)}`)
      .join(", ");
  }
  return String(value);
}

export const pct = (v: number | null | undefined, d = 0) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : (v * 100).toFixed(d) + "%";

/* ---------------------------------------------------------- navigasi
 * Satu penyimpan kecil supaya view mana pun bisa membuka view lain dengan
 * konteks (mis. peringatan di Quality -> dosir uji di Tests, baris peringkat ->
 * kartu investigasi). App berlangganan dan mengganti view; view tujuan membaca
 * fokusnya. */
type Nav = { view: View | null; focus: string | null; seq: number };
let nav: Nav = { view: null, focus: null, seq: 0 };
const subs = new Set<(n: Nav) => void>();

export function go(view: View, focus: string | null = null) {
  nav = { view, focus, seq: nav.seq + 1 };
  subs.forEach((f) => f(nav));
}

export function useNav() {
  const [n, setN] = useState(nav);
  useEffect(() => {
    subs.add(setN);
    return () => {
      subs.delete(setN);
    };
  }, []);
  return n;
}

/** Fokus yang dikirim ke view ini (berubah tiap kali go() dipanggil untuk view ini). */
export function useFocus(view: View): string | null {
  const n = useNav();
  return n.view === view ? n.focus : null;
}

/** GET JSON dengan status muat/galat; null url = tidak memuat. */
export function useJSON<T = any>(url: string | null) {
  const [state, setState] = useState<{ data: T | null; error: string | null; loading: boolean }>({
    data: null,
    error: null,
    loading: !!url,
  });
  useEffect(() => {
    if (!url) {
      setState({ data: null, error: null, loading: false });
      return;
    }
    const ac = new AbortController();
    setState((s) => ({ ...s, loading: true, error: null }));
    fetch(url, { signal: ac.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e) => {
        if (e.name !== "AbortError") setState({ data: null, error: String(e), loading: false });
      });
    return () => ac.abort();
  }, [url]);
  return state;
}
