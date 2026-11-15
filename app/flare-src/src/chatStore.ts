/**
 * Satu percakapan untuk seluruh FLARE+: halaman AI Assistant dan bola "Ask FLARE+" di
 * kanan bawah memakai thread yang SAMA. Pertanyaan dari bola langsung terlihat di halaman
 * penuh, dan "Open full assistant" melanjutkan thread itu, bukan memulai dari nol.
 */
import { useSyncExternalStore } from "react";
import { ask as askApi, type AskReply } from "./api";

export type Msg = { role: "user" | "assistant"; text: string; pending?: boolean; failed?: boolean; reply?: AskReply; q?: string };

type State = { messages: Msg[]; busy: boolean };

const WELCOME: Msg = {
  role: "assistant",
  text:
    "Ask about investigations, experimental conditions, publications, or evidence gaps. " +
    "Every number in my answer is checked against the tool output that produced it.",
};

let state: State = { messages: [WELCOME], busy: false };
const subs = new Set<() => void>();
const set = (s: Partial<State>) => {
  state = { ...state, ...s };
  subs.forEach((f) => f());
};

export async function sendChat(question: string) {
  const q = question.trim();
  if (!q || state.busy) return;
  const before = state.messages;
  // Backend (brain.py clean_history) menerima pasangan {q, a}.
  const history: { q: string; a: string }[] = [];
  before.forEach((m, i) => {
    const next = before[i + 1];
    if (m.role === "user" && next?.role === "assistant" && !next.pending && !next.failed) history.push({ q: m.text, a: next.text });
  });
  set({ busy: true, messages: [...before, { role: "user", text: q }, { role: "assistant", text: "", pending: true }] });
  try {
    const reply: AskReply = await askApi(q, history);
    set({ messages: [...state.messages.slice(0, -1), { role: "assistant", text: reply.answer, reply, q }] });
  } catch (e) {
    set({
      messages: [
        ...state.messages.slice(0, -1),
        {
          role: "assistant",
          text:
            "The backend did not answer (" + String(e) + "). Nothing is shown rather than a guess; " +
            "the public deployment also limits questions per visitor.",
          failed: true,
        },
      ],
    });
  } finally {
    set({ busy: false });
  }
}

export function clearChat() {
  if (!state.busy) set({ messages: [WELCOME] });
}

export function useChat() {
  return useSyncExternalStore(
    (f) => {
      subs.add(f);
      return () => {
        subs.delete(f);
      };
    },
    () => state,
    () => state,
  );
}
