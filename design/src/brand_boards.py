import itertools
import re

import folds
from gen import LIGHT_ACCENT, page
from desktop_boards import HOVER, INK, INK2, INK3, INK4, LINE, LINE2, MONO, PANE, SIDE, diamond_stack
from conversation_boards import h1, label, mono, small_diamond, spec

PAGE_W = 1280
PAD = "padding: 40px 48px"
PAPER, PAPER_INK, NIGHT, NIGHT_INK = "#f6f3ec", "#14110c", "#0c0b09", "#f3efe6"
BRICOLAGE = "'Bricolage Grotesque', 'Geist', sans-serif"
EXTRA_FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&amp;family=Instrument+Serif:ital@0;1&amp;display=swap">'
SELECTED_BG = "rgba(20,20,20,0.06)"


PREVIOUS = [("amber", "#f0b447"), ("terracotta", "#d97757"), ("brick", "#c14545"), ("magenta", "#c14580"), ("purple", "#9d4dc6"), ("indigo", "#6a6dd6"),
            ("denim", "#3d7ea6"), ("teal", "#2f8e9e"), ("pine", "#2f7d6e"), ("forest", "#3fb37a"), ("olive", "#8a7a4a"), ("slate", "#6c7480")]
BATH = folds.palette("bath")
PAL = dict(BATH)
PAIRS = [
    ("diamond", "amber", "Amber diamond", "balanced · classic · the starting point", "Today’s glyph, folded: the kite base. Every profile starts here until it chooses.", ""),
    ("house", "vermilion", "Vermilion house", "steady · home · base", "Home and the household: what lives on your own machine.", "etxea · yuri"),
    ("heart", "rose", "Rose heart", "warm · caring · close", "Health and wellbeing: anything that looks after you.", "doc"),
    ("plane", "magenta", "Magenta plane", "fast · direct · outbound", "Mail, messages and delegation: it sends and arrives.", "abby · lingua"),
    ("shield", "blue", "Blue shield", "vigilant · protective · exact", "Review, security and legal: it guards and flags risk.", "lens · sentinel · smith · themis · galt"),
    ("rocket", "teal", "Teal rocket", "bold · driven · launching", "Shipping and exploring: it takes work to production, or sets out to find out.", "scout · curator"),
    ("star", "violet", "Violet star", "bright · distinctive · inspiring", "Insight and delight: the profile you reach for first.", "pulse · lingo"),
    ("tree", "green", "Green tree", "rooted · patient · long-lived", "Knowledge and memory: it keeps what it learns, a family tree of it.", "agora · alexandra · clonara"),
    ("box", "sky", "Sky box", "solid · technical · built", "Engineering and builds: it makes things and keeps them in order.", "pixel · neo · morpheus · trinity"),
    ("crown", "indigo", "Indigo crown", "directed · decisive · leading", "Coordination: the hub of a project, the one that leads.", "mira"),
    ("feather", "lime", "Lime feather", "light · fluent · articulate", "Writing: it drafts, edits and signs, the quill.", "quill · scribe"),
    ("bulb", "orange", "Orange bulb", "bright · curious · inventive", "Ideas and inspiration: design, assets, anything that lights up a thought.", "muse"),
]
PAIR_COLOUR = {p[0]: p[1] for p in PAIRS}
SAMPLE = [("scout", "rocket"), ("lens", "shield"), ("lingua", "plane"), ("mira", "crown"), ("muse", "bulb"), ("pixel", "box"), ("quill", "feather")]
GROUPS = [("site-hotel-victoire-v1…", "crown"), ("site-apartamentos-m…", "box"), ("site-hotel-vasari-v108", "tree")]


def stack(*items, gap=14):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def flex(*items, gap=16, align="center", wrap=False, extra=""):
    return f'<div style="display: flex; align-items: {align}; gap: {gap}px; {"flex-wrap: wrap; " if wrap else ""}{extra}">{"".join(items)}</div>'


def panel(inner, pad=22, bg=PANE, extra=""):
    return f'<div style="padding: {pad}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE2}; box-sizing: border-box; {extra}">{inner}</div>'


def body(text, size=13, color=INK2, extra=""):
    return f'<p style="margin: 0; font-size: {size}px; line-height: 1.55; color: {color}; {extra}">{text}</p>'


def strong(text, size=15, color=INK):
    return f'<span style="font-size: {size}px; font-weight: 600; letter-spacing: -0.01em; color: {color}">{text}</span>'


def head(kicker, title, sub):
    return stack(label(kicker), h1(title, sub), gap=10)


def board(name, h, *sections, gap=28):
    inner = f'<div data-brand="{name}" style="{PAD}; display: flex; flex-direction: column; gap: {gap}px; box-sizing: border-box">{EXTRA_FONTS}{"".join(sections)}</div>'
    return page("Brand " + name, PAGE_W, h, inner)


def section_title(text, n=None):
    num = f'<span style="font-family: {MONO}; font-size: 11px; color: {INK4}">{n}</span>' if n else ""
    return f'<div style="display: flex; align-items: baseline; gap: 10px; margin-top: 6px"><span style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em">{text}</span>{num}</div>'


def fold(shape, color, size=64, **kw):
    return folds.fold(shape, color, size, **kw)


def pair(shape, size=64, **kw):
    return folds.fold(shape, PAL[PAIR_COLOUR[shape]], size, **kw)


def group_icon(hub, size, kind="honeycomb", **kw):
    colour = PAL[PAIR_COLOUR[hub]]
    if kind == "stack":
        return folds.copies(hub, colour, size, 3)
    if kind == "alpaca":
        return folds.fold("alpaca", colour, size, **kw)
    return folds.fold("honeycomb", colour, size, **kw)


def tile(inner, bg=PANE, size=96, radius=22, border=True):
    edge = f"border: 0.5px solid {LINE2}; " if border else ""
    return f'<span style="width: {size}px; height: {size}px; border-radius: {radius}px; background: {bg}; {edge}display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0">{inner}</span>'


def paper_box(inner, h=168, extra=""):
    return f'<div style="height: {h}px; border-radius: 10px; background: {PAPER}; display: flex; align-items: center; justify-content: center; {extra}">{inner}</div>'


def black_alpaca(size, color="rgb(20, 20, 20)"):
    polys = "".join('<polygon points="%s" fill="%s"/>' % (" ".join("%.1f,%.1f" % p for p in pts), color) for pts, _ in folds.alpaca_facets())
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="alpi mark" style="flex-shrink: 0; display: block">{polys}</svg>'


def alpaca(color, size):
    return fold("alpaca", color, size)


def alpaca_small(color, size):
    return fold("alpaca-low", color, size)


def black_small(size, color="rgb(20, 20, 20)"):
    polys = "".join('<polygon points="%s" fill="%s"/>' % (" ".join("%.1f,%.1f" % p for p in pts), color) for pts, _ in folds.facets("alpaca-low"))
    return f'<svg viewBox="0 0 100 100" width="{size}" height="{size}" role="img" aria-label="alpi mark, nine facets" style="flex-shrink: 0; display: block">{polys}</svg>'


def crease(text, size, tones3, family=BRICOLAGE, weight=800, angle=115, track="-0.04em"):
    a, b, c = tones3
    gap = round(max(1.2, size / 70), 1)
    stops = (f"{a} 0 calc(33% - {gap / 2}px), transparent calc(33% - {gap / 2}px) calc(33% + {gap / 2}px), {b} calc(33% + {gap / 2}px) calc(66% - {gap / 2}px), "
             f"transparent calc(66% - {gap / 2}px) calc(66% + {gap / 2}px), {c} calc(66% + {gap / 2}px) 100%")
    return (f'<span style="font-family: {family}; font-size: {size}px; font-weight: {weight}; letter-spacing: {track}; line-height: 0.95; '
            f'background: linear-gradient({angle}deg, {stops}); -webkit-background-clip: text; background-clip: text; color: transparent">{text}</span>')


def deep_tones(accent):
    t = folds.tones(accent)
    L, C, h = folds.lch(accent)
    return [t[folds.LIGHT], accent, t[folds.SHADE], folds.oklch(max(L - 0.28, 0.05), C * 0.9, h), folds.oklch(max(L - 0.40, 0.04), C * 0.8, h)]


def crease_on(accent, ground):
    if ground == "night":
        t = folds.tones(accent)
        return (accent, t[folds.LIGHT], t[folds.SHADE])
    ladder = [c for c in deep_tones(accent) if folds.contrast(c, PAPER) >= 3]
    ladder = (ladder + deep_tones(accent)[-1:] * 3)[:3] if len(ladder) < 3 else ladder[:3]
    return tuple(ladder)


def app_crease(text, size, accent, ground, **kw):
    return crease(text, size, folds.crease_tones(accent, ground), **kw)


def word(text, size, accent, ground):
    return crease(text, size, crease_on(accent, ground))


INK_PAPER = ("#14110c", "#3b362d", "#0a0907")
INK_NIGHT = ("#f3efe6", "#ffffff", "#b9b3a4")


BODY = {0, 1, 3, 4, 5, 7, 8}
BUILD = [(None, "1 · Sheet"), (BODY, "2 · Body and legs"), (BODY | {2}, "3 · Neck"), (set(range(12)), "4 · Head")]


def build_frames(size, box, color):
    frames = []
    for visible, name in BUILD:
        if visible is None:
            art = folds.flat(color, size)
        else:
            art = fold("alpaca", color, size, facet_attrs=lambda i, n, tone, v=visible: "" if i in v else ' opacity="0"')
        frames.append(stack(f'<div style="width: {box}px; height: {box}px; border-radius: 12px; background: {PAPER}; border: 0.5px solid {LINE2}; display: flex; align-items: center; justify-content: center">{art}</div>', mono(name, 11, INK3), gap=8))
    return flex(*frames, gap=18, align="flex-start")


def mark():
    big = lambda inner, cap_, sub, bg=PANE, w=270: stack(
        f'<div style="width: {w}px; height: 330px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE2}; display: flex; align-items: center; justify-content: center">{inner}</div>',
        strong(cap_, 13), mono(sub, 11, INK3), gap=8)
    options = flex(
        big(alpaca(LIGHT_ACCENT, 260), "Ink on paper", "ships · 12 facets · one flat ink · the folds are the seams", bg="#fefefe"),
        big(alpaca("#f3efe6", 260), "Cream on night", "ships · the same drawing on near-black", bg=NIGHT),
        big(folds.flat(PAL["amber"], 170), "The sheet", "the unfolded mark · empty and offline", bg=PANE),
        gap=18, align="flex-start")

    lock_h = lambda bg, mk, wd: f'<div style="width: 360px; height: 150px; border-radius: 12px; background: {bg}; display: flex; align-items: center; justify-content: center; gap: 18px">{mk}{wd}</div>'
    lock_v = lambda bg, mk, wd: f'<div style="width: 220px; height: 230px; border-radius: 12px; background: {bg}; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px">{mk}{wd}</div>'
    lockups = flex(
        lock_h(PAPER, alpaca(LIGHT_ACCENT, 96), crease("alpi", 64, INK_PAPER)),
        lock_h(NIGHT, alpaca("#f3efe6", 96), crease("alpi", 64, INK_NIGHT)),
        lock_v(PAPER, alpaca(LIGHT_ACCENT, 110), word("alpi", 50, LIGHT_ACCENT, "paper")),
        lock_v(NIGHT, alpaca("#f3efe6", 110), word("alpi", 50, "#f3efe6", "night")),
        gap=18, align="flex-start")

    tiles = flex(
        stack(tile(alpaca(LIGHT_ACCENT, 70), "#ffffff", 120, 28), mono("app icon · light", 11, INK3), gap=8),
        stack(tile(alpaca("#f3efe6", 70), NIGHT, 120, 28, border=False), mono("app icon · dark", 11, INK3), gap=8),
        stack(tile(black_small(56, PAPER_INK), "#ffffff", 120, 28), mono("menu bar · single ink", 11, INK3), gap=8),
        stack(tile(pair("shield", 78), "#ffffff", 120, 28), mono("per-profile tile", 11, INK3), gap=8),
        stack(tile(pair("crown", 78), "#ffffff", 120, 28), mono("per-profile tile", 11, INK3), gap=8),
        stack(tile(pair("rocket", 78), NIGHT, 120, 28, border=False), mono("per-profile · dark", 11, INK3), gap=8),
        gap=18, align="flex-start")

    sizes = flex(*[stack(f'<div style="height: 110px; display: flex; align-items: flex-end">{alpaca_small(LIGHT_ACCENT, z) if z <= 32 else alpaca(LIGHT_ACCENT, z)}</div>', mono(f"{z}" + (" · nine facets" if z <= 32 else ""), 11, INK3), gap=6) for z in (16, 24, 32, 48, 96)], gap=26, align="flex-end")
    note = panel(body("<b>Where each mark ships.</b> The alpaca is the brand and it is always one ink: the app icons, the splash, the site and the README; the iOS tinted icon and the tray templates are the same drawing recoloured by the system. The wordmark is cut like the alpaca: T3 Crease, three greys with a slit between them, in ink on paper or in cream on night. It is Bricolage Grotesque, shipped as a font in the apps and the site. At 32 px and below the alpaca is drawn with nine facets instead of twelve, the same drawing the menu bar uses in one ink; profiles wear a small object instead of the alpaca.", 12.5), 20, bg=SIDE)

    return board("mark", 2180, head("Brand · logo", "The alpaca stays, in the same cut as its name.",
                                  "The origami alpaca is drawn in one flat ink, black on paper and cream on night; its folds are the paper seams between twelve facets. It is the one mark that is not a profile. Only the name carries tones: T3 crease, three greys cut by a slit, like a sheet cut from paper."),
                 options, section_title("It builds from a sheet", "01"), build_frames(150, 190, LIGHT_ACCENT), section_title("Lockups", "02"), lockups,
                 section_title("Tiles and icons", "03"), tiles, section_title("Where it stops reading", "04"), spec("The alpaca at 16, 24, 32, 48 and 96 px", sizes, pad=18), note, gap=24)


def gate_rows():
    rows = []
    for name in folds.SHAPE_ORDER + ["honeycomb"]:
        shapes = folds.facets(name)
        pts = [p for poly, _ in shapes for p in poly]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        aspect = min(w, h) / max(w, h)
        ok = name in folds.MODELS and len(shapes) <= folds.MAX_FACETS and aspect >= folds.MIN_ASPECT
        rows.append((name, folds.MODELS.get(name, "?"), len(shapes), aspect, ok))
    return rows


def pairs_board():
    cards = []
    for shape, colour, name, temper, text, who in PAIRS:
        small = flex(*[pair(shape, z) for z in (11, 12, 16, 20, 24)], gap=8, extra=f"padding: 8px 8px; border-radius: 8px; background: {PAPER}")
        cards.append(panel(stack(
            paper_box(pair(shape, 112), 140),
            small,
            strong(name, 14),
            mono(temper, 10.5, INK2),
            body(text, 11.5, INK3),
            mono("origami · " + folds.MODELS[shape], 10, INK3),
            mono(who, 10.5, INK),
            gap=8), 12, extra="width: 178px; flex-shrink: 0"))
    gate = gate_rows()
    gate_table = stack(*[flex(f'<span style="font-family: {MONO}; font-size: 11.5px; color: {"#217a45" if ok else "#b73737"}; width: 36px">{"pass" if ok else "FAIL"}</span>', f'<span style="font-size: 12.5px; font-weight: 500; width: 84px">{n}</span>',
                              mono(f"{model}", 11, INK2), mono(f"{count} facets · fills {aspect * 100:.0f}% of the square", 10.5, INK3), gap=10) for n, model, count, aspect, ok in gate], gap=6)
    rules = panel(stack(strong("The gate: every object is origami", 15),
                        body("<b>1.</b> An established origami model, folded from one square, not an icon. A pencil, a flag, a picture or an isometric cube is a drawing of something, not a fold of paper, and does not enter.", 12.5),
                        body("<b>2.</b> Few creases: six facets at most. A real fold has a handful, not dozens.", 12.5),
                        body("<b>3.</b> It fills the square: its shorter side is at least 80 % of its longer one, so it takes the 1:1 slot the diamond takes today.", 12.5),
                        body("<b>4.</b> No shadows, no gradients, no outlines: three flat tones and the slits between the folds.", 12.5),
                        body("<b>5.</b> One piece of paper: every facet touches another, so nothing floats. A sailboat icon with its sails apart from the hull is a drawing; a folded paper boat is one fold.", 12.5),
                        body("<b>6.</b> Nothing that can read as a hate symbol: no four-fold rotating blades (a pinwheel reads as a swastika), and the test rejects any four-fold chiral shape.", 12.5),
                        body("The kit test enforces 1 to 6 on every object, and the table shows the same computation.", 12.5, INK3), gap=10), 18, extra="width: 420px; flex-shrink: 0")
    how = panel(stack(strong("How a profile gets its pair", 15),
                      body("<b>Chosen for the feeling.</b> Origami has few models and they are what they are, so the pair is a feeling, not a role: a shield for the ones that guard, a tree for the ones that remember, a crown for the one that leads. Under each card, who in the web factory, the Mirai fleet, casa and Satoshi wears it.", 12.5),
                      body("<b>Choose.</b> One picker of twelve in setup, the TUI and the apps. The pair has a name you can say: “blue shield”.", 12.5),
                      body("<b>Same feeling, another colour.</b> Several profiles share an object (three shields, three boxes). The object stays and the second takes the next free colour, so no two identities on the Fleet board are the same.", 12.5),
                      body("<b>Day one.</b> Every profile, the default one included, is a diamond in its current colour (mapped to the nearest colour of the new twelve), so the release changes nothing visible. Each profile then chooses its pair in its own settings and the choice is stored in its config as <code>fold</code> beside <code>accent</code>.", 12.5, INK3), gap=10), 18, extra="flex: 1")
    return board("pairs", 1700, head("Brand · pairs", "Twelve origami models, one colour each.",
                                    "Each is an established model folded from one square: few creases, three flat tones with the light from the top left, filling the 1:1 slot. Drawn once and shown at 112 px and at 11, 12, 16, 20 and 24 px, the sizes the apps use. No shadows."),
                 flex(*cards[:6], gap=14, align="stretch"), flex(*cards[6:], gap=14, align="stretch"),
                 flex(rules, panel(stack(strong("The gate, computed", 15), gate_table, gap=10), 18, extra="flex: 1"), gap=16, align="stretch"), how, gap=22)


def side_row(glyph, name, selected=False, meta="", weight=500):
    bg = SELECTED_BG if selected else "transparent"
    return (f'<div style="display: flex; align-items: center; gap: 10px; height: 30px; padding: 0 12px; border-radius: 8px; background: {bg}; box-sizing: border-box">'
            f'<span style="width: 24px; display: inline-flex; justify-content: center; flex-shrink: 0">{glyph}</span>'
            f'<span style="flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 14px; font-weight: {weight}; color: {INK}">{name}</span>'
            f'<span style="font-family: {MONO}; font-size: 11px; color: {INK3}">{meta}</span></div>')


def side_label(text):
    return f'<div style="padding: 10px 12px 4px">{label(text)}</div>'


def sidebar(title, tag, glyph_for, wg_glyph, width=248):
    rows = [side_label("Pinned"), side_row(folds.fold("alpaca", LIGHT_ACCENT, 16), "alpi", meta="2d"), side_label("Profiles")]
    rows += [side_row(glyph_for(s), n, selected=n == "lens", meta="2w" if n == "scout" else "") for n, s in SAMPLE]
    rows += [side_label("Workgroups")]
    rows += [side_row(wg_glyph(h), n, meta="19h") for n, h in GROUPS]
    return stack(flex(strong(title, 14), mono(tag, 10.5, INK3), gap=8), panel(stack(*rows, gap=1), 8, bg=SIDE, extra=f"width: {width}px"), gap=10)


def inline(glyph, text, size=13, color=INK):
    return f'<span style="display: inline-flex; align-items: center; gap: 5px; font-size: {size}px; color: {color}">{glyph}<span>{text}</span></span>'




def palette_stats(colors):
    hexes = [h for _, h in colors]
    min_de = min(folds.delta_e(a, b) * 100 for a, b in itertools.combinations(hexes, 2))
    shade_white = min(folds.contrast(folds.tones(h)[folds.SHADE], "#ffffff") for h in hexes)
    light_dark = min(folds.contrast(folds.tones(h)[folds.LIGHT], "#151515") for h in hexes)
    return min_de, shade_white, light_dark


def mix_hex_pct(color, amount, base):
    fg, bg = folds._hex(color), folds._hex(base)
    return "#%02x%02x%02x" % tuple(round(fg[i] * amount + bg[i] * (1 - amount)) for i in range(3))


def token_checks(colors):
    hexes = [h for _, h in colors]
    text_ratio = lambda h: max(folds.contrast(h, "#000000"), folds.contrast(h, "#ffffff"))
    return [
        ("Twelve distinct six-digit hexes", len(hexes) == 12 and len(set(hexes)) == 12 and all(re.fullmatch(r"#[0-9a-f]{6}", h) for h in hexes), f"{len(set(hexes))} distinct"),
        ("Names are lowercase letters, each once", all(re.fullmatch(r"[a-z]+", n) for n, _ in colors) and len({n for n, _ in colors}) == len(colors), ", ".join(n for n, _ in colors[:3]) + "…"),
        ("Black or white text on every accent reaches 4.5:1", min(text_ratio(h) for h in hexes) >= 4.5, f"lowest {min(text_ratio(h) for h in hexes):.2f}:1"),
        ("Ink on a 12 % tint of every accent, light and dark", min(min(folds.contrast("#141414", mix_hex_pct(h, 0.12, "#ffffff")), folds.contrast("#ededed", mix_hex_pct(h, 0.12, "#151515"))) for h in hexes) >= 4.5, f"lowest {min(min(folds.contrast('#141414', mix_hex_pct(h, 0.12, '#ffffff')), folds.contrast('#ededed', mix_hex_pct(h, 0.12, '#151515'))) for h in hexes):.1f}:1"),
        ("The dark-mode accent stays the alpi brand gold and stays in the set", "#f0b447" in hexes, "#f0b447 kept exactly"),
    ]


def palette_board():
    options = [
        ("A · Previous", f"{len(PREVIOUS)} accents · before v0.17", PREVIOUS, "The twelve before v0.17. Denim and teal sit closest; terracotta, brick and amber crowd the warm end while the cool end is sparse."),
        ("B · Equal bath", "12 hues · ships", BATH, "One lightness and chroma family, hues spaced round the wheel (amber lighter, as yellow must be). Every colour weighs the same on the page, so no object shouts and none disappears."),
        ("C · Soft", "12 hues · Dots-like", folds.palette("soft"), "Higher lightness, lower chroma: friendly, pastel. Reads gently and loses edge on white grounds; colours sit close together."),
        ("D · Deep", "12 hues · jewel", folds.palette("deep"), "Lower lightness, higher chroma: rich and serious, the best edge on white, but yellows and oranges merge and dark grounds lose them."),
    ]
    order = [p[0] for p in PAIRS]
    rows = []
    for title, tag, colors, text in options:
        de, sw, ld = palette_stats(colors)
        objects = flex(*[fold(order[i % 12], c, 36) for i, (_, c) in enumerate(colors)], gap=6, wrap=True)
        strip = flex(*[f'<span style="width: 36px; height: 12px; background: {c}; border-radius: 3px"></span>' for _, c in colors], gap=6, wrap=True)
        stats = stack(
            mono(f"min distance between two colours · {de:.1f}", 11, INK2),
            mono(f"darkest facet on white · {sw:.1f}:1", 11, INK2),
            mono(f"lightest facet on dark pane · {ld:.1f}:1", 11, INK2),
            gap=5)
        rows.append(panel(stack(
            flex(strong(title, 15), mono(tag, 10.5, INK3), gap=10, extra="justify-content: space-between"),
            paper_box(stack(objects, strip, gap=10), 100, extra="flex-direction: column; padding: 8px 14px; box-sizing: border-box"),
            stats, body(text, 12, INK2), gap=12), 16, extra="flex: 1; min-width: 0"))
    stats_a, stats_b = palette_stats(PREVIOUS), palette_stats(BATH)
    no_rose = palette_stats([c for c in BATH if c[0] != "rose"])[0]
    tone_rows = stack(*[
        flex(f'<span style="width: 84px; font-size: 12px; font-weight: 500">{n}</span>',
             '<span style="display: inline-flex; border-radius: 6px; overflow: hidden">' + "".join(
                 f'<span style="width: 62px; height: 34px; background: {folds.tones(h)[k]}; display: inline-flex; align-items: flex-end; padding: 3px 5px; box-sizing: border-box; font-family: {MONO}; font-size: 9px; color: {"#10100c" if folds.contrast(folds.tones(h)[k], "#10100c") >= 4 else "#fbf8f0"}">{folds.tones(h)[k][1:]}</span>'
                 for k in (folds.LIGHT, folds.BASE, folds.SHADE)) + "</span>",
             mono(f"{h}", 10.5, INK3), gap=10)
        for n, h in BATH], gap=5)
    checks = token_checks(BATH)
    check_rows = stack(*[flex(f'<span style="font-family: {MONO}; font-size: 12px; color: {"#217a45" if ok else "#b73737"}">{"pass" if ok else "FAIL"}</span>', f'<span style="font-size: 12.5px; flex: 1">{name}</span>', mono(detail, 10.5, INK3), gap=10) for name, ok, detail in checks], gap=8)
    notes = stack(
        panel(stack(strong("Confirmed: B is the palette", 15), body("It passes every check today’s token tests make on the accent set, computed here from the colours themselves. What has to change is the data: the twelve entries of <code>common/accents.mjs</code>, the per-profile accents in the mobile theme, and the stored colour of every existing profile, mapped once to its nearest new colour. No test needs weakening.", 12.5), check_rows, gap=12), 18),
        panel(stack(strong("Tones are computed", 15), body("Light is lifted and shade is lowered in OKLCH, keeping the hue, rather than mixed with white and black, so shadows stay rich instead of going grey. Each colour is one stored value; its three tones fall out of it.", 12.5), gap=8), 18),
        panel(stack(strong("What the numbers say", 15), body(f"B has the widest gap between any two colours ({stats_b[0]:.1f} against {stats_a[0]:.1f} today, about {stats_b[0] / stats_a[0]:.1f}× as far apart), and its darkest facet clears {stats_b[1]:.1f}:1 on white, in line with today’s {stats_a[1]:.1f}:1. D has more edge but fewer separable hues; C is the gentlest and the weakest on both counts. The twelfth colour, rose, is the one that costs least: it brings the closest pair only from {no_rose:.1f} to {stats_b[0]:.1f}.", 12.5), gap=8), 18),
        gap=14)
    return board("palette", 1400, head("Brand · palette", "Twelve colours, confirmed.",
                                      "Each colour has one default object, so the palette is the identity set. Four candidates drawn with the same objects, with the distances and contrasts measured rather than judged by eye. B keeps amber exactly and adds rose between vermilion and magenta."),
                 flex(*rows[:2], gap=16, align="stretch"), flex(*rows[2:], gap=16, align="stretch"),
                 section_title("B in three tones, and what it has to pass", "01"), flex(panel(tone_rows, 18), notes, gap=18, align="flex-start", extra="width: 100%"), gap=22)


def direction(title, tag, ground, ink, signal, text, mark_color, dark=False):
    button = f'<span style="padding: 7px 12px; border-radius: 8px; background: {signal}; color: {NIGHT if dark or signal != PAPER_INK else PAPER}; font-size: 12px; font-weight: 600">Add profile</span>'
    card = (f'<div style="height: 200px; border-radius: 10px; background: {ground}; padding: 18px; box-sizing: border-box; display: flex; flex-direction: column; justify-content: space-between">'
            f'<div style="display: flex; justify-content: space-between; align-items: flex-start">{black_alpaca(64, mark_color)}{button}</div>'
            f'<div style="display: flex; flex-direction: column; gap: 4px"><span style="font-size: 22px; font-weight: 600; letter-spacing: -0.03em; color: {ink}">Your private agent network.</span>'
            f'<span style="font-family: {MONO}; font-size: 10.5px; color: {ink}; opacity: 0.6">ground {ground[1:]} · ink {ink[1:]} · signal {signal[1:]}</span></div></div>')
    return panel(stack(flex(strong(title, 15), mono(tag, 10.5, INK3), gap=10, extra="justify-content: space-between"), card, body(text, 12, INK2), gap=12), 16, extra="flex: 1; min-width: 0")


def state_fold(shape, color, state, size=110):
    if state == "working":
        return f'{folds.sweep_style("sw", color, 2.4)}{fold(shape, color, size, facet_attrs=folds.sweep_attrs("sw", 2.4))}'
    if state == "offline":
        return folds.outline(shape, INK3, size)
    return fold(shape, color, size)


def motion():
    states = [
        ("idle", "Idle", "Still. The object at rest is the profile at rest.", "The default. No motion, so a roster of ten is calm."),
        ("working", "Working", "Light travels around the object: each facet takes its tones in turn.", "The large figure only. In a list the glyph pulses as the diamond does today; stops under reduced motion."),
        ("offline", "Paused or offline", "Unfolded: the crease pattern in grey, no fill.", "A paused profile or workgroup, or every profile of a connection whose daemon does not answer. The rows stay and can be opened; a paused name reads in grey. Needs you and failed stay chips."),
    ]
    cells = [panel(stack(
        paper_box(state_fold("shield", PAL["blue"], s, 112), 150),
        flex(strong(n, 15), mono(s, 10.5, INK3), gap=8, extra="justify-content: space-between"),
        body(a, 12.5, INK2), body(b, 11.5, INK3), gap=10), 14, extra="width: 220px; flex-shrink: 0") for s, n, a, b in states]
    strip = flex(*cells, gap=14, align="stretch")

    turn = folds.BREATHE_STYLE + group_icon("crown", 64, facet_attrs=folds.breathe_attrs)
    rule = panel(stack(strong("A profile does not cycle the palette", 15),
                       body("Colour is a profile’s identity, so its working state keeps it: the light sweeps round the object in its own colour on the large figure, and a small glyph pulses. A workgroup’s honeycomb ripples, its three cells one after the other. All of them stop under reduced motion and none blocks input.", 12.5),
                       flex(paper_box(turn, 100, extra="width: 130px; flex-shrink: 0"), mono("workgroup · working", 10.5, INK3), gap=14), gap=12), 20, extra="flex: 1")
    first = stack(section_title("The first fold", "01"), build_frames(110, 150, PAL["amber"]), gap=14)
    return board("motion", 1270, head("Brand · states and motion", "A profile that is working folds. A profile that is away is flat.",
                                     "A Dot is a character. A fold can be paper: the state is a property of the sheet, which keeps motion meaningful, cheap and quiet."),
                 strip, flex(first, rule, gap=24, align="stretch"), gap=24)


def creases():
    lines = []
    for i in range(-6, 14):
        x = i * 40
        lines.append(f'<line x1="{x}" y1="0" x2="{x + 250}" y2="250" stroke="#d8d0be" stroke-width="0.8" stroke-dasharray="4 4"/>')
        lines.append(f'<line x1="{x + 250}" y1="0" x2="{x}" y2="250" stroke="#d8d0be" stroke-width="0.8" stroke-dasharray="4 4"/>')
    return f'<svg width="100%" height="250" style="position: absolute; inset: 0" aria-hidden="true">{"".join(lines)}</svg>'


BRAND_BOARDS = [
    ("Brand-Mark.dc.html", mark, 2180, "Logo and mark"),
    ("Brand-Pairs.dc.html", pairs_board, 1700, "Pairs"),
    ("Brand-Palette.dc.html", palette_board, 1400, "Palette"),
    ("Brand-Motion.dc.html", motion, 1270, "States and motion"),
]
