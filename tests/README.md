# alf — tests

Pytest-based. One command to run everything.

## Layout

```
tests/
├── conftest.py              # --llm flag, shared fixtures
├── test_config.py           # config load/save/resolve_model
├── test_home.py             # HOME_DIR resolution & bootstrap
├── test_memory.py           # MemoryStore — add/dedup/hygiene/limits
├── test_memory_tool.py      # Memory tool (LLM-facing)
├── test_skills.py           # create_skill spec enforcement
├── test_tools.py            # all other tools (bash, read/write/edit, grep...)
├── test_session_search.py   # session_search unit
├── test_reflect_unit.py     # reflect JSON parsing / helpers
├── test_continue.py         # --continue resume logic
├── test_llm_chat.py         # ❗ needs --llm — full chat round-trip
└── test_llm_reflect.py      # ❗ needs --llm — reflect with real LLM
```

Anything marked with `pytestmark = pytest.mark.llm` is skipped unless you opt in.

## Running

```bash
# From the repo root, using the installed alf's venv:
PY=/Users/javi/.local/share/uv/tools/alf/bin/python

# Unit & fast tests only (no LLM, no cost)
$PY -m pytest

# Everything, including real LLM calls
$PY -m pytest --llm

# Or equivalently:
ALPI_LLM=1 $PY -m pytest --llm

# A specific file
$PY -m pytest tests/test_memory.py -v

# A specific test
$PY -m pytest tests/test_memory.py::test_add_rejects_exact_duplicate -v
```

## Fixtures

- **`tmp_home_no_env`** — fresh temp alf home, no `.env` copied. Use for unit tests that must not talk to any LLM.
- **`tmp_home`** — same, but copies `~/.alpi/.env` in so LLM calls work. Use for `--llm` tests.
- `_reset_session_search_state` runs automatically before each test to avoid state leaking.

## Adding tests

**Rule of thumb:**
- New capability → add one unit test covering the happy path + at least one edge case.
- If it's LLM-driven (needs a real model call), put it in `test_llm_*.py` and mark it with `pytest.mark.llm`.
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
$PY -m pytest --llm -q    # run LLM tests if the change touches the chat/reflect flow
```
