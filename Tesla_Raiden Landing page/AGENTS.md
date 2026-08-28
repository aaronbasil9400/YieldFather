1: # Agent Guide
2: 
3: ## Mission
4: 
5: Maintain and evolve Factory Analytics Hub as a local, reliable factory-data application. Preserve raw data, make every KPI definition explicit, and move the product toward a no-Python-setup desktop release.
6: 
7: Read [README.md](README.md), [docs/PROJECT_SCOPE.md](docs/PROJECT_SCOPE.md), and [docs/STATISTICAL_VALIDATION.md](docs/STATISTICAL_VALIDATION.md) before changing calculation, ingestion, or packaging code.
8: Read [docs/ANALYTICS_ROADMAP.md](docs/ANALYTICS_ROADMAP.md) before adding a chart, heatmap, drift/correlation analysis, or user-facing insight.
9: 
10: ## Fast orientation
11: 
12: | Area | Primary file | Notes |
13: | --- | --- | --- |
14: | Landing/navigation | `Home.py`, `pages/` | Streamlit multipage shell; page files execute the root dashboards. |
15: | Yield dashboard | `Yield_Report.py` | CSV load, PN/process mapping, yield/defect/WIP views. It currently executes UI code on import. |
16: | SPC dashboard | `SPC_DASHBOARD.py` | TDF parser, SQLite materialization, filtering, statistics, and charts. |
17: | Shared presentation | `theme_utils.py` | Streamlit CSS and Plotly theme helpers only. |
18: | Bundled sample | `rptTestDetail.csv` | Yield-report sample; it is operational data, not a synthetic test fixture. |
19: 
20: ## Working rules
21: 
22: 1. Do not alter a KPI merely to make a chart look plausible. Update its documented definition, tests, and UI label together.
23: 2. Treat `Result` (tester row PASS/FAIL), a numeric result versus specification, and a unit-level manufacturing outcome as different concepts unless a documented rule proves they are equivalent.
24: 3. Never mix measurement populations with different `TestNb`, `TestLabel`, channel, units, or limits in a single capability result. Partition them or block the calculation.
25: 4. Preserve raw inputs. Consolidated SQLite/CSV outputs must be reproducible from an identified source folder, parser version, and configuration.
26: 5. Keep UI code thin. New parsing, filtering, statistics, and metric functions should be import-safe, deterministic domain modules with unit tests.
27: 6. Do not silently change `PART_MASTER`, DUT part-number rules, dates, or TDF folder assumptions. These are business configuration and require an owner-approved change with a fixture.
28: 7. Do not commit generated databases, output CSVs, logs, `.DS_Store`, or `__pycache__`. Existing tracked cache artifacts are legacy; do not expand that pattern.
29: 8. Pin runtime and build dependencies before packaging. Do not upgrade Streamlit/Pandas/Numpy as an incidental change.
30: 9. New charts and insight cards must identify the applicable population, evidence, uncertainty/threshold policy, and drill-down path; they must not infer a root cause.
31: 
32: ## Required workflow for calculation changes
33: 
34: 1. State the population, unit of analysis, time window, specification source, and formula in [docs/DATA_AND_KPIS.md](docs/DATA_AND_KPIS.md).
35: 2. Add a small deterministic unit test plus a data-quality guard. Include edge cases: no samples, one sample, zero variation, one-sided limits, changing limits, and nonnumeric values.
36: 3. Add or update a golden-data regression fixture for user-visible KPI results.
37: 4. Surface an explicit `N`, grouping, limit source, and warning in the UI.
38: 5. Run the relevant tests and document any methodological change in [docs/STATISTICAL_VALIDATION.md](docs/STATISTICAL_VALIDATION.md).
39: 
40: ## Required workflow for portability changes
41: 
42: 1. Keep the product runnable as a developer Streamlit app until a packaged smoke test passes.
43: 2. Put user data in an OS-appropriate writable application-data directory, never beside a protected executable.
44: 3. Build and test each target operating system separately; one executable cannot reliably run on Windows, macOS, and Linux.
45: 4. Test on a clean machine/account with no Python, virtual environment, or prior cache.
46: 5. Do not ship unsigned installers or executable bundles without an agreed distribution policy.
47: 
48: ## Safety and data handling
49: 
50: - TDF/CSV data can contain serial numbers, tester information, and failure details. Keep it local unless the user explicitly authorizes another destination.
51: - Validate user-provided paths and write output only to a selected writable folder.
52: - SQLite materialization currently drops and rebuilds `test_results`; future code must use a temporary database plus atomic replacement to avoid corrupting a previous usable output on failure.
53: 
54: ## Verification baseline
55: 
56: The repository currently has no automated test suite. The source is syntactically valid under the available Python interpreter, but the active environment does not contain the declared Streamlit/Pandas/Numpy dependencies. Do not interpret syntax checking as an end-to-end application test. See [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md).

(End of file - total 56 lines)