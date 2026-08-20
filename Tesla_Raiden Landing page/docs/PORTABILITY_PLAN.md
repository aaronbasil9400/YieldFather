# Portability Plan

## Goal

Deliver a local desktop application that an end user can launch on a normal laptop without separately installing Python, Pip, Streamlit, or the project dependencies. The app must continue to work with local CSV/TDF data and write outputs to a user-writable location.

## Recommended delivery path

Start with a **Windows packaged local application** that embeds the existing Python runtime and dependencies, launches the app, and opens the local interface. This delivers the requested no-setup experience with the least UI rewrite. Keep a native desktop UI (for example, PySide6) as a later option if a local browser/server is unacceptable.

| Option | User experience | Effort/risk | Recommendation |
| --- | --- | --- | --- |
| Package Streamlit + embedded Python | Double-click app/installer; browser opens to localhost; no Python install | Lowest migration risk; Streamlit packaging needs careful data-file testing | **Phase 1** |
| Native desktop UI over extracted Python domain layer | Conventional app window; no local browser | Larger UI rewrite and per-OS UI QA | Future option |
| Static browser-only app | Browser files only | Cannot safely replace local TDF/SQLite Python workflow without a major redesign | Not recommended |

“Almost any laptop” requires separate artifacts: a signed Windows executable/installer, a signed/notarized macOS `.app`, and (if supported) a Linux AppImage/package. It cannot mean one universal executable.

## Phased implementation

### Phase 0 — lock requirements and success criteria

- Confirm target operating systems, first release distribution model, offline policy, output-data location, and support ownership.
- Pin exact runtime versions (the checked-in `requirements.txt` is unpinned) and create a lock file/build manifest.
- Decide licensing/signing and antivirus/enterprise deployment requirements.
- Establish sanitized, versioned TDF and CSV fixtures plus expected KPI outputs.

Exit criterion: a reproducible development environment and accepted KPI/event definitions.

### Phase 1 — correctness and modularization

- Move pure parsing, validation, yield, defects, capability, and chart-data calculations out of Streamlit files into import-safe modules.
- Add data contracts, explicit validation errors, and test coverage described in [TEST_STRATEGY.md](TEST_STRATEGY.md).
- Correct the P0/P1 metric issues in [STATISTICAL_VALIDATION.md](STATISTICAL_VALIDATION.md).
- Replace in-place SQLite rebuilding with temporary output plus atomic replacement and useful consolidation metadata.
- Centralize app settings and locate outputs under an OS user-data directory.

Exit criterion: deterministic domain tests and a Streamlit UI that is a thin adapter over tested services.

### Phase 2 — packaged Windows pilot

- Implement a small launcher that selects a free localhost port, starts the bundled app, waits for readiness, opens the browser, and shuts down cleanly.
- Package Python, Streamlit, Pandas, Numpy, Plotly, assets, pages, and configuration with a build tool appropriate to the chosen launcher (evaluate PyInstaller-based and installer-based approaches in a proof of concept).
- Do not make the app depend on the current working directory; resolve bundled resources separately from writable user data.
- Provide a signed portable bundle or installer, user guide, logs, version/about screen, and safe update path.
- Test on clean Windows 10/11 machines with no Python and with local/OneDrive/network data paths where supported.

Exit criterion: a clean laptop can install or unzip, launch, consolidate a fixture, run dashboards, and export results without an interpreter or package-install step.

### Phase 3 — harden and extend

- Add macOS build/sign/notarization if selected; test on supported Intel/Apple Silicon target(s).
- Add Linux only after defining supported distributions and packaging policy.
- Decide whether the Streamlit-local-browser experience remains acceptable. If not, build a native UI that calls the same tested domain services.
- Add telemetry only with explicit approval and a local-first/privacy design.

## Packaging acceptance checklist

- No Python, virtual environment, `pip`, or internet access required on the target laptop after delivery.
- App starts by double-click and gives actionable errors when source/output folders are inaccessible.
- Assets, page routing, uploads, Plotly charts, downloads, SQLite, and TDF parsing work from a path containing spaces and from a non-admin account.
- App data and logs go to a writable user directory; no source data is silently sent elsewhere.
- The build reports application version, dependency lock/build ID, and parser/calculation version.
- Smoke, regression, and clean-machine test evidence is retained for the exact shipped artifact.

## Decisions required before implementation

- Windows-only pilot or Windows + macOS release?
- Portable folder versus installer/MSIX/enterprise deployment?
- Whether localhost/browser UI is acceptable for the first standalone release?
- Data retention, output folder defaults, and maximum expected TDF dataset size?
- Code-signing certificate and update ownership?
