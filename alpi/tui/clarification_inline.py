"""Inline (stdin/stdout) clarification handler for the ``alpi chat --once`` path.

The full Textual ``AlpiApp`` registers its own handler that pops a panel;
this module is the simpler surface for non-Textual CLI runs where there is
just a terminal. Either path satisfies the ``ask_user`` tool contract.
"""

from __future__ import annotations

import sys
from typing import Any


def _format(
    question: str,
    choices: list[dict[str, Any]],
    allow_other: bool,
    multi: bool,
) -> list[str]:
    lines = ["", question.strip(), ""]
    for i, c in enumerate(choices, start=1):
        desc = c.get("description")
        if desc:
            lines.append(f"  {i}. {c['label']} — {desc}")
        else:
            lines.append(f"  {i}. {c['label']}")
    if allow_other and not multi:
        lines.append(f"  {len(choices) + 1}. Other (type your own answer)")
    lines.append("")
    return lines


def _resolve_multi(raw: str, choices: list[dict[str, Any]]) -> str:
    """Parse a comma-separated list of numbers and/or labels into a deduped, order-preserving label string. Empty string on no valid selections."""
    picked: list[str] = []
    label_lookup = {c["label"].lower(): c["label"] for c in choices}
    for tok in (t.strip() for t in raw.split(",")):
        if not tok:
            continue
        if tok.isdigit():
            idx = int(tok)
            if 1 <= idx <= len(choices):
                lab = choices[idx - 1]["label"]
                if lab not in picked:
                    picked.append(lab)
            continue
        resolved = label_lookup.get(tok.lower())
        if resolved and resolved not in picked:
            picked.append(resolved)
    return ", ".join(picked)


def inline_handler(
    question: str,
    choices: list[dict[str, Any]],
    allow_other: bool,
    multi: bool = False,
) -> str:
    """Render the prompt to ``stderr`` (so it never collides with ``--emit-events`` JSON on stdout) and read the answer from stdin. Returns the resolved label or free text; empty string on EOF / Ctrl-D / empty input so the tool surfaces a graceful 'no response' to the model. When ``multi`` is True the prompt asks for comma-separated picks and returns the labels joined by ``", "``."""
    out_lines = _format(question, choices, allow_other, multi)
    upper_bound = len(choices) + (1 if allow_other and not multi else 0)
    sys.stderr.write("\n".join(out_lines) + "\n")
    sys.stderr.flush()

    if multi:
        while True:
            try:
                sys.stderr.write("Choices (comma-separated numbers or labels): ")
                sys.stderr.flush()
                raw = sys.stdin.readline()
            except KeyboardInterrupt:
                return ""
            if not raw:
                return ""
            answer = raw.strip()
            if not answer:
                return ""
            resolved = _resolve_multi(answer, choices)
            if resolved:
                return resolved
            sys.stderr.write(
                "No valid picks recognised. Use the numbers shown or the "
                "labels exactly; separate with commas.\n",
            )

    while True:
        try:
            sys.stderr.write("Choice (number or text): ")
            sys.stderr.flush()
            raw = sys.stdin.readline()
        except KeyboardInterrupt:
            return ""
        if not raw:
            return ""
        answer = raw.strip()
        if not answer:
            return ""
        if answer.isdigit():
            idx = int(answer)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]["label"]
            if allow_other and idx == upper_bound:
                sys.stderr.write("Type your answer: ")
                sys.stderr.flush()
                try:
                    custom = sys.stdin.readline()
                except KeyboardInterrupt:
                    return ""
                custom = (custom or "").strip()
                return custom or ""
            sys.stderr.write(
                f"Out of range. Pick 1-{upper_bound} or type a choice label.\n"
            )
            continue
        for c in choices:
            if c["label"].lower() == answer.lower():
                return c["label"]
        if allow_other:
            return answer
        sys.stderr.write("Unknown choice. Pick a number or a listed label.\n")


__all__ = ["inline_handler"]
