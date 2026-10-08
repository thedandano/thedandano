"""Rebuild the profile README from live GitHub data.

The README only holds what GitHub's own profile page does not already show:
a one-line summary, one contact link, and open work in other people's repos.
"""

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
SUMMARY = (
    "AI and backend engineer. "
    "I build agent systems and the services behind them, mostly in Python and Rust."
)

API_HOST = "api.github.com"
API_PATH = "/graphql"
TIMEOUT_SECONDS = 30
LOOKBACK_DAYS = 365
ERROR_BODY_PREVIEW_CHARS = 300

MAX_OUTSIDE_ITEMS = 6
MAX_TITLE_CHARS = 80
README_PATH = "README.md"

# ponytail: one page of 100 results, no paging. Add paging if a year of outside
# work ever passes 100 items.
QUERY = """
query($login: String!, $outside: String!) {
  user(login: $login) {
    socialAccounts(first: 10) { nodes { provider url } }
  }
  search(query: $outside, type: ISSUE, first: 100) {
    nodes {
      __typename
      ... on PullRequest { title url state updatedAt repository { nameWithOwner isPrivate } }
      ... on Issue { title url state updatedAt repository { nameWithOwner isPrivate } }
    }
  }
}
"""

log = logging.getLogger("build")


@dataclass(frozen=True)
class OutsideItem:
    title: str
    url: str
    project: str
    kind: str
    status: str


def fetch(token: str, since: date) -> dict[str, Any]:
    """Run the one GraphQL query the page needs and return its data."""
    outside = (
        f"author:{LOGIN} is:public -user:{LOGIN} created:>={since.isoformat()} sort:updated-desc"
    )
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


def contact_link(user: dict[str, Any]) -> str:
    linkedin = next(
        (a["url"] for a in user["socialAccounts"]["nodes"] if a["provider"] == "LINKEDIN"), None
    )
    if linkedin:
        return f"[Message me on LinkedIn]({linkedin})"
    log.warning("No LinkedIn account on the GitHub profile; the page has no contact link.")
    return ""


def outside_row(item: OutsideItem) -> str:
    title = md_text(shorten(item.title))
    return f"- [{title}]({item.url}) · {item.project} · {item.kind}, {item.status}"


def render_readme(user: dict[str, Any], outside: list[OutsideItem], today: date) -> str:
    parts = [SUMMARY, contact_link(user)]
    if outside:
        parts += ["## Open-source work", "\n".join(outside_row(item) for item in outside)]
    parts.append(
        f"<sub>Rebuilt daily by [a script in this repo](build.py). "
        f"Last run {short_date(today)}.</sub>"
    )
    return "\n\n".join(part for part in parts if part) + "\n"


def build(data: dict[str, Any], today: date) -> str:
    """Turn API data into the README text. No I/O."""
    user = data["user"]
    if user is None:
        raise RuntimeError(f"GitHub has no user named {LOGIN!r}.")
    return render_readme(user, outside_work(data["search"]["nodes"]), today)


def main(root: Path) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is not set. Export a GitHub token and run again.")
    today = datetime.now(UTC).date()
    readme = build(fetch(token, today - timedelta(days=LOOKBACK_DAYS)), today)
    (root / README_PATH).write_text(readme, encoding="utf-8")
    log.info("Wrote %s", README_PATH)


if __name__ == "__main__":
    main(Path(__file__).parent)
