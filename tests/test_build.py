import logging
from datetime import date

import pytest

import build
from build import OutsideItem, Repo

TODAY = date(2026, 10, 8)


def repo_node(name: str, **overrides: object) -> dict:
    node = {
        "name": name,
        "url": f"https://github.com/thedandano/{name}",
        "description": f"About {name}",
        "isPrivate": False,
        "isArchived": False,
        "pushedAt": "2026-10-03T12:00:00Z",
        "primaryLanguage": {"name": "Python"},
    }
    return node | overrides


def work_node(typename: str, state: str, **overrides: object) -> dict:
    node = {
        "__typename": typename,
        "title": "Fix the thing",
        "url": "https://github.com/acme/tool/pull/1",
        "state": state,
        "updatedAt": "2026-10-01T00:00:00Z",
        "repository": {"nameWithOwner": "acme/tool", "isPrivate": False},
    }
    return node | overrides


def user_data(**overrides: object) -> dict:
    user = {
        "name": "Dan Sedano",
        "location": "San Diego, CA",
        "websiteUrl": "dsedano.dev",
        "socialAccounts": {
            "nodes": [{"provider": "LINKEDIN", "url": "https://linkedin.com/in/sdedano"}]
        },
        "pinnedItems": {"nodes": [repo_node("callback")]},
        "repositories": {"nodes": [repo_node("recent"), repo_node("blank", description=None)]},
        "contributionsCollection": {
            "totalPullRequestContributions": 153,
            "restrictedContributionsCount": 1993,
            "contributionCalendar": {
                "totalContributions": 2680,
                "weeks": [
                    {
                        "contributionDays": [
                            {"date": "2026-09-27", "contributionLevel": "NONE"},
                            {"date": "2026-09-28", "contributionLevel": "FOURTH_QUARTILE"},
                        ]
                    },
                    {
                        "contributionDays": [
                            {"date": "2026-10-04", "contributionLevel": "FIRST_QUARTILE"},
                        ]
                    },
                ],
            },
        },
    }
    return user | overrides


def test_featured_repos_uses_public_pins():
    user = user_data(
        pinnedItems={"nodes": [repo_node("callback"), repo_node("secret", isPrivate=True)]}
    )

    assert build.featured_repos(user) == [
        Repo(
            name="callback",
            url="https://github.com/thedandano/callback",
            description="About callback",
            language="Python",
            pushed=date(2026, 10, 3),
        )
    ]


def test_featured_repos_falls_back_to_described_repos_and_says_so(caplog):
    user = user_data(pinnedItems={"nodes": []})

    with caplog.at_level(logging.WARNING):
        repos = build.featured_repos(user)

    assert [repo.name for repo in repos] == ["recent"]
    assert caplog.messages == [
        "No public repos are pinned; falling back to the most recently active repos."
    ]


def test_featured_repos_warns_about_a_pin_without_description(caplog):
    user = user_data(
        pinnedItems={"nodes": [repo_node("bare", description=None, primaryLanguage=None)]}
    )

    with caplog.at_level(logging.WARNING):
        repos = build.featured_repos(user)

    assert repos == [
        Repo(
            name="bare",
            url="https://github.com/thedandano/bare",
            description="",
            language="",
            pushed=date(2026, 10, 3),
        )
    ]
    assert caplog.messages == ["Pinned repo bare has no description; showing its name only."]


def test_outside_work_keeps_only_open_or_merged_public_items_newest_first():
    nodes = [
        work_node("PullRequest", "CLOSED", title="Closed without merging"),
        work_node("PullRequest", "MERGED", title="Merged", updatedAt="2026-09-01T00:00:00Z"),
        work_node("Issue", "OPEN", title="Open issue", updatedAt="2026-10-05T00:00:00Z"),
        work_node("Issue", "CLOSED", title="Closed issue"),
        work_node(
            "PullRequest",
            "OPEN",
            title="Private",
            repository={"nameWithOwner": "acme/secret", "isPrivate": True},
        ),
        {},
    ]

    assert build.outside_work(nodes) == [
        OutsideItem(
            title="Open issue",
            url="https://github.com/acme/tool/pull/1",
            project="acme/tool",
            kind="issue",
            status="open",
        ),
        OutsideItem(
            title="Merged",
            url="https://github.com/acme/tool/pull/1",
            project="acme/tool",
            kind="pull request",
            status="merged",
        ),
    ]


def test_md_text_escapes_markdown_and_html():
    assert build.md_text("[AMD] fix a_b <tag> & `x`") == r"\[AMD\] fix a\_b &lt;tag&gt; &amp; \`x\`"


def test_shorten_cuts_long_titles_only():
    assert build.shorten("short") == "short"
    assert build.shorten("x" * 200) == "x" * 79 + "…"


def test_render_readme_full_page():
    outside = [
        OutsideItem(
            title="[AMD] Fix it",
            url="https://github.com/acme/tool/pull/1",
            project="acme/tool",
            kind="pull request",
            status="open",
        )
    ]

    assert build.render_readme(user_data(), outside, TODAY) == (
        "# Dan Sedano\n"
        "\n"
        "AI and backend engineer in San Diego, CA. I build agent systems and the services "
        "behind them, mostly in Python and Rust.\n"
        "\n"
        "[Message me on LinkedIn](https://linkedin.com/in/sdedano) · "
        "[dsedano.dev](https://dsedano.dev)\n"
        "\n"
        "<picture>\n"
        '  <source media="(prefers-color-scheme: dark)" srcset="assets/calendar-dark.svg">\n'
        '  <img src="assets/calendar-light.svg" alt="Contribution calendar: 2,680 '
        'contributions in the last 12 months." width="50">\n'
        "</picture>\n"
        "\n"
        "**2,680** contributions and **153** pull requests in the last 12 months, "
        "counting private work.\n"
        "\n"
        "## Featured work\n"
        "\n"
        "**[callback](https://github.com/thedandano/callback)** · Python · "
        "updated Oct 3, 2026<br>\n"
        "About callback\n"
        "\n"
        "## Open-source work\n"
        "\n"
        "- [\\[AMD\\] Fix it](https://github.com/acme/tool/pull/1) · acme/tool · "
        "pull request, open\n"
        "\n"
        "<sub>Rebuilt daily by [a script in this repo](build.py). Last run Oct 8, 2026.</sub>\n"
    )


def test_render_readme_hides_what_is_missing(caplog):
    user = user_data(location=None, websiteUrl=None, socialAccounts={"nodes": []})
    user["contributionsCollection"]["restrictedContributionsCount"] = 0

    with caplog.at_level(logging.WARNING):
        page = build.render_readme(user, [], TODAY)

    assert page.splitlines()[:4] == [
        "# Dan Sedano",
        "",
        "AI and backend engineer. I build agent systems and the services behind them, "
        "mostly in Python and Rust.",
        "",
    ]
    assert "Open-source work" not in page
    assert "counting private work" not in page
    assert caplog.messages == [
        "No LinkedIn account on the GitHub profile; the page has no main contact link."
    ]


def test_render_calendar_draws_one_cell_per_day_with_month_label():
    assert build.render_calendar(user_data(), "light") == (
        '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="107" '
        'viewBox="0 0 50 107" role="img" '
        "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\" "
        'font-size="10">\n'
        "<title>Contribution calendar: 2,680 contributions in the last 12 months.</title>\n"
        '<text x="13" y="10" fill="#6b655a">Oct</text>\n'
        '<rect x="0" y="16" width="10" height="10" rx="2" fill="#ebe8e2"/>\n'
        '<rect x="0" y="29" width="10" height="10" rx="2" fill="#8a5600"/>\n'
        '<rect x="13" y="16" width="10" height="10" rx="2" fill="#f1d9a8"/>\n'
        "</svg>\n"
    )


def test_build_returns_every_file():
    data = {"user": user_data(), "search": {"nodes": []}}

    assert sorted(build.build(data, TODAY)) == [
        "README.md",
        "assets/calendar-dark.svg",
        "assets/calendar-light.svg",
    ]


def test_build_fails_clearly_when_the_user_is_missing():
    with pytest.raises(RuntimeError, match="GitHub has no user named 'thedandano'"):
        build.build({"user": None, "search": {"nodes": []}}, TODAY)
