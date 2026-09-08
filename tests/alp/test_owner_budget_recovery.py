from types import SimpleNamespace

import pytest

from alpi import home as home_mod, service
from alpi.alp import peers


@pytest.fixture
def budget_case(tmp_path, monkeypatch):
    hub = tmp_path / "hub"
    hub.mkdir()
    owner = tmp_path / "muse"
    owner.mkdir()
    wg = SimpleNamespace(meta=SimpleNamespace(
        id="wg_budget_wait", name="hotel", hub_pubkey="HUB", paused=False,
        pipelines={"media-update": ("media-update", "media-qa")},
        pipeline_steps={"media-update": {"owner": "muse"}},
        launch_pipeline="media-update", quorum_timeout_seconds=0,
    ))
    recent = [{"seq": 1, "from": "HUB", "text": "@muse #task #media-update update images",
               "ts": "2026-09-08T00:00:00Z"}]
    monkeypatch.setattr(peers, "load", lambda _: [SimpleNamespace(id="muse", pubkey="MUSE")])
    monkeypatch.setattr(home_mod, "find_home_by_pubkey", lambda pk: owner if pk == "MUSE" else None)
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda path, *args: path == owner)
    return hub, owner, wg, recent


def test_budget_wait_resumes_after_cap_is_raised(budget_case, monkeypatch):
    hub, owner, wg, recent = budget_case
    service._WATCHDOG_OBSERVED_AT[(str(hub), wg.meta.id)] = (1, 0)
    assert service._active_owner_budget_blocks_recovery(hub, wg, recent)
    assert (str(hub), wg.meta.id) not in service._WATCHDOG_OBSERVED_AT
    monkeypatch.setattr(service, "_budget_blocks_dispatch", lambda *args: False)
    assert not service._active_owner_budget_blocks_recovery(hub, wg, recent)


@pytest.mark.parametrize("text", ["#media-update done — images updated", "#skip #media-update unchanged"])
def test_delivered_owner_can_close_even_over_budget(budget_case, text):
    hub, _, wg, recent = budget_case
    recent.append({"seq": 2, "from": "MUSE", "text": text})
    assert not service._active_owner_budget_blocks_recovery(hub, wg, recent)


def test_remote_owner_is_not_treated_as_local_budget_wait(budget_case, monkeypatch):
    hub, _, wg, recent = budget_case
    monkeypatch.setattr(home_mod, "find_home_by_pubkey", lambda pk: None)
    assert not service._active_owner_budget_blocks_recovery(hub, wg, recent)


@pytest.mark.asyncio
async def test_watchdog_does_not_spend_repair_attempts_on_budget_wait(budget_case, monkeypatch):
    import time

    hub, _, wg, recent = budget_case
    async def gate(*args):
        return None
    monkeypatch.setattr(service, "_maybe_gate_advance", gate)
    monkeypatch.setattr(service, "_spawn_dispatch", lambda *args: pytest.fail("budget wait dispatched hub"))
    service._WATCHDOG_OBSERVED_AT[(str(hub), wg.meta.id)] = (1, time.monotonic() - 10000)
    await service._maybe_watchdog_close(hub, "mira", wg, recent)
    assert service._peek_hub_watchdog_count(hub, wg.meta.id, 1) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("gate_passed", [False, True])
async def test_hub_budget_wait_preserves_gate_completion(budget_case, monkeypatch, gate_passed):
    from alpi.alp import keys

    hub, _, wg, recent = budget_case
    monkeypatch.setattr(keys, "load_or_generate", lambda _: SimpleNamespace(pubkey_b64=lambda: "HUB"))
    async def baseline(*args):
        return None
    async def gate(*args):
        return True if gate_passed else None
    monkeypatch.setattr(service, "_ensure_phase_baseline", baseline)
    monkeypatch.setattr(service, "_exhausted_working_phase", lambda *args: None)
    monkeypatch.setattr(service, "_maybe_gate_advance", gate)
    monkeypatch.setattr(service, "_empty_hub_exchange_phase", lambda *args: pytest.fail("budget wait reached recovery"))
    if gate_passed:
        monkeypatch.setattr(service, "_active_owner_budget_blocks_recovery", lambda *args: pytest.fail("completed gate checked owner budget"))
    await service._maybe_dispatch_for_hub(hub, "mira", wg, recent)
