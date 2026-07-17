from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-3.1-flash-lite"  # vision model, decoupled from muse's text base


def _die(msg: str) -> None:
    print(f"analyze-image: {msg}", file=sys.stderr)
    sys.exit(1)


def _data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    ext = (path.rsplit(".", 1)[-1] or "png").lower()
    mime = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True, help="absolute path to the image to look at")
    ap.add_argument("--question", required=True, help="what to find out about it")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        _die("OPENROUTER_API_KEY not set in the profile env")
    src = args.image
    if not os.path.isabs(src):
        base = os.environ.get("ALPI_WORKSPACE") or os.getcwd()
        src = os.path.abspath(os.path.join(base, src))
    if not os.path.exists(src):
        _die(f"image not found: {src}")

    body = {
        "model": args.model,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": _data_url(src)}},
            {"type": "text", "text": args.question},
        ]}],
        "usage": {"include": True},
    }
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        _die(f"HTTP {e.code} from OpenRouter: {e.read().decode()[:300]}")
    except Exception as e:  # noqa: BLE001
        _die(f"request failed: {e}")

    try:
        answer = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        _die(f"no answer in response: {json.dumps(payload)[:300]}")
    cost = 0.0
    try:
        cost = float(payload.get("usage", {}).get("cost") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    print(json.dumps({"answer": answer, "model": args.model, "cost_usd": cost}))


if __name__ == "__main__":
    main()
