from __future__ import annotations

import os
from pathlib import Path

from alpi import config


def test_deep_merge_does_not_share_defaults_with_caller() -> None:
    """Two profiles in one process must not see each other's mutations. Pre-fix, ``_deep_merge`` shallow-copied the top dict, so a caller's ``cfg.providers["ollama"].append(...)`` mutated ``DEFAULT_CONFIG["providers"]["ollama"]`` for every later load."""
    a = config._deep_merge(config.DEFAULT_CONFIG, {})
    a["providers"]["ollama"].append({"name": "leaked", "url": "x"})
    a["tools"]["terminal"]["approval"]["allowlist"].append("rm -rf /")

    b = config._deep_merge(config.DEFAULT_CONFIG, {})
    assert b["providers"]["ollama"] == []
    assert b["tools"]["terminal"]["approval"]["allowlist"] == []
    # And DEFAULT_CONFIG itself must remain pristine for future calls.
    assert config.DEFAULT_CONFIG["providers"]["ollama"] == []
    assert config.DEFAULT_CONFIG["tools"]["terminal"]["approval"]["allowlist"] == []


def test_deep_merge_merges_nested_dicts() -> None:
    defaults = {
        "tools": {
            "browser": {"vision": False, "human_typing": True},
            "terminal": {"sandbox": False},
        },
        "workspace": "",
    }
    user = {
        "tools": {
            "browser": {"vision": True},
        },
        "workspace": "~/work",
    }

    merged = config._deep_merge(defaults, user)

    assert merged["tools"]["browser"] == {
        "vision": True,
        "human_typing": True,
    }
    assert merged["tools"]["terminal"] == {"sandbox": False}
    assert merged["workspace"] == "~/work"


def test_workspace_path_normalizes_and_strips(tmp_path: Path) -> None:
    cfg = config.Config(
        home=tmp_path,
        model="",
        workspace="  ./workspace  ",
    )

    assert cfg.workspace_path == Path("workspace").resolve()


def test_workspace_path_returns_none_for_blank() -> None:
    cfg = config.Config(home=Path("/tmp"), model="", workspace="   ")
    assert cfg.workspace_path is None


def test_save_is_atomic_no_tmp_leftover(tmp_path: Path) -> None:
    """A crash mid-save must never leave a truncated config.yaml that would silently empty providers/mcp on next load."""
    home = tmp_path / "h"
    home.mkdir()
    cfg = config.Config(home=home, model="x")
    config.save(cfg)
    cfg_path = home / "config.yaml"
    tmp = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    assert cfg_path.exists()
    assert not tmp.exists()
    config.save(cfg)  # second save still atomic, no tmp residue
    assert not tmp.exists()


def test_load_does_not_mutate_os_environ(
    tmp_home_no_env: Path, monkeypatch
) -> None:
    """The daemon supervises many profiles in one process. Loading a profile
    config must NOT touch ``os.environ`` — secrets are bound per-call by
    ``resolve_model`` (see ``test_resolve_model_reads_api_key_from_profile_env``)."""
    env_path = tmp_home_no_env / ".env"
    env_path.write_text("ALPI_TEST_CONFIG_HELPER=from-env\nALPI_EXISTING=from-env\n")
    monkeypatch.setenv("ALPI_EXISTING", "stale")
    monkeypatch.delenv("ALPI_TEST_CONFIG_HELPER", raising=False)

    config.load(tmp_home_no_env)

    assert "ALPI_TEST_CONFIG_HELPER" not in os.environ
    assert os.environ["ALPI_EXISTING"] == "stale"
