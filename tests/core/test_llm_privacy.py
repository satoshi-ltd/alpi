"""Privacy guards on the litellm wrapper."""

from __future__ import annotations


def test_litellm_telemetry_is_disabled_on_import() -> None:
    """alpi's principle is no telemetry. LiteLLM defaults to
    ``telemetry = True``; ``_silence_litellm()`` runs at import time
    and must flip it off before any LLM call is made."""
    import alpi.llm  # noqa: F401 — side-effectful import triggers the guard
    import litellm
    assert litellm.telemetry is False, (
        "litellm.telemetry must be False. alpi sends zero telemetry; the "
        "LLM wrapper is the one place that could accidentally leak."
    )


_OFFLINE_PROBE = """
import os, socket
attempts = []
def guard(self, address, *a, **k):
    attempts.append(address)
    raise PermissionError(1, "blocked")
socket.socket.connect = guard
from alpi.llm import litellm_ready
from alpi.attachments import vision_status
from alpi.providers.curated import load_curated
litellm = litellm_ready()
TOOLS = [{"type": "function", "function": {"name": "t", "parameters": {"type": "object", "properties": {}}}}]
models = [(p, e["id"]) for p in ("openai", "anthropic") for e in load_curated(p)] + [("openai", "gpt-6.1-sol")]
bad = []
for provider, mid in models:
    info = litellm.model_cost.get(mid) or {}
    if info.get("max_input_tokens", 0) < 200_000 or not info.get("input_cost_per_token"):
        bad.append("catalogue:" + mid)
    if vision_status(provider + "/" + mid) != "yes":
        bad.append("vision:" + mid)
    try:
        litellm.get_optional_params(model=mid, custom_llm_provider=provider, tools=TOOLS, tool_choice="auto")
    except Exception as e:
        bad.append("tools:" + mid + ":" + type(e).__name__)
print("LOCAL", os.environ.get("LITELLM_LOCAL_MODEL_COST_MAP"), "ATTEMPTS", len(attempts), "BAD", bad)
"""


def test_alpi_starts_offline_and_every_recommended_model_keeps_window_price_vision_and_tools(tmp_path) -> None:
    import os
    import subprocess
    import sys

    env = {**os.environ, "HOME": str(tmp_path), "ALPI_SKIP_UPDATE_CHECK": "1"}
    env.pop("ALPI_HOME", None)
    env.pop("LITELLM_LOCAL_MODEL_COST_MAP", None)
    done = subprocess.run([sys.executable, "-c", _OFFLINE_PROBE], capture_output=True, text=True, timeout=180, env=env)
    assert done.returncode == 0, done.stderr
    assert "LOCAL True ATTEMPTS 0 BAD []" in done.stdout, done.stdout


def test_an_operator_can_still_ask_litellm_for_the_latest_price_map(tmp_path) -> None:
    import os
    import subprocess
    import sys

    env = {**os.environ, "HOME": str(tmp_path), "ALPI_SKIP_UPDATE_CHECK": "1", "LITELLM_LOCAL_MODEL_COST_MAP": "False"}
    env.pop("ALPI_HOME", None)
    done = subprocess.run(
        [sys.executable, "-c", "import alpi, os; print(os.environ['LITELLM_LOCAL_MODEL_COST_MAP'])"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    assert done.stdout.strip() == "False"


def test_the_output_price_of_a_native_model_comes_from_its_catalogue_entry() -> None:
    from alpi.host import usage

    assert usage.price_out("anthropic/claude-fable-5-2") == 4e-05
