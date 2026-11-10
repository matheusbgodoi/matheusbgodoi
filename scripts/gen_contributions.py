"""Generate assets/contributions.svg from the GitHub contribution calendar.

Fetches the last-year calendar through the GraphQL API using a token that
can see the user's private contributions (the user's own PAT with `read:user`),
then renders an animated SVG: cells pop in week by week, a light sweep loops
across the grid, and the header shows total, streaks and busiest day.

Usage:
    GITHUB_TOKEN=... python scripts/gen_contributions.py matheusbgodoi dist/contributions.svg
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import urllib.request

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel weekday } }
      }
    }
  }
}
"""

LEVELS = {
    "NONE": "#161b22",
    "FIRST_QUARTILE": "#4a2a12",
    "SECOND_QUARTILE": "#9a4a0f",
    "THIRD_QUARTILE": "#d9661a",
    "FOURTH_QUARTILE": "#ff8a3d",
}
BG = "#0b0f14"
FRAME = "#1f2a37"
TEXT = "#e6edf3"
MUTED = "#7d8590"
ACCENT = "#f97316"
FONT = "'JetBrains Mono','Fira Code','SFMono-Regular',Menlo,Consolas,'Liberation Mono',monospace"

CELL = 11
GAP = 3
STEP = CELL + GAP


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if "errors" in payload:
        raise SystemExit(f"GraphQL error: {payload['errors']}")
    return payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]


def streaks(days: list[dict]) -> tuple[int, int]:
    longest = cur = 0
    for d in days:
        if d["contributionCount"] > 0:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    # current streak: count back from the last day, allowing today to be empty
    current = 0
    for d in reversed(days):
        if d["contributionCount"] > 0:
            current += 1
        elif current == 0 and d is days[-1]:
            continue
        else:
            break
    return current, longest


def render(cal: dict, login: str) -> str:
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]
    current, longest = streaks(days)
    busiest = max(days, key=lambda d: d["contributionCount"])
    active = sum(1 for d in days if d["contributionCount"] > 0)

    left, top = 44, 78
    grid_w = len(weeks) * STEP - GAP
    grid_h = 7 * STEP - GAP
    width = left + grid_w + 24
    height = top + grid_h + 56

    out: list[str] = []
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">'
    )
    out.append(f"<title id=\"t\">{total:,} contributions in the last year</title>")
    out.append(
        f"<desc id=\"d\">GitHub contribution calendar for {login}: {total:,} contributions, "
        f"current streak {current} days, longest streak {longest} days.</desc>"
    )
    out.append(
        f"<style>text{{font-family:{FONT};}}"
        f".h{{font-size:15px;fill:{TEXT};font-weight:600}}"
        f".m{{font-size:10.5px;fill:{MUTED}}}"
        f".k{{font-size:11px;fill:{MUTED}}}"
        f".v{{font-size:11px;fill:{ACCENT}}}</style>"
    )
    out.append("<defs>")
    out.append(
        '<linearGradient id="sweep" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="#fff" stop-opacity="0.22"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )
    out.append(f'<clipPath id="grid"><rect x="{left}" y="{top}" width="{grid_w}" height="{grid_h}"/></clipPath>')
    out.append("</defs>")
    out.append(f'<rect x="0.5" y="0.5" width="{width-1}" height="{height-1}" rx="12" fill="{BG}" stroke="{FRAME}"/>')

    # header
    out.append(f'<text x="{left}" y="30" class="h">{total:,} contributions in the last year</text>')
    stats = [
        ("active days", f"{active}"),
        ("current streak", f"{current}d"),
        ("longest streak", f"{longest}d"),
        ("busiest day", f"{busiest['contributionCount']} · {busiest['date']}"),
    ]
    x = left
    out.append(f'<text x="{x}" y="52" class="k">')
    for i, (k, v) in enumerate(stats):
        sep = "   " if i else ""
        out.append(f'<tspan class="k">{sep}{k} </tspan><tspan class="v">{v}</tspan>')
    out.append("</text>")

    # month labels
    seen = set()
    for wi, w in enumerate(weeks):
        first = w["contributionDays"][0]
        d = dt.date.fromisoformat(first["date"])
        key = (d.year, d.month)
        if d.day <= 7 and key not in seen:
            seen.add(key)
            out.append(f'<text x="{left + wi*STEP}" y="{top-8}" class="m">{d.strftime("%b")}</text>')

    # weekday labels
    for row, label in ((1, "Mon"), (3, "Wed"), (5, "Fri")):
        out.append(f'<text x="{left-8}" y="{top + row*STEP + CELL - 2}" text-anchor="end" class="m">{label}</text>')

    # cells
    n_weeks = len(weeks)
    for wi, w in enumerate(weeks):
        delay = 0.03 * wi
        for d in w["contributionDays"]:
            row = d["weekday"]
            cx = left + wi * STEP
            cy = top + row * STEP
            color = LEVELS[d["contributionLevel"]]
            out.append(
                f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2.5" fill="{color}" opacity="0">'
                f'<title>{d["contributionCount"]} on {d["date"]}</title>'
                f'<animate attributeName="opacity" from="0" to="1" begin="{delay:.2f}s" dur="0.35s" fill="freeze"/>'
                "</rect>"
            )

    # light sweep
    sweep_w = 120
    start = 0.03 * n_weeks + 0.6
    out.append(
        f'<g clip-path="url(#grid)"><rect x="{left - sweep_w}" y="{top}" width="{sweep_w}" height="{grid_h}" fill="url(#sweep)">'
        f'<animate attributeName="x" values="{left - sweep_w};{left + grid_w}" begin="{start:.2f}s" dur="3.6s" repeatCount="indefinite"/>'
        "</rect></g>"
    )

    # legend
    ly = height - 22
    out.append(f'<text x="{left}" y="{ly+9}" class="m">updated {dt.date.today().isoformat()}</text>')
    lx = width - 24 - (len(LEVELS) * STEP) - 72
    out.append(f'<text x="{lx - 6}" y="{ly+9}" text-anchor="end" class="m">Less</text>')
    for i, color in enumerate(LEVELS.values()):
        out.append(f'<rect x="{lx + i*STEP}" y="{ly}" width="{CELL}" height="{CELL}" rx="2.5" fill="{color}"/>')
    out.append(f'<text x="{lx + len(LEVELS)*STEP + 4}" y="{ly+9}" class="m">More</text>')
    out.append("</svg>")
    return "\n".join(out)


def main() -> None:
    login, out_path = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is required")
    cal = fetch(login, token)
    svg = render(cal, login)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(svg)
    print(f"{out_path}: {len(svg)/1024:.1f} KB, total={cal['totalContributions']}")


if __name__ == "__main__":
    main()
