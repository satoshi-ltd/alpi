# Manual smoke, real fastembed + sqlite-vec, no LLM: uv run pytest tests/manual/test_rag_learn_file.py -q -s
from __future__ import annotations

import json
from pathlib import Path

from alpi.core.store import store_path
from alpi.tools import _state
from alpi.tools import workspace as ws_mod
from alpi.tools.learn_file import LearnFile


def test_learn_file_real_embedder_end_to_end(tmp_home, tmp_path):
    workspace = tmp_home / "ws"
    workspace.mkdir()
    (tmp_home / "config.yaml").write_text(f"workspace: {workspace}\n")

    unique = "Zephyrine quokka protocol revision 9173"
    attachment = tmp_path / "incoming" / "notes.md"
    attachment.parent.mkdir(parents=True)
    attachment.write_text(f"# Research notes\n\n{unique}\n\nFollow-up next week.\n")

    _state.set_turn_attachments([
        {"name": "notes.md", "path": str(attachment), "mime": "text/markdown"},
    ])

    out = LearnFile().run()
    assert out.ok, out.error
    body = json.loads(out.output)
    assert body["ok"] is True and body["indexed"] is True, body

    copied = workspace / body["path"]
    assert copied.is_file(), f"document not copied: {copied}"
    assert body["path"].startswith(".alpi/documents/")

    manifest = workspace / ".alpi" / "documents" / "manifest.jsonl"
    assert manifest.is_file(), "manifest.jsonl missing"
    entry = json.loads(manifest.read_text().splitlines()[-1])
    assert entry["original_name"] == "notes.md"

    assert store_path(tmp_home).is_file(), "rag/store.sqlite not created in profile"

    res = ws_mod.SearchWorkspace().run(query="quokka protocol revision", k=5)
    assert res.ok, res.error
    results = json.loads(res.output)["results"]
    assert results, "search returned nothing"
    assert any(unique in r["snippet"] for r in results), "learned document not found by search_workspace"
    print(f"OK — learned {body['path']} and found it via search_workspace ({len(results)} hits)")
