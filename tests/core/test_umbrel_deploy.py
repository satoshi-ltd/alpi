from pathlib import Path

from alpi import cli


ROOT = Path(__file__).resolve().parents[2]
UMBREL = ROOT / "deploy" / "umbrel" / "alpi"


def test_umbrel_package_runs_tui_behind_app_proxy() -> None:
    compose = (UMBREL / "docker-compose.yml").read_text()
    entrypoint = (UMBREL / "entrypoint.sh").read_text()
    manifest = (UMBREL / "umbrel-app.yml").read_text()

    assert "APP_HOST: alpi_server_1" in compose
    assert "APP_PORT: 8080" in compose
    assert "satoshiltd/alpi-umbrel:0.5.0" in compose
    assert "0.5.0-dev" not in compose
    assert 'version: "0.5.0"' in manifest
    assert 'releaseNotes: ""' in manifest
    assert "category: ai" in manifest
    assert "alpi daemon start &" in entrypoint
    assert "ttyd" in entrypoint
    assert "alpi; exec sh" in entrypoint


def test_umbrel_package_keeps_profile_state_persistent() -> None:
    dockerfile = (UMBREL / "Dockerfile").read_text()
    compose = (UMBREL / "docker-compose.yml").read_text()
    readme = (UMBREL / "README.md").read_text()

    assert "HOME=/data" in dockerfile
    assert 'VOLUME ["/data"]' in dockerfile
    assert "sha256sum -c -" in dockerfile
    assert "TARGETARCH" in dockerfile
    assert "ALPI_PLATFORM: umbrel" in compose
    assert "- ${APP_DATA_DIR}/data:/data" in compose
    assert "/data/.alpi" in readme


def test_umbrel_package_does_not_present_web_dashboard_as_scope() -> None:
    manifest = (UMBREL / "umbrel-app.yml").read_text()
    readme = (UMBREL / "README.md").read_text()

    assert "terminal TUI" in manifest
    assert "does not ship a separate web dashboard" in readme
    assert "host.sock" not in manifest


def test_umbrel_store_assets_are_present() -> None:
    icon = ROOT / "assets" / "umbrel" / "alpi-icon.svg"
    screenshots = sorted((ROOT / "assets" / "umbrel").glob("alpi-screenshot-*.png"))

    assert icon.exists()
    text = icon.read_text()
    assert 'viewBox="0 0 256 256"' in text
    assert "<rect" in text
    assert len(screenshots) == 4


def test_umbrel_setup_skips_system_service_install(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")

    def fail_install(root: Path) -> str:
        raise AssertionError(f"unexpected service install for {root}")

    monkeypatch.setattr("alpi.service.daemon_installed", lambda: False)
    monkeypatch.setattr("alpi.service.install_daemon", fail_install)

    cli._ensure_daemon_installed(tmp_path)
