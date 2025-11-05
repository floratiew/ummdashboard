# Production Sandbox

Tools in this folder fetch live (or cached) ENTSO-E/Nord Pool series, run the
water value estimator, and expose the outputs via a Streamlit dashboard. The
implementation follows the methodology described in *Estimation of water values
from live power production data* (SAMBA/05/11).

## Quick start

### 1. Prepare credentials

- `ENTSOE_TOKEN` – transparency platform token (env var or `toolkit/.env`). Optional if you only run the web scraper fallback.
- `NORDPOOL_API_KEY` – required for quarter-hour prices; the UI gracefully falls back to cached CSVs when absent.
- `GEMINI_API_KEY` – optional. When set, the Streamlit app summarises UMM events with the Gemini API.

### 2. Run the pipeline

```bash
cd WaterValues/sandbox/production
python3 pipeline.py --area NO2 --start 2024-10-01 --end 2024-10-08
```

Common flags:

- `--area` – bidding zone (NO1–NO5); selects matching plants from `config.PLANTS`.
- `--methods` – estimator variants (`minimum`, `jump`, or `raw` in the UI).
- `--strictness`, `--jumpm`, `--max-samples` – forwarded to `water_value.watervalue`.
- `--output-summary` – location for the aggregated JSON written to `output/`.
- `--production-source` – only `web` is supported; production is always scraped from the ENTSO-E transparency portal. Scraping emits per-unit CSVs beside the plant-level series.

Downloads are cached under `data/processed/`. In the Streamlit UI, the “Re-download production data (web scraper)”
checkbox forwards `refresh_data=True` into `run_pipeline()`. Programmatic callers can pass `refresh_data=False`
to reuse cached CSVs.

### 3. Launch the Streamlit dashboard

```bash
cd WaterValues/sandbox/production
streamlit run streamlit_app.py
```

The sidebar selects the price area, plant, estimation method, analysis range, and fetch options. “Re-download production data (web scraper)” calls `run_pipeline()` before refreshing the UI.

Displayed charts cover day-ahead, intraday auction, and quarter-hour prices (when available) alongside production, smoothed segment means, and breakpoint markers. Tables summarise production segments, transitions, and water-value curves produced by the pipeline.

## Layout

- `pipeline.py` – orchestrates downloads, alignment, estimator runs, and persistence of processed artefacts and the summary JSON.
- `fetchers.py` – wrappers around `toolkit.power` clients plus the ENTSO-E transparency web scraper used for production data.
- `config.py` – plant metadata (registered resources, max installed, prod limits) and directory helpers.
- `streamlit_app.py` – Streamlit UI for re-running the pipeline and visualising outputs, including optional UMM event summaries.
- `data/` – cached source series organised by area/plant (`processed/`) and raw fetch payloads (`raw/` when present).
- `output/` – per-plant results: aligned segments, breakpoints, water-value histories, and `production_summary.json`.

## Data flow

1. `run_pipeline()` downloads prices and production for the selected area, applies the water value estimator for each plant/method, and serialises CSVs plus the summary JSON.
2. `streamlit_app.py` consumes these files (`data/processed/` and `output/`) to render charts, segment summaries, and transition tables.
3. Optional UMM messages (`UMM/data/umm_messages.csv`) are filtered by plant and area and summarised if a Gemini key is configured.

Progress feedback is reported through the Streamlit sidebar progress bar when the UI triggers the pipeline, and the CLI prints incremental updates.

## Algorithm verification

`validate_sandbox.py` exercises synthetic scenarios and (optionally) compares against the numerical examples in `watervalue2011.pdf` via the original `eksempel.RData`, ensuring the implementation matches the methodology within tolerance.

## Further reading

- Original methodology: `../../watervalue2011.pdf`
- Pure sandbox workflows (synthetic data): `../README.md`
- Shared ENTSO-E/Nord Pool helpers: `../../toolkit/power.py`
