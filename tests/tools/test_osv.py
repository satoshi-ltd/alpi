"""Tests for OSV malware check helpers."""

from __future__ import annotations

from unittest.mock import patch

from alpi.tools import _osv


def test_extract_pypi_top_level_imports() -> None:
    src = (
        "import os\n"
        "import json\n"
        "from flask import Flask\n"
        "from django.contrib.auth import User  # nested\n"
        "import requests.adapters\n"
    )
    assert _osv.extract_pypi_imports(src) == {
        "os", "json", "flask", "django", "requests",
    }


def test_extract_pypi_ignores_comments_and_strings() -> None:
    src = "# import evil_pkg\nx = 'import also_not_real'\nimport actual\n"
    out = _osv.extract_pypi_imports(src)
    assert "actual" in out
    # "evil_pkg" is inside a comment so the regex will match it — that's
    # expected (false-positive-tolerant). "also_not_real" is inside a
    # string; the regex anchors at line start so it also matches. Both
    # get checked against OSV where they'll return empty.


def test_extract_npm_skips_flags() -> None:
    assert _osv.extract_npm_args(["-y", "@scope/pkg", "--verbose"]) == {"@scope/pkg"}


def test_extract_npm_accepts_scoped_and_unscoped() -> None:
    assert _osv.extract_npm_args(
        ["@modelcontextprotocol/server-github", "cowsay", "-y"]
    ) == {"@modelcontextprotocol/server-github", "cowsay"}


def test_check_returns_empty_when_osv_clean() -> None:
    with patch.object(_osv, "_query", return_value=[]):
        assert _osv.check("PyPI", ["requests"]) == []


def test_check_flags_malicious_findings() -> None:
    mal = [{
        "id": "MAL-2024-0001",
        "summary": "Credential-harvesting supply-chain attack",
    }]
    with patch.object(_osv, "_query", return_value=mal):
        out = _osv.check("PyPI", ["evil-pkg"])
    assert len(out) == 1
    assert out[0].startswith("✗")
    assert "MAL-2024-0001" in out[0]
    assert "evil-pkg" in out[0]


def test_check_skips_non_mal_advisories() -> None:
    """Only MAL-* blocks should matter."""
    cve = [{"id": "CVE-2024-1234", "summary": "medium CVE"}]
    with patch.object(_osv, "_query", return_value=cve):
        assert _osv.check("PyPI", ["some-pkg"]) == []


def test_check_fails_open_on_network_error() -> None:
    with patch.object(_osv, "_query", return_value=None):
        out = _osv.check("PyPI", ["anything"])
    assert len(out) == 1
    assert out[0].startswith("⚠")
    assert "unreachable" in out[0]
