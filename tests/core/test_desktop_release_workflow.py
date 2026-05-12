import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_JSON = ROOT / "desktop" / "package.json"
TAURI_CONF = ROOT / "desktop" / "src-tauri" / "tauri.conf.json"
CARGO_TOML = ROOT / "desktop" / "src-tauri" / "Cargo.toml"
CARGO_LOCK = ROOT / "desktop" / "src-tauri" / "Cargo.lock"
PUBLISH_DESKTOP = ROOT / ".github" / "workflows" / "publish-desktop.yml"
CHANGELOG = ROOT / "desktop" / "CHANGELOG.md"
RELEASING = ROOT / "desktop" / "RELEASING.md"

APPLE_SECRETS = [
    "APPLE_CERTIFICATE",
    "APPLE_CERTIFICATE_PASSWORD",
    "APPLE_SIGNING_IDENTITY",
    "APPLE_ID",
    "APPLE_PASSWORD",
    "APPLE_TEAM_ID",
]


def test_desktop_release_version_is_in_sync() -> None:
    package_version = json.loads(PACKAGE_JSON.read_text())["version"]
    tauri_version = json.loads(TAURI_CONF.read_text())["version"]
    cargo_version = re.search(
        r'(?m)^version = "([^"]+)"',
        CARGO_TOML.read_text(),
    ).group(1)
    lock_version = re.search(
        r'(?s)\[\[package\]\]\nname = "alpi-desktop"\nversion = "([^"]+)"',
        CARGO_LOCK.read_text(),
    ).group(1)
    changelog = CHANGELOG.read_text()

    assert package_version == tauri_version == cargo_version == lock_version
    assert f"## v{package_version} " in changelog


def test_tauri_config_declares_macos_hardened_runtime() -> None:
    config = json.loads(TAURI_CONF.read_text())
    macos = config["bundle"]["macOS"]

    assert macos["hardenedRuntime"] is True
    assert macos["entitlements"] is None
    assert "signingIdentity" not in macos
    assert "providerShortName" not in macos


def test_publish_desktop_checks_required_signing_secrets() -> None:
    text = PUBLISH_DESKTOP.read_text()
    secrets_step = text.split("      - name: secrets present", 1)[1].split(
        "\n      - name:",
        1,
    )[0]

    for secret in [
        "TAURI_SIGNING_PRIVATE_KEY",
        "TAURI_SIGNING_PRIVATE_KEY_PASSWORD",
        *APPLE_SECRETS,
    ]:
        assert secret in secrets_step
        assert f"secrets.{secret}" in secrets_step


def test_publish_desktop_scopes_apple_secrets_to_macos_build() -> None:
    text = PUBLISH_DESKTOP.read_text()
    macos_step = text.split("      - name: build signed macOS bundle", 1)[1].split(
        "\n      - name:",
        1,
    )[0]
    linux_step = text.split("      - name: build Linux bundles", 1)[1].split(
        "\n\n  # 3.",
        1,
    )[0]

    assert "matrix.os == 'macos-latest'" in macos_step
    assert "matrix.os == 'ubuntu-22.04'" in linux_step
    for secret in APPLE_SECRETS:
        assert f"secrets.{secret}" in macos_step
        assert f"secrets.{secret}" not in linux_step


def test_releasing_docs_match_publish_desktop_workflow() -> None:
    text = RELEASING.read_text()

    assert "publish-desktop.yml" in text
    assert "desktop-release.yml" not in text
    assert "Actions → ``desktop-release``" not in text
    for secret in APPLE_SECRETS:
        assert secret in text
