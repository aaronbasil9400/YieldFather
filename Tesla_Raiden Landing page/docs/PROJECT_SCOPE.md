# Project Scope

## Product purpose

Factory Analytics Hub turns two local factory-data sources into self-service operational analytics:

| Product area | Source | Current outcome |
| --- | --- | --- |
| Yield and defect analysis | `rptTestDetail`-style CSV | Filtered station/PN yield, first-pass view, trends, defect Pareto, WIP-style latest status, CSV exports. |
| SPC dashboard | Teradyne TDF log-folder tree | Parsed test rows in SQLite/CSV, filters by test/context, measurement chart, distribution, Cp/Cpk-style KPIs, and export. |

The primary audience is local manufacturing/test engineering users who need to inspect production results on their own laptop without operating a central service.

## In scope

- Parse the supported Teradyne TDF format and its documented folder context.
- Read a user-selected production-detail CSV.
- Calculate clearly defined, validated yield/defect and process-capability metrics.
- Filter, chart, export, and retain results locally.
- Deliver signed, OS-specific desktop packages with an embedded runtime and no end-user Python/package installation.
- Support Windows first; add macOS and Linux only through separately tested builds.

## Out of scope for the current product

- Direct MES/ERP/LIMS integration, live equipment control, or write-back to factory systems.
- Cloud synchronization, multi-user collaboration, remote data transfer, or centralized access control.
- Replacing a validated SPC system, formal quality release, MSA/Gage R&R, or automatic disposition decisions.
- Declaring a unit pass/fail independently of the factory’s approved routing and test rules.
- One binary that runs unchanged across all operating systems.

## Current deliverables and boundaries

```text
Local CSV ───────────────► Yield Report ─────────► charts / CSV downloads

TDF folder tree ─► parser/consolidator ─► SQLite + CSV ─► SPC dashboard ─► charts / CSV downloads
```

- The Yield report reads the bundled `rptTestDetail.csv` by default or an uploaded CSV.
- The SPC report asks the user for a source folder and output location, then looks for `*Data*.tdf` recursively.
- SQLite uses a single `test_results` table rebuilt on each consolidation.
- Inputs and outputs remain on the user’s machine in the current implementation.

## Scope decisions still needed

These choices materially change the implementation and must be confirmed before a production package is built:

1. Supported first release: Windows only, or Windows plus macOS?
2. Distribution: portable signed folder/ZIP, installer, enterprise software deployment, or all of these?
3. Approved definition of a Yield event, First-Pass Yield, defect event, and WIP for each production process.
4. Approved SPC policy: within-subgroup `Cp/Cpk` versus overall `Pp/Ppk`, subgroup definition, minimum sample size, and rules for control charts.
5. Data retention location, size limits, log redaction, and whether raw source paths may be stored in SQLite.

## Definition of success

A release meets the user’s goal only when a clean target laptop can launch the app by opening the delivered application, select local CSV/TDF folders, produce verified results, and export them—without installing Python, Pip, Streamlit, or any third-party dependency.
