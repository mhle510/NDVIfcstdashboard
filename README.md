# NDVIfcstdashboard

An interactive page that shows the cropland NDVI outlook for the next three months, for **one issue date**,
over Sub-Saharan Africa (Middle East and North Africa coming soon). Built from the random forest NDVI
forecasts of the DAPI pipeline (08c), as Figure 4 of the paper.

* **Left: map.** Standardized anomaly (SA) of NDVI of every cropland grid cell for the selected region,
  month and forecast model. Click a grid cell to select it, scroll to zoom, drag to pan.
* **Right: grid cell.** Country, lon/lat, crops and climate; SA category, NDVI and SA for each month;
  NDVI over 8 months (observed to the initial condition, forecast, normal and normal range);
  crop calendar (HarvestStats v1.0).
* **Lists:** Region (full domain, East, West, Southern Africa; Middle East and North Africa and Lebanon and
  Syria marked "coming soon"), Month (leads 1–3) and Forecast model (SMAP–FLDAS*, FLDAS SM + climate,
  FLDAS SM, NDVI ONLY, Persistence).
* The output is **one self-contained HTML file** (data compressed inside, no internet needed), like the
  ISMN dashboard. The selection is kept in the page address, so a link opens the same view.

## Issue convention

Issue on the 4th of month T; initial condition = month T − 1; leads 1–3 = T, T+1, T+2; the chart shows
T − 3 … T + 4 (8 months). Example: issued 4 September 2026, initial condition August 2026, outlook
September–November 2026. The forecast files are named by the 1st of the month (`forecast_2026-09-01_long.rds`).

## Run

Two steps. Step 1 runs where the forecasts are (Discover); step 2 runs anywhere with Python 3.

```bash
# 1. data file (place this repo at src/ndvi_dashboard of the NDVI forecasting project; needs ../5_paper/utils_paper.R)
cd src/ndvi_dashboard
Rscript export_dashboard.R --issue=2026-09-01                 # -> dashboard_data/ndvi_dashboard_2026-09-01.json
Rscript export_dashboard.R --issue=2026-09-01 --box=22,55,-12,23   # small test file

# 2. page
python ndvi_dashboard.py --data <PATH_ROOT>/dashboard_data/ndvi_dashboard_2026-09-01.json
#   -> ndvi_outlook_Sep2026.html next to the data (--output to choose, --issue-day 4 for the date shown)
```

To try the page without the real data:

```bash
python tools/make_sample_data.py sample/ndvi_dashboard_2026-09-01_sample.json   # SYNTHETIC values
python ndvi_dashboard.py --data sample/ndvi_dashboard_2026-09-01_sample.json --output sample/ndvi_outlook_Sep2026_sample.html
```

## Files

| File | Role |
|---|---|
| `export_dashboard.R` | one JSON per issue date: every cropland grid cell with forecasts (random forest models only), persistence, observed SA, normal (mean, SD, 5–95th percentile 2003–2025), crop calendar, and country outlines (`maps`) |
| `ndvi_dashboard.py` | JSON → self-contained HTML (Python standard library only) |
| `tools/make_sample_data.py` | synthetic JSON with the same layout, for testing |
| `sample/` | synthetic example data and page |

## Data file layout (`ndvi_dashboard_<issue>.json`)

`issue`, `ic_month`, `months[8]`, `obs_months[3]`, `lead_months[3]`, `models[{id, label, desc, n}]`,
`outline{x, y}` (polygons separated by `null`) and `cells[]` with
`lon, lat, c` (country), `ai` (aridity class), `cr` (crops), `mu[8], sd[8], p05[8], p95[8]` (normal),
`o[3]` (observed SA), `f{model id: [3] SA}` (a model without a forecast for the grid cell is absent),
`cal{crop: 8 letters}` (P planting–vegetative, G vegetative–harvest, H harvest–end of season, `.` none).
The `clim` entry of `f` (SA = 0) is not shown in the page; the normal is drawn in the chart instead.
