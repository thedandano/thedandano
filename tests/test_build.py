import logging
from datetime import date

import pytest

import build
from build import OutsideItem

TODAY = date(2026, 10, 8)
USER = {
    "socialAccounts": {
        "nodes": [{"provider": "LINKEDIN", "url": "https://linkedin.com/in/sdedano"}]
    }
}


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


def test_build_full_page():
    data = {
        "user": USER,
        "search": {"nodes": [work_node("PullRequest", "OPEN", title="[AMD] Fix")]},
    }

    assert build.build(data, TODAY) == (
        "AI and backend engineer. I build agent systems and the services behind them, "
        "mostly in Python and Rust.\n"
        "\n"
        "[Message me on LinkedIn](https://linkedin.com/in/sdedano)\n"
        "\n"
        "## Open-source work\n"
        "\n"
        "- [\\[AMD\\] Fix](https://github.com/acme/tool/pull/1) · acme/tool · "
        "pull request, open\n"
        "\n"
        "<sub>Rebuilt daily by [a script in this repo](build.py). Last run Oct 8, 2026.</sub>\n"
    )


def test_build_hides_what_is_missing_and_says_so(caplog):
    data = {"user": {"socialAccounts": {"nodes": []}}, "search": {"nodes": []}}

    with caplog.at_level(logging.WARNING):
        page = build.build(data, TODAY)

    assert page == (
        "AI and backend engineer. I build agent systems and the services behind them, "
        "mostly in Python and Rust.\n"
        "\n"
        "<sub>Rebuilt daily by [a script in this repo](build.py). Last run Oct 8, 2026.</sub>\n"
    )
    assert caplog.messages == [
        "No LinkedIn account on the GitHub profile; the page has no contact link."
    ]


def test_build_fails_clearly_when_the_user_is_missing():
    with pytest.raises(RuntimeError, match="GitHub has no user named 'thedandano'"):
        build.build({"user": None, "search": {"nodes": []}}, TODAY)


def test_main_writes_the_readme(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(
        build, "fetch", lambda token, since: {"user": USER, "search": {"nodes": []}}
    )

    build.main(tmp_path)

    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith("AI and backend")


def test_main_stops_clearly_without_a_token(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit, match="GITHUB_TOKEN is not set"):
        build.main(tmp_path)
