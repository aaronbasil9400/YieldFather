import re
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import theme_utils

st.set_page_config(page_title="Yield and Defect Analysis", page_icon="📊", layout="wide")

# Apply global CSS variables for native Streamlit light/dark theme support
theme_utils.apply_global_theme()

PART_MASTER = {
    "TDN-640-423-20": {"product": "Raiden", "processes": ["OTC", "HP_TEST", "PT_TEST"]},
    "TDN-638-249-30": {"product": "Raiden", "processes": ["MTF", "MTF Rescreening"]},
    "TDN-630-036-30": {"product": "Tesla", "processes": ["OTC"]},
    "TDN-630-036-32": {"product": "Tesla", "processes": ["OTC"]},
    "TDN-630-035-40": {"product": "Tesla", "processes": ["OTC"]},
    "TDN-627-001-30": {"product": "Tesla", "processes": ["MTF"]},
    "TDN-627-000-40": {"product": "Tesla", "processes": ["MTF"]},
    "TDN-639-977-13": {"product": "Tesla", "processes": ["MTF"]},
    "TDN-625-388-13": {"product": "Tesla", "processes": ["MTF"]},
}

DEFAULT_CSV = "rptTestDetail.csv"


def strip_tdn(value):
    if pd.isna(value):
        return None
    value = str(value).strip()
    m = re.search(r"TDN-\d+-\d+-\d+", value)
    return m.group(0) if m else value or None


def safe_div(n, d):
    return 0.0 if d in (0, None) or pd.isna(d) else float(n) / float(d)


def first_nonnull(*values):
    for v in values:
        if pd.notna(v) and str(v).strip() != "":
            return v
    return None


def parse_date_series(series):
    s = pd.to_datetime(series, errors="coerce", dayfirst=False, format="mixed")
    if s.isna().mean() > 0.3:
        alt = pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed")
        s = s.fillna(alt)
    return s


def load_data(uploaded_file=None, local_path=DEFAULT_CSV):
    if uploaded_file is not None:
        df = pd.read_csv(uploaded_file, engine="python")
    else:
        df = pd.read_csv(local_path, engine="python")

    df.columns = [c.strip() for c in df.columns]

    text_cols = [
        "PartNumber", "TestPartNumber", "CTOBasePartNumber", "TestStation1", "TestResult",
        "CurrentStation", "FailureCode", "FailureRemark", "DefectPart", "DefectDesc",
        "Remark", "RepairStation"
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).replace({"nan": None, "None": None})

    df["TestDate1_dt"] = parse_date_series(df["TestDate1"]) if "TestDate1" in df.columns else pd.NaT
    df["RepairDate_dt"] = parse_date_series(df["RepairDate"]) if "RepairDate" in df.columns else pd.NaT

    df["PN"] = df.apply(
        lambda r: first_nonnull(
            r.get("TestPartNumber"),
            r.get("CTOBasePartNumber"),
            strip_tdn(r.get("PartNumber"))
        ),
        axis=1
    )
    df["PN"] = df["PN"].apply(strip_tdn)
    df["Product"] = df["PN"].map(lambda x: PART_MASTER.get(x, {}).get("product", "Unmapped") if x else "Unmapped")

    def process_hint(row):
        pn = row.get("PN")
        station = str(row.get("TestStation1") or "").upper().strip()
        current = str(row.get("CurrentStation") or "").upper().strip()

        if pn == "TDN-638-249-30":
            if "RESCREEN" in current or "TER_RWK_BAKE_OUT" in current:
                return "MTF Rescreening"
            return "MTF"

        if pn == "TDN-640-423-20":
            if station == "HP_TEST":
                return "HP_TEST"
            if station == "PT_TEST":
                return "PT_TEST"
            return "OTC"

        if pn in {"TDN-630-036-30", "TDN-630-036-32", "TDN-630-035-40"}:
            return "OTC"

        if pn in {"TDN-627-001-30", "TDN-627-000-40", "TDN-639-977-13", "TDN-625-388-13"}:
            return "MTF"

        return row.get("TestStation1") or "Unknown"

    df["ProcessGroup"] = df.apply(process_hint, axis=1)

    if "Row" not in df.columns:
        df["Row"] = 1
    df["Row"] = pd.to_numeric(df["Row"], errors="coerce").fillna(1).astype(int)

    df = df.sort_values(["TestDate1_dt", "SerialNumber", "TestStation1", "Row"]).reset_index(drop=True)
    return df


def filter_data(df, pns, product, process, stations, date_range):
    out = df.copy()

    if pns and "All" not in pns:
        out = out[out["PN"].isin(pns)]

    if product != "All":
        out = out[out["Product"] == product]

    if process != "All":
        out = out[out["ProcessGroup"] == process]

    if stations and "All" not in stations:
        out = out[out["TestStation1"].isin(stations)]

    if date_range and len(date_range) == 2:
        start, end = date_range
        out = out[(out["TestDate1_dt"].dt.date >= start) & (out["TestDate1_dt"].dt.date <= end)]

    return out


def event_level(df):
    first = df[df["Row"] == 1].copy()
    all_events = df.copy()
    return first, all_events


def station_metrics(df):
    first, all_events = event_level(df)

    first_summary = first.groupby("TestStation1", dropna=False).agg(
        FirstPassQtyTested=("Row", "count"),
        FirstPassQtyPass=("TestResult", lambda s: (s == "PASS").sum()),
        FirstPassQtyFailed=("TestResult", lambda s: (s == "FAIL").sum()),
    ).reset_index()

    first_summary["FPY"] = first_summary.apply(
        lambda r: safe_div(r["FirstPassQtyPass"], r["FirstPassQtyTested"]),
        axis=1
    )

    overall_summary = all_events.groupby("TestStation1", dropna=False).agg(
        OverallQtyTested=("Row", "count"),
        OverallQtyPass=("TestResult", lambda s: (s == "PASS").sum()),
        OverallQtyFailed=("TestResult", lambda s: (s == "FAIL").sum()),
    ).reset_index()

    overall_summary["OverallYield"] = overall_summary.apply(
        lambda r: safe_div(r["OverallQtyPass"], r["OverallQtyTested"]),
        axis=1
    )

    summary = pd.merge(first_summary, overall_summary, on="TestStation1", how="outer").fillna(0)
    summary = summary.sort_values(["OverallQtyTested", "TestStation1"], ascending=[False, True])
    return summary, first, all_events


def station_yield_chart(summary, title):
    if summary.empty:
        fig = go.Figure()
        return theme_utils.update_plotly_theme(fig)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=summary["TestStation1"],
            y=summary["OverallQtyTested"],
            name="Overall Qty Tested",
            marker_color="#0284C7"
        ),
        secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            x=summary["TestStation1"],
            y=summary["OverallYield"] * 100,
            name="Overall Yield %",
            mode="lines+markers",
            line=dict(color="#F59E0B", width=3)
        ),
        secondary_y=True
    )

    fig.add_trace(
        go.Scatter(
            x=summary["TestStation1"],
            y=summary["FPY"] * 100,
            name="FPY %",
            mode="lines+markers",
            line=dict(color="#10B981", width=3)
        ),
        secondary_y=True
    )

    fig.update_layout(
        title=title,
        height=480,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_xaxes(title_text="Test Step / Station", tickangle=-35)
    fig.update_yaxes(title_text="Qty Tested", secondary_y=False)
    fig.update_yaxes(title_text="Yield %", secondary_y=True, ticksuffix="%", range=[0, 105])
    return theme_utils.update_plotly_theme(fig)


def daily_weekly_summary(df):
    first_df, all_events = event_level(df)

    fp_daily = (
        first_df[first_df["TestDate1_dt"].notna()]
        .assign(Date=lambda x: x["TestDate1_dt"].dt.date)
        .groupby("Date")
        .agg(
            FPQtyTested=("Row", "count"),
            FPQtyPass=("TestResult", lambda s: (s == "PASS").sum()),
            FPQtyFail=("TestResult", lambda s: (s == "FAIL").sum()),
        )
        .reset_index()
    )

    fp_daily["FPY"] = (
        fp_daily["FPQtyPass"]
        / fp_daily["FPQtyTested"]
        * 100
    )

    ov_daily = (
        all_events[all_events["TestDate1_dt"].notna()]
        .assign(Date=lambda x: x["TestDate1_dt"].dt.date)
        .groupby("Date")
        .agg(
            QtyTested=("Row", "count"),
            QtyPass=("TestResult", lambda s: (s == "PASS").sum()),
            QtyFail=("TestResult", lambda s: (s == "FAIL").sum()),
        )
        .reset_index()
    )

    ov_daily["OverallYield"] = (
        ov_daily["QtyPass"]
        / ov_daily["QtyTested"]
        * 100
    )

    daily = pd.merge(
        ov_daily,
        fp_daily,
        on="Date",
        how="outer"
    ).fillna(0)

    daily["Week"] = pd.to_datetime(daily["Date"]).dt.to_period("W").astype(str)

    weekly = (
        daily.groupby("Week")
        .agg(
            QtyTested=("QtyTested", "sum"),
            QtyPass=("QtyPass", "sum"),
            FPQtyTested=("FPQtyTested", "sum"),
            FPQtyPass=("FPQtyPass", "sum"),
        )
        .reset_index()
    )

    weekly["OverallYield"] = (
        weekly["QtyPass"]
        / weekly["QtyTested"]
        * 100
    )

    weekly["FPY"] = (
        weekly["FPQtyPass"]
        / weekly["FPQtyTested"]
        * 100
    )

    return daily, weekly


def yield_line_chart(df, x_col, title):
    if df.empty:
        fig = go.Figure()
        return theme_utils.update_plotly_theme(fig)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=df[x_col],
            y=df["QtyTested"],
            name="Overall Qty Tested",
            marker_color="#0284C7"
        ),
        secondary_y=False
    )

    if "OverallYield" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df["OverallYield"],
                name="Overall Yield %",
                mode="lines+markers",
                line=dict(color="#F59E0B", width=3)
            ),
            secondary_y=True
        )

    if "FPY" in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df["FPY"],
                name="FPY %",
                mode="lines+markers",
                line=dict(color="#10B981", width=3)
            ),
            secondary_y=True
        )

    fig.update_layout(
        title=title,
        height=420,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="Qty Tested", secondary_y=False)
    fig.update_yaxes(title_text="Yield %", secondary_y=True, ticksuffix="%", range=[0, 105])
    return theme_utils.update_plotly_theme(fig)


def top_defects_28d(df, end_date):
    if end_date is None:
        end_date = pd.Timestamp.today().normalize()

    start_date = end_date - pd.Timedelta(days=365)

    window = df[
        (df["TestDate1_dt"].notna()) &
        (df["TestDate1_dt"] >= start_date) &
        (df["TestDate1_dt"] <= end_date + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))
    ].copy()

    fail = window[window["TestResult"] == "FAIL"].copy()

    if fail.empty:
        cols_tf = pd.DataFrame(columns=["FailureReason", "Count"])
        cols_td = pd.DataFrame(columns=["DefectKey", "ImpactedPN", "Count", "Label", "CumCount", "CumPct"])
        cols_ip = pd.DataFrame(columns=["ImpactedPN", "Count"])
        return cols_tf, cols_td, cols_ip, cols_td, start_date.date(), end_date.date()

    fail["FailureReason"] = fail.apply(
        lambda r: first_nonnull(r.get("FailureCode"), r.get("FailureRemark"), r.get("DefectDesc"), "Unknown"),
        axis=1
    )
    fail["DefectKey"] = fail.apply(
        lambda r: first_nonnull(r.get("DefectDesc"), r.get("FailureCode"), "Unknown"),
        axis=1
    )
    fail["ImpactedPN"] = fail["DefectPart"].fillna("Unknown")

    top_failure = (
        fail.groupby("FailureReason")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(15)
    )

    top_defect = (
        fail.groupby(["DefectKey", "ImpactedPN"])
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(15)
        .reset_index(drop=True)
    )
    top_defect["Label"] = top_defect.apply(
        lambda r: f"{r['DefectKey']} | {r['ImpactedPN']}",
        axis=1
    )
    top_defect["CumCount"] = top_defect["Count"].cumsum()
    total = top_defect["Count"].sum()
    top_defect["CumPct"] = top_defect["CumCount"] / total * 100 if total > 0 else 0

    impacted = (
        fail.groupby("ImpactedPN")
        .size()
        .reset_index(name="Count")
        .sort_values("Count", ascending=False)
        .head(15)
    )

    return top_failure, top_defect, impacted, top_defect, start_date.date(), end_date.date()


def pareto_chart(df):
    if df.empty or "Count" not in df.columns:
        fig = go.Figure()
        fig.add_annotation(
            text="🎉 No defects found for the selected date range!",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=16)
        )
        fig.update_layout(title="Pareto of Top Defects", height=480)
        return theme_utils.update_plotly_theme(fig)

    df = df.sort_values("Count", ascending=False).reset_index(drop=True)

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(
        go.Bar(
            x=df["Label"],
            y=df["Count"],
            name="Count",
            marker_color="#EF4444"
        ),
        secondary_y=False
    )

    fig.add_trace(
        go.Scatter(
            x=df["Label"],
            y=df["CumPct"],
            name="Cumulative %",
            mode="lines+markers",
            line=dict(color="#10B981", width=3),
            marker=dict(size=7)
        ),
        secondary_y=True
    )

    fig.update_layout(
        title="Pareto of Top Defects",
        height=780,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(
            categoryorder="array",
            categoryarray=df["Label"].tolist()
        )
    )
    fig.update_xaxes(title_text="Defect / Impacted PN", tickangle=-35)
    fig.update_yaxes(title_text="Count", secondary_y=False)
    fig.update_yaxes(title_text="Cumulative %", secondary_y=True, ticksuffix="%", range=[0, 105])
    return theme_utils.update_plotly_theme(fig)


def wip_analysis(df):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()

    latest = df.sort_values("TestDate1_dt").drop_duplicates(subset=["SerialNumber", "PN"], keep="last").copy()
    latest["WIPStatus"] = latest["TestResult"].fillna("UNKNOWN")

    wip = latest.groupby(["PN", "Product", "ProcessGroup", "CurrentStation", "WIPStatus"]).agg(
        Qty=("SerialNumber", "nunique")
    ).reset_index()
    wip = wip.sort_values(["Qty", "PN"], ascending=[False, True])

    by_pn = latest.groupby(["PN", "Product", "ProcessGroup"]).agg(
        CurrentWIP=("SerialNumber", "nunique"),
        LatestPass=("TestResult", lambda s: (s == "PASS").sum()),
        LatestFail=("TestResult", lambda s: (s == "FAIL").sum()),
    ).reset_index().sort_values(["CurrentWIP", "PN"], ascending=[False, True])

    return by_pn, wip


# --- Main Dashboard Section ---
st.title("Yield and Defect Analysis")
st.caption("CSV based dashboard for PN / Process yield, defect Pareto, WIP, and daily / weekly trends.")

with st.sidebar:
    st.header("Data Source")
    uploaded = st.file_uploader("Upload CSV", type=["csv"], help="Optional. If not uploaded, reads rptTestDetail.csv.")
    load_local = st.toggle("Use local file if no upload", value=True)
    st.markdown("---")
    st.subheader("Filters")

try:
    if uploaded is not None:
        df_raw = load_data(uploaded_file=uploaded)
    elif load_local:
        df_raw = load_data(local_path=DEFAULT_CSV)
    else:
        st.info("Upload a CSV to begin.")
        st.stop()
except Exception as e:
    st.error(f"Unable to load CSV: {e}")
    st.stop()

if df_raw.empty:
    st.warning("CSV loaded but no rows found.")
    st.stop()

all_pns = sorted([x for x in df_raw["PN"].dropna().unique().tolist() if x])
all_products = ["All"] + sorted(df_raw["Product"].dropna().unique().tolist())
all_process = ["All"] + sorted(df_raw["ProcessGroup"].dropna().unique().tolist())
all_stations = ["All"] + sorted(df_raw["TestStation1"].dropna().unique().tolist())

min_date = df_raw["TestDate1_dt"].dropna().dt.date.min()
max_date = df_raw["TestDate1_dt"].dropna().dt.date.max()

with st.sidebar:
    pns = st.multiselect("PN", ["All"] + all_pns, default=["All"])
    product = st.selectbox("Product", all_products, index=0)
    process = st.selectbox("Process Group", all_process, index=0)
    stations = st.multiselect("Test Station", all_stations, default=["All"])
    date_range = st.date_input("Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    st.markdown("---")
    st.markdown("### PN Rules")
    st.write("Tesla: MTF, OTC")
    st.write("Raiden: MTF, MTF Rescreening, OTC, HP_TEST, PT_TEST")

filtered = filter_data(df_raw, pns, product, process, stations, date_range)
summary, first_df, all_events = station_metrics(filtered)
daily_df, weekly_df = daily_weekly_summary(filtered)
top_failure, top_defect, impacted, pareto_df, p_start, p_end = top_defects_28d(filtered, pd.Timestamp(max_date))
wip_by_pn, wip_detail = wip_analysis(filtered)

c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    theme_utils.render_kpi_card("Filtered rows", f"{len(filtered):,}", "Raw CSV records after filter")
with c2:
    theme_utils.render_kpi_card("Unique PN", f"{filtered['PN'].nunique():,}", "Distinct part numbers in scope")
with c3:
    theme_utils.render_kpi_card("Unique serials", f"{filtered['SerialNumber'].nunique():,}", "Serials in filtered dataset")
with c4:
    raw_yield_pct = safe_div((filtered["TestResult"] == "PASS").sum(), len(filtered)) * 100
    badge_type = "success" if raw_yield_pct >= 95 else ("warning" if raw_yield_pct >= 90 else "danger")
    badge_label = "HEALTHY" if raw_yield_pct >= 95 else ("WARN" if raw_yield_pct >= 90 else "ACTION REQUIRED")
    theme_utils.render_kpi_card("Raw record yield", f"{raw_yield_pct:,.1f}%", "Simple PASS / total rows", badge=badge_label, badge_type=badge_type)
with c5:
    event_yield_pct = safe_div((all_events["TestResult"] == "PASS").sum(), len(all_events)) * 100
    badge_type = "success" if event_yield_pct >= 95 else ("warning" if event_yield_pct >= 90 else "danger")
    badge_label = "HEALTHY" if event_yield_pct >= 95 else ("WARN" if event_yield_pct >= 90 else "ACTION REQUIRED")
    theme_utils.render_kpi_card("Overall yield", f"{event_yield_pct:,.1f}%", "Calculated from all rows", badge=badge_label, badge_type=badge_type)

st.markdown("---")

main_tabs = st.tabs(["Station Yield", "Summary Tables", "Daily / Weekly", "Pareto", "WIP", "Raw Detail"])

with main_tabs[0]:
    st.markdown('<div class="section-title">1) Histogram / Yield vs Qty Tested by Test Step</div>', unsafe_allow_html=True)
    st.plotly_chart(station_yield_chart(summary, "Qty Tested and Yield by Test Station"), use_container_width=True)
    with st.expander("Station summary table", expanded=False):
        show = summary.copy()
        show["FPY"] = (show["FPY"] * 100).round(1)
        show["OverallYield"] = (show["OverallYield"] * 100).round(1)
        st.dataframe(show, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Download Station Summary CSV",
            show.to_csv(index=False).encode("utf-8"),
            file_name="station_summary.csv",
            mime="text/csv"
        )

with main_tabs[1]:
    st.markdown('<div class="section-title">2) First Pass and Overall Summary by Test Station</div>', unsafe_allow_html=True)
    left, right = st.columns(2)

    with left:
        st.markdown("#### First Pass Metrics")
        fp = summary[["TestStation1", "FirstPassQtyTested", "FirstPassQtyPass", "FirstPassQtyFailed", "FPY"]].copy()
        fp["FPY"] = (fp["FPY"] * 100).round(1)
        st.dataframe(fp, use_container_width=True, hide_index=True)

    with right:
        st.markdown("#### Overall Metrics")
        ov = summary[["TestStation1", "OverallQtyTested", "OverallQtyPass", "OverallQtyFailed", "OverallYield"]].copy()
        ov["OverallYield"] = (ov["OverallYield"] * 100).round(1)
        st.dataframe(ov, use_container_width=True, hide_index=True)

    st.markdown("#### PN / Product Grouping")
    pn_summary = filtered.groupby(["Product", "PN", "ProcessGroup"]).agg(
        QtyRows=("Row", "count"),
        UniqueSerials=("SerialNumber", "nunique"),
        PassRows=("TestResult", lambda s: (s == 'PASS').sum()),
        FailRows=("TestResult", lambda s: (s == 'FAIL').sum()),
    ).reset_index()
    pn_summary["Yield"] = pn_summary.apply(lambda r: safe_div(r["PassRows"], r["QtyRows"]), axis=1) * 100
    st.dataframe(pn_summary.sort_values(["Product", "PN", "ProcessGroup"]), use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Download PN Summary CSV",
        pn_summary.to_csv(index=False).encode("utf-8"),
        file_name="pn_yield_summary.csv",
        mime="text/csv"
    )

with main_tabs[2]:
    st.markdown('<div class="section-title">3) Daily and Weekly Yield Trend</div>', unsafe_allow_html=True)
    trend_tabs = st.tabs(["Daily", "Weekly"])

    with trend_tabs[0]:
        st.plotly_chart(
            yield_line_chart(daily_df, "Date", "Daily Yield Trend"),
            use_container_width=True
        )
        daily_show = daily_df.copy()
        if "FPY" in daily_show.columns:
            daily_show["FPY"] = daily_show["FPY"].round(1)
        if "OverallYield" in daily_show.columns:
            daily_show["OverallYield"] = daily_show["OverallYield"].round(1)

        daily_cols = [
            c for c in [
                "Date",
                "FPQtyTested",
                "FPQtyPass",
                "FPQtyFail",
                "FPY",
                "QtyTested",
                "QtyPass",
                "QtyFail",
                "OverallYield"
            ]
            if c in daily_show.columns
        ]
        st.dataframe(
            daily_show[daily_cols],
            use_container_width=True,
            hide_index=True
        )

    with trend_tabs[1]:
        st.plotly_chart(
            yield_line_chart(weekly_df, "Week", "Weekly Yield Trend"),
            use_container_width=True
        )
        weekly_show = weekly_df.copy()
        if "FPY" in weekly_show.columns:
            weekly_show["FPY"] = weekly_show["FPY"].round(1)
        if "OverallYield" in weekly_show.columns:
            weekly_show["OverallYield"] = weekly_show["OverallYield"].round(1)

        weekly_cols = [
            c for c in [
                "Week",
                "FPQtyTested",
                "FPQtyPass",
                "FPY",
                "QtyTested",
                "QtyPass",
                "OverallYield"
            ]
            if c in weekly_show.columns
        ]
        st.dataframe(
            weekly_show[weekly_cols],
            use_container_width=True,
            hide_index=True
        )

with main_tabs[3]:
    st.markdown(f'<div class="section-title">4) Pareto of Top Defects : ({min_date} to {max_date})</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns([2, 1])

    with col_a:
        st.plotly_chart(pareto_chart(pareto_df), use_container_width=True)

    with col_b:
        st.markdown("#### Top Failure Reason")
        st.dataframe(top_failure, use_container_width=True, hide_index=True)
        st.markdown("#### Impacted PN")
        st.dataframe(impacted, use_container_width=True, hide_index=True)

    st.markdown("#### Top Defect Table")
    st.dataframe(top_defect, use_container_width=True, hide_index=True)
    if not top_defect.empty:
        st.download_button(
            "📥 Download Pareto Defects CSV",
            top_defect.to_csv(index=False).encode("utf-8"),
            file_name="top_defects_pareto.csv",
            mime="text/csv"
        )

with main_tabs[4]:
    st.markdown('<div class="section-title">5) WIP Analysis by PN</div>', unsafe_allow_html=True)
    st.dataframe(wip_by_pn, use_container_width=True, hide_index=True)
    with st.expander("WIP detail by current station and latest status", expanded=False):
        st.dataframe(wip_detail, use_container_width=True, hide_index=True)

with main_tabs[5]:
    st.markdown('<div class="section-title">Raw Detail</div>', unsafe_allow_html=True)
    st.dataframe(filtered, use_container_width=True, hide_index=True)
    st.download_button(
        "📥 Download Filtered Raw Data CSV",
        filtered.to_csv(index=False).encode("utf-8"),
        file_name="filtered_raw_data.csv",
        mime="text/csv"
    )

st.markdown("---")
st.markdown(
    """
    <div class='small-note'>
    Notes: First-pass metrics are calculated from rows where Row = 1.
    Overall metrics are calculated from all rows in the dataset.
    The product / process mapping can be edited in the PART_MASTER dictionary.
    </div>
    """,
    unsafe_allow_html=True,
)