# Factory Test Analytics Roadmap

## Purpose

This roadmap describes the next analytical capabilities for Factory Analytics Hub. It is deliberately staged: first make every calculation trustworthy and explainable; then add richer charts, tester/channel analysis, drift detection, and concise guidance for new users.

Nothing in this document changes the current application behavior. It is the design and acceptance contract for future work.

## Design principles

1. **Traceable before clever.** Every displayed result must identify its records, filters, time range, event definition, specification version, and calculation version.
2. **One population, one conclusion.** Do not compare or aggregate measurements with different test identity, units, limit revisions, or relevant process context.
3. **Separate observation from explanation.** The app may say that a pattern exists; it must not claim a root cause without supporting evidence.
4. **Progressive disclosure.** A first-time user sees the data health and a small number of actionable observations; detailed charts remain available for investigation.
5. **Local and deterministic by default.** Initial insights are rule-based and run locally. No source data leaves the laptop, and every message can be reproduced from its displayed evidence.
6. **Engineer remains accountable.** Insights guide investigation; they never automatically release, reject, or disposition production material.

## 1. Canonical event and measurement model

The app must distinguish four levels of factory data. A record can be incomplete, but its known level must be explicit.

```text
Manufacturing unit
  └─ Process visit (a unit at an operation/station)
       └─ Test attempt (one execution, including a retest)
            └─ Measurement (one test number/label/channel result)
```

| Entity | Required stable key | Purpose | Minimum contextual fields |
| --- | --- | --- | --- |
| Manufacturing unit | `unit_id` | Unique physical product/serial | part number, product, lot/order where available |
| Process visit | `unit_id + operation + visit_sequence` | One unit entering a defined manufacturing step | operation, station, route/status, start/end time |
| Test attempt | `attempt_id` | A single tester execution | unit, operation, tester, site, program revision, timestamp, retest/attempt sequence, overall result |
| Measurement | `measurement_id` | One numeric or categorical result within an attempt | attempt, test number, label, channel, units, value, limits, specification revision |

### Identity and lineage requirements

- Source-specific identifiers are mapped into this model without discarding their raw values.
- Each derived record retains a source file identifier, source-row/offset where practical, parser version, and extraction time.
- `TestNb`, `TestLabel`, `Channel`, `Units`, `ProgramName`, test step, tester/site, and the exact limits form the minimum identity for a numeric SPC population.
- Limit/program/calibration changes create a new analytical segment unless an approved rule says they are equivalent.
- Missing identity fields are counted and surfaced. They cannot silently join unrelated rows.

### First-pass and yield definitions to approve

These definitions must be approved by the process owner per route/process before implementation:

| Metric | Recommended definition | Must not be confused with |
| --- | --- | --- |
| Record yield | Passing result rows / all eligible result rows | Unit or attempt yield |
| Attempt yield | Passing test attempts / eligible test attempts | First-pass yield |
| First-pass yield (FPY) | Units whose **first eligible attempt** at the defined operation passes / units with a first eligible attempt | `Row == 1` unless that field is contractually the attempt order for the event |
| Final yield | Units that ultimately pass the defined route/operation / units that entered it | First-test pass or retest recovery |
| Retest recovery | Initially failed units that later pass / initially failed units with an eligible later attempt | Final yield |
| Defect rate | Approved defect-event definition / approved denominator | Failure-row count without a stated event rule |

The default dashboard must show the metric’s unit of analysis and denominator next to each yield value.

## 2. Data-quality gates

Data quality is a product feature, not an import-time detail. Every dashboard load should produce a compact readiness summary before the KPI cards.

| Gate | Checks | UI action |
| --- | --- | --- |
| Schema | Required columns, data types, allowed result values | Block affected view with an actionable mapping/error message |
| Identity | Missing/duplicate unit, attempt, or measurement keys | Warn; block unit-level KPIs when identity is insufficient |
| Time | Unparseable dates, timezone ambiguity, out-of-order attempts | Report count; exclude only under a visible rule |
| Specification | Missing, reversed, mixed, or changing limits; mixed units | Block capability calculation or partition it automatically |
| Measurement | Nonnumeric values, saturation/overflow codes, zero variance, calibration state | Report exclusions and prevent invalid capability claims |
| Result reconciliation | Tester PASS/FAIL versus numeric in/out-of-spec result | Show agreement, mismatch count, and affected records |
| Coverage | Filtered rows, analysed rows, capped/sampled rows, unique units/attempts | Display all counts in the analysis header |

### Data-health summary for first-time users

```text
Data readiness: Needs review
73,712 records loaded · 6,607 units · 63,000 first-attempt candidates
Warnings: FPY event key not yet confirmed; 2 distinct specification sets selected
Suggested next step: choose one TestNb/TestLabel/channel before reviewing capability.
```

The exact text is illustrative. Each message must link to the underlying records/filter and describe what the app did or did not include.

## 3. Correct the current KPI blockers

The following work is prerequisite to new analytical features. Details and source evidence are in [STATISTICAL_VALIDATION.md](STATISTICAL_VALIDATION.md).

| Work item | Desired outcome | Acceptance criteria |
| --- | --- | --- |
| Canonical event key | Yield metrics operate on approved units/attempts | FPY, final yield, and retest recovery reconcile to a small approved fixture |
| Pareto window | The UI and calculation agree on 28 days or an explicitly selected range | Boundary fixtures prove inclusivity and show the selected window |
| Pareto denominator | Cumulative percentage represents all eligible failures, including omitted tail | Top 15 bars do not automatically end at 100% when additional failures exist |
| Capability segmentation | One KPI group has one test identity, unit, and limit set | Mixed groups are partitioned or capability is blocked |
| Capability naming | Overall versus within variation is unambiguous | Pp/Ppk and Cp/Cpk use documented estimates and labels |
| One-sided conformance | Upper-only and lower-only tests yield a valid observed out-of-spec rate | Deterministic tests cover both cases |
| Query completeness | Users know if displayed results are capped or sampled | Header shows matched, analysed, and excluded counts |

## 4. Chart selection: use the graph that matches the question

SPC remains the default view for an eligible numeric test. The user can choose a complementary graph when the question calls for it, but the app should recommend a valid default from the data grain.

```text
Numeric measurement, one value per time-ordered attempt?
  └─ Individuals + Moving Range (I-MR)

Numeric measurement, rational subgroups available?
  └─ Xbar-R (small subgroups) or Xbar-S (larger subgroups)

Pass/fail result for units or attempts?
  └─ p chart (varying denominator) or np chart (constant denominator)

Defect counts with exposure/opportunities?
  └─ c chart (constant exposure) or u chart (varying exposure)

Comparing distribution, site, or channel?
  └─ Histogram, ECDF, box/violin plot, or a sample-size-aware heatmap
```

| Analytical question | Default chart | Complementary view | Guardrails |
| --- | --- | --- | --- |
| Is an individual measurement stable over time? | I-MR | Run chart, histogram | Time order and homogeneous segment required |
| Is a rational subgroup stable? | Xbar-R or Xbar-S | Range/S chart | Subgroup rule must be explicit |
| How does the measurement compare with specification? | Capability histogram + Pp/Ppk or Cp/Cpk | Probability plot/ECDF | Stable population, limits, units, and distribution policy required |
| Is yield changing? | p/np chart or yield run chart | Confidence-interval trend | Define unit and denominator; do not count retests twice unintentionally |
| Where are failures concentrated? | Pareto | Defect-by-station/shift heatmap | State record/event/unit counting rule |
| Are sites/channels different? | Heatmap | Box/violin + funnel plot | Minimum N, common test population, and uncertainty required |
| Did a small persistent shift occur? | EWMA or CUSUM | I-MR | Approved baseline and alert policy required |
| Which parameters move together? | Correlation matrix | Scatter/density plots | Same population; correlation is not causation |

For individual observations, an I-MR chart estimates short-term variation from moving ranges; mean ± 3 overall sample standard deviation is not the default I-MR implementation. See [NIST’s individuals chart method](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc322.htm). Capability decisions require a stable process, an appropriate distribution policy, and adequate independent data. See [NIST’s capability guidance](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm).

### Control limits and specification limits

The interface must always distinguish these visually and in wording:

- **Specification limits**: product/test requirements used for conformance.
- **Control limits**: statistically derived process-monitoring boundaries from an approved baseline.

Crossing a control limit prompts investigation; it is not automatically a product failure. Crossing a specification limit is a conformance observation; it does not prove the process is unstable.

## 5. Tester, site, and channel heatmaps

Heatmaps are a high-value navigation tool when a user needs to see where a consistent population behaves differently.

### Core heatmap modes

| Mode | Cell value | Best use |
| --- | --- | --- |
| Yield | Unit/attempt pass rate with denominator and confidence interval | Find low-yield tester/site/shift combinations |
| Observed conformance | Numeric out-of-spec percentage | Locate measurements near or beyond specification |
| Capability | Ppk/Cpk or mean-to-nearest-spec Z, with N | Compare homogeneous channels/sites only |
| Location shift | Difference from approved baseline mean, in sigma units | Detect channel/site bias or drift |
| Variation | Standard deviation or moving-range sigma versus baseline | Find noisy channels/fixtures |
| Coverage | Number of units/attempts/measurements | Reveal sparse cells before users over-interpret rates |

### Interaction model

- Rows/columns are selectable dimensions: tester, site, channel, test number, program revision, shift, lot, or date bucket.
- A cell hover shows numerator/denominator, `N`, limits, confidence interval where relevant, time window, and data-quality flags.
- Clicking a cell applies an inspectable filter and opens the appropriate chart for that exact population.
- Sparse cells are muted or marked “insufficient N,” not ranked as best/worst.
- A separate coverage heatmap is always available beside rate/capability heatmaps.
- Colors must not combine incomparable metrics. Use a diverging scale for signed mean shift and a sequential scale for rates/counts.

### Comparison rules

Do not compare a tester or channel until the selected data has the same test identity, units, limits, program/spec revision, and relevant product/process context. A future comparison view can add formal uncertainty intervals and approved hypothesis tests, but it should begin with effect size and sample size—not a p-value leaderboard.

## 6. Correlation and drift analysis

### Correlation workspace

Correlation is an exploratory diagnostic, useful for identifying tests that move together, channel coupling, or a likely common source. It does not establish causality.

Requirements:

- Include only measurements from a compatible product/program/test population and a clearly displayed time window.
- Report the method (Pearson for roughly linear numeric relationships; Spearman for rank/monotonic screening), pairwise sample size, and missing-data policy.
- Pair a matrix with selectable scatter/density plots, regression/LOESS only when appropriate, and time coloring to expose a common drift pattern.
- Flag correlations driven by a program revision, lot, tester, site, or time block before presenting them as a process relationship.
- Provide a “same unit/attempt” join mode and state the join key; never correlate unrelated rows by accidental row order.

### Drift workspace

Drift analysis should answer “what changed, when, and in which segment?” rather than simply draw a rolling average.

| Signal | Evidence to show | Initial response |
| --- | --- | --- |
| Mean shift | Baseline mean, current mean, effect size, sample size, start time | Inspect calibration/program/fixture/lot events and I-MR chart |
| Variation increase | Baseline versus current sigma or moving-range sigma | Inspect channel/site, fixture, environmental, and measurement-system context |
| Yield drop | Unit/attempt denominator, confidence interval, affected failure families | Open Pareto and tester/site heatmap |
| Limit/program change | Exact old/new values or version identifiers | Segment analysis; do not compare directly across the change |
| Localized site/channel effect | Difference versus comparable sites/channels plus N | Drill into cell and compare distributions |

Drift baselines must be explicit, versioned, time-bounded, and owner-approved. A program revision, calibration event, fixture replacement, or specification change should create an annotation and normally start a new baseline segment.

## 7. Small, useful insights for new users

Start with deterministic, evidence-backed insight cards. They should reduce the “where do I start?” burden without becoming an opaque AI layer.

### Insight card structure

```text
Status: Needs review
Observation: Channel 7 has a higher observed out-of-spec rate than the other selected channels.
Evidence: 18 / 420 (4.29%) versus 9 / 2,310 (0.39%); same TestNb, limits, units, and program revision.
Suggested next step: Open the Channel 7 distribution and I-MR chart.
Scope: Last 28 days · selected product/process · analysis version 1
```

Each card has four mandatory parts: observation, evidence, scope, and a next investigation action. It must link to the filtered chart/table that produced it.

### Initial rule set

| Insight category | Example trigger | User-facing behavior |
| --- | --- | --- |
| Data readiness | Missing/ambiguous event key, mixed limits, capped result, high invalid-value rate | Explain the limitation; block invalid KPI where necessary |
| Population composition | Multiple tests/channels/sites selected | Recommend grouping or a heatmap before a single capability figure |
| Specification proximity | Mean is close to a limit or observed conformance is worsening | Show distance/effect and open capability/distribution view |
| Stability | Control-rule signal, shift, trend, or increased moving range | Mark “investigate”; open relevant control chart |
| Yield change | Recent rate differs materially from baseline with adequate N | Open trend/Pareto with denominator and interval |
| Concentration | One defect, tester, site, or channel contributes a large share | Open Pareto/heatmap; state share and population |
| Reconciliation | Tester result and numeric conformance disagree | Open mismatch records; avoid calling either value “truth” without policy |

### Language policy

- Say “observed,” “higher than baseline,” “pattern,” or “needs review”—not “caused by,” “defective process,” or “root cause.”
- Never hide `N`, percentages, time window, filters, or data exclusions.
- Limit the default landing view to the three most material non-overlapping cards, ordered: blocked data quality → safety/limit risk → meaningful change.
- Suppress cards below configured sample-size/effect-size thresholds and show why a result is inconclusive.
- Keep insight generation local and deterministic in the first release. Any later generative summary must cite the same local evidence and have a clear privacy/approval design.

## 8. Delivery sequence

| Phase | Deliverable | Dependencies | Definition of done |
| --- | --- | --- | --- |
| A. Data foundation | Canonical model, mappings, data-quality profile, lineage metadata | Approved event definitions | Fixture tests show correct unit/attempt/measurement construction |
| B. KPI integrity | Yield/FPY/Pareto fixes, segmented conformance, Pp/Ppk/Cp/Cpk policy | Phase A | Results reconcile to approved golden datasets |
| C. Chart engine | Chart selector, I-MR/Xbar-R/Xbar-S/p/np/c/u where applicable, baseline metadata | Phase B | Every chart displays its population, rules, and limit type |
| D. Diagnostic navigation | Heatmaps, coverage view, drill-down filters, drift annotations | Phase A–C | A user can trace every cell to records and a compatible chart |
| E. Guided analysis | Rule-based data-health and insight cards | Phase A–D | Every card is reproducible, scoped, and action-linked |
| F. Advanced exploration | Correlation workspace, EWMA/CUSUM, change-point candidates | Stable baseline and governance | Clearly exploratory; no unapproved automatic decisions |

## 9. Decisions required before implementation

1. Approved event keys and ordering rules for each production route/process.
2. First-pass, final-yield, retest-recovery, defect-event, and WIP definitions.
3. Which tester/site/channel context values are trustworthy and consistently available.
4. SPC baseline ownership, subgroup rules, sample-size thresholds, and out-of-control policy.
5. Distribution/non-normal capability policy and measurement-system validation responsibility.
6. Which chart types are in the first release and which require advanced configuration.
7. Minimum sample/effect thresholds and wording policy for user insight cards.

## References

- [NIST/SEMATECH: Process capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm)
- [NIST/SEMATECH: Individuals control charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc322.htm)
- [NIST/SEMATECH: Assessing process stability](https://www.itl.nist.gov/div898/handbook/ppc/section4/ppc45.htm)
- [NIST/SEMATECH: Measurement process characterization](https://www.nist.gov/publications/nistsematech-engineering-statistics-handbook-chapter-2-measurement-process)
