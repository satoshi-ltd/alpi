"""ask_user — closed-question primitive (UX.1).

Use when the next step depends on a discrete choice the user must make
between 2-4 realistic options. Owned clients (desktop / mobile) render
native choice UI; the TUI prompts inline; headless/scheduled runs get a
graceful fallback string.
"""

from __future__ import annotations

import os
from typing import Any

from alpi.tools import _clarification
from alpi.tools.base import Tool, ToolResult


# Scheduled / unattended platforms have no live user and no paired client; the tool must NOT reach the handler (would block on stdin / wait 5 min for nobody) and returns a graceful fallback instead.
_HEADLESS_PLATFORMS = frozenset({"cron"})

_MIN_CHOICES = 2
_MAX_CHOICES_SINGLE = 4
_MAX_CHOICES_MULTI = 8


def _platform() -> str:
    return (os.environ.get("ALPI_PLATFORM") or "").strip().lower()


def _is_headless() -> bool:
    return _platform() in _HEADLESS_PLATFORMS


def _normalize_choices(
    choices: Any, multi: bool = False
) -> tuple[list[dict[str, str]] | None, str | None]:
    if not isinstance(choices, list):
        return None, "choices must be a list of {label, description?} objects"
    max_choices = _MAX_CHOICES_MULTI if multi else _MAX_CHOICES_SINGLE
    if len(choices) < _MIN_CHOICES or len(choices) > max_choices:
        return None, f"choices must contain {_MIN_CHOICES}-{max_choices} items"
    out: list[dict[str, str]] = []
    seen_labels: set[str] = set()
    for raw in choices:
        if not isinstance(raw, dict):
            return None, "each choice must be an object with a 'label'"
        label = str(raw.get("label") or "").strip()
        if not label:
            return None, "every choice needs a non-empty 'label'"
        if label in seen_labels:
            return None, f"duplicate choice label: {label!r}"
        seen_labels.add(label)
        desc = raw.get("description")
        item: dict[str, str] = {"label": label}
        if isinstance(desc, str) and desc.strip():
            item["description"] = desc.strip()
        out.append(item)
    return out, None


class AskUser(Tool):
    name = "ask_user"
    description = (
        "Ask the user to pick from a small set of discrete choices "
        "(2-4 for single-select, 2-8 for ``multi=True``). Desktop and "
        "mobile render native buttons; the TUI prompts inline.\n"
        "\n"
        "Use when:\n"
        " - the next step depends on a real preference (which account, "
        "which destination, how to resolve a conflict);\n"
        " - you can enumerate the realistic options (2-4, or up to 8 "
        "when ``multi=True``);\n"
        " - the user has not already given you the answer.\n"
        "\n"
        "Do NOT use for open-ended questions ('tell me more', "
        "'what do you think'), for brainstorming, or when you can just "
        "ask in prose. ``allow_other=True`` (the default) lets the user "
        "type a custom answer when none of your choices fit. "
        "``multi=True`` lets the user pick more than one option — "
        "owned clients render checkboxes; the returned string is the "
        "chosen labels joined by ``\", \"`` (ignores ``allow_other``).\n"
        "\n"
        "The tool returns a single string describing the user's choice "
        "(e.g. ``WHOOP``, ``Sleep summary, Training load``, "
        "``No response received before timeout.``). Treat that string "
        "as authoritative for the rest of the turn."
    )
    parameters = {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question to ask. One sentence; no trailing prompt — the UI/CLI already implies 'please pick'.",
            },
            "choices": {
                "type": "array",
                "minItems": _MIN_CHOICES,
                "maxItems": _MAX_CHOICES_MULTI,
                "items": {
                    "type": "object",
                    "properties": {
                        "label": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["label"],
                },
                "description": "2-4 options for single-select, 2-8 when ``multi=True``. Each has a short ``label`` (required, used as the on-screen button) and an optional ``description`` (one-line context). Labels must be unique.",
            },
            "allow_other": {
                "type": "boolean",
                "default": True,
                "description": "Whether to surface an 'Other' escape hatch so the user can type a free-form answer. Ignored when ``multi=True``. Default True.",
            },
            "multi": {
                "type": "boolean",
                "default": False,
                "description": "Allow the user to pick more than one option. Owned clients render checkboxes + an explicit Continue button. When True, ``allow_other`` is treated as False. The tool returns the chosen labels joined by ``\", \"`` in the order the user picked.",
            },
        },
        "required": ["question", "choices"],
    }

    def run(
        self,
        question: str = "",
        choices: Any = None,
        allow_other: bool = True,
        multi: bool = False,
    ) -> ToolResult:
        q = str(question or "").strip()
        if not q:
            return ToolResult(ok=False, output="", error="question is required")
        multi_bool = bool(multi)
        normalised, err = _normalize_choices(choices, multi=multi_bool)
        if err is not None or normalised is None:
            return ToolResult(ok=False, output="", error=err or "invalid choices")
        # Multi-select + free-text is a UX trap; force the escape hatch off.
        allow_other_bool = False if multi_bool else bool(allow_other)
        if _is_headless():
            return ToolResult(
                ok=True,
                output=(
                    "This run has no live user; ``ask_user`` cannot be used "
                    "from scheduled / headless jobs (ALPI_PLATFORM="
                    f"{_platform()!r}). Continue with a safe default or "
                    "report that user input is required."
                ),
            )
        handler = _clarification.get_handler()
        if handler is None:
            return ToolResult(
                ok=True,
                output=(
                    "No user-facing surface accepted the question; ask the "
                    "user plainly in your reply instead of using ``ask_user``."
                ),
            )
        try:
            answer = handler(q, normalised, allow_other_bool, multi_bool)
        except Exception as e:  # noqa: BLE001
            return ToolResult(
                ok=True,
                output=f"Clarification handler failed: {e}. Ask the user plainly.",
            )
        if not isinstance(answer, str) or not answer.strip():
            return ToolResult(ok=True, output="No response received before timeout.")
        return ToolResult(ok=True, output=answer.strip())


TOOL = AskUser
