#!/usr/bin/env python3
"""Uji jalur mode Claude TANPA biaya: SDK anthropic diarahkan ke API tiruan (MockTransport httpx2).

Memeriksa:
  1. bentuk permintaan: model, header beta fallback, fallbacks="default", effort, cache_control,
     alat strict (additionalProperties false + required lengkap), tidak ada tool_choice paksa
  2. loop alat: tool_use -> tool_result (satu pesan user) -> jawaban akhir; blok thinking & fallback ikut
  3. aksi UI, sitasi, grounding, penjumlahan token, catatan fallback
  4. galat: 401 / 429 / koneksi -> jatuh ke luring dengan catatan; max_tokens tidak menjalankan alat terpotong

  python scripts/test_claude_mode.py
"""
import json
import os
import sys
from pathlib import Path

import httpx2
import anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["ANTHROPIC_API_KEY"] = "sk-ant-uji-tiruan"     # hanya untuk tiruan; tidak pernah dikirim ke Anthropic
import assistant  # noqa: E402

CAPTURED = []
SCRIPT = []          # antrean respons tiruan


def msg(content, stop, model="claude-opus-5-5"):
    return {"id": "msg_x", "type": "message", "role": "assistant", "model": model, "content": content,
            "stop_reason": stop, "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 80, "cache_read_input_tokens": 900, "cache_creation_input_tokens": 0}}


def handler(request):
    if request.url.path.endswith("/v1/models"):
        return httpx2.Response(200, json={"data": [{"id": "claude-opus-5-5", "type": "model", "display_name": "x",
                                                   "created_at": "2026-01-01T00:00:00Z"}], "has_more": False,
                                          "first_id": "claude-opus-5-5", "last_id": "claude-opus-5-5"})
    body = json.loads(request.content)
    CAPTURED.append({"headers": dict(request.headers), "body": body})
    kind, payload = SCRIPT.pop(0)
    if kind == "status":
        return httpx2.Response(payload, json={"type": "error", "error": {"type": "x", "message": "tiruan"}},
                               headers={"retry-after": "7"})
    if kind == "raise":
        raise httpx2.ConnectError("tiruan: jaringan putus")
    return httpx2.Response(200, json=payload)


def patch_client():
    real = anthropic.Anthropic

    def fake(*a, **k):
        k["http_client"] = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
        k["max_retries"] = 0
        return real(*a, **k)
    anthropic.Anthropic = fake


ok = True


def check(c, m):
    global ok
    print(("  LULUS  " if c else "  GAGAL  ") + m)
    ok &= bool(c)


patch_client()
assistant._AUTH.update(ok=None)
print("1. verifikasi kredensial (models.list, tanpa token)")
check(assistant.claude_available() == (True, ""), "claude_available() lolos lewat models.list tiruan")

print("2. pertanyaan dengan dua putaran alat + fallback")
SCRIPT[:] = [
    ("ok", msg([{"type": "thinking", "thinking": "", "signature": "sig"},
                {"type": "tool_use", "id": "tu_1", "name": "explain_test", "input": {"test": "21106G8"}},
                {"type": "tool_use", "id": "tu_2", "name": "ui_action",
                 "input": {"action": "focus", "payload_json": "\"21106G8\""}}], "tool_use")),
    ("ok", msg([{"type": "fallback", "from": {"model": "claude-opus-5-5"}, "to": {"model": "claude-opus-4-8"}},
                {"type": "text", "text": "Uji [[test:PSI-159:21106G8]] dicurigai positif palsu: O2 akhir G7 = awal G9 = "
                                         "0.207473561, jadi tidak ada oksigen terpakai [[model:gp_boundary_cfig_ign]]."}],
               "end_turn", model="claude-opus-4-8")),
]
r = assistant.ask("Kenapa uji 21106G8 dicurigai?", mode="claude")
check(r["mode"] == "claude", f"mode claude dipakai (catatan: {r['note']})")
b0 = CAPTURED[0]
check(b0["body"]["model"] == "claude-opus-5-5", "model claude-opus-5-5")
check("server-side-fallback-2026-07-01" in b0["headers"].get("anthropic-beta", ""), "header beta fallback dikirim")
check(b0["body"].get("fallbacks") == "default", "fallbacks='default'")
check(b0["body"].get("output_config") == {"effort": "medium"}, "effort medium eksplisit")
check(b0["body"]["system"][0].get("cache_control") == {"type": "ephemeral"}, "system di-cache")
check("tool_choice" not in b0["body"], "tidak ada tool_choice paksa (400 di Opus 5.5)")
check("thinking" not in b0["body"], "thinking tidak dikirim (adaptif bawaan; disabled = 400)")
ts = b0["body"]["tools"]
check(all(t.get("strict") and t["input_schema"]["additionalProperties"] is False and
          sorted(t["input_schema"]["required"]) == sorted(t["input_schema"]["properties"]) for t in ts),
      f"{len(ts)} alat strict dengan required lengkap")
b1 = CAPTURED[1]["body"]["messages"]
check(b1[-2]["role"] == "assistant" and any(c.get("type") == "thinking" for c in b1[-2]["content"]),
      "blok thinking dikembalikan utuh ke API")
tr = b1[-1]["content"]
check(b1[-1]["role"] == "user" and len(tr) == 2 and all(c["type"] == "tool_result" for c in tr),
      "dua tool_result dalam SATU pesan user")
check(any(u["action"] == "focus" and u["args"] == "test:PSI-159:21106G8" for u in r["ui_actions"]), "aksi UI fokus diteruskan")
check(r["grounding"]["ok"], f"grounding ok (angka diperiksa: {r['grounding']['numbers_checked']})")
check(any(c["kind"] == "test" and c["exists"] for c in r["citations"]), "sitasi test terselesaikan")
check(r["usage"]["input_tokens"] == 2400 and r["usage"]["cache_read_input_tokens"] == 1800, "token dijumlah lintas putaran")
check("fallback" in (r["note"] or "") and "claude-opus-4-8" in r["model"], f"fallback dilaporkan: {r['note']}")

print("3. jawaban dengan angka karangan")
SCRIPT[:] = [("ok", msg([{"type": "text", "text": "Laju bakar rata-rata 0.987 mm2/s."}], "end_turn"))]
r = assistant.ask("berapa laju bakar?", mode="claude")
check(not r["grounding"]["ok"] and "0.987" in r["grounding"]["ungrounded"], "angka tanpa sumber tertangkap")

print("4. galat API -> luring dengan catatan")
for kind, payload, expect in (("status", 401, "kredensial ditolak"), ("status", 429, "batas laju"),
                              ("status", 500, "API galat 500"), ("raise", None, "koneksi")):
    SCRIPT[:] = [(kind, payload)]
    assistant._AUTH.update(ok=True, t=1e18, src="ANTHROPIC_API_KEY")   # lewati verifikasi supaya galat muncul saat bertanya
    r = assistant.ask("Kenapa uji 21106G8 dicurigai?", mode="claude")
    check(r["mode"] == "offline" and expect in (r["note"] or ""), f"{kind} {payload or ''} -> luring: {r['note']}")

print("5. max_tokens tidak menjalankan alat terpotong")
SCRIPT[:] = [("ok", msg([{"type": "text", "text": "Sebagian"}, {"type": "tool_use", "id": "tu_9", "name": "ui_action",
                                                                    "input": {"action": "focus", "payload_json": "\"21106G7\""}}], "max_tokens"))]
assistant._AUTH.update(ok=True, t=1e18, src="ANTHROPIC_API_KEY")
r = assistant.ask("x", mode="claude")
check(not r["ui_actions"] and "terpotong" in (r["note"] or ""), "alat tidak dijalankan; catatan terpotong")

print("\nHASIL:", "SEMUA LULUS" if ok else "ADA YANG GAGAL")
sys.exit(0 if ok else 1)
