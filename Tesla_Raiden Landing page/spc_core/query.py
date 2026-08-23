"""SQLite query helpers over a consolidated results database.

Plain functions operating on an open connection; caching belongs to each UI
layer. SQL is unchanged from the original SPC_DASHBOARD.py implementations,
except that rows are fetched directly instead of via pd.read_sql so behavior
does not depend on pandas SQL plumbing.
"""

import sqlite3

import pandas as pd

from .consolidation import TABLE


def connect(db_path) -> sqlite3.Connection:
    return sqlite3.connect(str(db_path))


def get_columns(conn):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})").fetchall()]


def get_distinct_values(conn, column: str, limit: int = 5000):
    q = f'SELECT DISTINCT "{column}" FROM {TABLE} WHERE "{column}" IS NOT NULL AND "{column}" != \'\' ORDER BY 1 LIMIT ?'
    try:
        return [r[0] for r in conn.execute(q, (limit,)).fetchall()]
    except Exception:
        return []


def get_testnb_label_pairs(conn, limit=None) -> pd.DataFrame:
    q = (f'SELECT DISTINCT "TestNb", "TestLabel" FROM {TABLE} '
         f'WHERE "TestNb" IS NOT NULL AND "TestNb" != \'\' ORDER BY "TestNb"')
    params = []
    if limit is not None:
        q += " LIMIT ?"
        params.append(limit)
    return pd.DataFrame(conn.execute(q, params).fetchall(), columns=["TestNb", "TestLabel"])


def get_dataset_summary(conn):
    def count_distinct(col):
        q = f'SELECT COUNT(DISTINCT "{col}") FROM {TABLE} WHERE "{col}" IS NOT NULL AND "{col}" != \'\''
        return conn.execute(q).fetchone()[0]
    try:
        return {
            "total_rows": conn.execute(f'SELECT COUNT(*) FROM {TABLE}').fetchone()[0],
            "n_testnb": count_distinct("TestNb"),
            "n_dut": count_distinct("DUT_SN"),
            "n_unit": count_distinct("UnitSN"),
        }
    except Exception:
        return None


def build_where_clause(filters: dict, or_clauses: list = None):
    """
    filters: dict of col -> list of allowed values, AND-ed together.
    or_clauses: list of (sql_fragment, params) tuples appended as their own
                AND-ed clause; used for the TestNb/TestLabel selection block.
    """
    clauses, params = [], []
    for col, values in filters.items():
        if not values: continue
        clauses.append(f'"{col}" IN ({",".join("?" for _ in values)})')
        params.extend(values)
    for clause_str, clause_params in (or_clauses or []):
        if not clause_str: continue
        clauses.append(clause_str)
        params.extend(clause_params)
    return (" AND ".join(clauses), params) if clauses else ("1=1", [])


QUERY_COLUMNS = ["Value_num", "LowLim_num", "HighLim_num", "ExpVal_num", "Result",
                 "RunTimestampFolder", "DUT_SN", "UnitSN", "TestStep", "TestNb",
                 "Channel", "Units", "TestLabel", "Tester", "FolderBin"]


def query_filtered(conn, where_sql: str, params: list, row_cap: int) -> pd.DataFrame:
    q = (f'SELECT {", ".join(f"\"{c}\"" for c in QUERY_COLUMNS)} FROM {TABLE} '
         f'WHERE {where_sql} ORDER BY "RunTimestampFolder" LIMIT ?')
    return pd.DataFrame(conn.execute(q, list(params) + [int(row_cap)]).fetchall(), columns=QUERY_COLUMNS)
