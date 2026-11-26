from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

CAP = 12_000
FIND_LIMIT = 40
SCROLL_FRACTION = 0.8

ACTIONABLE_ROLES = frozenset({
    "link", "button", "textbox", "searchbox", "combobox", "checkbox", "radio", "switch", "slider", "spinbutton",
    "tab", "menuitem", "menuitemcheckbox", "menuitemradio", "option", "listbox", "treeitem",
})
_WRAPPERS = frozenset({"generic", "group", "rowgroup"})
_LINE_MAX = 4_000
_HEAD = re.compile(r"^(\s*)- ")
_ROLE = re.compile(r"/?[\w-]+")
_NAME = re.compile(r' "((?:[^"\\]|\\.)*)"')
_ATTR = re.compile(r" \[([^\]\s=]+)(?:=([^\]]*))?\]")


@dataclass
class Row:
    indent: int
    role: str
    name: str = ""
    attrs: list[tuple[str, str | None]] = field(default_factory=list)
    tail: str = ""
    ref: str | None = None
    box: tuple[float, float, float, float] | None = None
    url: str = ""
    parent: int = -1
    framed: int = -1

    @property
    def actionable(self) -> bool:
        return self.ref is not None and (self.role in ACTIONABLE_ROLES or any(k == "cursor" for k, _ in self.attrs))

    def line(self, indent: int | None = None, *, keep_ref: bool | None = None, limit: int | None = None) -> str:
        show_ref = self.actionable if keep_ref is None else keep_ref
        pad = " " * (self.indent if indent is None else indent)
        name, tail = self.name, self.tail
        if limit is not None:
            name = name if len(name) <= limit else name[:limit] + "…"
            tail = tail if len(tail) <= limit else tail[:limit] + "…"
        if not self.role:
            return pad + _inert(tail)
        out = pad + f"- {self.role}"
        if name:
            out += f' "{_inert(name)}"'
        for key, value in self.attrs:
            if key in ("box", "cursor") or (key == "ref" and not show_ref):
                continue
            out += f" [{key}]" if value is None else f" [{key}={value}]"
        return out + _inert(tail)


_BREAKS = re.compile("[\\x00-\\x1f\\x7f\\x85\\u2028\\u2029]")


def _inert(page_text: str) -> str:
    return _BREAKS.sub(" ", page_text).replace("[ref=", "[ref:")


def _unquote(body: str) -> tuple[str, str] | None:
    out: list[str] = []
    i = 1
    while i < len(body):
        if body[i] != "'":
            out.append(body[i])
            i += 1
        elif body[i + 1:i + 2] == "'":
            out.append("'")
            i += 2
        else:
            return "".join(out), body[i + 1:]
    return None


# Ref and box are read only from the attribute run right after the name: the name and the trailing text are page-controlled and may spell a fake `[ref=…]`. Lines split on "\n" only, because a name may hold U+0085 and str.splitlines() would cut a row there.
def parse(snapshot: str) -> list[Row]:
    rows: list[Row] = []
    stack: list[int] = []
    for raw in snapshot.split("\n"):
        if not raw.strip():
            continue
        head = _HEAD.match(raw)
        body = raw[head.end():] if head is not None else ""
        # Playwright single-quotes the whole key when the name holds a YAML-special character such as ": ".
        key, rest = (_unquote(body) or (None, "")) if body.startswith("'") else (body, None)
        role = _ROLE.match(key) if key is not None else None
        if head is None or role is None:
            row = Row(indent=len(raw) - len(raw.lstrip()), role="", tail=raw.strip())
        else:
            row = Row(indent=len(head.group(1)), role=role.group(0))
            pos = role.end()
            if not row.role.startswith("/") and row.role != "text":
                name = _NAME.match(key, pos)
                if name is not None:
                    row.name, pos = name.group(1), name.end()
                while (attr := _ATTR.match(key, pos)) is not None:
                    row.attrs.append((attr.group(1), attr.group(2)))
                    pos = attr.end()
            row.tail = key[pos:] + (rest or "")
            for attr_key, value in row.attrs:
                if attr_key == "ref" and value:
                    row.ref = value
                elif attr_key == "box" and value:
                    try:
                        x, y, w, h = (float(part) for part in value.split(","))
                        row.box = (x, y, w, h)
                    except ValueError:
                        pass
        while stack and rows[stack[-1]].indent >= row.indent:
            stack.pop()
        if stack:
            row.parent = stack[-1]
            above = rows[row.parent]
            row.framed = row.parent if above.role == "iframe" and above.framed < 0 else above.framed
            if row.role == "/url":
                above.url = row.tail.removeprefix(":").strip().strip('"')
        rows.append(row)
        stack.append(len(rows) - 1)
    return rows


def refs(rows: list[Row]) -> set[str]:
    return {row.ref for row in rows if row.ref}


def _on_screen(row: Row, width: float, height: float) -> bool:
    x, y, w, h = row.box
    return y < height and y + h > 0 and x < width and x + w > 0


def _visible(rows: list[Row], width: float, height: float) -> list[bool]:
    own = [False] * len(rows)
    for i, row in enumerate(rows):
        # Boxes inside an iframe are relative to that frame, so its rows follow the iframe element itself.
        if row.framed >= 0:
            own[i] = own[row.framed]
        elif row.box is None or row.box[2] <= 0 or row.box[3] <= 0:
            own[i] = own[row.parent] if row.parent >= 0 else True
        else:
            own[i] = _on_screen(row, width, height)
    keep = list(own)
    for i in range(len(rows) - 1, -1, -1):
        if keep[i] and rows[i].parent >= 0:
            keep[rows[i].parent] = True
    return keep


def _lean(rows: list[Row], keep: list[bool] | None = None) -> list[str]:
    out: list[str] = []
    opens: list[bool] = []
    dropped: list[int] = []
    for i, row in enumerate(rows):
        while dropped and rows[dropped[-1]].indent >= row.indent:
            dropped.pop()
        if keep is not None and not keep[i]:
            continue
        if row.role == "/url":
            continue
        if row.role in _WRAPPERS and not row.name and row.tail in ("", ":") and not row.actionable:
            dropped.append(i)
            continue
        out.append(row.line(max(0, row.indent - 2 * len(dropped))))
        opens.append(row.tail == ":")
    for i, line in enumerate(out):
        if opens[i] and (i + 1 == len(out) or _depth(out[i + 1]) <= _depth(line)):
            out[i] = line[:-1]
    return out


def _depth(line: str) -> int:
    return len(line) - len(line.lstrip())


def _fit(header: str, lines: list[str], cap: int) -> str:
    budget = cap - len(header) - 80
    kept: list[str] = []
    used = 0
    for line in lines:
        limit = min(_LINE_MAX, budget - used - 1)
        if len(line) > limit:
            if limit < 200:
                break
            line = line[:limit - 20] + f"… [+{len(line) - limit + 20} chars]"
        kept.append(line)
        used += len(line) + 1
    if len(kept) == len(lines):
        return header + "\n".join(kept)
    return header + "\n".join(kept) + f"\n… {len(lines) - len(kept)} more lines not shown — use find"


def render(rows: list[Row], header: str, metrics: dict | None, cap: int = CAP) -> str:
    header = header[: cap // 3]
    whole = _lean(rows)
    if not whole:
        return header + ("\n" if header else "") + "(empty page)"
    if metrics is None or len(header) + 1 + sum(len(line) + 1 for line in whole) <= cap:
        return _fit(header + ("\n" if header else ""), whole, cap)
    height = max(1.0, float(metrics["h"]))
    step = height * SCROLL_FRACTION
    screens = math.ceil(max(0.0, float(metrics["total"]) - height) / step) + 1
    screen = min(screens, round(float(metrics["y"]) / step) + 1)
    header += f"view: screen {screen} of {screens} — scroll or find for the rest\n\n"
    return _fit(header, _lean(rows, _visible(rows, float(metrics["w"]), height)), cap)


def _haystack(row: Row) -> str:
    return f"{row.role} {row.name} {row.tail}".lower()


def find(rows: list[Row], query: str, cap: int = CAP) -> str:
    needle = query.strip().lower()
    hits = [i for i, row in enumerate(rows) if row.role != "/url" and needle in _haystack(row)]
    if not hits:
        return f'find "{query}": no match on this page'
    lines = [f'find "{query}": {len(hits)} match' + ("" if len(hits) == 1 else "es")
             + (f", first {FIND_LIMIT} shown" if len(hits) > FIND_LIMIT else "")]
    for i in hits[:FIND_LIMIT]:
        row = rows[i]
        line = row.line(0, keep_ref=True, limit=120)
        line = line[:-1] if row.tail == ":" else line
        if row.url:
            line += f" → {_inert(row.url[:200])}"
        if row.ref is None:
            above = row.parent
            while above >= 0 and rows[above].ref is None:
                above = rows[above].parent
            if above >= 0:
                line += f" — inside [ref={rows[above].ref}]"
        lines.append(line)
    return _fit("", lines, cap)


def candidates(rows: list[Row], role: str, name: str, text: str) -> list[Row]:
    if role:
        pool = [row for row in rows if row.role == role and row.ref]
        if not name:
            return pool
        exact = [row for row in pool if row.name == name]
        return exact or [row for row in pool if name.lower() in row.name.lower()]
    needle = text.strip().lower()
    pool = [row for row in rows if row.actionable and needle and needle in f"{row.name} {row.tail}".lower()]
    exact = [row for row in pool if row.name.lower() == needle]
    return exact or pool
