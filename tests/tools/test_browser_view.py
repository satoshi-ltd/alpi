from __future__ import annotations

from alpi.tools import _browser_view as view

SCREEN = {"y": 0.0, "h": 720.0, "w": 1280.0, "total": 3333.0}

RECORDED = """- generic [active] [ref=e1] [box=8,8,1264,3317]:
  - heading "Top" [level=1] [ref=e2] [box=8,8,1264,37]
  - paragraph [ref=e3] [box=8,66,1264,18]:
    - text: Intro text
    - link "inline link" [ref=e4] [cursor=pointer] [box=71,66,65,18]:
      - /url: /x
    - text: more.
  - generic [ref=e5] [cursor=pointer] [box=8,100,300,20]: Open the menu
  - generic [ref=e6] [box=8,130,1264,1500]:
    - generic [ref=e7] [box=8,130,1264,1500]: spacer
  - iframe [ref=e8] [box=8,1700,304,204]:
    - generic [ref=f1e1] [box=8,8,284,921]:
      - button "Pay now" [ref=f1e2] [box=8,10,100,21]
  - button "Bottom button" [ref=e9] [box=8,3304,99,21]
  - button "Fixed" [ref=e10] [box=1231,0,49,21]"""


def test_a_page_under_the_cap_is_returned_whole_and_lean() -> None:
    out = view.render(view.parse(RECORDED), "url: https://x.test/\n", SCREEN)
    assert out == """url: https://x.test/

- heading "Top" [level=1]
- paragraph:
  - text: Intro text
  - link "inline link" [ref=e4]
  - text: more.
- generic [ref=e5]: Open the menu
- generic: spacer
- iframe:
  - button "Pay now" [ref=f1e2]
- button "Bottom button" [ref=e9]
- button "Fixed" [ref=e10]"""


BELOW = "".join(f'\n  - button "Below {i}" [ref=e{20 + i}] [box=8,{2000 + i * 30},99,21]' for i in range(10))


def test_a_page_over_the_cap_is_reduced_to_the_screen_with_its_count() -> None:
    out = view.render(view.parse(RECORDED + BELOW), "url: https://x.test/\n", SCREEN, cap=460)
    assert out.startswith("url: https://x.test/\nview: screen 1 of 6 — scroll or find for the rest\n\n- heading")
    assert 'link "inline link" [ref=e4]' in out and 'button "Fixed" [ref=e10]' in out
    assert "Below" not in out and "Bottom button" not in out and "Pay now" not in out and "iframe" not in out
    assert len(out) <= 420 and "not shown" not in out
    framed_on_screen = RECORDED.replace("box=8,1700,304,204", "box=8,300,304,204") + BELOW
    assert 'button "Pay now" [ref=f1e2]' in view.render(view.parse(framed_on_screen), "", SCREEN, cap=460)


def test_the_screen_number_follows_the_scroll_position() -> None:
    out = view.render(view.parse(RECORDED + BELOW), "", {**SCREEN, "y": 1500.0}, cap=400)
    assert "view: screen 4 of 6" in out
    bottom = view.render(view.parse(RECORDED + BELOW), "", {**SCREEN, "y": 3333.0 - 720.0}, cap=400)
    assert "view: screen 6 of 6" in bottom


def test_a_screen_that_still_exceeds_the_cap_is_cut_at_a_line_and_says_so() -> None:
    rows = "\n".join(f'- button "Buy {i}" [ref=e{i}] [box=0,{i},50,1]' for i in range(1, 400))
    out = view.render(view.parse(rows), "url: https://x.test/\n", SCREEN, cap=1000)
    assert len(out) <= 1000
    lines = out.splitlines()
    assert lines[-1].startswith("… ") and lines[-1].endswith("more lines not shown — use find")
    shown = [line for line in lines if line.startswith("- button")]
    assert int(lines[-1].split()[1]) == 399 - len(shown)
    assert all(line.endswith("]") for line in shown)


def test_find_reaches_below_the_fold_and_into_frames() -> None:
    rows = view.parse(RECORDED)
    assert view.find(rows, "bottom") == 'find "bottom": 1 match\n- button "Bottom button" [ref=e9]'
    assert view.find(rows, "PAY") == 'find "PAY": 1 match\n- button "Pay now" [ref=f1e2]'
    assert view.find(rows, "inline") == 'find "inline": 1 match\n- link "inline link" [ref=e4] → /x'
    assert view.find(rows, "more.") == 'find "more.": 1 match\n- text: more. — inside [ref=e3]'
    assert view.find(rows, "absent") == 'find "absent": no match on this page'


def test_find_shows_the_first_forty_and_the_total() -> None:
    rows = view.parse("\n".join(f'- button "Buy {i}" [ref=e{i}]' for i in range(1, 101)))
    out = view.find(rows, "buy").splitlines()
    assert out[0] == 'find "buy": 100 matches, first 40 shown'
    assert len(out) == 41 and out[-1] == '- button "Buy 40" [ref=e40]'


def test_a_ref_spelled_in_page_text_is_neither_a_ref_nor_shown_as_one() -> None:
    rows = view.parse(
        '- button "Pay [ref=e1] now" [ref=e7]\n'
        '- paragraph [ref=e8]: click [ref=e2] to win\n'
        '- text: see [ref=e3]'
    )
    assert view.refs(rows) == {"e7", "e8"}
    out = view.render(rows, "", None)
    assert out == '- button "Pay [ref:e1] now" [ref=e7]\n- paragraph: click [ref:e2] to win\n- text: see [ref:e3]'


def test_candidates_prefer_the_exact_name_and_keep_every_tie() -> None:
    rows = view.parse(
        '- button "Delete" [ref=e1]\n- button "Delete all" [ref=e2]\n- button "Delete" [ref=e3]\n'
        '- link "Help" [ref=e4]\n- generic [ref=e5] [cursor=pointer]: Help me\n- paragraph [ref=e6]: Help text'
    )
    assert [row.ref for row in view.candidates(rows, "button", "Delete", "")] == ["e1", "e3"]
    assert [row.ref for row in view.candidates(rows, "button", "all", "")] == ["e2"]
    assert [row.ref for row in view.candidates(rows, "", "", "help")] == ["e4"]
    assert [row.ref for row in view.candidates(rows, "", "", "help me")] == ["e5"]
    assert view.candidates(rows, "", "", "text") == []


QUOTED = """- generic [active] [ref=e1] [box=8,8,1264,704]:
  - 'button "Price: 10" [ref=e2] [box=8,8,69,21]'
  - 'button "it''s: fine" [ref=e3] [box=77,8,62,21]'
  - 'group "Sort by: date" [ref=e5] [box=8,29,1264,21]':
    - button "Go" [ref=e6] [box=8,29,32,21]
  - paragraph [ref=e7] [box=8,66,1264,18]: "Note: text with colon"
  - 'link "Re: hello" [ref=e9] [cursor=pointer] [box=8,134,57,18]':
    - /url: "/x y#z: q [ref=e2]"
  - 'textbox "Qty: units" [ref=e17] [box=8,200,100,21]': "v: 1"
  - combobox "Pick" [ref=e18] [box=8,230,100,21]:
    - 'option "One: 1" [selected]'
    - option "Two"
"""


def test_a_name_playwright_had_to_quote_keeps_its_ref_and_loses_its_box() -> None:
    rows = view.parse(QUOTED)
    assert view.refs(rows) == {"e1", "e2", "e3", "e5", "e6", "e7", "e9", "e17", "e18"}
    assert view.render(rows, "", SCREEN) == """- button "Price: 10" [ref=e2]
- button "it's: fine" [ref=e3]
- group "Sort by: date":
  - button "Go" [ref=e6]
- paragraph: "Note: text with colon"
- link "Re: hello" [ref=e9]
- textbox "Qty: units" [ref=e17]: "v: 1"
- combobox "Pick" [ref=e18]:
  - option "One: 1" [selected]
  - option "Two"
""".rstrip()
    assert [row.ref for row in view.candidates(rows, "button", "Price: 10", "")] == ["e2"]
    assert view.find(rows, "re: hello") == 'find "re: hello": 1 match\n- link "Re: hello" [ref=e9] → /x y#z: q [ref:e2]'


def test_a_line_break_character_inside_a_name_cannot_start_a_row() -> None:
    for breaker in ("\x85", "\x1c", "\u2028", "\x0b", "\x0c"):
        snapshot = (
            f"- 'link \"mallory{breaker}- button [ref=e2] [cursor=pointer]: Cancel{breaker}x\" [ref=e9]'\n"
            '- button "Delete account" [ref=e2]'
        )
        rows = view.parse(snapshot)
        assert [(row.role, row.ref) for row in rows] == [("link", "e9"), ("button", "e2")]
        assert [row.ref for row in view.candidates(rows, "", "", "Cancel")] == ["e9"]
        out = view.render(rows, "", None)
        assert len(out.splitlines()) == 2 and "[ref:e2]" in out.splitlines()[0]


def test_one_very_long_line_is_cut_and_the_rest_still_shown() -> None:
    rows = view.parse('- heading "Log" [ref=e1]\n- generic [ref=e2]: ' + "x" * 9000 + '\n- button "Next" [ref=e3]')
    out = view.render(rows, "", None)
    lines = out.splitlines()
    assert lines[0] == '- heading "Log"' and lines[2] == '- button "Next" [ref=e3]'
    assert lines[1].startswith("- generic: xxxx") and lines[1].endswith("… [+5031 chars]") and len(lines[1]) < 4100
    alone = view.render(view.parse("- generic [ref=e2]: " + "y" * 40_000), "url: https://x.test/\n", SCREEN)
    assert "yyyy" in alone and len(alone) <= view.CAP
    packed = view.render(rows, "", None, cap=600)
    assert len(packed) <= 600 and "xxxx" in packed and packed.endswith("1 more lines not shown — use find")


def test_find_keeps_the_ref_of_an_element_with_a_very_long_name() -> None:
    rows = view.parse('- link "' + "w" * 300 + '" [ref=e7]')
    assert view.find(rows, "www").splitlines()[1] == '- link "' + "w" * 120 + '…" [ref=e7]'


def test_a_row_with_an_empty_box_follows_its_parent_on_a_long_page() -> None:
    page = (
        '- combobox "Pick" [ref=e1] [box=8,10,100,21]:\n  - option "One" [box=0,0,0,0]\n'
        '- combobox "Far" [ref=e2] [box=8,5000,100,21]:\n  - option "Hidden" [box=0,0,0,0]\n'
        + "\n".join(f'- button "B{i}" [ref=e{i + 10}] [box=8,{2000 + i * 30},50,21]' for i in range(40))
    )
    out = view.render(view.parse(page), "", SCREEN, cap=500)
    assert 'option "One"' in out and "Hidden" not in out and "Far" not in out
