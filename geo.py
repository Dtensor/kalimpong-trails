"""Tile helpers: cached XYZ fetch, mosaics, DEM sampling (terrarium)."""
from __future__ import annotations

import io
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import requests
from PIL import Image

ROOT = Path(__file__).parent
CACHE = ROOT / "data" / "tiles"
CENTER = (27.0450, 88.4610)  # Durpin Dara saddle: Morgan House / golf course
RADIUS_KM = 5.0
SAT = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
UA = {"User-Agent": "trail-planner/1.0"}


def ll2xy(lat: float, lon: float, z: int) -> tuple[float, float]:
    n = 2**z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def xy2ll(x: float, y: float, z: int) -> tuple[float, float]:
    n = 2**z
    lon = x / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def tile(kind: str, z: int, x: int, y: int) -> Image.Image:
    ext = "jpg" if kind == "sat" else "png"
    p = CACHE / kind / str(z) / f"{x}_{y}.{ext}"
    if not p.exists():
        url = (SAT if kind == "sat" else DEM).format(z=z, x=x, y=y)
        r = requests.get(url, headers=UA, timeout=30)
        r.raise_for_status()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(r.content)
    return Image.open(io.BytesIO(p.read_bytes())).convert("RGB")


def mosaic(kind: str, z: int, s: float, w: float, n: float, e: float):
    """Return (image, to_px) for bbox; to_px(lat,lon)->pixel in image."""
    x0, y0 = ll2xy(n, w, z)
    x1, y1 = ll2xy(s, e, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    jobs = [(x, y) for x in range(tx0, tx1 + 1) for y in range(ty0, ty1 + 1)]
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(lambda j: tile(kind, z, *j), jobs))
    im = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    for (x, y), t in zip(jobs, ims):
        im.paste(t, ((x - tx0) * 256, (y - ty0) * 256))

    def to_px(lat: float, lon: float) -> tuple[float, float]:
        x, y = ll2xy(lat, lon, z)
        return (x - tx0) * 256, (y - ty0) * 256

    return im, to_px


class Dem:
    def __init__(self, z: int = 14, pad_km: float = 6.5):
        dlat = pad_km / 111.0
        dlon = pad_km / (111.0 * math.cos(math.radians(CENTER[0])))
        self.z = z
        im, self.to_px = mosaic(
            "dem", z, CENTER[0] - dlat, CENTER[1] - dlon, CENTER[0] + dlat, CENTER[1] + dlon
        )
        a = np.asarray(im).astype(np.float64)
        self.h = a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768

    def at(self, lat: float, lon: float) -> float:
        x, y = self.to_px(lat, lon)
        x = min(max(x - 0.5, 0), self.h.shape[1] - 1.001)
        y = min(max(y - 0.5, 0), self.h.shape[0] - 1.001)
        i, j = int(y), int(x)
        fy, fx = y - i, x - j
        h = self.h
        return float(
            h[i, j] * (1 - fy) * (1 - fx) + h[i, j + 1] * (1 - fy) * fx
            + h[i + 1, j] * fy * (1 - fx) + h[i + 1, j + 1] * fy * fx
        )


def hav(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(h))
