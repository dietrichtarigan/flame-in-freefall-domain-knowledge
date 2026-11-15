#!/usr/bin/env bash
# One-command setup check: dependencies -> source PDF check -> pipeline (extract, cross-check, records, build, validate) -> tests.
# Usage: CHROME=/path/to/chrome ./setup_and_test.sh
set -euo pipefail
cd "$(dirname "$0")"
CHROME="${CHROME:-$(command -v google-chrome || command -v chromium || command -v chromium-browser || true)}"
fail() { echo "ERROR: $*" >&2; exit 1; }
command -v python3 >/dev/null || fail "python3 not found"
command -v pdftotext >/dev/null || fail "pdftotext not found (install poppler-utils / brew install poppler)"
[ -n "$CHROME" ] || fail "Chrome/Chromium not found; set CHROME=/path/to/chrome"
python3 -c "import playwright, pytest, jsonschema, pdfplumber, PIL, rocrate_validator" 2>/dev/null || fail "run: python3 -m pip install -r requirements.txt   (no Playwright browser download needed)"
PDF=sources/original/NASA-TP-2015-216046.pdf
[ -f "$PDF" ] || fail "missing $PDF (download NASA/TP-2015-216046, NTRS 20150023456, and place it there)"
EXPECT=$(grep 'NASA-TP-2015-216046.pdf' SOURCE_CHECKSUMS.sha256 | awk '{print $1}')
ACTUAL=$( (sha256sum "$PDF" 2>/dev/null || shasum -a 256 "$PDF") | awk '{print $1}')
[ "$EXPECT" = "$ACTUAL" ] || fail "PDF hash mismatch (expected $EXPECT, got $ACTUAL): wrong or modified file"
./tools/run_pipeline.sh
CHROME="$CHROME" python3 -m pytest -q tests
echo "OK: open dist/open_flex_lab.html"
