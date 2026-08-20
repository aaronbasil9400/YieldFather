# Architecture

## Current structure

```text
Home.py
  ├─ pages/1_Yield_Report.py ── runpy ──► Yield_Report.py
  │                                      ├─ pandas CSV loader
  │                                      ├─ PN/process mapping
  │                                      └─ Streamlit + Plotly UI
  └─ pages/2_SPC_Dashboard.py ─ runpy ──► SPC_DASHBOARD.py
                                         ├─ TDF parser
                                         ├─ CSV + SQLite consolidator
                                         ├─ cached SQLite queries
                                         ├─ numeric statistics
                                         └─ Streamlit + Plotly UI

theme_utils.py ───────────────────────────────► shared Streamlit/Plotly styling
```

`run.bat` changes to the project directory and launches `python -m streamlit run Home.py`. It assumes Python and Streamlit already exist on the user’s PATH.

## Yield pipeline

1. `load_data` reads uploaded CSV or `rptTestDetail.csv`, normalizes selected text fields, parses two dates, assigns a part number, product, and process group.
2. `filter_data` applies PN, product, process, station, and date filters.
3. `station_metrics`, `daily_weekly_summary`, `top_defects_28d`, and `wip_analysis` create data frames for the UI.
4. Plotly charts and Streamlit tables offer exports.

### Coupling to address

- `Yield_Report.py` runs Streamlit setup and UI logic at import time, which makes isolated testing difficult.
- `PART_MASTER` and process routing are embedded in code rather than a versioned business configuration file.
- The default sample CSV is a sizable operational dataset; it should not become the sole regression fixture.

## SPC pipeline

1. `parse_tdf_file` reads a TDF file: header, board configuration, then pipe-separated test data.
2. Folder names are parsed for source context in `find_ancestor_folders`, `parse_root_folder`, `parse_step_folder`, and `parse_run_timestamp`.
3. `iter_output_rows` combines folder/header/board/test fields and converts selected numeric fields.
4. `run_consolidation` writes `results.csv` and rebuilds a SQLite `test_results` table with selected indexes.
5. Cached query helpers get slicer values and retrieve a time-ordered, capped data frame.
6. `compute_stats` and chart functions render the dashboard.

### Ingestion assumptions

- Folder placement is meaningful: the code takes the four parent folders above a TDF file as bin, unit/run, test-step, and timestamp.
- Only files matching `*Data*.tdf` are parsed.
- Data rows with fewer than the fixed columns are silently skipped.
- A database is rebuilt by `DROP TABLE`/`CREATE TABLE`; an interrupted run can leave no usable previous table.

## Risks in the current design

| Risk | Why it matters | Direction |
| --- | --- | --- |
| UI, parsing, and statistics share large modules | Hard to test and package safely | Extract import-safe domain, ingestion, storage, and UI layers. |
| Unpinned dependencies | Rebuilds can change behavior | Lock dependencies and record build provenance. |
| User path fields | Typing errors and permissions are common | Use native file/folder pickers and writable app-data defaults. |
| SQLite rebuild in place | A failed run can destroy usable output | Validate a temporary DB and atomically replace it. |
| Cached open connections | A replaced DB may be locked or stale | Define connection lifecycle and cache invalidation. |
| Arbitrary row cap | A KPI may describe only an undocumented prefix of the filtered data | Report total/query-returned counts and block or aggregate safely. |

## Target architecture

```text
desktop launcher / UI adapter
             │
             ├── application services (orchestration, exports, user settings)
             ├── domain (yield, defects, SPC, validation)  ← no Streamlit imports
             ├── ingestion (CSV and TDF parsers)
             └── infrastructure (SQLite, file locations, logging)
```

This separation keeps the current Streamlit front end viable during migration while allowing a packaged Streamlit launcher or a future native desktop UI to use the same validated calculations.
