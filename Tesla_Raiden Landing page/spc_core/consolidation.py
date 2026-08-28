"""Consolidation of TDF log trees into results.csv + results.db.

Moved from SPC_DASHBOARD.py with one required behavior change from AGENTS.md:
outputs are built in temporary sibling files and atomically swapped into place,
so an interrupted or failed run can never destroy a previously usable result.
"""

import csv
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .tdf_parser import (
    DEFAULT_DUT_PARTNUMBERS,
    OUTPUT_COLUMNS,
    PARSER_VERSION,
    iter_output_rows,
)

TABLE = "test_results"
INDEX_COLUMNS = ["UnitSN", "TestStep", "TestNb", "Channel", "ModuleSN",
                 "TestLabel", "DUT_SN", "Tester", "FolderBin"]
_BATCH_SIZE = 5000


def _sqlite_sidecars(db_path: Path):
    return [db_path.with_name(db_path.name + suffix) for suffix in ("-journal", "-wal", "-shm")]


def _remove_temp_artifacts(tmp_db: Path, tmp_csv: Path):
    for leftover in [tmp_csv, tmp_db] + _sqlite_sidecars(tmp_db):
        try:
            if leftover.exists():
                leftover.unlink()
        except OSError:
            pass


def _write_consolidation_meta(conn, root, dut_list, pass_only, fail_only, n_files, n_rows):
    conn.execute(
        "CREATE TABLE IF NOT EXISTS consolidation_meta ("
        "created_utc TEXT, source_root TEXT, parser_version TEXT, "
        "config_json TEXT, n_tdf_files INTEGER, n_rows INTEGER)"
    )
    conn.execute(
        "INSERT INTO consolidation_meta VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            str(root),
            PARSER_VERSION,
            json.dumps({"dut_partnumbers": list(dut_list),
                        "pass_only": bool(pass_only), "fail_only": bool(fail_only)}),
            n_files,
            n_rows,
        ),
    )
    conn.commit()


def run_consolidation(root_dir, csv_out, db_out, pass_only=False, fail_only=False,
                      dut_partnumbers=None, progress_cb=None):
    """Parse *Data*.tdf files under root_dir; write csv_out/db_out atomically.

    progress_cb(done, total, filename) is invoked before each file is parsed.

    Returns (n_tdf_files, n_rows). Raises on failure without touching any
    pre-existing outputs.
    """
    root = Path(root_dir).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Root directory not found: {root}")
    tdf_files = sorted(root.rglob("*Data*.tdf"))
    if not tdf_files:
        return 0, 0

    csv_path, db_path = Path(csv_out), Path(db_out)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_db = db_path.with_name(db_path.name + ".tmp")
    tmp_csv = csv_path.with_name(csv_path.name + ".tmp")
    _remove_temp_artifacts(tmp_db, tmp_csv)

    dut_list = DEFAULT_DUT_PARTNUMBERS if dut_partnumbers is None else list(dut_partnumbers)
    conn = sqlite3.connect(tmp_db)
    n_rows = 0
    try:
        cur = conn.cursor()
        create_sql_cols = [f'"{c}" REAL' if c.endswith("_num") else f'"{c}" TEXT' for c in OUTPUT_COLUMNS]
        cur.execute(f'DROP TABLE IF EXISTS {TABLE}')
        cur.execute(f'CREATE TABLE {TABLE} ({", ".join(create_sql_cols)})')
        for idx_col in INDEX_COLUMNS:
            cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{idx_col} ON {TABLE} ("{idx_col}")')
        conn.commit()

        insert_sql = (f'INSERT INTO {TABLE} ({", ".join(f"\"{c}\"" for c in OUTPUT_COLUMNS)}) '
                      f'VALUES ({", ".join("?" for _ in OUTPUT_COLUMNS)})')

        with open(tmp_csv, "w", newline="", encoding="utf-8") as fout:
            writer = csv.DictWriter(fout, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            batch = []
            for i, tdf_path in enumerate(tdf_files):
                if progress_cb:
                    progress_cb(i + 1, len(tdf_files), tdf_path.name)
                for out_row in iter_output_rows(tdf_path, root, dut_list):
                    if pass_only and out_row["Result"].strip().upper() != "PASS":
                        continue
                    if fail_only and out_row["Result"].strip().upper() != "FAIL":
                        continue
                    n_rows += 1
                    writer.writerow(out_row)
                    batch.append([out_row.get(c) for c in OUTPUT_COLUMNS])
                    if len(batch) >= _BATCH_SIZE:
                        cur.executemany(insert_sql, batch)
                        conn.commit()
                        batch.clear()
            if batch:
                cur.executemany(insert_sql, batch)
                conn.commit()

        _write_consolidation_meta(conn, root, dut_list, pass_only, fail_only, len(tdf_files), n_rows)
        conn.close()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        _remove_temp_artifacts(tmp_db, tmp_csv)
        raise

    os.replace(tmp_db, db_path)
    os.replace(tmp_csv, csv_path)
    return len(tdf_files), n_rows
