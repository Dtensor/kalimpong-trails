"""crop.py name s w n e zoom [noosm] -> data/crops/name.jpg with lat/lon grid + OSM overlay."""

import json
import sys
from PIL import ImageDraw
import geo

name, s, w, n, e, z = sys.argv[1], *map(float, sys.argv[2:6]), int(sys.argv[6])
osm = "noosm" not in sys.argv
im, px0 = geo.mosaic("sat", z, s, w, n, e)
x0, y0 = px0(n, w)
x1, y1 = px0(s, e)
im = im.crop((int(x0), int(y0), int(x1), int(y1)))


def px(la, lo):
    return (px0(la, lo)[0] - int(x0), px0(la, lo)[1] - int(y0))


dr = ImageDraw.Draw(im)
if osm:
    col = {
        "path": "#ffee00",
        "footway": "#ffee00",
        "steps": "#ff7700",
        "track": "#00ffff",
    }
    for el in json.load(open(geo.ROOT / "data/osm_raw.json"))["elements"]:
        t = el.get("tags", {})
        if el["type"] == "way" and "highway" in t:
            dr.line(
                [px(p["lat"], p["lon"]) for p in el["geometry"]],
                fill=col.get(t["highway"], "#ffffff"),
                width=2 if t["highway"] in col else 1,
            )
        elif (
            t.get("name")
            and el["type"] == "node"
            and s < el["lat"] < n
            and w < el["lon"] < e
        ):
            x, y = px(el["lat"], el["lon"])
            dr.ellipse([x - 3, y - 3, x + 3, y + 3], fill="#ff0055")
            dr.text((x + 5, y - 5), t["name"][:26], fill="#fff")
step = 0.002 if (n - s) < 0.03 else 0.005
k = int(s / step) + 1
while k * step < n:
    y = px(k * step, w)[1]
    dr.line([(0, y), (im.width, y)], fill="#ff00ff55", width=1)
    dr.text((2, y + 1), f"{k * step:.3f}", fill="#ff66ff")
    k += 1
k = int(w / step) + 1
while k * step < e:
    x = px(s, k * step)[0]
    dr.line([(x, 0), (x, im.height)], fill="#ff00ff", width=1)
    dr.text((x + 2, 2), f"{k * step:.3f}", fill="#ff66ff")
    k += 1
out = geo.ROOT / "data/crops"
out.mkdir(exist_ok=True)
im.save(out / f"{name}.jpg", quality=88)
print(out / f"{name}.jpg", im.size)
