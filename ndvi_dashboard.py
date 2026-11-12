#!/usr/bin/env python3
"""
Build the NDVI outlook dashboard for ONE issue date: one self-contained HTML page with
a map of cropland grid cells (left) and the NDVI outlook of the selected grid cell (right).

Input  : dashboard_data/ndvi_dashboard_<YYYY-MM-01>.json, written by export_dashboard.R
Output : one .html file (data gzip-compressed and embedded, no internet needed to open it)

Page
----
  Controls   Region, Month (leads 1-3) and Forecast model, as drop-down lists
  Map        standardized anomaly (SA) of NDVI of the selected model and month, every cropland
             grid cell; click a grid cell to select it, scroll to zoom, drag to pan
  Grid cell  country, lon/lat, crops, climate; SA category, NDVI and SA per month; NDVI over the
             8 months (observed to the initial condition, forecast, normal and normal range);
             crop calendar (HarvestStats v1.0)
  The climatology entry of the data file is not shown (its SA is 0 everywhere); the normal is
  drawn in the grid cell chart instead.

Usage
-----
  python ndvi_dashboard.py --data dashboard_data/ndvi_dashboard_2026-09-01.json
  python ndvi_dashboard.py --data ... --output ndvi_outlook_Sep2026.html --issue-day 4 --author "Hung Le"

Needs only the Python standard library.
"""

import argparse
import base64
import datetime as dt
import gzip
import json
import os
import sys

# Regions of the Region list: (id, label, lon1, lon2, lat1, lat2, available)
REGIONS = [
    ("full",   "Full domain",                   -20, 60,   -40, 40, True),
    ("east",   "East Africa",                    22, 55,   -12, 23, True),
    ("west",   "West Africa",                   -19, 26,    -5, 25, True),
    ("south",  "Southern Africa",                 8, 52,   -37,  6, True),
    ("mena",   "Middle East and North Africa",  -19, 55,    20, 40, False),   # coming soon
    ("levant", "Lebanon and Syria",              35, 42.5,  32, 38, False),   # coming soon
]
HIDE_MODELS = {"clim"}          # in the data file, not shown in the Forecast model list
DEFAULT_MODEL = "smap"


def month_name(ym, fmt="%B %Y"):
    return dt.datetime.strptime(ym + "-01", "%Y-%m-%d").strftime(fmt)


def compact(cells, model_ids):
    """Columnar arrays: smaller than one dict per grid cell, quick to read in the page."""
    def r(v, k):
        return None if v is None else round(float(v), k)
    out = {"lon": [], "lat": [], "c": [], "u1": [], "u2": [], "ai": [], "cr": [], "mu": [], "sd": [], "p05": [], "p95": [],
           "o": [], "cal": [], "f": {m: [] for m in model_ids}}
    for c in cells:
        out["lon"].append(c["lon"]); out["lat"].append(c["lat"])
        out["c"].append(c.get("c") or ""); out["u1"].append(c.get("u1") or ""); out["u2"].append(c.get("u2") or "")
        out["ai"].append(c.get("ai") or ""); out["cr"].append(c.get("cr") or "")
        for k in ("mu", "sd", "p05", "p95"):
            v = c.get(k) or [None] * 8
            out[k].append([r(x, 3) for x in v])
        out["o"].append([r(x, 2) for x in (c.get("o") or [None] * 3)])
        cal = c.get("cal") or {}
        out["cal"].append(cal if isinstance(cal, dict) else {})
        f = c.get("f") or {}
        for m in model_ids:
            v = f.get(m)
            out["f"][m].append(None if v is None else [r(x, 2) for x in v])
    return out


def compact_units(units):
    """HarvestStat units: names and label points, all rings in one x/y list separated by None."""
    out = {"a0": [], "a1": [], "a2": [], "lx": [], "ly": [], "x": [], "y": []}
    for u in units or []:
        for k in ("a0", "a1", "a2"):
            out[k].append(u.get(k) or "")
        out["lx"].append(u.get("lx")); out["ly"].append(u.get("ly"))
        xs, ys = u.get("x") or [], u.get("y") or []
        if not isinstance(xs, list): xs, ys = [xs], [ys]
        out["x"].extend(xs + [None]); out["y"].extend(ys + [None])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", required=True, help="ndvi_dashboard_<issue>.json from export_dashboard.R")
    ap.add_argument("--output", help="output .html (default: ndvi_outlook_<Mon><YYYY>.html next to the data)")
    ap.add_argument("--issue-day", type=int, default=4, help="day of the month shown as the issue date (default 4)")
    ap.add_argument("--title", default="Cropland NDVI outlook")
    ap.add_argument("--author", default="Hung Le", help="name shown in the page header (empty to hide)")
    a = ap.parse_args()

    with open(a.data, encoding="utf-8") as fh:
        D = json.load(fh)
    models = [m for m in D["models"] if m["id"] not in HIDE_MODELS]
    ids = [m["id"] for m in models]
    cells = D["cells"]
    if not cells:
        sys.exit("No grid cells in " + a.data)

    lons = sorted({round(c["lon"], 4) for c in cells})
    steps = [b - a_ for a_, b in zip(lons, lons[1:]) if b - a_ > 1e-6]
    res = round(min(steps), 4) if steps else 0.25

    issue = D["issue"][:7]
    ic, leads = D["ic_month"], D["lead_months"]
    issue_date = dt.datetime.strptime(issue + "-01", "%Y-%m-%d").replace(day=a.issue_day)
    payload = {
        "title": a.title, "author": a.author,
        "issued": f"{issue_date.day} {issue_date.strftime('%B %Y')}",
        "ic": month_name(ic), "ic_short": month_name(ic, "%B"),
        "months": D["months"], "obs_months": D["obs_months"], "lead_months": leads,
        "outlook": f"{month_name(leads[0], '%B')}–{month_name(leads[-1])}"
                   if leads[0][:4] == leads[-1][:4] else f"{month_name(leads[0])}–{month_name(leads[-1])}",
        "models": [{"id": m["id"], "label": m["label"], "desc": m.get("desc", "")} for m in models],
        "default_model": DEFAULT_MODEL if DEFAULT_MODEL in ids else ids[0],
        "regions": [dict(id=r[0], label=r[1], b=[r[2], r[3], r[4], r[5]], ok=r[6]) for r in REGIONS],
        "res": res,
        "sample": bool(D.get("sample")),
        "outline": D.get("outline") or {"x": [], "y": []},
        "units": compact_units(D.get("units")),
        "cells": compact(cells, ids),
    }
    blob = base64.b64encode(gzip.compress(json.dumps(payload, separators=(",", ":")).encode("utf-8"), 9)).decode("ascii")

    out = a.output or os.path.join(os.path.dirname(os.path.abspath(a.data)),
                                   "ndvi_outlook_" + dt.datetime.strptime(issue, "%Y-%m").strftime("%b%Y") + ".html")
    html = HTML.replace("__TITLE__", f"{a.title} · issued {payload['issued']}").replace("__DATA__", blob)
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(html)
    n_f = {m: sum(v is not None for v in payload["cells"]["f"][m]) for m in ids}
    print(f"Issue {payload['issued']} | IC {payload['ic']} | outlook {payload['outlook']}")
    print(f"Grid cells: {len(cells)} (resolution {res} deg) | with a forecast: " +
          ", ".join(f"{m} {n}" for m, n in n_f.items()))
    print(f"Country outline points: {len(payload['outline']['x'])} | HarvestStat units: {len(payload['units']['a0'])}")
    if not payload["outline"]["x"]:
        print("WARNING: no country outlines in the data file -> re-run export_dashboard.R (current version)")
    print(f"-> {out} ({os.path.getsize(out) / 1e6:.1f} MB)")


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<style>
:root { --page:#f7f6f2; --card:#fcfcfa; --ink:#141413; --ink2:#52514e; --muted:#6b6a64; --line:#e3e1da;
  --chip:#f0efe9; --blue:#2171b5; --ocean:#eef3f7; --land:#f4f3ef; --border:#8a887f; }
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--page); color: var(--ink);
  font: 14px/1.4 Inter, system-ui, -apple-system, "Segoe UI", sans-serif; }
.wrap { max-width: 1440px; margin: 0 auto; padding: 18px 22px 26px; display: flex; flex-direction: column; gap: 14px; }
header { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; }
header h1 { margin: 0; font-size: 21px; font-weight: 700; letter-spacing: -0.01em; }
header .sub { font-size: 14px; font-weight: 500; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 12px 14px; min-width: 0; }
.controls { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 10px 18px; }
.controls label { display: flex; flex-direction: column; gap: 5px; font-size: 12px; color: var(--ink2); }
.controls label.chk { flex-direction: row; align-items: center; gap: 8px; font-size: 13.5px; color: var(--ink); min-height: 40px; cursor: pointer; }
.controls label.chk input { width: 18px; height: 18px; }
.controls select { font: inherit; font-size: 14px; min-height: 40px; padding: 4px 10px; border: 1px solid #cfcdc5;
  border-radius: 7px; background: #fff; color: var(--ink); cursor: pointer; }
main { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap: 14px; align-items: start; }
section.card { display: flex; flex-direction: column; gap: 10px; }
h2 { margin: 0; font-size: 15px; font-weight: 600; }
.small { font-size: 12.5px; color: var(--ink2); }
.note { margin: 0; font-size: 12px; color: var(--muted); }
#mapbox { position: relative; }
#map { display: block; width: 100%; background: var(--ocean); border-radius: 6px; cursor: crosshair; touch-action: none; }
#tip { position: absolute; pointer-events: none; background: rgba(20,20,19,0.9); color: #fff; font-size: 12px;
  padding: 4px 8px; border-radius: 5px; white-space: nowrap; transform: translate(10px, -120%); display: none; }
#soon { position: absolute; left: 50%; top: 50%; transform: translate(-50%, -50%); background: rgba(255,255,255,0.94);
  border: 1px solid #cfcdc5; border-radius: 8px; padding: 10px 18px; text-align: center; display: none; }
.legend { display: flex; gap: 2px; max-width: 440px; }
.legend div { display: flex; flex-direction: column; align-items: center; gap: 3px; flex: 1 1 0; }
.legend span.sw { display: block; width: 100%; height: 10px; }
.legend span.lb { font-size: 11px; color: var(--ink2); }
.ends { display: flex; justify-content: space-between; max-width: 440px; font-size: 11px; color: var(--ink2); }
.cell-title { font-size: 18px; font-weight: 700; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font-size: 12.5px; background: var(--chip); border-radius: 999px; padding: 2px 10px; }
.chip.model { background: var(--blue); color: #fff; }
.kpis { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.kpi { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; background: #fff; display: flex; flex-direction: column; gap: 5px; }
.kpi .m { font-size: 12.5px; color: var(--ink2); font-weight: 500; }
.kpi .cat { align-self: flex-start; font-size: 13px; font-weight: 600; border-radius: 4px; padding: 2px 8px; }
.kpi .vals { display: flex; gap: 14px; align-items: baseline; }
.kpi .vals span { display: flex; flex-direction: column; }
.kpi .vals small { font-size: 11px; color: var(--muted); }
.kpi .vals b { font-size: 20px; font-family: "JetBrains Mono", ui-monospace, monospace; }
.nofc { border: 1px dashed #b9b7ae; border-radius: 8px; padding: 12px 14px; font-size: 13px; color: #3d3c38; background: #fff; }
.tslegend { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; font-size: 12px; color: var(--ink2); padding-bottom: 4px; }
.tslegend > span { display: flex; align-items: center; gap: 6px; }
.tslegend .ln { display: block; width: 18px; height: 0; }
.cal { display: grid; grid-template-columns: 110px repeat(8, minmax(0, 1fr)); gap: 2px; font-size: 11.5px; align-items: center; }
.cal .mh { text-align: center; font-size: 11px; color: var(--ink2); }
.cal .bar { display: block; height: 14px; }
footer { font-size: 12px; color: var(--muted); border-top: 1px solid var(--line); padding-top: 10px; }
.banner { padding: 10px 14px; border-radius: 8px; border: 1px solid #cfcdc5; background: #fff; }
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1 id="title"></h1>
  <span class="sub" id="sub"></span>
  <span style="flex:1 1 auto"></span>
  <span class="small" id="author"></span>
</header>
<div class="banner" id="banner" hidden></div>
<div class="card controls">
  <label>Region <select id="region"></select></label>
  <label>Month <select id="lead"></select></label>
  <label>Forecast model <select id="model"></select></label>
  <label class="chk"><input type="checkbox" id="units" checked> HarvestStat units</label>
</div>
<main>
<section class="card">
  <div>
    <h2 id="maptitle"></h2>
    <div class="small" id="mapsub"></div>
  </div>
  <div id="mapbox">
    <canvas id="map" aria-label="Map of cropland grid cells. Click a grid cell to see its NDVI outlook."></canvas>
    <div id="tip"></div>
    <div id="soon"><div style="font-size:15px;font-weight:600">Forecasts coming soon</div>
      <div class="small">This region is being added to the forecast domain</div></div>
  </div>
  <div>
    <div style="font-size:12px;font-weight:600;margin-bottom:4px">NDVI compared with normal (standardized anomaly)</div>
    <div class="legend" id="legend"></div>
    <div class="ends"><span>Less green than normal</span><span>Greener than normal</span></div>
  </div>
  <p class="note">Click a cropland grid cell to see its NDVI outlook · scroll to zoom (HarvestStat unit names show when zoomed in), drag to pan · empty cropland = no forecast from this model for that grid cell · the selection is kept in the page address.</p>
</section>
<section class="card" id="panel">
  <div style="display:flex;flex-direction:column;gap:6px">
    <span class="small">Grid cell</span>
    <span class="cell-title" id="ctitle"></span>
    <span class="small" id="cunit"></span>
    <div class="chips"><span class="chip" id="ccrops"></span><span class="chip" id="cclim"></span><span class="chip model" id="cmodel"></span></div>
  </div>
  <div class="nofc" id="nofc" hidden></div>
  <div class="kpis" id="kpis"></div>
  <div>
    <div class="tslegend">
      <span style="font-weight:600;color:var(--ink)" id="tstitle"></span>
      <span><span class="ln" style="border-top:2.4px solid #141413"></span><span id="obslab"></span></span>
      <span><span class="ln" style="border-top:2.4px solid #2171b5"></span><span id="fclab"></span></span>
      <span><span class="ln" style="border-top:2px dotted #6b6a64"></span>Normal (2003–2025 average)</span>
      <span><span class="ln" style="height:9px;background:#e3e1da"></span>Normal range (5–95th percentile)</span>
    </div>
    <div id="ts"></div>
  </div>
  <div style="display:flex;flex-direction:column;gap:6px">
    <span style="font-size:12px;font-weight:600">Crop calendar (HarvestStats v1.0)</span>
    <div class="cal" id="cal"></div>
    <span class="note" style="font-size:11px">Light = planting · full = growing · pale = harvest to end of season</span>
  </div>
</section>
</main>
<footer id="foot"></footer>
</div>
<script id="payload" type="application/octet-stream">__DATA__</script>
<script>
(async () => {
const $ = id => document.getElementById(id);
if (typeof DecompressionStream === 'undefined') {
  $('banner').hidden = false;
  $('banner').textContent = 'This browser is too old to open the dashboard. Please use a recent Chrome, Edge, Firefox or Safari.';
  return;
}
async function gunzip(b64) {
  const bin = Uint8Array.from(atob(b64.trim()), c => c.charCodeAt(0));
  const ds = new Blob([bin]).stream().pipeThrough(new DecompressionStream('gzip'));
  return await new Response(ds).text();
}
const P = JSON.parse(await gunzip($('payload').textContent));
if (P.sample) { $('banner').hidden = false; $('banner').style.background = '#fdf1cf';
  $('banner').innerHTML = '<b>Synthetic sample.</b> Made-up values and hand-drawn outlines for testing the page only. Build the real page from the data file written by export_dashboard.R.'; }
const C = P.cells, N = C.lon.length, RES = P.res;

/* ---------- colours and words ---------- */
const SAB = [[-Infinity, -2, '#8c510a'], [-2, -1, '#d8b365'], [-1, -0.5, '#f1deb0'], [-0.5, 0.5, '#e7e5df'],
             [0.5, 1, '#b8e0d8'], [1, 2, '#5ab4ac'], [2, Infinity, '#01665e']];
const SAL = ['≤ −2', '−2', '−1', '±0.5', '+1', '+2', '≥ +2'];
const fillSA = v => { for (const b of SAB) if (v >= b[0] && v < b[1]) return b[2]; return SAB[6][2]; };
const cat = v => v <= -1 ? 'Well below normal' : v <= -0.5 ? 'Below normal' : v >= 1 ? 'Well above normal' : v >= 0.5 ? 'Above normal' : 'Near normal';
const tone = v => v <= -0.5 ? ['#7a4708', '#f6ecd6'] : v >= 0.5 ? ['#01594f', '#dcf0ec'] : ['#52514e', '#eeede8'];
const sgn = v => Math.abs(v) < 0.05 ? '0.0' : (v > 0 ? '+' : '−') + Math.abs(v).toFixed(1);
const CROPCOL = { maize: '#d9a15b', millet: '#d65f5f', 'pearl millet': '#d65f5f', 'small millet': '#d65f5f',
  sorghum: '#5b8a4b', wheat: '#a87650', teff: '#8d6cab', bean: '#3f7fa6', cassava: '#9c7a54', rice: '#4f9a94',
  barley: '#b58b3a', groundnut: '#c27c4e', sesame: '#9a8f5b' };
const tint = (hex, f) => { const n = parseInt(hex.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  const t = c => Math.round(255 - (255 - c) * f); return `rgb(${t(r)},${t(g)},${t(b)})`; };
const mon = (ym, o) => new Date(ym + '-01T00:00:00Z').toLocaleString('en', Object.assign({ timeZone: 'UTC' }, o));
const ew = i => `${Math.abs(C.lon[i]).toFixed(2)}°${C.lon[i] < 0 ? 'W' : 'E'}, ${Math.abs(C.lat[i]).toFixed(2)}°${C.lat[i] < 0 ? 'S' : 'N'}`;

/* ---------- static text ---------- */
$('title').textContent = P.title;
$('author').textContent = P.author ? 'Prepared by ' + P.author : '';
$('sub').textContent = `Issued ${P.issued} · initial condition ${P.ic} · outlook ${P.outlook}`;
$('legend').innerHTML = SAB.map((b, k) => `<div><span class="sw" style="background:${b[2]}"></span><span class="lb">${SAL[k]}</span></div>`).join('');
$('foot').textContent = 'Anomaly = how far NDVI is from its 2003–2025 normal for that month, in units of its usual year-to-year spread. ' +
  'Values below −1 mean vegetation is much less green than in a typical year. The outlook is issued early each month from conditions in the previous month.';
$('region').innerHTML = P.regions.map(r => `<option value="${r.id}">${r.label}${r.ok ? '' : ' (coming soon)'}</option>`).join('');
$('lead').innerHTML = P.lead_months.map((m, i) => `<option value="${i}">${mon(m, { month: 'long', year: 'numeric' })}</option>`).join('');
$('model').innerHTML = P.models.map(m => `<option value="${m.id}">${m.label}</option>`).join('');
const M1 = P.months[0], M8 = P.months[7];
$('tstitle').textContent = `NDVI, ${mon(M1, { month: 'long', year: 'numeric' })} – ${mon(M8, { month: 'long', year: 'numeric' })}`;
$('obslab').textContent = `Observed (to ${P.ic_short})`;

/* ---------- grid index for clicks ---------- */
const key = (lon, lat) => Math.round(lon / RES) + ',' + Math.round(lat / RES);
const IDX = new Map(); for (let i = 0; i < N; i++) IDX.set(key(C.lon[i], C.lat[i]), i);
function cellAt(lon, lat) {
  const i = IDX.get(key(lon, lat)); if (i !== undefined) return i;
  return undefined;
}

/* ---------- state (kept in the URL hash) ---------- */
const S = { region: 'full', lead: 0, model: P.default_model, cell: null };
(() => { const h = new URLSearchParams(location.hash.slice(1));
  if (P.regions.some(r => r.id === h.get('region'))) S.region = h.get('region');
  if (['0', '1', '2'].includes(h.get('lead'))) S.lead = +h.get('lead');
  if (P.models.some(m => m.id === h.get('model'))) S.model = h.get('model');
  if (h.get('cell')) { const [lo, la] = h.get('cell').split(',').map(Number); const i = cellAt(lo, la); if (i !== undefined) S.cell = i; }
})();
if (S.cell === null) {   // start on the grid cell with the strongest forecast anomaly of the default model
  const f = C.f[S.model]; let best = -1, bi = 0;
  for (let i = 0; i < N; i++) if (f[i] && f[i][0] !== null && Math.abs(f[i][0]) > best) { best = Math.abs(f[i][0]); bi = i; }
  S.cell = bi;
}
function saveHash() {
  const h = new URLSearchParams({ region: S.region, lead: S.lead, model: S.model, cell: C.lon[S.cell] + ',' + C.lat[S.cell] });
  history.replaceState(null, '', '#' + h.toString());
}
$('region').value = S.region; $('lead').value = S.lead; $('model').value = S.model;

/* ---------- map ---------- */
const cv = $('map'), ctx = cv.getContext('2d');
function pathOf(xs, ys, close) {           // lon/lat path, drawn with a lon/lat -> pixel transform
  const p = new Path2D(); let pen = false;
  for (let k = 0; k < xs.length; k++) {
    if (xs[k] === null || ys[k] === null) { if (pen && close) p.closePath(); pen = false; continue; }
    if (pen) p.lineTo(xs[k], -ys[k]); else { p.moveTo(xs[k], -ys[k]); pen = true; } }
  return p;
}
const U = P.units, NU = U.a0.length;
const OUTLINE = pathOf(P.outline.x, P.outline.y, true), UNITP = pathOf(U.x, U.y, true);
const HAS_OUTLINE = P.outline.x.length > 0;
const CTRY = (() => { const acc = new Map();      // country label = mean of its unit label points
  for (let k = 0; k < NU; k++) { if (!U.a0[k] || U.lx[k] === null) continue;
    const a = acc.get(U.a0[k]) || [0, 0, 0]; a[0] += U.lx[k]; a[1] += U.ly[k]; a[2]++; acc.set(U.a0[k], a); }
  return [...acc].map(([n, a]) => ({ n, x: a[0] / a[2], y: a[1] / a[2] })); })();
let showUnits = true;
let view = null;                      // [lon1, lon2, lat1, lat2] shown
function regionBox() { return P.regions.find(r => r.id === S.region).b.slice(); }
function fitView(b) { view = b; resize(); }
function resize() {
  const w = cv.clientWidth || cv.parentNode.clientWidth;
  const h = Math.round(w * (view[3] - view[2]) / (view[1] - view[0]));
  const d = window.devicePixelRatio || 1;
  cv.style.height = Math.min(h, 820) + 'px';
  cv.width = Math.round(w * d); cv.height = Math.round(Math.min(h, 820) * d);
  if (h > 820) {                         // too tall: widen the view to keep the aspect
    const c = (view[0] + view[1]) / 2, half = (view[3] - view[2]) * w / 820 / 2;
    view = [c - half, c + half, view[2], view[3]];
  }
  draw();
}
function proj() {
  const W = cv.width, H = cv.height, sx = W / (view[1] - view[0]), sy = H / (view[3] - view[2]);
  return { sx, sy, X: lon => (lon - view[0]) * sx, Y: lat => (view[3] - lat) * sy };
}
function draw() {
  const { sx, sy, X, Y } = proj(), d = window.devicePixelRatio || 1;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.fillStyle = '#eef3f7'; ctx.fillRect(0, 0, cv.width, cv.height);
  const geo = () => ctx.setTransform(sx, 0, 0, sy, -view[0] * sx, view[3] * sy);
  const px1 = () => ctx.setTransform(1, 0, 0, 1, 0, 0);
  geo(); ctx.fillStyle = '#f4f3ef'; ctx.fill(HAS_OUTLINE ? OUTLINE : UNITP); px1();
  const reg = P.regions.find(r => r.id === S.region);
  if (reg.ok) {
    const f = C.f[S.model], L = S.lead, w = RES * sx, h = RES * sy, gap = w > 6 ? 0.6 * d : 0;
    for (let i = 0; i < N; i++) {
      const v = f[i] ? f[i][L] : null; if (v === null || v === undefined) continue;
      const lo = C.lon[i], la = C.lat[i];
      if (lo < view[0] - RES || lo > view[1] + RES || la < view[2] - RES || la > view[3] + RES) continue;
      ctx.fillStyle = fillSA(v);
      ctx.fillRect(X(lo - RES / 2) + gap / 2, Y(la + RES / 2) + gap / 2, w - gap, h - gap);
    }
  }
  const width = view[1] - view[0];
  geo();
  if (showUnits && NU) { ctx.strokeStyle = 'rgba(90,89,84,0.55)'; ctx.lineWidth = (width < 15 ? 0.7 : 0.4) * d / sx; ctx.stroke(UNITP); }
  if (HAS_OUTLINE) { ctx.strokeStyle = '#3d3c38'; ctx.lineWidth = 0.9 * d / sx; ctx.stroke(OUTLINE); }
  px1();
  // labels: HarvestStat unit names when zoomed in, country names otherwise
  const taken = [], put = (txt, x, y, font, col) => {
    ctx.font = font; const w = ctx.measureText(txt).width, h = 12 * d, r = [x - w / 2 - 2 * d, y - h / 2, w + 4 * d, h];
    if (x < 0 || y < 0 || x > cv.width || y > cv.height) return;
    if (taken.some(t => r[0] < t[0] + t[2] && t[0] < r[0] + r[2] && r[1] < t[1] + t[3] && t[1] < r[1] + r[3])) return;
    taken.push(r); ctx.lineWidth = 3 * d; ctx.strokeStyle = 'rgba(255,255,255,0.9)'; ctx.strokeText(txt, x, y); ctx.fillStyle = col; ctx.fillText(txt, x, y); };
  ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.lineJoin = 'round';
  if (showUnits && NU && width <= 14) {
    for (let k = 0; k < NU; k++) { const n = U.a2[k] || U.a1[k]; if (!n || U.lx[k] === null) continue;
      put(n, X(U.lx[k]), Y(U.ly[k]), `${11 * d}px system-ui, sans-serif`, '#2b2a27'); }
  } else if (CTRY.length) {
    for (const c of CTRY) put(c.n.toUpperCase(), X(c.x), Y(c.y), `600 ${10 * d}px system-ui, sans-serif`, '#55544f');
  }
  if (reg.ok && S.cell !== null) {
    const i = S.cell, s = Math.max(RES * sx, 7 * d);
    ctx.strokeStyle = '#141413'; ctx.lineWidth = 2.5 * d;
    ctx.strokeRect(X(C.lon[i]) - s / 2 - 2 * d, Y(C.lat[i]) - s / 2 - 2 * d, s + 4 * d, s + 4 * d);
  }
  $('soon').style.display = reg.ok ? 'none' : 'block';
}
function lonlatAt(ev) {
  const r = cv.getBoundingClientRect();
  return [view[0] + (ev.clientX - r.left) / r.width * (view[1] - view[0]), view[3] - (ev.clientY - r.top) / r.height * (view[3] - view[2])];
}
cv.addEventListener('wheel', ev => {
  ev.preventDefault();
  const [lo, la] = lonlatAt(ev), k = ev.deltaY > 0 ? 1.2 : 1 / 1.2;
  const w = (view[1] - view[0]) * k, h = (view[3] - view[2]) * k; if (w < 2 || w > 140) return;
  const fx = (lo - view[0]) / (view[1] - view[0]), fy = (view[3] - la) / (view[3] - view[2]);
  view = [lo - fx * w, lo + (1 - fx) * w, la - (1 - fy) * h, la + fy * h]; draw();
}, { passive: false });
let drag = null;
cv.addEventListener('pointerdown', ev => { drag = { x: ev.clientX, y: ev.clientY, v: view.slice(), moved: false }; cv.setPointerCapture(ev.pointerId); });
cv.addEventListener('pointermove', ev => {
  if (drag) {
    const dx = ev.clientX - drag.x, dy = ev.clientY - drag.y; if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
    if (drag.moved) { const r = cv.getBoundingClientRect(), v = drag.v;
      const ux = dx / r.width * (v[1] - v[0]), uy = dy / r.height * (v[3] - v[2]);
      view = [v[0] - ux, v[1] - ux, v[2] + uy, v[3] + uy]; draw(); }
    $('tip').style.display = 'none'; return;
  }
  const [lo, la] = lonlatAt(ev), i = cellAt(lo, la), tip = $('tip');
  if (i === undefined || !P.regions.find(r => r.id === S.region).ok) { tip.style.display = 'none'; return; }
  const f = C.f[S.model][i], v = f ? f[S.lead] : null, r = $('mapbox').getBoundingClientRect();
  tip.textContent = [C.c[i] || 'Grid cell', C.u1[i], C.u2[i]].filter(Boolean).join(' · ') + ` · ${ew(i)} · ` + (v === null || v === undefined ? 'no forecast' : `anomaly ${sgn(v)}`);
  tip.style.left = (ev.clientX - r.left) + 'px'; tip.style.top = (ev.clientY - r.top) + 'px'; tip.style.display = 'block';
});
cv.addEventListener('pointerleave', () => { $('tip').style.display = 'none'; });
cv.addEventListener('pointerup', ev => {
  const d = drag; drag = null; if (!d || d.moved) return;
  if (!P.regions.find(r => r.id === S.region).ok) return;
  const [lo, la] = lonlatAt(ev), i = cellAt(lo, la);
  if (i !== undefined) { S.cell = i; update(); }
});
window.addEventListener('resize', () => resize());

/* ---------- grid cell panel ---------- */
function chart(i, f) {
  const W = 760, H = 300, ML = 46, MR = 16, MT = 14, MB = 36;
  const X = k => ML + k * (W - ML - MR) / 7;
  const mu = C.mu[i], sd = C.sd[i];
  const lo = mu.map((m, k) => C.p05[i][k] ?? (m === null ? null : m - 1.645 * sd[k]));
  const hi = mu.map((m, k) => C.p95[i][k] ?? (m === null ? null : m + 1.645 * sd[k]));
  const obs = [0, 1, 2].map(k => (C.o[i][k] === null || mu[k] === null) ? null : mu[k] + C.o[i][k] * sd[k]);
  const fv = f ? [0, 1, 2].map(k => (f[k] === null || mu[3 + k] === null) ? null : mu[3 + k] + f[k] * sd[3 + k]) : [];
  const all = [].concat(lo, hi, obs, fv).filter(v => v !== null && v !== undefined);
  if (!all.length) return '<p class="note">No NDVI record for this grid cell.</p>';
  const lo0 = Math.min(...all) - 0.01, hi0 = Math.max(...all) + 0.01;
  const step = (hi0 - lo0) > 0.4 ? 0.1 : (hi0 - lo0) > 0.15 ? 0.05 : 0.02;   // round NDVI ticks
  const y0 = Math.floor(lo0 / step) * step, y1 = Math.ceil(hi0 / step) * step;
  const Y = v => MT + (y1 - v) / (y1 - y0) * (H - MT - MB);
  const line = (ks, vs) => { let s = '', pen = false;
    ks.forEach((k, j) => { const v = vs[j]; if (v === null || v === undefined) { pen = false; return; }
      s += (pen ? 'L' : 'M') + X(k).toFixed(1) + ',' + Y(v).toFixed(1); pen = true; }); return s; };
  const ks = [0, 1, 2, 3, 4, 5, 6, 7];
  let band = '';
  if (lo.every(v => v !== null) && hi.every(v => v !== null))
    band = `<path d="${line(ks, hi)}L${ks.slice().reverse().map(k => X(k).toFixed(1) + ',' + Y(lo[k]).toFixed(1)).join('L')}Z" fill="#e3e1da"/>`;
  let g = '';
  for (let v = y0; v <= y1 + 1e-9; v += step) { const y = Y(v);
    g += `<line x1="${ML}" x2="${W - MR}" y1="${y}" y2="${y}" stroke="#e6e4dd"/><text x="${ML - 6}" y="${y + 4}" font-size="11" text-anchor="end" fill="#6b6a64">${v.toFixed(2)}</text>`; }
  const dots = (ks2, vs, col, r) => ks2.map((k, j) => vs[j] === null || vs[j] === undefined ? '' :
    `<circle cx="${X(k)}" cy="${Y(vs[j])}" r="${r}" fill="${col}" stroke="#fff" stroke-width="1.2"/>`).join('');
  const labs = P.months.map((m, k) => `<text x="${X(k)}" y="${H - MB + 16}" font-size="11" text-anchor="middle" fill="#52514e">${mon(m, { month: 'short' })}</text>`).join('');
  const yr = P.months.map((m, k) => (k === 0 || m.slice(0, 4) !== P.months[k - 1].slice(0, 4)) ?
    `<text x="${X(k)}" y="${H - MB + 30}" font-size="10" text-anchor="middle" fill="#6b6a64">${m.slice(0, 4)}</text>` : '').join('');
  return `<svg viewBox="0 0 ${W} ${H}" style="display:block;width:100%;height:auto" role="img" aria-label="NDVI of this grid cell: observed, forecast and normal">
    ${g}<rect x="${X(2.5)}" y="${MT}" width="${X(5.5) - X(2.5)}" height="${H - MT - MB}" fill="#2171b5" fill-opacity="0.06"/>
    <text x="${X(4)}" y="${MT + 14}" font-size="11" text-anchor="middle" fill="#1d5fa8" font-weight="600">Forecast</text>
    ${band}<path d="${line(ks, mu)}" fill="none" stroke="#6b6a64" stroke-width="1.4" stroke-dasharray="2 3"/>
    <path d="${line([0, 1, 2], obs)}" fill="none" stroke="#141413" stroke-width="2.4"/>${dots([0, 1, 2], obs, '#141413', 3.2)}
    ${f ? `<path d="${line([2, 3, 4, 5], [obs[2]].concat(fv))}" fill="none" stroke="#2171b5" stroke-width="2.4"/>${dots([3, 4, 5], fv, '#2171b5', 4)}` : ''}
    ${labs}${yr}</svg>`;
}
function panel() {
  const i = S.cell, m = P.models.find(x => x.id === S.model), f = C.f[S.model][i];
  $('ctitle').textContent = [C.c[i] || 'Unknown country', C.u1[i], C.u2[i]].filter(Boolean).join(' · ');
  $('cunit').textContent = ew(i);
  $('ccrops').textContent = 'Crops: ' + (C.cr[i] || 'not listed');
  $('cclim').textContent = 'Climate: ' + (C.ai[i] || 'not listed');
  $('cmodel').textContent = m.label;
  $('fclab').textContent = 'Forecast · ' + m.label;
  $('nofc').hidden = !!f; $('nofc').textContent = `${m.label} has no forecast for this grid cell. Pick another model to see one.`;
  $('kpis').hidden = !f;
  $('kpis').innerHTML = f ? P.lead_months.map((lm, k) => {
    const v = f[k], mu = C.mu[i][3 + k], sd = C.sd[i][3 + k];
    if (v === null) return `<div class="kpi"><span class="m">${mon(lm, { month: 'long', year: 'numeric' })}</span><span class="note">No forecast</span></div>`;
    const t = tone(v), nd = (mu === null || sd === null) ? '–' : (mu + v * sd).toFixed(2);
    return `<div class="kpi"><span class="m">${mon(lm, { month: 'long', year: 'numeric' })}</span>
      <span class="cat" style="color:${t[0]};background:${t[1]}">${cat(v)}</span>
      <div class="vals"><span><small>NDVI</small><b>${nd}</b></span><span><small>Anomaly</small><b style="color:${t[0]}">${sgn(v)}</b></span></div></div>`;
  }).join('') : '';
  $('ts').innerHTML = chart(i, f);
  const cal = C.cal[i], crops = Object.keys(cal);
  $('cal').innerHTML = '<span></span>' + P.months.map(mm => `<span class="mh">${mon(mm, { month: 'short' })}</span>`).join('') +
    (crops.length ? crops.map(cr => { const col = CROPCOL[cr] || '#808080';
      return `<span style="font-weight:600;color:${col}">${cr.charAt(0).toUpperCase() + cr.slice(1)}</span>` +
        cal[cr].split('').map(ch => `<span class="bar" style="background:${ch === 'P' ? tint(col, 0.45) : ch === 'G' ? col : ch === 'H' ? tint(col, 0.25) : 'transparent'}"></span>`).join(''); }).join('')
      : '<span class="note" style="grid-column:1 / -1">No crop calendar for this grid cell.</span>');
}
function update() {
  const reg = P.regions.find(r => r.id === S.region), m = P.models.find(x => x.id === S.model);
  $('maptitle').textContent = `NDVI outlook · ${m.label}, ${mon(P.lead_months[S.lead], { month: 'long', year: 'numeric' })}`;
  $('mapsub').textContent = reg.label + (reg.ok ? '' : ' · coming soon') + (m.desc ? ' · ' + m.desc : '');
  draw(); panel(); saveHash();
}
$('region').onchange = e => { S.region = e.target.value; fitView(regionBox()); update(); };
$('lead').onchange = e => { S.lead = +e.target.value; update(); };
$('model').onchange = e => { S.model = e.target.value; update(); };
$('units').onchange = e => { showUnits = e.target.checked; draw(); };
if (!NU) $('units').parentNode.hidden = true;
fitView(regionBox()); update();
})();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
