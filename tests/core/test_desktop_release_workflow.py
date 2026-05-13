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
    verify_step = text.split("      - name: verify Apple certificate secret", 1)[1].split(
        "\n      - name:",
        1,
    )[0]
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
    assert "matrix.os == 'macos-latest'" in verify_step
    assert "openssl pkcs12 -info" in verify_step
    assert "security import" in verify_step
    assert "APPLE_CERTIFICATE_PASSWORD" in verify_step
    for secret in APPLE_SECRETS:
        assert f"secrets.{secret}" in macos_step
        assert f"secrets.{secret}" not in linux_step


def test_publish_desktop_validates_notarization_credentials_before_build() -> None:
    """Pre-flight round-trips APPLE_ID/PASSWORD/TEAM_ID through Apple's notary; wrong creds fail fast."""
    text = PUBLISH_DESKTOP.read_text()
    step = text.split(
        "      - name: verify Apple notarization credentials", 1,
    )[1].split("\n      - name:", 1)[0]

    assert "matrix.os == 'macos-latest'" in step
    assert "xcrun notarytool history" in step
    for secret in ("APPLE_ID", "APPLE_PASSWORD", "APPLE_TEAM_ID"):
        assert f"secrets.{secret}" in step


def test_publish_desktop_asserts_gatekeeper_acceptance_after_build() -> None:
    """codesign can succeed while notarization silently no-ops — spctl assess catches it."""
    text = PUBLISH_DESKTOP.read_text()
    step = text.split(
        "      - name: verify Gatekeeper accepts the signed DMG", 1,
    )[1].split("\n      - name:", 1)[0]

    assert "matrix.os == 'macos-latest'" in step
    assert "spctl --assess --type install" in step
    assert "codesign -dvv" in step
    build_idx = text.index("      - name: build signed macOS bundle")
    verify_idx = text.index("      - name: verify Gatekeeper accepts the signed DMG")
    assert verify_idx > build_idx


def test_publish_desktop_notarizes_and_staples_dmg_explicitly() -> None:
    """tauri-action v0.6.2 signs but doesn't auto-notarize; explicit submit+staple owns it."""
    text = PUBLISH_DESKTOP.read_text()
    step = text.split("      - name: notarize + staple DMG", 1)[1].split(
        "\n      - name:", 1,
    )[0]

    assert "matrix.os == 'macos-latest'" in step
    assert "xcrun notarytool submit" in step
    assert "--wait" in step
    assert 'status=' in step and 'Accepted' in step
    assert "xcrun stapler staple" in step
    assert "xcrun stapler validate" in step
    for secret in ("APPLE_ID", "APPLE_PASSWORD", "APPLE_TEAM_ID"):
        assert f"secrets.{secret}" in step

    # ordering: must run AFTER tauri build but BEFORE the Gatekeeper assert.
    build_idx = text.index("      - name: build signed macOS bundle")
    notarize_idx = text.index("      - name: notarize + staple DMG")
    gatekeeper_idx = text.index("      - name: verify Gatekeeper accepts the signed DMG")
    assert build_idx < notarize_idx < gatekeeper_idx


def test_publish_release_uses_idempotent_gh_release_edit_by_tag() -> None:
    """gh api PATCH .../releases/$id breaks on re-runs whose check-version output is stale; gh release edit --tag is keyed by tag and survives that."""
    text = PUBLISH_DESKTOP.read_text()
    step = text.split("      - name: publish draft", 1)[1].split(
        "\n  # ", 1,
    )[0]

    assert "gh release edit" in step
    assert "--draft=false" in step
    assert "set -euo pipefail" in step
    # The brittle id-based PATCH must be gone.
    assert "gh api -X PATCH" not in step
    assert "needs.check-version.outputs.release_id" not in step


def test_stapled_dmg_is_re_uploaded_with_clobber_after_notarize() -> None:
    """tauri-action uploads the pre-notarize bytes; without --clobber here, users would download a DMG whose hash Apple never registered."""
    text = PUBLISH_DESKTOP.read_text()
    step = text.split("      - name: re-upload stapled DMG to the release", 1)[1].split(
        "\n      - name:", 1,
    )[0]

    assert "matrix.os == 'macos-latest'" in step
    assert "gh release upload" in step
    assert "--clobber" in step
    # Ordering: must run AFTER notarize+staple, BEFORE the Gatekeeper assert.
    staple_idx = text.index("      - name: notarize + staple DMG")
    reupload_idx = text.index("      - name: re-upload stapled DMG to the release")
    gatekeeper_idx = text.index("      - name: verify Gatekeeper accepts the signed DMG")
    assert staple_idx < reupload_idx < gatekeeper_idx


def test_releasing_docs_match_publish_desktop_workflow() -> None:
    text = RELEASING.read_text()

    assert "publish-desktop.yml" in text
    assert "desktop-release.yml" not in text
    assert "Actions → ``desktop-release``" not in text
    for secret in APPLE_SECRETS:
        assert secret in text
