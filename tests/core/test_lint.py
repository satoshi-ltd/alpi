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


# A Spring Boot layout: a shared base plus one document per profile, as in every Mirai Java service.
SPRING_APPLICATION_YML = """\
server:
  port: 8080
spring:
  application:
    name: metas-api-intelligence
---
spring:
  config:
    activate:
      on-profile: dev
  datasource:
    url: jdbc:postgresql://localhost:5432/metas
---
spring:
  config:
    activate:
      on-profile: prod
  datasource:
    url: jdbc:postgresql://db:5432/metas
"""


def test_yaml_with_several_documents_is_accepted():
    assert lint_content("src/main/resources/application.yml", SPRING_APPLICATION_YML) is None


def test_yaml_a_broken_later_document_is_refused_with_its_absolute_line():
    broken = SPRING_APPLICATION_YML.replace(
        "      on-profile: prod\n", "      on-profile: prod\n     bad: indent\n",
    )
    line = broken.splitlines().index("     bad: indent") + 1

    err = lint_content("application.yml", broken)

    assert err is not None and err.startswith("YAML parse error")
    # The line is counted from the top of the file, not from the start of the broken document.
    assert f"at line {line}:" in err


def test_yaml_a_broken_first_document_still_reports_its_line():
    err = lint_content("application.yaml", "a:\n  - 1\n - 2\n---\nb: 2\n")
    assert err is not None and "at line 3:" in err


def test_yaml_explicit_and_empty_documents_are_accepted():
    for content in ("---\na: 1\n", "---\n---\n", "a: 1\n...\n---\nb: 2\n", "# only a comment\n", ""):
        assert lint_content("k8s.yaml", content) is None, repr(content)


def test_yaml_a_broken_document_after_valid_ones_is_not_masked_by_them():
    content = "a: 1\n---\nb: 2\n---\nc: [unclosed\n"
    err = lint_content("deploy.yml", content)
    assert err is not None and err.startswith("YAML parse error")
