"""Rebuild the profile README from live GitHub data.

The README says who Dan is in three claims, each backed by merged work that a
reader can click. It repeats nothing GitHub's profile page already shows.
"""

from __future__ import annotations

import http.client
import json
import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html import escape
from http import HTTPStatus
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

LOGIN = "thedandano"
HEADLINE = "I don't let go of a problem, I ship, and I keep it simple."
CALLBACK_URL = f"https://github.com/{LOGIN}/callback"
# Pinned to one commit so the line numbers keep pointing at the same write-up.
VARIANCE_WRITEUP_URL = (
    f"{CALLBACK_URL}/blob/1be24db29568d6c5ed2a65221f0be361abcd1920/CLAUDE.md#L83-L94"
)
SCORER_URL = f"{CALLBACK_URL}/blob/main/callback/scorer.py"
ENPHASE_BRIDGE_URL = f"https://github.com/{LOGIN}/enphase-bridge"

API_HOST = "api.github.com"
API_PATH = "/graphql"
TIMEOUT_SECONDS = 30
LOOKBACK_DAYS = 365
ERROR_BODY_PREVIEW_CHARS = 300

MAX_OUTSIDE_ITEMS = 6
MAX_TITLE_CHARS = 80
PAIR = 2  # two words join with "and" alone; three or more need commas
README_PATH = "README.md"

# ponytail: languages come from the 100 most recently updated merged pull requests,
# no paging. The total count is exact either way. Add paging if the language list
# ever looks wrong.
QUERY = """
query($login: String!, $merged: String!, $outside: String!) {
  user(login: $login) {
    socialAccounts(first: 10) { nodes { provider url } }
  }
  callback: repository(owner: $login, name: "callback") {
    releases { totalCount }
    latestRelease { tagName }
  }
  merged: search(query: $merged, type: ISSUE, first: 100) {
    issueCount
    nodes { ... on PullRequest { repository { primaryLanguage { name } } } }
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


def fetch(token: str, since: date) -> dict[str, Any]:
    """Run the one GraphQL query the page needs and return its data."""
    merged = merged_query(since)
    variables = {
        "login": LOGIN,
        "merged": f"{merged} sort:updated-desc",
        "outside": f"{merged} -user:{LOGIN} sort:updated-desc",
    }
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
    return [name for name, _ in Counter(names).most_common()]


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


def outside_row(item: OutsideItem) -> str:
    return f"- [{md_text(shorten(item.title))}]({item.url}) · {item.project} · merged"


def claims(data: dict[str, Any], since: date) -> list[str]:
    """The three claims about Dan, each with a link to merged work that backs it."""
    callback = data["callback"]
    if callback is None or callback["latestRelease"] is None:
        raise RuntimeError(f"Could not read releases for {CALLBACK_URL}; was the repo renamed?")
    merged = data["merged"]
    search_url = f"https://github.com/search?q={quote_plus(merged_query(since))}&type=pullrequests"
    across = word_list(languages(merged["nodes"]))
    return [
        f"**Tenacious.** In [callback]({CALLBACK_URL}), a test case that had always passed "
        "suddenly failed. I re-ran it twice against the old version to prove the cause was "
        f"the AI model's randomness and not my change. [I wrote it down in the repo.]"
        f"({VARIANCE_WRITEUP_URL})",
        f"**Action oriented.** [{merged['issueCount']:,} merged pull requests]({search_url}) "
        f"in public repos in the last 12 months, across {across}. "
        f"[callback]({CALLBACK_URL}/releases) has shipped "
        f"{callback['releases']['totalCount']} releases, most recently "
        f"{callback['latestRelease']['tagName']}.",
        f"**Pragmatic.** callback [grades resumes with plain rules]({SCORER_URL}), not another "
        "AI call, so the same resume always gets the same score. "
        f"[enphase-bridge]({ENPHASE_BRIDGE_URL}) keeps solar data in one SQLite file and "
        "is small enough to run on a Raspberry Pi.",
    ]


def build(data: dict[str, Any], today: date) -> str:
    """Turn API data into the README text. No I/O."""
    user = data["user"]
    if user is None:
        raise RuntimeError(f"GitHub has no user named {LOGIN!r}.")
    since = today - timedelta(days=LOOKBACK_DAYS)
    parts = [f"# {HEADLINE}", *claims(data, since), contact_link(user)]
    outside = outside_work(data["outside"]["nodes"])
    if outside:
        parts += ["## Merged in other projects", "\n".join(outside_row(item) for item in outside)]
    parts.append(
        f"<sub>Rebuilt daily by [a script in this repo](build.py). "
        f"Last run {short_date(today)}.</sub>"
    )
    return "\n\n".join(part for part in parts if part) + "\n"


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
