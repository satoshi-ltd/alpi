from __future__ import annotations

import pytest


@pytest.fixture
def tui_home(tmp_home):
    from alpi.cli import _bootstrap

    _bootstrap(tmp_home)
    return tmp_home


@pytest.fixture
def tui_profile_home(tui_home):
    from alpi.cli import _bootstrap

    home = tui_home / "profiles" / "doc"
    home.mkdir(parents=True)
    _bootstrap(home)
    return home
