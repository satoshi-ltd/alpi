#!/usr/bin/env python3
"""Initialize one cloned hotel project without losing supplied assets."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def run(command: list[str], cwd: Path) -> None:
    print(f"+ {' '.join(command)}")
    subprocess.run(command, cwd=cwd, check=True)


def neutralize_legal(project: Path) -> bool:
    """The scaffold ships an empty-but-present `legal.company` with legal pages off, and the config gate reads presence."""
    config = project / "src" / "config" / "site.json"
    try:
        data = json.loads(config.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not data.get("legal") or (data.get("pages") or {}).get("legal") is True:
        return False
    data["legal"] = False
    config.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print("+ neutralized site.json legal (no company declared, legal pages off)")
    return True


def main() -> int:
    project = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    required = [project / "package.json", project / "factory" / "template-spec.json"]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        print("Not a valid hotel template clone. Missing: " + ", ".join(missing), file=sys.stderr)
        return 2

    assets = project / "assets"
    source = assets / "source"

    with tempfile.TemporaryDirectory(prefix="web-factory-assets-") as temp_name:
        temporary = Path(temp_name)
        if assets.is_dir():
            for item in assets.iterdir():
                if item.name in {"manifest.yaml", ".gitkeep"}:
                    continue
                supplied = item.iterdir() if item.name == "source" else [item]
                for supplied_item in supplied:
                    if supplied_item.name == ".gitkeep":
                        continue
                    target = temporary / supplied_item.name
                    if target.exists():
                        print(
                            f"Duplicate supplied asset name: {supplied_item.name}",
                            file=sys.stderr,
                        )
                        return 3
                    if supplied_item.is_dir():
                        shutil.copytree(supplied_item, target)
                    else:
                        shutil.copy2(supplied_item, target)

        install = ["npm", "ci"] if (project / "package-lock.json").is_file() else ["npm", "install"]
        run(install, project)
        run(["npm", "run", "site:init"], project)

        source.mkdir(parents=True, exist_ok=True)
        for item in temporary.iterdir():
            target = source / item.name
            if target.exists():
                print(f"Refusing to overwrite supplied asset: {target}", file=sys.stderr)
                return 3
            shutil.move(str(item), str(target))

    if assets.is_dir():
        for item in assets.iterdir():
            if item.name in {"manifest.yaml", ".gitkeep", "source"}:
                continue
            shutil.rmtree(item) if item.is_dir() else item.unlink()

    neutralize_legal(project)
    run(["npm", "run", "check:setup"], project)
    print("Project initialized. Kivara demo removed; supplied assets are in assets/source/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
