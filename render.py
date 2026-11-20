"""render.py name s w n e zoom [ids,...] -> trails drawn on satellite for checking."""

import json
import sys
from PIL import ImageDraw
import geo

name, s, w, n, e, z = sys.argv[1], *map(float, sys.argv[2:6]), int(sys.argv[6])
only = sys.argv[7].split(",") if len(sys.argv) > 7 else None
d = json.load(open(geo.ROOT / "data/trails.json"))
im, px0 = geo.mosaic("sat", z, s, w, n, e)
x0, y0 = px0(n, w)
x1, y1 = px0(s, e)
im = im.crop((int(x0), int(y0), int(x1), int(y1)))


def px(la, lo):
    return (px0(la, lo)[0] - int(x0), px0(la, lo)[1] - int(y0))


dr = ImageDraw.Draw(im)
for i, t in enumerate(d["trails"]):
    if only and t["id"] not in only:
        continue
    for leg in t["legs"]:
        pts = [px(p[0], p[1]) for p in leg["pts"]]
        if leg["kind"] == "osm":
            dr.line(pts, fill=t["color"], width=4)
        else:
            for k in range(0, len(pts) - 1, 2 if leg["kind"] == "scout" else 1):
                dr.line(
                    pts[k : k + 2],
                    fill=t["color"] if leg["kind"] == "scout" else "#ff0000",
                    width=4,
                )
    x, y = px(*t["legs"][0]["pts"][len(t["legs"][0]["pts"]) // 2][:2])
    dr.text((x + 5, y), t["id"], fill="#fff")
for p in d["pois"]:
    x, y = px(p["lat"], p["lon"])
    dr.ellipse([x - 4, y - 4, x + 4, y + 4], fill="#fff", outline="#000")
    dr.text((x + 6, y - 5), p["id"], fill="#fff", stroke_width=2, stroke_fill="#000")
out = geo.ROOT / "data/crops" / f"r_{name}.jpg"
im.save(out, quality=88)
print(out, im.size)
