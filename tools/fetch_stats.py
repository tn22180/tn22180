"""Fetch GitHub numbers for the card and the contribution board.

Writes cache/stats.json (card numbers) and cache/calendar.json (last year's
contribution grid). Lines of code is the expensive part -- it walks the commit
history of every owned repo -- so per-repo totals are cached in cache/loc.json
keyed by the default-branch head; a repo is only re-walked when its head moves.

    GITHUB_TOKEN=... python tools/fetch_stats.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
API = "https://api.github.com/graphql"

TOKEN = os.environ.get("GITHUB_TOKEN")
if not TOKEN:
    sys.exit("GITHUB_TOKEN is not set")

SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"bearer {TOKEN}", "User-Agent": "profile-card"})


def gql(query: str, **variables) -> dict:
    r = SESSION.post(API, json={"query": query, "variables": variables}, timeout=60)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise RuntimeError(body["errors"])
    return body["data"]


def viewer() -> dict:
    # GITHUB_LOGIN lets the built-in Actions token (which is a bot, not the
    # user) still target the profile owner.
    login = os.environ.get("GITHUB_LOGIN")
    if login:
        q = "query($l:String!){ user(login:$l){ id login createdAt followers{totalCount} } }"
        return gql(q, l=login)["user"]
    q = "{ viewer { id login createdAt followers{totalCount} } }"
    return gql(q)["viewer"]


def owned_repos(login: str) -> list[dict]:
    q = """
    query($l:String!, $after:String){
      user(login:$l){
        repositories(first:100, after:$after, ownerAffiliations:OWNER, isFork:false){
          pageInfo{ hasNextPage endCursor }
          nodes{
            nameWithOwner stargazerCount
            defaultBranchRef{ target{ ... on Commit { oid } } }
          }
        }
      }
    }"""
    out, after = [], None
    while True:
        page = gql(q, l=login, after=after)["user"]["repositories"]
        out += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return out
        after = page["pageInfo"]["endCursor"]


def contributed_count(login: str) -> int:
    q = """
    query($l:String!){ user(login:$l){
      repositoriesContributedTo(first:1, contributionTypes:[COMMIT, PULL_REQUEST, REPOSITORY]){ totalCount }
    } }"""
    return gql(q, l=login)["user"]["repositoriesContributedTo"]["totalCount"]


def total_commits(login: str, since: dt.datetime) -> int:
    # contributionsCollection spans at most one year per call.
    q = """
    query($l:String!, $from:DateTime!, $to:DateTime!){ user(login:$l){
      contributionsCollection(from:$from, to:$to){ totalCommitContributions restrictedContributionsCount }
    } }"""
    now = dt.datetime.now(dt.timezone.utc)
    total, start = 0, since
    while start < now:
        end = min(start + dt.timedelta(days=365), now)
        c = gql(q, l=login, **{"from": start.isoformat(), "to": end.isoformat()})
        cc = c["user"]["contributionsCollection"]
        total += cc["totalCommitContributions"] + cc["restrictedContributionsCount"]
        start = end
    return total


def calendar(login: str) -> dict:
    q = """
    query($l:String!){ user(login:$l){ contributionsCollection{ contributionCalendar{
      totalContributions
      weeks{ contributionDays{ date contributionCount contributionLevel } }
    } } } }"""
    cal = gql(q, l=login)["user"]["contributionsCollection"]["contributionCalendar"]
    levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    return {
        "total": cal["totalContributions"],
        "weeks": [
            [{"date": d["date"], "count": d["contributionCount"], "level": levels[d["contributionLevel"]]}
             for d in w["contributionDays"]]
            for w in cal["weeks"]
        ],
    }


def repo_loc(name: str, author_id: str) -> tuple[int, int]:
    owner, repo = name.split("/")
    q = """
    query($o:String!, $r:String!, $id:ID!, $after:String){ repository(owner:$o, name:$r){
      defaultBranchRef{ target{ ... on Commit {
        history(first:100, after:$after, author:{id:$id}){
          pageInfo{ hasNextPage endCursor }
          nodes{ additions deletions }
        }
      } } }
    } }"""
    add = dele = 0
    after = None
    while True:
        ref = gql(q, o=owner, r=repo, id=author_id, after=after)["repository"]["defaultBranchRef"]
        if not ref:
            return 0, 0
        h = ref["target"]["history"]
        for n in h["nodes"]:
            add += n["additions"]
            dele += n["deletions"]
        if not h["pageInfo"]["hasNextPage"]:
            return add, dele
        after = h["pageInfo"]["endCursor"]


def merge_gitlab(cal: dict, gl: dict) -> dict:
    """Add GitLab's per-day counts onto GitHub's grid and re-level it.

    GitHub's own levels are quartiles of its own counts; once the two sources
    are summed those no longer mean anything, so levels are recomputed the same
    way over the merged non-zero days.
    """
    daily = gl.get("daily", {})
    days = [d for w in cal["weeks"] for d in w]
    for d in days:
        d["count"] += daily.get(d["date"], 0)
    active = sorted(d["count"] for d in days if d["count"])
    if active:
        q = [active[min(len(active) - 1, len(active) * k // 4)] for k in (1, 2, 3)]
        for d in days:
            c = d["count"]
            d["level"] = 0 if not c else 1 + sum(c > t for t in q)
    cal["total"] = sum(d["count"] for d in days)
    return cal


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def main() -> None:
    CACHE.mkdir(exist_ok=True)
    me = viewer()
    login = me["login"]
    repos = owned_repos(login)

    loc_cache = load(CACHE / "loc.json")
    fresh = {}
    for r in repos:
        name = r["nameWithOwner"]
        # Keyed by hash: this file is committed to a public repo and the list
        # includes private repos, whose names should not leak.
        key = hashlib.sha256(name.encode()).hexdigest()[:16]
        head = ((r.get("defaultBranchRef") or {}).get("target") or {}).get("oid")
        hit = loc_cache.get(key)
        if hit and hit["head"] == head:
            fresh[key] = hit
            continue
        a, d = repo_loc(name, me["id"]) if head else (0, 0)
        fresh[key] = {"head": head, "add": a, "del": d}
        print(f"walked {key}: +{a} -{d}")
    (CACHE / "loc.json").write_text(json.dumps(fresh, indent=1, sort_keys=True) + "\n")

    added = sum(v["add"] for v in fresh.values())
    deleted = sum(v["del"] for v in fresh.values())
    since = dt.datetime.fromisoformat(me["createdAt"].replace("Z", "+00:00"))

    gl = load(CACHE / "gitlab.json")

    stats = {
        "login": login,
        "created_at": me["createdAt"],
        "repos": len(repos),
        "contrib": contributed_count(login),
        "stars": sum(r["stargazerCount"] for r in repos),
        "followers": me["followers"]["totalCount"],
        "commits": total_commits(login, since) + gl.get("commits", 0),
        "added": added,
        "deleted": deleted,
        "loc": added - deleted,
    }
    (CACHE / "stats.json").write_text(json.dumps(stats, indent=1) + "\n")
    cal = merge_gitlab(calendar(login), gl) if gl else calendar(login)
    (CACHE / "calendar.json").write_text(json.dumps(cal) + "\n")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
