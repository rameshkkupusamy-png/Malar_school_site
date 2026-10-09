"""Build the home-screen icons from the school crest.

    python scripts/make_icons.py [path/to/crest.png]

Writes portal/static/portal/icon-192.png, icon-512.png and icon-maskable-512.png: the crest
centred on white. The maskable icon keeps the crest inside the middle 60 % so phones that cut
icons into circles or rounded squares don't clip it. Run it again with a larger crest image
for sharper icons.
"""

import sys
from pathlib import Path

from PIL import Image

STATIC = Path(__file__).resolve().parent.parent / "portal" / "static" / "portal"


def icon(crest: Image.Image, size: int, fill: float) -> Image.Image:
    """The crest scaled to `fill` of the icon's height, centred on white."""
    canvas = Image.new("RGB", (size, size), "white")
    scale = size * fill / max(crest.size)
    width, height = round(crest.width * scale), round(crest.height * scale)
    resized = crest.resize((width, height), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((size - width) // 2, (size - height) // 2), resized)
    return canvas


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else STATIC / "crest.png"
    crest = Image.open(source).convert("RGBA")
    icon(crest, 192, 0.86).save(STATIC / "icon-192.png", optimize=True)
    icon(crest, 512, 0.86).save(STATIC / "icon-512.png", optimize=True)
    icon(crest, 512, 0.6).save(STATIC / "icon-maskable-512.png", optimize=True)
    print(f"Icons written to {STATIC}")


if __name__ == "__main__":
    main()
