import json, os
from shapely.geometry import LineString
from shapely.ops import unary_union, transform
from pyproj import Transformer

# Run extract.py first - this reads runs.json from the same folder as this script.
here = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(here, "runs.json")) as f:
    runs = json.load(f)

# UTM zone 10N - valid for the San Francisco area. If you ever adapt this
# script for a different city, pick the correct UTM zone for that location.
to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32610", always_xy=True).transform

lines = []
for r in runs:
    pts = r["points"]
    if len(pts) < 2:
        continue
    line = LineString([(lon, lat) for lat, lon in pts])
    line_utm = transform(to_utm, line)
    lines.append(line_utm)

print("lines:", len(lines))

# Total SF Public Works-maintained street miles, from DataSF's "Miles of
# Streets" dataset (excludes freeways). Update this if you re-check the source.
TOTAL_SF_STREET_MILES = 1071.7

# Buffer each track by `radius` meters and union all buffers; dividing the
# union's area by (2*radius) estimates the unique street length covered,
# collapsing overlapping/duplicate tracks down to a single count. Checking
# multiple radii is a sanity check that the estimate is stable.
CANONICAL_RADIUS = 10  # the radius whose result gets written to coverage.json

results = {}
for radius in [8, 10, 12, 15]:
    buffers = [ln.buffer(radius, cap_style=2, join_style=2) for ln in lines]
    merged = unary_union(buffers)
    area_m2 = merged.area
    unique_length_m = area_m2 / (2 * radius)
    unique_miles = unique_length_m / 1609.344
    pct = unique_miles / TOTAL_SF_STREET_MILES * 100
    results[radius] = unique_miles
    print(f"radius={radius}m  unique_miles={unique_miles:.1f}  pct={pct:.1f}%")

# Write the canonical-radius result so generate_map.py can pick it up without
# a manual copy-paste step.
out_path = os.path.join(here, "coverage.json")
with open(out_path, "w") as out:
    json.dump({
        "est_unique_miles": results[CANONICAL_RADIUS],
        "radius_m": CANONICAL_RADIUS,
        "total_sf_street_miles": TOTAL_SF_STREET_MILES,
    }, out, indent=2)
print("wrote", out_path)
