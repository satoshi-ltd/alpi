#!/usr/bin/env python3
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(HERE, "src"))

import gen  # noqa: E402
from desktop_boards import DESKTOP  # noqa: E402

FONT_LINK = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap">'
PAGES = (
    ("index.html", "system", "System", "Design system", "One token file feeds both clients. Colour, type, space, radius and every primitive of desktop and mobile, drawn from the values that ship."),
    ("desktop.html", "desktop", "Desktop", "Desktop", "Tauri client, 1280 wide. Every screen as the code paints it, with the sidebar it shares."),
    ("mobile.html", "mobile", "Mobile", "Phone and Fold", "Expo client. The phone keeps its own grammar; a fold or tablet renders the desktop layout at scale."),
    ("audit.html", "audit", "Open work", "Open work", "What is still pending between the two clients. Shipped rows leave the table; the changelogs keep the history."),
    ("proposals.html", "proposals", "Proposals", "Where to go next", "What is left from the UX and UI review of both clients against the agent and chat apps shipping now. A row leaves when it ships."),
)


def version(rel):
    with open(os.path.join(REPO, rel)) as f:
        return json.load(f)["version"]


# Boards are drawn in the light palette; the kit rewrites those literals to the token sheet so the theme switch reaches them.
THEMED = (
    ("rgba(11,17,23,0.07)", "var(--line)"),
    ("rgba(11,17,23,0.14)", "var(--line-2)"),
    ("rgba(11,17,23,0.04)", "var(--hover)"),
    ("rgba(11,17,23,0.06)", "var(--selected)"),
    ("#ffffff", "var(--bg-pane)"),
    ("#eef0f2", "var(--bg)"),
    ("#f5f6f8", "var(--bg-side)"),
    ("#f1f3f5", "var(--bg-side)"),
    ("#0b1117", "var(--ink)"),
    ("#3d4955", "var(--ink-2)"),
    ("#626e7d", "var(--ink-3)"),
    ("#b1bac4", "var(--ink-4)"),
    ("#8a5a0a", "var(--accent)"),
    ("#b73737", "var(--c-danger-text)"),
    ("#b3470e", "var(--c-warning-text)"),
)
LITERAL_BOARDS = {"System-Tokens.dc.html"}


def board_root(path):
    with open(path) as f:
        html = f.read()
    start = html.index("</helmet>\n") + len("</helmet>\n")
    end = html.index("\n</x-dc>")
    root = html[start:end]
    if os.path.basename(path) in LITERAL_BOARDS:
        return root
    for literal, token in THEMED:
        root = root.replace(literal, token)
    return root


def shell(current, heading, intro, sections, versions):
    nav = "".join(
        '<a href="%s"%s>%s</a>' % (file, ' aria-current="page"' if page == current else "", label)
        for file, page, label, _, _ in PAGES
    )
    body = "".join(sections)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>alpi design · {heading}</title>
<link rel="icon" href="../site/assets/alpi-favicon.svg" type="image/svg+xml">
{FONT_LINK}
<link rel="stylesheet" href="../desktop/src/styles/tokens.css">
<link rel="stylesheet" href="boards.css">
<link rel="stylesheet" href="kit.css">
<script src="kit.js" defer></script>
</head>
<body class="kit">
<header class="kit-header">
<div class="brand-lockup"><img class="logo-light" src="../site/assets/alpi-black.svg" alt=""><img class="logo-dark" src="../site/assets/alpi-white.svg" alt="">alpi</div>
<nav aria-label="Design kit">{nav}</nav>
<span class="kit-version">desktop {versions["desktop"]} · mobile {versions["mobile"]}</span>
<div class="kit-seg" role="group" aria-label="Theme"><button type="button" data-kit-theme="light">Light</button><button type="button" data-kit-theme="dark">Dark</button></div>
</header>
<main class="kit-main">
<section class="kit-intro"><h1>{heading}</h1><p>{intro}</p>
<div class="kit-facts"><span>sources common/tokens.mjs · desktop/src/styles · mobile/src/theme</span><span>type Geist · Geist Mono</span><span>icons Lucide · 1.75 stroke</span><span>regenerate python3 design/build.py</span></div></section>
{body}
</main>
</body>
</html>
"""


def build(out):
    canvas_root = os.path.join(out, "canvas", "project")
    os.makedirs(canvas_root, exist_ok=True)
    gen.ROOT = canvas_root
    gen.build(DESKTOP)
    with open(os.path.join(canvas_root, "canvas.json")) as f:
        index = json.load(f)
    versions = {"desktop": version("desktop/package.json"), "mobile": version("mobile/package.json")}
    with open(os.path.join(canvas_root, "parity.css")) as f:
        boards_css = f.read()
    for literal, token in THEMED:
        boards_css = boards_css.replace(literal, token)
    with open(os.path.join(out, "boards.css"), "w") as f:
        f.write(boards_css)
    boards = index["boards"]
    notes = index["notes"]
    for file, page, _label, heading, intro in PAGES:
        rows = {}
        for name, frame in boards.items():
            if frame.get("page") != page:
                continue
            rows.setdefault(frame["y"], []).append((frame["x"], name, frame))
        titles = {n["y"] + 223: n["text"] for n in notes.values() if n.get("page") == page}
        groups = []
        for y in sorted(rows):
            items = sorted(rows[y])
            if y in titles:
                groups.append((titles[y], items))
            else:
                groups.extend((frame["title"], [(x, name, frame)]) for x, name, frame in items)
        sections = []
        for i, (label, items) in enumerate(groups, start=1):
            cards = "".join(
                '<div><div class="kit-caption">%s</div><div class="kit-board" style="width: %spx">%s</div></div>'
                % (frame["title"], frame["w"], board_root(os.path.join(canvas_root, name)))
                for _, name, frame in items
            )
            sections.append('<section class="kit-section"><h2>%s<span>%02d</span></h2><div class="kit-row">%s</div></section>' % (label, i, cards))
        with open(os.path.join(out, file), "w") as f:
            f.write(shell(page, heading, intro, sections, versions))
    return [file for file, *_ in PAGES]


if __name__ == "__main__":
    target = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else HERE
    for page in build(target):
        print(page)
