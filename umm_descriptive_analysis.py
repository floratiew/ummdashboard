import pandas as pd
from pathlib import Path
from collections import Counter
import re

# Load UMM data
DATA_PATH = Path("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_messages.csv")
df = pd.read_csv(DATA_PATH)

# Helper: Find area names in remarks (simple regex for demonstration)
def extract_area_names(text):
    # Example: look for area codes like NO1, NO2, SE1, DK1, etc.
    return re.findall(r"\b([A-Z]{2}\d)\b", str(text))

# Filter for interconnector outages in remarks
outage_keywords = ["interconnector", "outage", "transmission", "link", "failure", "fault"]
def is_interconnector_outage(text):
    text = str(text).lower()
    return any(keyword in text for keyword in outage_keywords)

# Only include relevant outage types for counting
RELEVANT_OUTAGE_TYPES = {"1.0", "2.0", "3.0", 1.0, 2.0, 3.0, "Production unavailability", "Consumption unavailability", "Transmission outage"}

# Mapping for unavailability_type codes to human-readable labels
UNAVAILABILITY_TYPE_LABELS = {
    "1.0": "Production unavailability",
    "2.0": "Consumption unavailability",
    "3.0": "Transmission outage",
    "4.0": "Market notice",
    "5.0": "Other market information",
    "nan": "Unknown",
    "Unknown": "Unknown"
}

def get_type_label(code):
    return UNAVAILABILITY_TYPE_LABELS.get(str(code), "Unknown")

def is_relevant_outage(row):
    outage_type = row.get("unavailability_type", "Unknown")
    # Accept both numeric and string forms
    if str(outage_type).strip() in RELEVANT_OUTAGE_TYPES:
        return True
    label = get_type_label(outage_type)
    return label in RELEVANT_OUTAGE_TYPES

# Collect area mentions for interconnector outages (filtered by relevant outage types)
area_counter = Counter()
for _, row in df.iterrows():
    if is_interconnector_outage(row["remarks"]) and is_relevant_outage(row):
        areas = extract_area_names(row["remarks"])
        area_counter.update(areas)

# Top 5 areas with most outages (filtered)
top_areas = area_counter.most_common(5)
print("Top 5 areas with most interconnector outages (by remarks, filtered):")
for area, count in top_areas:
    print(f"{area}: {count} outages")

# Optionally, save a summary to CSV
summary_df = pd.DataFrame(top_areas, columns=["area", "outage_count"])
summary_df.to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_interconnector_outage_summary.csv", index=False)
print("Summary saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_interconnector_outage_summary.csv")

# Most common outage types in each area (filtered by relevant outage types)
outage_type_counter = {}
for _, row in df.iterrows():
    if is_interconnector_outage(row["remarks"]) and is_relevant_outage(row):
        areas = extract_area_names(row["remarks"])
        outage_type = str(row.get("unavailability_type", "Unknown"))
        for area in areas:
            if area not in outage_type_counter:
                outage_type_counter[area] = Counter()
            outage_type_counter[area][outage_type] += 1

print("Most common outage types in each area (filtered):")
for area, counter in outage_type_counter.items():
    most_common_type, count = counter.most_common(1)[0]
    label = get_type_label(most_common_type)
    print(f"{area}: {label} ({count} outages)")

# Optionally, save to CSV
area_type_summary = []
for area, counter in outage_type_counter.items():
    most_common_type, count = counter.most_common(1)[0]
    label = get_type_label(most_common_type)
    if label in RELEVANT_OUTAGE_TYPES:
        area_type_summary.append({"area": area, "outage_type": label, "count": count})
pd.DataFrame(area_type_summary).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_type_summary.csv", index=False)
print("Area outage type summary saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_type_summary.csv")

# Helper: Check if outage is planned or unplanned
planned_keywords = ["planned", "maintenance", "scheduled"]
unplanned_keywords = ["unplanned", "unexpected", "fault", "failure", "emergency"]
def get_planned_status(text, unavailability_type=None):
    # Prefer explicit unavailability_type if available
    if unavailability_type is not None:
        type_str = str(unavailability_type).strip().lower()
        if "planned" in type_str:
            return "Planned"
        if "unplanned" in type_str:
            return "Unplanned"
    # Fallback to keyword search in remarks
    text = str(text).lower()
    if any(word in text for word in planned_keywords):
        return "Planned"
    if any(word in text for word in unplanned_keywords):
        return "Unplanned"
    return "Unknown"

# Most common outage types in each area (with planned/unplanned status, filtered by relevant outage types)
area_type_status_summary = []
for area, counter in outage_type_counter.items():
    most_common_type, count = counter.most_common(1)[0]
    label = get_type_label(most_common_type)
    if label in RELEVANT_OUTAGE_TYPES:
        # Find planned/unplanned status for the most common outage type in this area
        status_counter = Counter()
        for _, row in df.iterrows():
            if is_interconnector_outage(row["remarks"]) and is_relevant_outage(row):
                areas = extract_area_names(row["remarks"])
                outage_type = str(row.get("unavailability_type", "Unknown"))
                if area in areas and outage_type == most_common_type:
                    status = get_planned_status(row.get('remarks', ''), row.get('unavailability_type', None))
                    status_counter[status] += 1
        planned_status, status_count = status_counter.most_common(1)[0] if status_counter else ("Unknown", 0)
        area_type_status_summary.append({"area": area, "outage_type": label, "count": count, "planned_status": planned_status, "status_count": status_count})
pd.DataFrame(area_type_status_summary).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_type_status_summary.csv", index=False)
print("Area outage type + planned/unplanned status summary saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_type_status_summary.csv")

# --- Additional analysis for user questions ---

# Helper: Extract MW from remarks using regex (e.g., '400 MW', '500MW', etc.)
def extract_mw_from_remarks(text):
    matches = re.findall(r"(\d{2,5})\s*mw", str(text).lower())
    if matches:
        # Return the largest MW value found in the string
        return float(max(matches, key=lambda x: float(x)))
    return 0.0

# Add MW column to dataframe
if 'remarks' in df:
    df['extracted_mw'] = df['remarks'].apply(extract_mw_from_remarks)
else:
    df['extracted_mw'] = 0.0

# Filter for outages > 400 MW
large_outages = df[df['extracted_mw'] > 400]

# Add year column (from publication_date or event_start)
if 'publication_date' in large_outages:
    large_outages['year'] = pd.to_datetime(large_outages['publication_date'], errors='coerce').dt.year
elif 'event_start' in large_outages:
    large_outages['year'] = pd.to_datetime(large_outages['event_start'], errors='coerce').dt.year
else:
    large_outages['year'] = None

# Count unplanned outages > 400 MW by year
unplanned_large = large_outages[large_outages['remarks'].apply(get_planned_status) == 'Unplanned']
unplanned_by_year = unplanned_large.groupby('year').size().reset_index(name='unplanned_outages')
print("Unplanned outages > 400 MW by year:")
print(unplanned_by_year)

# Compare planned vs unplanned outages > 400 MW (all years)
planned_count = (large_outages.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Planned').sum()
unplanned_count = (large_outages.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Unplanned').sum()
print(f"Planned outages > 400 MW: {planned_count}")
print(f"Unplanned outages > 400 MW: {unplanned_count}")
if planned_count > unplanned_count:
    print("There are more planned outages > 400 MW.")
elif unplanned_count > planned_count:
    print("There are more unplanned outages > 400 MW.")
else:
    print("Planned and unplanned outages > 400 MW are equal.")

# --- Area-level analysis for outages >400 MW ---
area_large_outage_summary = []
area_codes = sorted({area for areas in large_outages['remarks'].apply(extract_area_names) for area in areas})
for area in area_codes:
    area_mask = large_outages['remarks'].apply(lambda txt: area in extract_area_names(txt))
    planned = large_outages[area_mask & (large_outages.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Planned')]
    unplanned = large_outages[area_mask & (large_outages.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Unplanned')]
    area_large_outage_summary.append({
        'area': area,
        'planned_count': len(planned),
        'unplanned_count': len(unplanned)
    })
pd.DataFrame(area_large_outage_summary).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_large_outage_summary.csv", index=False)
print("Area-level large outage summary (>400 MW) saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_large_outage_summary.csv")
print(pd.DataFrame(area_large_outage_summary))

# --- Save each large outage (area, MW, status) for dashboard filtering ---
large_outage_rows = []
for _, row in df.iterrows():
    mw = extract_mw_from_remarks(row.get('remarks', ''))
    if mw > 0:
        areas = extract_area_names(row.get('remarks', ''))
        status = get_planned_status(row.get('remarks', ''), row.get('unavailability_type', None))
        for area in areas:
            large_outage_rows.append({
                'area': area,
                'mw': mw,
                'status': status,
                'publication_date': row.get('publication_date', ''),
                'remarks': row.get('remarks', '')
            })
pd.DataFrame(large_outage_rows).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_events.csv", index=False)
print("Saved area outage events with MW and status to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_events.csv")

# Ensure message_type_label exists
MESSAGE_TYPE_LABELS = {
    1: "Production unavailability",
    2: "Consumption unavailability",
    3: "Transmission outage",
    4: "Market notice",
    5: "Other market information",
}
if 'message_type_label' not in df.columns:
    df['message_type_label'] = df['message_type'].map(MESSAGE_TYPE_LABELS).fillna('Other')

# --- Area-level full outage analysis (using message_type_label, with year) ---
def extract_year(row):
    date_str = row.get('publication_date', None)
    if pd.notnull(date_str):
        try:
            return pd.to_datetime(date_str, errors='coerce').year
        except Exception:
            return None
    return None

area_full_summary = []
area_codes = sorted({area for areas in df['remarks'].apply(extract_area_names) for area in areas})
for area in area_codes:
    area_mask = df['remarks'].apply(lambda txt: area in extract_area_names(txt))
    area_df = df[area_mask]
    for year in sorted(area_df['publication_date'].dropna().apply(lambda x: pd.to_datetime(x, errors='coerce').year).unique()):
        year_mask = area_df['publication_date'].apply(lambda x: pd.to_datetime(x, errors='coerce').year == year if pd.notnull(x) else False)
        df_year = area_df[year_mask]
        planned = df_year[df_year.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Planned']
        unplanned = df_year[df_year.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == 'Unplanned']
        transmission = df_year[df_year['message_type_label'] == 'Transmission outage']
        production = df_year[df_year['message_type_label'] == 'Production unavailability']
        consumption = df_year[df_year['message_type_label'] == 'Consumption unavailability']
        area_full_summary.append({
            'area': area,
            'year': year,
            'planned_count': len(planned),
            'unplanned_count': len(unplanned),
            'transmission_outage_count': len(transmission),
            'production_unavailability_count': len(production),
            'consumption_unavailability_count': len(consumption)
        })
pd.DataFrame(area_full_summary).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_full_summary.csv", index=False)
print("Area-level full outage summary (with year) saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_full_summary.csv")
print(pd.DataFrame(area_full_summary))

# --- Area-level full outage analysis (using message_type_label, planned/unplanned, with year) ---
area_full_status_summary = []
area_codes = sorted({area for areas in df['remarks'].apply(extract_area_names) for area in areas})
for area in area_codes:
    area_mask = df['remarks'].apply(lambda txt: area in extract_area_names(txt))
    area_df = df[area_mask]
    for year in sorted(area_df['publication_date'].dropna().apply(lambda x: pd.to_datetime(x, errors='coerce').year).unique()):
        year_mask = area_df['publication_date'].apply(lambda x: pd.to_datetime(x, errors='coerce').year == year if pd.notnull(x) else False)
        df_year = area_df[year_mask]
        for outage_type in ["Transmission outage", "Production unavailability", "Consumption unavailability"]:
            for status in ["Planned", "Unplanned"]:
                count = df_year[(df_year['message_type_label'] == outage_type) & (df_year.apply(lambda row: get_planned_status(row['remarks'], row.get('unavailability_type', None)), axis=1) == status)].shape[0]
                area_full_status_summary.append({
                    'area': area,
                    'year': year,
                    'outage_type': outage_type,
                    'planned_status': status,
                    'count': count
                })
pd.DataFrame(area_full_status_summary).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_full_status_summary.csv", index=False)
print("Area-level full outage summary (with planned/unplanned status) saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_outage_full_status_summary.csv")
print(pd.DataFrame(area_full_status_summary))

# --- Area-level total outage count (all years) ---
area_total_outages = []
for area in area_codes:
    area_mask = df['remarks'].apply(lambda txt: area in extract_area_names(txt))
    area_df = df[area_mask]
    total_outages = area_df.shape[0]
    area_total_outages.append({'area': area, 'total_outages': total_outages})
pd.DataFrame(area_total_outages).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_total_outages.csv", index=False)
print("Total outages for each area saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_total_outages.csv")
print(pd.DataFrame(area_total_outages))

# --- Area-level yearly outage count ---
area_yearly_outages = []
for area in area_codes:
    area_mask = df['remarks'].apply(lambda txt: area in extract_area_names(txt))
    area_df = df[area_mask]
    for year in sorted(area_df['publication_date'].dropna().apply(lambda x: pd.to_datetime(x, errors='coerce').year).unique()):
        year_mask = area_df['publication_date'].apply(lambda x: pd.to_datetime(x, errors='coerce').year == year if pd.notnull(x) else False)
        df_year = area_df[year_mask]
        total_outages = df_year.shape[0]
        area_yearly_outages.append({'area': area, 'year': year, 'total_outages': total_outages})
pd.DataFrame(area_yearly_outages).to_csv("/Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_yearly_outages.csv", index=False)
print("Yearly outages for each area saved to /Users/floratiew/Desktop/power_sandbox/UMM/data/umm_area_yearly_outages.csv")
print(pd.DataFrame(area_yearly_outages))
