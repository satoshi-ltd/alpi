import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_design_kit_builds_every_page_from_the_shipped_tokens(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    pages = {name: (tmp_path / name).read_text() for name in ("index.html", "desktop.html", "mobile.html", "proposals.html")}
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
    assert {p["id"] for p in index["pages"]} == {"system", "desktop", "mobile", "proposals"}
    assert all("page" in frame for frame in index["boards"].values())


def test_every_design_page_links_a_favicon_copied_inside_design(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    source = (REPO / "site" / "assets" / "alpi-favicon.svg").read_bytes()
    pages = sorted(tmp_path.glob("*.html")) + sorted((tmp_path / "canvas" / "project").glob("*.html"))
    assert len(list(tmp_path.glob("*.html"))) == 4 and len(pages) > 4
    for page in pages:
        href = re.search(r'<link rel="icon" href="([^"]+)" type="image/svg\+xml">', page.read_text()).group(1)
        assert not href.startswith(("/", "http"))
        icon = (page.parent / href).resolve()
        assert icon.is_relative_to(tmp_path.resolve()), page
        assert icon.read_bytes() == source, page
    for page in (REPO / "design").glob("*.html"):
        assert 'href="favicon.svg"' in page.read_text()
    assert (REPO / "design" / "favicon.svg").read_bytes() == source


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


ROADMAP = REPO / "docs" / "ROADMAP.md"
TASK_TYPES = {"bug", "feature", "chore", "ui", "verify", "deploy", "decision"}


def roadmap_tasks():
    text = ROADMAP.read_text()
    text = text[text.index("\n## Queue"):text.index("\n## Discarded")]
    raw = len(re.findall(r"^- \*\*", text, re.M))
    tasks = {}
    for match in re.finditer(r"^- \*\*(.+?)\*\* — .*\n  `(\w+) · ", text, re.M):
        block = text[match.end():].split("\n- **", 1)[0]
        tasks[match.group(1)] = (match.group(2), block)
    assert raw > 0 and len(tasks) == raw
    assert {kind for kind, _ in tasks.values()} <= TASK_TYPES
    return tasks


def proposal_ids(html):
    raw = html.count("data-proposal=")
    ids = re.findall(r'data-proposal="([^"]+)"', html)
    assert len(ids) == raw
    return ids


def build_kit(out, monkeypatch=None, proposals=None):
    sys.path.insert(0, str(REPO / "design"))
    sys.path.insert(0, str(REPO / "design" / "src"))
    import build
    import proposals as proposals_module

    if proposals is not None:
        monkeypatch.setattr(proposals_module, "PROPOSAL_BOARDS", proposals)
    build.build(str(out))


def test_committed_design_files_match_what_the_generator_writes(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    generated = [p.relative_to(tmp_path) for p in tmp_path.rglob("*") if p.is_file() and p.name != "canvas.json"]
    assert {Path("index.html"), Path("proposals.html"), Path("boards.css")} <= set(generated)
    for rel in generated:
        assert (REPO / "design" / rel).read_text() == (tmp_path / rel).read_text(), f"{rel}: run python3 design/build.py"
    committed = {p.name for p in (REPO / "design" / "canvas" / "project").glob("*.dc.html")}
    assert committed == {p.name for p in generated if p.name.endswith(".dc.html")}


def test_design_has_no_open_work_tab(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    assert not (tmp_path / "audit.html").exists()
    assert not (REPO / "design" / "audit.html").exists()
    for name in ("index.html", "desktop.html", "mobile.html", "proposals.html"):
        nav = re.search(r"<nav[^>]*>(.*?)</nav>", (tmp_path / name).read_text(), re.S).group(1)
        assert re.findall(r">([^<]+)</a>", nav) == ["System", "Desktop", "Mobile", "Proposals"]


def test_every_ui_task_has_a_board_on_the_proposals_page(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    ids = proposal_ids((tmp_path / "proposals.html").read_text())
    sys.path.insert(0, str(REPO / "design" / "src"))
    from proposals import PROPOSALS
    assert ids == [p["id"] for p in PROPOSALS]
    frames = json.loads((tmp_path / "canvas" / "project" / "canvas.json").read_text())["boards"]
    assert sorted(name for name, frame in frames.items() if frame["page"] == "proposals") == sorted(f"Proposals-{i}.dc.html" for i in ids)
    for task, (kind, block) in roadmap_tasks().items():
        if kind == "ui":
            assert task in ids, task
            assert "board" in block, task


def test_a_board_without_a_task_is_a_pending_proposal_and_carries_its_parts(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    sys.path.insert(0, str(REPO / "design" / "src"))
    from proposals import PROPOSALS
    tasks = roadmap_tasks()
    for p in PROPOSALS:
        board = (tmp_path / "canvas" / "project" / f"Proposals-{p['id']}.dc.html").read_text()
        assert f'data-proposal="{p["id"]}"' in board
        assert all(part in board for part in (p["title"].replace("&", "&amp;"), "Now", "Proposed", "Accept"))
        assert p["why"] and p["accept"] and p["area"]
        if p["id"] in tasks:
            assert tasks[p["id"]][0] == "ui"


def test_proposals_page_shows_an_empty_state_without_boards(tmp_path, monkeypatch):
    build_kit(tmp_path, monkeypatch, proposals=[])
    html = (tmp_path / "proposals.html").read_text()
    assert proposal_ids(html) == []
    assert "No proposals open" in html


def test_a_parser_that_misses_a_board_fails_loudly():
    html = '<div data-proposal="UX.1"></div><div data-proposal=UX.2></div>'
    try:
        proposal_ids(html)
    except AssertionError:
        return
    raise AssertionError("a marker the parser cannot read must not pass")


def test_design_system_keeps_the_motion_and_conversation_boards(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    conversation = (project / "System-DesktopConversation.dc.html").read_text()
    assert "Thought for 3s" in conversation and "Inline approval" in conversation
    assert "System-Motion.dc.html" in json.loads((project / "canvas.json").read_text())["boards"]


def test_board_ids_are_unique_and_split_tasks_name_their_board():
    sys.path.insert(0, str(REPO / "design" / "src"))
    from proposals import PROPOSALS
    ids = [p["id"] for p in PROPOSALS]
    assert len(ids) == len(set(ids))
    tasks = roadmap_tasks()
    follows = re.compile(r"the interface follows board (\S+?)\.?(?:\s|$)")
    for board in ids:
        if board in tasks:
            assert tasks[board][0] == "ui", board
        if board.startswith("UI-") and board[3:] in tasks:
            kind, block = tasks[board[3:]]
            assert kind != "ui", board
            assert f"the interface follows board {board}" in block, board
    for task, (kind, block) in tasks.items():
        if kind == "ui":
            assert f"board {task}" in block, task
        for named in follows.findall(block):
            assert named in ids, (task, named)
            assert named == f"UI-{task}", (task, named)
    if "THINK.1" in tasks:
        assert tasks["THINK.1"][0] == "ui"
        assert "a test pins the static live row's classes" in " ".join(tasks["THINK.1"][1].split())


def test_the_design_contract_lives_in_design_and_scripts_holds_no_design_file():
    assert (REPO / "design" / "AGENTS.md").is_file()
    assert (REPO / "design" / "drift.py").is_file()
    for claude in (REPO / "CLAUDE.md", REPO / "design" / "CLAUDE.md"):
        if claude.exists():
            assert claude.read_text().strip() == "@AGENTS.md"
    assert not [p.name for p in (REPO / "scripts").iterdir() if "design" in p.name.lower()]
