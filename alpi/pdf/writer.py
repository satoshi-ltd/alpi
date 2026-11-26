from __future__ import annotations

import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone

from alpi.pdf.ttf import TrueTypeFont

PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89


def _num(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _pdf_string(text: str) -> str:
    text = "".join(ch for ch in text if not 0xD800 <= ord(ch) <= 0xDFFF)
    try:
        raw = text.encode("latin-1")
        escaped = raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
        return "(" + escaped.decode("latin-1") + ")"
    except UnicodeEncodeError:
        return "<FEFF" + text.encode("utf-16-be").hex().upper() + ">"


@dataclass
class _FontUse:
    font: TrueTypeFont
    resource: str
    used: dict[int, str] = field(default_factory=dict)


@dataclass
class Page:
    ops: list[str] = field(default_factory=list)
    links: list[tuple[float, float, float, float, str]] = field(default_factory=list)


class Document:
    def __init__(self, title: str = "") -> None:
        self.title = title
        self.pages: list[Page] = []
        self._fonts: dict[str, _FontUse] = {}

    def new_page(self) -> Page:
        page = Page()
        self.pages.append(page)
        return page

    def _font(self, font: TrueTypeFont) -> _FontUse:
        use = self._fonts.get(font.name)
        if use is None:
            use = _FontUse(font, f"F{len(self._fonts) + 1}")
            self._fonts[font.name] = use
        return use

    def text(self, page: Page, font: TrueTypeFont, size: float, x: float, y: float, text: str,
             color: tuple[float, float, float] = (0.1, 0.1, 0.1)) -> None:
        use = self._font(font)
        glyphs = []
        for ch in text:
            gid = font.glyph(ord(ch))
            use.used.setdefault(gid, ch)
            glyphs.append(f"{gid:04X}")
        r, g, b = color
        page.ops.append(
            f"BT {_num(r)} {_num(g)} {_num(b)} rg /{use.resource} {_num(size)} Tf "
            f"{_num(x)} {_num(y)} Td <{''.join(glyphs)}> Tj ET"
        )

    def rect(self, page: Page, x: float, y: float, w: float, h: float,
             fill: tuple[float, float, float] | None = None,
             stroke: tuple[float, float, float] | None = None, line: float = 0.5) -> None:
        parts = ["q"]
        if fill:
            parts.append(f"{_num(fill[0])} {_num(fill[1])} {_num(fill[2])} rg")
        if stroke:
            parts.append(f"{_num(stroke[0])} {_num(stroke[1])} {_num(stroke[2])} RG {_num(line)} w")
        op = "B" if fill and stroke else "f" if fill else "S"
        parts.append(f"{_num(x)} {_num(y)} {_num(w)} {_num(h)} re {op} Q")
        page.ops.append(" ".join(parts))

    def line(self, page: Page, x1: float, y1: float, x2: float, y2: float,
             color: tuple[float, float, float] = (0.8, 0.8, 0.82), width: float = 0.5) -> None:
        page.ops.append(
            f"q {_num(color[0])} {_num(color[1])} {_num(color[2])} RG {_num(width)} w "
            f"{_num(x1)} {_num(y1)} m {_num(x2)} {_num(y2)} l S Q"
        )

    def link(self, page: Page, x: float, y: float, w: float, h: float, uri: str) -> None:
        page.links.append((x, y, x + w, y + h, uri))

    def render(self) -> bytes:
        objects: list[bytes | None] = []

        def reserve() -> int:
            objects.append(None)
            return len(objects)

        def put(num: int, body: bytes) -> None:
            objects[num - 1] = body

        def stream(dictionary: str, data: bytes) -> bytes:
            packed = zlib.compress(data, 9)
            return (
                f"<< {dictionary} /Filter /FlateDecode /Length {len(packed)} >>\nstream\n".encode()
                + packed + b"\nendstream"
            )

        catalog = reserve()
        pages_obj = reserve()
        info = reserve()
        font_objs: dict[str, int] = {}
        for use in self._fonts.values():
            font_objs[use.resource] = self._write_font(use, reserve, put, stream)
        page_nums = []
        resources = " ".join(f"/{res} {num} 0 R" for res, num in font_objs.items())
        for page in self.pages:
            page_num = reserve()
            content = reserve()
            put(content, stream("", "\n".join(page.ops).encode("latin-1")))
            annots = []
            for x1, y1, x2, y2, uri in page.links:
                annot = reserve()
                put(annot, (
                    f"<< /Type /Annot /Subtype /Link /Rect [{_num(x1)} {_num(y1)} {_num(x2)} {_num(y2)}] "
                    f"/Border [0 0 0] /A << /S /URI /URI {_pdf_string(uri)} >> >>"
                ).encode("latin-1"))
                annots.append(f"{annot} 0 R")
            annot_part = f" /Annots [{' '.join(annots)}]" if annots else ""
            put(page_num, (
                f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {_num(PAGE_WIDTH)} {_num(PAGE_HEIGHT)}] "
                f"/Resources << /Font << {resources} >> >> /Contents {content} 0 R{annot_part} >>"
            ).encode("latin-1"))
            page_nums.append(page_num)
        kids = " ".join(f"{n} 0 R" for n in page_nums)
        put(pages_obj, f"<< /Type /Pages /Kids [{kids}] /Count {len(page_nums)} >>".encode())
        put(catalog, f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode())
        stamp = datetime.now(timezone.utc).strftime("D:%Y%m%d%H%M%SZ")
        title = f" /Title {_pdf_string(self.title)}" if self.title else ""
        put(info, f"<< /Producer (alpi) /CreationDate ({stamp}){title} >>".encode("latin-1"))

        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for index, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += f"{index} 0 obj\n".encode() + (body or b"null") + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
        for offset in offsets:
            out += f"{offset:010d} 00000 n \n".encode()
        out += (
            f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R /Info {info} 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
        return bytes(out)

    @staticmethod
    def _write_font(use: _FontUse, reserve, put, stream) -> int:
        font = use.font
        type0 = reserve()
        cid = reserve()
        descriptor = reserve()
        file_obj = reserve()
        to_unicode = reserve()
        put(file_obj, stream(f"/Length1 {len(font.data)}", font.data))
        flags = 32 | (1 if font.fixed_pitch else 0) | (64 if font.italic_angle else 0)
        bbox = " ".join(str(font.scaled(v)) for v in font.bbox)
        put(descriptor, (
            f"<< /Type /FontDescriptor /FontName /{font.name} /Flags {flags} /FontBBox [{bbox}] "
            f"/ItalicAngle {_num(font.italic_angle)} /Ascent {font.scaled(font.ascent)} "
            f"/Descent {font.scaled(font.descent)} /CapHeight {font.scaled(font.cap_height)} "
            f"/StemV 80 /FontFile2 {file_obj} 0 R >>"
        ).encode())
        widths = " ".join(f"{gid} [{font.scaled(font.advance(gid))}]" for gid in sorted(use.used))
        put(cid, (
            f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font.name} "
            "/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            f"/FontDescriptor {descriptor} 0 R /CIDToGIDMap /Identity /DW 1000 /W [{widths}] >>"
        ).encode())
        put(to_unicode, stream("", _to_unicode(use.used)))
        put(type0, (
            f"<< /Type /Font /Subtype /Type0 /BaseFont /{font.name} /Encoding /Identity-H "
            f"/DescendantFonts [{cid} 0 R] /ToUnicode {to_unicode} 0 R >>"
        ).encode())
        return type0


def _to_unicode(used: dict[int, str]) -> bytes:
    lines = [
        "/CIDInit /ProcSet findresource begin", "12 dict begin", "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def", "/CMapType 2 def",
        "1 begincodespacerange", "<0000> <FFFF>", "endcodespacerange",
    ]
    pairs = [(gid, ch) for gid, ch in sorted(used.items()) if gid]
    for start in range(0, len(pairs), 100):
        chunk = pairs[start:start + 100]
        lines.append(f"{len(chunk)} beginbfchar")
        lines += [f"<{gid:04X}> <{ch.encode('utf-16-be').hex().upper()}>" for gid, ch in chunk]
        lines.append("endbfchar")
    lines += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(lines).encode()
