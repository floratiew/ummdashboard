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
    df["unavailability_reason"] = df["unavailability_reason"].fillna("") if "unavailability_reason" in df.columns else ""

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

    df["area_names"] = df.apply(_extract_all_area_names, axis=1)
    df["publisher_codes"] = df["market_participants_json"].apply(
        lambda items: sorted({item.get("code") for item in items if isinstance(item, dict) and item.get("code")})
    )
    df["area_display"] = df["area_names"].apply(_join_items)
    
    # Extract production and generation unit information
    df["production_unit_names"] = df["production_units_json"].apply(_extract_unit_names)
    df["generation_unit_names"] = df["generation_units_json"].apply(_extract_unit_names)
    df["production_units_display"] = df["production_unit_names"].apply(_join_items)
    df["generation_units_display"] = df["generation_unit_names"].apply(_join_items)

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


def _extract_all_area_names(row) -> List[str]:
    """Extract area names from areas_json AND from production/generation/transmission units"""
    areas = set()
    
    # Get areas from areas_json
    for item in row.get("areas_json", []):
        if isinstance(item, dict) and item.get("name"):
            areas.add(str(item["name"]))
    
    # Get areas from production units
    for item in row.get("production_units_json", []):
        if isinstance(item, dict) and item.get("areaName"):
            areas.add(str(item["areaName"]))
    
    # Get areas from generation units
    for item in row.get("generation_units_json", []):
        if isinstance(item, dict) and item.get("areaName"):
            areas.add(str(item["areaName"]))
    
    # Get areas from transmission units
    for item in row.get("transmission_units_json", []):
        if isinstance(item, dict):
            # Transmission units may have inAreaName and outAreaName
            if item.get("inAreaName"):
                areas.add(str(item["inAreaName"]))
            if item.get("outAreaName"):
                areas.add(str(item["outAreaName"]))
    
    return sorted(areas)


def _join_items(items: Iterable) -> str:
    return ", ".join(sorted({str(item) for item in items if item}))


def _extract_unit_names(items: Sequence[dict]) -> List[str]:
    """Extract unit names from production/generation units JSON"""
    names = []
    for item in items:
        if not isinstance(item, dict):
            continue
        # Try different possible keys for unit name
        name = item.get("name") or item.get("productionUnitName") or item.get("generationUnitName")
        if name:
            names.append(str(name))
    return sorted(set(names))


def _extract_unit_capacities(items: Sequence[dict]) -> dict:
    """Extract unit capacities with their names"""
    capacities = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        installed_capacity = item.get("installedCapacity")
        available_capacity = item.get("availableCapacity")
        unavailable_capacity = item.get("unavailableCapacity")
        if name:
            capacities[name] = {
                "installed": installed_capacity,
                "available": available_capacity,
                "unavailable": unavailable_capacity
            }
    return capacities


def filter_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("📅 Date Range")
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
    
    st.sidebar.divider()
    st.sidebar.header("📊 Message Type")
    type_options = sorted(df["message_type_label"].unique())
    selected_types = st.sidebar.multiselect("Select message types", type_options, default=type_options)
    
    st.sidebar.divider()
    st.sidebar.header("🌍 Areas")
    all_areas = sorted({area for areas in df["area_names"] for area in areas})
    selected_areas = st.sidebar.multiselect("Select areas to view", all_areas, help="Leave empty to show all areas")
    
    st.sidebar.divider()
    st.sidebar.header("🏢 Publishers")
    publishers = sorted(df["publisher_name"].unique())
    selected_publishers = st.sidebar.multiselect("Select publishers", publishers, help="Leave empty to show all publishers")
    
    st.sidebar.divider()
    st.sidebar.header("🔍 Search")
    search_term = st.sidebar.text_input("Search in remarks", "", placeholder="Enter keywords...")
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
    # Extract additional fields from JSON for display
    table = df.copy()
    
    # Extract capacity information
    def extract_capacity_info(row):
        total_installed = 0
        total_unavailable = 0
        total_available = 0
        
        for unit in row.get('production_units_json', []):
            if isinstance(unit, dict):
                total_installed += unit.get('installedCapacity', 0) or 0
                # Check time periods for unavailable capacity
                for period in unit.get('timePeriods', []):
                    if isinstance(period, dict):
                        total_unavailable += period.get('unavailableCapacity', 0) or 0
                        total_available += period.get('availableCapacity', 0) or 0
                        break  # Just take first period
        
        for unit in row.get('generation_units_json', []):
            if isinstance(unit, dict):
                total_installed += unit.get('installedCapacity', 0) or 0
                for period in unit.get('timePeriods', []):
                    if isinstance(period, dict):
                        total_unavailable += period.get('unavailableCapacity', 0) or 0
                        total_available += period.get('availableCapacity', 0) or 0
                        break
        
        return pd.Series({
            'installed_mw': total_installed if total_installed > 0 else None,
            'unavailable_mw': total_unavailable if total_unavailable > 0 else None,
            'available_mw': total_available if total_available > 0 else None
        })
    
    # Extract fuel type
    def extract_fuel_type(row):
        fuel_types = set()
        fuel_map = {
            1: "Nuclear", 2: "Lignite", 3: "Hard Coal", 4: "Natural Gas",
            5: "Oil", 6: "Biomass", 7: "Geothermal", 8: "Waste",
            9: "Wind Onshore", 10: "Wind Offshore", 11: "Solar", 12: "Hydro",
            13: "Pumped Storage", 14: "Marine", 15: "Other"
        }
        
        for unit in row.get('production_units_json', []) + row.get('generation_units_json', []):
            if isinstance(unit, dict) and unit.get('fuelType'):
                fuel_type_num = unit.get('fuelType')
                fuel_types.add(fuel_map.get(fuel_type_num, f"Type {fuel_type_num}"))
        
        return ", ".join(sorted(fuel_types)) if fuel_types else None
    
    # Calculate duration
    def calculate_duration(row):
        if pd.notna(row.get('event_start_dt')) and pd.notna(row.get('event_stop_dt')):
            duration = row['event_stop_dt'] - row['event_start_dt']
            hours = duration.total_seconds() / 3600
            if hours < 24:
                return f"{hours:.1f}h"
            else:
                days = hours / 24
                return f"{days:.1f}d"
        return None
    
    # Apply extractions
    capacity_info = table.apply(extract_capacity_info, axis=1)
    table['installed_mw'] = capacity_info['installed_mw']
    table['unavailable_mw'] = capacity_info['unavailable_mw']
    table['available_mw'] = capacity_info['available_mw']
    table['fuel_type'] = table.apply(extract_fuel_type, axis=1)
    table['duration'] = table.apply(calculate_duration, axis=1)
    
    # Select and rename columns for display
    display_columns = [
        "publication_date",
        "message_type_label",
        "event_status_label",
        "publisher_name",
        "area_display",
        "production_units_display",
        "installed_mw",
        "unavailable_mw",
        "available_mw",
        "fuel_type",
        "event_start",
        "event_stop",
        "duration",
        "unavailability_reason",
        "remarks",
    ]
    
    display_table = table[display_columns].copy()
    display_table.columns = [
        "Publication Date",
        "Message Type",
        "Status",
        "Publisher",
        "Price Area(s)",
        "Unit(s)",
        "Installed (MW)",
        "Unavailable (MW)",
        "Available (MW)",
        "Fuel Type",
        "Event Start",
        "Event Stop",
        "Duration",
        "Reason",
        "Remarks"
    ]
    
    st.dataframe(display_table, use_container_width=True, hide_index=True)
    st.caption(f"Showing {len(display_table):,} messages that match the selected filters.")

    csv_bytes = display_table.to_csv(index=False).encode("utf-8")
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


def render_production_unit_analysis(df: pd.DataFrame):
    """Analyze market events by production units and their associated price areas"""
    st.sidebar.divider()
    st.sidebar.header("🏭 Production Unit Analysis")
    
    st.subheader("Production Units and Market Events by Price Area")
    st.caption("Analyze how production/generation units (like Kvilldal) relate to price areas through market unavailability messages")
    
    # Get all unique production units
    all_production_units = sorted({unit for units in df["production_unit_names"] for unit in units if unit})
    all_generation_units = sorted({unit for units in df["generation_unit_names"] for unit in units if unit})
    
    # Combine both types of units
    all_units = sorted(set(all_production_units + all_generation_units))
    
    if not all_units:
        st.warning("No production or generation units found in the current dataset.")
        return
    
    # Filter by unit name
    unit_search = st.sidebar.text_input("🔍 Search for unit (e.g., Kvilldal)", "", placeholder="Enter unit name...", key="unit_search")
    
    if unit_search:
        matching_units = [u for u in all_units if unit_search.lower() in u.lower()]
        selected_unit = st.sidebar.selectbox("Select unit", matching_units if matching_units else ["No matches found"], key="unit_select")
    else:
        selected_unit = st.sidebar.selectbox("Or select from all units", [""] + all_units, key="unit_select_all")
    
    # Filter by message type for unit analysis
    unit_msg_types = st.sidebar.multiselect("Message types", 
                                            ["Production unavailability", "Consumption unavailability", "Transmission outage"],
                                            default=["Production unavailability"],
                                            key="unit_msg_types")
    
    if selected_unit and selected_unit != "No matches found":
        # Filter messages related to this unit
        df_unit = df[
            (df["production_unit_names"].apply(lambda units: selected_unit in units)) |
            (df["generation_unit_names"].apply(lambda units: selected_unit in units))
        ]
        
        if not unit_msg_types:
            unit_msg_types = list(MESSAGE_TYPE_LABELS.values())
        df_unit = df_unit[df_unit["message_type_label"].isin(unit_msg_types)]
        
        if df_unit.empty:
            st.info(f"No messages found for unit '{selected_unit}' with selected message types.")
            return
        
        # Extract unit location and capacity information from JSON
        unit_areas = set()
        unit_capacity = None
        for _, row in df_unit.head(10).iterrows():  # Check first 10 rows for unit details
            for prod_unit in row['production_units_json']:
                if isinstance(prod_unit, dict):
                    unit_name = prod_unit.get("name") or prod_unit.get("productionUnitName")
                    if unit_name == selected_unit:
                        if prod_unit.get("areaName"):
                            unit_areas.add(prod_unit.get("areaName"))
                        if not unit_capacity and prod_unit.get("installedCapacity"):
                            unit_capacity = prod_unit.get("installedCapacity")
            for gen_unit in row['generation_units_json']:
                if isinstance(gen_unit, dict):
                    unit_name = gen_unit.get("name") or gen_unit.get("generationUnitName")
                    if unit_name == selected_unit:
                        if gen_unit.get("areaName"):
                            unit_areas.add(gen_unit.get("areaName"))
                        if not unit_capacity and gen_unit.get("installedCapacity"):
                            unit_capacity = gen_unit.get("installedCapacity")
        
        # Display unit overview
        st.markdown("### 📍 Unit Overview")
        col1, col2, col3, col4 = st.columns(4)
        
        col1.metric("Location (Price Area)", ", ".join(sorted(unit_areas)) if unit_areas else "Unknown")
        col2.metric("Installed Capacity", f"{unit_capacity:,} MW" if unit_capacity else "N/A")
        
        # Display ownership/publisher information
        publishers = df_unit['publisher_name'].value_counts()
        primary_owner = publishers.index[0] if len(publishers) > 0 else "Unknown"
        col3.metric("Primary Publisher", primary_owner[:20] + "..." if len(primary_owner) > 20 else primary_owner)
        col4.metric("Total Events", f"{len(df_unit):,}")
        
        if len(publishers) > 1:
            st.caption(f"📢 Also published by: {', '.join(publishers.index[1:3])}")
        
        # Display market event metrics
        st.markdown("### 📊 Market Event Statistics")
        col1, col2, col3 = st.columns(3)
        all_event_areas = set([a for areas in df_unit['area_names'] for a in areas])
        col1.metric("Affected Price Areas", f"{len(all_event_areas):,}")
        col2.metric("Unique Publishers", f"{df_unit['publisher_name'].nunique():,}")
        col3.metric("Date Range", f"{df_unit['publication_date_dt'].min().year}-{df_unit['publication_date_dt'].max().year}")
        
        if all_event_areas:
            st.caption(f"🌍 Affected areas: {', '.join(sorted(all_event_areas))}")
        
        # Events by year
        st.markdown(f"### 📅 Unavailability Events for {selected_unit} Over Time")
        st.caption("Shows the frequency of unavailability messages for this production unit over the years")
        
        yearly_events = (
            df_unit.dropna(subset=["publication_date_dt"])
            .assign(year=lambda x: x["publication_date_dt"].dt.year)
            .groupby(["year", "message_type_label"])
            .size()
            .reset_index(name="count")
        )
        
        if not yearly_events.empty:
            # Show summary statistics
            total_by_type = yearly_events.groupby("message_type_label")["count"].sum().to_dict()
            summary_text = " | ".join([f"{msg_type}: {count:,} events" for msg_type, count in total_by_type.items()])
            st.info(f"**Total across all years:** {summary_text}")
            
            chart = alt.Chart(yearly_events).mark_bar().encode(
                x=alt.X("year:O", title="Year"),
                y=alt.Y("count:Q", title="Number of Market Messages"),
                color=alt.Color("message_type_label:N", title="Message Type"),
                tooltip=["year:O", "message_type_label", "count"]
            )
            st.altair_chart(chart, use_container_width=True)
        
        # Events by area
        st.markdown(f"### 🌍 Market Events by Price Area for {selected_unit}")
        st.caption("Shows which price areas are affected by this unit's unavailability events (unit may be located in one area but affect multiple areas)")
        
        area_events = []
        for _, row in df_unit.iterrows():
            for area in row["area_names"]:
                area_events.append({
                    "area": area,
                    "message_type": row["message_type_label"],
                    "year": row["publication_date_dt"].year if pd.notna(row["publication_date_dt"]) else None,
                    "planned_status": "Planned" if "Planned" in str(row.get("remarks", "")) else "Unplanned"
                })
        
        if area_events:
            df_area_events = pd.DataFrame(area_events)
            area_summary = df_area_events.groupby(["area", "message_type"]).size().reset_index(name="count")
            area_summary = area_summary.sort_values("count", ascending=False)
            
            # Show which areas are most affected
            st.info(f"**Most affected area:** {area_summary.iloc[0]['area']} with {area_summary.iloc[0]['count']:,} events")
            
            chart = alt.Chart(area_summary).mark_bar().encode(
                x=alt.X("count:Q", title="Number of Market Messages"),
                y=alt.Y("area:N", sort="-x", title="Price Area"),
                color=alt.Color("message_type:N", title="Message Type"),
                tooltip=["area", "message_type", "count"]
            )
            st.altair_chart(chart, use_container_width=True)
            
            # Show detailed breakdown by area
            with st.expander("📋 View detailed breakdown by price area"):
                area_detail = df_area_events.groupby(["area", "message_type", "year"]).size().reset_index(name="count")
                area_pivot = area_detail.pivot_table(
                    index=["area", "message_type"],
                    columns="year",
                    values="count",
                    aggfunc="sum",
                    fill_value=0
                )
                st.dataframe(area_pivot, use_container_width=True)
                st.caption("This table shows the number of events per area, message type, and year")
        
        # Detailed event table
        st.markdown(f"### 📄 All Market Messages for {selected_unit}")
        st.caption("Complete list of all unavailability messages published for this production unit")
        
        # Extract capacity, fuel type, and duration for each row
        def extract_unit_capacity_info(row):
            total_installed = 0
            total_unavailable = 0
            total_available = 0
            fuel_types = set()
            
            fuel_map = {
                1: "Nuclear", 2: "Lignite", 3: "Hard Coal", 4: "Natural Gas",
                5: "Oil", 6: "Biomass", 7: "Geothermal", 8: "Waste",
                9: "Wind Onshore", 10: "Wind Offshore", 11: "Solar", 12: "Hydro",
                13: "Pumped Storage", 14: "Marine", 15: "Other"
            }
            
            # Check production units
            for unit in row.get('production_units_json', []):
                if isinstance(unit, dict):
                    unit_name = unit.get("name") or unit.get("productionUnitName")
                    if unit_name == selected_unit:
                        total_installed += unit.get('installedCapacity', 0) or 0
                        if unit.get('fuelType'):
                            fuel_types.add(fuel_map.get(unit.get('fuelType'), f"Type {unit.get('fuelType')}"))
                        # Get capacity from time periods
                        for period in unit.get('timePeriods', []):
                            if isinstance(period, dict):
                                total_unavailable += period.get('unavailableCapacity', 0) or 0
                                total_available += period.get('availableCapacity', 0) or 0
                                break
            
            # Check generation units
            for unit in row.get('generation_units_json', []):
                if isinstance(unit, dict):
                    unit_name = unit.get("name") or unit.get("generationUnitName")
                    if unit_name == selected_unit:
                        total_installed += unit.get('installedCapacity', 0) or 0
                        if unit.get('fuelType'):
                            fuel_types.add(fuel_map.get(unit.get('fuelType'), f"Type {unit.get('fuelType')}"))
                        for period in unit.get('timePeriods', []):
                            if isinstance(period, dict):
                                total_unavailable += period.get('unavailableCapacity', 0) or 0
                                total_available += period.get('availableCapacity', 0) or 0
                                break
            
            return pd.Series({
                'installed_mw': total_installed if total_installed > 0 else None,
                'unavailable_mw': total_unavailable if total_unavailable > 0 else None,
                'available_mw': total_available if total_available > 0 else None,
                'fuel_type': ", ".join(sorted(fuel_types)) if fuel_types else None
            })
        
        def calculate_unit_duration(row):
            if pd.notna(row.get('event_start_dt')) and pd.notna(row.get('event_stop_dt')):
                duration = row['event_stop_dt'] - row['event_start_dt']
                hours = duration.total_seconds() / 3600
                if hours < 24:
                    return f"{hours:.1f}h"
                else:
                    days = hours / 24
                    return f"{days:.1f}d"
            return None
        
        # Apply extractions
        unit_table = df_unit.copy()
        capacity_info = unit_table.apply(extract_unit_capacity_info, axis=1)
        unit_table['installed_mw'] = capacity_info['installed_mw']
        unit_table['unavailable_mw'] = capacity_info['unavailable_mw']
        unit_table['available_mw'] = capacity_info['available_mw']
        unit_table['fuel_type'] = capacity_info['fuel_type']
        unit_table['duration'] = unit_table.apply(calculate_unit_duration, axis=1)
        
        # Select columns for display
        display_cols = [
            "publication_date", "message_type_label", "event_status_label", 
            "area_display", "event_start", "event_stop", "duration",
            "installed_mw", "unavailable_mw", "available_mw", "fuel_type",
            "publisher_name", "remarks"
        ]
        unit_display = unit_table[display_cols].copy()
        unit_display.columns = [
            "Publication Date", "Message Type", "Status", "Price Area(s)", 
            "Event Start", "Event Stop", "Duration",
            "Installed (MW)", "Unavailable (MW)", "Available (MW)", "Fuel Type",
            "Publisher", "Remarks"
        ]
        st.dataframe(unit_display, use_container_width=True, hide_index=True)
        
        # Download button with enhanced fields
        csv_bytes = unit_display.to_csv(index=False).encode("utf-8")
        st.download_button(
            f"Download {selected_unit} events as CSV",
            data=csv_bytes,
            file_name=f"{selected_unit.replace(' ', '_')}_events.csv",
            mime="text/csv",
        )
    else:
        st.info("💡 Search or select a production/generation unit above to view its market events and price area relationships.")
        
        # Show overview of units by price area
        st.markdown("### 🗺️ Production Units by Price Area")
        st.caption("Overview of how production/generation units are distributed across price areas")
        
        # Extract unit-area relationships
        unit_area_map = []
        for _, row in df.iterrows():
            for prod_unit in row['production_units_json']:
                if isinstance(prod_unit, dict):
                    unit_name = prod_unit.get("name") or prod_unit.get("productionUnitName")
                    area_name = prod_unit.get("areaName")
                    capacity = prod_unit.get("installedCapacity")
                    if unit_name and area_name:
                        unit_area_map.append({
                            "Unit": unit_name,
                            "Price Area": area_name,
                            "Capacity (MW)": capacity if capacity else 0,
                            "Type": "Production"
                        })
            for gen_unit in row['generation_units_json']:
                if isinstance(gen_unit, dict):
                    unit_name = gen_unit.get("name") or gen_unit.get("generationUnitName")
                    area_name = gen_unit.get("areaName")
                    capacity = gen_unit.get("installedCapacity")
                    if unit_name and area_name:
                        unit_area_map.append({
                            "Unit": unit_name,
                            "Price Area": area_name,
                            "Capacity (MW)": capacity if capacity else 0,
                            "Type": "Generation"
                        })
        
        if unit_area_map:
            df_unit_area = pd.DataFrame(unit_area_map).drop_duplicates()
            
            # Summary by area
            area_summary = df_unit_area.groupby("Price Area").agg({
                "Unit": "count",
                "Capacity (MW)": "sum"
            }).reset_index()
            area_summary.columns = ["Price Area", "Number of Units", "Total Capacity (MW)"]
            area_summary = area_summary.sort_values("Total Capacity (MW)", ascending=False)
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Unique Units", f"{len(df_unit_area):,}")
                st.metric("Total Capacity", f"{df_unit_area['Capacity (MW)'].sum():,.0f} MW")
            with col2:
                st.metric("Price Areas", f"{df_unit_area['Price Area'].nunique():,}")
                top_area = area_summary.iloc[0] if len(area_summary) > 0 else None
                if top_area is not None:
                    st.metric("Largest Area (by capacity)", f"{top_area['Price Area']}")
            
            # Chart showing units per area
            st.bar_chart(area_summary.set_index("Price Area")["Number of Units"])
            st.caption("Number of production/generation units per price area")
            
            # Detailed table
            with st.expander("📊 View detailed unit-area breakdown"):
                df_unit_area_sorted = df_unit_area.sort_values(["Price Area", "Capacity (MW)"], ascending=[True, False])
                st.dataframe(df_unit_area_sorted, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(df_unit_area_sorted):,} unit-price area relationships")
        
        # Show a sample of unit-publisher relationships
        with st.expander("📋 View Unit-Publisher/Owner Relationships"):
            st.write("This table shows which publishers/owners are associated with production units:")
            
            # Create a mapping of units to their publishers
            unit_publisher_map = []
            for _, row in df.iterrows():
                publishers = row['publisher_name']
                for unit in row['production_unit_names']:
                    unit_publisher_map.append({"Unit": unit, "Publisher/Owner": publishers})
                for unit in row['generation_unit_names']:
                    unit_publisher_map.append({"Unit": unit, "Publisher/Owner": publishers})
            
            if unit_publisher_map:
                df_mapping = pd.DataFrame(unit_publisher_map)
                # Get most common publisher for each unit
                unit_owners = df_mapping.groupby("Unit")["Publisher/Owner"].agg(
                    lambda x: x.value_counts().index[0]
                ).reset_index()
                unit_owners.columns = ["Production/Generation Unit", "Primary Publisher/Owner"]
                unit_owners = unit_owners.sort_values("Production/Generation Unit")
                
                # Add search functionality
                owner_search = st.text_input("Search units or owners:", "", placeholder="e.g., Hafslund, Aurland...", key="owner_search")
                if owner_search:
                    unit_owners = unit_owners[
                        unit_owners["Production/Generation Unit"].str.contains(owner_search, case=False, na=False) |
                        unit_owners["Primary Publisher/Owner"].str.contains(owner_search, case=False, na=False)
                    ]
                
                st.dataframe(unit_owners, use_container_width=True, hide_index=True)
                st.caption(f"Showing {len(unit_owners):,} unit-publisher relationships")
                
                # Download button
                csv_bytes = unit_owners.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download unit-publisher mapping as CSV",
                    data=csv_bytes,
                    file_name="unit_publisher_mapping.csv",
                    mime="text/csv",
                )
            else:
                st.warning("No unit-publisher relationships found in the data.")


def render_outage_events_interactive():
    st.sidebar.divider()
    st.sidebar.header("⚡ Outage Events Filters")
    mw_threshold = st.sidebar.slider("MW threshold", min_value=100, max_value=2000, value=400, step=50, key="event_mw_slider", help="Filter outages by minimum MW capacity")
    status = st.sidebar.selectbox("Outage status", ["Both", "Planned", "Unplanned"], key="event_status_select")
    
    st.subheader(f"Areas with Outages ≥ {mw_threshold} MW")
    events_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_events.csv"
    if not events_path.exists():
        st.warning("Area outage events CSV not found.")
        return
    df = pd.read_csv(events_path)
    area_options = sorted(df["area"].unique())
    selected_areas_event = st.sidebar.multiselect("Select areas", area_options, key="event_area_multiselect", help="Leave empty to show all areas")
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
    st.sidebar.divider()
    st.sidebar.header("📈 Full Outage Summary")
    
    st.subheader("Area-level Full Outage Summary")
    summary_path = Path(__file__).resolve().parent / "data" / "umm_area_outage_full_status_summary.csv"
    if not summary_path.exists():
        st.warning("Area-level full outage summary CSV not found.")
        return
    df = pd.read_csv(summary_path)
    
    year_options = sorted(df["year"].dropna().unique())
    selected_years = st.sidebar.multiselect("📅 Years", year_options, default=year_options, key="full_status_year_multiselect", help="Select years to analyze")
    df = df[df["year"].isin(selected_years)]
    
    # Area inclusion logic
    area_options = sorted(df["area"].unique())
    selected_areas_full = st.sidebar.multiselect("🌍 Areas", area_options, key="areas_full_multiselect", help="Leave empty to show all areas")
    
    if selected_areas_full:
        df = df[df["area"].isin(selected_areas_full)]
    
    outage_type_options = sorted(df["outage_type"].unique())
    selected_types = st.sidebar.multiselect("📊 Outage types", outage_type_options, default=outage_type_options, key="full_status_type_multiselect")
    df = df[df["outage_type"].isin(selected_types)]
    
    status_options = ["Planned", "Unplanned"]
    selected_status = st.sidebar.multiselect("⚡ Status", status_options, default=status_options, key="full_status_status_multiselect")
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
    
    st.sidebar.divider()
    top_n = st.sidebar.slider("🔝 Top N areas to display", min_value=1, max_value=30, value=10, key="top_n_outage_areas_table", help="Show only the top N areas with most outages")
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

    # Production Unit Analysis Section
    st.divider()
    render_production_unit_analysis(df)

    # Add top outage areas query with filter
    # st.sidebar.header("Top Outage Area Filter")
    # top_n = st.sidebar.slider("Show top N areas with most outages", min_value=1, max_value=20, value=5)
    # st.sidebar.header("Outage Type Status Summary Filter")
    # top_n_status = st.sidebar.slider("Show top N areas by outage type & status", min_value=1, max_value=20, value=10)
    # render_outage_type_status_summary()

    st.divider()
    render_outage_events_interactive()
    
    st.divider()
    render_area_full_outage_summary()

    earliest = df["publication_date_dt"].min()
    if earliest is not None:
        st.caption(
            f"Available publication window: {earliest.date()} to {df['publication_date_dt'].max().date()} "
            "(older entries are not provided by the public API)."
        )


if __name__ == "__main__":
    main()
