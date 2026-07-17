import importlib.util
import json
from pathlib import Path

import pytest
import yaml

_WF = Path(__file__).resolve().parents[1] / "web-factory"
_SCRIPT = (
    _WF / "agents" / "lingua" / "skills" / "communication"
    / "multi-locale-translation-pass" / "scripts" / "run.py"
)
_spec = importlib.util.spec_from_file_location("lingua_translate", _SCRIPT)
tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tr)


def _frontmatter(path: Path) -> dict:
    _, raw, _ = path.read_text().split("---", 2)
    return yaml.safe_load(raw) or {}


def test_lingua_has_no_delegate_and_script_owns_the_files():
    front = _frontmatter(_WF / "agents" / "lingua" / "agent.md")
    assert "delegate" in front["tools_deny"]
    skill = _frontmatter(
        _WF / "agents" / "lingua" / "skills" / "communication"
        / "multi-locale-translation-pass" / "SKILL.md"
    )
    assert "delegate" not in skill["tools"]
    assert "OPENROUTER_API_KEY" in skill["requires_env"]


def _project(tmp_path: Path) -> Path:
    p = tmp_path / "casa-test"
    (p / "src" / "config").mkdir(parents=True)
    (p / "src" / "config" / "site.json").write_text(json.dumps({
        "brand": {"name": "Casa Test"},
        "defaultLocale": "es",
        "locales": ["es", "en", "fr"],
    }))
    content = p / "src" / "content"
    for coll in ("pages", "rooms", "legal", "posts"):
        (content / coll).mkdir(parents=True)
    (content / "pages" / "home.es.json").write_text(json.dumps({
        "lang": "es",
        "hero": {"title": "Luz sobre el río", "image": "/img/hero.webp"},
        "seo": {"title": "Casa Test — hotel boutique", "keywords": "hotel, rio"},
    }))
    (content / "rooms" / "deluxe.es.json").write_text(json.dumps({
        "lang": "es",
        "slug": "deluxe",
        "name": "La habitación de la esquina",
        "view": "Calle y patio interior",
        "amenities": ["Balcón privado", "Wi-Fi"],
        "priceFrom": 120,
        "image": "/img/deluxe.webp",
    }))
    (content / "legal" / "privacy.es.md").write_text(
        "---\ntitle: Privacidad\nlang: es\n---\n\nTexto legal del hotel.\n"
    )
    (content / "posts" / "rio.es.md").write_text(
        "---\ntitle: El río\nexcerpt: Paseos al alba\nlang: es\n---\n\nEl Guadalquivir al amanecer.\n"
    )
    return p


def _fake_batch():
    def fake(call_kwargs, target, mapping, brand):
        return {k: f"[{target}] {v}" for k, v in mapping.items()}
    return fake


def test_walk_skips_immutable_and_non_prose():
    data = {
        "slug": "deluxe", "image": "/img/x.webp", "url": "https://x.com",
        "phone": "+34 954 59 13 43", "name": "La esquina",
        "nested": {"priceFrom": 120, "view": "Patio interior"},
        "list": ["Balcón privado"],
    }
    leaves = {v for _, v in tr._walk(data)}
    assert leaves == {"La esquina", "Patio interior", "Balcón privado"}


def test_full_pass_writes_targets_preserving_structure(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setattr(tr, "_model_kwargs", lambda: {})
    monkeypatch.setattr(tr, "translate_batch", _fake_batch())
    assert tr.run(project, only=None, check_only=False) == 0

    en_room = json.loads((project / "src/content/rooms/deluxe.en.json").read_text())
    assert en_room["lang"] == "en"
    assert en_room["slug"] == "deluxe"
    assert en_room["priceFrom"] == 120
    assert en_room["image"] == "/img/deluxe.webp"
    assert en_room["view"].startswith("[en]")
    assert en_room["amenities"][0].startswith("[en]")
    assert en_room["amenities"][1].startswith("[en]")

    fr_home = json.loads((project / "src/content/pages/home.fr.json").read_text())
    assert fr_home["hero"]["image"] == "/img/hero.webp"
    assert fr_home["seo"]["title"].startswith("[fr]")

    post = (project / "src/content/posts/rio.en.md").read_text()
    assert "lang: en" in post and "[en]" in post

    assert not (project / "src/content/legal/privacy.en.md").exists()
    assert not (project / "src/content/legal/privacy.fr.md").exists()


def test_identical_multiword_leaf_warns_but_singleword_does_not(monkeypatch):
    calls = {"n": 0}

    def fake(call_kwargs, target, mapping, brand):
        calls["n"] += 1
        return dict(mapping)

    monkeypatch.setattr(tr, "translate_batch", fake)
    leaves = {"a": "Calle y patio interior", "b": "Wi-Fi"}
    result, warnings = tr._translate_leaves({}, "fr", leaves, "Casa")
    assert result == leaves
    assert len(warnings) == 1 and "Calle y patio" in warnings[0]
    assert calls["n"] == 2


def test_dropped_field_fails_hard(monkeypatch):
    def fake(call_kwargs, target, mapping, brand):
        out = {k: f"[{target}] {v}" for k, v in mapping.items()}
        out.pop(next(iter(out)))
        return out

    monkeypatch.setattr(tr, "translate_batch", fake)
    with pytest.raises(SystemExit, match="dropped"):
        tr._translate_leaves({}, "fr", {"a": "Vista al río", "b": "Patio interior"}, "Casa")


def test_check_mode_catches_missing_and_structure_drift(tmp_path, monkeypatch):
    project = _project(tmp_path)
    monkeypatch.setattr(tr, "_model_kwargs", lambda: {})
    monkeypatch.setattr(tr, "translate_batch", _fake_batch())
    assert tr.run(project, only=None, check_only=False) == 0
    assert tr.run(project, only=None, check_only=True) == 0

    drifted = project / "src/content/rooms/deluxe.en.json"
    data = json.loads(drifted.read_text())
    del data["view"]
    drifted.write_text(json.dumps(data))
    assert tr.run(project, only=None, check_only=True) == 1

    (project / "src/content/pages/home.fr.json").unlink()
    assert tr.run(project, only=None, check_only=True) == 1
