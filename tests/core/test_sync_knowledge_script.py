"""scripts/sync_knowledge.py — drift validator between TOPICS and the on-disk references."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "sync_knowledge.py"


def _load_sync_module():
    spec = importlib.util.spec_from_file_location("sync_knowledge", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_passes_on_a_clean_repo() -> None:
    # Running the script in the real repo must exit 0; a non-zero exit means the references and TOPICS have drifted.
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"sync_knowledge.py reports drift:\n{result.stdout}\n{result.stderr}"


def test_module_exposes_repo_paths() -> None:
    sync = _load_sync_module()
    assert sync.REFS.is_dir()
    assert sync.REFS.name == "references"
