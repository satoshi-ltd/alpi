"""Textual-based TUI for alpi — mother.py-inspired minimal chat layout."""

from alpi.tui._links import install as _install_link_style
from alpi.tui.app import AlpiApp

_install_link_style()

__all__ = ["AlpiApp"]
