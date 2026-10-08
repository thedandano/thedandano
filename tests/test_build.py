import logging
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

import build
from build import OutsideItem

TODAY = date(2026, 10, 8)
SINCE = date(2025, 10, 8)
REAL_TEMPLATE = (Path(__file__).parent.parent / "template.md").read_text(encoding="utf-8")
SUMMARY = (
    "Merged pull requests by week since Sep 2026. Totals, in the order the bars stack "
    "from the bottom: callback 5, Solar stack 1, Other 1."
)


def merged_node(repo: str, merged: str, language: str | None = "Python") -> dict:
    return {
        "mergedAt": f"{merged}T12:00:00Z",
        "repository": {
            "nameWithOwner": repo,
            "primaryLanguage": {"name": language} if language else None,
        },
    }


def outside_node(title: str, private: bool = False) -> dict:
    return {
        "title": title,
        "url": "https://github.com/acme/tool/pull/1",
        "repository": {"nameWithOwner": "acme/tool", "isPrivate": private},
    }


def merged_nodes() -> list[dict]:
    return [
        *[merged_node("thedandano/callback", "2026-09-29") for _ in range(5)],
        merged_node("thedandano/enphase-bridge", "2026-10-06", "Rust"),
        merged_node("someone-else/callback", "2026-10-07", None),
    ]


def api_data(**overrides: object) -> dict:
    data = {
        "user": {
            "socialAccounts": {
                "nodes": [{"provider": "LINKEDIN", "url": "https://linkedin.com/in/sdedano"}]
            }
        },
        "callback": {"releases": {"totalCount": 19}, "latestRelease": {"tagName": "v1.8.0"}},
        "merged": {"issueCount": 1024, "nodes": merged_nodes()},
        "outside": {"nodes": []},
    }
    return data | overrides


def page(has_next: bool, nodes: list[dict], total: int = 2) -> dict:
    merged = {
        "issueCount": total,
        "pageInfo": {"hasNextPage": has_next, "endCursor": "next"},
        "nodes": nodes,
    }
    return {"merged": merged}


def test_outside_work_drops_private_and_empty_results():
    nodes = [outside_node("Merged fix"), outside_node("Secret", private=True), {}]

    assert build.outside_work(nodes) == [
        OutsideItem(
            title="Merged fix", url="https://github.com/acme/tool/pull/1", project="acme/tool"
        )
    ]


def test_languages_need_enough_merged_work_to_be_named():
    assert build.languages([*merged_nodes(), {}]) == ["Python"]


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


def test_weekly_counts_start_at_the_first_week_with_work():
    assert build.weekly_counts([*merged_nodes(), {}], SINCE, TODAY) == {
        date(2026, 9, 28): Counter({"callback": 5}),
        date(2026, 10, 5): Counter({"Solar stack": 1, "Other": 1}),
    }


def test_weekly_counts_never_reach_back_past_the_lookback():
    nodes = [
        merged_node("thedandano/callback", "2020-01-01"),
        merged_node("thedandano/callback", "2026-10-06"),
    ]

    weeks = build.weekly_counts(nodes, date(2026, 9, 30), TODAY)

    assert weeks == {date(2026, 9, 28): Counter(), date(2026, 10, 5): Counter({"callback": 1})}


def test_page_values_are_everything_the_template_asks_for():
    assert build.page_values(api_data(), TODAY) == {
        "merged_count": "1,024",
        "merged_url": (
            "https://github.com/search?q=author%3Athedandano+is%3Apr+is%3Amerged+is%3Apublic"
            "+merged%3A%3E%3D2025-10-08&type=pullrequests"
        ),
        "languages_clause": ", across Python",
        "release_count": "19",
        "latest_release": "v1.8.0",
        "chart_alt": SUMMARY,
        "chart_width": "713",
        "chart_summary": SUMMARY,
        "contact": "[Message me on LinkedIn](https://linkedin.com/in/sdedano)",
        "outside_section": "",
        "today": "Oct 8, 2026",
    }


def test_page_values_list_merged_outside_work_when_there_is_some():
    data = api_data(outside={"nodes": [outside_node("[AMD] Fix")]})

    assert build.page_values(data, TODAY)["outside_section"] == (
        "## Merged in other projects\n"
        "\n"
        "- [\\[AMD\\] Fix](https://github.com/acme/tool/pull/1) · acme/tool · merged"
    )


def test_page_values_say_so_when_there_is_no_contact_link(caplog):
    data = api_data(user={"socialAccounts": {"nodes": []}})

    with caplog.at_level(logging.WARNING):
        contact = build.page_values(data, TODAY)["contact"]

    assert contact == ""
    assert caplog.messages == [
        "No LinkedIn account on the GitHub profile; the page has no contact link."
    ]


def test_render_chart_draws_stacked_bars_with_axis_and_legend():
    weeks = build.weekly_counts(merged_nodes(), SINCE, TODAY)

    assert build.render_chart(weeks, "light") == (
        '<svg xmlns="http://www.w3.org/2000/svg" width="713" height="144" '
        'viewBox="0 0 713 144" role="img" '
        "font-family=\"-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif\" "
        'font-size="10">\n'
        f"<title>{SUMMARY}</title>\n"
        '<line x1="24" y1="8" x2="713" y2="8" stroke="#d1d9e0" stroke-width="1"/>\n'
        '<text x="20" y="12" text-anchor="end" fill="#59636e">10</text>\n'
        '<line x1="24" y1="56" x2="713" y2="56" stroke="#d1d9e0" stroke-width="1"/>\n'
        '<text x="20" y="60" text-anchor="end" fill="#59636e">5</text>\n'
        '<line x1="24" y1="104" x2="713" y2="104" stroke="#d1d9e0" stroke-width="1"/>\n'
        '<text x="20" y="108" text-anchor="end" fill="#59636e">0</text>\n'
        '<rect x="24" y="56" width="16" height="47" rx="1" fill="#2a78d6"/>\n'
        '<rect x="44" y="94.4" width="16" height="8.6" rx="1" fill="#eb6834"/>\n'
        '<rect x="44" y="84.8" width="16" height="8.6" rx="1" fill="#8c959f"/>\n'
        '<text x="24" y="118" fill="#59636e">Sep</text>\n'
        '<rect x="24" y="126" width="10" height="10" rx="1" fill="#2a78d6"/>\n'
        '<text x="38" y="135" fill="#59636e">callback</text>\n'
        '<rect x="102" y="126" width="10" height="10" rx="1" fill="#eb6834"/>\n'
        '<text x="116" y="135" fill="#59636e">Solar stack</text>\n'
        '<rect x="198" y="126" width="10" height="10" rx="1" fill="#8c959f"/>\n'
        '<text x="212" y="135" fill="#59636e">Other</text>\n'
        "</svg>\n"
    )


def test_build_fills_the_real_template_and_draws_both_charts():
    files = build.build(api_data(), TODAY, REAL_TEMPLATE)

    assert sorted(files) == ["README.md", "assets/work-dark.svg", "assets/work-light.svg"]
    assert "$" not in files["README.md"]
    assert "\n\n\n" not in files["README.md"]


def test_build_fills_a_template():
    files = build.build(api_data(), TODAY, "$merged_count merged\n\n$outside_section\n\n$today\n")

    assert files["README.md"] == "1,024 merged\n\nOct 8, 2026\n"


def test_build_fails_clearly_when_the_template_asks_for_something_unknown():
    with pytest.raises(RuntimeError, match="template.md asks for 'nonsense'"):
        build.build(api_data(), TODAY, "$nonsense")


def test_build_fails_clearly_when_the_user_is_missing():
    with pytest.raises(RuntimeError, match="GitHub has no user named 'thedandano'"):
        build.build(api_data(user=None), TODAY, REAL_TEMPLATE)


def test_build_fails_clearly_when_callback_releases_are_missing():
    with pytest.raises(RuntimeError, match="Could not read releases for"):
        build.build(api_data(callback=None), TODAY, REAL_TEMPLATE)


def test_fetch_follows_extra_pages_of_merged_work(monkeypatch):
    pages = iter([page(True, [{"n": 1}]), page(False, [{"n": 2}])])
    cursors = []

    def fake_graphql(token: str, variables: dict) -> dict:
        cursors.append(variables["cursor"])
        return next(pages)

    monkeypatch.setattr(build, "graphql", fake_graphql)

    data = build.fetch("token", SINCE)

    assert data["merged"]["nodes"] == [{"n": 1}, {"n": 2}]
    assert cursors == [None, "next"]


def test_fetch_says_so_when_github_returns_fewer_than_the_total(monkeypatch, caplog):
    monkeypatch.setattr(build, "graphql", lambda token, variables: page(False, [{}], total=1500))

    with caplog.at_level(logging.WARNING):
        build.fetch("token", SINCE)

    assert caplog.messages == [
        "GitHub returned 1 of 1500 merged pull requests; the chart and the language list "
        "leave out the rest. The total count is still exact."
    ]


def test_month_labels_start_at_the_first_week_and_never_crowd():
    weeks = {
        date(2026, 7, 27): Counter(),
        date(2026, 8, 3): Counter(),
        date(2026, 8, 10): Counter(),
        date(2026, 8, 31): Counter(),
        date(2026, 9, 7): Counter(),
    }

    assert build.month_labels(weeks, {"ink": "#000"}) == [
        '<text x="24" y="118" fill="#000">Jul</text>',
        '<text x="104" y="118" fill="#000">Sep</text>',
    ]


def test_chart_summary_says_so_when_there_is_no_merged_work():
    weeks = build.weekly_counts([], SINCE, TODAY)

    assert build.chart_summary(weeks) == "No merged pull requests in the last 12 months."


def test_languages_clause_disappears_without_languages():
    assert [build.languages_clause(names) for names in ([], ["Python", "Rust"])] == [
        "",
        ", across Python and Rust",
    ]


def test_main_writes_the_page_and_charts(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(build, "fetch", lambda token, since: api_data())
    (tmp_path / "template.md").write_text("$merged_count merged\n", encoding="utf-8")

    build.main(tmp_path)

    assert (tmp_path / "README.md").read_text(encoding="utf-8") == "1,024 merged\n"
    assert sorted(path.name for path in (tmp_path / "assets").iterdir()) == [
        "work-dark.svg",
        "work-light.svg",
    ]


def test_main_stops_clearly_without_a_token(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(SystemExit, match="GITHUB_TOKEN is not set"):
        build.main(tmp_path)
