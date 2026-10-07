import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_design_kit_builds_every_page_from_the_shipped_tokens(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    pages = {name: (tmp_path / name).read_text() for name in ("index.html", "desktop.html", "mobile.html", "brand.html", "proposals.html")}
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
    assert [p["id"] for p in index["pages"]] == ["brand", "system", "desktop", "mobile", "proposals"]
    assert all("page" in frame for frame in index["boards"].values())


def test_every_design_page_links_a_favicon_copied_inside_design(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    source = (REPO / "site" / "assets" / "alpi-favicon.svg").read_bytes()
    pages = sorted(tmp_path.glob("*.html")) + sorted((tmp_path / "canvas" / "project").glob("*.html"))
    assert len(list(tmp_path.glob("*.html"))) == 5 and len(pages) > 5
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
    assert "#141414" not in body and "#6b6b6b" not in body
    system = (tmp_path / "index.html").read_text()
    assert "#141414" in system
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
    for name in ("index.html", "desktop.html", "mobile.html", "brand.html", "proposals.html"):
        nav = re.search(r"<nav[^>]*>(.*?)</nav>", (tmp_path / name).read_text(), re.S).group(1)
        assert re.findall(r">([^<]+)</a>", nav) == ["Brand", "System", "Desktop", "Mobile", "Proposals"]


def test_brand_tab_draws_every_pair_from_the_shipped_accents_and_mark(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    boards = json.loads((project / "canvas.json").read_text())["boards"]
    brand = sorted(name for name, frame in boards.items() if frame["page"] == "brand")
    assert brand == sorted(f"Brand-{n}.dc.html" for n in ("Mark", "Pairs", "Palette", "Motion"))
    accents = re.findall(r'\["\w+", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text())
    assert len(accents) == 12 and len(set(accents)) == 12
    palette = (project / "Brand-Palette.dc.html").read_text()
    assert all(hexv in palette for hexv in accents)
    pairs = (project / "Brand-Pairs.dc.html").read_text()
    assert all(f'aria-label="{name}"' in pairs for name in ("diamond", "house", "heart", "plane", "shield", "rocket", "star", "tree", "box", "crown", "feather", "bulb"))
    source_facets = len(re.findall(r'<path d="', (REPO / "site" / "assets" / "alpi-black.svg").read_text()))
    assert source_facets == 12 and (project / "Brand-Mark.dc.html").read_text().count('aria-label="alpaca"') >= 1
    html = (tmp_path / "brand.html").read_text()
    assert "#141414" not in html.split('<main class="kit-main">', 1)[1]
    nav = re.search(r"<nav[^>]*>(.*?)</nav>", html, re.S).group(1)
    assert nav.index("Brand") < nav.index("System") < nav.index("Proposals")


def test_the_daemon_knows_exactly_the_folds_the_design_kit_draws():
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "design" / "src"))
    import folds
    from alpi import palette
    assert list(palette.FOLDS) == list(folds.SHAPE_ORDER)


def test_the_system_views_draw_their_sample_profiles_from_the_shipped_palette(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    shipped = set(re.findall(r'\["\w+", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text()))
    for name in ("desktop.html", "mobile.html"):
        html = (tmp_path / name).read_text()
        assert "#3d7ea6" not in html and "#3899e2" in html, name
        assert "#3899e2" in shipped


def test_the_brand_palette_is_the_one_in_common_accents():
    sys.path.insert(0, str(REPO / "design" / "src"))
    import folds
    shipped = dict(re.findall(r'\["(\w+)", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text()))
    assert dict(folds.palette("bath")) == shipped


def test_every_brand_object_passes_the_origami_gate(tmp_path):
    sys.path.insert(0, str(REPO / "design" / "src"))
    import folds
    assert set(folds.SHAPES) == set(folds.MODELS)
    for name, make in folds.SHAPES.items():
        shapes = folds.facets(name)
        assert 2 <= len(shapes) <= folds.MAX_FACETS, name
        pts = [p for poly, _ in shapes for p in poly]
        w = max(p[0] for p in pts) - min(p[0] for p in pts)
        h = max(p[1] for p in pts) - min(p[1] for p in pts)
        assert min(w, h) / max(w, h) >= folds.MIN_ASPECT, name
        assert {tone for _, tone in shapes} <= {folds.LIGHT, folds.BASE, folds.SHADE}, name
        assert not folds.four_fold_chiral(name), name
        assert folds.one_piece(name), name
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for board in (tmp_path / "canvas" / "project").glob("Brand-*.dc.html"):
        html = board.read_text()
        assert "drop-shadow" not in html and "filter: blur" not in html, board.name
        assert "<linearGradient" not in html and "<radialGradient" not in html, board.name


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


def test_the_design_contract_lives_in_design_and_scripts_holds_no_design_file():
    assert (REPO / "design" / "AGENTS.md").is_file()
    assert (REPO / "design" / "drift.py").is_file()
    for claude in (REPO / "CLAUDE.md", REPO / "design" / "CLAUDE.md"):
        if claude.exists():
            assert claude.read_text().strip() == "@AGENTS.md"
    assert not [p.name for p in (REPO / "scripts").iterdir() if "design" in p.name.lower()]


def _panel_kit():
    import importlib

    src = str(REPO / "design" / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    importlib.import_module("desktop_boards")
    return importlib.import_module("panel_kit")


def _css_rule(css, selector):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    match = re.search(r"(?<![\w-])" + re.escape(selector) + r"\s*\{([^}]*)\}", css)
    assert match, selector
    props = {}
    for declaration in match.group(1).split(";"):
        if ":" in declaration:
            name, value = declaration.split(":", 1)
            props[name.strip()] = " ".join(value.split())
    return props


def _jsx_condition(jsx, class_ref):
    match = re.search(r"\{\s*([^<{}]+?)\s*\?\s*\(?\s*<span[^>]*" + re.escape(class_ref), jsx, re.S)
    assert match, class_ref
    return " ".join(match.group(1).split())


def _html_text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html)).strip()


def test_kit_tabs_are_the_profile_panels_in_the_shipped_order():
    kit = _panel_kit()
    source = (REPO / "desktop" / "src" / "lib" / "profilePanels.js").read_text()
    labels = re.findall(r'label:\s*"([^"]+)"', source)
    assert labels and tuple(labels) == tuple(kit.TABS)
    html = _html_text(kit.head("Skills", 5))
    assert [html.index(label) for label in labels] == sorted(html.index(label) for label in labels)


def test_kit_draws_the_count_on_the_open_tab_and_the_flag_on_any_tab_like_browse_modal():
    kit = _panel_kit()
    jsx = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.jsx").read_text()
    assert _jsx_condition(jsx, "styles.count") == "on && count != null"
    assert _jsx_condition(jsx, "styles.flag") == "shell?.badges?.[s.id]?.count > 0"
    head = kit.head("Skills", 5, {"Memories": 2, "Schedules": 1})
    assert head.count('data-part="count"') == 1
    assert head.count('data-part="flag"') == 2
    assert head.index('data-part="count"') > head.index("Skills") and head.index('data-part="count"') < head.index("Tools")
    assert kit.head("Tools", 37).count('data-part="flag"') == 0


def test_kit_sidebar_and_search_row_follow_browse_modal_css():
    kit = _panel_kit()
    css = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.module.css").read_text()
    tokens = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    assert _css_rule(css, ".sidebar")["background"] == "var(--bg-side)"
    assert int(re.search(r"--modal-side:\s*(\d+)px", tokens).group(1)) == kit.SIDE_W
    wrap_rule = _css_rule(css, ".searchWrap")
    assert not {"background", "box-shadow", "border-radius", "border"} & set(wrap_rule)
    input_rule = _css_rule(css, ".searchInput")
    assert input_rule["background"] == "transparent" and input_rule["border"] == "0"
    window = kit.window("Skills", 5, None, "Search skills…", "", "", 200)
    side = re.search(r'<div style="width: 340px;[^>]*background: ([^;]+);', window)
    assert side and side.group(1) == re.search(r"--bg-side:\s*(#[0-9a-f]{6})", tokens).group(1)
    search = kit.search_row("Search skills…")
    assert "background" not in search and "border-radius" not in search and "0 0 0 0.5px" not in search


def test_kit_schedule_groups_are_the_shipped_job_groups():
    kit = _panel_kit()
    source = (REPO / "common" / "attention.mjs").read_text()
    body = source.split("export function jobGroups", 1)[1]
    shipped = re.findall(r'id:\s*"(\w+)"\s*,\s*label:\s*"([^"]+)"', body)
    assert shipped and tuple(shipped) == tuple(kit.JOB_GROUPS)
    import profile_panel_studies as studies

    text = _html_text(studies.schedules_window(True))
    positions = [text.index(label) for _, label in shipped]
    assert positions == sorted(positions)
    assert "Needs you" not in _html_text(studies.schedules_window(False))


def test_kit_banner_and_badge_follow_the_paper_direction():
    kit = _panel_kit()
    tokens = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    radius = int(re.search(r"--r-xs:\s*(\d+)px", tokens).group(1))
    assert radius <= 4
    banner_css = (REPO / "desktop" / "src" / "primitives" / "AlertBanner.module.css").read_text()
    assert "border-left" not in banner_css and _css_rule(banner_css, ".banner")["border-radius"] == "var(--r-xs)"
    flag_css = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.module.css").read_text()
    assert _css_rule(flag_css, ".flag")["border-radius"] == "var(--r-xs)"
    for html in (kit.alert_banner("Lead", "Detail", "Run now"), kit.flag_badge(2), kit.phone_banner("Lead", "Detail"), kit.attention_value(1, "5")):
        assert not re.search(r"border-(left|right|top|bottom)\s*:", html)
        assert not re.search(r"inset\s+-?\d+(\.\d+)?px\s+0\s+0", html)
        assert not re.search(r"inset\s+0\s+-?\d+(\.\d+)?px\s+0\s+0\s+(?!0\.5)", html)
        assert not re.search(r"blur|999px", html)
        assert all(int(px) <= 4 for px in re.findall(r"border-radius:\s*(\d+)px", html))


def test_kit_badge_uses_the_danger_fill_and_on_danger_pair_in_both_themes(tmp_path):
    kit = _panel_kit()
    tokens = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    css = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.module.css").read_text()
    flag = _css_rule(css, ".flag")
    assert flag["background"] == "var(--c-danger)" and flag["color"] == "var(--on-danger)"
    pill = (REPO / "mobile" / "src" / "components" / "AttentionPill.jsx").read_text()
    assert "colors.danger" in pill and "colors.onDanger" in pill and "colors.dangerText" not in pill
    assert re.search(r"--c-danger:\s*" + kit.DANGER_FILL, tokens)
    assert re.search(r"--on-danger:\s*#ffffff", tokens)
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    built = (tmp_path / "desktop.html").read_text() + (tmp_path / "mobile.html").read_text()
    badges = re.findall(r'data-part="flag" style="([^"]*)"', built)
    assert badges
    for style in badges:
        assert "background: var(--c-danger);" in style and "color: var(--on-danger)" in style
        assert "--c-danger-text" not in style and "--bg-pane" not in style
    assert "background: var(--c-danger); display: inline-flex" in built


def test_kit_phone_rows_use_the_attention_wording_and_groups_of_the_mobile_app():
    kit = _panel_kit()
    import profile_panel_studies as studies

    attention = (REPO / "common" / "attention.mjs").read_text()
    assert "fails lint" in attention and re.search(r"over \$\{[^}]*\"their\"[^}]*\} limit", attention)
    assert re.search(r"\$\{items\.length\} failed", attention)
    settings = (REPO / "mobile" / "app" / "profile" / "[id]" / "settings.jsx").read_text()
    for phrase in ("instructions loaded on demand", "USER · MEMORY · AGENT", "disable · fire · delete · add new", "native callable functions"):
        assert phrase in settings
        assert phrase in _html_text(studies.m_settings_rows(False))
    flagged = _html_text(studies.m_settings_rows(True))
    for phrase in ("1 fails lint", "2 over their limit", "1 failed", "Cron jobs"):
        assert phrase in flagged
    for screen in ("skills/index.jsx", "memory/index.jsx"):
        assert "Needs you" in (REPO / "mobile" / "app" / "profile" / "[id]" / "brain" / screen).read_text()
    assert "Needs you · 1" in _html_text(studies.m_skill_list(True))
    assert "Needs you · 2" in _html_text(studies.m_memory_list(True))
    sched = _html_text(studies.m_schedule_list(True))
    labels = [label for _, label in kit.JOB_GROUPS]
    assert [sched.index(label) for label in labels] == sorted(sched.index(label) for label in labels)
    job = (REPO / "mobile" / "app" / "profile" / "[id]" / "schedule" / "[job].jsx").read_text()
    assert "[next, nextRunWord(job)].filter(Boolean).join(' · ')" in job
    assert "tomorrow 07:30 · failed" in _html_text(studies.m_schedule_page(True))


def _node_json(script):
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True, cwd=REPO)
    return json.loads(out.stdout)


def test_kit_busy_wave_and_pre_run_strip_follow_the_shipped_sources(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    shipped = _node_json("import {busyFacetDelays} from './common/busy.mjs'; process.stdout.write(JSON.stringify(busyFacetDelays()));")
    index = (tmp_path / "index.html").read_text()
    drawn = re.findall(r'<polygon points="[^"]+" class="(\w+)-f" style="fill: ([^;]+); animation-delay: ([-\d.]+)s"', index)
    assert drawn
    by_key = {}
    for key, fill, delay in drawn:
        assert fill == "var(--accent)"
        by_key.setdefault(key, []).append(float(delay))
    assert all(delays == shipped for delays in by_key.values())
    jsx = (REPO / "desktop" / "src" / "primitives" / "PipelineStages.jsx").read_text()
    ghosts = len(re.search(r"GHOST_WIDTHS\s*=\s*\[([^\]]*)\]", jsx).group(1).split(","))
    board = (tmp_path / "canvas" / "project" / "System-DesktopWorkgroup.dc.html").read_text()
    assert board.count('class="pl-ghost"') == ghosts
    strip = (REPO / "mobile" / "src" / "features" / "chat" / "PipelineStrip.jsx").read_text()
    bars = len(re.search(r"PLACEHOLDER_WIDTHS\s*=\s*\[([^\]]*)\]", strip).group(1).split(","))
    phone = (tmp_path / "canvas" / "project" / "System-MobileWorkgroup.dc.html").read_text()
    assert phone.count('class="pl-bar"') == bars
