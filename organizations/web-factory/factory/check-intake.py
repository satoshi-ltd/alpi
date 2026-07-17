from __future__ import annotations

import json
import sys
from pathlib import Path

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif"}


def main() -> int:
    project = Path.cwd()
    site = project / "src" / "config" / "site.json"
    intake = project / "intake.md"
    if not site.exists() or not intake.exists():
        print("intake incomplete: site.json or intake.md missing")
        return 1
    try:
        data = json.loads(site.read_text())
    except json.JSONDecodeError as e:
        print(f"site.json invalid JSON: {e}")
        return 1
    for key in ("theme", "brand", "locales", "defaultLocale"):
        if not data.get(key):
            print(f"site.json missing {key!r}")
            return 1
    text = intake.read_text()
    if "visual_assets: not_required" not in text:
        print("assets phase needed: intake signal is not `not_required` — the hub runs the assets gate")
        return 1
    assets = project / "assets"
    images = [p.name for p in assets.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES] if assets.exists() else []
    if images:
        print(f"assets phase needed: signal says not_required but assets/ holds {len(images)} image(s) — supplied photos must be restored")
        return 1
    print(f"intake verified · theme {data['theme']} · locales {','.join(data['locales'])} · not_required + assets/ empty → content")
    return 0


if __name__ == "__main__":
    sys.exit(main())
