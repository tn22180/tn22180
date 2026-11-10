"""Turn a background-removed portrait into the card's ASCII art.

Writes two files, because the glyphs are light-on-dark in one theme and
dark-on-light in the other: a bright face has to be dense ink on the dark card
and sparse ink on the light one.

    assets/ascii-art.txt        dark theme  (density follows brightness)
    assets/ascii-art-light.txt  light theme (density follows darkness)

Run locally, not in CI -- the art only changes when the photo does, and keeping
Pillow out of the workflow keeps the daily job to one dependency. The input
needs a transparent background (e.g. `rembg`); transparent pixels become
spaces, so the silhouette stays clean.

    uv run --with pillow python tools/make_ascii.py assets/avatar.png [cols]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
OUT_DARK = ROOT / "assets" / "ascii-art.txt"
OUT_LIGHT = ROOT / "assets" / "ascii-art-light.txt"

RAMP = " .:-=+*#%@"

# Monospace cells are ~0.54 as wide as they are tall at the card's line
# height (build_card.ART_CELL_ASPECT); sampling rows at that ratio keeps the
# face from coming out stretched.
CELL_ASPECT = 0.54


def render(lum: Image.Image, alpha: Image.Image, invert: bool) -> list[str]:
    cols, rows = lum.size
    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            if alpha.getpixel((x, y)) < 128:
                line.append(" ")
                continue
            d = lum.getpixel((x, y)) / 255
            if invert:
                d = 1 - d
            # Never a space inside the subject: black hair or a black shirt
            # would otherwise punch holes in the silhouette.
            line.append(RAMP[1 + min(len(RAMP) - 2, int(d * (len(RAMP) - 1)))])
        lines.append("".join(line).rstrip())
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def main() -> None:
    src = Path(sys.argv[1])
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 64

    img = Image.open(src).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)

    w, h = img.size
    rows = max(1, round(cols * h / w * CELL_ASPECT))
    small = img.resize((cols, rows), Image.LANCZOS)
    alpha = small.getchannel("A")
    # Stretch contrast over the subject only, so the removed background does
    # not drag the histogram.
    lum = ImageOps.autocontrast(small.convert("L"), cutoff=2, mask=alpha.point(lambda a: 255 if a >= 128 else 0))

    for out, invert in ((OUT_DARK, False), (OUT_LIGHT, True)):
        lines = render(lum, alpha, invert)
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT)}: {cols} cols x {len(lines)} rows")


if __name__ == "__main__":
    main()
