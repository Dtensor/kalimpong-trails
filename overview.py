"""Overview: satellite z15 + OSM ways coloured by class + POIs + 5 km ring."""

import json
import math
import sys
from PIL import ImageDraw
import geo

z = int(sys.argv[1]) if len(sys.argv) > 1 else 15
d = 5.6 / 111.0
dl = 5.6 / (111.0 * math.cos(math.radians(geo.CENTER[0])))
im, px = geo.mosaic(
    "sat",
    z,
    geo.CENTER[0] - d,
    geo.CENTER[1] - dl,
    geo.CENTER[0] + d,
    geo.CENTER[1] + dl,
)
dr = ImageDraw.Draw(im)
els = json.load(open(geo.ROOT / "data/osm_raw.json"))["elements"]
col = {"path": "#ffee00", "footway": "#ffee00", "steps": "#ff7700", "track": "#00ffff"}
for e in els:
    t = e.get("tags", {})
    if e["type"] == "way" and "highway" in t:
        c = col.get(t["highway"], "#ffffff")
        w = 3 if t["highway"] in col else 1
        dr.line([px(p["lat"], p["lon"]) for p in e["geometry"]], fill=c, width=w)
ring = [
    (
        geo.CENTER[0] + 5 / 111.0 * math.cos(a / 50 * math.pi),
        geo.CENTER[1]
        + 5 / (111.0 * math.cos(math.radians(27.045))) * math.sin(a / 50 * math.pi),
    )
    for a in range(101)
]
dr.line([px(*p) for p in ring], fill="#ff00ff", width=2)
for e in els:
    t = e.get("tags", {})
    if t.get("name") and "highway" not in t and e["type"] == "node":
        x, y = px(e["lat"], e["lon"])
        dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill="#ff0055")
        dr.text((x + 6, y - 6), t["name"][:28], fill="#ffffff")
out = geo.ROOT / f"data/overview_z{z}.jpg"
im.save(out, quality=85)
print(out, im.size)
