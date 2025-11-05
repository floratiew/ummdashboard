# Norwegian Power Market Data Toolkit

This `toolkit/` directory contains a single CLI (`power.py`) that wraps the key Norwegian power-market sources—ENTSO-E, Statnett, NVE HydAPI, and Elhub—into one consistent workflow. All Ably-specific assets live next door in `../ably/`, while this folder focuses on the public-market download tooling.

## Project Layout

- `power.py` – main CLI entry point.
- `.env` – local environment variables automatically loaded by `power.py`.
- `data/` – default landing spot for downloaded CSV/Parquet files (already contains sample outputs).
- `__pycache__/` – bytecode cache (safe to ignore).

## Quick Start

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install requests pandas  # add pyarrow if you want Parquet output
python toolkit/power.py --help
```

All examples assume you remain in the repository root and invoke the CLI via `python toolkit/power.py …`.

## Credentials and Environment

Two upstream APIs require keys:

| Service | Variable | Where to obtain |
|---------|----------|-----------------|
| ENTSO-E Transparency Platform | `ENTSOE_TOKEN` | Create an account at <https://transparency.entsoe.eu>, register an application, copy the security token. |
| NVE HydAPI | `NVE_API_KEY` | Request an API key at <https://hydapi.nve.no>. |

Populate `toolkit/.env` (preferred) or export the variables in your shell:

```bash
echo 'ENTSOE_TOKEN=your_token_here' >> toolkit/.env
echo 'NVE_API_KEY=your_hydapi_key' >> toolkit/.env
```

`power.py` autoloads the `.env` file on start. You can still pass `--token` or `--api-key` to override the defaults per command.

## Command Reference

### ENTSO-E Transparency Platform

Fetch XML documents (day-ahead prices, load, generation, flows, balancing, etc.) and convert them to tidy tabular output:

```bash
python toolkit/power.py entsoe \
  --document A44 \
  --process A01 \
  --in-domain '10YNO-1--------2' \
  --out-domain '10YNO-1--------2' \
  --start 2024-01-01T00:00 \
  --end   2024-01-02T00:00 \
  --out toolkit/data/no1_day_ahead_prices.csv
```

- `--document` chooses the dataset (A44 = day-ahead prices by bidding zone).
- Use `--extra key=value` for additional parameters (e.g. `psrType`, `contract_MarketAgreement.type`).
- `--out` controls the output format based on extension (`.csv`, `.parquet`, `.json`, `.ndjson`). Omit it to stream CSV to stdout.

### Statnett “Last ned grunndata”

```bash
# Inspect available bulk archives
python toolkit/power.py statnett list --out toolkit/data/statnett_links.csv

# Download a single dataset by slug/year
python toolkit/power.py statnett download \
  --dataset produksjon \
  --year 2023 \
  --out toolkit/data/statnett_produksjon_2023.csv
```

### NVE HydAPI

```bash
# Discover stations or parameters
python toolkit/power.py nve stations --name magasin --out toolkit/data/nve_stations.csv
python toolkit/power.py nve parameters --out toolkit/data/nve_parameters.csv

# Retrieve observation series (weekly reservoir fill example)
python toolkit/power.py nve observations \
  --station 109.25.0 \
  --parameter reservoirlevel \
  --resolution week \
  --start 2024-01-01 \
  --end 2024-06-01 \
  --out toolkit/data/nve_reservoirlevel_weekly.csv
```

Add `--include-quality` to keep quality/correction flags, and use `--aggregation` (mean, sum, min, max, first, last, median) when resampling weekly/monthly.

### Elhub Energy-Data

```bash
python toolkit/power.py elhub \
  --resource price-areas \
  --dataset CONSUMPTION_PER_GROUP_MBA_HOUR \
  --start 2024-08-01 \
  --end 2024-08-07 \
  --filter consumptionGroup=private \
  --out toolkit/data/elhub_price_area.csv
```

Append `--filter key=value` multiple times to refine the query. Outputs arrive as CSV by default.

## Logging & Debugging

Increase verbosity to inspect resolved parameters and raw responses:

```bash
python toolkit/power.py --log-level DEBUG entsoe ...
```

## Known Constraints

- ENTSO-E resolutions shift between hourly and quarter-hour; the CLI keeps original timestamps—aggregate downstream as needed.
- Statnett occasionally renames archive slugs; rerun the `statnett list` command to refresh.
- HydAPI enforces rate limits—sleep between loops to avoid 429s.
- Elhub throttles at roughly 5 req/s per IP; retry with backoff if necessary.

## Verification Snapshot

Running:

```bash
python toolkit/power.py entsoe \
  --start 2024-01-01T00:00 \
  --end 2024-01-02T00:00 \
  --in-domain '10YNO-1--------2' \
  --out-domain '10YNO-1--------2' \
  --out toolkit/data/test_entsoe.csv
```

produced `toolkit/data/test_entsoe.csv` with hourly NO1 day-ahead prices (ENTSO-E response HTTP 200). Use it as a sanity check before wiring the CLI into automation.

## Extending

`power.py` is intentionally modular—add subcommands, schedule regular pulls, or swap output formats as needed. Contributions welcome.
