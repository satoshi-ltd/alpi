from __future__ import annotations

import os
from pathlib import Path

from alpi import config


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


def test_load_reads_env_file_and_overrides_existing_values(
    tmp_home_no_env: Path, monkeypatch
) -> None:
    """The daemon supervises many profiles in one process; per-profile
    ``.env`` loads MUST win over inherited values so a profile's
    credentials aren't poisoned by whoever loaded first."""
    env_path = tmp_home_no_env / ".env"
    env_path.write_text("ALPI_TEST_CONFIG_HELPER=from-env\nALPI_EXISTING=from-env\n")
    monkeypatch.setenv("ALPI_EXISTING", "stale")

    config.load(tmp_home_no_env)

    assert os.environ["ALPI_TEST_CONFIG_HELPER"] == "from-env"
    assert os.environ["ALPI_EXISTING"] == "from-env"
