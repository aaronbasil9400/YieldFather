# Agent Task Playbooks

This is a project playbook, not an executable Codex skill package. Use the smallest applicable playbook and read its linked contract before changing code.

## 1. TDF ingestion and consolidation

Use for changes in `SPC_DASHBOARD.py` parser or SQLite materialization.

1. Start from a representative, sanitized TDF fixture that covers header fields, board configuration, multiple data lines, missing numeric fields, and malformed lines.
2. Validate the expected four-level folder context: bin → unit/run → test-step → timestamp → `*Data*.tdf`.
3. Assert every output column, numeric conversion, row count, source path, and rejected-record reason.
4. Build to a temporary SQLite file, validate schema/indexes/counts, then atomically replace the previous database.
5. Record parser version, source count, skipped rows, and warnings in the output metadata.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DATA_AND_KPIS.md](docs/DATA_AND_KPIS.md).

## 2. SPC/capability changes

Use for `compute_stats`, control charts, capability tables, or KPI labels.

1. Define a homogeneous population and verify a single unit/limit pair (or explicitly group it).
2. Decide whether the variation estimate is overall (`Pp`/`Ppk`) or within-subgroup (`Cp`/`Cpk`).
3. Test two-sided, upper-only, lower-only, zero-variation, `N < 2`, and out-of-spec cases against known answers.
4. Make control-chart limits a chart-specific calculation; do not treat mean ± 3 overall standard deviations as an I-chart implementation by default.
5. Show warnings for insufficient samples, instability, limit changes, non-normality policy, and measurement-system limitations.

See [docs/STATISTICAL_VALIDATION.md](docs/STATISTICAL_VALIDATION.md).

## 3. Yield, defects, and WIP changes

Use for `Yield_Report.py` metrics.

1. Confirm the business event key (normally serial number + process/station + attempt) before counting units.
2. Define “first pass” from ordered attempts, not merely a field named `Row`, unless its contract is confirmed.
3. State whether a defect Pareto counts records, events, or unique units; calculate cumulative percentage against all failures in the chosen window.
4. Treat WIP as a business-status calculation, not simply a last-observed test result, until the routing/status rules are documented.
5. Keep CSV field validation and date parsing diagnostics visible to the user.

See [docs/DATA_AND_KPIS.md](docs/DATA_AND_KPIS.md) and [docs/STATISTICAL_VALIDATION.md](docs/STATISTICAL_VALIDATION.md).

## 4. Desktop packaging and release

Use for the standalone-app goal.

1. Separate domain logic from Streamlit UI before choosing a packaging tool.
2. Pin dependencies and produce a reproducible lock file and build manifest.
3. Package an embedded runtime per target OS; do not require end users to install Python or execute `pip`.
4. Test the installer/portable build on a clean computer, with sample CSV and TDF data outside the app folder.
5. Produce release notes, checksums/signing evidence, and a rollback path.

See [docs/PORTABILITY_PLAN.md](docs/PORTABILITY_PLAN.md) and [docs/TEST_STRATEGY.md](docs/TEST_STRATEGY.md).

## 5. Documentation maintenance

When behavior changes, update the relevant contract in the same change. Keep present-state statements factual, distinguish verified behavior from planned behavior, and link decisions to source files or tests.
