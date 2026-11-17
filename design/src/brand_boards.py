import agent_marks as am
import marks
import volume_marks as vm
import workgroup_marks as wg
from conversation_boards import h1, label
from desktop_boards import INK, INK2, INK3, LINE, LINE2, MONO
from gen import page

PAGE_W = 1280
PAD = "padding: 40px 48px"
BRICOLAGE = "'Bricolage Grotesque', 'Geist', sans-serif"
EXTRA_FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&amp;display=swap">'
TWIN, INK_MARK = marks.TWIN, marks.TWIN_INK
ROW, HEADER, HERO = am.MARK_SIZES["row"], am.MARK_SIZES["header"], am.MARK_SIZES["hero"]
PAIRS = len(am.SHAPE_ORDER) * len(am.PALETTE)
HELD = vm.STILL["idle"]
SMALL_HELD = tuple(a * vm.SMALL_TURN for a in HELD)
WEIGHT, TRACK = 800, "-0.04em"
MARK_RATIO, GAP_RATIO = 1.15, 0.22
PAPER, NIGHT = "rgb(255, 255, 255)", "rgb(12, 11, 9)"
INK_LIGHT, CREAM = "rgb(20, 17, 12)", "rgb(243, 239, 230)"
OK, NO = "#217a45", "#b73737"
LIGHT_GROUND, DARK_GROUND = "#ffffff", "#1a1a1a"
HEIGHTS = {"mark": 900, "wordmark": 630, "icon": 670, "family": 1055, "eyes": 940, "motion": 1080, "names": 780, "workgroups": 750, "gate": 590}

GATE = (
    "One closed silhouette of tangent-continuous curves: no corners, nothing floating, no holes but the eyes cut out of the one-ink icon, menu-bar template and favicon.",
    "One flat fill on the body: no outline, no gradient, no shadow, no second colour but the eyes.",
    "Two eyes filled in the paper tone of the theme, white on light and black on dark, at 3:1 or more on the body, inside it in every pose of every state from 16 px; in light a pale accent's body is drawn deeper by <code>markTone</code> until they reach it.",
    f"Equal area and a shared optical centre across the twelve, so no profile shouts in a row of {ROW} px.",
    "Upright at rest: a held angle is a turn in 3D, never a flat tilt of the drawing; the app icon is static and may show the held turn.",
    "Readable at 16 px: the silhouette and both eyes survive the menu bar and the smallest row.",
    f"Every state has a still form; motion only from {am.MOTION_MIN} px and never under reduce motion.",
    "Never a copy of a known character, mascot or logo, and nothing that reads as a hate symbol.",
    f"alpi is always neutral ink, cream in dark, never an accent; a profile is always one of the {PAIRS} shape × accent pairs.",
)


def solid(text, size, colour, family=BRICOLAGE, weight=WEIGHT, track=TRACK):
    return (f'<span style="font-family: {family}; font-size: {size}px; font-weight: {weight}; letter-spacing: {track}; line-height: 0.95; color: {colour}; '
            f'white-space: nowrap">{text}</span>')


def app_name(text, size, accent, ground, literal=False, **kw):
    from gen import ALPI_ACCENT
    if accent and accent.lower() == ALPI_ACCENT.lower():
        accent = None
    light = marks.name_tone(accent, ground)
    if not light or literal:
        return solid(text, size, light or "#141414", **kw)
    from gen import PALETTES
    dark_ground = PALETTES["dark"][next(k for k in ("bgSide", "bgInput", "bgPane") if PALETTES["light"][k].lower() == ground.lower())]
    return solid(text, size, f"light-dark({light}, {marks.name_tone(accent, dark_ground)})", **kw)


def stack(*items, gap=14):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def row(*items, gap=18, align="flex-end", spread=False):
    justify = "justify-content: space-between; " if spread else ""
    return f'<div style="display: flex; {justify}align-items: {align}; gap: {gap}px; flex-wrap: wrap">{"".join(items)}</div>'


def tag(text, colour=INK3, size=10):
    return f'<span style="font-family: {MONO}; font-size: {size}px; color: {colour}">{text}</span>'


def caption(text):
    return f'<span style="font-size: 12px; line-height: 1.5; color: {INK3}; max-width: 1080px">{text}</span>'


def cell(inner, text, w=None, sub=""):
    width = f"width: {w}px; " if w else ""
    second = tag(sub, size=9) if sub else ""
    return (f'<span style="{width}display: inline-flex; flex-direction: column; align-items: center; gap: 6px; text-align: center">'
            f'{inner}{tag(text)}{second}</span>')


def well(inner, h, w=None, bg="#f6f6f6"):
    width = f"width: {w}px; " if w else "flex: 1; min-width: 0; "
    return (f'<div style="{width}height: {h}px; border-radius: 10px; background: {bg}; display: flex; align-items: center; justify-content: center; '
            f'flex-shrink: 0; box-sizing: border-box">{inner}</div>')


def block(title, *items):
    return stack(f'<span style="font-size: 17px; font-weight: 600; letter-spacing: -0.01em; color: {INK}">{title}</span>', *items, gap=14)


def blocks(*items):
    rule = f'<div style="height: 0.5px; background: {LINE}"></div>'
    return stack(*[x for item in items for x in (rule, item)][1:], gap=28)


def board(name, kicker, title, sub, *sections):
    inner = (f'<div data-brand="{name}" style="{PAD}; display: flex; flex-direction: column; gap: 28px; box-sizing: border-box">{EXTRA_FONTS}'
             f'{stack(label(kicker), h1(title, sub), gap=10)}{blocks(*sections)}</div>')
    return page("Brand " + name, PAGE_W, HEIGHTS[name], inner)


FIXED_EYE = {INK_LIGHT: "rgb(255, 255, 255)", CREAM: "rgb(0, 0, 0)"}


def held(size, colour=INK_MARK):
    return vm.turned(TWIN, colour, size, HELD if size > ROW else SMALL_HELD, FIXED_EYE.get(colour, am.EYE_INK))


def lockup(size, colour=INK_MARK):
    return (f'<span style="display: inline-flex; align-items: center; gap: {size * GAP_RATIO:.0f}px">{held(round(size * MARK_RATIO), colour)}'
            f'{solid("alpi", size, colour)}</span>')


def stacked(size, colour=INK_MARK):
    return (f'<span style="display: inline-flex; flex-direction: column; align-items: center; gap: {size * GAP_RATIO:.0f}px">{held(round(size * 1.6), colour)}'
            f'{solid("alpi", size, colour)}</span>')


def clear_space():
    return (f'<span style="display: inline-flex; padding: 16px; border: 1px dashed #b4b4b4; border-radius: 6px; position: relative">'
            f'<span style="display: inline-flex; outline: 1px dashed #b4b4b4">{held(64)}</span>'
            f'<span style="position: absolute; top: 2px; left: 50%; transform: translateX(-50%); font-family: {MONO}; font-size: 9px; color: {INK3}">¼</span>'
            f'<span style="position: absolute; left: 4px; top: 50%; transform: translateY(-50%); font-family: {MONO}; font-size: 9px; color: {INK3}">¼</span></span>')


def verdict(inner, text, ok):
    return (f'<span style="width: 110px; display: inline-flex; flex-direction: column; align-items: center; gap: 6px; text-align: center">'
            f'{well(inner, 84, 110)}{tag("do" if ok else "don’t", OK if ok else NO)}<span style="font-size: 11px; line-height: 1.3; color: {INK2}">{text}</span></span>')


def do_dont():
    px = 50
    outlined = (f'<svg viewBox="0 0 100 100" width="{px}" height="{px}" style="display: block; overflow: visible">'
                f'<path d="{am.outline(TWIN)["d"]}" fill="none" stroke="{INK_MARK}" stroke-width="5"/></svg>')
    return row(verdict(vm.turned_icon(TWIN, "close-white", 60), "the icon in the held turn", True),
               verdict(held(px), "ink, cream in dark", True),
               verdict(vm.turned(TWIN, am.COLOUR["blue"], px, HELD), "never an accent", False),
               verdict(outlined, "never outlined", False),
               verdict(f'<span style="display: inline-flex; transform: rotate(-14deg)">{am.mark(TWIN, INK_MARK, px, still=True)}</span>', "never a flat tilt", False),
               verdict(f'<span style="display: inline-flex; transform: scaleX(1.4)">{held(px)}</span>', "never stretched", False),
               gap=0, align="flex-start", spread=True)


FRAMES = 8


def turning_family():
    cells = "".join(cell(vm.mark(shape, am.COLOUR[colour], 72, seed=shape, held=True), shape, 84, colour) for shape, colour in am.FAMILY)
    return f'<div style="display: grid; grid-template-columns: repeat(6, 84px); gap: 20px 4px; justify-content: space-between">{cells}</div>'


def frame_strip(state="idle"):
    seconds = vm.TURN[state][0]
    blue = am.COLOUR["blue"]
    cells = "".join(cell(vm.mark("squircle", blue, 52, state, pose=vm.pose_at(state, k / FRAMES)), f"{seconds * k / FRAMES:.1f} s") for k in range(FRAMES))
    return stack(tag(f"{am.STATE_LABEL[state]}, paused every {seconds / FRAMES:.1f} s"), f'<div style="display: flex; justify-content: space-between">{cells}</div>', gap=10)


def turn_strip():
    blue = am.COLOUR["blue"]
    cells = "".join(f'<span style="width: 92px; display: inline-flex; flex-direction: column; align-items: center; gap: 10px">'
                    f'{vm.mark("squircle", blue, 52, s, seed="turn" + s)}{vm.mark("squircle", blue, 16, s)}{tag(am.STATE_LABEL[s])}</span>' for s in am.STATES)
    return f'<div style="display: flex; justify-content: space-between">{cells}</div>'


def turn_table():
    cols = (("state", "width: 74px; flex-shrink: 0; font-weight: 600; color: " + INK), ("turn", "flex: 1.7; color: " + INK2),
            ("eyes", "flex: 1; color: " + INK3), ("motion", "width: 150px; flex-shrink: 0; color: " + INK3))
    head = "".join(f'<span style="{css.split("; color")[0]}">{name}</span>' for name, css in cols)
    rows = "".join(f'<div style="display: flex; gap: 10px; padding: 6px 0; border-top: 0.5px solid {LINE}; font-size: 11.5px; line-height: 1.4">'
                   + "".join(f'<span style="{css}">{text}</span>' for (_, css), text in zip(cols, (am.STATE_LABEL[s],) + vm.TURN_TABLE[s])) + "</div>" for s in am.STATES)
    return (f'<div style="display: flex; flex-direction: column; gap: 4px"><div style="display: flex; gap: 10px; font-family: {MONO}; font-size: 10px; color: {INK3}">{head}</div>'
            f'{rows}</div>')


def honeycomb_strip():
    blue = am.COLOUR["blue"]
    out = []
    for s in wg.WG_STATES:
        kw = dict(phase=wg.RUN) if s == "running" else dict(cell="top") if s == "needs" else dict(cell="right") if s == "failed" else {}
        out.append(f'<span style="width: 92px; display: inline-flex; flex-direction: column; align-items: center; gap: 10px">{wg.honeycomb(blue, wg.PREVIEW, s, seed="strip" + s, **kw)}'
                   f'{wg.honeycomb(blue, ROW, s, **kw)}{wg.honeycomb(blue, wg.INLINE, s, **kw)}{tag(wg.WG_LABEL[s])}</span>')
    return f'<div style="display: flex; justify-content: space-between">{"".join(out)}</div>'


def pipeline_turns():
    out = []
    for done, (phase, owner, colour) in enumerate((("fetch", "yuri", "rose"), ("translate", "lingo", "violet"), ("file", "etxea", "green"))):
        lit = am.COLOUR[colour]
        out.append(row(cell(wg.honeycomb(lit, 56, "running", phase=(done, 3), seed="pt" + owner), f"{done}/3 · {wg.current_cell((done, 3))}"),
                       cell(wg.honeycomb(lit, ROW, "running", phase=(done, 3)), f"{ROW} still"), tag(f"Working · {phase} · @{owner}", INK2, 11), gap=10, align="center"))
    return f'<div style="display: flex; flex-direction: column; gap: 14px">{"".join(out)}</div>'


def honeycomb_sizes():
    ladder = (cell(wg.running_hub(px, "sz" + str(px)), f"{key} {px}") for key, px in am.MARK_SIZES.items())
    return row(*ladder, gap=30)


def workgroup_names():
    rows = []
    for name, state, kw, meta, muted in (("alpha", "running", dict(phase=wg.RUN), "Working · translate · @lingo", False),
                                          ("launch-crew", "needs", dict(cell="top"), "Needs you · approval · @yuri", False),
                                          ("digest", "idle", {}, "Idle", False), ("archive", "paused", {}, "Paused", True)):
        rows.append(row(wg.honeycomb(am.COLOUR["blue"], HEADER, state, seed="nm" + name, still=True, **kw), solid(name, 24, INK3 if muted else INK), tag(meta, INK2, 11), gap=12, align="center"))
    return stack(*rows, gap=10)


def twin_states():
    cells = "".join(f'<span style="width: 92px; display: inline-flex; flex-direction: column; align-items: center; gap: 10px">{marks.twin(56, s, seed="brand" + s)}'
                    f'{marks.twin(16, s)}{tag(am.STATE_LABEL[s], size=10)}</span>' for s in am.STATES)
    return f'<div style="display: flex; justify-content: space-between">{cells}</div>'


def mark_board():
    hero = well(vm.mark(TWIN, INK_MARK, 150, seed="brand", held=True), 240, 300)
    sizes = row(*(cell(held(px), str(px), sub=use) for px, use in ((16, "menu bar"), (ROW, "row"), (HEADER, "header"), (am.MARK_SIZES["tile"], "tile"), (HERO, "hero"))), gap=24)
    right = f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 12px">{well(sizes, 134)}{well(clear_space(), 94)}</div>'
    return board("mark", "Brand · the mark", "Twin, alpi’s mark, turning in 3D.",
                 "A robot head with two antenna balls, from the same family as the twelve profile shapes, in neutral ink on light and cream on dark, never an accent. "
                 "It is the default profile’s mark and the brand’s; under 24 px it draws its small variant, <code>alpi-twin-small</code>.",
                 block("1 · The mark", f'<div style="display: flex; gap: 12px">{hero}{right}</div>',
                       caption(f"At rest it holds a turn ({HELD[0]:g}° round, perspective {vm.DEPTH:g} × the size), half of it at {ROW} px and below; only a hero mark turns toward the pointer, never a paused one. "
                               "Clear space is a quarter of the mark."),
                       do_dont()),
                 block("2 · States", twin_states(),
                       caption(f"Twin’s eight states turn like the family; from {am.MOTION_MIN} px its two antenna balls pulse in turn while busy and blink while working. "
                               "Busy is also the wait: a page or a section that loads shows Twin busy.")))


def ground(inner, bg, w, h):
    return (f'<div style="width: {w}px; height: {h}px; border-radius: 12px; background: {bg}; border: 0.5px solid {LINE2}; display: flex; align-items: center; '
            f'justify-content: center; flex-shrink: 0; box-sizing: border-box">{inner}</div>')


def wordmark_board():
    fixed = row(ground(lockup(64, INK_LIGHT), PAPER, 370, 170), ground(lockup(64, CREAM), NIGHT, 370, 170),
                ground(stacked(44, INK_LIGHT), PAPER, 196, 170), ground(stacked(44, CREAM), NIGHT, 196, 170), gap=12, align="flex-start")
    themed = row(*(cell(lockup(px), f"{px} px") for px in (48, 32, 22, 16)), gap=40)
    return board("wordmark", "Brand · the wordmark", "The name, solid, beside the mark.",
                 f"alpi is set in Bricolage Grotesque {WEIGHT} at {TRACK}, solid, in the mark’s ink: the face and weight the apps and the site already ship.",
                 block("Lockups · ink on paper, cream on night", fixed,
                       caption(f"The mark is {MARK_RATIO:g} × the type size, so its head matches the x-height and the antenna balls rise to the ascender; the gap is {GAP_RATIO:g} × the size. "
                               "Stacked, the mark is 1.6 × the type size above the name.")),
                 block("Following the theme", well(themed, 120),
                       caption("The lockup in the kit’s ink: it flips with the theme like every brand surface, and never takes a profile accent.")))


def menu_bar():
    items = "".join(f'<span style="font-size: 12px; font-weight: {600 if i == 0 else 400}; color: #141414">{t}</span>' for i, t in enumerate(("Finder", "File", "Edit", "View")))
    glyphs = "".join(f'<span style="display: inline-flex; align-items: center; gap: 4px">{vm.turned(TWIN, INK_MARK, px, SMALL_HELD, None)}{tag(str(px), size=9)}</span>' for px in (18, 22))
    return (f'<div style="display: flex; align-items: center; gap: 14px; height: 30px; padding: 0 12px; border-radius: 8px; background: #f0f0f0">{items}'
            f'<span style="flex: 1"></span>{glyphs}<span style="font-size: 12px; color: #141414">Thu 12 Nov 19:40</span></div>')


def favicon():
    tab = (f'<span style="display: inline-flex; align-items: center; gap: 8px; height: 30px; padding: 0 12px; border-radius: 8px 8px 0 0; background: #ffffff; min-width: 140px">'
           f'{vm.turned_icon(TWIN, "white", 16, bleed=True, pose=SMALL_HELD)}<span style="font-size: 12px; color: #141414">alpi</span></span>')
    return (f'<div style="display: flex; align-items: flex-end; gap: 6px; padding: 8px 10px 0; border-radius: 8px; background: #f0f0f0">{tab}'
            f'<span style="flex: 1"></span><span style="display: inline-flex; padding-bottom: 4px">{vm.turned_icon(TWIN, "white", 32, bleed=True, pose=SMALL_HELD)}</span></div>')


def icon_board():
    icons = row(cell(vm.turned_icon(TWIN, "close-white", 160), "dock 128 @2x"), cell(vm.turned_icon(TWIN, "close-white", 64), "Finder 64"),
                cell(vm.turned_icon(TWIN, "white", 32), "32 · full mark"), cell(vm.turned_icon(TWIN, "white", 16), "16"), gap=28)
    return board("icon", "Brand · the app icon", "The close-up of Twin in its held turn, on white.",
                 "The app icon, the menu-bar template and the favicon are projected from the same turn, drawn as fixed geometry by <code>scripts/gen_icons.py</code>.",
                 block("App icon", icons,
                       caption(f"Twin’s outline, eyes and antenna balls projected through the held turn ({HELD[0]:g}° round), the eyes slid toward the side it faces, static. "
                               "At 32 and 16 px the crop stops reading, so the full turned mark on white.")),
                 block("Menu bar and favicon", menu_bar(), favicon(),
                       caption("The menu-bar template and the favicon keep half the turn, in one ink, as every mark at 20 px and below; both still read at 16 and 18 px.")))


def swatch(name, hex_):
    return (f'<span style="display: inline-flex; flex-direction: column; gap: 4px; width: 84px">'
            f'<span style="height: 30px; border-radius: 6px; background: {am.rgb(hex_)}"></span>'
            f'<span style="font-size: 11.5px; font-weight: 500; color: {INK}">{name}</span>{tag(hex_, size=9.5)}</span>')


def neutral(name, value, bg, ink):
    return (f'<span style="flex: 1; min-width: 0; height: 64px; border-radius: 8px; background: {bg}; border: 0.5px solid {LINE}; display: flex; align-items: center; gap: 12px; padding: 0 14px; box-sizing: border-box">'
            f'{vm.turned(TWIN, ink, 36, HELD, FIXED_EYE.get(ink, am.EYE_INK))}<span style="display: flex; flex-direction: column; gap: 2px"><span style="font-size: 12px; font-weight: 600; color: {ink}">{name}</span>'
            f'<span style="font-family: {MONO}; font-size: 10px; color: {ink}; opacity: 0.7">{value}</span></span></span>')


def legacy_table():
    cells = "".join(cell(vm.mark(shape, marks.accent_of(shape), 28, still=True), legacy, 84, "→ " + shape) for legacy, shape in am.LEGACY_SHAPE.items())
    return f'<div style="display: grid; grid-template-columns: repeat(12, 1fr); gap: 12px 0">{cells}</div>'


def family_board():
    grid = f'<div style="display: grid; grid-template-columns: repeat(6, 84px); gap: 12px 0; justify-content: space-between">{"".join(swatch(n, h) for n, h in am.PALETTE)}</div>'
    neutrals = (f'<div style="display: flex; gap: 12px">{neutral("alpi · ink", "14110c · on light", PAPER, INK_LIGHT)}'
                f'{neutral("alpi · cream", "f3efe6 · on dark", NIGHT, CREAM)}</div>')
    return board("family", "Brand · the family", "Twelve soft shapes in twelve accents, and alpi in neutral ink.",
                 f"A profile is a shape and an accent from <code>common/accents.mjs</code>, {PAIRS} pairs in all; the shapes share their area and optical centre so no profile shouts in a row.",
                 block("The twelve shapes", turning_family(),
                       caption("Soft bodies of equal area, one flat fill, two eyes filled in the paper tone of the theme (white on light, black on dark), nothing else; in light amber, orange, rose, sky, teal, green and lime draw their body a step deeper with <code>markTone</code> so the white eyes hold 3:1, while the stored accent never changes; at rest each holds an angle; only a hero mark turns toward the pointer, and every mark holds its still pose while the window is in the background.")),
                 block("The palette", grid, neutrals,
                       caption("The twelve shipped accents as stored; a mark draws the body in <code>markTone(accent, theme)</code>, the accent itself in dark. alpi alone is neutral, ink on light and cream on dark, never an accent.")),
                 block("Legacy ids", legacy_table(),
                       caption("A profile stores and sends its shape name (<code>tui.shape</code>, <code>shape</code> in the summaries). Every input takes shape names only; the daemon alone reads an old config that still stores <code>tui.fold</code> and translates it one to one through <code>LEGACY_SHAPE</code>, and the default profile is always <code>twin</code>.")))


def expression(name, colour):
    o = am.outline("round")
    pair = am.eye_pair("round", 56, am._k(0, name))
    eyes = "".join(f'<path d="{am._d(p)}" fill="{am.EYE_INK}"/>' for p in pair)
    return (f'<svg viewBox="0 0 100 100" width="56" height="56" role="img" aria-label="{name}" data-mark="round" style="display: block; overflow: visible">'
            f'{am._filled(o["d"], am.body_fill(colour), eyes)}</svg>')


def state_rows():
    head = (f'<div style="display: flex; gap: 10px; font-family: {MONO}; font-size: 10px; color: {INK3}"><span style="width: 74px">state</span>'
            f'<span style="flex: 1.3">what the app knows</span><span style="flex: 1">eyes</span><span style="width: 150px">body</span></div>')
    rows = "".join(f'<div style="display: flex; gap: 10px; padding: 6px 0; border-top: 0.5px solid {LINE}; font-size: 11.5px; line-height: 1.4">'
                   f'<span style="width: 74px; flex-shrink: 0; font-weight: 600; color: {INK}">{am.STATE_LABEL[s]}</span>'
                   f'<span style="flex: 1.3; color: {INK2}">{am.STATE_TABLE[s][0]}</span><span style="flex: 1; color: {INK3}">{am.STATE_TABLE[s][1]}</span>'
                   f'<span style="width: 150px; flex-shrink: 0; color: {INK3}">{am.STATE_TABLE[s][2]} · {am.STATE_TABLE[s][3]}</span></div>' for s in am.STATES)
    return f'<div style="display: flex; flex-direction: column; gap: 4px">{head}{rows}</div>'


def eyes_board():
    blue = am.COLOUR["orange"]
    faces = "".join(cell(expression(name, blue), name, 120, am.EXPRESSION_LABEL[name].split(" · ")[1]) for name in am.EXPRESSIONS)
    return board("eyes", "Brand · eyes and states", "Two eyes that say what the profile is doing.",
                 f"The eyes are filled in the paper tone of the theme, white on light and black on dark, drawn over the body, and morph between {len(am.EXPRESSIONS)} expressions, each a {am.EYE_POINTS}-point outline, so any two blend; "
                 "every state plays a sequence of them and keeps one still expression for small sizes and reduced motion.",
                 block("Expressions", f'<div style="display: flex; justify-content: space-between">{faces}</div>'),
                 block("Eight states", state_rows(),
                       caption(f"Every state has a still form readable at 16 px; motion starts at {am.MOTION_MIN} px and never runs under reduce motion. "
                               "Paused draws a dashed neutral outline with no fill; offline fades the mark to 30 %. A profile with no model reads needs. "
                               "In the sidebar and the roster only the selected row moves; every other row holds the still form of its state.")))


def sizes_ladder():
    blue = am.COLOUR["blue"]
    return row(*(cell(vm.mark("squircle", blue, px, seed="ladder" + key), f"{key} {px}") for key, px in am.MARK_SIZES.items()), gap=30)


def motion_board():
    return board("motion", "Brand · motion", "Each state is a way of turning.",
                 "The flat mark turns in 3D perspective while the eyes slide and narrow toward the side it faces, as if painted on a rounded solid. "
                 f"At rest it holds an angle; at {ROW} px and below a smaller fixed one; paused and offline face you, and under reduce motion every mark faces you, still.",
                 block("States, turning · 52 live and 16 still", turn_strip(), turn_table()),
                 block("One turn, frame by frame", frame_strip()),
                 block("Sizes", sizes_ladder(),
                       caption("One scale for every surface, <code>MARK_SIZES</code> in <code>common/agentMarks.mjs</code>: inline in text, row in the sidebar and menus, header beside a title, "
                               "list in phone rows, the inbox and the picker, tile for pinned profiles, hero on empty and first-run pages.")))


def names_board():
    def name_cell(shape, colour, bg, ground_):
        tone = marks.name_tone(colour, ground_)
        theme = "light" if ground_ == LIGHT_GROUND else "dark"
        return (f'<span style="display: inline-flex; align-items: center; gap: 10px; padding: 8px 14px; border-radius: 8px; background: {bg}">'
                f'{vm.mark(shape, colour, ROW, still=True, theme=theme)}{solid(shape, 22, am.rgb(tone))}</span>')
    rows = "".join(f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">{name_cell(shape, am.COLOUR[name], PAPER, LIGHT_GROUND)}'
                   f'{name_cell(shape, am.COLOUR[name], NIGHT, DARK_GROUND)}</div>' for shape, name in am.FAMILY)
    head = f'<div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px">{tag("light · the name a step darker")}{tag("dark · the name a step lighter")}</div>'
    return board("names", "Brand · names", "Names in the UI, solid, in the profile’s tone.",
                 "Profile and workgroup names are set solid in the wordmark’s face and weight. A profile’s mark carries its accent (in light a pale one a step deeper, from <code>markTone</code>); its name is the same hue one step darker on light "
                 "and one step lighter on dark, moved further only until it reads at 4.5:1, from <code>nameTone</code> in <code>common/name.mjs</code>. A workgroup’s name is neutral ink, cream in dark, like alpi’s.",
                 block("The twelve accents on both grounds", f'<div style="display: flex; flex-direction: column; gap: 6px">{head}{rows}</div>'))


def workgroups_board():
    return board("workgroups", "Brand · workgroups", "Workgroups are places: a neutral soft honeycomb that lights up, only when something happens, in the accent of the profile at work.",
                 "Three soft cells in neutral ink, without eyes, turning in 3D like the marks. Idle, done and queued stay neutral (queued as an outline); running fills the current phase cell in the accent of the profile that owns the phase (the hub’s when the owner is not a profile on this device), "
                 "the finished cells faint and the pending ones outlined; needs you squares up and lifts the waiting cell in that accent; failed fills that cell in the danger tone and turns away; "
                 "paused is a dashed outline and offline is faint. The colour says who works, and the meta names them in words.",
                 block(f"States · {wg.PREVIEW} turning, {ROW} and {wg.INLINE} still", honeycomb_strip()),
                 block("The turn follows the pipeline", pipeline_turns(),
                       caption("The current cell is the phase in progress, lit in the colour of the profile that owns it, so the mark says where the run is and who works, even still at 20 px; the meta names the owner.")),
                 block("Titles · neutral ink, cream in dark, never the hub’s tone; rows keep the plain row type", workgroup_names()),
                 block("Sizes · one scale with the marks", honeycomb_sizes()))


def gate_board():
    items = "".join(f'<div style="display: flex; gap: 12px; padding: 9px 0; border-top: 0.5px solid {LINE}; font-size: 13px; line-height: 1.45">'
                    f'<span style="width: 18px; flex-shrink: 0; font-family: {MONO}; font-size: 11px; color: {INK3}">{i}</span>'
                    f'<span style="flex: 1; color: {INK}">{text}</span></div>' for i, text in enumerate(GATE, 1))
    return board("gate", "Brand · the gate", "What every mark must pass.",
                 "A new shape, a new state or a change to Twin enters only if it passes every rule; <code>tests/test_design_kit.py</code> computes them from <code>common/agentMarks.mjs</code>.",
                 block("The Brand gate", f'<div style="display: flex; flex-direction: column">{items}</div>'))


BRAND_BOARDS = [
    ("Brand-Mark.dc.html", mark_board, HEIGHTS["mark"], "Mark"),
    ("Brand-Wordmark.dc.html", wordmark_board, HEIGHTS["wordmark"], "Wordmark"),
    ("Brand-Icon.dc.html", icon_board, HEIGHTS["icon"], "App icon"),
    ("Brand-Family.dc.html", family_board, HEIGHTS["family"], "Family and palette"),
    ("Brand-Eyes.dc.html", eyes_board, HEIGHTS["eyes"], "Eyes and states"),
    ("Brand-Motion.dc.html", motion_board, HEIGHTS["motion"], "Motion"),
    ("Brand-Names.dc.html", names_board, HEIGHTS["names"], "Names"),
    ("Brand-Workgroups.dc.html", workgroups_board, HEIGHTS["workgroups"], "Workgroups"),
    ("Brand-Gate.dc.html", gate_board, HEIGHTS["gate"], "Gate"),
]
