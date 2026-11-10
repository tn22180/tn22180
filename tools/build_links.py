"""Render the three link buttons under the card: link_<name>_<theme>.svg.

The README lays them out at width="33.3%" each, so every button shares one
viewBox and scales together with the card above it.

    python tools/build_links.py
"""

from __future__ import annotations

from pathlib import Path

from palette import THEMES

ROOT = Path(__file__).resolve().parent.parent

W, H = 330, 52

# 20x20 pixel-ish icons, drawn with strokes in the button's accent colour.
ICONS = {
    # monitor
    "avada": '<rect x="1" y="2" width="18" height="12" rx="1.5" fill="none" stroke-width="2"/>'
             '<path d="M7 18h6M10 14v4" fill="none" stroke-width="2"/>'
             '<path d="M5 6l3 2-3 2M10 10h4" fill="none" stroke-width="1.6"/>',
    # shopping bag
    "shopify": '<path d="M3 6h14l-1.2 12H4.2z" fill="none" stroke-width="2" stroke-linejoin="round"/>'
               '<path d="M7 8V5a3 3 0 0 1 6 0v3" fill="none" stroke-width="2"/>',
    # envelope
    "email": '<rect x="1" y="3" width="18" height="14" rx="1.5" fill="none" stroke-width="2"/>'
             '<path d="M2 4l8 7 8-7" fill="none" stroke-width="2" stroke-linejoin="round"/>',
}

LINKS = [("avada", "AVADA"), ("shopify", "SHOPIFY APPS"), ("email", "EMAIL")]


def build(theme: str, idx: int, icon: str, label: str) -> str:
    c = THEMES[theme]
    accent = c["link"][idx]
    font = 15
    # Icon (20px) + 12px gap + label, centred as one block.
    text_w = len(label) * font * 0.6
    block = 20 + 12 + text_w
    x0 = (W - block) / 2
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}"
     font-family="Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace">
<rect x="3" y="1" width="{W - 6}" height="{H - 2}" rx="4" fill="{c['bg']}" stroke="{c['border']}" stroke-width="1.5"/>
<rect x="3" y="{H - 4}" width="{W - 6}" height="3" rx="1.5" fill="{accent}"/>
<g transform="translate({x0:.1f} {(H - 20) / 2 - 1:.1f})" stroke="{accent}" stroke-linecap="round">{ICONS[icon]}</g>
<text x="{x0 + 32:.1f}" y="{H / 2 + font * 0.32:.1f}" font-size="{font}px" letter-spacing="1" fill="{c['fg']}">{label}</text>
</svg>
"""


def main() -> None:
    for theme in THEMES:
        for i, (icon, label) in enumerate(LINKS):
            out = ROOT / f"link_{icon}_{theme}.svg"
            out.write_text(build(theme, i, icon, label), encoding="utf-8")
    print(f"wrote {len(THEMES) * len(LINKS)} link buttons")


if __name__ == "__main__":
    main()
