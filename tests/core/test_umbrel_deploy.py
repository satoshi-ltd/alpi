import os
import subprocess
from pathlib import Path

from alpi import __version__ as ALPI_VERSION
from alpi import cli


ROOT = Path(__file__).resolve().parents[2]
UMBREL = ROOT / "deploy" / "umbrel" / "alpi"


def test_umbrel_package_runs_tui_behind_app_proxy() -> None:
    compose = (UMBREL / "docker-compose.yml").read_text()
    entrypoint = (UMBREL / "entrypoint.sh").read_text()
    manifest = (UMBREL / "umbrel-app.yml").read_text()

    assert "APP_HOST: alpi_server_1" in compose
    assert "APP_HOST: server" not in compose
    assert "APP_PORT: 8080" in compose
    assert f"satoshiltd/alpi-umbrel:{ALPI_VERSION}" in compose
    assert 'user: "1000:1000"' in compose
    assert "- 49200:49200" in compose
    assert "DEVICE_DOMAIN_NAME: $DEVICE_DOMAIN_NAME" in compose
    assert "0.5.0-dev" not in compose
    assert f'version: "{ALPI_VERSION}"' in manifest
    assert 'releaseNotes: ""' in manifest
    assert "category: ai" in manifest
    assert 'submission: https://github.com/getumbrel/umbrel-apps/pull/5533' in manifest
    assert 'icon: ""' in manifest
    assert "alpi daemon start &" in entrypoint
    assert "ttyd_pid=" in entrypoint
    assert 'kill -0 "$daemon_pid"' in entrypoint
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
    assert "USER 1000:1000" in dockerfile
    assert "ALPI_PLATFORM: umbrel" in compose
    assert "- ${APP_DATA_DIR}/data:/data" in compose
    assert "/data/.alpi" in readme
    assert "49200" in readme
    assert (UMBREL / "data" / ".gitkeep").exists()


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
    assert "M 512,508" in text
    assert "M80.0047" not in text
    assert len(screenshots) == 4


def test_umbrel_local_package_generator_keeps_submission_manifest_clean(
    tmp_path: Path,
) -> None:
    script = ROOT / "deploy" / "umbrel" / "prepare-local-package.sh"
    dest = tmp_path / "alpi"

    result = subprocess.run(
        [str(script), str(dest)],
        check=True,
        capture_output=True,
        text=True,
    )
    local_manifest = (dest / "umbrel-app.yml").read_text()

    assert "gallery: []" in (UMBREL / "umbrel-app.yml").read_text()
    assert 'icon: ""' in (UMBREL / "umbrel-app.yml").read_text()
    assert result.stdout.strip() == str(dest)
    assert "raw.githubusercontent.com/satoshi-ltd/alpi/main/assets/umbrel" in local_manifest
    assert "alpi-icon.svg" in local_manifest
    assert "alpi-screenshot-04.png" in local_manifest
    assert 'icon: ""' not in local_manifest


def test_umbrel_local_package_generator_honours_asset_base_override(
    tmp_path: Path,
) -> None:
    script = ROOT / "deploy" / "umbrel" / "prepare-local-package.sh"
    dest = tmp_path / "alpi"

    subprocess.run(
        [str(script), str(dest)],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": os.environ["PATH"],
            "ASSET_BASE": "https://example.invalid/branch-x/assets/umbrel",
        },
    )
    local_manifest = (dest / "umbrel-app.yml").read_text()
    assert "example.invalid/branch-x/assets/umbrel/alpi-icon.svg" in local_manifest
    assert "example.invalid/branch-x/assets/umbrel/alpi-screenshot-04.png" in local_manifest
    assert "raw.githubusercontent.com" not in local_manifest


def test_umbrel_local_package_generator_refuses_unsafe_dest(tmp_path: Path) -> None:
    script = ROOT / "deploy" / "umbrel" / "prepare-local-package.sh"
    for bad in ("/", str(ROOT / "deploy")):
        result = subprocess.run(
            [str(script), bad],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, bad
        assert "refuse to rm -rf unsafe dest_dir" in result.stderr


def test_umbrel_one_shot_deploy_script_is_guarded() -> None:
    script = ROOT / "deploy" / "umbrel" / "deploy-to-umbrel.sh"
    text = script.read_text()

    assert "version mismatch:" in text
    assert "prepare-local-package.sh" in text
    assert "Injecting Syncthing workspace bind into local package compose" in text
    assert '${APP_DATA_DIR}/../syncthing/data:/data/workspace' in text
    assert "Resolving Umbrel app-store path" in text
    assert "ControlMaster=auto" in text
    assert 'PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"' in text
    assert "Applying package on Umbrel" in text
    assert "sync_app_data" in text
    assert "rsync -a --exclude=data" in text
    assert "apps.restart.mutate" in text
    assert "apps.install.mutate" in text
    assert "apps.uninstall.mutate" not in text
    assert "server_container()" in text
    assert r"^${app_id}[-_]server[-_]1$" in text


def test_umbrel_migration_script_uses_backup_restore_flow() -> None:
    script = ROOT / "deploy" / "umbrel" / "migrate-home-to-umbrel.sh"
    text = script.read_text()

    assert 'SOURCE_HOME="${SOURCE_HOME:-$HOME/.alpi}"' in text
    assert "ALPI_HOME=\"$SOURCE_HOME\" uv run alpi backup" in text
    assert "--passphrase-stdin" in text
    assert "sudo -n docker cp" in text
    assert "alpi restore /tmp/alpi-migration.alpi-backup --passphrase-stdin --force" in text
    assert 'printf "Migration passphrase: " >&2' in text
    assert 'printf \'%s\\n\' "$passphrase" | sudo -n docker exec -i' in text
    assert "apps.restart.mutate" in text
    assert "ControlMaster=auto" in text
    assert "Local encrypted archive kept at:" in text


def test_umbrel_setup_skips_system_service_install(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")

    def fail_install(root: Path) -> str:
        raise AssertionError(f"unexpected service install for {root}")

    monkeypatch.setattr("alpi.service.daemon_installed", lambda: False)
    monkeypatch.setattr("alpi.service.install_daemon", fail_install)

    cli._ensure_daemon_installed(tmp_path)


def test_umbrel_daemon_wizard_short_circuits(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")

    def fail_call(*args, **kwargs):
        raise AssertionError("unexpected service call in Umbrel daemon wizard")

    calls: list[tuple[str, str]] = []

    class FakeUi:
        @staticmethod
        def banner(*args, **kwargs):
            calls.append(("banner", kwargs.get("subtitle", "")))

        @staticmethod
        def dim(message: str):
            calls.append(("dim", message))

        @staticmethod
        def ok_and_wait(message: str):
            calls.append(("ok", message))

    monkeypatch.setattr("alpi.service.daemon_installed", fail_call)
    monkeypatch.setattr("alpi.service.daemon_running_pid", fail_call)
    monkeypatch.setattr("alpi.ui.banner", FakeUi.banner)
    monkeypatch.setattr("alpi.ui.dim", FakeUi.dim)
    monkeypatch.setattr("alpi.ui.ok_and_wait", FakeUi.ok_and_wait)

    cli._daemon_lifecycle_wizard(tmp_path)

    assert calls
    assert calls[0] == ("banner", "managed by Umbrel")
    assert calls[-1] == ("ok", "daemon lifecycle is managed by Umbrel")


def test_umbrel_service_status_uses_platform_wording(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    monkeypatch.setattr("alpi.service.daemon_running_pid", lambda root: 1234)

    assert cli._service_status(tmp_path, "default") == "managed by Umbrel · pid 1234"


def test_umbrel_devices_subtitle_uses_advertised_host(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    monkeypatch.setenv("DEVICE_DOMAIN_NAME", "umbrel.local")

    assert cli._devices_subtitle(
        tmp_path, ("umbrel.local", "umbrel"),
    ) == "umbrel · umbrel.local:49200"


def test_devices_network_row_uses_auto_wording_outside_umbrel(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("ALPI_PLATFORM", raising=False)
    assert cli._network_row_status(tmp_path, None) == "auto-detect Tailscale or LAN"


def test_devices_network_setup_saves_pairing_name(
    tmp_path: Path, monkeypatch,
) -> None:
    from alpi import config as cfg_mod

    cfg_mod.save(cfg_mod.Config(home=tmp_path, model=""))
    monkeypatch.setenv("ALPI_PLATFORM", "umbrel")
    monkeypatch.setenv("DEVICE_DOMAIN_NAME", "umbrel.local")

    prompts = iter(["umbrel.local", "Umbrel Home"])

    class FakeUi:
        @staticmethod
        def crumb(*_parts):
            return "crumb"

        @staticmethod
        def banner(*_args, **_kwargs):
            return None

        @staticmethod
        def dim(*_args, **_kwargs):
            return None

        class _console:
            @staticmethod
            def print(*_args, **_kwargs):
                return None

        @staticmethod
        def text(*_args, **_kwargs):
            return next(prompts)

        @staticmethod
        def ok_and_wait(*_args, **_kwargs):
            return None

        @staticmethod
        def cancelled():
            return None

    monkeypatch.setattr("alpi.ui.crumb", FakeUi.crumb)
    monkeypatch.setattr("alpi.ui.banner", FakeUi.banner)
    monkeypatch.setattr("alpi.ui.dim", FakeUi.dim)
    monkeypatch.setattr("alpi.ui._console", FakeUi._console)
    monkeypatch.setattr("alpi.ui.text", FakeUi.text)
    monkeypatch.setattr("alpi.ui.ok_and_wait", FakeUi.ok_and_wait)
    monkeypatch.setattr("alpi.ui.cancelled", FakeUi.cancelled)
    monkeypatch.setattr("alpi.cli._restart_daemon_for_apply", lambda _root: "")

    cli._devices_network_setup(tmp_path)

    cfg = cfg_mod.load(tmp_path)
    assert cfg.host["tcp_host"] == "umbrel.local"
    assert cfg.host["device_name"] == "Umbrel Home"


def test_alp_peer_tcp_label_uses_clear_wording(
    tmp_path: Path, monkeypatch,
) -> None:
    calls = []

    class FakeUi:
        @staticmethod
        def Heading(text: str):
            return {"heading": text}

        @staticmethod
        def banner(*args, **kwargs):
            return None

        @staticmethod
        def dim(*args, **kwargs):
            return None

        class _console:
            @staticmethod
            def print(*args, **kwargs):
                return None

        @staticmethod
        def menu(_title, items, **_kwargs):
            calls.extend(items)
            return None

    from alpi import config as cfg_mod

    cfg = cfg_mod.Config(home=tmp_path, model="")
    cfg_mod.save(cfg)

    monkeypatch.setattr("alpi.service.enabled_subsystems", lambda _h: {
        "gateway": True,
        "schedule": True,
        "alp": True,
        "workgroups": True,
        "host": True,
    })
    monkeypatch.setattr("alpi.service.daemon_running_pid", lambda _root: None)
    monkeypatch.setattr("alpi.ui.Heading", FakeUi.Heading)
    monkeypatch.setattr("alpi.ui.banner", FakeUi.banner)
    monkeypatch.setattr("alpi.ui.dim", FakeUi.dim)
    monkeypatch.setattr("alpi.ui._console", FakeUi._console)
    monkeypatch.setattr("alpi.ui.menu", FakeUi.menu)

    cli._subsystems_wizard(tmp_path, "default")

    labels = [item[0] for item in calls if isinstance(item, tuple)]
    assert "Peer TCP listener" in labels
