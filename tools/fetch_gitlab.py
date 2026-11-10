"""Snapshot self-hosted GitLab activity into cache/gitlab.json.

Most of the real work lives on a company GitLab that GitHub Actions cannot
reach, and its token does not belong in a public repo's secrets. So this runs
on the owner's machine (via the authenticated `glab` CLI) and the snapshot is
committed; fetch_stats.py merges it into the card and the board in CI.

Counts follow GitLab's own calendar: one per event, per day, summed across
hosts (the team moved from gitlab.com to a self-hosted instance in 2026-08, so
history is split between the two). Commits are the sum of
push_data.commit_count, skipping pushes over MAX_PUSH_COMMITS: those are branch
imports and rebased force-pushes (one was 1,953), not work done that day.

    python tools/fetch_gitlab.py [--hosts gitlab.com git.avada.net] [--days 400]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cache" / "gitlab.json"
MAX_PUSH_COMMITS = 50


def glab(host: str, path: str, paginate: bool = False) -> list | dict:
    args = ["glab", "api", "--hostname", host] + (["--paginate"] if paginate else []) + [path]
    raw = subprocess.run(
        args,
        check=True, capture_output=True, text=True,
    ).stdout
    # --paginate concatenates one JSON array per page.
    dec, out, i = json.JSONDecoder(), [], 0
    while i < len(raw):
        while i < len(raw) and raw[i].isspace():
            i += 1
        if i >= len(raw):
            break
        obj, i = dec.raw_decode(raw, i)
        if isinstance(obj, list):
            out += obj
        else:
            return obj
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hosts", nargs="+", default=["gitlab.com", "git.avada.net"])
    ap.add_argument("--days", type=int, default=400)
    a = ap.parse_args()

    after = (dt.date.today() - dt.timedelta(days=a.days)).isoformat()
    events = []
    for host in a.hosts:
        me = glab(host, "user")
        got = glab(host, f"users/{me['username']}/events?after={after}&per_page=100", paginate=True)
        print(f"{host}: {me['username']} {len(got)} events")
        events += got

    daily: Counter[str] = Counter()
    commits = 0
    for e in events:
        daily[e["created_at"][:10]] += 1
        n = (e.get("push_data") or {}).get("commit_count") or 0
        if n <= MAX_PUSH_COMMITS:
            commits += n

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({
        "fetched_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "events": len(events),
        "commits": commits,
        "daily": dict(sorted(daily.items())),
    }, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(events)} events, {commits} commits, {len(daily)} active days")


if __name__ == "__main__":
    main()
