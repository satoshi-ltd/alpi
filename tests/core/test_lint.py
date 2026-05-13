from __future__ import annotations

from pathlib import Path

from alpi.tools._lint import lint_content


def test_python_valid():
    assert lint_content("foo.py", "def f():\n    return 1\n") is None


def test_python_invalid():
    err = lint_content("foo.py", "def f(:\n")
    assert err is not None and "Python syntax error" in err


def test_python_empty_module_ok():
    assert lint_content("foo.py", "") is None


def test_json_valid():
    assert lint_content("foo.json", '{"a": 1, "b": [2, 3]}') is None


def test_json_invalid_trailing_comma():
    err = lint_content("foo.json", '{"a": 1,}')
    assert err is not None and "JSON parse error" in err


def test_yaml_valid():
    assert lint_content("foo.yaml", "a: 1\nb:\n  - 2\n  - 3\n") is None


def test_yaml_invalid_indent():
    err = lint_content("foo.yaml", "a:\n  - 1\n - 2\n")
    assert err is not None and "YAML parse error" in err


def test_toml_valid():
    assert lint_content("pyproject.toml", '[project]\nname = "x"\n') is None


def test_toml_invalid():
    err = lint_content("foo.toml", "[project\n")
    assert err is not None and "TOML parse error" in err


def test_unknown_suffix_passes_through():
    # No linter for .md / .txt / no-suffix → never blocks the write.
    assert lint_content("notes.md", "anything goes # not a header") is None
    assert lint_content("notes.txt", "{[")  is None
    assert lint_content("Makefile", "all:\n\techo hi\n") is None


def test_pathlib_path_accepted():
    assert lint_content(Path("/tmp/foo.json"), "{}") is None
    err = lint_content(Path("/tmp/foo.json"), "{")
    assert err is not None and "JSON" in err
