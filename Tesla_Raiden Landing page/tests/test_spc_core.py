"""Deterministic tests for spc_core: parser, consolidator, queries, statistics."""

import csv
import sqlite3

import numpy as np
import pandas as pd
import pytest
from pytest import approx

from spc_core import consolidation as cons
from spc_core.consolidation import OUTPUT_COLUMNS, TABLE, run_consolidation
from spc_core.query import (
    build_where_clause,
    connect,
    get_columns,
    get_dataset_summary,
    get_distinct_values,
    get_testnb_label_pairs,
    query_filtered,
)
from spc_core.stats import compute_stats
from spc_core.tdf_parser import iter_output_rows, parse_tdf_file, safe_float


TDF_TEXT = (
    "TDF Version: 8.00.00\n"
    "Tester: UFP-012\n"
    "IG-XL VERSION: 7.2.1\n"
    "IG-XL BUILD: 20230301\n"
    "CURRENT TIME: 03/14/2024 10:11:12\n"
    "SYSTEM TYPE: UltraFlexPlus\n"
    "PROGRAM NAME: DRAGON_FT\n"
    "SYSTEM SERIAL NUMBER: SN123\n"
    "FileNumber: 7\n"
    "Board Configuration:\n"
    "0.0\tOPTA\tMODSN1\t2024-01-01\t638-249-30\tCAL_OK\n"
    "1.0\tOPTB\tOTHERSN\t2024-02-02\t999-999-99\tUNCAL\n"
    "P/F\tSlot\tSubslot\tInstrument\tTestGrp2\tTestGrp1\n"
    "F|0|0|PS1600|GP2|GP1|FUNC|12|CH0|CONT|1.0|0.0|0.5|2.0|V|0.1|1|MyLabel|p=1\n"
    "P|1|0|PS1600|GP2|GP1|FUNC|12|CH0|CONT|1.0|0.0|1.5|2.0|V|0.0|1|MyLabel|p=2\n"
    "P|0|0|PS1600|GP2|GP1|FUNC|13|CH1|CONT|abc|0.0|1.25|2.0|V|x|1|Lbl3|q\n"
    "\n"
    "DIB\tjunk\n"
    "X|Y|Z\n"
)


def make_tdf_tree(base):
    tdf_dir = base / "SN001_003" / "PROD_02_EVT_FT_T123_ATP-1-2" / "20240102_030405"
    tdf_dir.mkdir(parents=True)
    tdf_file = tdf_dir / "TestData.tdf"
    tdf_file.write_text(TDF_TEXT, encoding="utf-8")
    return tdf_file


def vals(values, lsl=None, usl=None):
    return compute_stats(np.asarray(values, dtype=float), lsl, usl)


class TestComputeStats:
    def test_no_samples(self):
        s = vals([], 0.0, 10.0)
        assert s["N"] == 0
        for k in ("Mean", "StdDev", "Min", "Max", "Cp", "Cpk", "Sigma_Level", "PctOutOfSpec"):
            assert np.isnan(s[k])

    def test_one_sample(self):
        s = vals([5.0], 0.0, 10.0)
        assert s["N"] == 1
        assert s["Mean"] == 5.0
        assert s["StdDev"] == 0.0
        assert np.isnan(s["Cp"]) and np.isnan(s["Cpk"]) and np.isnan(s["Sigma_Level"])
        assert s["PctOutOfSpec"] == 0.0

    def test_two_sided_known_values(self):
        s = vals([2.0, 4.0, 6.0, 8.0], 0.0, 10.0)
        std = np.std([2, 4, 6, 8], ddof=1)
        assert s["Mean"] == 5.0
        assert s["StdDev"] == approx(std)
        assert s["Cp"] == approx(10.0 / (6 * std))
        assert s["Cpk"] == approx(5.0 / (3 * std))
        assert s["Sigma_Level"] == approx(s["Cpk"] * 3)
        assert s["PctOutOfSpec"] == 0.0
        assert s["Min"] == 2.0 and s["Max"] == 8.0

    def test_upper_only_limit(self):
        s = vals([2.0, 4.0, 6.0, 8.0], None, 4.5)
        std = np.std([2, 4, 6, 8], ddof=1)
        assert s["Cpk"] == approx((4.5 - 5.0) / (3 * std))
        assert np.isnan(s["Cp"])
        assert np.isnan(s["Sigma_Level"]) or s["Sigma_Level"] == approx(s["Cpk"] * 3)
        assert np.isnan(s["PctOutOfSpec"])
        assert s["Sigma_Level"] == approx(((4.5 - 5.0) / (3 * std)) * 3)

    def test_lower_only_limit(self):
        s = vals([2.0, 4.0, 6.0, 8.0], 4.5, None)
        std = np.std([2, 4, 6, 8], ddof=1)
        assert s["Cpk"] == approx((5.0 - 4.5) / (3 * std))
        assert np.isnan(s["Cp"])
        assert np.isnan(s["PctOutOfSpec"])

    def test_zero_variation_in_spec(self):
        s = vals([5.0, 5.0, 5.0], 0.0, 10.0)
        assert s["StdDev"] == 0.0
        assert np.isnan(s["Cpk"])
        assert s["PctOutOfSpec"] == 0.0

    def test_zero_variation_out_of_spec(self):
        s = vals([11.0, 11.0], 0.0, 10.0)
        assert s["StdDev"] == 0.0
        assert np.isnan(s["Cpk"])
        assert s["PctOutOfSpec"] == 100.0

    def test_boundary_equality_is_in_spec(self):
        s = vals([0.0, 10.0], 0.0, 10.0)
        assert s["PctOutOfSpec"] == 0.0


class TestParser:
    def test_safe_float(self):
        assert safe_float(None) is None
        assert safe_float("") is None
        assert safe_float("abc") is None
        assert safe_float("-1.5e2") == -150.0

    def test_parse_tdf_file_sections(self, tmp_path):
        f = tmp_path / "x.tdf"
        f.write_text(TDF_TEXT, encoding="utf-8")
        meta, board, rows = parse_tdf_file(f)
        assert meta["ProgramName"] == "DRAGON_FT"
        assert meta["FileNumber"] == "7"
        assert board[("0", "0")]["ModuleSN"] == "MODSN1"
        assert board[("1", "0")]["ModulePartNum"] == "999-999-99"
        assert len(rows) == 3
        assert rows[0]["TestLabel"] == "MyLabel" and rows[0]["TestParameters"] == "p=1"

    def test_iter_output_rows_context_and_dut(self, tmp_path):
        tdf_file = make_tdf_tree(tmp_path)
        rows = list(iter_output_rows(tdf_file, tmp_path, ["638-249-30"]))
        r0, r2 = rows[0], rows[2]
        assert r0["UnitSN"] == "SN001" and r0["RunAttempt"] == "003"
        assert r0["ProductCode"] == "PROD" and r0["FolderRev"] == "02"
        assert r0["TestStep"] == "T123" and r0["ATP"] == "1-2"
        assert r0["RunTimestampFolder"] == "2024-01-02 03:04:05"
        assert r0["FileNumber"] == "7"
        assert r0["DUT_SN"] == "MODSN1"
        assert r0["Value_num"] == 0.5 and r0["LowLim_num"] == 0.0 and r0["HighLim_num"] == 2.0
        assert rows[1]["DUT_SN"] == ""
        assert r2["ExpVal_num"] is None and r2["Value_num"] == 1.25

    def test_shallow_tree_unit_from_root_name(self, tmp_path):
        step_dir = tmp_path / "SN777_005" / "PROD_01_EVT_FT_T999_ATP-3-4" / "20240101_010203"
        step_dir.mkdir(parents=True)
        (step_dir / "TestData.tdf").write_text(TDF_TEXT, encoding="utf-8")
        root = tmp_path / "SN777_005"
        rows = list(iter_output_rows(step_dir / "TestData.tdf", root, ["638-249-30"]))
        assert rows[0]["UnitSN"] == "SN777" and rows[0]["RunAttempt"] == "005"

    def test_unmatched_root_name_yields_whole_name(self, tmp_path):
        step_dir = tmp_path / "PLAINNAME" / "PROD_01_EVT_FT_T999_ATP-3-4" / "20240101_010203"
        step_dir.mkdir(parents=True)
        (step_dir / "TestData.tdf").write_text(TDF_TEXT, encoding="utf-8")
        root = tmp_path / "PLAINNAME"
        rows = list(iter_output_rows(step_dir / "TestData.tdf", root, ["638-249-30"]))
        assert rows[0]["UnitSN"] == "PLAINNAME" and rows[0]["RunAttempt"] == ""


@pytest.fixture()
def consolidated(tmp_path):
    make_tdf_tree(tmp_path / "tree")
    out_dir = tmp_path / "out"
    files, rows = run_consolidation(tmp_path / "tree", out_dir / "results.csv", out_dir / "results.db")
    return tmp_path, out_dir, files, rows


class TestConsolidation:
    def test_happy_path_counts_and_outputs(self, consolidated):
        _, out_dir, files, rows = consolidated
        assert (files, rows) == (1, 3)
        conn = sqlite3.connect(out_dir / "results.db")
        try:
            assert conn.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] == 3
            cols = [r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})").fetchall()]
            assert cols == OUTPUT_COLUMNS
            meta = conn.execute(
                "SELECT source_root, parser_version, n_tdf_files, n_rows FROM consolidation_meta"
            ).fetchone()
            assert meta[1] == "2" and meta[2] == 1 and meta[3] == 3
        finally:
            conn.close()
        with open(out_dir / "results.csv", newline="", encoding="utf-8") as fh:
            header = next(csv.reader(fh))
        assert header == OUTPUT_COLUMNS

    def test_atomic_replacement_preserves_previous_db(self, tmp_path, monkeypatch):
        make_tdf_tree(tmp_path / "tree")
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        db_path = out_dir / "results.db"
        prev = sqlite3.connect(db_path)
        prev.execute("CREATE TABLE keep_me (x INTEGER)")
        prev.execute("INSERT INTO keep_me VALUES (42)")
        prev.commit()
        prev.close()

        def boom(*a, **k):
            raise RuntimeError("boom")
        monkeypatch.setattr(cons, "iter_output_rows", boom)

        with pytest.raises(RuntimeError):
            run_consolidation(tmp_path / "tree", out_dir / "results.csv", db_path)

        assert not list(out_dir.glob("*.tmp*"))
        conn = sqlite3.connect(db_path)
        try:
            assert conn.execute("SELECT x FROM keep_me").fetchone() == (42,)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            assert TABLE not in tables
        finally:
            conn.close()

    def test_missing_root_raises(self, tmp_path):
        with pytest.raises(ValueError):
            run_consolidation(tmp_path / "nope", tmp_path / "a.csv", tmp_path / "a.db")

    def test_no_tdf_files_returns_zero_without_outputs(self, tmp_path):
        (tmp_path / "empty").mkdir()
        files, rows = run_consolidation(tmp_path / "empty", tmp_path / "o.csv", tmp_path / "o.db")
        assert (files, rows) == (0, 0)
        assert not (tmp_path / "o.db").exists()


class TestQueries:
    def test_columns_distinct_pairs_summary(self, consolidated):
        tmp_path, out_dir, _, _ = consolidated
        conn = connect(out_dir / "results.db")
        try:
            assert get_columns(conn)[:5] == OUTPUT_COLUMNS[:5]
            assert get_distinct_values(conn, "Tester") == ["UFP-012"]
            pairs = get_testnb_label_pairs(conn)
            assert set(zip(pairs["TestNb"], pairs["TestLabel"])) == {
                ("12", "MyLabel"), ("13", "Lbl3"),
            }
            summary = get_dataset_summary(conn)
            assert summary["total_rows"] == 3
            assert summary["n_unit"] == 1 and summary["n_dut"] == 1 and summary["n_testnb"] == 2
        finally:
            conn.close()

    def test_where_clause_and_query_filtered(self, consolidated):
        tmp_path, out_dir, _, _ = consolidated
        conn = connect(out_dir / "results.db")
        try:
            sql, params = build_where_clause({"TestNb": ["12"]})
            assert sql == '"TestNb" IN (?)' and params == ["12"]
            df = query_filtered(conn, sql, params, 100)
            assert sorted(df["Value_num"].tolist()) == [0.5, 1.5]

            or_sql = '("TestNb" = ? AND "TestLabel" = ?)'
            full_sql, full_params = build_where_clause({}, [(or_sql, ["13", "Lbl3"])])
            assert full_sql == or_sql
            df2 = query_filtered(conn, full_sql, full_params, 100)
            assert df2["Value_num"].tolist() == [1.25]

            everything_sql, _ = build_where_clause({})
            assert everything_sql == "1=1"
            df3 = query_filtered(conn, everything_sql, [], 100)
            assert len(df3) == 3
            assert pd.isna(df3.loc[df3["TestNb"] == "13", "ExpVal_num"]).all()
        finally:
            conn.close()
