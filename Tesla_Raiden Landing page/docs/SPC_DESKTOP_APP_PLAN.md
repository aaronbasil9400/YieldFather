# SPC Desktop App Plan

Companion to [PORTABILITY_PLAN.md](PORTABILITY_PLAN.md). Turns the SPC dashboard into a standalone portable Windows desktop app while keeping the existing Streamlit app working.

## Confirmed decisions

| Decision | Choice |
| --- | --- |
| UI toolkit | PySide6 (native Qt window, no browser) |
| Charts | pyqtgraph (interactive control chart and histogram) |
| Packaging | Portable folder via PyInstaller (embedded Python, double-click launcher; no signing/installer yet) |
| Code layout | Shared import-safe core (`spc_core/`) used by BOTH the desktop app and the existing Streamlit `SPC_DASHBOARD.py` |

## Architecture

```text
spc_core/                     Streamlit-free, import-safe domain package
  tdf_parser.py               FIXED_COLUMNS, HEADER_KEYS, folder regexes,
                              parse_tdf_file, folder-context helpers,
                              safe_float, is_dut_partnum, iter_output_rows
  consolidation.py            OUTPUT_COLUMNS, run_consolidation with
                              temporary DB + CSV plus atomic replacement
  query.py                    build_where_clause, get_columns,
                              get_distinct_values, get_testnb_label_pairs,
                              get_dataset_summary, query_filtered
  stats.py                    compute_stats (unchanged formulas)

spc_app/                      PySide6 desktop application
  main.py                     entry point: QApplication + MainWindow
  workers.py                  QThread consolidation worker (progress signals)
  widgets/                    filter panel, KPI cards, tables
  charts.py                   pyqtgraph control chart + histogram builders

SPC_DASHBOARD.py              Streamlit UI becomes a thin adapter over spc_core;
                              st.cache_* wrappers stay in this layer only
```

No Streamlit or PySide6 imports are allowed inside `spc_core`.

## Implementation steps

### Step 1 - Extract `spc_core`

1. Move TDF parsing, folder-context parsing, and row generation verbatim into `tdf_parser.py`.
2. Move consolidation into `consolidation.py`. Change required by AGENTS.md: write DB and CSV to temporary files in the target directory and `os.replace` them on success so an interrupted run can never destroy a previous usable output.
3. Move query helpers and `build_where_clause` into `query.py` as plain functions (caching stays in each UI layer).
4. Move `compute_stats` unchanged into `stats.py`.
5. Add deterministic unit tests per TEST_STRATEGY.md minimums: empty input, one sample, zero variation, one-sided limits, changing limits, nonnumeric values, malformed TDF lines, DUT part-number matching.

### Step 2 - Rewire the Streamlit page

1. `SPC_DASHBOARD.py` imports from `spc_core`; duplicated parser/stats/query code is deleted.
2. Plotly chart builders and theme stay in the Streamlit layer.
3. UI behavior must remain identical: same slicers, warnings on mixed TestNb/Channel populations, KPI set, exports.

### Step 3 - Build the PySide6 app

1. Main window: left control panel (data source mode TDF-folder vs existing-DB, native folder pickers, Run Consolidator button, row cap), filter panel (broad TestNb select, fine TestNb-TestLabel pairs, primary slicers, collapsible secondary filters), results area.
2. Results area replicates the Streamlit output: 10 KPI cards (Cpk, Cp, Sigma Level, Min, Max, Mean, StdDev, N, % Out of Spec, % PASS rows), SPC control chart with mean/UCL/LCL/USL/LSL lines and red/amber/green point coloring, histogram, Cpk-by-group table, raw filtered table with CSV export.
3. Population guard preserved: warn when filters span multiple TestNb or Channel values.
4. Consolidation runs on a worker thread with progress/log feedback; UI stays responsive; errors surface as dialog messages.
5. Writable-output rule: default output directory resolves under the OS user-data folder when running frozen; bundled resources resolve relative to the executable, never the working directory.

### Step 4 - Package portable Windows bundle

1. Pin runtime/build dependencies (PySide6, pyqtgraph, numpy, pandas, pyinstaller) in a lock file before first build.
2. PyInstaller spec produces an onedir bundle: embedded interpreter, `spc_core`, `spc_app`, assets.
3. Launcher exe opens the window directly (no console, no browser).
4. Smoke test checklist from PORTABILITY_PLAN.md: launch by double-click, consolidate a fixture TDF tree, load existing DB, filter, chart, export CSV, error dialogs for bad paths, works from a path with spaces and a non-admin account.

## Constraints honored

- KPI definitions and statistical formulas are moved, not changed; any future formula change follows the DATA_AND_KPIS.md workflow.
- `DEFAULT_DUT_PARTNUMBERS`, folder-name assumptions, and TDF rules are carried over untouched.
- No generated databases, CSV outputs, logs, or `__pycache__` are committed.
- One artifact per OS; this phase targets Windows only.

## Open items

- Dependency version lock values (record at first successful build).
- App icon/version metadata for the executable.
- macOS/Linux builds deferred to PORTABILITY_PLAN.md Phase 3.
