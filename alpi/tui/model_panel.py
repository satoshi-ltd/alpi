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
        try:
            olist = self.query_one(OptionList)
        except Exception:
            return
        if self._active_idx is not None:
            olist.highlighted = self._active_idx
        olist.focus()

    def _build_options(self) -> list[Option]:
        active_head = self.cfg.model.split("/", 1)[0]
        options: list[Option] = []

        or_models = (
            self.cfg.providers.get("openrouter", {}).get("models", []) or []
        )
        for p in prov_mod.builtin():
            if p.api_key_env and not p.has_key():
                continue
            # OpenRouter is usable only once the user has registered at
            # least one model id via `alpi setup` — we don't fetch the
            # catalog. Without models, skip it here.
            if p.name == "openrouter" and not or_models:
                continue
            self._providers[p.name] = p
            label = Text()
            label.append(f"{p.display:<14}", style="bold")
            label.append("  ")
            label.append(p.description)
            if p.name == active_head:
                self._active_idx = len(options)
            options.append(Option(label, id=p.name))

        for p in prov_mod.ollama(self.cfg.providers.get("ollama", [])):
            self._providers[p.name] = p
            label = Text()
            label.append(f"{p.name:<14}", style="bold")
            label.append("  ")
            label.append(p.url)
            if p.name == active_head:
                self._active_idx = len(options)
            options.append(Option(label, id=p.name))

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
        error = self.app.theme_variables.get("error", "red")
        try:
            models = self.provider.list_models()
        except Exception as e:  # noqa: BLE001
            status = self.query_one("#fetch-status", Static)
            err = Text()
            err.append("failed to load models: ", style=error)
            err.append(str(e), style=error)
            status.update(err)
            return

        olist = self.query_one("#model-options", OptionList)
        active = self.cfg.model
        for i, m in enumerate(models):
            opt_id = f"m{i}"
            self._model_ids[opt_id] = m.id
            label = Text()
            label.append(m.display, style="bold")
            if m.note:
                label.append("  ")
                label.append(m.note)
            if m.id == active:
                self._active_idx = i
            olist.add_option(Option(label, id=opt_id))

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
        # Session-only switch: update in-memory cfg + engine, do NOT persist
        # to config.yaml. The saved default only changes via `alpi setup`.
        # `/new` reloads cfg from disk, so the switch also resets there.
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
