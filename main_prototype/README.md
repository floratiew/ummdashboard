# Utility Vision Prototype

Self-contained Node.js prototype that showcases the combined Water Values production insights and UMM outage transparency dashboards. The goal is to provide a demo-friendly experience inside the `main_prototype` folder without relying on the full production stacks.

## Features

- Simple login gate (accepts any credentials) to mimic the production authentication flow.
- Landing page summarising hydro plant production, water value bands, and price curves.
- Interactive charts powered by Chart.js using the real NO2 production extracts from `watervalues_production_app/WaterValues/sandbox/production`.
- UMM feed page with searching and filtering across area, status, and participant, backed by live data pulled from the Nord Pool UMM API.
- Derived outage tables and breakdowns calculated from the fetched messages (no more placeholder summaries).
- All assets (frontend, backend, data files) live under `main_prototype` so the prototype is portable.

## Project layout

```
main_prototype/
├── data/                      # Static datasets copied or authored for the prototype
│   ├── water_values_no2.json          # Derived from Saurdal & Kvilldal processed feeds
│   ├── umm_messages.csv               # Latest 500 Nord Pool UMM records
│   ├── umm_area_total_outages.csv     # Legacy summaries (kept for comparison)
│   ├── umm_area_large_outage_summary.csv
│   └── umm_area_outage_type_status_summary.csv
├── public/                    # Static React client served via Express
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── server.js                  # Express server exposing JSON APIs + static hosting
├── package.json
└── README.md                  # This file
```

## Getting started

1. Install dependencies (already done once but safe to repeat):

   ```bash
   cd main_prototype
   npm install
   ```

2. Launch the prototype server:

   ```bash
   npm start
   ```

3. Visit http://localhost:3000 to interact with the UI. Use any username/password at the login prompt.

## Data refresh

- **Water values**: `data/water_values_no2.json` was generated from `watervalues_production_app/WaterValues/sandbox/production` (Saurdal & Kvilldal plants, price area NO2). Re-run the helper snippet from the repository root if you ingest newer processed CSVs.
- **UMM feed**: `data/umm_messages.csv` contains the latest 500 messages retrieved via `python3 scrape_umm.py --max-records 500 --output main_prototype/data/umm_messages.csv`. Increase `--max-records` if you need a broader sample.

## Notes & possible extensions

- The datasets under `data/` are lightweight samples. Swap them for live extracts to demo real numbers.
- React is loaded via CDN and compiled at runtime with Babel for simplicity. When ready, move to a Vite or Next.js build to bundle assets and add routing/auth integration.
- The Express endpoints currently read static files synchronously on each request. For larger data or live integrations, promote this to cached loads or a proper data service layer.
