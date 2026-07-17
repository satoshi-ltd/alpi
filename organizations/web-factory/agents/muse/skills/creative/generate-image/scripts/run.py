from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
# Transformative default; --model overrides are the maintainer's call, never the agent's.
DEFAULT_MODEL = "bytedance-seed/seedream-4.5"


def _die(msg: str) -> None:
    print(f"generate-image: {msg}", file=sys.stderr)
    sys.exit(1)


def _data_url(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    ext = (path.rsplit(".", 1)[-1] or "png").lower()
    mime = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True, help="absolute output image path (.png)")
    ap.add_argument("--input", default=None, help="source image for restore/img2img")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--aspect", default=None, help="e.g. 16:9, 1:1")
    args = ap.parse_args()

    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        _die("OPENROUTER_API_KEY not set in the profile env")

    # Ownership split for relative paths (never against the skill's cwd, else
    # outputs orphan inside the skill dir): a `projects/...` path belongs to a
    # project → resolve against the workspace; anything else is a personal chat
    # artifact → resolve against the profile home (~/.alpi/profiles/<name>/).
    workspace = os.environ.get("ALPI_WORKSPACE") or os.getcwd()
    home = os.environ.get("ALPI_HOME") or workspace

    def _resolve(p: str) -> str:
        if os.path.isabs(p):
            return p
        base = workspace if p.startswith("projects/") else home
        return os.path.abspath(os.path.join(base, p))

    out = _resolve(args.out)

    # Mode guardrail: writing into a project is allowed ONLY inside a workgroup
    # turn (the daemon sets ALPI_WORKGROUP_DISPATCH then). In a direct chat there
    # is no project — refuse to touch one, so a chat can never corrupt a launched
    # site's assets. Prompt rules alone proved insufficient (Muse hijacked a project).
    in_workgroup = bool(os.environ.get("ALPI_WORKGROUP_DISPATCH"))
    projects_root = os.path.abspath(os.path.join(workspace, "projects")) + os.sep
    if not in_workgroup and os.path.abspath(out).startswith(projects_root):
        _die("direct chat: outputs must go under out/ (profile home) or an explicit user path — "
             "writing projects/<slug>/ requires a workgroup task")

    if args.input:
        src = _resolve(args.input)
        if not in_workgroup and os.path.abspath(src).startswith(projects_root):
            _die("direct chat: --input cannot read projects/<slug>/ — that path is workgroup-only")
        if not os.path.exists(src):
            _die(f"--input not found: {src} — pass the real source path; never guess /data/attachments")
        content = [
            {"type": "image_url", "image_url": {"url": _data_url(src)}},
            {"type": "text", "text": args.prompt},
        ]
    else:
        content = args.prompt

    body: dict = {
        "model": args.model,
        "messages": [{"role": "user", "content": content}],
        "usage": {"include": True},
    }
    if args.aspect:
        body["image_config"] = {"aspect_ratio": args.aspect}

    def _post(modalities: list[str]) -> dict:
        body["modalities"] = modalities
        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode())

    # Omni models want ["image","text"]; image-only models 404 on that and need ["image"].
    try:
        payload = _post(["image", "text"])
    except urllib.error.HTTPError as e:
        detail = e.read().decode()
        if e.code == 404 and "modalit" in detail.lower():
            try:
                payload = _post(["image"])
            except urllib.error.HTTPError as e2:
                _die(f"HTTP {e2.code} from OpenRouter: {e2.read().decode()[:300]}")
            except Exception as e2:  # noqa: BLE001
                _die(f"request failed: {e2}")
        else:
            _die(f"HTTP {e.code} from OpenRouter: {detail[:300]}")
    except Exception as e:  # noqa: BLE001
        _die(f"request failed: {e}")

    try:
        url = payload["choices"][0]["message"]["images"][0]["image_url"]["url"]
    except (KeyError, IndexError, TypeError):
        _die(f"no image in response (model {args.model} may not output images): {json.dumps(payload)[:300]}")

    if not url.startswith("data:") or ";base64," not in url:
        _die(f"unexpected image url shape: {url[:80]}")
    # Honour the real format: the model may return JPEG even if --out said .png.
    mime = url.split(";base64,", 1)[0][len("data:"):]
    ext = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif"}.get(mime)
    if ext and os.path.splitext(out)[1].lower().lstrip(".") != ext:
        out = os.path.splitext(out)[0] + "." + ext
    raw = base64.b64decode(url.split(";base64,", 1)[1])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        f.write(raw)
    cost = 0.0
    try:
        cost = float(payload.get("usage", {}).get("cost") or 0.0)
    except (TypeError, ValueError):
        cost = 0.0
    print(json.dumps({"out": out, "bytes": len(raw), "model": args.model, "cost_usd": cost}))


if __name__ == "__main__":
    main()
