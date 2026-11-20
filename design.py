"""Trail designer: routes circuits over the OSM network, hand-read imagery lines
and terrain-computed scout lines, then writes data/trails.json + GPX files.

Leg kinds
  osm   - shortest walk over mapped OSM ways (confidence: mapped)
  img   - polyline read off satellite imagery by eye (confidence: seen, +-20 m)
  scout - least-effort line over the elevation model (confidence: must be walked)
"""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

import geo
from trails_def import HUBS, POIS, TRAILS

ROOT = Path(__file__).parent
DEM = geo.Dem()
CLASS_COST = {
    "trunk": 2.5, "primary": 2.0, "secondary": 1.5, "tertiary": 1.1,
    "path": 0.7, "footway": 0.7, "steps": 0.8, "track": 0.75, "pedestrian": 0.8,
}
FOOT = {"path", "footway", "steps", "track", "pedestrian"}


# ---------------------------------------------------------------- OSM graph
def build_graph():
    adj: dict[tuple, list] = {}
    for el in json.loads((ROOT / "data/osm_raw.json").read_text())["elements"]:
        t = el.get("tags", {})
        hw = t.get("highway")
        if el["type"] != "way" or not hw or hw == "construction":
            continue
        pts = [(round(p["lat"], 7), round(p["lon"], 7)) for p in el["geometry"]]
        for a, b in zip(pts, pts[1:]):
            d = geo.hav(a, b)
            adj.setdefault(a, []).append((b, d, hw))
            adj.setdefault(b, []).append((a, d, hw))
    # keep the largest connected component so snapping never lands on an island
    seen: dict[tuple, int] = {}
    comps = []
    for n in adj:
        if n in seen:
            continue
        stack, comp = [n], []
        seen[n] = len(comps)
        while stack:
            u = stack.pop()
            comp.append(u)
            for v, _, _ in adj[u]:
                if v not in seen:
                    seen[v] = len(comps)
                    stack.append(v)
        comps.append(comp)
    big = max(comps, key=len)
    keep = set(big)
    return {n: e for n, e in adj.items() if n in keep}, len(adj), len(big)


GRAPH, N_ALL, N_BIG = build_graph()
NODES = list(GRAPH)


def snap(p):
    n = min(NODES, key=lambda q: (q[0] - p[0]) ** 2 + ((q[1] - p[1]) * 0.89) ** 2)
    return n, geo.hav(p, n) * 1000


def route_osm(a, b, used):
    s, ds = snap(a)
    t, dt = snap(b)
    dist = {s: 0.0}
    prev: dict = {}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w, hw in GRAPH[u]:
            c = w * CLASS_COST.get(hw, 1.0)
            if (u, v) in used or (v, u) in used:
                c *= 3.0  # discourage walking the same stretch twice in one circuit
            nd = d + c
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = (u, hw)
                heapq.heappush(pq, (nd, v))
    if t not in prev and t != s:
        raise RuntimeError(f"no OSM route {a} -> {b}")
    path, kinds = [t], []
    while path[-1] != s:
        u, hw = prev[path[-1]]
        kinds.append(hw)
        path.append(u)
    path.reverse()
    kinds.reverse()
    for u, v in zip(path, path[1:]):
        used.add((u, v))
    foot_km = sum(geo.hav(u, v) for (u, v), k in zip(zip(path, path[1:]), kinds) if k in FOOT)
    return [list(p) for p in path], max(ds, dt), foot_km


# ------------------------------------------------------------- scout router
STEP = 2  # DEM pixels per grid cell (~17 m, matches the 30 m SRTM source)
MOVES = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1),
         (-2, -1), (-2, 1), (2, -1), (2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2)]


def route_scout(a, b, band=False):
    """Least-time line on the DEM using Tobler's hiking function, with a steep
    penalty above ~30 % grade so the line switchbacks instead of plunging."""
    ax, ay = DEM.to_px(*a)
    bx, by = DEM.to_px(*b)
    s = (int(ay / STEP), int(ax / STEP))
    t = (int(by / STEP), int(bx / STEP))
    cell_m = 156543.03 * math.cos(math.radians(geo.CENTER[0])) / 2**DEM.z * STEP
    pad = 25
    lo_i, hi_i = min(s[0], t[0]) - pad, max(s[0], t[0]) + pad
    lo_j, hi_j = min(s[1], t[1]) - pad, max(s[1], t[1]) + pad
    H = DEM.h

    def h(c):
        return H[c[0] * STEP, c[1] * STEP]

    def step_cost(u, v):
        run = math.hypot(v[0] - u[0], v[1] - u[1]) * cell_m
        g = (h(v) - h(u)) / run
        speed = 6.0 * math.exp(-3.5 * abs(g + 0.05))  # km/h
        cost = run / speed * (1 + (abs(g) / 0.30) ** 4)
        if band:  # balcony mode: hold the straight-line gradient between the ends
            f = ((v[0] - s[0]) * (t[0] - s[0]) + (v[1] - s[1]) * (t[1] - s[1])) / span2
            target = hs + min(1.0, max(0.0, f)) * (ht - hs)
            cost *= 1 + ((h(v) - target) / 25.0) ** 2
        return cost

    span2 = max(1, (t[0] - s[0]) ** 2 + (t[1] - s[1]) ** 2)
    hs, ht = h(s), h(t)

    dist = {s: 0.0}
    prev: dict = {}
    pq = [(0.0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist[u]:
            continue
        for di, dj in MOVES:
            v = (u[0] + di, u[1] + dj)
            if not (lo_i <= v[0] <= hi_i and lo_j <= v[1] <= hi_j):
                continue
            nd = d + step_cost(u, v)
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    cells = [t]
    while cells[-1] != s:
        cells.append(prev[cells[-1]])
    cells.reverse()
    x0, y0 = geo.ll2xy(*a, DEM.z)
    off_x, off_y = x0 * 256 - ax, y0 * 256 - ay  # mosaic origin in world pixels
    pts = [list(a)]
    for c in cells[1:-1]:
        wx = (c[1] * STEP + STEP / 2 + off_x) / 256
        wy = (c[0] * STEP + STEP / 2 + off_y) / 256
        pts.append(list(geo.xy2ll(wx, wy, DEM.z)))
    pts.append(list(b))
    # light smoothing: SRTM cells are blocky, a walker is not
    for _ in range(2):
        pts = [pts[0]] + [
            [(p[0] + 2 * q[0] + r[0]) / 4, (p[1] + 2 * q[1] + r[1]) / 4]
            for p, q, r in zip(pts, pts[1:], pts[2:])
        ] + [pts[-1]]
    return pts


# ------------------------------------------------------------------ helpers
def densify(pts, step_m=12.0):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(geo.hav(a, b) * 1000 / step_m))
        out += [[a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n] for k in range(1, n + 1)]
    return out


def smooth(v, k=4):
    return [sum(v[max(0, i - k): i + k + 1]) / len(v[max(0, i - k): i + k + 1]) for i in range(len(v))]


def stats(pts, scout_mult):
    el = smooth([DEM.at(*p) for p in pts])
    km = up = down = hours = 0.0
    ref = el[0]
    for i in range(1, len(pts)):
        d = geo.hav(pts[i - 1], pts[i])
        km += d
        if d > 0:
            g = (el[i] - el[i - 1]) / (d * 1000)
            hours += d / (6.0 * math.exp(-3.5 * abs(g + 0.05))) * scout_mult[i]
        if el[i] - ref > 3:
            up += el[i] - ref
            ref = el[i]
        elif ref - el[i] > 3:
            down += ref - el[i]
            ref = el[i]
    return km, up, down, hours, el


def grade(km, up, down, scout_share):
    score = km + (up + 0.5 * down) / 100 + scout_share * 3
    return "Easy" if score < 6 else "Moderate" if score < 12 else "Strenuous" if score < 18 else "Expedition"


def gpx(tr):
    seg = "".join(
        f'<trkpt lat="{p[0]:.6f}" lon="{p[1]:.6f}"><ele>{p[2]:.0f}</ele></trkpt>'
        for leg in tr["legs"] for p in leg["pts"]
    )
    wps = "".join(f'<wpt lat="{w["lat"]:.6f}" lon="{w["lon"]:.6f}"><name>{w["name"]}</name></wpt>' for w in tr["stops"])
    return (
        '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="kalimpong-trails" '
        f'xmlns="http://www.topografix.com/GPX/1/1">{wps}<trk><name>{tr["name"]}</name><trkseg>{seg}</trkseg></trk></gpx>'
    )


def where(ref):
    if isinstance(ref, str):
        src = HUBS.get(ref) or POIS[ref]
        return (src["lat"], src["lon"])
    return tuple(ref)


# --------------------------------------------------------------------- main
def main():
    out, report = [], []
    (ROOT / "gpx").mkdir(exist_ok=True)
    for n, td in enumerate(TRAILS, 1):
        used: set = set()
        legs, warn, legkm = [], [], []
        for kind, *arg in td["legs"]:
            if kind == "osm":
                pts, snap_m, _ = route_osm(where(arg[0]), where(arg[1]), used)
                if snap_m > 90:
                    warn.append(f"osm snap {snap_m:.0f} m at {arg}")
            elif kind == "scout":
                pts = route_scout(where(arg[0]), where(arg[1]), band=len(arg) > 2)
            else:  # img
                pts = [list(where(p)) for p in arg[0]]
            legs.append({"kind": kind, "pts": densify(pts)})
            legkm.append(f"{kind[0]}{sum(geo.hav(a, b) for a, b in zip(pts, pts[1:])):.1f}")
        # stitch small gaps between consecutive legs so the track is continuous
        for a, b in zip(legs, legs[1:]):
            gap = geo.hav(a["pts"][-1], b["pts"][0]) * 1000
            if gap > 120:
                warn.append(f"gap {gap:.0f} m between {a['kind']} and {b['kind']} leg")
            b["pts"].insert(0, a["pts"][-1])
        allp = [p for leg in legs for p in leg["pts"]]
        mult = [1.5 if leg["kind"] == "scout" else 1.2 if leg["kind"] == "img" else 1.0 for leg in legs for _ in leg["pts"]]
        km, up, down, hours, el = stats(allp, mult)
        i = 0
        share = {"osm": 0.0, "img": 0.0, "scout": 0.0}
        for leg in legs:
            k = len(leg["pts"])
            share[leg["kind"]] += sum(geo.hav(a, b) for a, b in zip(leg["pts"], leg["pts"][1:]))
            leg["pts"] = [[round(p[0], 6), round(p[1], 6), round(e, 1)] for p, e in zip(leg["pts"], el[i: i + k])]
            i += k
        far = max(geo.hav(geo.CENTER, p) for p in allp)
        stops = [{"name": (HUBS.get(s) or POIS[s])["name"], "lat": where(s)[0], "lon": where(s)[1],
                  "elev": round(DEM.at(*where(s)))} for s in td["stops"]]
        tr = {
            "id": f"T{n:02d}", "name": td["name"], "color": td["color"], "theme": td["theme"],
            "shape": td["shape"], "story": td["story"], "highlights": td["highlights"],
            "caution": td["caution"], "best": td["best"],
            "km": round(km, 2), "up": round(up), "down": round(down),
            "min": round(min(el)), "max": round(max(el)),
            "hours": round(hours + 0.25 * len(stops) * 0.5, 1),
            "grade": td.get("grade") or grade(km, up, down, share["scout"] / km),
            "share": {k: round(v / km * 100) for k, v in share.items()},
            "far_km": round(far, 2), "stops": stops, "legs": legs,
        }
        (ROOT / "gpx" / f"{tr['id']}.gpx").write_text(gpx(tr))
        out.append(tr)
        report.append(
            f"{tr['id']} {tr['name'][:34]:34s} {tr['km']:5.2f} km +{tr['up']:4d}/-{tr['down']:4d} m "
            f"{tr['min']}-{tr['max']} m {tr['hours']:4.1f} h {tr['grade']:10s} "
            f"mapped {tr['share']['osm']:3d}% seen {tr['share']['img']:3d}% scout {tr['share']['scout']:3d}% "
            f"far {tr['far_km']:.1f} km [{' '.join(legkm)}] {'WARN ' + '; '.join(warn) if warn else ''}"
        )
    pois = [{"id": k, **v, "elev": round(DEM.at(v["lat"], v["lon"]))} for k, v in {**HUBS, **POIS}.items()]
    data = {"center": list(geo.CENTER), "radius_km": geo.RADIUS_KM, "trails": out, "pois": pois}
    (ROOT / "data/trails.json").write_text(json.dumps(data, separators=(",", ":")))
    print(f"graph: {N_BIG}/{N_ALL} nodes in main component")
    print("\n".join(report))


if __name__ == "__main__":
    main()
