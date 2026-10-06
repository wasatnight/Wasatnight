#!/usr/bin/env python3
"""Generate a self-hosted SVG contribution heatmap using only the stdlib."""

from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path


@dataclass(frozen=True)
class Contribution:
    day: date
    level: int
    count: int


class ContributionParser(HTMLParser):
    """Parse contribution-day cells and their accessible tooltip text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.days: dict[date, dict[str, int]] = {}
        self.id_to_date: dict[str, date] = {}
        self.tooltip_date: date | None = None
        self.in_tooltip = False
        self.tooltip_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        raw_date = values.get("data-date")
        if tag == "td" and "ContributionCalendar-day" in classes and raw_date:
            try:
                parsed = date.fromisoformat(raw_date)
            except ValueError:
                return
            level = int(values.get("data-level") or 0)
            self.days[parsed] = {"level": max(0, min(level, 4)), "count": 0}
            if values.get("id"):
                self.id_to_date[values["id"]] = parsed
        elif tag == "tool-tip" and values.get("for") in self.id_to_date:
            self.tooltip_date = self.id_to_date[values["for"]]
            self.in_tooltip = True
            self.tooltip_parts = []

    def handle_data(self, data: str) -> None:
        if self.in_tooltip:
            self.tooltip_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_tooltip and tag == "tool-tip":
            tooltip = " ".join(self.tooltip_parts)
            match = re.search(r"([\d,]+)\s+contribution", tooltip, re.IGNORECASE)
            if match and self.tooltip_date in self.days:
                self.days[self.tooltip_date]["count"] = int(match.group(1).replace(",", ""))
            self.in_tooltip = False
            self.tooltip_date = None


def fetch_contributions(username: str, timeout: int = 20) -> list[Contribution]:
    url = f"https://github.com/users/{username}/contributions"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml",
            "User-Agent": "wasatnight-profile-heatmap/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        source = response.read().decode("utf-8", errors="replace")

    parser = ContributionParser()
    parser.feed(source)
    if not parser.days:
        raise RuntimeError("GitHub returned no contribution-day cells")

    return [
        Contribution(day=day, level=data["level"], count=data["count"])
        for day, data in sorted(parser.days.items())
    ]


def render_svg(username: str, contributions: list[Contribution]) -> str:
    by_date = {item.day: item for item in contributions}
    last = max(by_date)
    first = min(by_date)

    # GitHub calendars start on Sunday; align the visible range to full weeks.
    start = first - timedelta(days=(first.weekday() + 1) % 7)
    end = last + timedelta(days=(6 - ((last.weekday() + 1) % 7)))
    weeks = ((end - start).days // 7) + 1

    cell = 13
    gap = 4
    step = cell + gap
    left = 68
    top = 82
    width = max(920, left + weeks * step + 34)
    height = 245
    total = sum(item.count for item in contributions)
    active = sum(1 for item in contributions if item.level > 0)
    palette = ["#25212d", "#4f3578", "#7148a8", "#9867d8", "#c4a0ff"]

    cells: list[str] = []
    month_labels: list[str] = []
    previous_month: int | None = None
    cursor = start
    while cursor <= end:
        week = (cursor - start).days // 7
        weekday = (cursor.weekday() + 1) % 7
        item = by_date.get(cursor, Contribution(cursor, 0, 0))
        x = left + week * step
        y = top + weekday * step
        label = f"{item.count} contribution{'s' if item.count != 1 else ''} on {cursor.isoformat()}"
        cells.append(
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{palette[item.level]}"><title>{html.escape(label)}</title></rect>'
        )
        if cursor.day <= 7 and cursor.month != previous_month and weekday == 0:
            month_labels.append(
                f'<text x="{x}" y="64" class="month">{cursor.strftime("%b")}</text>'
            )
            previous_month = cursor.month
        cursor += timedelta(days=1)

    legend = "".join(
        f'<rect x="{width - 155 + i * step}" y="205" width="{cell}" height="{cell}" rx="3" fill="{color}"/>'
        for i, color in enumerate(palette)
    )
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    escaped_username = html.escape(username)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">GitHub contribution activity for {escaped_username}</title>
  <desc id="desc">{total} contributions across {active} active days in the visible GitHub contribution calendar.</desc>
  <style>
    .bg {{ fill: #111018; }}
    .border {{ fill: none; stroke: #3d3152; }}
    text {{ font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace; }}
    .heading {{ fill: #f2ecdf; font-size: 19px; font-weight: 700; }}
    .meta {{ fill: #91899d; font-size: 12px; }}
    .month,.weekday {{ fill: #91899d; font-size: 11px; }}
    .accent {{ fill: #b993ff; }}
  </style>
  <rect class="bg" x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18"/>
  <rect class="border" x="1" y="1" width="{width - 2}" height="{height - 2}" rx="18"/>
  <text x="28" y="35" class="heading">activity.log</text>
  <text x="155" y="35" class="meta">{total} contributions · {active} active days</text>
  {''.join(month_labels)}
  <text x="28" y="{top + step + 10}" class="weekday">Mon</text>
  <text x="28" y="{top + 3 * step + 10}" class="weekday">Wed</text>
  <text x="28" y="{top + 5 * step + 10}" class="weekday">Fri</text>
  {''.join(cells)}
  <text x="28" y="216" class="meta">github.com/{escaped_username}</text>
  <text x="{width - 236}" y="216" class="meta">less</text>
  {legend}
  <text x="{width - 50}" y="216" class="meta">more</text>
  <text x="28" y="235" class="meta">updated {generated} UTC</text>
</svg>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="wasatnight")
    parser.add_argument("--output", type=Path, default=Path("assets/contributions.svg"))
    args = parser.parse_args()

    try:
        contributions = fetch_contributions(args.username)
        svg = render_svg(args.username, contributions)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(svg, encoding="utf-8", newline="\n")
    except Exception as exc:  # Keep the workflow error concise and actionable.
        print(f"Unable to generate contribution SVG: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {args.output} from {len(contributions)} contribution days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
