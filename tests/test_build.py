import logging
from datetime import date

import pytest

import build
from build import OutsideItem

TODAY = date(2026, 10, 8)
SEARCH_URL = (
    "https://github.com/search?q=author%3Athedandano+is%3Apr+is%3Amerged+is%3Apublic"
    "+merged%3A%3E%3D2025-10-08&type=pullrequests"
)
CLAIMS = (
    "# I don't let go of a problem, I ship, and I keep it simple.\n"
    "\n"
    "**Tenacious.** In [callback](https://github.com/thedandano/callback), a test case that "
    "had always passed suddenly failed. I re-ran it twice against the old version to prove "
    "the cause was the AI model's randomness and not my change. [I wrote it down in the repo.]"
    "(https://github.com/thedandano/callback/blob/1be24db29568d6c5ed2a65221f0be361abcd1920/"
    "CLAUDE.md#L83-L94)\n"
    "\n"
    f"**Action oriented.** [1,024 merged pull requests]({SEARCH_URL}) in public repos in the "
    "last 12 months, across Python and Rust. "
    "[callback](https://github.com/thedandano/callback/releases) has shipped 19 releases, "
    "most recently v1.8.0.\n"
    "\n"
    "**Pragmatic.** callback [grades resumes with plain rules]"
    "(https://github.com/thedandano/callback/blob/main/callback/scorer.py), not another AI "
    "call, so the same resume always gets the same score. "
    "[enphase-bridge](https://github.com/thedandano/enphase-bridge) keeps solar data in one "
    "SQLite file and is small enough to run on a Raspberry Pi.\n"
    "\n"
)
FOOTER = "<sub>Rebuilt daily by [a script in this repo](build.py). Last run Oct 8, 2026.</sub>\n"


def language_node(name: str | None) -> dict:
    return {"repository": {"primaryLanguage": {"name": name} if name else None}}


def outside_node(title: str, private: bool = False) -> dict:
    return {
        "title": title,
        "url": "https://github.com/acme/tool/pull/1",
        "repository": {"nameWithOwner": "acme/tool", "isPrivate": private},
    }


def api_data(**overrides: object) -> dict:
    data = {
        "user": {
            "socialAccounts": {
                "nodes": [{"provider": "LINKEDIN", "url": "https://linkedin.com/in/sdedano"}]
            }
        },
        "callback": {"releases": {"totalCount": 19}, "latestRelease": {"tagName": "v1.8.0"}},
        "merged": {
            "issueCount": 1024,
            "nodes": [language_node("Rust"), language_node("Python"), language_node("Python")],
        },
        "outside": {"nodes": []},
    }
    return data | overrides


def test_outside_work_drops_private_and_empty_results():
    nodes = [outside_node("Merged fix"), outside_node("Secret", private=True), {}]

    assert build.outside_work(nodes) == [
        OutsideItem(
            title="Merged fix", url="https://github.com/acme/tool/pull/1", project="acme/tool"
        )
    ]


def test_languages_are_ordered_by_use_and_skip_repos_without_one():
    nodes = [
        language_node("Rust"),
        language_node(None),
        language_node("Python"),
        {},
        language_node("Python"),
    ]

    assert build.languages(nodes) == ["Python", "Rust"]


def test_word_list_reads_naturally():
    assert [build.word_list(words) for words in ([], ["a"], ["a", "b"], ["a", "b", "c"])] == [
        "",
        "a",
        "a and b",
        "a, b, and c",
    ]


def test_md_text_escapes_markdown_and_html():
    assert build.md_text("[AMD] fix a_b <tag> & `x`") == r"\[AMD\] fix a\_b &lt;tag&gt; &amp; \`x\`"


def test_shorten_cuts_long_titles_only():
    assert build.shorten("short") == "short"
    assert build.shorten("x" * 200) == "x" * 79 + "…"


def test_build_full_page_without_outside_work():
    assert build.build(api_data(), TODAY) == (
        CLAIMS + "[Message me on LinkedIn](https://linkedin.com/in/sdedano)\n\n" + FOOTER
    )


def test_build_lists_merged_outside_work_when_there_is_some():
    data = api_data(outside={"nodes": [outside_node("[AMD] Fix")]})

    assert build.build(data, TODAY) == (
        CLAIMS
        + "[Message me on LinkedIn](https://linkedin.com/in/sdedano)\n"
        + "\n"
        + "## Merged in other projects\n"
        + "\n"
        + "- [\\[AMD\\] Fix](https://github.com/acme/tool/pull/1) · acme/tool · merged\n"
        + "\n"
        + FOOTER
    )


def test_build_says_so_when_there_is_no_contact_link(caplog):
    data = api_data(user={"socialAccounts": {"nodes": []}})

    with caplog.at_level(logging.WARNING):
        page = build.build(data, TODAY)

    assert page == CLAIMS + FOOTER
    assert caplog.messages == [
        "No LinkedIn account on the GitHub profile; the page has no contact link."
    ]


def test_build_fails_clearly_when_the_user_is_missing():
    with pytest.raises(RuntimeError, match="GitHub has no user named 'thedandano'"):
        build.build(api_data(user=None), TODAY)


def test_build_fails_clearly_when_callback_releases_are_missing():
    with pytest.raises(RuntimeError, match="Could not read releases for"):
        build.build(api_data(callback=None), TODAY)


def test_main_writes_the_readme(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(build, "fetch", lambda token, since: api_data())

    build.main(tmp_path)

    assert (tmp_path / "README.md").read_text(encoding="utf-8").startswith("# I don't let go")


def test_main_stops_clearly_without_a_token(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit, match="GITHUB_TOKEN is not set"):
        build.main(tmp_path)
