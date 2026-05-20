"""Floating panels for /model — provider + model picker.

Inline `/model` only switches among providers already configured (API key
set) and known models from those providers. Adding new providers / keys
happens via `alpi setup`, never inline. If nothing is configured we point
the user there.
"""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from alpi import config as cfg_mod
from alpi import providers as prov_mod
from alpi.providers.base import Provider
from alpi.tui.screens import FloatingPanel


_OPTION_LIST_CSS = """
OptionList {
    background: transparent !important;
    margin: 0;
    max-height: 18;
}
"""


class ProviderPanel(FloatingPanel):
    panel_title = "/model · provider"
    DEFAULT_CSS = _OPTION_LIST_CSS

    def __init__(self, cfg: cfg_mod.Config, home: Path) -> None:
        super().__init__()
        self.cfg = cfg
        self.home = home
        self._providers: dict[str, Provider] = {}
        self._active_idx: int | None = None

    def compose_body(self) -> ComposeResult:
        options = self._build_options()
        if not options:
            yield Static(
                "No providers configured yet. Run `alpi setup` from the "
                "shell to add one (API key or Ollama server). /model "
                "here only switches between providers already set up.",
                classes="entry-desc",
            )
            return
        yield OptionList(*options, id="provider-options", compact=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self._focus)

    def _focus(self) -> None:
        if not self.is_mounted:
            return
        try:
            olist = self.query_one(OptionList)
        except Exception:  # noqa: BLE001
            return
        if self._active_idx is not None:
            olist.highlighted = self._active_idx
        olist.focus()

    def _build_options(self) -> list[Option]:
        from alpi.home import effective_profile_env
        from alpi.tui.list_row import build_options

        env = effective_profile_env(self.cfg.home)
        active_head = self.cfg.model.split("/", 1)[0]
        items: list[tuple[str, str, str]] = []

        or_models = (
            self.cfg.providers.get("openrouter", {}).get("models", []) or []
        )
        for p in prov_mod.builtin():
            if p.api_key_env and not p.has_key(env):
                continue
            # OpenRouter is usable only once the user has registered at
            # least one model id via `alpi setup` — we don't fetch the
            # catalog. Without models, skip it here.
            if p.name == "openrouter" and not or_models:
                continue
            self._providers[p.name] = p
            items.append((p.name, p.display, p.description))

        for p in prov_mod.ollama(self.cfg.providers.get("ollama", [])):
            self._providers[p.name] = p
            items.append((p.name, p.name, p.url))

        accent = self.app.theme_variables.get("accent")
        options = build_options(items, active_key=active_head, accent=accent)
        for idx, item in enumerate(items):
            if item[0] == active_head:
                self._active_idx = idx
                break
        return options

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_id:
            return
        provider = self._providers.get(event.option_id)
        if provider is None:
            return
        self.app._show_panel(ModelListPanel(provider, self.cfg, self.home))


class ModelListPanel(FloatingPanel):
    DEFAULT_CSS = _OPTION_LIST_CSS

    def __init__(self, provider: Provider, cfg: cfg_mod.Config, home: Path) -> None:
        super().__init__()
        self.provider = provider
        self.cfg = cfg
        self.home = home
        self._model_ids: dict[str, str] = {}
        self._active_idx: int | None = None
        self.panel_title = f"/model · {provider.display}"

    def compose_body(self) -> ComposeResult:
        yield Static("Fetching models…", id="fetch-status")
        yield OptionList(id="model-options", compact=True)

    def on_mount(self) -> None:
        self.call_after_refresh(self._load_models)

    def _load_models(self) -> None:
        from alpi.tui.list_row import build_options

        # `call_after_refresh` can fire after dismiss; bail quietly.
        if not self.is_mounted:
            return

        error = self.app.theme_variables.get("error", "red")
        try:
            models = self.provider.list_models()
        except Exception as e:  # noqa: BLE001
            try:
                status = self.query_one("#fetch-status", Static)
            except Exception:  # noqa: BLE001
                return
            err = Text()
            err.append("failed to load models: ", style=error)
            err.append(str(e), style=error)
            status.update(err)
            return

        try:
            olist = self.query_one("#model-options", OptionList)
        except Exception:  # noqa: BLE001
            return
        active = self.cfg.model
        accent = self.app.theme_variables.get("accent")

        items: list[tuple[str, str, str]] = []
        for i, m in enumerate(models):
            opt_id = f"m{i}"
            self._model_ids[opt_id] = m.id
            items.append((opt_id, m.display, m.note or ""))
            if m.id == active:
                self._active_idx = i

        active_opt_id = next(
            (opt_id for opt_id, mid in self._model_ids.items() if mid == active),
            None,
        )
        for opt in build_options(items, active_key=active_opt_id, accent=accent):
            olist.add_option(opt)

        self.query_one("#fetch-status", Static).display = False
        if self._active_idx is not None:
            olist.highlighted = self._active_idx
        olist.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_id:
            return
        model_id = self._model_ids.get(event.option_id)
        if not model_id:
            return
        # Session-only switch: update memory only; do not persist.
        self.cfg.model = model_id
        app = self.app
        app.cfg = self.cfg                            # type: ignore[attr-defined]
        app.engine.cfg = self.cfg                     # type: ignore[attr-defined]
        app.engine.session.model = self.cfg.model     # type: ignore[attr-defined]
        app._update_header()                           # type: ignore[attr-defined]
        app._dismiss_panels()                          # type: ignore[attr-defined]
        from alpi.tui.widgets import DimLine
        app._mount_message(DimLine(                    # type: ignore[attr-defined]
            f"(model set to {model_id} for this session)"
        ))
