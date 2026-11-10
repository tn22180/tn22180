"""Colours shared by the card, the link buttons and the contribution board.

Backgrounds match GitHub's own canvas so the SVGs sit flush on the profile.
"""

THEMES = {
    "dark": {
        "bg": "#161b22", "border": "#30363d", "fg": "#c9d1d9",
        "accent": "#f76e0a", "value": "#a5d6ff", "dots": "#616e7f",
        "add": "#3fb950", "del": "#f85149",
        "link": ["#f76e0a", "#a5d6ff", "#f0866b"],
        "levels": ["#21262d", "#39414a", "#5b636d", "#8b949e", "#e6edf3"],
        "ghost": "#f0866b",
    },
    "light": {
        "bg": "#ffffff", "border": "#d0d7de", "fg": "#24292f",
        "accent": "#bc4c00", "value": "#0550ae", "dots": "#8c959f",
        "add": "#1a7f37", "del": "#cf222e",
        "link": ["#bc4c00", "#0550ae", "#c4432b"],
        "levels": ["#ebedf0", "#c9cdd2", "#9aa1a9", "#6e7781", "#24292f"],
        "ghost": "#c4432b",
    },
}
