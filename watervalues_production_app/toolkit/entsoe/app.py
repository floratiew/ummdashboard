"""
Streamlit dashboard for visualising ENTSO-E day-ahead price data saved in this folder.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).resolve().parent


@st.cache_data
def load_dataset(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    if "value" in df.columns:
        df.rename(columns={"value": "price"}, inplace=True)
    return df


def main() -> None:
    st.set_page_config(page_title="ENTSO-E Day-Ahead Prices", layout="wide")
    st.title("ENTSO-E Day-Ahead Prices")

    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        st.warning("No CSV files found in the entsoe directory. Run the ENTSO-E fetch command first.")
        st.stop()

    file_lookup = {file.name: file for file in csv_files}
    selected_filename = st.selectbox("Select dataset", options=list(file_lookup))
    selected_path = file_lookup[selected_filename]

    df = load_dataset(selected_path)

    st.caption(f"Loaded {selected_filename} with {len(df)} rows.")

    meta_columns = [col for col in ("document_type", "in_domain", "out_domain", "currency") if col in df.columns]
    if meta_columns:
        with st.expander("Metadata", expanded=False):
            st.write(df[meta_columns].drop_duplicates().reset_index(drop=True))

    if {"timestamp", "price"} <= set(df.columns):
        st.line_chart(df.set_index("timestamp")["price"], height=320)

    st.dataframe(df)


if __name__ == "__main__":
    main()
