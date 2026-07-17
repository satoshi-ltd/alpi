import importlib.util
from pathlib import Path

import pytest

_SYNC_PATH = Path(__file__).resolve().parents[1] / "web-factory" / "sync-template.py"
_spec = importlib.util.spec_from_file_location("sync_template", _SYNC_PATH)
sync = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sync)


@pytest.fixture()
def workspace(monkeypatch, tmp_path):
    template = tmp_path / "templates" / "hotel-web"
    projects = tmp_path / "projects"
    (template / "src" / "components").mkdir(parents=True)
    (template / "src" / "components" / "Hero.astro").write_text("new hero")
    (template / "src" / "config").mkdir(parents=True)
    (template / "src" / "config" / "site-schema.ts").write_text("new schema")

    project = projects / "casa-test"
    (project / "src" / "components").mkdir(parents=True)
    (project / "src" / "components" / "Hero.astro").write_text("old hero")
    (project / "src" / "components" / "Stale.astro").write_text("removed upstream")
    (project / "src" / "config").mkdir(parents=True)
    (project / "src" / "config" / "site-schema.ts").write_text("old schema")
    (project / "src" / "config" / "site.json").write_text('{"theme": "boutique"}')
    (project / "src" / "content").mkdir(parents=True)
    (project / "src" / "content" / "home.es.json").write_text('{"lang": "es"}')

    monkeypatch.setattr(sync, "WORKSPACE", tmp_path)
    monkeypatch.setattr(sync, "TEMPLATE", template)
    monkeypatch.setattr(sync, "PROJECTS", projects)
    return project


def test_sync_replaces_fixed_layer_only(workspace):
    changed = sync.sync_project("casa-test", dry_run=False)
    assert changed
    assert (workspace / "src" / "components" / "Hero.astro").read_text() == "new hero"
    assert not (workspace / "src" / "components" / "Stale.astro").exists()
    assert (workspace / "src" / "config" / "site-schema.ts").read_text() == "new schema"
    assert (workspace / "src" / "config" / "site.json").read_text() == '{"theme": "boutique"}'
    assert (workspace / "src" / "content" / "home.es.json").read_text() == '{"lang": "es"}'


def test_dry_run_reports_without_writing(workspace):
    changed = sync.sync_project("casa-test", dry_run=True)
    assert changed
    assert (workspace / "src" / "components" / "Hero.astro").read_text() == "old hero"
    assert (workspace / "src" / "components" / "Stale.astro").exists()


def test_sync_is_idempotent(workspace):
    sync.sync_project("casa-test", dry_run=False)
    assert not sync.sync_project("casa-test", dry_run=False)


def test_missing_project_fails(workspace):
    with pytest.raises(SystemExit):
        sync.sync_project("no-such-project", dry_run=False)
