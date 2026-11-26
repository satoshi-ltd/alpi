from __future__ import annotations

import struct
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


class FontError(ValueError):
    pass


@dataclass
class TrueTypeFont:
    name: str
    data: bytes
    units_per_em: int
    ascent: int
    descent: int
    cap_height: int
    bbox: tuple[int, int, int, int]
    italic_angle: float
    fixed_pitch: bool
    advances: list[int]
    cmap: dict[int, int] = field(repr=False)

    def glyph(self, codepoint: int) -> int:
        return self.cmap.get(codepoint, 0)

    def advance(self, gid: int) -> int:
        if not self.advances:
            return 0
        return self.advances[gid] if gid < len(self.advances) else self.advances[-1]

    def width(self, text: str, size: float) -> float:
        units = sum(self.advance(self.glyph(ord(ch))) for ch in text)
        return units * size / self.units_per_em

    def scaled(self, units: int) -> int:
        return round(units * 1000 / self.units_per_em)


def _tables(data: bytes) -> dict[str, tuple[int, int]]:
    if len(data) < 12:
        raise FontError("not a TrueType font")
    version, count = struct.unpack(">IH", data[:6])
    if version not in (0x00010000, 0x74727565):
        raise FontError("only TrueType outlines are supported")
    tables = {}
    for i in range(count):
        tag, _, offset, length = struct.unpack(">4sIII", data[12 + 16 * i: 28 + 16 * i])
        if offset + length > len(data):
            raise FontError(f"table {tag!r} runs past the end of the file")
        tables[tag.decode("latin-1")] = (offset, length)
    for required in ("head", "hhea", "hmtx", "maxp", "cmap"):
        if required not in tables:
            raise FontError(f"missing {required} table")
    return tables


def _cmap(data: bytes, offset: int) -> dict[int, int]:
    _, count = struct.unpack(">HH", data[offset:offset + 4])
    records = {}
    for i in range(count):
        platform, encoding, sub = struct.unpack(">HHI", data[offset + 4 + 8 * i: offset + 12 + 8 * i])
        records[(platform, encoding)] = offset + sub
    for key in ((3, 10), (0, 4), (0, 6), (3, 1), (0, 3), (0, 1), (0, 0)):
        start = records.get(key)
        if start is None:
            continue
        fmt = struct.unpack(">H", data[start:start + 2])[0]
        if fmt == 12:
            return _cmap12(data, start)
        if fmt == 4:
            return _cmap4(data, start)
    raise FontError("no Unicode cmap of format 4 or 12")


def _cmap4(data: bytes, start: int) -> dict[int, int]:
    seg_count = struct.unpack(">H", data[start + 6:start + 8])[0] // 2
    ends_at = start + 14
    starts_at = ends_at + 2 * seg_count + 2
    deltas_at = starts_at + 2 * seg_count
    ranges_at = deltas_at + 2 * seg_count
    mapping = {}
    for i in range(seg_count):
        end = struct.unpack(">H", data[ends_at + 2 * i:ends_at + 2 * i + 2])[0]
        first = struct.unpack(">H", data[starts_at + 2 * i:starts_at + 2 * i + 2])[0]
        delta = struct.unpack(">h", data[deltas_at + 2 * i:deltas_at + 2 * i + 2])[0]
        range_offset = struct.unpack(">H", data[ranges_at + 2 * i:ranges_at + 2 * i + 2])[0]
        if first == 0xFFFF:
            continue
        for code in range(first, end + 1):
            if range_offset == 0:
                gid = (code + delta) & 0xFFFF
            else:
                at = ranges_at + 2 * i + range_offset + 2 * (code - first)
                gid = struct.unpack(">H", data[at:at + 2])[0]
                if gid:
                    gid = (gid + delta) & 0xFFFF
            if gid:
                mapping[code] = gid
    return mapping


def _cmap12(data: bytes, start: int) -> dict[int, int]:
    groups = struct.unpack(">I", data[start + 12:start + 16])[0]
    mapping = {}
    for i in range(groups):
        first, last, gid = struct.unpack(">III", data[start + 16 + 12 * i: start + 28 + 12 * i])
        for offset, code in enumerate(range(first, last + 1)):
            mapping[code] = gid + offset
    return mapping


def parse(data: bytes, name: str) -> TrueTypeFont:
    try:
        tables = _tables(data)
        head, _ = tables["head"]
        units_per_em = struct.unpack(">H", data[head + 18:head + 20])[0]
        bbox = struct.unpack(">hhhh", data[head + 36:head + 44])
        hhea, _ = tables["hhea"]
        ascent, descent = struct.unpack(">hh", data[hhea + 4:hhea + 8])
        metrics_count = struct.unpack(">H", data[hhea + 34:hhea + 36])[0]
        maxp, _ = tables["maxp"]
        glyph_count = struct.unpack(">H", data[maxp + 4:maxp + 6])[0]
        hmtx, _ = tables["hmtx"]
        advances = [
            struct.unpack(">H", data[hmtx + 4 * i:hmtx + 4 * i + 2])[0] for i in range(metrics_count)
        ]
        advances += [advances[-1]] * max(0, glyph_count - metrics_count)
        cap_height = ascent
        if "OS/2" in tables:
            os2, length = tables["OS/2"]
            if struct.unpack(">H", data[os2:os2 + 2])[0] >= 2 and length >= 90:
                cap_height = struct.unpack(">h", data[os2 + 88:os2 + 90])[0]
        italic_angle, fixed_pitch = 0.0, False
        if "post" in tables:
            post, _ = tables["post"]
            raw = struct.unpack(">i", data[post + 4:post + 8])[0]
            italic_angle = raw / 65536
            fixed_pitch = struct.unpack(">I", data[post + 12:post + 16])[0] != 0
        cmap = _cmap(data, tables["cmap"][0])
    except struct.error as exc:
        raise FontError(f"truncated font table: {exc}") from exc
    if not units_per_em:
        raise FontError("unitsPerEm is zero")
    return TrueTypeFont(
        name=name, data=data, units_per_em=units_per_em, ascent=ascent, descent=descent,
        cap_height=cap_height, bbox=bbox, italic_angle=italic_angle, fixed_pitch=fixed_pitch,
        advances=advances, cmap=cmap,
    )


FONT_DIR = Path(__file__).with_name("fonts")


@lru_cache(maxsize=None)
def load(stem: str) -> TrueTypeFont:
    return parse((FONT_DIR / f"{stem}.ttf").read_bytes(), stem)
