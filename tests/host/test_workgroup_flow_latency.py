from __future__ import annotations

import asyncio
import json
import threading
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from alpi import home as home_mod
from alpi.alp import workgroup as wg_mod
from alpi.alp.keys import load_or_generate
from alpi.host import handlers, server
from alpi.tui import host_client


@pytest.fixture
def flow_root():
    with tempfile.TemporaryDirectory(prefix="wg-flow-", dir="/tmp") as directory:
        yield Path(directory)


@pytest.mark.integration
@pytest.mark.parametrize("warm", [False, True])
def test_pipeline_state_arrives_while_turn_and_transcript_are_pending(flow_root: Path, monkeypatch, warm):
    home = flow_root / "home"
    home.mkdir()
    kp = load_or_generate(home)
    wg = wg_mod.create(
        home, name="flow", hub_kp=kp, member_pubkeys=[],
        pipelines={"build": ["build", "qa"]}, launch_pipeline="build",
        pipeline_steps={"build": {"owner": "worker"}, "qa": {"owner": "worker"}},
    )
    member = wg.member(kp.pubkey_b64())
    key = wg_mod.open_sealed_group_key(member.sealed_key, kp)
    path = home / "alp" / "workgroups" / wg.meta.id / "transcript.jsonl"
    with path.open("w") as stream:
        for seq in range(1, 1001):
            body = "@worker #task #build build the project" if seq == 1 else "progress " + "x" * 500
            nonce, ciphertext = wg_mod.encrypt_post(key, body.encode())
            stream.write(json.dumps({
                "seq": seq, "from": kp.pubkey_b64(), "key_version": member.key_version,
                "nonce": nonce, "ciphertext": ciphertext, "pipeline_trigger": seq == 1,
            }) + "\n")
    monkeypatch.setenv("ALPI_HOME", str(home))
    monkeypatch.setattr(home_mod, "_ROOT", home)
    if warm:
        from alpi.host.workgroup import fold_task_state
        fold_task_state(home, wg.meta.id)

    async def check():
        loop = asyncio.get_running_loop()
        loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
        host = server.Server(home=home)
        handlers.register(host)
        await host.start()
        entered, release = threading.Event(), threading.Event()

        def turn():
            entered.set()
            release.wait(5)

        occupied = loop.run_in_executor(None, turn)
        while not entered.is_set():
            await asyncio.sleep(0)
        params = {"profile": "default", "wg_id": wg.meta.id}
        transcript = asyncio.create_task(host_client.acall(
            "host.workgroup.transcript", {**params, "tail": True, "limit": 200},
        ))
        try:
            state = await asyncio.wait_for(host_client.acall("host.workgroup.tasks", params), timeout=1)
            assert state["pipeline_run"]["current_phase"] == "build"
            assert state["active"]["slug"] == "build"
            assert not transcript.done()
        finally:
            release.set()
            await occupied
            await transcript
            await host.stop()

    asyncio.run(check())
