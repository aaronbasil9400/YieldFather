"""Unit tests for spc_app.reporting (Qt-free deterministic report writers)."""

from datetime import datetime, timezone

import numpy as np
import pandas as pd
import pytest

from spc_app.reporting import format_kpi_lines, write_report
from spc_core.stats import compute_stats


def make_df():
    return pd.DataFrame({
        "TestNb": ["12"] * 4,
        "Channel": ["CH0"] * 4,
        "Value_num": [2.0, 4.0, 6.0, 8.0],
        "LowLim_num": [0.0] * 4,
        "HighLim_num": [10.0] * 4,
        "Result": ["PASS"] * 3 + ["FAIL"],
    })


class TestFormatKpiLines:
    def test_known_values(self):
        s = compute_stats(np.array([2.0, 4.0, 6.0, 8.0]), 0.0, 10.0)
        lines = format_kpi_lines(s, 75.0, 0.0, 10.0)
        joined = "\n".join(lines)
        assert "N (samples): 4" in joined
        assert "LSL: 0 | USL: 10" in joined
        assert "Mean: 5" in joined
        assert "% PASS (tester rows): 75.00%" in joined

    def test_no_samples_and_missing_limits(self):
        s = compute_stats(np.array([], dtype=float), None, None)
        joined = "\n".join(format_kpi_lines(s, float("nan"), None, None))
        assert "N (samples): 0" in joined
        assert "LSL: N/A | USL: N/A" in joined
        assert "Cpk: N/A" in joined
        assert "% PASS (tester rows): N/A" in joined


class TestWriteReport:
    def test_writes_summary_data_and_cpk(self, tmp_path):
        df = make_df()
        s = compute_stats(df["Value_num"].to_numpy(dtype=float), 0.0, 10.0)
        cpk = pd.DataFrame([{"TestNb": "12", "Cpk": 1.33}])
        written = write_report(
            tmp_path, df, s, 75.0, "T123 | TestNb 12 | MyLabel",
            lsl=0.0, usl=10.0, cpk_df=cpk,
            generated_utc=datetime(2024, 1, 2, tzinfo=timezone.utc))
        assert {p.name for p in written} == {
            "report_summary.txt", "filtered_data.csv", "cpk_by_group.csv"}
        for p in written:
            assert p.exists() and p.stat().st_size > 0
        text = (tmp_path / "report_summary.txt").read_text(encoding="utf-8")
        assert "2024-01-02T00:00:00+00:00" in text
        assert "T123 | TestNb 12 | MyLabel" in text
        back = pd.read_csv(tmp_path / "filtered_data.csv")
        assert len(back) == 4

    def test_skips_cpk_file_when_empty(self, tmp_path):
        df = make_df()
        s = compute_stats(df["Value_num"].to_numpy(dtype=float), 0.0, 10.0)
        written = write_report(tmp_path, df, s, 75.0, "title", cpk_df=pd.DataFrame())
        assert {p.name for p in written} == {"report_summary.txt", "filtered_data.csv"}

    def test_empty_dataframe_writes_header_only_csv(self, tmp_path):
        s = compute_stats(np.array([], dtype=float), None, None)
        written = write_report(tmp_path, pd.DataFrame(), s, float("nan"), "empty")
        summary = next(p for p in written if p.name == "report_summary.txt")
        assert "N (samples): 0" in summary.read_text(encoding="utf-8")
