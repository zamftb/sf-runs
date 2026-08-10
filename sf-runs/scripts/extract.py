import gpxpy, glob, os, json
from math import radians, sin, cos, sqrt, atan2

try:
    from shapely.geometry import Point, Polygon
except ImportError:
    Point = Polygon = None

# Folder this script lives in is assumed to be a "scripts" subfolder of the
# Garmin Tracks project folder, which itself contains the .gpx files.
folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(folder, "activity_*.gpx")))
print(f"found {len(files)} gpx files")

# Exclusion zones: private property Brad has run near/around (e.g. a gated
# community interior) that should not count toward mileage even though the
# GPS track legitimately passes along the public street bordering it. Each
# entry in excluded_zones.json is {"name": ..., "polygon": [[lat, lon], ...]}.
# Adding a new zone to that file is enough - no code changes needed here.
here = os.path.dirname(os.path.abspath(__file__))
zones_path = os.path.join(here, "excluded_zones.json")
zone_polys = []
if os.path.exists(zones_path):
    with open(zones_path) as zf:
        zones = json.load(zf)
    zone_polys = [Polygon([(lon, lat) for lat, lon in z["polygon"]]) for z in zones]
    print(f"loaded {len(zone_polys)} exclusion zone(s)")


def in_any_zone(lat, lon):
    if not zone_polys:
        return False
    pt = Point(lon, lat)
    return any(poly.contains(pt) for poly in zone_polys)


def haversine_miles(lat1, lon1, lat2, lon2):
    R = 3958.7613  # earth radius in miles
    p1, p2 = radians(lat1), radians(lat2)
    dphi = radians(lat2 - lat1)
    dlambda = radians(lon2 - lon1)
    a = sin(dphi / 2) ** 2 + cos(p1) * cos(p2) * sin(dlambda / 2) ** 2
    return 2 * R * atan2(sqrt(a), sqrt(1 - a))


runs = []
for f in files:
    with open(f, 'r', encoding='utf-8', errors='ignore') as fh:
        try:
            gpx = gpxpy.parse(fh)
        except Exception as e:
            print("PARSE FAIL", f, e)
            continue
    pts = []
    first_time = None
    for track in gpx.tracks:
        for seg in track.segments:
            for p in seg.points:
                pts.append((p.latitude, p.longitude))
                if first_time is None and p.time:
                    first_time = p.time
    if not pts:
        print("NO POINTS", f)
        continue

    has_excluded_point = any(in_any_zone(lat, lon) for lat, lon in pts)
    if has_excluded_point:
        # Split into contiguous segments of points OUTSIDE all exclusion
        # zones and sum each segment's distance separately. A naive filter
        # that just dropped the excluded points and kept summing would
        # create a phantom straight-line "jump" across the gap; splitting
        # avoids that. (Points are kept as-is in the "points" list below so
        # the drawn route on the map is unaffected - only the mileage math
        # changes.)
        valid_segments = []
        current = []
        for lat, lon in pts:
            if in_any_zone(lat, lon):
                if len(current) >= 2:
                    valid_segments.append(current)
                current = []
            else:
                current.append((lat, lon))
        if len(current) >= 2:
            valid_segments.append(current)

        dist_miles = 0.0
        for seg_pts in valid_segments:
            for i in range(len(seg_pts) - 1):
                lat1, lon1 = seg_pts[i]
                lat2, lon2 = seg_pts[i + 1]
                dist_miles += haversine_miles(lat1, lon1, lat2, lon2)
        print(f"  {os.path.basename(f)}: excluded-zone points found, "
              f"recomputed via {len(valid_segments)} segment(s) -> {dist_miles:.2f} mi")
    else:
        # No zone overlap - keep the original whole-track distance exactly
        # as before, so runs unaffected by any exclusion zone don't shift.
        dist_miles = gpx.length_2d() / 1609.344 if gpx.length_2d() else 0

    date_str = first_time.strftime("%Y-%m-%d") if first_time else "unknown"
    runs.append({
        "file": os.path.basename(f),
        "date": date_str,
        "points": pts,
        "miles": dist_miles,
    })

runs.sort(key=lambda r: r["date"])
print("total runs parsed:", len(runs))
print("total raw miles:", sum(r["miles"] for r in runs))
print("date range:", runs[0]["date"], "to", runs[-1]["date"])

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs.json")
with open(out_path, "w") as out:
    json.dump(runs, out)
print("wrote", out_path)
