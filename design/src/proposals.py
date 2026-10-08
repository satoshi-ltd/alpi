import json
import os
import subprocess

import folds
from gen import page
from desktop_boards import INK, INK3, MONO
from conversation_boards import h1, label, mono, spec
from brand_boards import EXTRA_FONTS, crease

PAGE_W = 1280
COLUMN_PAD = 20


def drawing(title, inner):
    return f'<div style="flex: 1; min-width: 0; display: flex; flex-direction: column">{spec(title, inner, pad=COLUMN_PAD)}</div>'


def cap(text):
    return mono(text, 11, INK3)


def stack(*items, gap=14):
    return f'<div style="display: flex; flex-direction: column; gap: {gap}px">{"".join(items)}</div>'


def tagged(title, inner):
    return stack(cap(title), inner, gap=8)


def hero_palette():
    common = lambda name: json.dumps(os.path.join(folds.COMMON, name))
    script = (
        f"import {{ACCENTS, ACCENT_FOLDS}} from {common('accents.mjs')};"
        f"import {{creaseTones}} from {common('crease.mjs')};"
        f"import {{BRAND_INK}} from {common('folds.mjs')};"
        f"import {{palettes}} from {common('tokens.mjs')};"
        "const grounds = {paper: palettes.light.bg, night: palettes.dark.bg};"
        "const ink = {paper: [BRAND_INK.light, BRAND_INK.light], night: [BRAND_INK.dark, '#ffffff']};"
        "process.stdout.write(JSON.stringify({grounds,"
        "ink: Object.fromEntries(Object.entries(ink).map(([k, pair]) => [k, pair.map((hex) => creaseTones(hex, grounds[k]))])),"
        "accents: ACCENTS.map(([name, hex]) => ({name, hex, fold: ACCENT_FOLDS[name],"
        "paper: creaseTones(hex, grounds.paper), night: creaseTones(hex, grounds.night)}))}));"
    )
    out = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


# rgb() escapes build.py's THEMED hex rewrite, which would theme the site's own grounds away.
def rgb(value):
    return "rgb(%d, %d, %d)" % tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))


def hero_word(text, size, tones3):
    return crease(text, size, [rgb(t) for t in tones3], track="-0.03em")


def hero_panel(inner, ground, pad=22, gap=12):
    return (f'<div style="padding: {pad}px; border-radius: 10px; background: {rgb(ground)}; display: flex; flex-direction: column; gap: {gap}px; overflow: hidden">'
            f'{inner}</div>')


def hero_caption(text, ground):
    colour = "rgba(255,255,255,0.52)" if ground == hero_palette()["grounds"]["night"] else "rgba(20,20,20,0.5)"
    return f'<span style="font-family: {MONO}; font-size: 10.5px; letter-spacing: 0.05em; text-transform: uppercase; color: {colour}">{text}</span>'


def hero_now_lines(key, size=40):
    first, second = hero_palette()["ink"][key]
    return (f'<div style="display: flex; flex-direction: column; gap: 2px">'
            f'<span>{hero_word("Your agents.", size, first)}</span><span>{hero_word("Your machines.", size, second)}</span></div>')


def hero_cycle_lines(key, accent, size=40):
    first, second = hero_palette()["ink"][key]
    return (f'<div style="display: flex; flex-direction: column; gap: 2px">'
            f'<span>{hero_word("Your&nbsp;", size, first)}{hero_word("agents.", size, accent[key])}</span>'
            f'<span>{hero_word("Your machines.", size, second)}</span></div>')


def cycle_words(key, size=21):
    cells = []
    for accent in hero_palette()["accents"]:
        cells.append(f'<div style="display: flex; flex-direction: column; gap: 3px; align-items: flex-start">'
                     f'<span>{hero_word("agents", size, accent[key])}</span>{hero_caption(accent["name"], hero_palette()["grounds"][key])}</div>')
    return f'<div style="display: flex; flex-wrap: wrap; gap: 14px 22px">{"".join(cells)}</div>'


def cycle_bar(key, h=14):
    accents = hero_palette()["accents"]
    cells = []
    for i, accent in enumerate(accents):
        this = rgb(accent[key][0])
        nxt = rgb(accents[(i + 1) % len(accents)][key][0])
        cells.append(f'<div style="flex: 1; background: linear-gradient(90deg, {this} 0 80%, {nxt} 100%)"></div>')
    return f'<div style="display: flex; height: {h}px; border-radius: {h // 2}px; overflow: hidden">{"".join(cells)}</div>'


ON_PAGE = ("shield", "tree", "star", "rocket")
NAMED = (("reviewer", "blue"), ("librarian", "green"), ("researcher", "violet"))


def page_pair(accent, size=30):
    dim = "" if accent["fold"] in ON_PAGE else "; opacity: 0.28"
    return f'<span style="display: inline-flex{dim}">{folds.fold(accent["fold"], accent["hex"], size)}</span>'


def profile_names(key, size=18):
    by_name = {a["name"]: a for a in hero_palette()["accents"]}
    items = []
    for name, colour in NAMED:
        accent = by_name[colour]
        items.append(f'<span style="display: inline-flex; align-items: center; gap: 8px">'
                     f'{folds.fold(accent["fold"], accent["hex"], size)}{hero_word(name, size, accent[key])}</span>')
    return f'<div style="display: flex; flex-wrap: wrap; gap: 10px 22px; align-items: center">{"".join(items)}</div>'


def hero_colour_now():
    paper, night = hero_palette()["grounds"]["paper"], hero_palette()["grounds"]["night"]
    return EXTRA_FONTS + stack(
        tagged("Night · as it ships", hero_panel(hero_now_lines("night") + hero_caption("--crease-first and --crease-second · one ink ladder", night), night)),
        tagged("Paper · as it ships", hero_panel(hero_now_lines("paper") + hero_caption("--crease-first and --crease-second · one ink ladder", paper), paper)),
        tagged("Four of the twelve reach the page; the other eight never do",
               f'<div style="display: flex; flex-wrap: wrap; gap: 10px">'
               f'{"".join(page_pair(a) for a in hero_palette()["accents"])}</div>'),
        tagged("profileName() already creases a colour, at 14, 18 and 28 px",
               stack(hero_panel(profile_names("night"), night, pad=16), hero_panel(profile_names("paper"), paper, pad=16), gap=10)),
        cap("Both lines take creaseTones(BRAND_INK, ground): near-black down to warm grey on paper, white down to warm grey on night. The largest word on the page is the one place a profile colour never reaches."),
    )


def hero_colour_proposed():
    accents = {a["name"]: a for a in hero_palette()["accents"]}
    paper, night = hero_palette()["grounds"]["paper"], hero_palette()["grounds"]["night"]
    return stack(
        tagged("Night · at rest and under reduced motion",
               hero_panel(hero_cycle_lines("night", accents["amber"]) + hero_caption("amber · step 1 and step 13", night), night)),
        tagged("Night · the pass", hero_panel(cycle_words("night") + cycle_bar("night"), night, gap=16)),
        tagged("Paper · at rest and under reduced motion",
               hero_panel(hero_cycle_lines("paper", accents["amber"]) + hero_caption(f'amber, darkened to {accents["amber"]["paper"][0]} by the ladder', paper), paper)),
        tagged("Paper · the pass", hero_panel(cycle_words("paper") + cycle_bar("paper"), paper, gap=16)),
        cap("2.4 s held, 0.6 s crossfaded, twelve steps in the order of ACCENTS — the wheel from amber back to amber — then it stops. 36 s in all, paused while the hero is off screen."),
        cap("Paper keeps the hue and loses the swatch: nine of the twelve only clear 3:1 on paper after creaseTones darkens them, so the bands sit closer together there than on night."),
    )


PROPOSALS = [
    {
        "id": "UI-SITE.HERO-COLOUR",
        "client": "site",
        "area": "Hero · the landing headline",
        "title": "The word “agents” wears the twelve profile colours, once",
        "why": "The hero is two creased lines in the same ink: brandCss() builds --crease-first and --crease-second from creaseTones(BRAND_INK, ground) (site/scripts/brand.mjs, ladders), so <span class=\"crease crease-first\">Your agents.</span> (site/templates/landing.html:470) is grey on paper and white on night. Colour is already beside it: the console in the same hero draws reviewer, librarian and builder as their objects in blue, green and teal, and profileName() creases those names in their own colour at 14, 18 and 28 px further down — four of the twelve pairs, and the other eight never reach the page at all. The largest words on the site say “your agents” in the one voice no agent has, next to a terminal already proving the opposite. The mechanism needs nothing new: creaseTones(accent, ground) takes any accent to a legible three-tone ladder and creaseGradient turns it into the same band gradient. Measured on the hero’s own grounds, palettes.light.bg and palettes.dark.bg, all twelve accents clear CREASE_MIN_CONTRAST in both themes and the floor is 3.13:1 (vermilion on night) — but nine of the twelve only clear it on paper after the ladder darkens them, so paper keeps the hue and loses the swatch. Recommendation: the word “agents” alone carries the cycle, in the order of ACCENTS, which is already the hue wheel starting at amber; one pass of 36 s that settles back on amber; “machines.” stays ink, because the contrast is what makes the agents the coloured ones.",
        "now": hero_colour_now,
        "proposed": hero_colour_proposed,
        "accept": "The hero draws “Your” and “Your machines.” in the ink crease and the word “agents” in a profile colour. brandCss() emits one @keyframes per ground over three @property-registered <color> custom properties that feed creaseGradient, holding each of the twelve creaseTones(hex, ground) ladders 2.4 s and crossfading 0.6 s, twelve steps in ACCENTS order from amber back to amber, with animation-iteration-count 1 so the hero is still 36 s after load; an IntersectionObserver of a few lines pauses it while the hero is off screen, and no dependency is added. Under prefers-reduced-motion: reduce the animation is none and the word rests on amber, the colour the pass ends on. The new class joins .crease in the forced-colors and print resets. site/scripts/brand.test.mjs asserts the twenty-four ladders are three distinct tones each at CREASE_MIN_CONTRAST or better against palettes.light.bg and palettes.dark.bg, that the keyframes name all twelve accents in ACCENTS order and open and close on amber, and that the reduced-motion rule and both resets carry the class; site/scripts/build.test.mjs replaces its hero assertion with the new spans and checks “Your machines.” still reads --crease-second.",
        "h": 1580,
    },
]





def proposal_board(p):
    kicker = " · ".join((p["id"], p["client"], p["area"]))
    head = f'<div style="display: flex; flex-direction: column; gap: 10px">{label(kicker)}{h1(p["title"], p["why"])}</div>'
    drawings = f'<div style="display: flex; gap: 24px; align-items: stretch">{drawing("Now", p["now"]())}{drawing("Proposed", p["proposed"]())}</div>'
    accept = (f'<div style="display: flex; flex-direction: column; gap: 6px">{label("Accept")}'
              f'<p style="margin: 0; max-width: 1080px; font-size: 13px; line-height: 1.55; color: {INK}">{p["accept"]}</p></div>')
    body = (f'<div data-proposal="{p["id"]}" style="padding: 40px 48px; display: flex; flex-direction: column; gap: 26px; box-sizing: border-box">'
            f'{head}{drawings}{accept}</div>')
    return page("Proposal " + p["id"], PAGE_W, p["h"], body)


def board_name(p):
    return "Proposals-" + p["id"] + ".dc.html"


PROPOSAL_BOARDS = [(board_name(p), (lambda p=p: proposal_board(p)), p["h"], p["id"] + " · " + p["title"]) for p in PROPOSALS]
