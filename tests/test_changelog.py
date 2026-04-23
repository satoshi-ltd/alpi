"""Changelog generator — parses the repo's own git history."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from alpi import changelog, cli


def test_split_prefix_extracts_type() -> None:
    assert changelog._split_prefix("setup: do a thing") == ("setup", "do a thing")
    assert changelog._split_prefix("gateway:compact") == ("gateway", "compact")


def test_split_prefix_on_unprefixed_returns_empty() -> None:
    assert changelog._split_prefix("no prefix here") == ("", "no prefix here")


def test_clean_subject_strips_trailers() -> None:
    raw = "setup: do it\n\nCo-Authored-By: Foo <bar@x>\n🤖 Generated with Claude"
    assert changelog._clean_subject(raw) == "setup: do it"


def test_is_skippable_for_version_bumps() -> None:
    assert changelog._is_skippable("version: 1.2.3")
    assert changelog._is_skippable("bump: 1.2.3")
    assert not changelog._is_skippable("setup: add wizard")


def test_group_walks_releases_and_closes_at_bump() -> None:
    commits = [
        changelog.Commit("aaa", "2026-01-01", "setup: a"),
        changelog.Commit("bbb", "2026-01-02", "gateway: b"),  # bump → v0.1.0
        changelog.Commit("ccc", "2026-01-03", "cli: c"),      # bump → v0.1.1
    ]
    bumps = [("bbb", "0.1.0", "2026-01-02"), ("ccc", "0.1.1", "2026-01-03")]
    releases = changelog._group(commits, bumps)
    assert len(releases) == 2
    assert releases[0].version == "0.1.0"
    assert [c.sha for c in releases[0].commits] == ["aaa", "bbb"]
    assert releases[1].version == "0.1.1"
    assert [c.sha for c in releases[1].commits] == ["ccc"]


def test_render_groups_by_prefix_and_sorts_newest_first() -> None:
    releases = [
        changelog.Release(
            version="0.1.0", date="2026-01-02",
            commits=[
                changelog.Commit("aaa", "2026-01-01", "setup: one"),
                changelog.Commit("bbb", "2026-01-02", "gateway: two"),
            ],
        ),
        changelog.Release(
            version="0.2.0", date="2026-01-05",
            commits=[changelog.Commit("ccc", "2026-01-05", "cli: three")],
        ),
    ]
    md = changelog.render_markdown(releases)
    # Newest first.
    assert md.index("v0.2.0") < md.index("v0.1.0")
    # Grouped by prefix, alphabetical within a release.
    assert md.index("### gateway") < md.index("### setup")
    assert "- one (`aaa`)" in md
    assert "- three (`ccc`)" in md


def test_render_empty_release_shows_placeholder() -> None:
    md = changelog.render_markdown([
        changelog.Release(version="0.1.0", date="2026-01-01", commits=[])
    ])
    assert "_No user-visible changes._" in md


def test_cli_release_notes_renders_something(tmp_path, monkeypatch) -> None:
    """Full-stack check — runs against the real repo history."""
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    result = CliRunner().invoke(cli.main, ["release", "notes"])
    assert result.exit_code == 0
    assert result.output.startswith("# Changelog")
    # Sanity: multiple versions parsed.
    assert result.output.count("## v") > 1


def test_cli_release_notes_writes_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ALPI_HOME", str(tmp_path))
    out = tmp_path / "OUT.md"
    result = CliRunner().invoke(cli.main, ["release", "notes", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert out.read_text().startswith("# Changelog")
    assert "wrote" in result.output
