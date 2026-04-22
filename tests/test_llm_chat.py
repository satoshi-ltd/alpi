"""End-to-end chat tests — make real LLM calls.

Skipped unless pytest is run with --llm or ALPI_LLM=1.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.llm

ALPI_BIN = os.environ.get("ALPI_BIN", "alpi")


def _run_once(home: Path, prompt: str, timeout: int = 90) -> tuple[int, str]:
    env = dict(os.environ)
    env["ALPI_HOME"] = str(home)
    r = subprocess.run(
        [ALPI_BIN, "chat", "--once", prompt],
        capture_output=True, text=True, timeout=timeout, env=env,
    )
    return r.returncode, r.stdout.strip()


def test_single_turn_replies(tmp_home: Path) -> None:
    rc, out = _run_once(tmp_home, "responde exactamente con la palabra 'OK' y nada mas")
    assert rc == 0
    assert out, "empty reply"


def test_session_is_persisted(tmp_home: Path) -> None:
    _run_once(tmp_home, "di solo 'listo'")
    files = list((tmp_home / "sessions").glob("*.json"))
    assert files, "no session saved"
    data = json.loads(files[0].read_text())
    assert any(m.get("role") == "user" for m in data["messages"])


def test_memory_learned_is_recalled_next_session(tmp_home: Path) -> None:
    rc, _ = _run_once(tmp_home, "Me llamo Marta Suárez. Recuérdalo.")
    assert rc == 0
    user_md = tmp_home / "memories" / "USER.md"
    assert user_md.exists()
    # Should have at least the name somewhere
    assert "Marta" in user_md.read_text()

    rc, out = _run_once(tmp_home, "¿Cómo me llamo?")
    assert rc == 0
    assert "Marta" in out


def test_session_search_finds_past_topic(tmp_home: Path) -> None:
    _run_once(tmp_home, "Cuéntame brevemente qué es tailscale.")
    rc, out = _run_once(
        tmp_home,
        "¿Recuerdas lo que hablamos sobre tailscale? Usa session_search si hace falta.",
    )
    assert rc == 0
    assert "tailscale" in out.lower()


def test_style_rule_lands_in_personality(tmp_home: Path) -> None:
    _run_once(
        tmp_home,
        "A partir de ahora responde siempre en un solo bullet. Guárdalo como instrucción de estilo.",
    )
    personality = (tmp_home / "personality.md").read_text().lower()
    assert "bullet" in personality or "bulleted" in personality
