"""Native Textual screens for picking provider + model."""

from __future__ import annotations

from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option

from alf import config as cfg_mod
from alf import providers as prov_mod
from alf.providers.base import Provider


class ProviderScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "cancel")]

    def __init__(self, cfg: cfg_mod.Config, home: Path) -> None:
        super().__init__()
        self.cfg = cfg
        self.home = home
        # Map option id -> Provider so selection is lossless.
        self._providers: dict[str, Provider] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("Select provider", classes="modal-title")
            yield OptionList(*self._build_options(), id="provider-options")
            yield Static(
                "↑↓ navigate  ENTER select  ESC cancel",
                classes="modal-hint",
            )

    def _build_options(self) -> list[Option]:
        active_head = self.cfg.model.split("/", 1)[0]
        tv = self.app.theme_variables
        muted = tv.get("text-muted", "")
        success = tv.get("success", "green")
        options: list[Option] = []

        for p in prov_mod.builtin():
            self._providers[p.name] = p
            label = Text()
            label.append(f"{p.display:<14}", style="bold")
            label.append("  ")
            label.append(p.description, style=muted)
            if p.name == active_head:
                label.append("  ")
                label.append("← active", style=success)
            if p.api_key_env and not p.has_key():
                label.append("  ")
                label.append("(key needed)", style=muted)
            options.append(Option(label, id=p.name))

        customs = prov_mod.custom(self.cfg.providers.get("custom", []))
        if customs:
            options.append(Option(
                Text("── custom endpoints ──", style=muted),
                disabled=True,
            ))
            for p in customs:
                self._providers[p.name] = p
                label = Text(p.display)
                if p.name == active_head:
                    label.append("  ")
                    label.append("← active", style=success)
                options.append(Option(label, id=p.name))

        return options

    def on_mount(self) -> None:
        self.query_one(OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_id:
            return
        provider = self._providers.get(event.option_id)
        if provider is None:
            return

        if provider.api_key_env and not provider.has_key():
            self.app.push_screen(
                _ApiKeyScreen(provider.display, provider.api_key_env),
                lambda value: self._after_key(provider, value),
            )
            return

        self.app.push_screen(ModelListScreen(provider, self.cfg, self.home))

    def _after_key(self, provider: Provider, value: str | None) -> None:
        if not value:
            return
        _save_key_to_env(self.home / ".env", provider.api_key_env, value)
        import os
        os.environ[provider.api_key_env] = value
        self.app.push_screen(ModelListScreen(provider, self.cfg, self.home))


class ModelListScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "back")]

    def __init__(self, provider: Provider, cfg: cfg_mod.Config, home: Path) -> None:
        super().__init__()
        self.provider = provider
        self.cfg = cfg
        self.home = home
        self._model_ids: dict[str, str] = {}  # opt_id -> litellm model id

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                Text.from_markup(f"Select model  ({self.provider.display})"),
                classes="modal-title",
            )
            yield Static("Fetching models…", id="fetch-status", classes="modal-hint")
            yield OptionList(id="model-options")
            yield Static(
                "↑↓ navigate  ENTER select  ESC back",
                classes="modal-hint",
            )

    def on_mount(self) -> None:
        self._load_models()

    def _load_models(self) -> None:
        tv = self.app.theme_variables
        error = tv.get("error", "red")
        success = tv.get("success", "green")
        muted = tv.get("text-muted", "")
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
                label.append(m.note, style=muted)
            if m.id == active:
                label.append("  ")
                label.append("← active", style=success)
            olist.add_option(Option(label, id=opt_id))

        try:
            self.query_one("#fetch-status", Static).display = False
        except Exception:
            pass
        olist.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if not event.option_id:
            return
        model_id = self._model_ids.get(event.option_id)
        if not model_id:
            return
        self.cfg.model = model_id
        cfg_mod.save(self.cfg)
        try:
            self.app.engine.cfg = self.cfg  # type: ignore[attr-defined]
            self.app.engine.session.model = self.cfg.model  # type: ignore[attr-defined]
            self.app._update_header()  # type: ignore[attr-defined]
        except Exception:
            pass
        # Close this screen AND the provider screen behind it.
        self.dismiss()
        try:
            self.app.pop_screen()
        except Exception:
            pass


class _ApiKeyScreen(ModalScreen[str]):
    BINDINGS = [Binding("escape", "dismiss", "cancel")]

    def __init__(self, provider_display: str, env_name: str) -> None:
        super().__init__()
        self.provider_display = provider_display
        self.env_name = env_name

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(
                Text.from_markup(f"[b]{self.provider_display}[/b] needs an API key"),
                classes="modal-title",
            )
            yield Static(
                Text.from_markup(
                    f"Paste the value for [b]{self.env_name}[/b]. "
                    "Saved to ~/.alf/.env."
                ),
            )
            yield Input(password=True, id="key-input")
            yield Static(
                "ENTER save  ESC cancel",
                classes="modal-hint",
            )

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        value = (event.value or "").strip()
        self.dismiss(value or None)


def _save_key_to_env(env_path: Path, key: str, value: str) -> None:
    lines = env_path.read_text().splitlines() if env_path.exists() else []
    out: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith(f"{key}="):
            out.append(f"{key}={value}")
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(out) + "\n")
