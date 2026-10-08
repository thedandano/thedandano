"""Rebuild the profile README and contribution calendar from live GitHub data."""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape
from http import HTTPStatus
from pathlib import Path
from typing import Any

LOGIN = "thedandano"
ROLE = "AI and backend engineer"
SUMMARY = "I build agent systems and the services behind them, mostly in Python and Rust."

API_HOST = "api.github.com"
API_PATH = "/graphql"
TIMEOUT_SECONDS = 30
LOOKBACK_DAYS = 365
ERROR_BODY_PREVIEW_CHARS = 300

MAX_FALLBACK_REPOS = 4
MAX_OUTSIDE_ITEMS = 6
MAX_TITLE_CHARS = 80

README_PATH = "README.md"
CALENDAR_PATHS = {"light": "assets/calendar-light.svg", "dark": "assets/calendar-dark.svg"}

CELL_SIZE = 10
CELL_STEP = 13
CELL_RADIUS = 2
LABEL_HEIGHT = 16
LABEL_BASELINE = 10
LABEL_ROOM = 24
DAYS_PER_WEEK = 7
FONT_STACK = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"

LEVELS = ("NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE")
# Colors come from DESIGN.md: five heat steps and a label color per theme.
PALETTES = {
    "light": {
        "heat": ("#ebe8e2", "#f1d9a8", "#e3b25a", "#c4831a", "#8a5600"),
        "label": "#6b655a",
    },
    "dark": {
        "heat": ("#1c1f24", "#4a3410", "#80570f", "#b9801c", "#f0b452"),
        "label": "#9c958a",
    },
}

QUERY = """
query($login: String!, $outside: String!) {
  user(login: $login) {
    name
    location
    websiteUrl
    socialAccounts(first: 10) { nodes { provider url } }
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes { ... on Repository { ...repo } }
    }
    repositories(first: 20, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: PUSHED_AT, direction: DESC}) {
      nodes { ...repo }
    }
    contributionsCollection {
      totalPullRequestContributions
      restrictedContributionsCount
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionLevel } }
      }
    }
  }
  search(query: $outside, type: ISSUE, first: 30) {
    nodes {
      __typename
      ... on PullRequest { title url state updatedAt repository { nameWithOwner isPrivate } }
      ... on Issue { title url state updatedAt repository { nameWithOwner isPrivate } }
    }
  }
}
fragment repo on Repository {
  name url description isPrivate isArchived pushedAt primaryLanguage { name }
}
"""

log = logging.getLogger("build")


@dataclass(frozen=True)
class Repo:
    name: str
    url: str
    description: str
    language: str
    pushed: date


@dataclass(frozen=True)
class OutsideItem:
    title: str
    url: str
    project: str
    kind: str
    status: str


def fetch(token: str, since: date) -> dict[str, Any]:
    """Run the one GraphQL query the page needs and return its data."""
    outside = f"author:{LOGIN} is:public -user:{LOGIN} created:>={since.isoformat()}"
    payload = json.dumps({"query": QUERY, "variables": {"login": LOGIN, "outside": outside}})
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


def to_repo(node: dict[str, Any]) -> Repo:
    return Repo(
        name=node["name"],
        url=node["url"],
        description=node["description"] or "",
        language=(node["primaryLanguage"] or {}).get("name", ""),
        pushed=parse_day(node["pushedAt"]),
    )


def parse_day(timestamp: str) -> date:
    return datetime.fromisoformat(timestamp).date()


def featured_repos(user: dict[str, Any]) -> list[Repo]:
    """Pinned public repos, or the most recently active described repos if nothing is pinned."""
    pins = [
        to_repo(node) for node in user["pinnedItems"]["nodes"] if node and not node["isPrivate"]
    ]
    for repo in pins:
        if not repo.description:
            log.warning("Pinned repo %s has no description; showing its name only.", repo.name)
    if pins:
        return pins
    log.warning("No public repos are pinned; falling back to the most recently active repos.")
    recent = [
        to_repo(node)
        for node in user["repositories"]["nodes"]
        if node["description"] and not node["isArchived"] and not node["isPrivate"]
    ]
    return recent[:MAX_FALLBACK_REPOS]


def item_status(node: dict[str, Any]) -> str | None:
    """Real status of a pull request or issue; None for anything the page must not show."""
    state = node["state"]
    if state in ("OPEN", "MERGED"):
        return state.lower()
    return None


def outside_work(nodes: list[dict[str, Any]]) -> list[OutsideItem]:
    """Open or merged work in other people's public repos, newest first."""
    kinds = {"PullRequest": "pull request", "Issue": "issue"}
    shown = [
        node
        for node in nodes
        if node.get("__typename") in kinds
        and not node["repository"]["isPrivate"]
        and item_status(node) is not None
    ]
    shown.sort(key=lambda node: node["updatedAt"], reverse=True)
    return [
        OutsideItem(
            title=node["title"],
            url=node["url"],
            project=node["repository"]["nameWithOwner"],
            kind=kinds[node["__typename"]],
            status=item_status(node) or "",
        )
        for node in shown[:MAX_OUTSIDE_ITEMS]
    ]


def md_text(text: str) -> str:
    """Make free text safe to drop into Markdown."""
    return escape(re.sub(r"([\\`*_\[\]])", r"\\\1", text), quote=False)


def shorten(title: str) -> str:
    if len(title) <= MAX_TITLE_CHARS:
        return title
    return title[: MAX_TITLE_CHARS - 1].rstrip() + "…"


def short_date(day: date) -> str:
    return f"{day:%b} {day.day}, {day.year}"


def with_scheme(url: str) -> str:
    return url if "://" in url else f"https://{url}"


def contact_links(user: dict[str, Any]) -> list[str]:
    links = []
    linkedin = next(
        (a["url"] for a in user["socialAccounts"]["nodes"] if a["provider"] == "LINKEDIN"), None
    )
    if linkedin:
        links.append(f"[Message me on LinkedIn]({linkedin})")
    else:
        log.warning("No LinkedIn account on the GitHub profile; the page has no main contact link.")
    if user["websiteUrl"]:
        site = with_scheme(user["websiteUrl"])
        links.append(f"[{site.split('://', 1)[1].rstrip('/')}]({site})")
    return links


def calendar_alt(user: dict[str, Any]) -> str:
    total = user["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return f"Contribution calendar: {total:,} contributions in the last 12 months."


def activity_line(user: dict[str, Any]) -> str:
    contributions = user["contributionsCollection"]
    total = contributions["contributionCalendar"]["totalContributions"]
    pull_requests = contributions["totalPullRequestContributions"]
    private_note = (
        ", counting private work" if contributions["restrictedContributionsCount"] else ""
    )
    return (
        f"**{total:,}** contributions and **{pull_requests:,}** pull requests "
        f"in the last 12 months{private_note}."
    )


def repo_row(repo: Repo) -> str:
    facts = [f"**[{repo.name}]({repo.url})**", repo.language, f"updated {short_date(repo.pushed)}"]
    heading = " · ".join(fact for fact in facts if fact)
    return f"{heading}<br>\n{md_text(repo.description)}" if repo.description else heading


def outside_row(item: OutsideItem) -> str:
    title = md_text(shorten(item.title))
    return f"- [{title}]({item.url}) · {item.project} · {item.kind}, {item.status}"


def calendar_width(week_count: int) -> int:
    return week_count * CELL_STEP + LABEL_ROOM


def render_readme(user: dict[str, Any], outside: list[OutsideItem], today: date) -> str:
    place = f" in {user['location']}" if user["location"] else ""
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    parts = [
        f"# {user['name'] or LOGIN}",
        f"{ROLE}{place}. {SUMMARY}",
        " · ".join(contact_links(user)),
        "<picture>\n"
        f'  <source media="(prefers-color-scheme: dark)" srcset="{CALENDAR_PATHS["dark"]}">\n'
        f'  <img src="{CALENDAR_PATHS["light"]}" alt="{escape(calendar_alt(user))}" '
        f'width="{calendar_width(len(weeks))}">\n'
        "</picture>",
        activity_line(user),
        "## Featured work",
        "\n\n".join(repo_row(repo) for repo in featured_repos(user)),
    ]
    if outside:
        parts += ["## Open-source work", "\n".join(outside_row(item) for item in outside)]
    parts.append(
        f"<sub>Rebuilt daily by [a script in this repo](build.py). "
        f"Last run {short_date(today)}.</sub>"
    )
    return "\n\n".join(part for part in parts if part) + "\n"


def month_labels(weeks: list[dict[str, Any]], color: str) -> list[str]:
    """One label above the first column of each new month."""
    labels = []
    previous_month = None
    for column, week in enumerate(weeks):
        first_day = date.fromisoformat(week["contributionDays"][0]["date"])
        if previous_month is not None and first_day.month != previous_month:
            labels.append(
                f'<text x="{column * CELL_STEP}" y="{LABEL_BASELINE}" fill="{color}">'
                f"{first_day:%b}</text>"
            )
        previous_month = first_day.month
    return labels


def render_calendar(user: dict[str, Any], theme: str) -> str:
    """Draw the contribution calendar as an SVG with a transparent background."""
    palette = PALETTES[theme]
    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    cells = []
    for column, week in enumerate(weeks):
        for day in week["contributionDays"]:
            row = date.fromisoformat(day["date"]).isoweekday() % DAYS_PER_WEEK
            fill = palette["heat"][LEVELS.index(day["contributionLevel"])]
            cells.append(
                f'<rect x="{column * CELL_STEP}" y="{LABEL_HEIGHT + row * CELL_STEP}" '
                f'width="{CELL_SIZE}" height="{CELL_SIZE}" rx="{CELL_RADIUS}" fill="{fill}"/>'
            )
    width = calendar_width(len(weeks))
    height = LABEL_HEIGHT + DAYS_PER_WEEK * CELL_STEP
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" font-family="{FONT_STACK}" font-size="10">',
        f"<title>{escape(calendar_alt(user))}</title>",
        *month_labels(weeks, palette["label"]),
        *cells,
        "</svg>",
    ]
    return "\n".join(lines) + "\n"


def build(data: dict[str, Any], today: date) -> dict[str, str]:
    """Turn API data into the files to write, keyed by path. No I/O."""
    user = data["user"]
    if user is None:
        raise RuntimeError(f"GitHub has no user named {LOGIN!r}.")
    files = {README_PATH: render_readme(user, outside_work(data["search"]["nodes"]), today)}
    for theme, path in CALENDAR_PATHS.items():
        files[path] = render_calendar(user, theme)
    return files


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set. Export a GitHub token and run again.")
    today = datetime.now(UTC).date()
    files = build(fetch(token, today - timedelta(days=LOOKBACK_DAYS)), today)
    root = Path(__file__).parent
    for path, content in files.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        log.info("Wrote %s", path)


if __name__ == "__main__":
    main()
