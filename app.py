import json
from pathlib import Path
from typing import Iterable, List, Sequence

import altair as alt
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent / "data" / "umm_messages1.csv"
API_URL = "https://ummapi.nordpoolgroup.com/messages"

MESSAGE_TYPE_LABELS = {
    1: "Production unavailability",
    2: "Consumption unavailability",
    3: "Transmission outage",
    4: "Market notice",
    5: "Other market information",
}

EVENT_STATUS_LABELS = {
    1: "Active",
    3: "Cancelled / postponed",
}


@st.cache_data(show_spinner=False)
def load_data(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["message_type"] = pd.to_numeric(df["message_type"], errors="coerce").astype("Int64")
    df["event_status"] = pd.to_numeric(df["event_status"], errors="coerce").astype("Int64")
    for col in ("publication_date", "event_start", "event_stop", "retrieved_at"):
        if col in df:
            df[f"{col}_dt"] = pd.to_datetime(df[col], utc=True, errors="coerce")
    df["message_type_label"] = df["message_type"].map(MESSAGE_TYPE_LABELS).fillna("Other")
    df["event_status_label"] = df["event_status"].map(EVENT_STATUS_LABELS).fillna("Other")
    df["publisher_name"] = df["publisher_name"].fillna("Unknown")
    df["remarks"] = df["remarks"].fillna("")

    json_columns = [
        "areas_json",
        "market_participants_json",
        "assets_json",
        "generation_units_json",
        "production_units_json",
        "consumption_units_json",
        "transmission_units_json",
        "other_market_units_json",
        "acer_rss_message_ids_json",
    ]
    for col in json_columns:
        if col not in df:
            continue
        df[col] = df[col].apply(_parse_json_series)

    df["area_names"] = df["areas_json"].apply(_extract_area_names)
    df["publisher_codes"] = df["market_participants_json"].apply(
        lambda items: sorted({item.get("code") for item in items if isinstance(item, dict) and item.get("code")})
    )
    df["area_display"] = df["area_names"].apply(_join_items)

    return df


def _parse_json_series(value: object) -> List:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, dict)):
        return value if isinstance(value, list) else [value]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return parsed
    return [parsed]


def _extract_area_names(items: Sequence[dict]) -> List[str]:
    names = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name:
            names.append(str(name))
    return sorted(set(names))


def _join_items(items: Iterable) -> str:
    return ", ".join(sorted({str(item) for item in items if item}))


def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("General Message Filters")
    min_date = df["publication_date_dt"].min()
    max_date = df["publication_date_dt"].max()
    if min_date is None or pd.isna(min_date):
        start_date = end_date = None
    else:
        start_date = min_date.date()
        end_date = max_date.date()
    selected_range = st.sidebar.date_input(
        "Publication date",
        value=(start_date, end_date) if start_date and end_date else None,
        min_value=start_date,
        max_value=end_date,
    )
    if isinstance(selected_range, tuple) and len(selected_range) == 2:
        start, end = selected_range
    else:
        start = start_date
        end = end_date
    type_options = sorted(df["message_type_label"].unique())
    selected_types = st.sidebar.multiselect("Message types", type_options, default=type_options)
    all_areas = sorted({area for areas in df["area_names"] for area in areas})
    st.sidebar.subheader("Area Filtering")
    selected_areas = st.sidebar.multiselect("Filter by areas (leave empty for all)", all_areas)
    publishers = sorted(df["publisher_name"].unique())
    selected_publishers = st.sidebar.multiselect("Publishers", publishers)
    search_term = st.sidebar.text_input("Search remarks", "")
    filtered = df.copy()
    if start and end:
        start_ts = pd.to_datetime(start, utc=True)
        end_ts = pd.to_datetime(end, utc=True) + pd.Timedelta(days=1)
        filtered = filtered[
            (filtered["publication_date_dt"] >= start_ts) & (filtered["publication_date_dt"] < end_ts)
        ]
    if selected_types and len(selected_types) != len(type_options):
        filtered = filtered[filtered["message_type_label"].isin(selected_types)]
    if selected_publishers:
        filtered = filtered[filtered["publisher_name"].isin(selected_publishers)]
    # Area inclusion logic - only filter if areas are selected
    if selected_areas:
        filtered = filtered[
            filtered["area_names"].apply(lambda names: any(area in names for area in selected_areas))
        ]
    if search_term:
        filtered = filtered[
            filtered["remarks"].str.contains(search_term, case=False, na=False)
        ]
    return filtered.sort_values("publication_date_dt", ascending=False)


def render_metrics(df: pd.DataFrame, total_count: int) -> None:
    col1, col2, col3 = st.columns(3)
    fraction = len(df) / total_count if total_count else 0
    col1.metric("Messages", f"{len(df):,}", f"{fraction:.1%} of {total_count:,}")
    col2.metric("Publishers", f"{df['publisher_name'].nunique():,}")
    unique_areas = sorted({area for areas in df['area_names'] for area in areas})
    col3.metric("Areas", f"{len(unique_areas):,}")


def render_charts(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("No data to display for the selected filters.")
        return

    yearly = (
        df.dropna(subset=["publication_date_dt"])
        .assign(year=lambda x: x["publication_date_dt"].dt.to_period("Y").dt.to_timestamp())
        .groupby("year")
        .size()
        .reset_index(name="messages")
    )
    if not yearly.empty:
        yearly_chart = (
            alt.Chart(yearly)
            .mark_bar()
            .encode(x=alt.X("year:T", title="Year"), y=alt.Y("messages:Q", title="Messages"))
        )
        st.altair_chart(yearly_chart, use_container_width=True)

    type_counts = df.groupby("message_type_label").size().reset_index(name="messages")
    type_chart = (
        alt.Chart(type_counts)
        .mark_bar()
        .encode(
            x=alt.X("messages:Q", title="Messages"),
            y=alt.Y("message_type_label:N", sort="-x", title="Message type"),
            tooltip=["message_type_label", "messages"],
        )
    )
    st.altair_chart(type_chart, use_container_width=True)

    publisher_counts = (
        df.groupby("publisher_name")
        .size()
        .reset_index(name="messages")
        .sort_values("messages", ascending=False)
        .head(15)
    )
    publisher_chart = (
        alt.Chart(publisher_counts)
        .mark_bar()
        .encode(
            x=alt.X("messages:Q", title="Messages"),
            y=alt.Y("publisher_name:N", sort="-x", title="Publisher"),
            tooltip=["publisher_name", "messages"],
        )
    )
    st.altair_chart(publisher_chart, use_container_width=True)


def render_table(df: pd.DataFrame) -> None:
    display_columns = [
        "publication_date",
        "message_type_label",
        "event_status_label",
        "publisher_name",
        "area_display",
        "event_start",
        "event_stop",
        "remarks",
    ]

    table = df[display_columns].copy()
    st.dataframe(table, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(table):,} messages that match the selected filters.")

    csv_bytes = table.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered data as CSV",
        data=csv_bytes,
        file_name="umm_filtered.csv",
        mime="text/csv",
    )


def render_outage_type_summary():
    st.subheader("All Areas by Outage Type")
    type_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_type_summary.csv"
    if type_path.exists():
        df_type = pd.read_csv(type_path)
        st.dataframe(df_type, use_container_width=True)
        st.bar_chart(df_type.set_index("area")["count"])
        st.caption("Showing all areas by outage type count (from CSV)")
    else:
        st.warning("Outage type summary CSV not found.")


def render_outage_type_status_summary():
    # st.subheader("All Areas by Outage Type & Planned Status")
    status_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_type_status_summary.csv"
    # The following code is commented out to remove the chart and table for this section:
    # if status_path.exists():
    #     df_status = pd.read_csv(status_path)
    #     st.dataframe(df_status, use_container_width=True)
    #     st.bar_chart(df_status.set_index("area")["count"])
    #     st.caption("Showing all areas by outage type and planned/unplanned status (from CSV)")
    # else:
    #     st.warning("Outage type status summary CSV not found.")


def render_outage_events_interactive():
    st.sidebar.header("Outage Events Filters")
    mw_threshold = st.sidebar.slider("MW threshold", min_value=100, max_value=2000, value=400, step=50, key="event_mw_slider")
    st.subheader(f"Areas with Outages ≥ {mw_threshold} MW")
    events_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_events.csv"
    if not events_path.exists():
        st.warning("Area outage events CSV not found.")
        return
    df = pd.read_csv(events_path)
    status = st.sidebar.selectbox("Outage status (event)", ["Planned", "Unplanned", "Both"], key="event_status_select")
    area_options = sorted(df["area"].unique())
    selected_areas_event = st.sidebar.multiselect("Filter by areas (event, leave empty for all)", area_options, key="event_area_multiselect")
    if selected_areas_event:
        filtered = df[df["area"].isin(selected_areas_event)]
    else:
        filtered = df
    filtered = filtered[filtered["mw"] >= mw_threshold]
    if status != "Both":
        filtered = filtered[filtered["status"] == status]
    st.dataframe(filtered, use_container_width=True)
    st.bar_chart(filtered.groupby("area")["mw"].sum())
    st.caption(f"Showing outage events above {mw_threshold} MW by selected status and area.")


def render_area_full_outage_summary():
    st.sidebar.header("Full Outage Summary Filters")
    st.subheader("Area-level Full Outage Summary")
    summary_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_full_status_summary.csv"
    if not summary_path.exists():
        st.warning("Area-level full outage summary CSV not found.")
        return
    df = pd.read_csv(summary_path)
    year_options = sorted(df["year"].dropna().unique())
    selected_years = st.sidebar.multiselect("Year (full summary)", year_options, default=year_options, key="full_status_year_multiselect")
    df = df[df["year"].isin(selected_years)]
    
    # Area inclusion logic
    area_options = sorted(df["area"].unique())
    selected_areas_full = st.sidebar.multiselect("Filter by areas (full summary, leave empty for all)", area_options, key="areas_full_multiselect")
    
    if selected_areas_full:
        df = df[df["area"].isin(selected_areas_full)]
    
    outage_type_options = sorted(df["outage_type"].unique())
    selected_types = st.sidebar.multiselect("Outage types (full summary)", outage_type_options, default=outage_type_options, key="full_status_type_multiselect")
    df = df[df["outage_type"].isin(selected_types)]
    status_options = ["Planned", "Unplanned"]
    selected_status = st.sidebar.multiselect("Planned/Unplanned", status_options, default=status_options, key="full_status_status_multiselect")
    df = df[df["planned_status"].isin(selected_status)]
    table = df.pivot_table(index=["area", "year"], columns=["outage_type", "planned_status"], values="count", aggfunc="sum", fill_value=0)
    st.dataframe(table, use_container_width=True)
    st.caption("Table shows each area/year and the number of planned/unplanned outages for each type, filtered by year and area.")
    
    # Aggregate data across all years for chart visualization
    df_agg = df.groupby(["area", "outage_type", "planned_status"])["count"].sum().reset_index()
    
    import altair as alt
    chart = alt.Chart(df_agg).mark_bar().encode(
        x=alt.X("area:N", title="Area", sort="-y"),
        y=alt.Y("count:Q", title="Total Outages", stack=True),
        color=alt.Color("outage_type:N", title="Outage Type"),
        column=alt.Column("planned_status:N", title="Planned/Unplanned"),
        tooltip=["area", "outage_type", "planned_status", "count"]
    ).properties(width=350, height=400)
    st.altair_chart(chart, use_container_width=True)
    st.caption("Stacked bar chart shows total planned/unplanned outages by type for each area (summed across all selected years).")
    top_n = st.sidebar.slider("Show top N Areas with most outages", min_value=1, max_value=30, value=10, key="top_n_outage_areas_table")
    st.subheader(f"Top {top_n} Areas with Most Outages")
    total_outages = df.groupby("area")["count"].sum().reset_index().sort_values("count", ascending=False)
    top_areas = total_outages.head(top_n)["area"].tolist()
    df_top = df[df["area"].isin(top_areas)]
    top_table = df_top.pivot_table(index="area", columns=["outage_type", "planned_status"], values="count", aggfunc="sum", fill_value=0)
    st.dataframe(top_table, use_container_width=True)
    st.caption("Table shows top N areas and the number of consumption unavailability, production unavailability, transmission outage, planned and unplanned outages.")


def main() -> None:
    st.set_page_config(page_title="Nord Pool UMM Explorer", layout="wide")
    st.title("Nord Pool UMM Explorer")
    st.caption(f"Data source: {API_URL}")

    if not DATA_PATH.exists():
        st.error(f"Could not find data file at {DATA_PATH}")
        return

    df = load_data(DATA_PATH)
    total_rows = len(df)

    filtered = filter_dataframe(df)

    render_metrics(filtered, total_rows)
    render_charts(filtered)
    render_table(filtered)

    # Add top outage areas query with filter
    # st.sidebar.header("Top Outage Area Filter")
    # top_n = st.sidebar.slider("Show top N areas with most outages", min_value=1, max_value=20, value=5)
    # st.sidebar.header("Outage Type Status Summary Filter")
    # top_n_status = st.sidebar.slider("Show top N areas by outage type & status", min_value=1, max_value=20, value=10)
    # render_outage_type_status_summary()

    render_outage_events_interactive()
    render_area_full_outage_summary()

    earliest = df["publication_date_dt"].min()
    if earliest is not None:
        st.caption(
            f"Available publication window: {earliest.date()} to {df['publication_date_dt'].max().date()} "
            "(older entries are not provided by the public API)."
        )


if __name__ == "__main__":
    main()
