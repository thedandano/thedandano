"""Rebuild the profile README and its chart from live GitHub data.

The wording lives in template.md. This script fills in the live numbers,
draws the "where the work went" chart, and writes README.md.
"""

from __future__ import annotations

import http.client
import json
import logging
import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape
from http import HTTPStatus
from pathlib import Path
from string import Template
from typing import Any
from urllib.parse import quote_plus

LOGIN = "thedandano"
CALLBACK_URL = f"https://github.com/{LOGIN}/callback"

API_HOST = "api.github.com"
API_PATH = "/graphql"
TIMEOUT_SECONDS = 30
LOOKBACK_DAYS = 365
ERROR_BODY_PREVIEW_CHARS = 300
# ponytail: GitHub search hands back at most 1,000 results (10 pages of 100). Past that
# the chart and language list go short and fetch() says so. Split the search by date
# range if a year of merged work ever passes 1,000.
MAX_EXTRA_PAGES = 9

MAX_OUTSIDE_ITEMS = 6
MAX_TITLE_CHARS = 80
PAIR = 2  # two words join with "and" alone; three or more need commas
MIN_LANGUAGE_PULLS = 5  # a language is named only with this many merged pull requests

TEMPLATE_PATH = "template.md"
README_PATH = "README.md"
CHART_PATHS = {"light": "assets/work-light.svg", "dark": "assets/work-dark.svg"}

# Chart series, in fixed order. Repos not listed here count as "Other".
OTHER = "Other"
SERIES = ("callback", "Solar stack", "World Cup Bar", OTHER)
PROJECT_OF = {
    f"{LOGIN}/callback": "callback",
    f"{LOGIN}/enphase-bridge": "Solar stack",
    f"{LOGIN}/enphase-bridge-dashboard": "Solar stack",
    f"{LOGIN}/enphase-bridge-plugin": "Solar stack",
    f"{LOGIN}/world-cup-kickoff-bar": "World Cup Bar",
}
# Series colors passed the dataviz palette validator on GitHub's light and dark
# backgrounds. "Other" is a neutral gray on purpose. Text uses ink, never a series color.
CHART_COLORS = {
    "light": {
        "series": ("#2a78d6", "#eb6834", "#1baf7a", "#8c959f"),
        "ink": "#59636e",
        "grid": "#d1d9e0",
    },
    "dark": {
        "series": ("#3987e5", "#d95926", "#199e70", "#6e7681"),
        "ink": "#9198a1",
        "grid": "#3d444d",
    },
}

CHART_WIDTH = 713
MAX_BAR_STEP = 20
BAR_GAP = 4
RIGHT_PADDING = 20
SEGMENT_GAP = 1
BAR_RADIUS = 1
AXIS_WIDTH = 24
PLOT_TOP = 8
PLOT_HEIGHT = 96
MONTH_ROW_HEIGHT = 18
LEGEND_ROW_HEIGHT = 22
SWATCH_SIZE = 10
LEGEND_CHAR_WIDTH = 6
LEGEND_ITEM_PADDING = 30
TICK_ROUNDING = 10
LABEL_OFFSET = 4
MIN_LABEL_GAP_COLUMNS = 2
DAYS_PER_WEEK = 7
FONT_STACK = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

QUERY = """
query($login: String!, $merged: String!, $outside: String!, $cursor: String) {
  user(login: $login) {
    socialAccounts(first: 10) { nodes { provider url } }
  }
  callback: repository(owner: $login, name: "callback") {
    releases { totalCount }
    latestRelease { tagName }
  }
  merged: search(query: $merged, type: ISSUE, first: 100, after: $cursor) {
    issueCount
    pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest { mergedAt repository { nameWithOwner primaryLanguage { name } } } }
  }
  outside: search(query: $outside, type: ISSUE, first: 20) {
    nodes { ... on PullRequest { title url repository { nameWithOwner isPrivate } } }
  }
}
"""

log = logging.getLogger("build")


@dataclass(frozen=True)
class OutsideItem:
    title: str
    url: str
    project: str


def merged_query(since: date) -> str:
    """Search text for merged public pull requests; also used as the evidence link."""
    return f"author:{LOGIN} is:pr is:merged is:public merged:>={since.isoformat()}"


def graphql(token: str, variables: dict[str, Any]) -> dict[str, Any]:
    """Send the page's one query to GitHub and return its data."""
    payload = json.dumps({"query": QUERY, "variables": variables})
    headers = {"Authorization": f"Bearer {token}", "User-Agent": LOGIN}
    connection = http.client.HTTPSConnection(API_HOST, timeout=TIMEOUT_SECONDS)
    try:
        connection.request("POST", API_PATH, body=payload, headers=headers)
        response = connection.getresponse()
        raw = response.read()
    except (OSError, http.client.HTTPException) as error:
        raise RuntimeError(f"Could not reach {API_HOST}: {error}") from error
    finally:
        connection.close()
    if response.status != HTTPStatus.OK:
        preview = raw[:ERROR_BODY_PREVIEW_CHARS].decode(errors="replace")
        raise RuntimeError(f"GitHub API answered {response.status}: {preview}")
    body = json.loads(raw)
    if body.get("errors"):
        raise RuntimeError(f"GitHub API returned errors: {body['errors']}")
    return body["data"]


def fetch(token: str, since: date) -> dict[str, Any]:
    """Fetch everything the page needs, following extra pages of merged pull requests."""
    merged = merged_query(since)
    variables = {
        "login": LOGIN,
        "merged": f"{merged} sort:updated-desc",
        "outside": f"{merged} -user:{LOGIN} sort:updated-desc",
        "cursor": None,
    }
    data = graphql(token, variables)
    page = data["merged"]
    for _ in range(MAX_EXTRA_PAGES):
        if not page["pageInfo"]["hasNextPage"]:
            break
        page = graphql(token, variables | {"cursor": page["pageInfo"]["endCursor"]})["merged"]
        data["merged"]["nodes"] += page["nodes"]
    collected = len(data["merged"]["nodes"])
    if collected < data["merged"]["issueCount"]:
        log.warning(
            "GitHub returned %d of %d merged pull requests; the chart and the language "
            "list leave out the rest. The total count is still exact.",
            collected,
            data["merged"]["issueCount"],
        )
    return data


def outside_work(nodes: list[dict[str, Any]]) -> list[OutsideItem]:
    """Merged pull requests in other people's public repos, newest first."""
    return [
        OutsideItem(
            title=node["title"], url=node["url"], project=node["repository"]["nameWithOwner"]
        )
        for node in nodes
        if node and not node["repository"]["isPrivate"]
    ][:MAX_OUTSIDE_ITEMS]


def languages(nodes: list[dict[str, Any]]) -> list[str]:
    """Main languages of the repos behind the merged pull requests, most used first."""
    names = [
        node["repository"]["primaryLanguage"]["name"]
        for node in nodes
        if node and node["repository"]["primaryLanguage"]
    ]
    return [name for name, count in Counter(names).most_common() if count >= MIN_LANGUAGE_PULLS]


def languages_clause(names: list[str]) -> str:
    """ ", across X, Y, and Z" for the sentence in template.md, or nothing without names."""
    return f", across {word_list(names)}" if names else ""


def word_list(words: list[str]) -> str:
    if len(words) <= PAIR:
        return " and ".join(words)
    return f"{', '.join(words[:-1])}, and {words[-1]}"


def md_text(text: str) -> str:
    """Make free text safe to drop into Markdown."""
    return escape(re.sub(r"([\\`*_\[\]])", r"\\\1", text), quote=False)


def shorten(title: str) -> str:
    if len(title) <= MAX_TITLE_CHARS:
        return title
    return title[: MAX_TITLE_CHARS - 1].rstrip() + "…"


def short_date(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def contact_link(user: dict[str, Any]) -> str:
    linkedin = next(
        (a["url"] for a in user["socialAccounts"]["nodes"] if a["provider"] == "LINKEDIN"), None
    )
    if linkedin:
        return f"[Message me on LinkedIn]({linkedin})"
    log.warning("No LinkedIn account on the GitHub profile; the page has no contact link.")
    return ""


def outside_section(items: list[OutsideItem]) -> str:
    """A list of merged outside work, or nothing when there is none."""
    if not items:
        return ""
    rows = [
        f"- [{md_text(shorten(item.title))}]({item.url}) · {item.project} · merged"
        for item in items
    ]
    return "## Merged in other projects\n\n" + "\n".join(rows)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def weekly_counts(
    nodes: list[dict[str, Any]], since: date, today: date
) -> dict[date, Counter[str]]:
    """Merged pull requests per week (Monday start) and project, oldest week first.

    Starts at the first week with merged work, so the chart has no empty lead-in.
    """
    merged_days = [datetime.fromisoformat(node["mergedAt"]).date() for node in nodes if node]
    first = week_start(max(min(merged_days, default=today), since))
    week_count = (week_start(today) - first).days // DAYS_PER_WEEK + 1
    weeks: dict[date, Counter[str]] = {
        first + timedelta(weeks=index): Counter() for index in range(week_count)
    }
    for node in nodes:
        if not node:
            continue
        week = week_start(datetime.fromisoformat(node["mergedAt"]).date())
        if week in weeks:
            weeks[week][PROJECT_OF.get(node["repository"]["nameWithOwner"], OTHER)] += 1
    return weeks


def project_totals(weeks: dict[date, Counter[str]]) -> list[tuple[str, int]]:
    """Total per series, in series order, leaving out series with no work."""
    totals = sum(weeks.values(), Counter())
    return [(name, totals[name]) for name in SERIES if totals[name]]


def chart_summary(weeks: dict[date, Counter[str]]) -> str:
    """The chart's numbers as a sentence, so nobody has to read them off the picture."""
    parts = [f"{name} {count}" for name, count in project_totals(weeks)]
    if not parts:
        return "No merged pull requests in the last 12 months."
    since = next(iter(weeks))
    return (
        f"Merged pull requests by week since {since:%b %Y}. "
        f"Totals, in the order the bars stack from the bottom: {', '.join(parts)}."
    )


def bar_step(week_count: int) -> int:
    """Width of one week's slot: as wide as fits, up to a cap."""
    return min((CHART_WIDTH - AXIS_WIDTH - RIGHT_PADDING) // max(week_count, 1), MAX_BAR_STEP)


def axis_top(weeks: dict[date, Counter[str]]) -> int:
    """Top of the y-axis: the busiest week, rounded up to a round number."""
    peak = max((sum(counts.values()) for counts in weeks.values()), default=0)
    return max(math.ceil(peak / TICK_ROUNDING), 1) * TICK_ROUNDING


def grid_lines(top: int, colors: dict[str, Any]) -> list[str]:
    """Faint lines and labels at the top and middle of the y-axis, plus the baseline."""
    lines = []
    for value in (top, top // 2, 0):
        y = PLOT_TOP + PLOT_HEIGHT - value * PLOT_HEIGHT / top
        lines.append(
            f'<line x1="{AXIS_WIDTH}" y1="{y:g}" x2="{CHART_WIDTH}" y2="{y:g}" '
            f'stroke="{colors["grid"]}" stroke-width="1"/>'
        )
        lines.append(
            f'<text x="{AXIS_WIDTH - LABEL_OFFSET}" y="{y + LABEL_OFFSET:g}" '
            f'text-anchor="end" fill="{colors["ink"]}">{value}</text>'
        )
    return lines


def bars(weeks: dict[date, Counter[str]], top: int, colors: dict[str, Any]) -> list[str]:
    """One stacked bar per week, with a thin gap between projects."""
    rects = []
    unit = PLOT_HEIGHT / top
    step = bar_step(len(weeks))
    for column, counts in enumerate(weeks.values()):
        y = PLOT_TOP + PLOT_HEIGHT
        for name, fill in zip(SERIES, colors["series"], strict=True):
            height = counts[name] * unit
            if not height:
                continue
            y -= height
            rects.append(
                f'<rect x="{AXIS_WIDTH + column * step}" y="{y:g}" width="{step - BAR_GAP}" '
                f'height="{max(height - SEGMENT_GAP, 1):g}" rx="{BAR_RADIUS}" fill="{fill}"/>'
            )
    return rects


def month_labels(weeks: dict[date, Counter[str]], colors: dict[str, Any]) -> list[str]:
    """A month name under the first week shown and under each new month after it.

    A new month too close to the previous label is skipped so names never overlap.
    """
    labels = []
    previous_month = None
    last_labeled = -MIN_LABEL_GAP_COLUMNS
    y = PLOT_TOP + PLOT_HEIGHT + MONTH_ROW_HEIGHT - LABEL_OFFSET
    for column, week in enumerate(weeks):
        if week.month != previous_month and column - last_labeled >= MIN_LABEL_GAP_COLUMNS:
            x = AXIS_WIDTH + column * bar_step(len(weeks))
            labels.append(f'<text x="{x}" y="{y}" fill="{colors["ink"]}">{week:%b}</text>')
            last_labeled = column
        previous_month = week.month
    return labels


def legend(weeks: dict[date, Counter[str]], colors: dict[str, Any]) -> list[str]:
    """A swatch and a name for each project that has work in the chart."""
    items = []
    x = AXIS_WIDTH
    y = PLOT_TOP + PLOT_HEIGHT + MONTH_ROW_HEIGHT + LABEL_OFFSET
    shown = {name for name, _ in project_totals(weeks)}
    for name, fill in zip(SERIES, colors["series"], strict=True):
        if name not in shown:
            continue
        items.append(
            f'<rect x="{x}" y="{y}" width="{SWATCH_SIZE}" height="{SWATCH_SIZE}" '
            f'rx="{BAR_RADIUS}" fill="{fill}"/>'
        )
        items.append(
            f'<text x="{x + SWATCH_SIZE + LABEL_OFFSET}" y="{y + SWATCH_SIZE - 1}" '
            f'fill="{colors["ink"]}">{escape(name)}</text>'
        )
        x += len(name) * LEGEND_CHAR_WIDTH + LEGEND_ITEM_PADDING
    return items


def render_chart(weeks: dict[date, Counter[str]], theme: str) -> str:
    """Draw merged pull requests per week by project as an SVG with no background."""
    colors = CHART_COLORS[theme]
    top = axis_top(weeks)
    width = CHART_WIDTH
    height = PLOT_TOP + PLOT_HEIGHT + MONTH_ROW_HEIGHT + LEGEND_ROW_HEIGHT
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" font-family="{FONT_STACK}" font-size="10">',
        f"<title>{escape(chart_summary(weeks))}</title>",
        *grid_lines(top, colors),
        *bars(weeks, top, colors),
        *month_labels(weeks, colors),
        *legend(weeks, colors),
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def page_values(data: dict[str, Any], today: date) -> dict[str, str]:
    """Every value template.md asks for. No I/O."""
    user = data["user"]
    if user is None:
        raise RuntimeError(f"GitHub has no user named {LOGIN!r}.")
    callback = data["callback"]
    if callback is None or callback["latestRelease"] is None:
        raise RuntimeError(f"Could not read releases for {CALLBACK_URL}; was the repo renamed?")
    since = today - timedelta(days=LOOKBACK_DAYS)
    merged = data["merged"]
    weeks = weekly_counts(merged["nodes"], since, today)
    summary = chart_summary(weeks)
    return {
        "merged_count": f"{merged['issueCount']:,}",
        "merged_url": (
            f"https://github.com/search?q={quote_plus(merged_query(since))}&type=pullrequests"
        ),
        "languages_clause": languages_clause(languages(merged["nodes"])),
        "release_count": str(callback["releases"]["totalCount"]),
        "latest_release": callback["latestRelease"]["tagName"],
        "chart_alt": escape(summary),
        "chart_width": str(CHART_WIDTH),
        "chart_summary": summary,
        "contact": contact_link(user),
        "outside_section": outside_section(outside_work(data["outside"]["nodes"])),
        "today": short_date(today),
    }


def build(data: dict[str, Any], today: date, template: str) -> dict[str, str]:
    """Turn API data and the template into the files to write, keyed by path. No I/O."""
    try:
        page = Template(template).substitute(page_values(data, today))
    except KeyError as error:
        raise RuntimeError(
            f"{TEMPLATE_PATH} asks for {error}, which build.py does not provide."
        ) from error
    files = {README_PATH: re.sub(r"\n{3,}", "\n\n", page)}
    weeks = weekly_counts(data["merged"]["nodes"], today - timedelta(days=LOOKBACK_DAYS), today)
    for theme, path in CHART_PATHS.items():
        files[path] = render_chart(weeks, theme)
    return files


def main(root: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set. Export a GitHub token and run again.")
    today = datetime.now(UTC).date()
    template = (root / TEMPLATE_PATH).read_text(encoding="utf-8")
    data = fetch(token, today - timedelta(days=LOOKBACK_DAYS))
    for path, content in build(data, today, template).items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log.info("Wrote %s", path)


if __name__ == "__main__":
    main(Path(__file__).parent)
