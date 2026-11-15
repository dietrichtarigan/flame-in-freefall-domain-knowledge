"""Pasang lab Open FLEX ke FLARE+ dengan tampilan yang menyatu dengan dashboard.

Open FLEX (proyek terpisah) dibangun menjadi satu file HTML offline. Skrip ini mengambil
file itu apa adanya lalu:
  1. membuang bagian yang merupakan catatan proyek, bukan konten untuk pengguna
     (panel "Removed in Phase B and why", "Validation label policy", rencana milestone);
  2. memasang "kulit" FLARE+: palet hangat gelap, aksen amber, Poppins / IBM Plex Mono,
     sudut tegas, tanpa bayangan; kepala aplikasi Open FLEX disembunyikan karena FLARE+
     sudah punya kepala sendiri;
  3. memaksa tema gelap (juga saat dibuka layar penuh).
Semua warna lab adalah variabel CSS, jadi kulit cukup menimpa variabel di [data-theme="dark"].

  python scripts/integrate_openflex.py <path/ke/open_flex_lab.html>
  -> app/flare-src/public/openflex/index.html   (lalu: cd app/flare-src && npx vite build)
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "app" / "flare-src" / "public" / "openflex" / "index.html"

SKIN = """
<style id="flare-skin">
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Poppins:wght@300;400;500;600&display=swap");
html[data-theme="dark"], html {
  --bg: #161513; --surface: #1f1e1a; --surface-2: #26241f;
  --border: rgba(232, 227, 216, 0.14); --border-strong: rgba(232, 227, 216, 0.26);
  --text: #e8e3d8; --text-muted: rgba(232, 227, 216, 0.66); --text-faint: rgba(232, 227, 216, 0.46);
  --accent: #d4874d; --accent-weak: rgba(212, 135, 77, 0.14); --link: #e0a26f;
  --ok: #a6b86a; --ok-bg: rgba(166, 184, 106, 0.12); --warn: #e2b84a; --warn-bg: rgba(226, 184, 74, 0.12);
  --danger: #e07a6c; --danger-bg: rgba(224, 122, 108, 0.12); --info: #65c6d1; --info-bg: rgba(101, 198, 209, 0.1);
  --violet: #b38be0; --violet-bg: rgba(179, 139, 224, 0.12);
  --scene-bg: #12110f; --plot-bg: #1f1e1a; --plot-grid: rgba(232, 227, 216, 0.08); --plot-text: #c9c2b4;
  --s1: #65c6d1; --s2: #e0894f; --s3: #a6b86a;
  --radius: 2px; --shadow: none;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}
html { font-size: 14px; }
body { background: transparent; font-family: "Poppins", system-ui, sans-serif; }
/* kepala Open FLEX: judul, build dan tombol tema sudah tidak perlu di dalam FLARE+ */
.brand, #btn-theme, .skip-link { display: none !important; }
.app-header { background: #1a1916; padding: 10px 16px 0; border-bottom: 1px solid var(--border); }
.header-row { justify-content: flex-start; }
.test-picker label, .run-meta-box { font: 500 10px "IBM Plex Mono", monospace; letter-spacing: .08em; text-transform: uppercase; color: var(--text-faint); }
.run-meta-box { text-transform: none; letter-spacing: 0; }
select, input, textarea {
  background: rgba(0, 0, 0, 0.3); color: var(--text); border: 1px solid var(--border-strong); border-radius: 2px;
  font: 13px "Poppins", sans-serif; min-height: 32px;
}
.scope-strip { gap: 8px; }
.badge {
  background: transparent !important; border: 1px solid var(--border-strong) !important; border-radius: 2px !important;
  color: var(--text-muted) !important; font: 500 9.5px "IBM Plex Mono", monospace !important; letter-spacing: .08em;
}
.badge-danger { border-color: rgba(224, 122, 108, .55) !important; color: #e07a6c !important; }
.badge-warn { border-color: rgba(226, 184, 74, .55) !important; color: #e2b84a !important; }
.tab-btn { font: 500 13px "Poppins", sans-serif; color: var(--text-muted); padding: 11px 16px; }
.tab-btn[aria-selected="true"] { color: var(--text); border-bottom-color: var(--accent); }
.workspace { padding: 16px 16px 32px; }
.panel { background: rgba(31, 30, 26, 0.92); border-radius: 2px; box-shadow: none; }
.panel-header { padding: 0 16px; min-height: 46px; }
.panel-title { font: 500 13px "Poppins", sans-serif; color: var(--text); display: flex; align-items: center; gap: 8px; }
.panel-title::before { content: ""; width: 4px; height: 4px; border-radius: 50%; background: #65c6d1; flex: 0 0 auto; }
.panel-body { padding: 16px 18px; }
th { font: 500 10px "IBM Plex Mono", monospace; letter-spacing: .06em; text-transform: uppercase; color: var(--text-faint); }
td { color: var(--text-muted); }
.btn, .mode-btn {
  border-radius: 2px; box-shadow: none; font: 500 11px "Poppins", sans-serif; letter-spacing: .06em; text-transform: uppercase;
  background: transparent; color: var(--text); border: 1px solid var(--border-strong);
}
.btn:hover, .mode-btn:hover { border-color: var(--accent); }
.btn-primary, .mode-btn.active, .mode-btn[aria-checked="true"] { background: #65c6d1 !important; color: #10201f !important; border-color: #65c6d1 !important; }
.btn-emerald { background: transparent !important; color: var(--accent) !important; border-color: var(--accent) !important; }
.alert-box { border-radius: 2px; }
.stat .num { font-weight: 300; color: var(--text); }
.app-footer { background: transparent; color: var(--text-faint); border-top: 1px solid var(--border); font-size: 11px; }
input[type="range"] { accent-color: var(--accent); background: none; border: 0; }
::-webkit-scrollbar { width: 7px; height: 7px; }
::-webkit-scrollbar-thumb { background: rgba(101, 198, 209, 0.34); }
</style>
"""

FORCE_DARK = """
<script id="flare-force-dark">
/* FLARE+ selalu gelap: tema lab dikunci ke "dark" (juga bila browser menyimpan "light"). */
(function () {
  function lock() {
    if (!window.OF || !OF.applyTheme || OF.__flareDark) return false;
    var apply = OF.applyTheme;
    OF.applyTheme = function () { apply("dark"); };
    OF.__flareDark = true;
    apply("dark");
    try { localStorage.setItem("openflex-theme", "dark"); } catch (e) {}
    if (OF.state && OF.state.testId && OF.selectTest) OF.selectTest(OF.state.testId);
    return true;
  }
  document.documentElement.setAttribute("data-theme", "dark");
  if (!lock()) document.addEventListener("DOMContentLoaded", lock);
  window.addEventListener("load", function () { lock(); });
})();
</script>
"""

REMOVE_SECTIONS = ["rm-h", "val-h"]  # "Removed in Phase B and why", "Validation label policy"
REMOVE_TEXT = [
    (r"\s*a validated RO-Crate export is planned for M6\.", ""),
    (r"It is not an RO-Crate;", "It is not an RO-Crate."),
    (r'<p class="sub-note" data-interpretive="removal note">.*?</p>', ""),
]


def main(src):
    html = Path(src).read_text(encoding="utf-8")
    n0 = len(html)
    for sid in REMOVE_SECTIONS:
        pat = re.compile(r'<section class="panel" aria-labelledby="%s">.*?</section>' % sid, re.S)
        html, k = pat.subn("", html)
        print(f"panel {sid}: {k} removed")
    for pat, rep in REMOVE_TEXT:
        html, k = re.subn(pat, rep, html, flags=re.S)
        print(f"text {pat[:40]!r}: {k}")
    assert "Removed in Phase B" not in html, "Phase B section still present"
    html = html.replace("</head>", SKIN + "</head>", 1)
    i = html.rfind("</body>")
    html = html[:i] + FORCE_DARK + html[i:]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    print(f"{n0} -> {len(html)} bytes -> {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
