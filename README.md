# Nord Pool UMM Data Pipeline

This folder contains a small data pipeline that downloads Urgent Market Messages (UMMs) from Nord Pool's public API and visualises them in Streamlit.

## Prerequisites

- Python 3.10+ (pandas and Streamlit benefit from a reasonably recent interpreter).
- A virtual environment is recommended.

Install dependencies:

```bash
pip install -r UMM/requirements.txt
```

## Download the dataset

```bash
python UMM/scrape_umm.py --since 2011-01-01
```

Arguments of interest:

- `--since` / `--until` restrict publication dates (UTC, `YYYY-MM-DD`).
- `--batch-size` adjusts the API page size (max observed 2000).
- `--max-records` is handy for smoke tests.

The script writes `UMM/data/umm_messages.csv` (created automatically). The public API currently returns data from May 2013 onwards; earlier records are not exposed.

## Launch the dashboard

```bash
streamlit run UMM/app.py
```

The dashboard loads the CSV, offers filters in the sidebar, plots annual and categorical breakdowns, and exposes the filtered subset as both an on-screen table and a downloadable CSV.
