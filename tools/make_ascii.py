"""Turn an image into the card's ASCII art (assets/ascii-art.txt).

Run locally, not in CI -- the art only changes when the source image does, and
keeping Pillow out of the workflow keeps the daily job to one dependency.

    uv run --with pillow python tools/make_ascii.py assets/avatar.png [cols]
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "ascii-art.txt"

RAMP = " .:-=+*#%@"

# Monospace cells are ~0.54 as wide as they are tall at the card's line
# height (build_card.ART_CELL_ASPECT); sampling rows at that ratio keeps the
# picture from coming out stretched.
CELL_ASPECT = 0.54


def main() -> None:
    src = Path(sys.argv[1])
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    img = Image.open(src).convert("RGBA")
    bbox = img.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)

    w, h = img.size
    rows = max(1, round(cols * h / w * CELL_ASPECT))
    small = img.resize((cols, rows), Image.LANCZOS)

    lines = []
    for y in range(rows):
        line = []
        for x in range(cols):
            r, g, b, a = small.getpixel((x, y))
            lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
            # Density follows coverage first, brightness second: a logo with a
            # navy end would otherwise vanish where it is darkest.
            d = (a / 255) * (0.45 + 0.55 * lum)
            line.append(RAMP[min(len(RAMP) - 1, int(d * len(RAMP)))])
        lines.append("".join(line).rstrip())

    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {cols} cols x {len(lines)} rows")


if __name__ == "__main__":
    main()
