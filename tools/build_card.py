"""Render the neofetch-style card: dark_mode.svg and light_mode.svg.

Left: assets/ascii-art.txt. Right: a terminal panel of key ....... value rows,
every row padded to exactly PANEL_COLS characters so the right edge lines up.
A row that cannot fit raises instead of silently overflowing.

    python tools/build_card.py
"""

from __future__ import annotations

import datetime as dt
import json
from html import escape
from pathlib import Path

from palette import THEMES

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "assets" / "ascii-art.txt"
STATS = ROOT / "cache" / "stats.json"

TITLE = "tony@nguyen"

INFO: list[tuple[str, str] | None] = [
    ("OS", "macOS, Ubuntu, iOS"),
    ("Uptime", "{uptime}"),
    ("Host", "Avada, Vietnam"),
    ("Kernel", "Tech Lead · Team SEOOn"),
    ("IDE", "VSCode, Claude Code, Orca"),
    None,
    ("Languages.Programming", "JavaScript, TypeScript, Python"),
    ("Languages.Computer", "HTML, SCSS, Liquid, GraphQL, YAML"),
    ("Languages.Real", "Vietnamese, English"),
    None,
    ("Focus.AI", "Agents, MCP, Claude Code"),
    ("Focus.Web", "Shopify Apps, Firebase, GCP"),
    ("Focus.Infra", "BullMQ, Redis, Cloud Run"),
]

CONTACT = [
    ("Email", "tuannv@avada.email"),
    ("Company", "avada.io"),
    ("GitHub", "tn22180"),
]

# Monospace advance as a fraction of font size. Menlo/Consolas/DejaVu all sit
# at ~0.6em, which is what lets the panel's right edge stay aligned on any OS.
ADVANCE = 0.6
PANEL_FONT = 16
PANEL_LINE = 20
PANEL_COLS = 58
ART_WIDTH = 414
# Cell aspect the art was sampled at (tools/make_ascii.py CELL_ASPECT).
ART_CELL_ASPECT = 0.54
MARGIN = 15
GUTTER = 22


def uptime(since: dt.date, today: dt.date) -> str:
    y = today.year - since.year
    m = today.month - since.month
    d = today.day - since.day
    if d < 0:
        m -= 1
        prev_month_end = today.replace(day=1) - dt.timedelta(days=1)
        d += prev_month_end.day
    if m < 0:
        y -= 1
        m += 12
    plural = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"
    return f"{plural(y, 'year')}, {plural(m, 'month')}, {plural(d, 'day')}"


def fmt(n: int) -> str:
    return f"{n:,}"


class Line:
    """Segments of (text, css class); `pad` marks the one elastic dot run."""

    def __init__(self) -> None:
        self.segs: list[tuple[str, str | None]] = []
        self.pads: list[tuple[int, str]] = []

    def add(self, text: str, cls: str | None = None) -> "Line":
        self.segs.append((text, cls))
        return self

    def key(self, name: str) -> "Line":
        for i, part in enumerate(name.split(".")):
            if i:
                self.add(".")
            self.add(part, "key")
        return self

    def pad(self, char: str = ".") -> "Line":
        self.pads.append((len(self.segs), char))
        self.segs.append(("", "dots"))
        return self

    def render(self, x: float, y: float) -> str:
        used = sum(len(t) for t, _ in self.segs)
        spare = PANEL_COLS - used
        if spare < len(self.pads):
            raise ValueError(f"row overflows by {len(self.pads) - spare}: {''.join(t for t, _ in self.segs)!r}")
        segs = list(self.segs)
        # Split spare width over the pads, leftmost pads take the remainder.
        n = len(self.pads)
        for k, (idx, ch) in enumerate(self.pads):
            width = spare // n + (1 if k < spare % n else 0)
            segs[idx] = (ch * width, "dots")
        body = "".join(
            f'<tspan class="{c}">{escape(t)}</tspan>' if c else escape(t)
            for t, c in segs if t
        )
        return f'<tspan x="{x}" y="{y}">{body}</tspan>'


def kv(key: str, value: str) -> Line:
    return Line().add(". ", "dots").key(key).add(": ").pad().add(" ").add(value, "value")


def rule(title: str, cls: str = "key") -> Line:
    return Line().add(title, cls).add(" ").pad("—")


def panel_lines(stats: dict) -> list[Line | None]:
    since = dt.date.fromisoformat(stats["created_at"][:10])
    up = uptime(since, dt.date.today())
    rows: list[Line | None] = [rule(TITLE, "title")]
    for item in INFO:
        rows.append(None if item is None else kv(item[0], item[1].format(uptime=up)))
    rows += [None, rule("- Contact", "plain")]
    rows += [kv(k, v) for k, v in CONTACT]
    rows += [None, rule("- Stats · GitHub + GitLab", "plain")]
    rows.append(
        Line().add(". ", "dots").key("Repos").add(": ").pad().add(" ").add(fmt(stats["repos"]), "value")
        .add(" {").add("Contributed", "key").add(": ").add(fmt(stats["contrib"]), "value").add("}")
        .add(" | ").key("Stars").add(": ").pad().add(" ").add(fmt(stats["stars"]), "value")
    )
    rows.append(
        Line().add(". ", "dots").key("Commits").add(": ").pad().add(" ").add(fmt(stats["commits"]), "value")
        .add(" | ").key("Followers").add(": ").pad().add(" ").add(fmt(stats["followers"]), "value")
    )
    rows.append(
        Line().add(". ", "dots").key("Lines of Code").add(": ").pad().add(" ").add(fmt(stats["loc"]), "value")
        .add(" ( ").add(fmt(stats["added"]) + "++", "add").add(", ").add(fmt(stats["deleted"]) + "--", "del").add(" )")
    )
    return rows


def build(theme: str, art: list[str], stats: dict) -> str:
    c = THEMES[theme]
    cols = max(len(l) for l in art)
    art_font = ART_WIDTH / (cols * ADVANCE)
    art_line = art_font * ADVANCE / ART_CELL_ASPECT

    rows = panel_lines(stats)
    n_panel = len(rows) + 2  # blank + prompt
    panel_h = (n_panel - 1) * PANEL_LINE
    art_h = (len(art) - 1) * art_line
    inner = max(panel_h + PANEL_FONT, art_h + art_font)
    height = round(inner + 2 * MARGIN + 10)
    mid = height / 2

    panel_x = MARGIN + ART_WIDTH + GUTTER
    width = round(panel_x + PANEL_COLS * PANEL_FONT * ADVANCE + MARGIN)

    # Baselines sit ~0.35em below the line centre; both blocks centre on `mid`.
    py0 = mid - panel_h / 2 + 0.35 * PANEL_FONT
    ay0 = mid - art_h / 2 + 0.35 * art_font

    panel = []
    for i, r in enumerate(rows):
        y = round(py0 + i * PANEL_LINE, 2)
        panel.append(f'<tspan x="{panel_x}" y="{y}" class="dots">.</tspan>' if r is None else r.render(panel_x, y))
    y = round(py0 + (len(rows) + 1) * PANEL_LINE, 2)
    panel.append(
        f'<tspan x="{panel_x}" y="{y}"><tspan class="key">&gt; </tspan>'
        f'<tspan class="value">█<animate attributeName="opacity" values="1;0" dur="1.06s" '
        f'calcMode="discrete" repeatCount="indefinite"/></tspan></tspan>'
    )
    art_spans = "\n".join(
        f'<tspan x="{MARGIN}" y="{ay0 + i * art_line:.2f}">{escape(l)}</tspan>' for i, l in enumerate(art)
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" width="{width}" height="{height}" viewBox="0 0 {width} {height}"
     font-family="Menlo,Consolas,'DejaVu Sans Mono','Liberation Mono',monospace">
<style>
text, tspan {{white-space: pre;}}
.key {{fill: {c['accent']};}}
.title {{fill: {c['accent']}; font-weight: bold;}}
.plain {{fill: {c['fg']};}}
.value {{fill: {c['value']};}}
.dots {{fill: {c['dots']};}}
.add {{fill: {c['add']};}}
.del {{fill: {c['del']};}}
</style>
<rect width="{width}" height="{height}" rx="15" fill="{c['bg']}"/>
<text fill="{c['fg']}" font-size="{art_font:.2f}px">
{art_spans}
</text>
<text fill="{c['fg']}" font-size="{PANEL_FONT}px">
{chr(10).join(panel)}
</text>
</svg>
"""


def main() -> None:
    art = ART.read_text(encoding="utf-8").rstrip("\n").split("\n")
    stats = json.loads(STATS.read_text())
    for theme in THEMES:
        out = ROOT / f"{theme}_mode.svg"
        out.write_text(build(theme, art, stats), encoding="utf-8")
        print(f"wrote {out.name} ({out.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
