# Map generation scripts

Regenerates `runs_overlay_map.html` and `index.html` in the parent (repo root)
folder from all `activity_*.gpx` files sitting in that same parent folder.

## Automatic (GitHub Actions)

Once this whole folder structure is uploaded to the `sf-runs` GitHub repo
(including the `.github/workflows/build-map.yml` file), pushing a new
`activity_*.gpx` file to the repo automatically re-runs everything below and
commits the updated `index.html` back. No local setup needed for day-to-day
use - see the top-level setup instructions for the one-time upload steps.

## Manual (local)

Run in this order, from inside this `scripts` folder:

```
pip install gpxpy folium shapely pyproj --break-system-packages
python3 extract.py     # parses all GPX files -> runs.json
python3 coverage.py    # estimates unique street-mile coverage -> coverage.json
python3 generate_map.py   # builds runs_overlay_map.html + index.html
```

Notes:

- `extract.py` writes `runs.json` into this `scripts` folder - a cache of parsed
  points/dates/distances so you don't have to re-parse every GPX file each time.
- `coverage.py` reads `runs.json` and estimates how many *unique* miles of SF
  street you've covered (buffers and unions all tracks so overlapping/repeated
  routes aren't double-counted), checked against DataSF's total of 1,071.7
  Public Works-maintained street miles (excludes freeways). Writes the result
  to `coverage.json` in this folder.
- `generate_map.py` reads `runs.json` and `coverage.json`, builds the map
  (CartoDB Positron basemap, one distinctly colored line per run, a stats box,
  a client-side "you are here" live location marker, and a "locate me" button
  that zooms to your current location), and writes both html files into the
  parent folder. `index.html` is a copy with a `noindex` robots meta tag and
  page title added, meant for GitHub Pages; `runs_overlay_map.html` is the
  plain working copy.
