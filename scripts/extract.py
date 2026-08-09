import gpxpy, glob, os, json

# Folder this script lives in is assumed to be a "scripts" subfolder of the
# Garmin Tracks project folder, which itself contains the .gpx files.
folder = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(folder, "activity_*.gpx")))
print(f"found {len(files)} gpx files")

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
