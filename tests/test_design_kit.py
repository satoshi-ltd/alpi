import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_design_kit_builds_every_page_from_the_shipped_tokens(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    pages = {name: (tmp_path / name).read_text() for name in ("index.html", "desktop.html", "mobile.html", "audit.html", "proposals.html")}
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
    assert {p["id"] for p in index["pages"]} == {"system", "desktop", "mobile", "audit", "proposals"}
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



def test_design_system_covers_conversation_and_workgroups_on_both_clients(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    boards = json.loads((tmp_path / "canvas" / "project" / "canvas.json").read_text())["boards"]
    system = {name for name, frame in boards.items() if frame["page"] == "system"}
    for client in ("Desktop", "Mobile"):
        assert {f"System-{client}Components.dc.html", f"System-{client}Conversation.dc.html", f"System-{client}Workgroup.dc.html"} <= system
    conversation = (tmp_path / "canvas" / "project" / "System-DesktopConversation.dc.html").read_text()
    assert all(label in conversation for label in ("User message", "Alpi message", "Peer reply", "Process block", "Composer"))
    workgroup = (tmp_path / "canvas" / "project" / "System-DesktopWorkgroup.dc.html").read_text()
    assert all(f"Marker · {state}" in workgroup for state in ("task", "working", "done", "skip"))


def test_design_kit_draws_what_desktop_0_7_and_mobile_0_6_shipped(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    boards = json.loads((project / "canvas.json").read_text())["boards"]
    read = lambda name: (project / name).read_text()
    for name in ("Phone-Activity.dc.html", "Fold-Activity.dc.html", "Phone-Roster.dc.html", "Phone-ToolSheet.dc.html", "Phone-SelectText.dc.html"):
        assert boards[name]["page"] == "mobile"
    chat = read("Desktop-Chat.dc.html")
    assert all(f'data-state="{s}"' in chat for s in ("needs-you", "failed", "working"))
    assert "Pinned" in chat and 'aria-label="phase 2 of 4"' in chat and "Activity · 2 need you" in chat
    assert "Thought for 4s" in chat and "wants to run a command" in chat
    overlays = read("Desktop-Overlays.dc.html")
    assert all(group in overlays for group in ("Needs you · 2", "Running · 2", "Scheduled", "Keyboard shortcuts", 'data-keys="⌘K"', "Sessions"))
    assert "Tooltip" not in overlays and "was: raw" not in overlays
    profile = read("Desktop-ProfileSettings.dc.html")
    assert 'aria-label="Settings sections"' in profile and "Search settings" in profile and "MCP Servers" in profile
    tokens = read("System-Tokens.dc.html")
    shipped = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    for role in ("--text-meta", "--text-ui", "--text-chat", "--text-title", "--text-display", "--text-hero", "--dur-1", "--dur-2", "--dur-loop", "--dur-spin", "--icon-sm", "--icon-md"):
        value = re.search(rf"{role}:\s*([^;]+);", shipped).group(1).strip()
        assert role in tokens, role
        assert value.removesuffix("px") in tokens, (role, value)
    desktop_components = read("System-DesktopComponents.dc.html")
    assert "KeyHint" in desktop_components and "Tip" in desktop_components and "iconOnly" in desktop_components
    mobile_components = read("System-MobileComponents.dc.html")
    assert "chat · 16" in mobile_components and "RowState" in mobile_components and "Model chip" in mobile_components
    assert "xxs · 9" not in mobile_components
    for name in ("Phone-Roster.dc.html", "Fold-Chat.dc.html"):
        html = read(name)
        assert 'data-state="needs-you"' in html and "Activity · 2 need you" in html
    assert "Needs you · 2" in read("Phone-Activity.dc.html") and "Review" in read("Phone-Activity.dc.html")
    tool = read("Phone-ToolSheet.dc.html")
    assert "Arguments" in tool and "Output" in tool and "Copy output" in tool
    assert "Select text" in read("Phone-SelectText.dc.html")
    assert "deepseek-v4.1-flash · medium" in read("Phone-Chat.dc.html")


def test_design_proposals_list_only_open_work(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    sys.path.insert(0, str(REPO / "design" / "src"))
    from proposals_boards import PROPOSALS
    project = tmp_path / "canvas" / "project"
    assert [p.name for p in project.glob("Proposals-*.dc.html")] == ["Proposals-Overview.dc.html"]
    overview = (project / "Proposals-Overview.dc.html").read_text()
    for _key, _who, area, *_rest in PROPOSALS:
        assert area in overview
    conversation = (project / "System-DesktopConversation.dc.html").read_text()
    assert "Thought for 3s" in conversation and "Inline approval" in conversation
    assert "System-Motion.dc.html" in json.loads((project / "canvas.json").read_text())["boards"]
