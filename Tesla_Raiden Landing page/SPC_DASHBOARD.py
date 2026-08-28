#!/usr/bin/env python3
"""
SPC_DASHBOARD.py
================
Streamlit front end for the Unified TDF Log Consolidator & Interactive SPC
Dashboard. Parsing, consolidation, queries, and statistics live in the
import-safe `spc_core` package; this file is a thin UI adapter that adds
caching and presentation only.
"""

import logging
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import theme_utils
from spc_core import query as core_query
from spc_core.consolidation import TABLE, run_consolidation
from spc_core.query import build_where_clause
from spc_core.stats import compute_stats

st.set_page_config(page_title="Flex - Teradyne UltraFlexPlus Dragon SPC Dashboard", page_icon="📊", layout="wide")

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
log = logging.getLogger("tdf_consolidator")

# ----------------------------------------------------------------------------
# SLICER CONFIGURATION (UI concern)
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

# ----------------------------------------------------------------------------
# CACHED ACCESS TO THE SPC_CORE QUERY LAYER
# ----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_connection(db_path: str, _mtime: float):
    return core_query.connect(db_path)


@st.cache_data(show_spinner=False)
def get_columns(db_path: str, _mtime: float):
    return core_query.get_columns(get_connection(db_path, _mtime))


@st.cache_data(show_spinner="Loading filter options...")
def get_distinct_values(db_path: str, _mtime: float, column: str, limit: int = 5000):
    return core_query.get_distinct_values(get_connection(db_path, _mtime), column, limit)


@st.cache_data(show_spinner="Loading TestNb / TestLabel options...")
def get_testnb_label_pairs(db_path: str, _mtime: float, limit: int = None):
    return core_query.get_testnb_label_pairs(get_connection(db_path, _mtime), limit)


@st.cache_data(show_spinner=False)
def get_dataset_summary(db_path: str, _mtime: float):
    """High-level counts for the sidebar header: total rows plus distinct TestNb/DUT/Unit counts."""
    return core_query.get_dataset_summary(get_connection(db_path, _mtime))


@st.cache_data(show_spinner="Querying filtered data...")
def query_filtered(db_path: str, _mtime: float, where_sql: str, params: list, row_cap: int):
    return core_query.query_filtered(get_connection(db_path, _mtime), where_sql, params, row_cap)


# ----------------------------------------------------------------------------
# CHART BUILDERS (Plotly presentation layer)
# ----------------------------------------------------------------------------
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
LOGO_PATH = BASE_DIR / "assets" / "logo.png"  # drop your own company logo here if you have one


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
                            get_connection.clear()
                            get_columns.clear()
                            get_dataset_summary.clear()
                            get_testnb_label_pairs.clear()
                            get_distinct_values.clear()
                            query_filtered.clear()
                            st.success(f"Parsing Complete! Cleaned {r_count} data entries across {f_count} TDF logfiles.")
                        except Exception as ex:
                            log.exception("Consolidation failed")
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
