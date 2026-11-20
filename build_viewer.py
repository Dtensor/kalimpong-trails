"""Inline MapLibre + trail data into one self-contained kalimpong-trails.html."""

from pathlib import Path

ROOT = Path(__file__).parent


def safe(text: str) -> str:
    return text.replace("</script", "<\\/script")


def main() -> None:
    html = (ROOT / "viewer_template.html").read_text()
    parts = {
        "/*__MAPLIBRE_CSS__*/": (ROOT / "vendor/maplibre-gl.css").read_text(),
        "/*__MAPLIBRE_JS__*/": safe((ROOT / "vendor/maplibre-gl.js").read_text()),
        "__DATA_JSON__": safe((ROOT / "data/trails.json").read_text()),
    }
    for key, value in parts.items():
        if html.count(key) != 1:
            raise SystemExit(
                f"placeholder {key} found {html.count(key)} times, expected 1"
            )
        html = html.replace(key, value)
    out = ROOT / "kalimpong-trails.html"
    out.write_text(html)
    (ROOT / "index.html").write_text(html)  # same page, served by GitHub Pages
    print(out.resolve(), f"{out.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
