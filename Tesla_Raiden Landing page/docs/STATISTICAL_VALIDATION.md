# Statistical Validation

## Conclusion

The core **arithmetic for sample standard deviation, Cp, Cpk, and two-sided observed out-of-spec rate is correctly implemented** in `compute_stats`. The displayed results are nevertheless **not ready to be treated as validated production SPC KPIs** because the dashboard can combine unlike measurement populations/limits and labels overall variation as `Cp/Cpk`. Yield/defect metrics also contain confirmed definition and labeling defects.

This review is a source-and-data-contract validation, not a formal quality-system approval. No consolidated `results.db` is included in the repository, so numerical end-to-end SPC results could not be checked against a controlled TDF golden dataset.

## Formula review

For values `x`, sample size `n`, sample mean `x̄`, and sample standard deviation `s`:

| Metric | Current implementation | Assessment |
| --- | --- | --- |
| Mean/min/max | `numpy.mean/min/max` | Correct. |
| Standard deviation | `numpy.std(values, ddof=1)` for `n > 1` | Correct sample standard deviation. Returns zero for one observation. |
| Cpu | `(USL - x̄) / (3s)` | Correct where an upper spec and `s > 0` exist. |
| Cpl | `(x̄ - LSL) / (3s)` | Correct where a lower spec and `s > 0` exist. |
| Cpk | `min(Cpu, Cpl)` | Correct for a homogeneous population; correct one-sided behavior when only one side exists. |
| Cp | `(USL - LSL) / (6s)` | Correct for two-sided specifications and the chosen standard deviation. |
| Observed % out of spec | `(x < LSL or x > USL) / n` | Correct inclusive-spec convention: equality is in specification. |
| “Sigma Level” | `3 * Cpk` | Mathematically a nearest-spec Z value from Cpk. It must not be presented as a Six Sigma long-term level without a stated convention/shift. |

When `s == 0`, the current code returns `N/A` capability. That is safer than inventing a finite value, but the UI should explain the zero-variation condition and whether all values are in spec.

## Confirmed blockers and issues

| Priority | Finding | Evidence and impact | Required correction |
| --- | --- | --- | --- |
| P0 | Headline SPC can use incorrect limits for a mixed selection | The headline selects the first non-null `LowLim_num`/`HighLim_num`, while filters may include multiple TestNb, channels, test steps, units, or limit revisions. The warning does not prevent calculation. | Enforce one homogeneous specification group or calculate only a grouped table; verify every retained row has the same limits/units/identity. |
| P0 | Overall variation is labelled Cp/Cpk | All selected measurements use one ordinary sample SD. Traditional Cp/Cpk requires a within-subgroup sigma; whole-population sigma is normally reported as Pp/Ppk. | Define rational subgroups and estimate within sigma for Cp/Cpk, or rename to Pp/Ppk until that exists. |
| P0 | “Past 28 Days” Pareto is actually 365 days | `top_defects_28d` subtracts `Timedelta(days=365)`. | Change the window or label; test the inclusive date bounds. |
| P1 | Pareto cumulative percent uses only the displayed top 15 | The denominator is `top_defect["Count"].sum()` after `.head(15)`, forcing the last shown bar to 100%. | Divide cumulative counts by all selected failures, while optionally showing the omitted share. |
| P1 | “FPY” is not demonstrated to be a unit first-pass metric | Code treats all `Row == 1` records as first attempts. In the bundled CSV this selects 63,000 rows but only 6,237 unique serials, so it is clearly not one record per unit. | Agree an event key and first-attempt ordering; derive one first event per key before calculating FPY. |
| P1 | “Overall yield” duplicates raw record yield | `event_level` returns `all_events = df`, so both cards use the same numerator and denominator. | Remove one card or replace it with a separately defined event/unit metric. |
| P1 | Out-of-spec rate is absent for one-sided tests | Code requires both limits before calculating it. | Calculate failures against every available specification side and label the one-sided condition. |
| P1 | Chart control limits are not a validated control chart | Mean ± 3 overall sample SD is drawn as UCL/LCL. An individuals chart normally estimates sigma from moving ranges; other charts require their own subgroup constants and rules. | Implement a selected chart type (I-MR, Xbar-R, etc.), baseline rules, and Nelson/Western Electric policy. |
| P2 | Row cap can silently change KPI population | `query_filtered` orders then applies `LIMIT`; the default is 800,000 but users can select larger data. | Show filtered total vs analysed count, make sampling explicit, or aggregate in SQL. |
| P2 | `% PASS (rows)` and numeric conformance are different measures | Tester `Result` is shown beside calculated spec conformance without a reconciliation. | Label it clearly and add a mismatch count/explanation. |
| P2 | Capability prerequisites are unchecked | No stability, normality/non-normal capability policy, measurement-system analysis, or minimum-N warning exists. | Add quality gates and warnings before publishing capability decisions. |

## Bundled CSV sanity check

The sample was parsed with a standards-library CSV reader (its embedded newlines mean line count is not record count). It contains 73,712 records: 68,671 PASS and 5,041 FAIL. Therefore its current raw-row/overall yield formula gives **93.1612%**.

After applying the report’s `Row` normalization (blank `Row` becomes 1), 63,000 records qualify as `Row == 1`: 60,856 PASS and 2,144 FAIL, for **96.5968%**. Those records represent 6,237 serial numbers, not 63,000 units. This confirms the aggregation warning; it does not establish what the authoritative FPY definition should be.

## Conditions before enabling capability decisions

1. Select exactly one approved test identity, unit, tester/process population, and specification revision—or display separate groups only.
2. Validate limits are present, ordered, and unchanged within each group.
3. State whether a result is Pp/Ppk (overall) or Cp/Cpk (within subgroup), with the subgroup strategy and sample threshold.
4. Use a control-chart method suited to the sampling structure and distinguish control limits from specification limits.
5. Add deterministic formula tests plus golden TDF and CSV regression fixtures approved by process owners.
6. Reconcile the tester PASS/FAIL result with calculated numeric conformance and expose exceptions.

Until then, use the SPC dashboard for exploratory engineering analysis only, not automatic disposition or formal capability release.
