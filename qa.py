"""qa.py <outdir> name=hash[@WxH] ... : real-time headless Chrome checks + screenshots."""

import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
url = (Path(__file__).parent / "kalimpong-trails.html").resolve().as_uri()
with sync_playwright() as pw:
    br = pw.chromium.launch(
        channel="chrome", headless=True, args=["--use-angle=metal", "--enable-gpu"]
    )
    for spec in sys.argv[2:]:
        name, rest = spec.split("=", 1)
        frag, _, size = rest.partition("@")
        w, h = map(int, (size or "1600x1000").split("x"))
        pg = br.new_page(viewport={"width": w, "height": h})
        logs = []
        pg.on("console", lambda m: logs.append(m.text) if m.type == "error" else None)
        pg.goto(url + ("#" + frag if frag else ""))
        try:
            pg.wait_for_function(
                "window.__state && window.__state().layers > 3", timeout=30000
            )
            pg.wait_for_function("map.loaded() && map.areTilesLoaded()", timeout=30000)
        except Exception as e:
            logs.append("WAIT: " + str(e)[:120])
        pg.wait_for_timeout(7000)
        try:
            pg.wait_for_function("map.areTilesLoaded()", timeout=20000)
        except Exception:
            pass
        pg.wait_for_timeout(1500)
        st = pg.evaluate("""() => ({...window.__state(), errs: __ERRS, rendered: map.getLayer('leg-osm') ? map.queryRenderedFeatures({layers:['leg-osm','leg-scout','leg-img']}).length : -1,
            center: map.getCenter().toArray().map(v => +v.toFixed(5)), elev: map.transform.elevation, cam: S.cam, tgt: S.tgt})""")
        if name.startswith(
            "play"
        ):  # click through a real playback and confirm it advances and ends
            pg.select_option(".card.sel select", "4")
            pg.click(
                '.card.sel [data-a="%s"]' % ("walk" if "walk" in name else "aerial")
            )
            pg.wait_for_function(
                "window.__state().playing && window.__state().progress > 0.05",
                timeout=30000,
            )
            mid = pg.evaluate("window.__state()")
            pg.screenshot(path=str(out / f"{name}_mid.png"))
            pg.wait_for_function("!window.__state().mode", timeout=120000)
            pg.wait_for_timeout(2500)
            st = {
                "mid_progress": round(mid["progress"], 3),
                "mid_pitch": round(mid["pitch"]),
                "end": pg.evaluate("window.__state()"),
                "errs": pg.evaluate("__ERRS"),
            }
            with pg.expect_download() as dl:
                pg.click('.card.sel [data-a="gpx"]')
            f = out / dl.value.suggested_filename
            dl.value.save_as(str(f))
            st["gpx"] = [f.name, f.stat().st_size, f.read_text().count("<trkpt")]
            pg.click("#chips button:nth-child(2)")
            st["easy_cards"] = pg.locator(".card").count()
        pg.screenshot(path=str(out / f"{name}.png"))
        print(name, json.dumps(st)[:700], "| console:", logs[:3])
        pg.close()
    br.close()
