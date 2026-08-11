"""read_image — answer a question about an image (local path or URL) via vision LLM."""

from __future__ import annotations

import base64

from alpi import config as cfg_mod
from alpi import llm
from alpi.home import get_home
from alpi.tools._paths import resolve_path
from alpi.tools import _state as tool_state_mod
from alpi.tools.base import Tool, ToolResult


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".svg"}

MAX_EDGE = 1568  # Anthropic's recommended upper bound (pixels)

MAGIC_BYTES: dict[str, bytes] = {
    "image/png":  b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/gif":  b"GIF87a",
    "image/gif2": b"GIF89a",
    "image/webp": b"RIFF",
    "image/bmp":  b"BM",
}

MAX_BYTES = 20 * 1024 * 1024
DOWNLOAD_TIMEOUT = 20.0


def _maybe_resize(data: bytes, mime: str, max_edge: int) -> tuple[bytes, str]:
    """Downscale if the longer edge exceeds *max_edge*; else return as-is.

    Skips SVG (vector) and any format Pillow can't round-trip. Returns
    the same ``data, mime`` pair on failure so the caller can proceed."""
    if mime == "image/svg+xml" or max_edge <= 0:
        return data, mime
    try:
        import io
        from PIL import Image
    except Exception:  # noqa: BLE001
        return data, mime
    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            longer = max(w, h)
            if longer <= max_edge:
                return data, mime
            ratio = max_edge / longer
            new_size = (max(1, round(w * ratio)), max(1, round(h * ratio)))
            resized = img.resize(new_size, Image.LANCZOS)
            buf = io.BytesIO()
            if mime == "image/png" and resized.mode in ("RGBA", "LA", "P"):
                resized.save(buf, format="PNG", optimize=True)
                return buf.getvalue(), "image/png"
            if resized.mode in ("RGBA", "LA", "P"):
                resized = resized.convert("RGB")
            resized.save(buf, format="JPEG", quality=85, optimize=True)
            return buf.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001
        return data, mime


def _sniff_mime(data: bytes) -> str | None:
    if data.startswith(MAGIC_BYTES["image/png"]):
        return "image/png"
    if data.startswith(MAGIC_BYTES["image/jpeg"]):
        return "image/jpeg"
    if data.startswith(MAGIC_BYTES["image/gif"]) or data.startswith(MAGIC_BYTES["image/gif2"]):
        return "image/gif"
    if data.startswith(MAGIC_BYTES["image/bmp"]):
        return "image/bmp"
    if data.startswith(MAGIC_BYTES["image/webp"]) and data[8:12] == b"WEBP":
        return "image/webp"
    head = data[:4096].lstrip()
    if head.startswith(b"<?xml") or head.startswith(b"<svg"):
        if b"<svg" in data[:4096].lower():
            return "image/svg+xml"
    return None


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _download(url: str) -> bytes:
    from alpi.tools._pinned_dns import safe_client
    current = url
    r = None
    for _ in range(10):
        ok, reason, client = safe_client(current, follow_redirects=False, timeout=DOWNLOAD_TIMEOUT)
        if not ok or client is None:
            raise ValueError(f"URL blocked: {reason}")
        with client:
            r = client.get(
                current,
                headers={
                    "User-Agent": "alpi/read_image",
                    "Accept": "image/*,*/*;q=0.8",
                },
            )
        if r.status_code in (301, 302, 303, 307, 308):
            nxt = r.headers.get("location") or ""
            if not nxt:
                raise ValueError("redirect without location")
            if nxt.startswith("/"):
                from urllib.parse import urljoin
                nxt = urljoin(current, nxt)
            current = nxt
            continue
        r.raise_for_status()
        break
    else:
        raise ValueError("too many redirects")

    cl = r.headers.get("content-length")
    if cl and int(cl) > MAX_BYTES:
        raise ValueError(f"image too large ({int(cl):,} bytes > {MAX_BYTES:,})")
    body = r.content
    if len(body) > MAX_BYTES:
        raise ValueError(f"image too large ({len(body):,} bytes > {MAX_BYTES:,})")
    return body


class ReadImage(Tool):
    name = "read_image"
    description = (
        "Look at an image and return a text answer to a specific question "
        "about it. Accepts a local file path or an http(s) URL. Sends the "
        "image to the current model in multimodal mode, so the model must "
        "support vision (GPT-4o, Claude 3.5+, Gemini 2.0+, etc.).\n"
        "\n"
        "Use for: reading a screenshot the user saved, describing a "
        "diagram, extracting text from a photo of a receipt, counting "
        "objects in a picture. Not for generating images.\n"
        "\n"
        "Supported formats: PNG, JPEG, GIF, WebP, BMP, SVG. Max 20 MB. "
        "For URLs, private / link-local / metadata hosts are blocked. "
        "Relative local paths root at the workspace; absolute paths work "
        "anywhere except sensitive system locations.\n"
        "\n"
        "Always pass a focused `question` — 'describe the image' is "
        "cheaper and more useful than hoping the model narrates by default."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Local file path (relative to workspace or absolute) "
                    "or an http(s) URL pointing to an image."
                ),
            },
            "question": {
                "type": "string",
                "description": (
                    "What you want to know about the image. Specific beats "
                    "generic — 'what's the error in this stack trace?' over "
                    "'describe this'."
                ),
            },
        },
        "required": ["path", "question"],
    }

    def run(self, path: str, question: str) -> ToolResult:
        if _is_url(path):
            from alpi.tools._sandbox import require_network
            blocked = require_network("read_image")
            if blocked is not None:
                return blocked
            try:
                tool_state_mod.emit_state("downloading image…")
                data = _download(path)
            except Exception as e:  # noqa: BLE001
                return ToolResult(ok=False, output="", error=f"download failed: {e}")
            origin_hint = path
        else:
            try:
                resolved = resolve_path(path)
            except ValueError as e:
                return ToolResult(ok=False, output="", error=str(e))
            if not resolved.exists():
                return ToolResult(ok=False, output="", error=f"no such file: {path}")
            if not resolved.is_file():
                return ToolResult(ok=False, output="", error=f"not a file: {path}")
            if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
                return ToolResult(
                    ok=False, output="",
                    error=(
                        f"not an image extension ({resolved.suffix}). "
                        f"Supported: {sorted(IMAGE_EXTENSIONS)}"
                    ),
                )
            size = resolved.stat().st_size
            if size > MAX_BYTES:
                return ToolResult(
                    ok=False, output="",
                    error=f"image too large ({size:,} bytes > {MAX_BYTES:,})",
                )
            data = resolved.read_bytes()
            origin_hint = str(resolved)

        mime = _sniff_mime(data)
        if mime is None:
            return ToolResult(
                ok=False, output="",
                error=f"bytes at {origin_hint} don't match a supported image format",
            )

        cfg = cfg_mod.load(get_home())
        override = cfg.tools.read_image.model.strip()
        override_tier = override if override in cfg_mod.TIER_NAMES else None
        if override_tier is not None:
            override = cfg_mod.tier_model(cfg, override_tier)
        main_kwargs = cfg_mod.resolve_model(cfg)

        before = len(data)
        data, mime = _maybe_resize(data, mime, MAX_EDGE)
        if len(data) < before:
            tool_state_mod.emit_state(
                f"resized image ({before:,} → {len(data):,} bytes)"
            )

        tool_state_mod.emit_state("analyzing image…")
        b64 = base64.b64encode(data).decode("ascii")
        data_url = f"data:{mime};base64,{b64}"
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }]

        first_error: str | None = None
        if override:
            try:
                # resolve_model with the override head ("openai", "anthropic"…) resolves the profile's api_key from .env. `include_reasoning=False` so the profile's effort doesn't leak into a tool sub-model.
                override_kwargs = (
                    cfg_mod.resolve_model(cfg, tier=override_tier)
                    if override_tier is not None
                    else cfg_mod.resolve_model(cfg, model=override, include_reasoning=False)
                )
                out = llm.complete(messages=messages, **override_kwargs)
                return _finalize(out)
            except Exception as e:  # noqa: BLE001
                tool_state_mod.emit_state("retrying with main model…", error=True)
                first_error = f"override {override!r} failed: {e}"

        try:
            out = llm.complete(messages=messages, **main_kwargs)
        except Exception as e:  # noqa: BLE001
            err_lower = str(e).lower()
            hint = ""
            if any(k in err_lower for k in ("vision", "image", "multimodal", "content_type")):
                hint = (
                    " (the current model may not support vision — "
                    "switch via /model to GPT-4o, Claude 3.5+, Gemini, etc.)"
                )
            err = f"vision LLM call failed: {e}{hint}"
            if first_error:
                err = f"{first_error}; then {err}"
            return ToolResult(ok=False, output="", error=err)

        result = _finalize(out)
        if first_error and result.ok:
            result.output = f"[fallback: {override} unavailable, used main model]\n\n{result.output}"
        return result


def _finalize(out) -> ToolResult:  # noqa: ANN001
    tool_state_mod.record_usage(
        out.input_tokens, out.output_tokens, out.cost_usd,
        getattr(out, "cached_tokens", None),
        getattr(out, "cache_discount", None),
        getattr(out, "cost_source", None),
    )
    answer = (out.content or "").strip() or "(empty answer)"
    return ToolResult(ok=True, output=answer)


TOOL = ReadImage
