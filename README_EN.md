# FLARE+ (Flame in Freefall) — Domain Knowledge & Analysis Pipeline

A derived evidence layer built from NASA's microgravity combustion data (Physical Sciences Informatics / PSI, NASA Technical Reports Server / NTRS, and peer-reviewed journal papers). This repository contains **analysis-ready datasets and the reproducible scripts that built them** — not the raw ~15.6 GB archive.

* **Live Interactive App:** [https://flame-in-freefall-wfbl.onrender.com/insight/](https://flame-in-freefall-wfbl.onrender.com/insight/)
* **Data License:** PSI source data is **CC0** (Public Domain). This repository is an independent project and is not affiliated with or endorsed by NASA.

---

## Where to Start

The single most useful file in this repository is **`kb/gold/freefall.sqlite`** (9 tables).

Because the uncompressed database is 101 MB—exceeding GitHub's strict 100 MiB file limit—the repository stores the compressed archive **`freefall.sqlite.gz`** (34 MB). Decompress it once before querying:

```bash
gunzip -k kb/gold/freefall.sqlite.gz      # -k keeps the original .gz file

# On Windows without gunzip:
python -c "import gzip,shutil; shutil.copyfileobj(gzip.open(r'kb/gold/freefall.sqlite.gz','rb'), open(r'kb/gold/freefall.sqlite','wb'))"
```

Once extracted, inspect it with DB Browser for SQLite, DuckDB, or Python:

```python
import sqlite3, pandas as pd
con = sqlite3.connect("kb/gold/freefall.sqlite")
pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", con)
```

### Database Schema (`freefall.sqlite`)

| Table | Rows | Contents |
|---|---|---|
| `tests` | 1,990 | Standardized test records across 24 PSI investigations; `raw_json` preserves all original columns |
| `telemetry` | 943 | ACME tests mined from raw 125 Hz sensor telemetry — **not tabulated in NASA's tables** |
| `video_episodes` | 139 | BASS / BASS-II flame episodes extracted via video analysis — **not tabulated in NASA's tables** |
| `investigations` | 24 | Catalog of objectives, hypotheses, flight hardware, and DOIs |
| `publications` | 352 | NASA-indexed publications mapped per investigation |
| `papers`, `papers_doi` | 695 / 295 | NTRS technical reports and DOI-indexed journal papers |
| `paper_chunks` + `paper_search` | 7,924 | Page-level extracted paper text + **FTS5** full-text search index |
| `files` | 16,372 | Complete manifest of all PSI files with SHA-256 checksums |

Example full-text search query:

```sql
SELECT paper_uid, page, snippet(paper_search, 2, '[', ']', '...', 12)
FROM paper_search WHERE paper_search MATCH 'PMMA AND spread' LIMIT 10;
```

---

## Repository Structure

| Folder | Contents |
|---|---|
| `kb/gold/` | Gold-standard SQLite database, ready-to-use CSVs, and `data_dictionary.md` |
| `kb/clean/` | Standardized per-investigation test tables preserving original columns |
| `kb/manifest/` | Download manifests and SHA-256 checksums (used to re-fetch raw data) |
| `analysis/telemetry/` | Mined ACME sensor telemetry outputs and methodology notes |
| `analysis/video_full/` | Video-derived flame episodes + **PNG visual proof sheets** |
| `analysis/saffire/`, `analysis/ml/` | Saffire spacecraft burn analysis and predictive ML models |
| `scripts/` | End-to-end data pipelines, from ingestion to database construction |
| `app/` | Interactive web dashboard (run via local server; see below) |
| `docs/` | Technical specifications, including the 3D visualization pipeline |

---

## Re-Fetching Raw Data (Optional, ~15.6 GB)

Raw files are excluded from Git tracking due to size, but can be fully reproduced from scratch:

```bash
python scripts/psi_fetch.py --dry-run   # Fetch metadata and manifests first
python scripts/psi_fetch.py             # Download files <= 10 MB (~6.8 GB)
python scripts/ntrs_fetch.py            # Fetch NTRS technical reports
python scripts/build_kb.py              # Rebuild freefall.sqlite from scratch
```

Requires **Python 3.9+**. `build_kb.py` uses `pymupdf` when installed to extract PDF text; if omitted, PDF text extraction is skipped and the remaining tables still build cleanly.

---

## Running the Dashboard Locally

Files inside `app/` load `data.json` via `fetch()`, so they must be served over HTTP rather than opened directly via `file://`:

```bash
cd app && python -m http.server 8000
```

Then open `http://localhost:8000/insight/index.html` in your browser (or visit the live deployment at `https://flame-in-freefall-wfbl.onrender.com/insight/`).

---

## Important Caveats Before Using the Numbers

1. **Telemetry values are raw sensor voltages, not SI physical units.** `tc_burner_rise_v` records thermocouple voltage rise in **volts**, not degrees Celsius. It is valid for relative comparisons across tests, but must not be displayed as calibrated temperature.
2. **Telemetry flame detection is validated at 93.8% accuracy** against NASA's `ignited` label across 320 CFI-G tests (vs. an 81.9% majority-class baseline). Rows flagged with `signal_strength = weak` (117 tests) denote low-amplitude signals that warrant manual review.
3. **Video-derived flame durations have unquantified timing uncertainty.** Only one test (`T16`) was re-recorded in full. Inspect `analysis/video_full/proof/` before relying on duration figures.
4. **Null/empty values indicate unreported measurements, not zero.**
5. **All records represent microgravity (`0g`) conditions.** NASA PSI does not yet contain long-duration partial-gravity (`0.16g` Lunar or `0.38g` Martian) combustion datasets.

Detailed methodologies and documented dead-ends—including approaches we tested and discarded along with the reasons why—are recorded in `analysis/*/README.md`.

---

## Super Intelligence (SI) & AI Disclosure

* **In-Product Models & Assistant:** FLARE+ integrates Gaussian Process boundary modeling, `scikit-learn`/`PyTorch` ignition and extinction classifiers, and an Anthropic Claude-powered conversational assistant ("Ask the data") that grounds responses against the verified SQLite knowledge base.
* **Development Assistance:** Large Language Models (LLMs) were used during development to assist with code debugging, pipeline refactoring, and cross-referencing NTRS technical documentation.