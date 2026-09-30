from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


class VersionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Spot:
    label: str
    path: str
    pattern: str

    def _match(self, text: str) -> re.Match:
        matches = list(re.finditer(self.pattern, text, re.M | re.S))
        if len(matches) != 1:
            raise VersionError(
                f"{self.label}: expected exactly one match in {self.path}, found {len(matches)}"
            )
        return matches[0]

    def read(self, text: str) -> str:
        return self._match(text).group("v")

    def write(self, text: str, value: str) -> str:
        m = self._match(text)
        return text[: m.start("v")] + value + text[m.end("v") :]


def _json_key(key: str, indent: int) -> str:
    return rf'^{" " * indent}"{key}": "(?P<v>[^"]+)"'


def _toml_section_key(section: str, key: str) -> str:
    return rf'^\[{re.escape(section)}\]$(?:(?!^\[).)*?^{key}\s*=\s*"(?P<v>[^"]+)"'


def _lock_package(name: str) -> str:
    return rf'^\[\[package\]\]\nname = "{re.escape(name)}"\nversion = "(?P<v>[^"]+)"'


def load(path: Path) -> str:
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def save(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def cargo_package_name(root: Path) -> str:
    text = load(root / "desktop/src-tauri/Cargo.toml")
    return Spot(
        "Cargo.toml [package] name",
        "desktop/src-tauri/Cargo.toml",
        _toml_section_key("package", "name"),
    ).read(text)


def pyproject_name(root: Path) -> str:
    text = load(root / "pyproject.toml")
    return Spot(
        "pyproject [project] name", "pyproject.toml", _toml_section_key("project", "name")
    ).read(text)


def version_spots(product: str, root: Path) -> list[Spot]:
    if product == "alpi":
        return [
            Spot(
                "pyproject.toml [project] version",
                "pyproject.toml",
                _toml_section_key("project", "version"),
            ),
            Spot(
                "alpi/__init__.py __version__",
                "alpi/__init__.py",
                r'^__version__\s*=\s*"(?P<v>[^"]+)"',
            ),
            Spot("uv.lock project entry", "uv.lock", _lock_package(pyproject_name(root))),
        ]
    if product == "desktop":
        return [
            Spot("desktop/package.json version", "desktop/package.json", _json_key("version", 2)),
            Spot(
                "tauri.conf.json version",
                "desktop/src-tauri/tauri.conf.json",
                _json_key("version", 2),
            ),
            Spot(
                "Cargo.toml [package] version",
                "desktop/src-tauri/Cargo.toml",
                _toml_section_key("package", "version"),
            ),
            Spot(
                "Cargo.lock package entry",
                "desktop/src-tauri/Cargo.lock",
                _lock_package(cargo_package_name(root)),
            ),
        ]
    if product == "mobile":
        return [
            Spot("mobile/package.json version", "mobile/package.json", _json_key("version", 2)),
            Spot(
                "package-lock.json top-level version",
                "mobile/package-lock.json",
                _json_key("version", 2),
            ),
            Spot(
                'package-lock.json packages[""] version',
                "mobile/package-lock.json",
                r'^    "": \{\n(?:      [^\n]*\n)*?      "version": "(?P<v>[^"]+)"',
            ),
            Spot("app.json expo.version", "mobile/app.json", _json_key("version", 4)),
        ]
    raise VersionError(f"unknown product {product!r}")


def mobile_counter_spots() -> list[Spot]:
    return [
        Spot("app.json expo.ios.buildNumber", "mobile/app.json", r'"buildNumber": "(?P<v>\d+)"'),
        Spot("app.json expo.android.versionCode", "mobile/app.json", r'"versionCode": (?P<v>\d+)'),
    ]


CHANGELOGS = {
    "alpi": "CHANGELOG.md",
    "desktop": "desktop/CHANGELOG.md",
    "mobile": "mobile/CHANGELOG.md",
}
PRODUCTS = tuple(CHANGELOGS)


def read_versions(product: str, root: Path) -> list[tuple[Spot, str]]:
    cache: dict[str, str] = {}
    out = []
    for spot in version_spots(product, root):
        if spot.path not in cache:
            cache[spot.path] = load(root / spot.path)
        out.append((spot, spot.read(cache[spot.path])))
    return out


def next_version(current: str, part: str) -> str:
    m = SEMVER.match(current)
    if not m:
        raise VersionError(f"not a plain X.Y.Z version: {current!r}")
    major, minor, patch = map(int, m.groups())
    if part == "major":
        return f"{major + 1}.0.0"
    if part == "minor":
        return f"{major}.{minor + 1}.0"
    if part == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise VersionError(f"unknown part {part!r}")


def changelog_top(root: Path, product: str) -> str | None:
    for line in load(root / CHANGELOGS[product]).splitlines():
        if line.startswith("## "):
            return line[3:].strip()
    return None
