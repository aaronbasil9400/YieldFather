#!/usr/bin/env python3
"""
app.py
======
Unified TDF Log Consolidator & Interactive SPC Dashboard.
Combines data parsing and SQLite compilation with automated analysis.
"""

import csv
import datetime as dt
import logging
import os
import re
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import theme_utils

st.set_page_config(page_title="Flex - Teradyne UltraFlexPlus Dragon SPC Dashboard", page_icon="📊", layout="wide")

# Setup Logging
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger("tdf_consolidator")

# ----------------------------------------------------------------------------
# CONSTANTS & CONFIGURATIONS FROM CONSOLIDATOR[span_2](start_span)[span_2](end_span)
# ----------------------------------------------------------------------------
FIXED_COLUMNS = [
    "Result", "Slot", "Subslot", "Instrument", "TestGrp2", "TestGrp1",
    "TestType", "TestNb", "Channel", "TypeofTest", "ExpVal", "LowLim",
    "Value", "HighLim", "Units", "PctDelta", "LpCnt",
]
N_FIXED = len(FIXED_COLUMNS)
NUMERIC_COLS = ["ExpVal", "LowLim", "Value", "HighLim", "PctDelta"]
DEFAULT_DUT_PARTNUMBERS = ["638-249-30", "627-001-30", "627-000-40"]

OUTPUT_COLUMNS = (
    ["SourceFile", "FolderBin", "RootFolder", "UnitSN", "RunAttempt",
     "TestStepFolder", "ProductCode", "FolderRev", "TestStep", "ATP",
     "RunTimestampFolder", "DataFileName", "FileNumber"]
    + ["TDFVersion", "Tester", "IGXLVersion", "IGXLBuild", "TestDateTime",
       "SystemType", "ProgramName", "TesterSystemSN"]
    + ["DUT_SN", "ModuleSN", "ModulePartNum", "ModuleRevDate", "ModuleCalState", "ModuleOptionName"]
    + FIXED_COLUMNS
    + ["ExpVal_num", "LowLim_num", "Value_num", "HighLim_num", "PctDelta_num"]
    + ["TestLabel", "TestParameters"]
)

# ----------------------------------------------------------------------------
# CONSTANTS FROM DASHBOARD[span_3](start_span)[span_3](end_span)
# ----------------------------------------------------------------------------
PRIMARY_SLICERS = [
    ("UnitSN", "UnitSN"),
    ("ModuleSN", "ModuleSN"),
    ("ProgramName", "ProgramName"),
    ("TestStep", "TestStep"),
    ("TestNbLabel", "TestNb / TestLabel"),
    ("Channel", "Channel"),
    ("Tester", "TestStation (Tester)"),
    ("FolderBin", "Bin (PASS/FAIL folder)"),
    ("Result", "Result (row-level PASS/FAIL)"),
]

SECONDARY_SLICERS = [
    ("RunAttempt", "RunAttempt"), ("DUT_SN", "DUT_SN"), ("ProductCode", "ProductCode"),
    ("FolderRev", "FolderRev"), ("ATP", "ATP"), ("Instrument", "Instrument"),
    ("TestGrp1", "TestGrp1"), ("TestGrp2", "TestGrp2"), ("TypeofTest", "TypeofTest"),
    ("Slot", "Slot"), ("Subslot", "Subslot"), ("LpCnt", "LpCnt (loop count)"),
    ("ModulePartNum", "ModulePartNum"), ("ModuleCalState", "ModuleCalState"),
    ("IGXLVersion", "IGXLVersion"), ("SystemType", "SystemType"), ("Units", "Units"),
]

TABLE = "test_results"

# ----------------------------------------------------------------------------
# TDF PARSING ENGINE HELPER METHODS[span_4](start_span)[span_4](end_span)
# ----------------------------------------------------------------------------
ROOT_FOLDER_RE = re.compile(r"^(?P<sn>.+?)_(?P<run>\d+)$")
STEP_FOLDER_RE = re.compile(
    r"^(?P<product>[A-Za-z0-9]+)_(?P<rev>\d+)_(?P<phase>[A-Za-z]+)_(?P<stage>[A-Za-z]+)_"
    r"(?P<teststep>[A-Za-z0-9]+)_ATP-(?P<atp>[\d\-]+)$"
)
TIMESTAMP_FOLDER_RE = re.compile(r"^(?P<ts>\d{8}_\d{6})$")
SLOT_ROW_RE = re.compile(r"^\d+\.\d+\t")

def parse_root_folder(name: str):
    m = ROOT_FOLDER_RE.match(name)
    return (m.group("sn"), m.group("run")) if m else (name, "")

def parse_step_folder(name: str):
    m = STEP_FOLDER_RE.match(name)
    return (m.group("product"), m.group("rev"), m.group("teststep"), m.group("atp")) if m else ("", "", name, "")

def parse_run_timestamp(name: str):
    m = TIMESTAMP_FOLDER_RE.match(name)
    if not m: return name, None
    ts_raw = m.group("ts")
    try:
        return ts_raw, dt.datetime.strptime(ts_raw, "%Y%m%d_%H%M%S").isoformat(sep=" ")
    except ValueError:
        return ts_raw, None

def find_ancestor_folders(tdf_path: Path, root: Path):
    parts = tdf_path.relative_to(root).parts[:-1]
    run_ts = parts[-1] if len(parts) >= 1 else ""
    step = parts[-2] if len(parts) >= 2 else ""
    rootf = parts[-3] if len(parts) >= 3 else ""
    binf = parts[-4] if len(parts) >= 4 else ""
    return binf, rootf, step, run_ts

def safe_float(s):
    if s is None or s == "": return None
    try: return float(s)
    except ValueError: return None

def parse_tdf_file(path: Path):
    header_meta = {v: "" for v in HEADER_KEYS.values()}
    board_cfg, rows = {}, []
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        section = "header"
        for raw_line in f:
            line = raw_line.rstrip("\r\n")
            if section == "header":
                if line.startswith("Board Configuration:"):
                    section = "boardcfg"
                    continue
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip()
                    if key in HEADER_KEYS: header_meta[HEADER_KEYS[key]] = val.strip()
                continue
            if section == "boardcfg":
                if line.startswith("P/F\t"):
                    section = "data"
                    continue
                if SLOT_ROW_RE.match(line):
                    cols = line.split("\t")
                    slot_part, _, subslot_part = cols[0].partition(".")
                    board_cfg[(slot_part, subslot_part)] = {
                        "ModuleSN": cols[2].strip() if len(cols) > 2 else "",
                        "ModulePartNum": cols[4].strip() if len(cols) > 4 else "",
                        "ModuleRevDate": cols[3].strip() if len(cols) > 3 else "",
                        "ModuleCalState": cols[5].strip() if len(cols) > 5 else "",
                        "ModuleOptionName": cols[1].strip() if len(cols) > 1 else "",
                    }
                continue
            if section == "data":
                if not line or line.startswith("DIB\t"): continue
                parts_ = line.split("|", N_FIXED)
                if len(parts_) < N_FIXED + 1: continue
                fixed = parts_[:N_FIXED]
                test_label, _, test_params = parts_[N_FIXED].rpartition("|")
                row = dict(zip(FIXED_COLUMNS, fixed))
                row["TestLabel"], row["TestParameters"] = test_label, test_params
                rows.append(row)
    return header_meta, board_cfg, rows

HEADER_KEYS = {
    "TDF Version": "TDFVersion", "Tester": "Tester", "IG-XL VERSION": "IGXLVersion",
    "IG-XL BUILD": "IGXLBuild", "CURRENT TIME": "TestDateTime", "SYSTEM TYPE": "SystemType",
    "PROGRAM NAME": "ProgramName", "SYSTEM SERIAL NUMBER": "TesterSystemSN", "FileNumber": "FileNumber",
}

def is_dut_partnum(partnum: str, dut_partnumbers) -> bool:
    partnum = (partnum or "").strip()
    if not partnum: return False
    return any(partnum == pn or partnum.startswith(pn) for pn in dut_partnumbers if pn.strip())

def iter_output_rows(tdf_path: Path, root: Path, dut_partnumbers):
    header_meta, board_cfg, data_rows = parse_tdf_file(tdf_path)
    binf, rootf, step, run_ts_folder = find_ancestor_folders(tdf_path, root)
    unit_sn, run_attempt = parse_root_folder(rootf)
    product, folder_rev, test_step, atp = parse_step_folder(step)
    run_ts_raw, run_ts_iso = parse_run_timestamp(run_ts_folder)
    file_number = header_meta.get("FileNumber", "").strip() or "1"

    base_meta = {
        "SourceFile": str(tdf_path), "FolderBin": binf, "RootFolder": rootf, "UnitSN": unit_sn,
        "RunAttempt": run_attempt, "TestStepFolder": step, "ProductCode": product, "FolderRev": folder_rev,
        "TestStep": test_step, "ATP": atp, "RunTimestampFolder": run_ts_iso or run_ts_raw,
        "DataFileName": tdf_path.name, "FileNumber": file_number, "TDFVersion": header_meta.get("TDFVersion", ""),
        "Tester": header_meta.get("Tester", ""), "IGXLVersion": header_meta.get("IGXLVersion", ""),
        "IGXLBuild": header_meta.get("IGXLBuild", ""), "TestDateTime": header_meta.get("TestDateTime", "").strip(),
        "SystemType": header_meta.get("SystemType", ""), "ProgramName": header_meta.get("ProgramName", ""),
        "TesterSystemSN": header_meta.get("TesterSystemSN", ""),
    }
    empty_module = {"ModuleSN": "", "ModulePartNum": "", "ModuleRevDate": "", "ModuleCalState": "", "ModuleOptionName": ""}

    for row in data_rows:
        mod = board_cfg.get((row["Slot"].strip(), row["Subslot"].strip()), empty_module)
        out = dict(base_meta)
        out.update(mod)
        out["DUT_SN"] = mod["ModuleSN"] if is_dut_partnum(mod.get("ModulePartNum", ""), dut_partnumbers) else ""
        out.update(row)
        for c in NUMERIC_COLS: out[f"{c}_num"] = safe_float(row.get(c))
        yield out

def run_consolidation(root_dir, csv_out, db_out, pass_only=False, fail_only=False):
    root = Path(root_dir).expanduser().resolve()
    if not root.is_dir(): raise ValueError(f"Root directory not found: {root}")
    tdf_files = sorted(root.rglob("*Data*.tdf"))
    if not tdf_files: return 0, 0
    
    Path(csv_out).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_out)
    cur = conn.cursor()
    create_sql_cols = [f'"{c}" REAL' if c.endswith("_num") else f'"{c}" TEXT' for c in OUTPUT_COLUMNS]
    cur.execute(f'DROP TABLE IF EXISTS {TABLE}')
    cur.execute(f'CREATE TABLE {TABLE} ({", ".join(create_sql_cols)})')
    for idx_col in ["UnitSN", "TestStep", "TestNb", "Channel", "ModuleSN", "TestLabel", "DUT_SN", "Tester", "FolderBin"]:
        cur.execute(f'CREATE INDEX IF NOT EXISTS idx_{idx_col} ON {TABLE} ("{idx_col}")')
    conn.commit()

    insert_sql = f'INSERT INTO {TABLE} ({", ".join(f"""\"{c}\"""" for c in OUTPUT_COLUMNS)}) VALUES ({", ".join("?" for _ in OUTPUT_COLUMNS)})'
    sqlite_batch = []
    n_rows = 0

    with open(csv_out, "w", newline="", encoding="utf-8") as fout:
        writer = csv.DictWriter(fout, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for tdf_path in tdf_files:
            for out_row in iter_output_rows(tdf_path, root, DEFAULT_DUT_PARTNUMBERS):
                if pass_only and out_row["Result"].strip().upper() != "PASS": continue
                if fail_only and out_row["Result"].strip().upper() != "FAIL": continue
                n_rows += 1
                writer.writerow(out_row)
                sqlite_batch.append([out_row.get(c) for c in OUTPUT_COLUMNS])
                if len(sqlite_batch) >= 5000:
                    cur.executemany(insert_sql, sqlite_batch)
                    conn.commit()
                    sqlite_batch.clear()
        if sqlite_batch:
            cur.executemany(insert_sql, sqlite_batch)
            conn.commit()
    conn.close()
    return len(tdf_files), n_rows

# ----------------------------------------------------------------------------
# DASHBOARD CORE INTERACTIVE ENGINE MODULES[span_5](start_span)[span_5](end_span)
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_connection(db_path: str, _mtime: float):
    return sqlite3.connect(db_path, check_same_thread=False)

@st.cache_data(show_spinner=False)
def get_columns(db_path: str, _mtime: float):
    conn = get_connection(db_path, _mtime)
    return [r[1] for r in conn.execute(f"PRAGMA table_info({TABLE})").fetchall()]

@st.cache_data(show_spinner="Loading filter options...")
def get_distinct_values(db_path: str, _mtime: float, column: str, limit: int = 5000):
    conn = get_connection(db_path, _mtime)
    q = f'SELECT DISTINCT "{column}" FROM {TABLE} WHERE "{column}" IS NOT NULL AND "{column}" != "" ORDER BY 1 LIMIT ?'
    try: return pd.read_sql(q, conn, params=(limit,)).iloc[:, 0].tolist()
    except Exception: return []

@st.cache_data(show_spinner="Loading TestNb / TestLabel options...")
def get_testnb_label_pairs(db_path: str, _mtime: float, limit: int = 20000):
    conn = get_connection(db_path, _mtime)
    q = f'SELECT DISTINCT "TestNb", "TestLabel" FROM {TABLE} WHERE "TestNb" IS NOT NULL AND "TestNb" != "" ORDER BY "TestNb" LIMIT ?'
    return pd.read_sql(q, conn, params=(limit,))

@st.cache_data(show_spinner=False)
def get_dataset_summary(db_path: str, _mtime: float):
    """High-level counts for the sidebar header: total rows plus distinct TestNb/DUT/Unit counts."""
    conn = get_connection(db_path, _mtime)
    def count_distinct(col):
        q = f'SELECT COUNT(DISTINCT "{col}") FROM {TABLE} WHERE "{col}" IS NOT NULL AND "{col}" != ""'
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
    filters: dict of col -> list of allowed values, AND-ed together (existing behavior).
    or_clauses: list of (sql_fragment, params) tuples, each appended as its own
                AND-ed clause. Used for the TestNb/TestLabel test-selection block,
                where the fragment itself may internally OR together a broad
                "any TestLabel under this TestNb" match with specific fine-control
                TestNb+TestLabel pairs.
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

@st.cache_data(show_spinner="Querying filtered data...")
def query_filtered(db_path: str, _mtime: float, where_sql: str, params: list, row_cap: int):
    conn = get_connection(db_path, _mtime)
    cols = ["Value_num", "LowLim_num", "HighLim_num", "ExpVal_num", "Result", "RunTimestampFolder",
            "DUT_SN", "UnitSN", "TestStep", "TestNb", "Channel", "Units", "TestLabel", "Tester", "FolderBin"]
    q = f'SELECT {", ".join(f"""\"{c}\"""" for c in cols)} FROM {TABLE} WHERE {where_sql} ORDER BY "RunTimestampFolder" LIMIT ?'
    return pd.read_sql(q, conn, params=params + [row_cap])

def compute_stats(values: np.ndarray, lsl, usl):
    n = len(values)
    out = {"N": n, "Mean": np.nan, "StdDev": np.nan, "Min": np.nan, "Max": np.nan, "Cp": np.nan, "Cpk": np.nan, "Sigma_Level": np.nan, "PctOutOfSpec": np.nan}
    if n == 0: return out
    out["Mean"], out["Min"], out["Max"] = float(np.mean(values)), float(np.min(values)), float(np.max(values))
    out["StdDev"] = float(np.std(values, ddof=1)) if n > 1 else 0.0
    std = out["StdDev"]
    if std > 0:
        cpu = (usl - out["Mean"]) / (3 * std) if usl is not None and not np.isnan(usl) else np.nan
        cpl = (out["Mean"] - lsl) / (3 * std) if lsl is not None and not np.isnan(lsl) else np.nan
        candidates = [v for v in (cpu, cpl) if not np.isnan(v)]
        if candidates: out["Cpk"] = min(candidates)
        if lsl is not None and usl is not None and not np.isnan(lsl) and not np.isnan(usl):
            out["Cp"] = (usl - lsl) / (6 * std)
        if not np.isnan(out["Cpk"]): out["Sigma_Level"] = out["Cpk"] * 3
    if lsl is not None and usl is not None and not np.isnan(lsl) and not np.isnan(usl):
        out["PctOutOfSpec"] = 100.0 * np.sum((values < lsl) | (values > usl)) / n
    return out

def build_spc_chart(df: pd.DataFrame, stats: dict, lsl, usl, title: str):
    x, y = list(range(1, len(df) + 1)), df["Value_num"].tolist()
    hover = [f"UnitSN: {u}<br>DUT_SN: {d}<br>Channel: {c}<br>Result: {r}<br>Time: {t}"
             for u, d, c, r, t in zip(df["UnitSN"], df["DUT_SN"], df["Channel"], df["Result"], df["RunTimestampFolder"])]
    mean, std = stats["Mean"], stats["StdDev"]
    ucl = mean + 3 * std if not np.isnan(mean) and not np.isnan(std) else None
    lcl = mean - 3 * std if not np.isnan(mean) and not np.isnan(std) else None

    colors = []
    for val in y:
        if (lsl is not None and not np.isnan(lsl) and val < lsl) or (usl is not None and not np.isnan(usl) and val > usl): colors.append("#EF4444")
        elif (ucl is not None and val > ucl) or (lcl is not None and val < lcl): colors.append("#F59E0B")
        else: colors.append("#10B981")

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines+markers", name="Measured Value", line=dict(color="#64748B", width=1.2), marker=dict(color=colors, size=7), text=hover, hoverinfo="text+y"))
    if mean is not None and not np.isnan(mean): fig.add_hline(y=mean, line=dict(color="#3B82F6", width=1.8), annotation_text=f"Mean={mean:.4g}")
    if ucl is not None: fig.add_hline(y=ucl, line=dict(color="#F59E0B", dash="dash", width=1.5), annotation_text=f"UCL={ucl:.4g}")
    if lcl is not None: fig.add_hline(y=lcl, line=dict(color="#F59E0B", dash="dash", width=1.5), annotation_text=f"LCL={lcl:.4g}")
    if usl is not None and not np.isnan(usl): fig.add_hline(y=usl, line=dict(color="#EF4444", dash="dot", width=1.8), annotation_text=f"USL={usl:.4g}", annotation_position="top right")
    if lsl is not None and not np.isnan(lsl): fig.add_hline(y=lsl, line=dict(color="#EF4444", dash="dot", width=1.8), annotation_text=f"LSL={lsl:.4g}", annotation_position="bottom right")
    fig.update_layout(title=title, xaxis_title="Sample #", yaxis_title="Measured Value", height=520, showlegend=False)
    return theme_utils.update_plotly_theme(fig)

def build_histogram(df: pd.DataFrame, stats: dict, lsl, usl):
    fig = go.Figure(go.Histogram(x=df["Value_num"], nbinsx=30, marker_color="#0284C7"))
    if lsl is not None and not np.isnan(lsl): fig.add_vline(x=lsl, line=dict(color="#EF4444", dash="dot", width=1.8))
    if usl is not None and not np.isnan(usl): fig.add_vline(x=usl, line=dict(color="#EF4444", dash="dot", width=1.8))
    if stats["Mean"] is not None and not np.isnan(stats["Mean"]): fig.add_vline(x=stats["Mean"], line=dict(color="#3B82F6", width=1.8))
    fig.update_layout(title="Distribution", height=420)
    return theme_utils.update_plotly_theme(fig)

def kpi_box(label, value, fmt="{:.4g}"):
    display = "N/A" if value is None or (isinstance(value, float) and np.isnan(value)) else fmt.format(value)
    st.metric(label, display)

# ----------------------------------------------------------------------------
# SIDEBAR HEADER (logo/branding, usage guide, dataset summary)
# ----------------------------------------------------------------------------
LOGO_PATH = Path(__file__).parent / "assets" / "logo.png"  # drop your own company logo here if you have one

def render_sidebar_header(summary: dict | None):
    if LOGO_PATH.exists():
        st.image(str(LOGO_PATH), use_container_width=True)
    else:
        st.markdown(
            """
            <div style="text-align:center; padding: 2px 0 10px 0;">
                <span style="font-size:2.1rem;">📊🛠️⚡</span>
                <div style="font-weight:700; font-size:1.05rem; color:#31333F; line-height:1.25;">
                    FLEX - Teradyne UltraFlexPlus<br>Dragon SPC Dashboard
                </div>
                <div style="font-size:0.75rem; color:#808495;">Flex H1 Test Engineering &middot; Penang</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.expander("ℹ️ How to use this tool", expanded=False):
        st.markdown(
            "- **Load data**: run the consolidator on a TDF root folder, or check "
            "*Load existing DB file* to reuse a prior `results.db`.\n"
            "- **Pick a test**: use *Select by TestNb* to include every TestLabel under it, "
            "or *Fine control* for exact TestNb/TestLabel pairs.\n"
            "- **Narrow further**: add slicers (UnitSN, Tester, Channel, etc.) or open "
            "*More filters* for the full list.\n"
            "- **Read the results**: Key Statistics, the SPC Control Chart, and the "
            "Cpk breakdown below all update live as filters change."
        )

    if summary:
        st.caption(
            f"📊 **{summary['total_rows']:,}** rows &nbsp;·&nbsp; "
            f"**{summary['n_testnb']:,}** TestNb &nbsp;·&nbsp; "
            f"**{summary['n_dut']:,}** DUTs &nbsp;·&nbsp; "
            f"**{summary['n_unit']:,}** Units",
            unsafe_allow_html=True,
        )
    st.markdown("---")


# ----------------------------------------------------------------------------
# MAIN APPLICATION EXECUTIVE
# ----------------------------------------------------------------------------
def main():
    theme_utils.apply_global_theme()

    st.title("FLEX - Teradyne UltraFlexPlus Dragon SPC Dashboard")

    with st.sidebar:
        header_placeholder = st.empty()

        st.header("1. Consolidator Section")
        load_existing_db = st.checkbox(
            "📂 Load existing DB file (skip consolidation)",
            value=False,
            help="Point directly at an already-consolidated SQLite DB instead of re-parsing TDF logs.",
        )

        if load_existing_db:
            db_path = st.text_input(
                "Existing DB File Path",
                value="./output_data/results.db",
                help="Full path to a results.db previously produced by the Log Consolidator.",
            )
        else:
            tdf_root = st.text_input("TDF Root Folder", value="./tdf_logs")
            output_dir = st.text_input("Output Storage Folder Path", value="./output_data")

            csv_path = str(Path(output_dir) / "results.csv")
            db_path = str(Path(output_dir) / "results.db")

            if st.button("Run Log Consolidator", type="primary"):
                if not Path(tdf_root).exists():
                    st.error("🚨 Specified TDF Root folder path does not exist!")
                else:
                    with st.spinner("Processing local logs and refreshing DB indices..."):
                        try:
                            f_count, r_count = run_consolidation(tdf_root, csv_path, db_path)
                            st.success(f"Parsing Complete! Cleaned {r_count} data entries across {f_count} TDF logfiles.")
                        except Exception as ex:
                            st.error(f"Execution terminated: {ex}")

        st.markdown("---")
        st.header("2. Dashboard Controls")
        row_cap = st.number_input("Max rows to pull per chart", min_value=1000, max_value=6000000, value=800000, step=1000)

    db_file = Path(db_path).expanduser()
    mtime = db_file.stat().st_mtime if db_file.exists() else None
    db_path_str = str(db_file.resolve()) if db_file.exists() else None

    columns, summary, load_error = [], None, None
    if db_file.exists():
        try:
            columns = get_columns(db_path_str, mtime)
            if not columns:
                load_error = f"No '{TABLE}' table found — is this a valid consolidated results DB?"
            else:
                summary = get_dataset_summary(db_path_str, mtime)
        except Exception as ex:
            load_error = str(ex)

    with header_placeholder.container():
        render_sidebar_header(summary)

    if not db_file.exists():
        if load_existing_db:
            st.info("👈 Enter the path to an existing **.db** file in the sidebar to load it.")
        else:
            st.info("👈 Enter paths and select **Run Log Consolidator** in the sidebar control frame above to load dataset arrays.")
        st.stop()

    if load_error:
        st.error(f"🚨 Couldn't read this DB file: {load_error}")
        st.stop()

    st.sidebar.success(f"Connected: {db_file.name}")
    st.sidebar.header("Slicers")
    filters = {}

    st.sidebar.markdown("**TestNb / TestLabel**")
    tn_df = get_testnb_label_pairs(db_path_str, mtime)
    tn_df["combo"] = tn_df["TestNb"].astype(str) + " — " + tn_df["TestLabel"].fillna("").astype(str)
    combo_map = dict(zip(tn_df["combo"], zip(tn_df["TestNb"], tn_df["TestLabel"])))
    all_testnbs = sorted(tn_df["TestNb"].astype(str).unique().tolist())

    selected_testnb_broad = st.sidebar.multiselect(
        "Select by TestNb (includes every TestLabel)",
        options=all_testnbs,
        help="Pick one or more TestNb values to pull in all rows for that TestNb, "
             "regardless of which TestLabel they carry.",
    )
    selected_combo = st.sidebar.multiselect(
        "Fine control: specific TestNb — TestLabel pairs",
        options=sorted(combo_map.keys()),
        help="Narrow down to exact TestNb + TestLabel combinations. "
             "Adds to (does not replace) any broad TestNb selection above.",
    )

    test_select_parts, test_select_params = [], []
    if selected_testnb_broad:
        test_select_parts.append(f'"TestNb" IN ({",".join("?" for _ in selected_testnb_broad)})')
        test_select_params.extend(selected_testnb_broad)
    if selected_combo:
        combo_parts = []
        for c in selected_combo:
            combo_parts.append('("TestNb" = ? AND "TestLabel" = ?)')
            test_select_params.extend(combo_map[c])
        test_select_parts.append("(" + " OR ".join(combo_parts) + ")")

    has_test_selection = bool(selected_testnb_broad or selected_combo)
    or_clauses = [("(" + " OR ".join(test_select_parts) + ")", test_select_params)] if test_select_parts else []

    for col, label in PRIMARY_SLICERS:
        if col == "TestNbLabel" or col not in columns: continue
        opts = get_distinct_values(db_path_str, mtime, col)
        if opts:
            sel = st.sidebar.multiselect(label, options=opts)
            if sel: filters[col] = sel

    with st.sidebar.expander("More filters"):
        for col, label in SECONDARY_SLICERS:
            if col not in columns: continue
            opts = get_distinct_values(db_path_str, mtime, col)
            if opts:
                sel = st.multiselect(label, options=opts, key=f"sec_{col}")
                if sel: filters[col] = sel

    where_sql, params = build_where_clause(filters, or_clauses)

    if not has_test_selection:
        st.info("👈 Select a **TestNb** (broad) or a **TestNb / TestLabel** pair (fine control) within the sidebar to populate the evaluation engine matrix.")
        st.stop()

    df = query_filtered(db_path_str, mtime, where_sql, params, int(row_cap)).dropna(subset=["Value_num"])
    if df.empty:
        st.warning("No rows match the current filter selection.")
        st.stop()

    group_cols = [c for c in ["TestNb", "Channel"] if df[c].nunique() > 1]
    if group_cols:
        st.warning(f"Warning: Selected filters cross-reference multiple distinct values across {', '.join(group_cols)} variations.")

    lsl = df["LowLim_num"].dropna().iloc[0] if df["LowLim_num"].notna().any() else None
    usl = df["HighLim_num"].dropna().iloc[0] if df["HighLim_num"].notna().any() else None
    stats = compute_stats(df["Value_num"].to_numpy(), lsl, usl)
    test_title = f"{df['TestStep'].iloc[0]} | TestNb {df['TestNb'].iloc[0]} | {df['TestLabel'].iloc[0]}"

    st.subheader("Key Statistics")
    k1, k2, k3, k4, k5, k6, k7, k8, k9, k10 = st.columns(10)
    with k1: kpi_box("Cpk", stats["Cpk"])
    with k2: kpi_box("Cp", stats["Cp"])
    with k3: kpi_box("Sigma Level", stats["Sigma_Level"])
    with k4: kpi_box("Min", stats["Min"])
    with k5: kpi_box("Max", stats["Max"])
    with k6: kpi_box("Mean", stats["Mean"])
    with k7: kpi_box("Std Dev", stats["StdDev"])
    with k8: kpi_box("N (samples)", stats["N"], fmt="{:.0f}")
    with k9: kpi_box("% Out of Spec", stats["PctOutOfSpec"], fmt="{:.2f}%")
    with k10:
        pass_pct = 100.0 * (df["Result"].str.upper() == "PASS").mean() if "Result" in df else np.nan
        kpi_box("% PASS (rows)", pass_pct, fmt="{:.2f}%")

    st.subheader("SPC Control Chart")
    st.plotly_chart(build_spc_chart(df, stats, lsl, usl, test_title), use_container_width=True)

    with st.expander("Distribution / Histogram", expanded=False):
        st.plotly_chart(build_histogram(df, stats, lsl, usl), use_container_width=True)

    if group_cols:
        st.subheader("Cpk by " + " / ".join(group_cols))
        rows = []
        for keys, g in df.groupby(group_cols):
            keys = keys if isinstance(keys, tuple) else (keys,)
            g_lsl = g["LowLim_num"].dropna().iloc[0] if g["LowLim_num"].notna().any() else None
            g_usl = g["HighLim_num"].dropna().iloc[0] if g["HighLim_num"].notna().any() else None
            s = compute_stats(g["Value_num"].to_numpy(), g_lsl, g_usl)
            row = dict(zip(group_cols, keys))
            row.update({"N": s["N"], "Mean": s["Mean"], "StdDev": s["StdDev"], "Cp": s["Cp"], "Cpk": s["Cpk"], "%OutOfSpec": s["PctOutOfSpec"]})
            rows.append(row)
        st.dataframe(pd.DataFrame(rows).sort_values("Cpk"), use_container_width=True)

    with st.expander(f"Raw filtered data ({len(df):,} rows)", expanded=False):
        st.dataframe(df, use_container_width=True, height=600)
        st.download_button("Download filtered data as CSV", df.to_csv(index=False).encode("utf-8"), file_name="filtered_spc_data.csv", mime="text/csv")

if __name__ == "__main__":
    main()