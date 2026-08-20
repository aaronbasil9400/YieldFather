# Test Strategy

## Current baseline

There is no automated test suite in the repository. Syntax checking succeeds, but the active environment lacks the declared dashboard dependencies, so the current review did not run the Streamlit UI or a full consolidation. The bundled `rptTestDetail.csv` is useful for manual exploration but is not a controlled regression fixture.

## Test layers to add

| Layer | Coverage | Examples |
| --- | --- | --- |
| Unit | Pure functions | TDF line parsing, date parsing, PN mapping, event construction, Cp/Cpk/Pp/Ppk, one-sided OOS rates. |
| Contract | Input validation | Missing columns, malformed files, invalid limits, mixed units, changing specs, unsupported Result values. |
| Golden regression | Approved small datasets | Exact output rows and KPI tables for sanitized CSV/TDF fixtures. |
| Storage/integration | Consolidation lifecycle | Temporary DB, schema/indexes, row counts, atomic swap, refresh/cache behavior. |
| UI smoke | User paths | Load data, filters, warnings, downloads, page navigation. |
| Packaging | Clean device | No Python installed; launch, file selection, aggregation, export, and graceful error paths. |

## Minimum deterministic statistical cases

For each capability function, use hand-calculated expected values and test:

- no numeric samples and one numeric sample;
- sample standard deviation (`ddof=1`) for a known sequence;
- two-sided, upper-only, and lower-only specification limits;
- zero variation in and out of spec;
- equality at a specification boundary;
- mixed test identity/units or changing limits (must partition or reject);
- within-subgroup versus overall capability labeling;
- control-chart baseline calculation and out-of-control rules.

## Minimum deterministic Yield/defect cases

- One unit with pass/fail/retest records to establish event ordering.
- Multiple units with overlapping stations and repeated `Row == 1` values.
- Blank/unknown test results and malformed dates.
- A 28-day Pareto boundary with failures outside the window.
- Pareto cumulative percentage against total failures, including an omitted tail beyond top 15.
- WIP routing/status transitions approved by the business owner.

## Release gate

A change that affects inputs, calculations, or packaging is complete only when its unit/contract tests, relevant golden regression, and appropriate clean-machine smoke test pass. Record the fixture version, operating system, artifact checksum/version, and any manual sign-off with the release.
