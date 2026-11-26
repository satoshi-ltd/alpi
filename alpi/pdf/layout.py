from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

from markdown_it import MarkdownIt

from alpi.pdf import ttf
from alpi.pdf.writer import PAGE_HEIGHT, PAGE_WIDTH, Document, Page

MAX_MARKDOWN_CHARS = 150_000
MAX_PAGES = 300
MAX_TABLE_CELLS = 20_000
MAX_NESTING = 60
PAGE_BREAK = re.compile(r"^<!--\s*pagebreak\s*-->$", re.I)

LEFT = 56.0
RIGHT = PAGE_WIDTH - 56.0
TOP = PAGE_HEIGHT - 60.0
BOTTOM = 64.0

INK = (0.1, 0.1, 0.11)
MUTED = (0.45, 0.45, 0.48)
LINK = (0.15, 0.39, 0.92)
RULE = (0.83, 0.83, 0.85)
SHADE = (0.957, 0.957, 0.961)

BODY = 10.5
LEADING = 1.45
HEADINGS = {1: 20.0, 2: 15.0, 3: 12.5, 4: 11.0, 5: 10.5, 6: 10.5}
CODE = 9.0
TABLE = 9.5
FOOTER = 8.0

_SUBSTITUTES = {
    "✓": "√", "✔": "√", "☑": "√", "✅": "√",
    "✗": "×", "✘": "×", "✕": "×", "✖": "×", "☒": "×", "❌": "×",
    "☐": "○", "□": "○", "■": "●", "▪": "●", "◆": "●", "◇": "○",
    "►": "▶", "‣": "•", "⁃": "•", "★": "*", "☆": "*", "⚠": "!",
    "\t": "    ",
}


class DocumentTooLarge(ValueError):
    pass


@dataclass(frozen=True)
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    href: str = ""


def _font(span: Span) -> ttf.TrueTypeFont:
    if span.code:
        return ttf.load("GeistMono-Regular")
    if span.bold and span.italic:
        return ttf.load("Geist-BoldItalic")
    if span.bold:
        return ttf.load("Geist-Bold")
    if span.italic:
        return ttf.load("Geist-Italic")
    return ttf.load("Geist-Regular")


def _drawable(text: str, font: ttf.TrueTypeFont) -> str:
    out = []
    for ch in unicodedata.normalize("NFC", text):
        if ch in "\r\n":
            continue
        if unicodedata.category(ch) in ("Cc", "Cf", "Cs") and ch != "\t":
            continue
        if font.glyph(ord(ch)):
            out.append(ch)
            continue
        sub = _SUBSTITUTES.get(ch, "")
        if sub and all(font.glyph(ord(c)) for c in sub):
            out.append(sub)
        elif unicodedata.category(ch) in ("Mn", "Me", "Sk") or ord(ch) in range(0xFE00, 0xFE10):
            continue
        elif unicodedata.category(ch) == "So":
            continue
        else:
            out.append("?")
    return "".join(out)


@dataclass
class _Fragment:
    text: str
    span: Span
    size: float
    color: tuple[float, float, float]
    width: float


def _inline(children) -> list[Span]:
    spans: list[Span] = []
    bold = italic = 0
    href = ""
    for tok in children or []:
        kind = tok.type
        if kind == "strong_open":
            bold += 1
        elif kind == "strong_close":
            bold = max(0, bold - 1)
        elif kind == "em_open":
            italic += 1
        elif kind == "em_close":
            italic = max(0, italic - 1)
        elif kind == "link_open":
            href = str(tok.attrGet("href") or "")
        elif kind == "link_close":
            href = ""
        elif kind == "text":
            spans.append(Span(tok.content, bool(bold), bool(italic), False, href))
        elif kind == "code_inline":
            spans.append(Span(tok.content, bool(bold), bool(italic), True, href))
        elif kind == "softbreak":
            spans.append(Span(" ", bool(bold), bool(italic), False, href))
        elif kind == "hardbreak":
            spans.append(Span("\n", bool(bold), bool(italic), False, href))
        elif kind == "image":
            alt = tok.content or "image"
            spans.append(Span(f"[{alt}]", bool(bold), True, False, href))
        elif kind == "html_inline":
            continue
    return spans


def _safe_href(href: str) -> str:
    return href if re.match(r"^(https?://|mailto:)", href, re.I) else ""


class Layout:
    def __init__(self, title: str = "") -> None:
        self.title = title
        self.doc = Document(title)
        self.page: Page | None = None
        self.y = TOP
        self.blank = True

    def _new_page(self) -> None:
        if len(self.doc.pages) >= MAX_PAGES:
            raise DocumentTooLarge(f"the document would run past {MAX_PAGES} pages")
        self.page = self.doc.new_page()
        self.y = TOP
        self.blank = True

    def _ensure(self, height: float) -> None:
        if self.page is None or (self.y - height < BOTTOM and not self.blank):
            self._new_page()

    def _space(self, gap: float) -> None:
        if self.page is not None and not self.blank:
            self.y -= gap

    def page_break(self) -> None:
        if self.page is not None and not self.blank:
            self._new_page()

    def _fragments(self, spans: list[Span], size: float, color) -> list[_Fragment]:
        frags = []
        for span in spans:
            font = _font(span)
            span_size = CODE * size / BODY if span.code else size
            text = span.text if span.text == "\n" else _drawable(span.text, font)
            for piece in re.findall(r"\n|[^\S\n]+|[^\s]+", text):
                width = 0.0 if piece == "\n" else font.width(piece, span_size)
                frags.append(_Fragment(piece, span, span_size, LINK if _safe_href(span.href) else color, width))
        return frags

    @staticmethod
    def _split_long(frag: _Fragment, limit: float) -> list[_Fragment]:
        font = _font(frag.span)
        parts: list[_Fragment] = []
        current: list[str] = []
        used = 0.0
        for ch in frag.text:
            advance = font.width(ch, frag.size)
            if current and used + advance > limit + 0.01:
                parts.append(_Fragment("".join(current), frag.span, frag.size, frag.color, used))
                current, used = [], 0.0
            current.append(ch)
            used += advance
        if current:
            parts.append(_Fragment("".join(current), frag.span, frag.size, frag.color, used))
        return parts

    def _lines(self, frags: list[_Fragment], width: float) -> list[list[_Fragment]]:
        lines: list[list[_Fragment]] = [[]]
        used = 0.0
        for frag in frags:
            if frag.text == "\n":
                lines.append([])
                used = 0.0
                continue
            if frag.text.isspace():
                if lines[-1]:
                    lines[-1].append(frag)
                    used += frag.width
                continue
            pieces = self._split_long(frag, width) if frag.width > width + 0.01 else [frag]
            for piece in pieces:
                if used + piece.width > width + 0.01 and lines[-1]:
                    while lines[-1] and lines[-1][-1].text.isspace():
                        used -= lines[-1].pop().width
                    lines.append([])
                    used = 0.0
                lines[-1].append(piece)
                used += piece.width
        for line in lines:
            while line and line[-1].text.isspace():
                line.pop()
        return lines if any(lines) else [[]]

    def _draw_line(self, line: list[_Fragment], x: float, baseline: float) -> None:
        runs: list[_Fragment] = []
        for frag in line:
            last = runs[-1] if runs else None
            if last and last.span == frag.span and last.size == frag.size and last.color == frag.color:
                runs[-1] = _Fragment(last.text + frag.text, last.span, last.size, last.color, last.width + frag.width)
            else:
                runs.append(frag)
        for run in runs:
            self.doc.text(self.page, _font(run.span), run.size, x, baseline, run.text, run.color)
            href = _safe_href(run.span.href)
            if href:
                self.doc.link(self.page, x, baseline - run.size * 0.25, run.width, run.size * 1.15, href)
            x += run.width

    def paragraph(self, spans: list[Span], *, size: float = BODY, indent: float = 0.0,
                  color=INK, prefix: str = "", bar: float | None = None,
                  before: float = 0.0, after: float = 6.0, keep: float = 0.0) -> None:
        lead = size * LEADING
        width = RIGHT - LEFT - indent
        lines = self._lines(self._fragments(spans, size, color), width)
        self._space(before)
        for index, line in enumerate(lines):
            self._ensure(lead + (keep if index == 0 else 0.0))
            baseline = self.y - size
            if index == 0 and prefix:
                marker = Span(prefix)
                font = _font(marker)
                text = _drawable(prefix, font)
                marker_x = max(LEFT - 40.0, LEFT + indent - font.width(text, size) - 5)
                self.doc.text(self.page, font, size, marker_x, baseline, text, color)
            if bar is not None:
                self.doc.line(self.page, LEFT + bar, self.y, LEFT + bar, self.y - lead, RULE, 2.0)
            self._draw_line(line, LEFT + indent, baseline)
            self.y -= lead
            self.blank = False
        self.y -= after

    def heading(self, level: int, spans: list[Span]) -> None:
        size = HEADINGS.get(level, BODY)
        bold = [Span(s.text, True, s.italic, s.code, s.href) for s in spans]
        before = {1: 16.0, 2: 14.0, 3: 10.0}.get(level, 8.0)
        self.paragraph(bold, size=size, before=before, after=6.0 if level <= 2 else 4.0,
                       keep=BODY * LEADING * 2)
        if level == 1:
            self.doc.line(self.page, LEFT, self.y + 3, RIGHT, self.y + 3, RULE, 0.8)
            self.y -= 4

    def code(self, text: str, *, indent: float = 0.0) -> None:
        font = ttf.load("GeistMono-Regular")
        lead = CODE * 1.4
        width = RIGHT - LEFT - indent - 16
        self._space(4)
        raw_lines = text.rstrip("\n").split("\n") or [""]
        for raw in raw_lines:
            drawable = _drawable(raw.replace("\t", "    "), font)
            pieces = [drawable] if font.width(drawable, CODE) <= width else [
                f.text for f in self._split_long(_Fragment(drawable, Span(drawable, code=True), CODE, INK,
                                                           font.width(drawable, CODE)), width)
            ]
            for piece in pieces or [""]:
                self._ensure(lead)
                self.doc.rect(self.page, LEFT + indent, self.y - lead, RIGHT - LEFT - indent, lead, fill=SHADE)
                if piece:
                    self.doc.text(self.page, font, CODE, LEFT + indent + 8, self.y - CODE - 1, piece, INK)
                self.y -= lead
                self.blank = False
        self.y -= 8

    def rule(self) -> None:
        self._ensure(14)
        self.y -= 6
        self.doc.line(self.page, LEFT, self.y, RIGHT, self.y, RULE, 0.8)
        self.y -= 8
        self.blank = False

    def table(self, rows: list[list[list[Span]]], header_rows: int, *, indent: float = 0.0) -> None:
        if not rows:
            return
        columns = max(len(r) for r in rows)
        if columns * len(rows) > MAX_TABLE_CELLS:
            raise DocumentTooLarge(f"a table has over {MAX_TABLE_CELLS:,} cells")
        rows = [
            [[Span(s.text, s.bold or i < header_rows, s.italic, s.code, s.href) for s in cell] for cell in r]
            + [[]] * (columns - len(r))
            for i, r in enumerate(rows)
        ]
        avail = RIGHT - LEFT - indent
        pad = min(5.0, avail / columns / 4)
        lead = TABLE * 1.35
        floor, natural = [], []
        for c in range(columns):
            longest = full = 0.0
            for r in rows:
                frags = self._fragments(r[c], TABLE, INK)
                full = max(full, sum(f.width for f in frags))
                longest = max([longest] + [f.width for f in frags if not f.text.isspace()])
            floor.append(min(longest, avail) + 2 * pad)
            natural.append(min(full, avail) + 2 * pad)
        if sum(natural) <= avail:
            widths = natural
        elif sum(floor) >= avail:
            widths = [0.0] * columns
            room, left = avail, columns
            for c in sorted(range(columns), key=lambda k: floor[k]):
                widths[c] = min(floor[c], room / left)
                room -= widths[c]
                left -= 1
        else:
            grow = [n - f for n, f in zip(natural, floor)]
            extra = avail - sum(floor)
            widths = [f + g * extra / sum(grow) for f, g in zip(floor, grow)]
        cells = [
            [self._lines(self._fragments(cell, TABLE, INK), widths[c] - 2 * pad) for c, cell in enumerate(row)]
            for row in rows
        ]
        header_height = sum((max(len(cell) for cell in cells[h]) or 1) * lead + 2 * pad for h in range(header_rows))
        repeat = header_rows and header_height <= (TOP - BOTTOM) / 3
        self._space(4)
        if self.page is None:
            self._new_page()

        def draw(index: int, lines: list[list[list[_Fragment]]], count: int) -> None:
            height = count * lead + 2 * pad
            x = LEFT + indent
            for c, cell_lines in enumerate(lines):
                fill = SHADE if index < header_rows else None
                self.doc.rect(self.page, x, self.y - height, widths[c], height, fill=fill, stroke=RULE, line=0.5)
                for n, line in enumerate(cell_lines[:count]):
                    self._draw_line(line, x + pad, self.y - pad - (n + 1) * lead + (lead - TABLE) * 0.6)
                x += widths[c]
            self.y -= height
            self.blank = False

        fresh = False
        for index, row in enumerate(cells):
            remaining = [list(cell) for cell in row]
            while True:
                need = max(len(cell) for cell in remaining) or 1
                room = int((self.y - BOTTOM - 2 * pad) // lead)
                fits_a_page = need * lead + 2 * pad <= TOP - BOTTOM - (header_height if repeat else 0.0)
                if room < 1 or (room < need and fits_a_page and not self.blank and not fresh):
                    self._new_page()
                    if repeat and index >= header_rows:
                        for h in range(header_rows):
                            hrow = [list(cell) for cell in cells[h]]
                            draw(h, hrow, max(len(cell) for cell in hrow) or 1)
                        fresh = True
                    continue
                count = min(need, room)
                draw(index, remaining, count)
                fresh = False
                remaining = [cell[count:] for cell in remaining]
                if not any(remaining):
                    break
        self.y -= 8

    def finish(self) -> bytes:
        if not self.doc.pages:
            self._new_page()
        total = len(self.doc.pages)
        font = ttf.load("Geist-Regular")
        label = _drawable(self.title, font)
        for number, page in enumerate(self.doc.pages, start=1):
            counter = f"{number} / {total}"
            self.doc.line(page, LEFT, BOTTOM - 18, RIGHT, BOTTOM - 18, RULE, 0.5)
            if label:
                limit = RIGHT - LEFT - font.width(counter, FOOTER) - 24
                shown = label
                while shown and font.width(shown, FOOTER) > limit:
                    shown = shown[:-2] + "…"
                self.doc.text(page, font, FOOTER, LEFT, BOTTOM - 30, shown, MUTED)
            self.doc.text(page, font, FOOTER, RIGHT - font.width(counter, FOOTER), BOTTOM - 30, counter, MUTED)
        return self.doc.render()


def _chart_rows(info: str, content: str) -> tuple[str, list[list[list[Span]]]] | None:
    if info.strip().split(" ")[0].lower() != "chart":
        return None
    try:
        spec = json.loads(content)
        labels = [str(x) for x in spec["x"]]
        series = [(str(s.get("name") or ""), list(s.get("values") or [])) for s in spec["series"]]
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    unit = str(spec.get("unit") or "")
    header = [[Span("")]] + [[Span(name)] for name, _ in series]
    rows = [header]
    for i, label in enumerate(labels):
        row = [[Span(label)]]
        for _, values in series:
            value = values[i] if i < len(values) else None
            row.append([Span("" if value is None else f"{value}{unit}")])
        rows.append(row)
    return str(spec.get("title") or ""), rows


@dataclass
class Rendered:
    data: bytes
    pages: int
    title: str


def _fragments_join(state) -> None:
    level = 0
    kept = []
    parts: dict[int, list[str]] = {}
    for tok in state.tokens:
        if tok.nesting < 0:
            level -= 1
        tok.level = level
        if tok.nesting > 0:
            level += 1
        if tok.type == "text" and kept and kept[-1].type == "text":
            parts.setdefault(id(kept[-1]), [kept[-1].content]).append(tok.content)
        else:
            kept.append(tok)
    for tok in kept:
        if id(tok) in parts:
            tok.content = "".join(parts[id(tok)])
    state.tokens[:] = kept


def _first_title(tokens) -> str:
    for index, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.tag == "h1" and index + 1 < len(tokens):
            return "".join(s.text for s in _inline(tokens[index + 1].children)).strip()
    return ""


def render(markdown: str, title: str = "") -> Rendered:
    if len(markdown) > MAX_MARKDOWN_CHARS:
        raise DocumentTooLarge(f"the Markdown is over {MAX_MARKDOWN_CHARS:,} characters")
    parser = MarkdownIt("commonmark", {"maxNesting": MAX_NESTING}).enable("table").enable("strikethrough")
    parser.inline.ruler2.at("fragments_join", _fragments_join)
    tokens = parser.parse(markdown)
    raw_title = title.strip() or _first_title(tokens)
    title = " ".join("".join(ch for ch in raw_title if not 0xD800 <= ord(ch) <= 0xDFFF).split())[:200]
    layout = Layout(title)
    lists: list[dict] = []
    quote = 0
    pending: list[str] = []
    i = 0

    def indent() -> float:
        return min(18.0 * len(lists) + 14.0 * quote, (RIGHT - LEFT) / 2)

    def bar() -> float | None:
        return min(14.0 * quote, (RIGHT - LEFT) / 2) - 8.0 if quote else None

    while i < len(tokens):
        tok = tokens[i]
        kind = tok.type
        if kind == "heading_open":
            layout.heading(int(tok.tag[1]), _inline(tokens[i + 1].children))
            i += 3
            continue
        if kind == "paragraph_open":
            spans = _inline(tokens[i + 1].children)
            prefix = pending.pop() if pending else ""
            in_list = bool(lists)
            layout.paragraph(spans, indent=indent(), prefix=prefix, bar=bar(),
                             after=2.0 if in_list and tok.hidden else 6.0)
            i += 3
            continue
        if kind in ("bullet_list_open", "ordered_list_open"):
            start = int(tok.attrGet("start") or 1) if kind == "ordered_list_open" else 0
            lists.append({"ordered": kind == "ordered_list_open", "n": start})
        elif kind in ("bullet_list_close", "ordered_list_close"):
            lists.pop()
            if not lists:
                layout.y -= 4
        elif kind == "list_item_open":
            current = lists[-1]
            if current["ordered"]:
                pending.append(f"{current['n']}.")
                current["n"] += 1
            else:
                pending.append("•" if len(lists) % 2 else "◦" if ttf.load("Geist-Regular").glyph(ord("◦")) else "-")
        elif kind == "list_item_close":
            if pending:
                pending.pop()
        elif kind == "blockquote_open":
            quote += 1
        elif kind == "blockquote_close":
            quote = max(0, quote - 1)
        elif kind in ("fence", "code_block"):
            chart = _chart_rows(tok.info or "", tok.content) if kind == "fence" else None
            if pending:
                layout.paragraph([Span("")], indent=indent(), prefix=pending.pop(), after=0.0)
            if chart:
                chart_title, rows = chart
                if chart_title:
                    layout.paragraph([Span(chart_title, bold=True)], indent=indent(), after=2.0, keep=40.0)
                layout.table(rows, 1, indent=indent())
            else:
                layout.code(tok.content, indent=indent())
        elif kind == "hr":
            layout.rule()
        elif kind == "html_block":
            if PAGE_BREAK.match(tok.content.strip()):
                layout.page_break()
            else:
                text = re.sub(r"<[^>]+>", "", tok.content).strip()
                if text:
                    layout.paragraph([Span(text)], indent=indent(), bar=bar())
        elif kind == "table_open":
            rows: list[list[list[Span]]] = []
            header_rows = 0
            in_head = False
            row: list[list[Span]] = []
            j = i + 1
            while j < len(tokens) and tokens[j].type != "table_close":
                t = tokens[j]
                if t.type == "thead_open":
                    in_head = True
                elif t.type == "thead_close":
                    in_head = False
                elif t.type == "tr_open":
                    row = []
                elif t.type == "tr_close":
                    rows.append(row)
                    if in_head:
                        header_rows += 1
                elif t.type == "inline":
                    row.append(_inline(t.children))
                j += 1
            if pending:
                layout.paragraph([Span("")], indent=indent(), prefix=pending.pop(), after=0.0)
            layout.table(rows, header_rows, indent=indent())
            i = j + 1
            continue
        i += 1
    data = layout.finish()
    return Rendered(data, len(layout.doc.pages), title)
