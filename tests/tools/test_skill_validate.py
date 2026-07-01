"""Tests for skill validation."""

from __future__ import annotations

from pathlib import Path

from alpi.tools._skill_validate import validate_skill


def _write_skill(tmp_path: Path, name: str, skill_md: str, scripts: dict[str, str]):
    d = tmp_path / name
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(skill_md)
    for fname, src in scripts.items():
        (d / "scripts" / fname).write_text(src)
    return d


def test_clean_skill_has_no_findings(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "clean", "# Clean\n", {
        "hello.py": "import os\nimport json\nprint(os.getcwd())\n",
    })
    assert validate_skill(d) == []


def test_ignores_smb_appledouble_files(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "appledouble", "# Clean\n", {
        "run.py": "import os\nprint(os.getcwd())\n",
        "._run.py": "\x00\x05Mac OS X resource fork",
    })
    (d / "._SKILL.md").write_text("\x00\x05Mac OS X resource fork")
    (d / "scripts" / "__pycache__").mkdir()
    (d / "scripts" / "__pycache__" / "._run.cpython-314.pyc").write_bytes(b"\0\5Mac OS X")
    assert validate_skill(d) == []


def test_detects_syntax_error(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "broken", "# Broken\n", {
        "bad.py": "def foo(:\n    pass\n",
    })
    findings = validate_skill(d)
    assert any("SyntaxError" in f and "bad.py" in f for f in findings)


def test_detects_missing_import(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "missing", "# X\n", {
        "x.py": "import definitely_not_a_real_module_xyzzy\n",
    })
    findings = validate_skill(d)
    assert any("definitely_not_a_real_module_xyzzy" in f for f in findings)


def test_stdlib_imports_are_fine(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "std", "# Std\n", {
        "x.py": "import os\nimport json\nimport subprocess\nfrom pathlib import Path\n",
    })
    assert validate_skill(d) == []


def test_local_module_imports_are_fine(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "local", "# Local\n", {
        "main.py": "from helpers import run\n",
        "helpers.py": "def run(): pass\n",
    })
    assert validate_skill(d) == []


def test_oauth_race_detected(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "oauth", "# OAuth\n", {
        "go.py": (
            "import webbrowser\n"
            "import http.server\n"
            "webbrowser.open('https://p.com/auth')\n"
            "http.server.HTTPServer(('', 8080), None).serve_forever()\n"
        ),
    })
    findings = validate_skill(d)
    assert any("race" in f and "webbrowser.open" in f for f in findings)


def test_oauth_ok_when_server_starts_first(tmp_path: Path) -> None:
    d = _write_skill(tmp_path, "oauth_ok", "# OAuth\n", {
        "go.py": (
            "import webbrowser\n"
            "import threading\n"
            "import http.server\n"
            "server = http.server.HTTPServer(('', 8080), None)\n"
            "threading.Thread(target=server.serve_forever).start()\n"
            "webbrowser.open('https://p.com/auth')\n"
        ),
    })
    # webbrowser.open is after serve_forever in source order → no race flagged.
    findings = [f for f in validate_skill(d) if "race" in f]
    assert findings == []


def test_port_drift_between_doc_and_code(tmp_path: Path) -> None:
    d = _write_skill(
        tmp_path, "drift",
        "# Drift\nRun the callback server on localhost:8765.\n",
        {
            "server.py": (
                "import http.server\n"
                "http.server.HTTPServer(('localhost', 8080), None).serve_forever()\n"
            ),
        },
    )
    findings = validate_skill(d)
    assert any("8765" in f and "8080" in f for f in findings)


def test_port_match_no_flag(tmp_path: Path) -> None:
    d = _write_skill(
        tmp_path, "match",
        "# Match\nRun the callback server on localhost:8080.\n",
        {
            "server.py": (
                "import http.server\n"
                "http.server.HTTPServer(('localhost', 8080), None).serve_forever()\n"
            ),
        },
    )
    findings = [f for f in validate_skill(d) if "port" in f.lower()]
    assert findings == []
