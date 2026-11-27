import html
import importlib.util
import json
import math
import re
import subprocess
import sys
from functools import lru_cache
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
    assert 'data-mark="alpi-twin' in system.split('<header class="kit-header">', 1)[1].split("</header>", 1)[0]
    assert (tmp_path / "boards.css").read_text().count("var(--") >= 2



def test_design_system_covers_conversation_and_workgroups_on_both_clients(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    boards = json.loads((tmp_path / "canvas" / "project" / "canvas.json").read_text())["boards"]
    system = {name for name, frame in boards.items() if frame["page"] == "system"}
    for client in ("Desktop", "Mobile"):
        assert {f"System-{client}Components.dc.html", f"System-{client}Conversation.dc.html", f"System-{client}Workgroup.dc.html"} <= system
    conversation = (tmp_path / "canvas" / "project" / "System-DesktopConversation.dc.html").read_text()
    assert all(label in conversation for label in ("User message", "Alpi message", "Peer reply", "Work line", "Composer"))
    workgroup = (tmp_path / "canvas" / "project" / "System-DesktopWorkgroup.dc.html").read_text()
    assert all(f"Marker · {state}" in workgroup for state in ("task", "working", "done", "skip"))


def test_mobile_draws_the_pairing_safeguards_with_the_copy_the_screen_uses(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    boards = json.loads((project / "canvas.json").read_text())["boards"]
    copy = _node_json(
        "import * as m from './common/onboarding.mjs';"
        "const scan = m.pairHostConfirmation({fact: '@@', scanned: true});"
        "const move = m.pairMoveConfirmation({label: '@@', from: '@@', to: '@@'});"
        "const refused = m.pairingFailure('scanned-token');"
        "const parts = (c) => [c.title, c.confirmLabel, ...c.body.split('@@')];"
        "console.log(JSON.stringify({ScanConfirm: parts(scan), MoveConfirm: parts(move),"
        " TokenRefused: [refused.title, refused.hint, refused.action]}));"
    )
    for name, phrases in copy.items():
        board = f"Phone-Pair{name}.dc.html"
        assert boards[board]["page"] == "mobile", board
        text = _html_text(html.unescape((project / board).read_text()))
        for phrase in phrases:
            assert phrase.strip() in text, (board, phrase)
    refused = (project / "Phone-PairTokenRefused.dc.html").read_text()
    assert "box-shadow: inset 0 0 0 1.5px #6b6b6b" in refused


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
    assert "Worked for 5s" in chat and "wants to run a command" in chat
    overlays = read("Desktop-Overlays.dc.html")
    assert all(group in overlays for group in ("Needs you · 2", "Failing · 3", "Running · 2", "Upcoming · 2", "Keyboard shortcuts", 'data-keys="⌘K"', "Sessions"))
    assert "Tooltip" not in overlays and "was: raw" not in overlays
    profile = read("Desktop-ProfileSettings.dc.html")
    assert 'aria-label="Settings sections"' in profile and "Search settings" in profile and "MCP servers" in profile
    tokens = read("System-Tokens.dc.html")
    shipped = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    for role in ("--text-meta", "--text-small", "--text-ui", "--text-read", "--text-title", "--text-display", "--icon-sm", "--icon-md", "--icon-lg", "--r-xs", "--r-control", "--r-surface", "--r-sheet", "--ctl-32", "--ctl-40", "--ctl-48"):
        value = re.search(rf"{role}:\s*([^;]+);", shipped).group(1).strip()
        assert role in tokens, role
        assert value.removesuffix("px") in tokens, (role, value)
    assert "Contrast · computed from the values" in tokens and "focus ring on fill" in tokens and "Geist Mono" in tokens and "tile 48" in tokens
    desktop_components = read("System-DesktopComponents.dc.html")
    assert "KeyHint" in desktop_components and "Tip" in desktop_components and "iconOnly" in desktop_components
    mobile_components = read("System-MobileComponents.dc.html")
    assert "chat · 16" in mobile_components and "RowState" in mobile_components and "Model chip" in mobile_components
    assert "xxs · 9" not in mobile_components
    for name in ("Phone-Roster.dc.html", "Fold-Chat.dc.html"):
        html = read(name)
        assert 'data-state="needs-you"' in html and "Activity · 2 need you" in html
    activity = read("Phone-Activity.dc.html")
    assert all(text in activity for text in ("Needs you · 2", "Failing · 3", "Upcoming · 3", "Retry all", "Review", "Tomorrow"))
    assert "Scheduled" not in activity
    tool = read("Phone-ToolSheet.dc.html")
    assert "Arguments" in tool and "Output" in tool and "Copy output" in tool
    assert "Select text" in read("Phone-SelectText.dc.html")
    assert "deepseek-v4.1-flash" not in read("Phone-Chat.dc.html")
    details = read("Phone-ChatDetails.dc.html")
    assert all(text in details for text in ("deepseek-v4.1-flash", "Context", "Cost today"))


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


BRAND_BOARDS = ("Mark", "Wordmark", "Icon", "Family", "Eyes", "Motion", "Names", "Workgroups", "Gate")


def design_src():
    sys.path.insert(0, str(REPO / "design" / "src"))


def test_brand_tab_draws_twin_the_twelve_shapes_and_the_shipped_palette(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    boards = json.loads((project / "canvas.json").read_text())["boards"]
    brand = [name for name, frame in sorted(boards.items(), key=lambda kv: kv[1]["y"]) if frame["page"] == "brand"]
    assert brand == [f"Brand-{n}.dc.html" for n in BRAND_BOARDS]
    accents = re.findall(r'\["\w+", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text())
    assert len(accents) == 12 and len(set(accents)) == 12
    family = (project / "Brand-Family.dc.html").read_text()
    assert all(hexv in family for hexv in accents)
    marks = agent_marks()
    assert all(f'data-mark="{shape}"' in family for shape in marks["SHAPE_ORDER"])
    assert "LEGACY_SHAPE" not in marks
    from alpi import mark_shapes
    assert all(f"→ {shape}" in family for shape in mark_shapes.LEGACY_SHAPE.values())
    assert 'data-mark="alpi-twin"' in (project / "Brand-Mark.dc.html").read_text()
    assert 'data-mark="soft-honeycomb"' in (project / "Brand-Workgroups.dc.html").read_text()
    html = (tmp_path / "brand.html").read_text()
    body = html.split('<main class="kit-main">', 1)[1]
    assert "#141414" not in body and "alpaca" not in body
    nav = re.search(r"<nav[^>]*>(.*?)</nav>", html, re.S).group(1)
    assert nav.index("Brand") < nav.index("System") < nav.index("Proposals")


def test_no_view_draws_the_origami_folds_or_the_alpaca(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for name in ("index.html", "desktop.html", "mobile.html", "brand.html", "proposals.html"):
        html = (tmp_path / name).read_text()
        assert "<polygon" not in html.replace('class="pl-', ""), name
        assert "alpi-black.svg" not in html and "alpi-white.svg" not in html, name
        assert not re.search(r"\b(origami|crease)\b", html, re.I), name
    for name in ("desktop.html", "mobile.html"):
        html = (tmp_path / name).read_text()
        assert 'data-mark="alpi-twin' in html and 'data-mark="soft-honeycomb"' in html, name
        twins = re.findall(r'data-mark="alpi-twin[^"]*"[^>]*>(.*?)</svg>', html, re.S)
        assert twins and all("var(--accent" in svg or "stroke=" in svg for svg in twins), name


def test_the_daemon_knows_exactly_the_shapes_the_design_kit_draws():
    sys.path.insert(0, str(REPO))
    design_src()
    import marks
    from alpi import appearance, palette
    assert list(palette.SHAPES) == agent_marks()["SHAPE_ORDER"]
    assert set(marks.SHAPE_ACCENT) == set(palette.SHAPES)
    assert {shape: accent for accent, shape in appearance.SHAPE_OF.items()} == marks.SHAPE_ACCENT
    from alpi import mark_shapes
    assert set(mark_shapes.LEGACY_SHAPE.values()) == set(palette.SHAPES)


def test_the_system_views_draw_their_sample_profiles_from_the_shipped_palette(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    shipped = set(re.findall(r'\["\w+", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text()))
    for name in ("desktop.html", "mobile.html"):
        html = (tmp_path / name).read_text()
        assert "#3d7ea6" not in html and "rgb(56, 153, 226)" in html, name
        assert "#3899e2" in shipped


def test_the_brand_palette_is_the_one_in_common_accents():
    design_src()
    import agent_marks as am
    shipped = dict(re.findall(r'\["(\w+)", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text()))
    assert dict(am.PALETTE) == shipped


def test_the_generated_mark_modules_match_the_design_sources():
    design_src()
    import marks_export
    for name, draw in marks_export.GENERATED.items():
        assert (REPO / "common" / name).read_text() == draw(), f"common/{name}: run python3 design/build.py"
    spec = importlib.util.spec_from_file_location("design_drift", REPO / "design" / "drift.py")
    drift = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drift)
    assert set(drift.GENERATED) == {f"common/{name}" for name in marks_export.GENERATED}


def test_the_mark_modules_are_written_atomically_and_left_alone_when_unchanged(tmp_path, monkeypatch):
    design_src()
    import marks_export
    marks_export.write(str(tmp_path))
    paths = {name: tmp_path / name for name in marks_export.GENERATED}
    stamps = {name: path.stat().st_mtime_ns for name, path in paths.items()}
    opened = []
    real_open = open
    monkeypatch.setattr("builtins.open", lambda file, mode="r", *a, **k: (opened.append((str(file), mode)), real_open(file, mode, *a, **k))[1])
    marks_export.write(str(tmp_path))
    assert not [f for f, mode in opened if "w" in mode]
    assert {name: path.stat().st_mtime_ns for name, path in paths.items()} == stamps
    first = next(iter(paths.values()))
    first.write_text("stale")
    opened.clear()
    marks_export.write(str(tmp_path))
    assert [f for f, mode in opened if "w" in mode] == [f"{first}.tmp"]
    assert first.read_text() == marks_export.GENERATED[first.name]()
    assert not list(tmp_path.glob("*.tmp"))


def test_drift_names_a_stale_generated_mark_module(tmp_path):
    spec = importlib.util.spec_from_file_location("design_drift", REPO / "design" / "drift.py")
    drift = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(drift)
    (tmp_path / "design").mkdir()
    (tmp_path / "common").mkdir()
    (tmp_path / "common" / "agentMarks.mjs").write_text("old")
    (tmp_path / "design" / "build.py").write_text("from pathlib import Path\n(Path(__file__).parent.parent / 'common' / 'agentMarks.mjs').write_text('new')\n")
    assert drift.main(tmp_path) == 1


@lru_cache(maxsize=None)
def _agent_marks_json():
    script = "const m = await import('./common/agentMarks.mjs'); process.stdout.write(JSON.stringify(m));"
    return subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True, cwd=REPO).stdout


def agent_marks():
    return json.loads(_agent_marks_json())


def _curves(d):
    assert re.fullmatch(r"M[^MZ]+Z", d.strip()), "one closed subpath"
    assert set(re.findall(r"[A-Za-z]", d)) == {"M", "C", "Z"}, "curves only"
    nums = [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?", d)]
    p0, out = (nums[0], nums[1]), []
    for i in range(2, len(nums), 6):
        c1, c2, p3 = (nums[i], nums[i + 1]), (nums[i + 2], nums[i + 3]), (nums[i + 4], nums[i + 5])
        out.append((p0, c1, c2, p3))
        p0 = p3
    return out


def _corner(curves):
    worst = 0.0
    for a, b in zip(curves, curves[1:] + curves[:1]):
        u = (a[3][0] - a[2][0], a[3][1] - a[2][1])
        v = (b[1][0] - b[0][0], b[1][1] - b[0][1])
        nu, nv = math.hypot(*u), math.hypot(*v)
        if nu and nv:
            worst = max(worst, math.degrees(math.acos(max(-1.0, min(1.0, (u[0] * v[0] + u[1] * v[1]) / nu / nv)))))
    return worst


def _outline(curves, n=12):
    pts = []
    for p0, c1, c2, p3 in curves:
        for k in range(n):
            t = k / n
            w = ((1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3)
            pts.append(tuple(sum(wi * p[j] for wi, p in zip(w, (p0, c1, c2, p3))) for j in (0, 1)))
    return pts


def _area_centre(pts):
    a = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        cross = x0 * y1 - x1 * y0
        a, cx, cy = a + cross, cx + (x0 + x1) * cross, cy + (y0 + y1) * cross
    a /= 2
    return abs(a), cx / (6 * a), cy / (6 * a)


def _inside(pt, poly):
    x, y, hit = pt[0], pt[1], False
    for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def _eye_pair(m, spec, size, key):
    _, gx, gy, left, right = key
    reach = 0.7 if size < m["SMALL"] else 1
    grow = min(m["EYE_CAP"], max(1, m["EYE_MIN_PX"] * 50 / (m["EYE_PILL_HALF"] * size)))
    gap = max(3, m["EYE_GAP_PX"] * 100 / size) / 2
    eyes = []
    for side, (name, s, dy) in ((-1, left), (1, right)):
        pts = m["EXPRESSIONS"][name]
        inner = -min(p[0] for p in pts)
        scale = min(grow * s, (spec["eyeDx"] - gap) / inner) if inner > 0 else grow * s
        x0, y0 = spec["eyeX"] + reach * gx + side * spec["eyeDx"], spec["eyeY"] + reach * (gy + dy)
        eyes.append([(x0 + side * x * scale, y0 + y * scale) for x, y in pts])
    return eyes


def test_every_mark_passes_the_brand_gate(tmp_path):
    m = agent_marks()
    twelve = m["SHAPE_ORDER"]
    assert len(twelve) == 12 and not {"alpi-twin", "alpi-twin-small"} & set(twelve)
    keys = list(m["STILL"].values()) + [k for seq in m["SEQUENCE"].values() for k in seq["keys"]]
    areas, centres = [], []
    for name, spec in m["SHAPES"].items():
        curves = _curves(spec["d"])
        assert _corner(curves) < 25, name
        body = _outline(curves)
        area, cx, cy = _area_centre(body)
        if name in twelve:
            areas.append(area)
            centres.append((cx, cy))
        for size in (16, 20, 28, 40, 72):
            for key in keys:
                for eye in _eye_pair(m, spec, size, key):
                    assert all(_inside(p, body) for p in eye), (name, size, key)
            rest = _eye_pair(m, spec, 16, m["STILL"]["idle"])[0]
            assert (max(p[0] for p in rest) - min(p[0] for p in rest)) * 16 / 100 >= 1.5, name
    mean = sum(areas) / len(areas)
    assert all(abs(a - mean) / mean < 0.02 for a in areas)
    assert all(abs(cx - 50) <= 1 and abs(cy - 50) <= 4 for cx, cy in centres)
    for ry, rx, rz in m["TURN"]["still"].values():
        assert abs(rz) < max(abs(ry), abs(rx)), "a held angle is a turn in 3D, not a flat tilt"
    assert set(m["STILL"]) | {"offline"} == {"idle", "busy", "working", "needs", "done", "failed", "paused", "offline"}
    assert "disabled" not in m["TURN"]["still"] and "disabled" not in m["TURN"].get("live", [])
    assert m["MOTION_MIN"] == 20 and m["MARK_SIZES"] == {"inline": 16, "row": 24, "header": 28, "list": 40, "tile": 48, "hero": 72}
    for css in (m["MOTION_CSS"], m["TURN_CSS"]):
        assert re.search(r"@media \(prefers-reduced-motion: reduce\)\{[^}]*animation: none", css)
    shapes = (REPO / "common" / "shapes.mjs").read_text()
    assert 'BRAND_INK = { light: "#14110c", dark: "#f3efe6" }' in shapes
    accents = re.findall(r'\["\w+", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text())
    assert len(twelve) * len(accents) == 144
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for board in (tmp_path / "canvas" / "project").glob("Brand-*.dc.html"):
        html = board.read_text()
        assert "filter: blur" not in html, board.name
        for svg in re.findall(r"<svg[^>]*data-mark=[^>]*>.*?</svg>", html, re.S):
            assert "Gradient" not in svg and "<filter" not in svg, board.name
    gate = (REPO / "design" / "AGENTS.md").read_text()
    assert "origami" not in gate.lower() and "Brand gate" in gate


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
    assert radius == _shipped_tokens()["radii"]["xs"] == 6
    banner_css = (REPO / "desktop" / "src" / "primitives" / "AlertBanner.module.css").read_text()
    banner_rule = _css_rule(banner_css, ".banner")
    assert "border-left" not in banner_css and not {"border", "border-radius", "box-shadow", "outline"} & set(banner_rule)
    assert banner_rule["background"] == "color-mix(in srgb, var(--c-danger) var(--banner-tint), var(--bg-pane))"
    flag_css = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.module.css").read_text()
    assert _css_rule(flag_css, ".flag")["border-radius"] == "var(--r-pill)"
    for html in (kit.alert_banner("Lead", "Detail", "Run now"), kit.flag_badge(2), kit.phone_banner("Lead", "Detail"), kit.attention_value(1, "5")):
        assert not re.search(r"border-(left|right|top|bottom)\s*:", html)
        assert not re.search(r"inset\s+-?\d+(\.\d+)?px\s+0\s+0", html)
        assert not re.search(r"inset\s+0\s+-?\d+(\.\d+)?px\s+0\s+0\s+(?!0\.5)", html)
        assert "blur" not in html
    for html in (kit.alert_banner("Lead", "Detail", "Run now"), kit.phone_banner("Lead", "Detail")):
        assert not re.search(r"border-radius:\s*[1-9]", html.split(">", 1)[0])
    for html in (kit.flag_badge(2), kit.attention_value(1, "5")):
        assert "border-radius: 999px" in html
    for html in (kit.alert_banner("Lead", "Detail", "Run now"), kit.phone_banner("Lead", "Detail")):
        assert not re.search(r"border|box-shadow|outline", html.split(">", 1)[0])
        assert "var(--banner-tint, 10%)" in html.split(">", 1)[0]


def test_kit_count_badges_read_the_shared_badge_spec():
    kit = _panel_kit()
    script = f"const m = await import({json.dumps(str(REPO / 'common' / 'countBadge.mjs'))}); process.stdout.write(JSON.stringify(m.countBadgeSpec));"
    spec = json.loads(subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True).stdout)
    import gen

    assert spec["family"] == "sans"
    weight = f"font-weight: {spec['weight']}"
    for html, size in ((gen.m_count_badge(3), spec["size"]["mobile"]), (kit.attention_value(1, "5"), spec["size"]["mobile"]), (kit.flag_badge(2), spec["size"]["desktop"])):
        assert weight in html and "Geist Mono" not in html and "font-family: Geist, " in html
        assert f"min-width: {size}px" in html


def test_kit_badge_uses_the_danger_fill_and_on_danger_pair_in_both_themes(tmp_path):
    kit = _panel_kit()
    tokens = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    css = (REPO / "desktop" / "src" / "primitives" / "BrowseModal.module.css").read_text()
    flag = _css_rule(css, ".flag")
    assert flag["background"] == "var(--c-danger)" and flag["color"] == "var(--on-danger)"
    badge = (REPO / "mobile" / "src" / "components" / "CountBadge.jsx").read_text()
    assert "colors.danger" in badge and "colors.onDanger" in badge and "colors.dangerText" not in badge
    pill = (REPO / "mobile" / "src" / "components" / "AttentionPill.jsx").read_text()
    assert "CountBadge" in pill and "colors.dangerText" not in pill
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
    for phrase in ("instructions loaded on demand", "User · memory · agent", "disable · fire · delete · add new", "native callable functions"):
        assert phrase in settings
        assert phrase in _html_text(studies.m_settings_rows(False))
    flagged = _html_text(studies.m_settings_rows(True))
    for phrase in ("1 fails lint", "2 over their limit", "1 failed", "Cron jobs"):
        assert phrase in flagged
    for screen in (REPO / "mobile" / "src" / "features" / "brain" / "SkillsList.jsx", REPO / "mobile" / "src" / "features" / "brain" / "MemoryList.jsx"):
        assert "Needs you" in screen.read_text()
    assert "Needs you · 1" in _html_text(studies.m_skill_list(True))
    assert "Needs you · 2" in _html_text(studies.m_memory_list(True))
    sched = _html_text(studies.m_schedule_list(True))
    labels = [label for _, label in kit.JOB_GROUPS]
    assert [sched.index(label) for label in labels] == sorted(sched.index(label) for label in labels)
    job = (REPO / "mobile" / "src" / "features" / "schedule" / "JobDetail.jsx").read_text()
    assert "[next, nextRunCountdown(job)].filter(Boolean).join(' · ')" in job
    page = _html_text(studies.m_schedule_page(True))
    assert "Sat 10 Oct at 07:30 · in 23h" in page
    assert "07:30 · failed" not in page


def _node_json(script):
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True, cwd=REPO)
    return json.loads(out.stdout)


def test_kit_busy_mark_and_pre_run_strip_follow_the_shipped_sources(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    busy = _node_json("import * as b from './common/busy.mjs'; process.stdout.write(JSON.stringify({delay: b.BUSY_DELAY_MS, min: b.BUSY_MIN_MS, px: b.BUSY_MIN_MARK_PX}));")
    index = (tmp_path / "index.html").read_text()
    small = "alpi-twin-small" if busy["px"] < 24 else "alpi-twin"
    assert f'width="{busy["px"]}" height="{busy["px"]}" role="img" aria-label="{small} turning busy"' in index
    assert 'aria-label="alpi-twin turning busy"' in index and 'class="am-a am-sig-pulse"' in index
    assert f'after {busy["delay"]} ms, at least {busy["min"]} ms on screen' in index
    jsx = (REPO / "desktop" / "src" / "primitives" / "PipelineStages.jsx").read_text()
    ghosts = len(re.search(r"GHOST_WIDTHS\s*=\s*\[([^\]]*)\]", jsx).group(1).split(","))
    board = (tmp_path / "canvas" / "project" / "System-DesktopWorkgroup.dc.html").read_text()
    assert board.count('class="pl-ghost"') == ghosts
    strip = (REPO / "mobile" / "src" / "features" / "chat" / "PipelineStrip.jsx").read_text()
    bars = len(re.search(r"PLACEHOLDER_WIDTHS\s*=\s*\[([^\]]*)\]", strip).group(1).split(","))
    phone = (tmp_path / "canvas" / "project" / "System-MobileWorkgroup.dc.html").read_text()
    assert phone.count('class="pl-bar"') == bars


def _workgroup_marks():
    import importlib

    design_src()
    return importlib.import_module("workgroup_marks")


def _contrast(a, b):
    def lum(hex_):
        ch = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in ch]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_kit_lights_every_hub_accent_at_3_to_1_on_both_themes():
    wg = _workgroup_marks()
    import agent_marks as am

    accents = [hex_ for _, hex_ in re.findall(r'\["(\w+)", "(#[0-9a-f]{6})"\]', (REPO / "common" / "accents.mjs").read_text())]
    assert len(accents) == 12
    for accent in accents:
        for ground in (am.LIGHT_GROUNDS[0], am.LIGHT_GROUNDS[1], am.DARK_GROUNDS[1], am.DARK_GROUNDS[2]):
            tone = wg.lit_tone(accent, ground)
            assert _contrast(tone, ground) >= 3, (accent, ground)
            html = wg.honeycomb(accent, 40, "running", phase=(1, 3), ground=ground, still=True)
            assert am.rgb(tone) in html and am.rgb(accent) not in html or tone == accent


def test_kit_pops_the_waiting_cell_only_above_row_size():
    wg = _workgroup_marks()
    assert "scale(" in wg.honeycomb("#3899e2", wg.HEADER, "needs", cell="top", still=True).split("<svg", 1)[1]
    assert "scale(" not in wg.honeycomb("#3899e2", wg.ROW, "needs", cell="top", still=True).split("<svg", 1)[1]


def _shipped_tokens():
    return _node_json("import * as t from './common/tokens.mjs'; process.stdout.write(JSON.stringify({radii: t.radii, bannerTint: t.bannerTint, stateFill: t.stateFill, focusRing: t.focusRing}));")


def test_kit_has_no_design_system_boards_left_once_shipped():
    design_src()
    from proposals import PROPOSALS

    assert not [p["id"] for p in PROPOSALS if p["id"].startswith("DS.")]
    assert not (REPO / "design" / "src" / "shape_language_proposals.py").exists()
    assert not list((REPO / "design" / "canvas" / "project").glob("Proposals-DS.*"))


def cb_composer():
    import conversation_boards as cb
    return cb.d_composer()


def test_kit_draws_the_shipped_radius_scale_and_nesting():
    _panel_kit()
    import desktop_boards as db
    import desktop_overlays as do
    import gen
    import mobile_overlays as mo

    t = _shipped_tokens()
    r = t["radii"]
    assert gen.RADII == r and set(r) == {"xs", "control", "surface", "sheet", "pill"}
    assert (r["xs"], r["control"], r["surface"], r["sheet"]) == (6, 12, 20, 28)
    pill = f"border-radius: {r['pill']}px"
    assert pill in db.button("Send", "primary") and gen.ALPI_ACCENT in db.button("Send", "primary")
    assert pill in db.chip("on", "on") and pill in db.selectish("medium") and pill in db.iconbtn("more", "More")
    assert f"border-radius: {r['control']}px" in db.field_input("doc") and f"border-radius: {r['control']}px" in db.sb_row("", "doc")
    seg = db.seg(("All", "Paused"), "All")
    assert f"padding: 4px; border-radius: {r['pill']}px" in seg and "box-shadow: 0 1px 3px" in seg
    assert gen.NEST == r["surface"] - r["control"] == 8
    assert f"border-radius: {r['sheet']}px" in do.modal("Delete", "", do.dialog_footer("Delete"))
    assert "box-shadow" not in do.dialog_footer("Delete").split(">", 1)[0]
    assert f"border-radius: {r['sheet']}px {r['sheet']}px 0 0" in mo.sheet(390, 844, "Effort", "", "")
    assert f"border-radius: {r['xs']}px" in do.checkbox(True) and "border:" not in do.checkbox(True).split(">", 1)[0]
    assert "inset 0 0 0 1.5px" in do.checkbox(False)
    assert f"border-radius: {r['sheet']}px" in cb_composer() and f"border-radius: {r['surface']}px" in do.toast_box("Saved", "#3fb37a")


def test_kit_draws_surfaces_by_tone_and_lists_with_a_neutral_fill():
    _panel_kit()
    import conversation_boards as cb
    import desktop_boards as db
    import desktop_overlays as do
    import gen

    t = _shipped_tokens()
    chosen = f"rgba(20,20,20,{t['stateFill']['selected']:g})"
    row = db.sb_row("", "doc", "6w", active=True)
    assert 'aria-current="page"' in row and f"background: {chosen}" in row
    assert "inset 3px" not in row and "margin: 0 -12px" not in row and f"border-radius: {t['radii']['control']}px" in row
    assert "border-right" not in db.d_sidebar(400)
    assert "box-shadow" not in gen.WELL and "box-shadow" not in gen.M_WELL
    group = gen.m_group(gen.m_row("A"), gen.m_row("B"))
    assert f"gap: {gen.TILE_GAP}px" in group and "0.5px" not in group
    composer = cb.m_composer()
    assert "border-top" not in composer and "border: 1px" not in composer
    lit = do.menu_item("gear", "Open settings", highlight=True)
    assert f"background: {chosen}" in lit and "outline" not in lit
    assert "background" not in do.menu_sep()


def test_kit_banners_read_the_shared_tints_and_match_the_desktop_role():
    kit = _panel_kit()
    import gen

    tint = _shipped_tokens()["bannerTint"]
    for mode in ("light", "dark"):
        assert f"var(--banner-tint, {round(tint[mode]['tint'] * 100)}%)" in gen.banner_surface("danger", mode)
        assert f"var(--banner-tint-quiet, {round(tint[mode]['quiet'] * 100)}%)" in gen.banner_surface("info", mode)
    assert gen.BANNER_TEXT["danger"] == "#b73737" and gen.BANNER_HUE["warning"] == "#e08a3c"
    jsx = (REPO / "desktop" / "src" / "primitives" / "AlertBanner.jsx").read_text()
    role = re.search(r'className=\{styles\.banner\} role="(\w+)"', jsx).group(1)
    assert f'role="{role}"' in kit.alert_banner("Lead", "Detail")


def test_kit_views_draw_the_ds_v2_shell_on_both_clients():
    _panel_kit()
    import conversation_boards as cb
    import desktop_boards as db
    import gen

    t = _node_json("import * as t from './common/tokens.mjs'; process.stdout.write(JSON.stringify(t.shell));")
    side = db.d_sidebar(800)
    assert f"width: {t['sidebar']}px" in side and side.count("data-tile=") >= 2
    assert "<button" not in db.conn_head() and "New session" not in side and 'data-icon="pencil"' not in side
    footer = db.sidebar_footer("0.9.23")
    assert 'aria-label="Search · ⌘K"' in footer and 'aria-label="Search · ⌘K"' in side.split("Workgroups")[-1]
    assert "border-radius: 999px" in db.footer_button("Search · ⌘K", "search")
    row = db.sb_row("", "doc", "6w")
    assert f"height: {t['rowDesktop']}px" in row and "font-size: 15px" in row and "width: 24px" in row
    assert "text-transform" not in db.sb_section("Profiles") and "font-size: 14px" in db.sb_section("Profiles")
    head = db.d_hero(db.h1("doc", "", "#3899e2"), "deepseek-v4.1-flash", "", "#3899e2")
    assert f"height: {t['header']}px" in head and "deepseek" not in head and "linear-gradient" in head
    composer = cb.d_composer(name="doc", model_name="deepseek-v4.1-flash")
    assert f"min-height: {t['composer']}px" in composer and "border-radius: 28px" in composer and "font-size: 16px" in composer
    assert "mention" not in composer and "outline" not in composer and 'aria-label="Send · ⌘↵"' in composer
    chat = db.desktop_chat()
    assert f"max-width: {t['stream']}px" in chat and "border-top" not in chat
    assert "background: #f2f2f2" in cb.d_user("hi") and "background" not in cb.d_assistant("hi", meta=False)
    phone_head = gen.m_chat_header("doc", "#3899e2", "")
    assert "deepseek" not in phone_head and "grid-template-columns: 88px 1fr 88px" in phone_head
    roster = gen.m_roster_row("doc", "#3899e2", compact=False)
    assert f"min-height: {t['rowPhone']}px" in roster and "width: 40px; height: 40px" in roster
    assert gen.m_tiles().count("data-tile=") >= 2
    phone = gen.m_composer()
    assert "min-height: 56px" in phone and "deepseek" not in phone and "border-top" not in phone


def test_kit_views_keep_the_type_floor_and_mono_for_machine_text_only(tmp_path):
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    project = tmp_path / "canvas" / "project"
    for page in sorted(project.glob("*.dc.html")):
        if not page.name.startswith(("Desktop-", "Phone-", "Fold-")):
            continue
        html = page.read_text()
        for style in re.findall(r'style="([^"]*font-size: [0-9.]+px[^"]*)"', html):
            size = float(re.search(r"font-size: ([0-9.]+)px", style).group(1))
            assert size >= 12, (page.name, style[:120])
            assert "text-transform: uppercase" not in style, (page.name, style[:120])
        if page.name.startswith("Phone-"):
            assert not re.search(r"border-(top|bottom):\s*[0-9.]+px solid", html), page.name


def test_marks_wear_filled_eyes_in_the_paper_tone_of_the_theme(tmp_path):
    tokens = (REPO / "common" / "tokens.mjs").read_text()
    assert re.search(r'const light = \{[^}]*markEye: "#ffffff"', tokens, re.S)
    assert re.search(r'const dark = \{[^}]*markEye: "#000000"', tokens, re.S)
    css = (REPO / "desktop" / "src" / "styles" / "tokens.css").read_text()
    assert css.count("--mark-eye: #ffffff") == 1 and css.count("--mark-eye: #000000") == 2
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for page in ("desktop.html", "mobile.html", "index.html"):
        svgs = re.findall(r"<svg[^>]*data-mark=[^>]*>.*?</svg>", (tmp_path / page).read_text(), re.S)
        assert svgs, page
        assert not [s for s in svgs if "<mask" in s], page
        assert any('fill="var(--mark-eye)"' in s for s in svgs), page
    brand = (tmp_path / "brand.html").read_text()
    faces = re.findall(r'<svg[^>]*aria-label="(?:rest|wide|squint|happy|sleepy|sad|look|blink)" data-mark="round"[^>]*>.*?</svg>', brand, re.S)
    assert len(faces) == 8 and all(s.count('fill="var(--mark-eye)"') == 2 and "<mask" not in s for s in faces)


def test_kit_panels_and_charts_match_the_shipped_rows_and_bars():
    _panel_kit()
    import chart_studies as cs
    import notif_studies as ns
    import profile_panel_studies as pps
    import mobile_attention_studies as mas
    import gen

    svg = cs.vbar_svg([("AI", [3, 4], "#000"), ("Human", [1, 2], "#666")], ["Mon", "Tue"], 200, 120, stacked=True)
    assert "<rect" not in svg and svg.count("A4,4 0 0 1") == 4
    single = cs.vbar_svg([("AI", [3, 4], "#000")], ["Mon", "Tue"], 200, 120)
    assert single.count("A4,4 0 0 1") == 4
    assert "border-radius: 0 4px 4px 0" in cs.hbar_html([("Spa", 3), ("Rooms", 5)], 240)
    row = pps.skill_row("hotel-intake", "inactive", "4.2kb", "blurb")
    assert "margin-left" not in row and "border-radius: 999px; border:" not in row
    job = pps.job_row({**pps.JOBS[0], "state": "paused", "word": "paused"})
    assert "margin-left" not in job and "border-radius: 999px" not in job
    assert "padding-left: 15px" not in mas.list_row(pps.JOBS[1]) and "border-radius: 999px" not in mas.list_row(pps.JOBS[1])
    for compact, name_weight in ((True, 600), (False, 700)):
        roster = gen.m_roster_row("yuri", "#f36a8a", ts="6w", unread=True, compact=compact)
        assert 'font-weight: 500; font-size: 12px; line-height: 1; color: #6b6b6b">6w<' in roster
        assert re.search(rf'font-weight: {name_weight};[^"]*">yuri<', roster)
    desk, phone = ns.a_row(ns.VIEW, ns.ROWS[0]), ns.phone_row(ns.VIEW, ns.ROWS[0])
    for unread in (desk, phone):
        assert "width: 6px; padding-top" not in unread and "border-radius: 999px; background: #141414" not in unread
    assert f'color: {ns.VIEW["ink"]}; font-weight: 600' in phone
    when = re.search(rf'<span style="([^"]*)">{re.escape(ns.ROWS[0]["at"])}</span>', desk).group(1)
    assert "font-weight: 600" in when and f'color: {ns.VIEW["ink"]}' in when and "Mono" not in when
    assert "Mono" not in re.search(rf'<span style="([^"]*)">· {re.escape(ns.ROWS[0]["conn"])}</span>', desk).group(1)


def test_kit_profile_names_pass_4_5_to_1_on_the_ground_of_each_theme():
    html = (REPO / "design" / "canvas" / "project" / "Desktop-Chat.dc.html").read_text()
    pairs = re.findall(r"light-dark\((#[0-9a-f]{6}), (#[0-9a-f]{6})\)", html)
    assert pairs
    for light, dark in pairs:
        assert light != dark
        assert _contrast(light, "#ffffff") >= 4.5 and _contrast(dark, "#1a1a1a") >= 4.5, (light, dark)


def test_marks_draw_a_pale_accent_deeper_in_light_so_the_white_eyes_hold_3_to_1(tmp_path):
    design_src()
    import agent_marks as am

    pale = []
    for _, accent in am.PALETTE:
        light = am.mark_tone(accent)
        assert _contrast(light, "#ffffff") >= 3, accent
        assert am.body_fill(accent, "dark") == am.rgb(accent)
        if light != accent:
            pale.append(accent)
            assert am.body_fill(accent) == f"light-dark({am.rgb(light)}, {am.rgb(accent)})"
            assert am.body_fill(accent, "light") == am.rgb(light)
    assert len(pale) == 7
    subprocess.run([sys.executable, str(REPO / "design" / "build.py"), "--out", str(tmp_path)], check=True, capture_output=True)
    for page in ("desktop.html", "mobile.html", "index.html"):
        svgs = re.findall(r"<svg[^>]*data-mark=[^>]*>.*?</svg>", (tmp_path / page).read_text(), re.S)
        assert any("light-dark(" in s for s in svgs), page
        for accent in pale:
            assert not [s for s in svgs if f'fill="{am.rgb(accent)}"' in s], (page, accent)



def test_literal_boards_and_ink_names_never_switch_to_a_dark_name_tone():
    project = REPO / "design" / "canvas" / "project"
    assert "light-dark(" not in (project / "System-Tokens.dc.html").read_text()
    for board in project.glob("*.dc.html"):
        assert "#898580" not in board.read_text(), board.name
