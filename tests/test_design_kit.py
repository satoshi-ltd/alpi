import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_design_kit_builds_every_page_from_the_shipped_tokens(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    pages = {name: (tmp_path / name).read_text() for name in ("index.html", "desktop.html", "mobile.html", "audit.html")}
    for html in pages.values():
        assert 'href="kit.css"' in html
        assert 'src="kit.js"' in html and 'data-kit-theme="dark"' in html
        assert all(f'href="{name}"' in html for name in pages)
    tokens = (REPO / "common" / "tokens.mjs").read_text()
    light = re.search(r"const light = \{(.*?)\};", tokens, re.S).group(1)
    for hexv in re.findall(r"#[0-9a-f]{6}", light):
        assert hexv in pages["index.html"], hexv
    versions = {name: json.loads((REPO / name / "package.json").read_text())["version"] for name in ("desktop", "mobile")}
    assert f"desktop {versions['desktop']} · mobile {versions['mobile']}" in pages["index.html"]
    index = json.loads((tmp_path / "canvas" / "project" / "canvas.json").read_text())
    assert {p["id"] for p in index["pages"]} == {"system", "desktop", "mobile", "audit"}
    assert all("page" in frame for frame in index["boards"].values())


def test_design_boards_follow_the_theme_except_the_literal_swatches(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    desktop = (tmp_path / "desktop.html").read_text()
    assert "var(--ink)" in desktop and "var(--bg-pane)" in desktop
    body = desktop.split('<main class="kit-main">', 1)[1]
    assert "#0b1117" not in body and "#626e7d" not in body
    system = (tmp_path / "index.html").read_text()
    assert "#0b1117" in system
    assert 'class="logo-dark"' in system and (tmp_path / "boards.css").read_text().count("var(--") >= 2

