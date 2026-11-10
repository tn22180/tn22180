"""Render the contribution board with Pac-Man eating it: pacman_<theme>.svg.

Pac-Man snakes down one week column and up the next, so every step is the
same 17px and a single linear animateMotion keeps him in lock-step with the
per-cell timings below. Each lit cell blanks out at the instant he reaches it,
and the counter in the header adds that day's contributions as he eats.
Everything is SMIL, so it animates inside GitHub's <img> sandbox, where CSS
and scripts are stripped.

    python tools/build_pacman.py
"""

from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path

from palette import THEMES

ROOT = Path(__file__).resolve().parent.parent
CAL = ROOT / "cache" / "calendar.json"

CELL, STEP = 14, 17
X0, Y0 = 50, 68
W, H = 1018, 224
DT = 0.06          # seconds per cell
PAUSE = 3.0        # full board stays eaten before the loop restarts
GHOST_LAG = [6, 10, 14]  # cells behind Pac-Man
FONT = "Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace"


def grid(cal: dict) -> list[list[dict | None]]:
    """[col][row] with row 0 = Sunday; None where the calendar has no day."""
    cols = []
    for week in cal["weeks"]:
        col: list[dict | None] = [None] * 7
        for d in week:
            col[(dt.date.fromisoformat(d["date"]).weekday() + 1) % 7] = d
        cols.append(col)
    return cols


def path_order(ncols: int) -> list[tuple[int, int]]:
    out = []
    for c in range(ncols):
        rows = range(7) if c % 2 == 0 else range(6, -1, -1)
        out += [(c, r) for r in rows]
    return out


def centre(c: int, r: int) -> tuple[int, int]:
    return X0 + c * STEP + CELL // 2, Y0 + r * STEP + CELL // 2


def pac_shape(mouth_deg: float, r: float = 7.5) -> str:
    a = math.radians(mouth_deg)
    x, y = r * math.cos(a), r * math.sin(a)
    return f"M0,0 L{x:.2f},{-y:.2f} A{r},{r} 0 1,0 {x:.2f},{y:.2f} Z"


def ghost(color: str, eye: str) -> str:
    body = "M-7,7 L-7,-1 A7,7 0 0,1 7,-1 L7,7 L4.7,4.7 L2.3,7 L0,4.7 L-2.3,7 L-4.7,4.7 Z"
    return (f'<path d="{body}" fill="{color}"/>'
            f'<circle cx="-2.6" cy="-1.5" r="2" fill="{eye}"/><circle cx="2.6" cy="-1.5" r="2" fill="{eye}"/>'
            f'<circle cx="-2" cy="-1.5" r="0.9" fill="#1f2328"/><circle cx="3.2" cy="-1.5" r="0.9" fill="#1f2328"/>')


def build(theme: str, cal: dict) -> str:
    c = THEMES[theme]
    lv = c["levels"]
    cols = grid(cal)
    order = path_order(len(cols))
    move = len(order) * DT
    total = move + PAUSE
    frac = lambda t: f"{t / total:.5f}"

    out = []

    # Cells: each lit one blanks when Pac-Man arrives.
    eaten_at: list[tuple[float, int]] = []
    for i, (ci, r) in enumerate(order):
        d = cols[ci][r]
        if d is None:
            continue
        x, y = X0 + ci * STEP, Y0 + r * STEP
        if d["level"] == 0:
            out.append(f'<use href="#d" x="{x}" y="{y}" fill="{lv[0]}"/>')
            continue
        t = i * DT
        eaten_at.append((t, d["count"]))
        out.append(
            f'<use href="#d" x="{x}" y="{y}" fill="{lv[d["level"]]}">'
            f'<animate attributeName="fill" values="{lv[d["level"]]};{lv[0]}" keyTimes="0;{frac(t)}" '
            f'dur="{total:.3f}s" calcMode="discrete" repeatCount="indefinite"/></use>'
        )

    # Running counter: one tspan per value, each visible only for its window.
    width = len(f"{cal['total']:,}")
    states = [(0.0, 0)]
    run = 0
    for t, n in eaten_at:
        run += n
        states.append((t, run))
    counter = []
    for k, (t, v) in enumerate(states):
        t_end = states[k + 1][0] if k + 1 < len(states) else None
        if t_end is None:
            vals, keys = ("hidden;visible", f"0;{frac(t)}") if t else ("visible", "0")
        elif t == 0:
            vals, keys = "visible;hidden", f"0;{frac(t_end)}"
        else:
            vals, keys = "hidden;visible;hidden", f"0;{frac(t)};{frac(t_end)}"
        counter.append(
            f'<tspan x="15" visibility="{"visible" if t == 0 else "hidden"}">'
            f'<animate attributeName="visibility" values="{vals}" keyTimes="{keys}" dur="{total:.3f}s" '
            f'calcMode="discrete" repeatCount="indefinite"/>{v:>{width},}</tspan>'
        )
    head_x = 15 + (width + 1) * 14 * 0.6

    # Month labels at the first column whose first day starts a new month.
    months, last = [], None
    for ci, col in enumerate(cols):
        first = next((d for d in col if d), None)
        if not first:
            continue
        m = dt.date.fromisoformat(first["date"]).month
        if m != last and ci < len(cols) - 2:
            months.append(f'<text x="{X0 + ci * STEP}" y="{Y0 - 8}">{dt.date(2000, m, 1):%b}</text>')
        last = m
    days = "".join(f'<text x="15" y="{Y0 + r * STEP + 11}">{n}</text>' for r, n in ((1, "Mon"), (3, "Wed"), (5, "Fri")))

    legend_x = X0 + len(cols) * STEP - 5 * STEP - 3
    legend = "".join(f'<use href="#d" x="{legend_x + k * STEP}" y="{H - 30}" fill="{lv[k]}"/>' for k in range(5))

    pts = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in
                   ((i, centre(cc, rr)) for i, (cc, rr) in enumerate(order)))
    motion = (f'<animateMotion path="{pts}" keyPoints="0;1;1" keyTimes="0;{frac(move)};1" '
              f'calcMode="linear" dur="{total:.3f}s" repeatCount="indefinite"{{rot}}/>')

    ghosts = []
    for k, lag in enumerate(GHOST_LAG):
        ghosts.append(
            f'<g opacity="0">{ghost(c["ghost"], "#ffffff")}'
            f'<set attributeName="opacity" to="1" begin="{lag * DT:.2f}s"/>'
            f'{motion.replace("{rot}", "").replace("repeatCount", f"begin=\"{lag * DT:.2f}s\" repeatCount")}</g>'
        )

    pac = (f'<g><path d="{pac_shape(35)}" fill="{c["accent"]}">'
           f'<animate attributeName="d" values="{pac_shape(35)};{pac_shape(2)};{pac_shape(35)}" '
           f'dur="0.3s" repeatCount="indefinite"/></path>{motion.replace("{rot}", " rotate=\"auto\"")}</g>')

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="{FONT}">
<style>text, tspan {{white-space: pre;}}</style>
<defs><rect id="d" width="{CELL}" height="{CELL}" rx="3"/></defs>
<rect width="{W}" height="{H}" rx="15" fill="{c['bg']}"/>
<text y="29" font-size="14px" fill="{c['fg']}">{''.join(counter)}</text>
<text x="{head_x:.1f}" y="29" font-size="14px" fill="{c['fg']}">contributions in the last year</text>
<g font-size="12px" fill="{c['dots']}">{''.join(months)}{days}
<text x="{legend_x - 8}" y="{H - 19}" text-anchor="end">Less</text>
<text x="{legend_x + 5 * STEP + 5}" y="{H - 19}">More</text></g>
{legend}
{chr(10).join(out)}
{''.join(ghosts)}
{pac}
</svg>
"""


def main() -> None:
    cal = json.loads(CAL.read_text())
    for theme in THEMES:
        out = ROOT / f"pacman_{theme}.svg"
        out.write_text(build(theme, cal), encoding="utf-8")
        print(f"wrote {out.name} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
