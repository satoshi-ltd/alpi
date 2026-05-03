# alpi - tests

Pytest-based. One command to run everything.

## Layout

```
tests/
├── conftest.py              # --llm flag, shared fixtures
├── alp/                     # ALP transport, workgroups, keys, mention, TCP
├── core/                    # config, home, logs, sessions, CLI, engine, status
├── gateway/                 # Telegram / IMAP / Gmail gateway flows
├── llm/                     # real model probes, skipped unless --llm is set
├── mail/                    # mail auth/setup helpers
├── mcp/                     # MCP client and registry
├── tools/                   # deterministic tool implementations
├── tui/                     # TUI widgets, panels, and shared UI helpers
└── manual/                  # runnable scripts, not collected by pytest
```

Anything marked with `pytestmark = pytest.mark.llm` is skipped unless you opt in.
Anything marked with `pytestmark = pytest.mark.integration` is skipped unless you opt in.

## Running

```bash
# From the repo root:
PY=.venv/bin/python

# Unit & fast tests only (integration tests skipped by default)
$PY -m pytest

# Include integration tests that need sockets, sandboxes, or real subprocesses
$PY -m pytest --integration

# Manual system probe with real LLM calls
$PY -m pytest tests/llm --llm -q

# Or equivalently:
ALPI_LLM=1 $PY -m pytest tests/llm --llm -q

# A specific file
$PY -m pytest tests/core/test_memory.py -v

# A specific test
$PY -m pytest tests/core/test_memory.py::test_add_rejects_exact_duplicate -v
```

## Fixtures

- **`tmp_home_no_env`** - fresh temp alpi home, no `.env` copied. Use for unit tests that must not talk to any LLM.
- **`tmp_home_with_real_env`** - fresh temp alpi home with `~/.alpi/.env` copied and loaded. Use only for `--llm` tests.
- **`llm_engine`** - real Engine fixture for `tests/llm`, parametrized across the manual LLM model matrix.
- `_reset_session_search_state` runs automatically before each test to avoid state leaking.

## Adding tests

**Rule of thumb:**
- New capability → add one unit test covering the happy path + at least one edge case.
- If it's LLM-driven (needs a real model call), put it under `tests/llm/` and mark it with `pytest.mark.llm`.
- If it's deterministic (just Python logic), keep it LLM-free.

**Example for an LLM test:**

```python
import pytest
pytestmark = pytest.mark.llm

def test_my_new_flow(tmp_home: Path) -> None:
    ...
```

**Example for a unit test:**

```python
def test_my_helper(tmp_home_no_env: Path) -> None:
    ...
```

## CI checklist

Before shipping a change:

```bash
$PY -m pytest -q          # all fast tests must pass
$PY -m pytest tests/llm --llm -q  # manual probe for prompt/tool-routing changes
```
