import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "web-factory" / "tools" / "pipeline_state.py"
_spec = importlib.util.spec_from_file_location("pipeline_state", _PATH)
ps = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ps)

HUB = "HUBKEY"


def _post(seq: int, author: str, text: str) -> dict:
    return {"seq": seq, "from": author, "text": text}


def test_open_task_maps_to_its_phase():
    posts = [_post(1, HUB, "@quill #task #content write it")]
    assert ps.derive_state(posts, HUB) == "content"


def test_fix_slug_canonicalizes_to_phase():
    posts = [
        _post(1, HUB, "@quill #task #content write it"),
        _post(2, HUB, "#done content verified"),
        _post(3, HUB, "@quill #task #content-fix expand deluxe description"),
    ]
    assert ps.derive_state(posts, HUB) == "content"


def test_closed_phase_maps_to_next_phase():
    posts = [
        _post(1, HUB, "@scout #task #intake go"),
        _post(2, HUB, "#done intake verified"),
    ]
    assert ps.derive_state(posts, HUB) == "assets"


def test_closed_qa_means_launched():
    posts = [
        _post(1, HUB, "@lens #task #qa audit dist/"),
        _post(2, HUB, "#done qa green — launching"),
    ]
    assert ps.derive_state(posts, HUB) == "launched"


def test_done_blocked_means_blocked():
    posts = [
        _post(1, HUB, "@pixel #task #build ship"),
        _post(2, HUB, "#done BLOCKED · build · npm broken"),
    ]
    assert ps.derive_state(posts, HUB) == "blocked"


def test_open_maintenance_task():
    posts = [
        _post(1, HUB, "@lens #task #qa audit"),
        _post(2, HUB, "#done qa green"),
        _post(3, HUB, "@muse #task #maint-001-images re-export restaurant photos"),
    ]
    assert ps.derive_state(posts, HUB) == "maintenance"


def test_closed_maintenance_returns_to_launched():
    posts = [
        _post(1, HUB, "@muse #task #maint-001-images re-export"),
        _post(2, HUB, "#done maint shipped"),
    ]
    assert ps.derive_state(posts, HUB) == "launched"


def test_member_markers_carry_no_state():
    posts = [_post(1, "MEMBER", "#task #content sneaky")]
    assert ps.derive_state(posts, HUB) is None
