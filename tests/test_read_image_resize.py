"""Auto-resize of `read_image` inputs to stay under max_edge."""

from __future__ import annotations

import io

import pytest

from alpi.tools.read_image import _maybe_resize

PIL = pytest.importorskip("PIL.Image")


def _png_bytes(w: int, h: int, mode: str = "RGB") -> bytes:
    img = PIL.new(mode, (w, h), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_bytes(w: int, h: int) -> bytes:
    img = PIL.new("RGB", (w, h), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def _open_size(data: bytes) -> tuple[int, int]:
    with PIL.open(io.BytesIO(data)) as im:
        return im.size


def test_no_resize_under_threshold() -> None:
    data = _png_bytes(800, 600)
    out, mime = _maybe_resize(data, "image/png", max_edge=1568)
    assert out == data
    assert mime == "image/png"


def test_resizes_when_longer_edge_over_threshold() -> None:
    data = _png_bytes(3000, 2000)
    out, mime = _maybe_resize(data, "image/png", max_edge=1568)
    w, h = _open_size(out)
    assert max(w, h) == 1568
    assert abs((w / h) - (3000 / 2000)) < 0.01  # aspect preserved
    assert len(out) < len(data)


def test_jpeg_stays_jpeg_after_resize() -> None:
    data = _jpeg_bytes(4000, 3000)
    out, mime = _maybe_resize(data, "image/jpeg", max_edge=1568)
    assert mime == "image/jpeg"
    assert len(out) < len(data)


def test_rgba_png_stays_png() -> None:
    """Transparent PNG must not be flattened to JPEG."""
    data = _png_bytes(3000, 2000, mode="RGBA")
    out, mime = _maybe_resize(data, "image/png", max_edge=1568)
    assert mime == "image/png"
    with PIL.open(io.BytesIO(out)) as im:
        assert im.mode in ("RGBA", "LA", "P")


def test_svg_is_skipped() -> None:
    """SVG is vector — no point resizing."""
    svg = b'<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="10000" height="10000"/>'
    out, mime = _maybe_resize(svg, "image/svg+xml", max_edge=1568)
    assert out == svg
    assert mime == "image/svg+xml"


def test_max_edge_zero_disables() -> None:
    """max_edge<=0 → passthrough. Lets a user opt out via config."""
    data = _png_bytes(4000, 3000)
    out, _ = _maybe_resize(data, "image/png", max_edge=0)
    assert out == data


def test_corrupt_bytes_pass_through() -> None:
    """Garbage input must not crash the tool — return original bytes."""
    junk = b"\x89PNG\r\n\x1a\n" + b"not actually a png"
    out, mime = _maybe_resize(junk, "image/png", max_edge=1568)
    assert out == junk
    assert mime == "image/png"
