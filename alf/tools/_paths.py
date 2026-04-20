"""Path sandbox — alf can only touch files inside approved roots."""

from __future__ import annotations

from pathlib import Path


def _allowed_roots() -> list[Path]:
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
