import importlib.util
from pathlib import Path

_NP_PATH = Path(__file__).resolve().parents[1] / "web-factory" / "new-project.py"
_spec = importlib.util.spec_from_file_location("new_project", _NP_PATH)
np = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(np)

HUB = "HUBKEY"


def _post(seq: int, author: str, text: str) -> dict:
    return {"seq": seq, "from": author, "text": text}


def test_open_task_maps_to_its_phase():
    posts = [_post(1, HUB, "@quill #task #content write it")]
    assert np.derive_state(posts, HUB) == "content"


def test_fix_slug_canonicalizes_to_phase():
    posts = [
        _post(1, HUB, "@quill #task #content write it"),
        _post(2, HUB, "#done content verified"),
        _post(3, HUB, "@quill #task #content-fix expand deluxe description"),
    ]
    assert np.derive_state(posts, HUB) == "content"


def test_closed_phase_maps_to_next_phase():
    posts = [
        _post(1, HUB, "@scout #task #intake go"),
        _post(2, HUB, "#done intake verified"),
    ]
    assert np.derive_state(posts, HUB) == "assets"


def test_closed_qa_means_launched():
    posts = [
        _post(1, HUB, "@lens #task #qa audit dist/"),
        _post(2, HUB, "#done qa green — launching"),
    ]
    assert np.derive_state(posts, HUB) == "launched"


def test_done_blocked_means_blocked():
    posts = [
        _post(1, HUB, "@pixel #task #build ship"),
        _post(2, HUB, "#done BLOCKED · build · npm broken"),
    ]
    assert np.derive_state(posts, HUB) == "blocked"


def test_open_maintenance_task():
    posts = [
        _post(1, HUB, "@lens #task #qa audit"),
        _post(2, HUB, "#done qa green"),
        _post(3, HUB, "@muse #task #maint-001-images re-export restaurant photos"),
    ]
    assert np.derive_state(posts, HUB) == "maintenance"


def test_closed_maintenance_returns_to_launched():
    posts = [
        _post(1, HUB, "@muse #task #maint-001-images re-export"),
        _post(2, HUB, "#done maint shipped"),
    ]
    assert np.derive_state(posts, HUB) == "launched"


def test_member_markers_carry_no_state():
    posts = [_post(1, "MEMBER", "#task #content sneaky")]
    assert np.derive_state(posts, HUB) is None


def test_sync_payload_appends_transition_and_launch_date():
    original = {
        "state": "qa",
        "launched_at": None,
        "history": [{"state": "qa", "at": "2026-07-16", "by": "mira"}],
    }

    updated, changed = np.sync_status_payload(original, "launched", "2026-07-17")

    assert changed is True
    assert original["state"] == "qa"
    assert updated["state"] == "launched"
    assert updated["launched_at"] == "2026-07-17"
    assert updated["history"][-1] == {
        "state": "launched",
        "at": "2026-07-17",
        "by": "status-sync",
        "note": "derived from transcript (was qa)",
    }


def test_sync_payload_is_idempotent():
    status = {"state": "build", "history": []}

    updated, changed = np.sync_status_payload(status, "build", "2026-07-17")

    assert changed is False
    assert updated is status
