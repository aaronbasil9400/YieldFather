"""Deterministic report writers for the SPC desktop app.

Pure file-output helpers (no Qt imports) so they remain unit-testable per
AGENTS.md rule 5. Every report surfaces the evaluated population (N), the
spec-limit values with their source, and the row-level PASS share explicitly;
it never infers a root cause.
"""

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _fmt_num(v):
    if v is None or pd.isna(v):
        return "N/A"
    return f"{v:.6g}"


def format_kpi_lines(stats: dict, pass_pct, lsl, usl) -> list[str]:
    pass_str = ("N/A" if pass_pct is None or pd.isna(pass_pct)
                else f"{pass_pct:.2f}%")
    return [
        f"N (samples): {stats.get('N', 0)}",
        f"LSL: {_fmt_num(lsl)} | USL: {_fmt_num(usl)}"
        " (limits from consolidated LowLim/HighLim columns)",
        f"Min: {_fmt_num(stats.get('Min'))}",
        f"Max: {_fmt_num(stats.get('Max'))}",
        f"Mean: {_fmt_num(stats.get('Mean'))}",
        f"StdDev: {_fmt_num(stats.get('StdDev'))}",
        f"Cp: {_fmt_num(stats.get('Cp'))}",
        f"Cpk: {_fmt_num(stats.get('Cpk'))}",
        f"Sigma Level: {_fmt_num(stats.get('Sigma_Level'))}",
        f"% Out of Spec: {_fmt_num(stats.get('PctOutOfSpec'))}",
        f"% PASS (tester rows): {pass_str}",
    ]


def write_report(out_dir: Path, df: pd.DataFrame, stats: dict, pass_pct,
                 title: str, lsl=None, usl=None, cpk_df: pd.DataFrame = None,
                 generated_utc: datetime = None) -> list[Path]:
    """Write summary text plus filtered-data (and optional Cpk) CSVs.

    Returns the list of file paths actually written.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = generated_utc or datetime.now(timezone.utc)
    lines = [
        "FLEX - Teradyne UltraFlexPlus Dragon SPC report",
        f"Generated (UTC): {stamp.isoformat(timespec='seconds')}",
        f"Evaluation: {title}",
        "Population: numeric rows (Value_num present) matching the current "
        "filter selection",
    ]
    lines.extend(format_kpi_lines(stats, pass_pct, lsl, usl))

    written = []
    summary_path = out_dir / "report_summary.txt"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append(summary_path)

    data_path = out_dir / "filtered_data.csv"
    df.to_csv(data_path, index=False, encoding="utf-8")
    written.append(data_path)

    if cpk_df is not None and not cpk_df.empty:
        cpk_path = out_dir / "cpk_by_group.csv"
        cpk_df.to_csv(cpk_path, index=False, encoding="utf-8")
        written.append(cpk_path)
    return written
