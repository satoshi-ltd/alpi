from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
import yaml
from pypdf import PdfReader

from alpi import attachments, tools
from alpi.host.connection_context import ConnectionContext
from alpi.host.connection_context import use as use_connection
from alpi.pdf import layout, ttf
from alpi.tools import _policy, _state

MEMBER = ConnectionContext(connection_id="c2", device_id="d2", source="remote", role="member")


def _reader(data: bytes) -> PdfReader:
    return PdfReader(io.BytesIO(data))


def _text(data: bytes) -> list[str]:
    return [page.extract_text() for page in _reader(data).pages]


def _render(markdown: str, **kwargs) -> bytes:
    return layout.render(markdown, **kwargs).data


@pytest.fixture
def home(tmp_path: Path, monkeypatch) -> Path:
    root = tmp_path / "alpi"
    workspace = tmp_path / "ws"
    (root / "out").mkdir(parents=True)
    (root / "sessions").mkdir()
    workspace.mkdir()
    monkeypatch.setenv("ALPI_HOME", str(root))
    monkeypatch.chdir(workspace)
    (root / "config.yaml").write_text(f"workspace: {workspace}\n")
    return root


def test_the_bundled_fonts_parse_and_cover_the_languages_a_knowledge_assistant_writes() -> None:
    for stem in ("Geist-Regular", "Geist-Bold", "Geist-Italic", "Geist-BoldItalic", "GeistMono-Regular"):
        font = ttf.load(stem)
        missing = [ch for ch in "áéíóúñçüÁÉÑºª«»“”‘’…€→—–•·×√" if not font.glyph(ord(ch))]
        assert missing == [], (stem, missing)
        assert font.width("Kaixo", 10) > 0


def test_a_document_renders_searchable_text_with_accents_symbols_and_styles() -> None:
    data = _render(
        "# alpi profilak\n\nEuskaraz: **ñ á ç** € → *etzana* `kodea` ✓ ✗ — «aipua».\n\n- bat\n- bi\n\n1. lehen\n2. bigarren\n",
        title="alpi profilak",
    )
    assert data.startswith(b"%PDF-1.7") and data.rstrip().endswith(b"%%EOF")
    page = _text(data)[0]
    for piece in ("alpi profilak", "ñ á ç", "€ → etzana kodea √ × — «aipua»", "• bat", "2. bigarren", "1 / 1"):
        assert piece in page, piece


def test_characters_no_bundled_font_has_become_a_question_mark_and_emoji_vanish() -> None:
    page = _text(_render("中文 ok 🙂 end"))[0]
    assert "?? ok" in page and "🙂" not in page and "end" in page


def test_a_pagebreak_comment_starts_a_new_page_and_the_footer_counts_pages() -> None:
    texts = _text(_render("# Uno\n\ntexto\n\n<!-- pagebreak -->\n\n# Dos\n\nmás\n", title="Perfiles"))
    assert len(texts) == 2
    assert "Uno" in texts[0] and "Dos" not in texts[0] and "Dos" in texts[1]
    assert "Perfiles" in texts[1] and "2 / 2" in texts[1]


def test_a_pagebreak_at_the_top_does_not_leave_an_empty_first_page() -> None:
    assert len(_text(_render("<!-- pagebreak -->\n\n# Uno\n"))) == 1


def test_a_long_table_continues_on_the_next_page_with_its_header_again() -> None:
    rows = "\n".join(f"| fila {i} | valor {i} |" for i in range(120))
    texts = _text(_render(f"| Perfil | Lanak |\n|---|---|\n{rows}\n"))
    assert len(texts) >= 2
    assert "Perfil Lanak" in texts[1] and "fila 119" in texts[-1]
    assert "fila 0 valor 0" in texts[0]


def test_a_table_cell_taller_than_a_page_is_split_instead_of_lost() -> None:
    cell = "palabra " * 3000
    texts = _text(_render(f"| A | B |\n|---|---|\n| {cell} | fin |\n"))
    assert len(texts) >= 2
    assert sum(t.count("palabra") for t in texts) == 3000


def test_long_words_and_long_code_lines_wrap_instead_of_running_off_the_page() -> None:
    word = "x" * 400
    data = _render(f"{word}\n\n```\n{'y' * 400}\n```\n")
    text = "".join(_text(data)).replace("\n", "")
    assert text.count("x") == 400 and text.count("y") == 400


def test_http_links_are_clickable_and_other_schemes_are_not() -> None:
    reader = _reader(_render("[ok](https://example.com/a) [bad](javascript:alert(1)) [file](file:///etc/passwd)"))
    uris = [a.get_object()["/A"]["/URI"] for a in reader.pages[0].get("/Annots", [])]
    assert uris == ["https://example.com/a"]


def test_a_chart_block_becomes_a_table_and_a_broken_one_stays_code() -> None:
    chart = json.dumps({"type": "bar", "title": "Kostua", "unit": "$", "x": ["lun", "mar"],
                        "series": [{"name": "assistant", "values": [1.2, None]}]})
    page = _text(_render(f"```chart\n{chart}\n```\n\n```chart\nnot json\n```\n"))[0]
    assert "Kostua" in page and "assistant" in page and "lun 1.2$" in page and "not json" in page


def test_oversized_documents_are_refused_before_rendering(monkeypatch) -> None:
    with pytest.raises(layout.DocumentTooLarge):
        layout.render("x" * (layout.MAX_MARKDOWN_CHARS + 1))
    monkeypatch.setattr(layout, "MAX_PAGES", 2)
    with pytest.raises(layout.DocumentTooLarge):
        layout.render("\n\n<!-- pagebreak -->\n\n".join(f"page {i}" for i in range(5)))
    with pytest.raises(layout.DocumentTooLarge):
        layout.render("| a |\n|---|\n" + "| x |\n" * (layout.MAX_TABLE_CELLS + 1))


def test_the_tool_writes_a_new_pdf_in_out_and_reports_it_as_an_attachment(home: Path) -> None:
    first = tools.execute("pdf", {"markdown": "# Informe\n\nhola", "name": "informe"})
    second = tools.execute("pdf", {"markdown": "# Informe\n\nadiós", "name": "informe"})
    assert first.ok and second.ok, (first.error, second.error)
    paths = [Path(json.loads(r.output.splitlines()[0])["out"]) for r in (first, second)]
    assert [p.name for p in paths] == ["informe.pdf", "informe-2.pdf"]
    assert "hola" in _text(paths[0].read_bytes())[0] and "adiós" in _text(paths[1].read_bytes())[0]
    produced = attachments.produced_attachment(
        "pdf", first.output, roots=attachments.servable_roots(home, None, image=True),
        doc_roots=attachments.servable_roots(home, None, image=False),
    )
    assert produced and produced["kind"] == "pdf" and produced["producer"] == "pdf"


def test_without_a_name_the_file_takes_the_title_and_a_timestamp(home: Path) -> None:
    result = tools.execute("pdf", {"markdown": "# alpi profilak\n\ntexto"})
    out = Path(json.loads(result.output.splitlines()[0])["out"])
    assert out.parent == home / "out" and out.name.startswith("alpi-profilak-") and out.suffix == ".pdf"


def test_the_tool_converts_a_markdown_file_and_needs_exactly_one_source(home: Path) -> None:
    source = home / "out" / "nota.md"
    source.write_text("# Nota\n\ncontenido del archivo")
    result = tools.execute("pdf", {"path": str(source), "name": "nota"})
    assert result.ok, result.error
    assert "contenido del archivo" in _text((home / "out" / "nota.pdf").read_bytes())[0]
    assert not tools.execute("pdf", {}).ok
    assert not tools.execute("pdf", {"markdown": "x", "path": str(source)}).ok


def test_a_name_cannot_escape_the_out_folder(home: Path) -> None:
    result = tools.execute("pdf", {"markdown": "x", "name": "../../evil"})
    assert result.ok
    out = Path(json.loads(result.output.splitlines()[0])["out"])
    assert out.parent == home / "out" and out.name == "evil.pdf"


def test_write_paths_that_leave_out_refuse_the_pdf(home: Path) -> None:
    cfg = yaml.safe_load((home / "config.yaml").read_text())
    cfg["tools"] = {"write_paths": ["drafts"]}
    (home / "config.yaml").write_text(yaml.safe_dump(cfg))
    result = tools.execute("pdf", {"markdown": "x", "name": "blocked"})
    assert not result.ok and "tools.write_paths" in result.error
    assert not (home / "out" / "blocked.pdf").exists()
    cfg["tools"] = {"write_paths": ["out"]}
    (home / "config.yaml").write_text(yaml.safe_dump(cfg))
    assert tools.execute("pdf", {"markdown": "x", "name": "allowed"}).ok


def test_denying_write_file_also_denies_pdf() -> None:
    denies = _policy.effective_denies(["write_file"])
    assert "pdf" in denies
    assert "pdf" not in {s["function"]["name"] for s in tools.schemas(deny=denies)}
    assert "pdf" not in _policy.effective_denies(["terminal"])
    assert "pdf" in {s["function"]["name"] for s in tools.schemas(deny=_policy.effective_denies([]))}


def test_a_member_makes_a_pdf_and_can_attach_it_but_cannot_convert_someone_elses_file(home: Path) -> None:
    theirs = home / "out" / "theirs.md"
    theirs.write_text("SECRET OF ANOTHER CONNECTION")
    _state.reset_turn_outputs()
    with use_connection(MEMBER):
        made = tools.execute("pdf", {"markdown": "# Mío\n\nhola", "name": "mio"})
        assert made.ok, made.error
        assert tools.execute("attach_file", {"path": str(home / "out" / "mio.pdf")}).ok
        assert not tools.execute("pdf", {"path": str(theirs), "name": "stolen"}).ok
    assert not (home / "out" / "stolen.pdf").exists()


def test_a_body_row_that_fits_a_page_but_not_under_the_repeated_header_does_not_loop() -> None:
    for words in (834, 880, 930):
        texts = _text(_render("| Name | Notes |\n|---|---|\n| a | " + "texto " * words + "|\n| b | fin |\n"))
        assert len(texts) <= 3, words
        assert sum(t.count("texto") for t in texts) == words and "fin" in texts[-1]


def test_short_columns_keep_their_longest_word_whole_next_to_a_prose_column() -> None:
    prose = "una explicación bastante larga que ocupa varias líneas en la celda " * 4
    page = _text(_render(f"| Perfil | Coste | Notas |\n|---|---|---|\n| assistant | 1.2 | {prose} |\n"))[0]
    assert "Perfil Coste" in page and "assistant 1.2" in page


def test_the_title_is_the_first_real_level_one_heading_as_plain_text() -> None:
    assert layout.render("## Sección\n\n```bash\n# install the deps\n```\n").title == ""
    assert layout.render("# **Informe** de `alpi` [enlace](https://x.y)\n").title == "Informe de alpi enlace"
    assert layout.render("Informe\n=======\n\ntexto\n").title == "Informe"
    assert layout.render("# Uno\n", title="  Dos   tres ").title == "Dos tres"


def test_a_lone_surrogate_in_the_title_or_text_does_not_crash() -> None:
    rendered = layout.render("# bad \ud83d heading\n\ntext \udc00 here", title="bad \ud83d")
    page = " ".join(_text(rendered.data)[0].split())
    assert "bad heading" in page and "text here" in page
    assert _reader(rendered.data).metadata.title == "bad"


def test_deep_nesting_keeps_its_content() -> None:
    quotes = ">" * 30 + " deep quote"
    bullets = "\n".join("  " * i + f"- level {i}" for i in range(12))
    text = "".join(_text(_render(f"{quotes}\n\n{bullets}\n")))
    assert "deep quote" in text and "level 11" in text


def test_a_pagebreak_comment_tolerates_case_and_spacing() -> None:
    assert len(_text(_render("uno\n\n<!--PageBreak -->\n\ndos\n"))) == 2


def test_a_long_non_latin_name_stays_under_the_filesystem_limit(home: Path) -> None:
    result = tools.execute("pdf", {"markdown": "x", "name": "文" * 200})
    assert result.ok, result.error
    out = Path(json.loads(result.output.splitlines()[0])["out"])
    assert len(out.name.encode("utf-8")) <= 255


def test_a_member_pdf_that_fails_claims_no_name_for_later(home: Path, monkeypatch) -> None:
    _state.reset_turn_outputs()
    later = home / "out" / "weekly.pdf"
    with use_connection(MEMBER):
        assert not tools.execute("pdf", {"markdown": "x" * (layout.MAX_MARKDOWN_CHARS + 1), "name": "weekly"}).ok
    later.write_bytes(b"%PDF-1.7 owner's report")
    with use_connection(MEMBER):
        assert not tools.execute("read_file", {"path": str(later)}).ok
        assert not tools.execute("attach_file", {"path": str(later)}).ok

    raced = home / "out" / "raced.pdf"
    from alpi.tools import pdf as pdf_tool
    real_open = pdf_tool.os.open

    def lose_the_race(path, flags, mode=0o777):
        if str(path) == str(raced.resolve()):
            raced.write_bytes(b"%PDF-1.7 someone else's")
        return real_open(path, flags, mode)

    monkeypatch.setattr(pdf_tool.os, "open", lose_the_race)
    with use_connection(MEMBER):
        lost = tools.execute("pdf", {"markdown": "x", "name": "raced"})
        assert not lost.ok and "appeared while writing" in lost.error
        assert not tools.execute("read_file", {"path": str(raced)}).ok
    assert raced.read_bytes() == b"%PDF-1.7 someone else's"


def test_the_apps_tool_list_marks_pdf_denied_with_write_file(home: Path, monkeypatch) -> None:
    import asyncio

    from alpi import home as home_mod
    from alpi.host import tools as host_tools

    monkeypatch.setattr(home_mod, "_ROOT", home)
    (home / "config.yaml").write_text(yaml.safe_dump({"tools": {"deny": ["write_file"]}}))
    listed = asyncio.run(host_tools._tools_list({"profile": "default"}, None))
    assert next(t for t in listed["tools"] if t["name"] == "pdf")["denied"] is True


def test_a_workgroup_phase_that_may_not_write_hides_pdf(monkeypatch) -> None:
    monkeypatch.setenv("ALPI_WORKGROUP_WRITE_SCOPE", '{"root":"","paths":[]}')
    assert "pdf" in _policy.effective_denies([])


def test_a_successful_pdf_counts_as_delivering_the_turn() -> None:
    from types import SimpleNamespace

    from alpi import engine

    assert engine._delivered_by_tool([SimpleNamespace(name="pdf", ok=True, args={})])
    assert not engine._delivered_by_tool([SimpleNamespace(name="pdf", ok=False, args={})])


def test_a_long_line_of_emphasis_markers_parses_in_bounded_memory() -> None:
    import tracemalloc

    tracemalloc.start()
    try:
        rendered = layout.render("*a " * 20000 + "\n\n" + "foo_bar " * 8000)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    assert peak < 150 * 1024 * 1024
    assert "foo_bar" in "".join(_text(rendered.data))


def test_emphasis_still_renders_after_the_linear_text_join() -> None:
    page = _text(_render("antes *cursiva* **negrita** ~~tachado~~ después_de_todo"))[0]
    assert "antes cursiva negrita tachado después_de_todo" in page


def test_a_long_url_column_does_not_split_the_short_columns() -> None:
    url = "https://miraiproduct.atlassian.net/wiki/pages/viewpage.action?pageId=" + "4" * 60
    page = _text(_render(f"| Perfil | Coste | Fuente |\n|---|---|---|\n| assistant | 1.2 | {url} |\n"))[0]
    assert "Perfil Coste" in page and "assistant 1.2" in page


def test_deep_quotes_keep_words_together_instead_of_one_letter_per_line() -> None:
    page = _text(_render(">" * 40 + " palabra larga aquí"))[0]
    assert "palabra larga aquí" in page


def test_a_long_ordered_marker_stays_on_the_page() -> None:
    reader = _reader(_render("123456789. item\n"))
    xs = []
    reader.pages[0].extract_text(visitor_text=lambda text, cm, tm, font, size: xs.append(tm[4]) if text.strip() else None)
    assert min(xs) >= 0


def test_a_refused_write_claims_no_out_name_for_a_member(home: Path) -> None:
    cfg = yaml.safe_load((home / "config.yaml").read_text())
    cfg["tools"] = {"write_paths": ["drafts"]}
    (home / "config.yaml").write_text(yaml.safe_dump(cfg))
    _state.reset_turn_outputs()
    with use_connection(MEMBER):
        assert not tools.execute("pdf", {"markdown": "x", "name": "weekly"}).ok
        assert not tools.execute("write_file", {"path": str(home / "out" / "notes.md"), "content": "x"}).ok
    (home / "out" / "weekly.pdf").write_bytes(b"%PDF owner secret")
    (home / "out" / "notes.md").write_text("owner notes")
    with use_connection(MEMBER):
        assert not tools.execute("read_file", {"path": str(home / "out" / "weekly.pdf")}).ok
        assert not tools.execute("read_file", {"path": str(home / "out" / "notes.md")}).ok


@pytest.mark.parametrize("tool,args", [
    ("edit_file", {"old_string": "a", "new_string": "b"}),
    ("delete_file", {}),
])
def test_a_failed_edit_or_delete_claims_no_out_name_for_a_member(home: Path, tool: str, args: dict) -> None:
    _state.reset_turn_outputs()
    target = home / "out" / "weekly.pdf"
    with use_connection(MEMBER):
        assert not tools.execute(tool, {"path": str(target), **args}).ok
    target.write_text("owner secret")
    with use_connection(MEMBER):
        assert not tools.execute("read_file", {"path": str(target)}).ok


def test_a_url_column_leaves_room_for_every_other_column_word() -> None:
    url = "https://miraiproduct.atlassian.net/wiki/pages/viewpage.action?pageId=" + "4" * 60
    header = "| ID | Profile | Owner | Cost | Runs | Status | Responsibility | Source |\n" + "|---" * 8 + "|\n"
    row = f"| 1 | agora | platform | 0.17 | 3 | active | Infrastructure | {url} |\n"
    page = " ".join(_text(_render(header + row))[0].split())
    assert "Responsibility" in page and "Infrastructure" in page


def test_many_long_columns_never_get_a_cell_narrower_than_its_padding() -> None:
    url = "https://example.com/" + "a" * 80
    rows = "| " + " | ".join([url] * 14 + ["x"]) + " |\n"
    layout_ = layout.Layout()
    widths_seen = []
    real_lines = layout_._lines

    def spy(frags, width):
        widths_seen.append(width)
        return real_lines(frags, width)

    layout_._lines = spy
    layout_.table([[[layout.Span(c)] for c in rows.strip("|\n").split(" | ")]], 0)
    assert min(widths_seen) > 0
