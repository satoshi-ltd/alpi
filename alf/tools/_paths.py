"""Path sandbox — alf can only touch files inside approved roots.

Two approved roots:

1. **Primary** — one of:
   * The active profile's ``workspace`` from ``config.yaml`` if set
     (e.g. a "work" profile pinned to ``~/git``). Overrides cwd entirely.
   * Otherwise ``os.getcwd()`` at the time of the call — the directory
     the user launched alf from.
2. **Profile home** — ``~/.alf/`` (or ``~/.alf/profiles/<name>/``). alf
   *must* be able to inspect/edit its own skills, memories and configs.

Anything outside both roots is rejected. To work on a different project
directory, either configure ``workspace`` in the profile or relaunch
alf from the target directory.

Usage::

    from alf.tools._paths import check_path

    def run(self, path: str, ...):
        try:
            p = check_path(path)
        except ValueError as e:
            return ToolResult(ok=False, output="", error=str(e))
        # p is now an absolute, resolved Path inside an allowed root.

Rules:
- ``~`` expands.
- Relative paths resolve against ``os.getcwd()`` at the time of the call.
- Symlinks are followed (``Path.resolve()``).
"""

from __future__ import annotations

from pathlib import Path


def _allowed_roots() -> list[Path]:
    """Approved roots, resolved. Profile workspace (or cwd) + profile home."""
    from alf.home import get_home
    alf_home = get_home().resolve()

    # Primary root: profile.workspace if configured, else cwd.
    primary: Path
    try:
        from alf import config as cfg_mod
        cfg = cfg_mod.load(alf_home)
        wp = cfg.workspace_path
    except Exception:
        wp = None
    primary = wp if wp is not None else Path.cwd().resolve()

    roots = [primary]
    if alf_home != primary:
        roots.append(alf_home)
    return roots


def check_path(path: str) -> Path:
    """Return the resolved Path if inside an allowed root; else ValueError."""
    roots = _allowed_roots()
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    resolved = p.resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return resolved
        except ValueError:
            continue
    root_list = ", ".join(str(r) for r in roots)
    raise ValueError(
        f"path escapes allowed roots ({root_list}): {path}. "
        f"Relaunch alf from the target directory if you need to work there."
    )


# Backwards-compat alias — older call sites may still import this name.
check_in_cwd = check_path
