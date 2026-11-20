# Durpin Dara Nature Walks (Kalimpong)

**Live map:** https://dtensor.github.io/kalimpong-trails/

**Comments wanted.** Walked one of these? Know a path that is missing, closed or wrong? [Open a comment](https://github.com/Dtensor/kalimpong-trails/issues/new/choose) and name the trail (T01 to T13).

## What we built

A set of 13 walking circuits within 5 km of Div Chowk (the Durpin roundabout) in Kalimpong, drawn on satellite imagery draped over real 3D terrain. Open one file in a browser and you can look at every trail, read its story, see its climb profile, fly over it from the air, or glide along it at head height.

Every stretch of every trail is honest about how sure we are:

| Line style | Meaning |
|---|---|
| Solid | A path or road already mapped in OpenStreetMap |
| Dotted | Not on any map, but visible to the eye on satellite imagery (good to about 20 m) |
| Dashed | Scout line. The computer worked out the easiest walkable line from the shape of the hill. Nobody has walked it yet. |

## How I use it manually

```bash
open kalimpong-trails.html
```
Click a trail card, then **Aerial fly-through** or **Walk-through**. **Tour all trails** flies the lot. **Download GPX** gives a file for a phone or GPS watch. The page needs internet for the satellite and terrain tiles.

Links that jump straight to a view: `kalimpong-trails.html#t=T03` selects a trail, `#t=T03&mode=walk&p=0.45` parks the walk-through camera 45 percent of the way along.

## Changing the trails

1. Edit `trails_def.py`. Move a pin, add a stop, or change a trail's list of legs. Div Chowk, the start of every walk, is the `chowk` pin at 27.04266, 88.46075.
2. `python3.11 design.py` re-routes everything and prints one line per trail (length, climb, hours, grade, percent mapped / seen / scout). Any `WARN` means a leg did not join up.
3. `python3.11 build_viewer.py` rebuilds the single HTML file.
4. `python3.11 qa.py /tmp/qa "sel=t=T03" "play=t=T02"` opens it in headless Chrome, clicks through a playback and saves screenshots.

To look at any patch of ground before drawing a line: `python3.11 crop.py NAME south west north east ZOOM` writes a gridded satellite picture to `data/crops/`, and `python3.11 render.py NAME south west north east ZOOM T03,T04` draws the trails on it.

## Commands

| Command | What it does | When I use it |
|---|---|---|
| `python3.11 design.py` | Routes all trails, writes `data/trails.json` and `gpx/T01..T13.gpx` | After any edit to `trails_def.py` |
| `python3.11 build_viewer.py` | Packs map engine + data into `kalimpong-trails.html` | After design.py |
| `python3.11 qa.py <dir> name=hash ...` | Headless check and screenshots | Before sharing |
| `python3.11 crop.py ...` | Gridded satellite crop with OSM overlay | Reading the ground for new lines |
| `python3.11 render.py ...` | Trails drawn on a satellite crop | Checking a line sits where intended |

## Where things live

- Viewer: `kalimpong-trails.html` (single file, 1.4 MB)
- GPX: `gpx/`
- Trail recipes: `trails_def.py`. Router: `design.py`. Tiles and elevation helper: `geo.py`
- Raw OpenStreetMap pull (20 Nov 2026, 6.5 km radius): `data/osm_raw.json`

## Honest limits

- Trails pass close to army land (golf course, cantonment roads). Follow signs and local instructions; a line on this map is not permission to enter.
- Scout lines come from a 30 m elevation model. They show where a trail could go, not where one is. Walk each one with a GPS before guests do.
- The walk-through is satellite imagery on terrain, so close-up ground is blurry. It is not street-level photography. Each stop has a Street View link that works only where Google has coverage.
- Data: OpenStreetMap contributors (ODbL), Esri World Imagery, AWS Terrain Tiles (SRTM).
