#!/usr/bin/env bash
# Rebuild every derived artefact from the source PDF, in dependency order, then validate.
# Order: extract -> verify -> digitize -> analyze -> cross-check -> records -> build (manifest) -> validate
#   ./tools/run_pipeline.sh            extraction -> cross-checks -> records -> app build -> validation
#   ./tools/run_pipeline.sh --properties  also regenerate the D²-law property table (needs CoolProp 8.0.0)
#   ./tools/run_pipeline.sh --verify   also re-run the page-image checks of Table IX and Tables I-VIII (~9 min, needs tesseract)
# The visual-review file data/verification/table_ix_manual_review.json is hand-made and is not regenerated;
# if --verify finds disagreements not covered by it, the unit tests fail until they are reviewed.
set -euo pipefail
cd "$(dirname "$0")/.."
PDF=sources/original/NASA-TP-2015-216046.pdf
python3 -I tools/extract_table_ix.py "$PDF" data/extracted/table_ix.csv
python3 -I tools/extract_appendix_b_index.py "$PDF" data/extracted/appendix_b_figures.csv
python3 -I tools/extract_test_matrix.py "$PDF" data/extracted/test_matrix.csv
python3 -I tools/verify_test_matrix.py "$PDF" . > /dev/null
if [ "${1:-}" = "--verify" ]; then
  python3 -I tools/verify_table_ix.py "$PDF" .
  python3 -I tools/verify_test_matrix_images.py "$PDF" .
fi
for c in data/digitization/configs/*.json; do python3 -I tools/digitize_figure.py "$PDF" "$c" . > /dev/null; done
for c in data/digitization/configs/*.json; do
  t=$(python3 -I -c "import json,sys; print(json.load(open(sys.argv[1]))['test_id'])" "$c")
  python3 -I tools/analyze_d2_fit.py . "$t" > /dev/null
done
python3 -I tools/crosscheck_tables.py . > /dev/null
# D²-law educational baseline: property table only with --properties (needs CoolProp 8.0.0), then verification and runs
if [ "${1:-}" = "--properties" ]; then python3 -I tools/build_model_properties.py .; fi
python3 -I tools/verify_d2law.py . > /dev/null
python3 -I tools/run_d2law_baseline.py . > /dev/null
python3 -I tools/build_records.py .
python3 -I tools/build_app.py
python3 -I tools/validate_data.py
python3 -I tools/build_rocrate.py .
python3 tools/validate_rocrate.py . --severity required > /dev/null 2>&1 || { echo "RO-Crate 1.2 validation failed: python3 tools/validate_rocrate.py ."; exit 1; }
