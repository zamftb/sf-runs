import json, os, colorsys, folium, datetime

here = os.path.dirname(os.path.abspath(__file__))
project_folder = os.path.dirname(here)  # Garmin Tracks folder, one level up

with open(os.path.join(here, "runs.json")) as f:
    runs = json.load(f)

n = len(runs)
all_lats = [lat for r in runs for lat, lon in r["points"]]
all_lons = [lon for r in runs for lat, lon in r["points"]]
center = [sum(all_lats)/len(all_lats), sum(all_lons)/len(all_lons)]

m = folium.Map(location=center, zoom_start=13, control_scale=False, tiles="CartoDB Positron")

# Exclusion zones (private property etc.) - drawn as grey, semi-transparent
# polygons with a tooltip. Loading from excluded_zones.json means adding a
# new zone there is enough to show up on the map; no code changes needed.
# Drawn before the colored run polylines so a track that happens to skirt a
# zone's edge still renders clearly on top of the grey overlay.
zones_path = os.path.join(here, "excluded_zones.json")
if os.path.exists(zones_path):
    with open(zones_path) as f:
        excluded_zones = json.load(f)
else:
    excluded_zones = []

for zone in excluded_zones:
    folium.Polygon(
        locations=zone["polygon"],
        color="#666666",
        weight=1,
        fill=True,
        fill_color="#888888",
        fill_opacity=0.45,
        tooltip=zone.get("name", "Excluded zone"),
    ).add_to(m)

def color_for(i):
    # Hue sweeps 0-270 degrees (red to violet) across runs in date order,
    # skipping the last 90 degrees back to red so the first and last run
    # don't end up as similar-looking colors.
    hue = (i / (n - 1)) * 270 if n > 1 else 0
    rr, gg, bb = colorsys.hsv_to_rgb(hue / 360, 0.653, 0.847)
    return "#{:02x}{:02x}{:02x}".format(int(round(rr*255)), int(round(gg*255)), int(round(bb*255)))

for i, r in enumerate(runs):
    color = color_for(i)
    line = folium.PolyLine(
        r["points"],
        color=color,
        weight=3,
        opacity=0.8,
        # Deliberately no fill/fill_color/fill_opacity here - folium has a
        # quirk where supplying those forces "fill": true even if you pass
        # fill=False, which shows as a translucent polygon filling any
        # loop/out-and-back route. Leaving them out avoids that entirely.
    )
    line.add_to(m)
    line.add_child(folium.Tooltip(f"{r['date']} — San Francisco Running", sticky=True))

m.fit_bounds([[min(all_lats), min(all_lons)], [max(all_lats), max(all_lons)]])

total_miles = sum(r["miles"] for r in runs)

# est_unique_miles / sf_street_miles come from coverage.py's output. Fall
# back to a placeholder if coverage.json isn't there yet (e.g. first-ever
# run before coverage.py has been run once) so this script never hard-fails.
coverage_path = os.path.join(here, "coverage.json")
if os.path.exists(coverage_path):
    with open(coverage_path) as f:
        cov = json.load(f)
    est_unique_miles = cov["est_unique_miles"]
    sf_street_miles = cov["total_sf_street_miles"]
else:
    print("WARNING: coverage.json not found - run coverage.py first. Using placeholder values.")
    est_unique_miles = total_miles
    sf_street_miles = 1071.7

pct = est_unique_miles / sf_street_miles * 100

# Most recent run + a "last updated" timestamp for the legend. `runs` is
# sorted ascending by date (see extract.py), so the last entry is the most
# recent run. The "last updated" date is just today's date wherever this
# script executes - locally, or on GitHub Actions' server when the workflow
# runs - so it reflects whenever the map was last regenerated.
most_recent = runs[-1]
last_updated = datetime.date.today().strftime("%b %d, %Y")

stats_html = (
    f'<div style="position: fixed; top: 20px; right: 20px; z-index:9999; '
    f'background:white; padding:12px 16px; border:1px solid #999; border-radius:6px; '
    f'font-size:13px; width:230px; line-height:1.5;">'
    f'<b>Total SF miles run:</b> {total_miles:.1f} mi<br>'
    f'<b>Unique SF miles run:</b> {est_unique_miles:.1f} mi<br>'
    f'<b>SF street miles:</b> {sf_street_miles:,.1f} mi<br>'
    f'<b>Est. % of SF run:</b> {pct:.1f}%'
    f'<hr style="margin:8px 0; border-color:#ddd;">'
    f'<b>Runs logged:</b> {n}<br>'
    f'<b>Most recent run:</b> {most_recent["date"]} ({most_recent["miles"]:.1f} mi)<br>'
    f'<b>Last updated:</b> {last_updated}</div>'
)
m.get_root().html.add_child(folium.Element(stats_html))

# Live "you are here" marker - client-side browser geolocation, so each
# viewer only ever sees their own current location; nothing is transmitted
# or shared. Finds whichever Leaflet map instance folium created (its
# variable name is randomized each time) rather than hardcoding the id.
geolocation_script = """
<script>
document.addEventListener("DOMContentLoaded", function () {
    var mapObj = window[Object.keys(window).find(k => k.startsWith("map_") && window[k] instanceof L.Map)];
    if (!mapObj || !navigator.geolocation) return;
    var marker = null, circle = null;
    navigator.geolocation.watchPosition(
        function (position) {
            var lat = position.coords.latitude;
            var lng = position.coords.longitude;
            var accuracy = position.coords.accuracy;
            if (!marker) {
                marker = L.circleMarker([lat, lng], {
                    radius: 8, color: "#1a73e8", fillColor: "#1a73e8",
                    fillOpacity: 0.9, weight: 2
                }).addTo(mapObj);
                marker.bindTooltip("You are here");
                circle = L.circle([lat, lng], {
                    radius: accuracy, color: "#1a73e8", fillColor: "#1a73e8",
                    fillOpacity: 0.08, weight: 1
                }).addTo(mapObj);
            } else {
                marker.setLatLng([lat, lng]);
                circle.setLatLng([lat, lng]);
                circle.setRadius(accuracy);
            }
        },
        function (error) { console.warn("Geolocation error:", error.message); },
        { enableHighAccuracy: true, maximumAge: 5000, timeout: 10000 }
    );
});
</script>
"""
m.get_root().html.add_child(folium.Element(geolocation_script))

# "Locate me" button - click it to snap/zoom the map to your current
# location, like the target-arrow button on Google Maps. Separate from the
# live watch-position marker above (that one just shows a dot passively;
# this one recenters the view on demand).
locate_button_html = """
<button id="locateMeBtn" title="Find my location" style="position: fixed; bottom: 30px; right: 20px; z-index:9999; width:44px; height:44px; border-radius:50%; background:white; border:1px solid #999; box-shadow:0 1px 4px rgba(0,0,0,0.3); font-size:20px; cursor:pointer;">📍</button>
<script>
document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("locateMeBtn");
    if (!btn || !navigator.geolocation) return;
    btn.addEventListener("click", function () {
        var mapObj = window[Object.keys(window).find(k => k.startsWith("map_") && window[k] instanceof L.Map)];
        if (!mapObj) return;
        btn.style.opacity = "0.5";
        navigator.geolocation.getCurrentPosition(
            function (position) {
                btn.style.opacity = "1";
                var lat = position.coords.latitude;
                var lng = position.coords.longitude;
                mapObj.setView([lat, lng], 16);
            },
            function (error) {
                btn.style.opacity = "1";
                console.warn("Geolocation error:", error.message);
                alert("Couldn't get your location: " + error.message);
            },
            { enableHighAccuracy: true, timeout: 10000 }
        );
    });
});
</script>
"""
m.get_root().html.add_child(folium.Element(locate_button_html))

overlay_path = os.path.join(project_folder, "runs_overlay_map.html")
m.save(overlay_path)
print(f"saved {overlay_path}. {n} runs, {total_miles:.1f} total miles, {est_unique_miles:.1f} unique miles, {pct:.1f}% coverage")

# GitHub-ready copy with robots meta + title added, so search engines don't
# index it and it has a real page title instead of the folium default.
with open(overlay_path, "r", encoding="utf-8") as f:
    html = f.read()

html = html.replace(
    "<head>",
    '<head>\n   <meta name="robots" content="noindex, nofollow, noarchive">\n   <title>San Francisco Running Log</title>',
    1,
)
index_path = os.path.join(project_folder, "index.html")
with open(index_path, "w", encoding="utf-8") as f:
    f.write(html)
print("saved", index_path)
