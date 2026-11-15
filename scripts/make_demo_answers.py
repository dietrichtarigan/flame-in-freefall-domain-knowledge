"""Contoh jawaban asisten untuk tab Assistant di FLARE+ (dibuat sekali dengan model sungguhan).

Pengunjung melihat jawaban NYATA yang sudah dijalankan -- lengkap dengan alat yang
dipanggil, sitasi, gambar/rumus paper, plot dan laporan grounding -- tanpa menunggu
dan tanpa biaya API. Setiap contoh mencatat tanggal dan model yang menjawabnya.

  python scripts/make_demo_answers.py      -> app/flare-src/public/demo_answers.json
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import assistant  # noqa: E402

DEMOS = [
    ("moon", "Moon base at 30% O₂", "Could a PMMA rod keep burning on a Moon base at 30% oxygen and 70 kPa? Show how the limit changes with gravity."),
    ("equation", "Formula from a paper", "Show me the equation for opposed-flow flame spread rate over a thin solid, and explain its variables."),
    ("rank", "Rank for a habitat", "Which NASA investigations matter most for a Moon or Mars base, and why?"),
    ("figure", "Figures from papers", "What does a flame spreading over PMMA look like in microgravity? Show figures from the papers."),
    ("plot", "Plot real data", "Plot the SPICE smoke-point data and tell me what the trend is."),
]


def main():
    out = []
    for key, label, q in DEMOS:
        t0 = time.time()
        r = assistant.ask(q, [], {}, "deepseek")
        print(f"{key}: {r['mode']} {len(r.get('figures') or [])} fig {len(r.get('plots') or [])} plot "
              f"grounded={r['grounding']['ok']} {time.time() - t0:.0f}s tools={[c['name'] for c in r['tool_calls']]}")
        out.append({"key": key, "label": label, "question": q, "asked": time.strftime("%Y-%m-%d"),
                    "model": r.get("model") or assistant.llm_model(),
                    "reply": {k: r.get(k) for k in ("answer", "mode", "tool_calls", "citations", "grounding", "figures", "plots")}})
    dst = ROOT / "app" / "flare-src" / "public" / "demo_answers.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, default=str), encoding="utf-8")
    print("->", dst)


if __name__ == "__main__":
    main()
