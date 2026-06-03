from __future__ import annotations

import pytest

from alpi.alp.workgroup_client import _check_hub_single_marker


def test_single_done_accepted() -> None:
    _check_hub_single_marker("#done build green")


def test_single_task_accepted() -> None:
    _check_hub_single_marker("@lens #task #qa audit dist")


def test_plain_prose_accepted() -> None:
    _check_hub_single_marker("just a status note, no markers here")


def test_mixed_done_and_task_rejected() -> None:
    with pytest.raises(ValueError, match="one lifecycle marker"):
        _check_hub_single_marker("#done build green\n\n@lens #task #qa audit dist")


def test_two_task_openers_rejected() -> None:
    with pytest.raises(ValueError, match="one lifecycle marker"):
        _check_hub_single_marker("@pixel #task #build wire it\n@lens #task #qa audit")


def test_two_done_closers_rejected() -> None:
    with pytest.raises(ValueError, match="one lifecycle marker"):
        _check_hub_single_marker("#done build green\n#done qa green")
