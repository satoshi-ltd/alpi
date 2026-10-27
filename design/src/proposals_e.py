from gen import identity_glyph
from desktop_boards import INK, INK3, LINE2, MONO


def bar(w, h=5, color=LINE2, gap=6):
    return f'<div style="height: {h}px; width: {w}%; border-radius: 3px; background: {color}; margin-bottom: {gap}px"></div>'


def lines(*widths):
    return "".join(bar(w) for w in widths)


def chart_block():
    cols = "".join(f'<div style="flex: 1; background: #e3b3b3; height: {h}px; border-radius: 2px 2px 0 0"></div>' for h in (30, 42, 24, 52, 36, 46))
    return f'<div style="display: flex; align-items: flex-end; gap: 4px; height: 56px; margin: 4px 0 10px; border-bottom: 0.5px solid {LINE2}">{cols}</div>'


def sheet(inner, header="", footer=""):
    return (f'<div style="width: 250px; height: 354px; box-sizing: border-box; padding: 16px 18px; background: #ffffff; border: 0.5px solid {LINE2}; border-radius: 3px; '
            f'box-shadow: 0 2px 10px rgba(20,20,20,0.08); display: flex; flex-direction: column; flex-shrink: 0">{header}'
            f'<div style="flex: 1; min-height: 0; overflow: hidden">{inner}</div>{footer}</div>')


def title_block(meta=True):
    line = f'<div style="font-family: {MONO}; font-size: 7px; color: {INK3}; margin-bottom: 6px">@sentinel · casa · Oct 27, 2026</div>' if meta else ""
    return line + f'<div style="font-size: 13px; font-weight: 600; color: {INK}; margin-bottom: 10px">Weekly review report</div>'


def running_header(mark_px=9):
    return (f'<div style="display: flex; align-items: center; gap: 5px; padding-bottom: 5px; margin-bottom: 8px; border-bottom: 0.5px solid {LINE2}; font-family: {MONO}; font-size: 6.5px; color: {INK3}">'
            f'{identity_glyph("alpi", "#14110c", mark_px)}<b style="font-family: sans-serif; font-size: 7.5px; color: {INK}">alpi</b>'
            f'<span style="white-space: nowrap">· @sentinel · casa</span><span style="flex: 1"></span><span style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis">Weekly review report</span></div>')


def running_footer(n, total):
    return (f'<div style="display: flex; align-items: center; padding-top: 5px; margin-top: 8px; border-top: 0.5px solid {LINE2}; font-family: {MONO}; font-size: 6.5px; color: {INK3}">'
            f'<span>@sentinel · Oct 27, 2026</span><span style="flex: 1"></span><span>{n} / {total}</span></div>')


def end_footer():
    return (f'<div style="display: flex; align-items: center; gap: 5px; padding-top: 5px; margin-top: 8px; border-top: 0.5px solid {LINE2}; font-family: {MONO}; font-size: 6.5px; color: {INK3}">'
            f'{identity_glyph("alpi", "#14110c", 9)}<b style="font-family: sans-serif; font-size: 7.5px; color: {INK}">alpi</b><span>· @sentinel on casa · Oct 27, 2026</span></div>')


def strip(*sheets):
    return f'<div style="display: flex; gap: 14px; overflow: hidden">{"".join(sheets)}</div>'


def pdf_now():
    p1 = sheet(title_block() + lines(100, 96, 92, 100, 70) + chart_block() + lines(100, 94, 98, 60))
    p2 = sheet(lines(100, 92, 97, 88, 100, 74, 100, 90, 96, 62), footer=end_footer())
    return strip(p1, p2)


def pdf_proposed():
    p1 = sheet(title_block(False) + lines(100, 96, 92, 100, 70) + chart_block() + lines(100, 94, 98, 60), running_header(), running_footer(1, 2))
    p2 = sheet(lines(100, 92, 97, 88, 100, 74, 100, 90, 96, 62), running_header(), running_footer(2, 2))
    return strip(p1, p2)


PROPOSALS_E = [
    dict(
        id="UI-EXPORT.PAGES", client="desktop", area="PDF export",
        title="An exported PDF has a header and a page number on every page",
        why=("Today the PDF carries one meta line above the title on page 1 and one footer after the last block, so a loose page 2 does not say whose report it is, "
             "and nothing numbers the pages. A header cannot be done in CSS here: a WKWebView print operation on macOS (the engine behind the desktop print sheet) repeats neither a "
             "<code>thead</code> nor a <code>position: fixed</code> element, which both print on page 1 only, and WebKit has no page-margin boxes or page counters. "
             "The proposal builds the pages itself. The hidden print root measures every block (a paragraph, a list item, a table row, a chart, a code line group), packs them into fixed-height pages "
             "and gives each page its own running header (mark, profile, server, title) and footer (profile, date, page n / m). A block taller than a page splits by code line or table row. "
             "The phone keeps today's single footer: <code>expo-print</code> has no measured layout before it prints, so it needs a device check first."),
        mobile=(pdf_now, None),
        desktop=(pdf_now, pdf_proposed),
        accept=("A pure <code>paginate(heights, pageHeight)</code> in <code>common/messageExport.mjs</code> packs measured block heights into pages, never splits a chart or a table row, "
                "splits an over-tall code block by line, and is covered by unit tests; every page of <code>exportArticle</code> carries the header and the footer with its number and the total; "
                "the single end-of-document footer goes away on desktop; the page size follows the print sheet's paper (A4 or Letter) with the margins of today; the Markdown export is unchanged. "
                "A creator <code>verify</code> task checks the printed PDF on macOS: header and footer on pages 2 and later, no block cut across pages."),
        h=1180,
    ),
]
