# Data and KPI Contract

## Yield CSV contract

The current code expects a `rptTestDetail`-style CSV. At minimum it needs the following fields for the associated views:

| View | Required fields |
| --- | --- |
| Core filtering and yields | `SerialNumber`, `TestStation1`, `TestResult`, `TestDate1`, `Row` |
| PN/product/process mapping | one of `TestPartNumber`, `CTOBasePartNumber`, or `PartNumber`; process also uses `CurrentStation` |
| Defect Pareto | `FailureCode`, `FailureRemark`, `DefectDesc`, `DefectPart`, `TestResult`, `TestDate1` |
| WIP-style view | `SerialNumber`, part fields, `TestDate1`, `CurrentStation`, `TestResult` |

`TestResult` is expected to be `PASS` or `FAIL`. Current code includes any other/missing status in denominators but does not count it as either pass or fail; a future validator must report and resolve these values.

Date parsing first tries month-first parsing, then fills invalid values with day-first parsing when more than 30% of the first pass is invalid. Source format must be standardized or the UI must display date-parse diagnostics before users filter.

## TDF and consolidated data contract

The SPC parser produces one `test_results` row per parsed TDF result. Measurement analysis uses:

| Field | Meaning |
| --- | --- |
| `Value_num` | Numeric measured value. Nonnumeric values are excluded from statistics. |
| `LowLim_num`, `HighLim_num` | Lower/upper specification limits from the test row. |
| `TestNb`, `TestLabel`, `Channel`, `Units`, `TestStep` | Minimum identity/context for a measurement population. |
| `RunTimestampFolder` | Ordering timestamp inferred from the folder name. |
| `Result` | Tester row PASS/FAIL; it is separate from recalculated numeric conformance. |

The parser also preserves source file, tester, program, board/module, and folder metadata. See `OUTPUT_COLUMNS` in [SPC_DASHBOARD.py](../SPC_DASHBOARD.py).

## Current KPI definitions

| KPI | Current calculation | Unit of analysis | Status |
| --- | --- | --- | --- |
| Raw record yield | `PASS rows / all filtered rows` | CSV row | Correctly named; not unit yield. |
| Overall yield | Same as raw record yield because `all_events = df` | CSV row | Duplicate of raw record yield. |
| First-pass yield (FPY) | `PASS / Row == 1 rows` | CSV row selected by `Row` | Only valid if `Row == 1` is contractually the first attempt for the intended event. |
| Daily/weekly yield | Pass rows / rows by date/week | CSV row | Same unit-of-analysis caveat. |
| Defect Pareto | Failed rows grouped by defect/part | Failed CSV row | Current time window and cumulative percentage are mislabeled; see validation. |
| WIP | Latest selected record per `SerialNumber + PN` | Serial/PN observed in filtered data | A latest-test-status view, not a confirmed inventory WIP definition. |
| Sample standard deviation | `numpy.std(values, ddof=1)` | Filtered numeric measurement row | Formula is correct for the sample standard deviation. |
| Cp | `(USL - LSL) / (6s)` | Combined filtered numeric measurements | Formula is correct only for a stable, homogeneous two-sided population and the chosen sigma estimate. |
| Cpk | `min((USL - mean)/(3s), (mean - LSL)/(3s))` | Combined filtered numeric measurements | Formula is correct under the same conditions; supports one-sided limits. |
| Percent out of spec | measurements strictly below LSL or above USL / `N` | Numeric measurement row | Correct boundary convention, but current code only reports it when both limits exist. |
| `% PASS (rows)` | Tester `Result == PASS` / measurement rows | TDF test row | A tester result rate; not the same as spec conformance. |

## Required future metadata

Every exported or displayed KPI must carry:

- calculation version;
- source name/path or a safe source identifier;
- extraction date/time and filter definition;
- `N` before and after invalid-value removal;
- event key / unit of analysis;
- test identity, units, and exact specification limits used;
- whether the result is overall or within-subgroup capability; and
- warnings/rejection counts.
