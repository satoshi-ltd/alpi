"""Path resolution + sensitive-path denylist shared by file tools."""

from __future__ import annotations

import fnmatch
import json
import os
import re
from pathlib import Path


_SENSITIVE_PATH_PREFIXES: tuple[str, ...] = (
    "/etc/", "/boot/", "/sys/", "/proc/",
    "/usr/lib/systemd/", "/System/",
    "/private/etc/",
)

_SENSITIVE_EXACT_PATHS: frozenset[str] = frozenset({
    "/var/run/docker.sock",
    "/run/docker.sock",
})

_SENSITIVE_PATH_REGEX: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?:^|/)\.ssh/(?:id_|.*_key$|.*_ed25519$)", re.I),
    re.compile(r"(?:^|/)\.ssh/authorized_keys$", re.I),
    re.compile(r"\.(?:pem|p12|pfx)$", re.I),
    re.compile(r"(?:^|/)\.aws/(?:credentials|config)$", re.I),
    re.compile(r"(?:^|/)\.gnupg/", re.I),
    re.compile(r"(?:^|/)\.(?:netrc|npmrc|pypirc|pgpass|sentryclirc)$", re.I),
    re.compile(r"(?:^|/)\.config/(?:gh|gcloud)/", re.I),
    # Shell rc / login files and launchd plists — persistence write vectors.
    re.compile(r"(?:^|/)\.(?:bashrc|zshrc|bash_profile|zprofile|zlogin|profile)$", re.I),
    re.compile(r"(?:^|/)Library/Launch(?:Agents|Daemons)/", re.I),
    # Profile secrets and config must only be edited by hand or setup.
    re.compile(r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/config\.yaml$", re.I),
    # .env* blocked except .env.example/.sample/.template/.dist
    re.compile(r"(?:^|/)\.env(?!\.(?:example|sample|template|dist)$)[^/]*$", re.I),
    # Skill secrets dir (mode 0700, scanner-skipped) — never via file tools.
    re.compile(r"(?:^|/)skills/(?:\.archive/)?[^/]+/[^/]+/secrets/", re.I),
)


# Off-limits to members for READ as well as write — reading host/ would leak an admin token and escalate.
_MEMBER_HOME_AREA: frozenset[str] = frozenset({
    "host", "secrets", "gateway", "cache", "logs", "outputs", "out",
    "sessions", "memories", "schedule", "skills", "alp", "runs", "mentions", "run", "browser", "recipes",
})
_MEMBER_HOME_FILE_PREFIXES = ("knowledge.sqlite", "config.yaml")
_MEMBER_HOME_REGEX = re.compile(
    r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/(" + "|".join(sorted(_MEMBER_HOME_AREA)) + r")(?:/|$)",
    re.IGNORECASE,
)
_ALP_SECRETS_RE = re.compile(r"(?:^|/)alp/secrets(?:/|$)", re.IGNORECASE)


def _profile_homes() -> list[str]:
    from alpi.home import alpi_root, get_home
    root = alpi_root()
    homes = [root, get_home()]
    try:
        homes += [p for p in (root / "profiles").iterdir() if p.is_dir()]
    except OSError:
        pass
    forms: list[str] = []
    for home in homes:
        for form in (home.absolute(), home.resolve()):
            forms.append(str(form).lower().rstrip("/"))
    return list(dict.fromkeys(forms))


def _area_of(parts: list[str]) -> str | None:
    if not parts:
        return None
    if parts[0] in _MEMBER_HOME_AREA:
        return parts[0]
    if len(parts) == 1 and parts[0].startswith(_MEMBER_HOME_FILE_PREFIXES):
        return parts[0]
    if parts[0] == "profiles" and len(parts) >= 3:
        return _area_of(parts[2:])
    return None


def _member_home_area(*paths: Path | str) -> str | None:
    for p in paths:
        m = _MEMBER_HOME_REGEX.search(str(p))
        if m:
            return m.group(1).lower()
    homes = _profile_homes()
    for p in paths:
        forms = {str(Path(p).absolute()).lower()}
        try:
            forms.add(str(Path(p).resolve()).lower())
        except OSError:
            pass
        for form in forms:
            for home in homes:
                if form.startswith(home + "/"):
                    area = _area_of(form[len(home) + 1:].split("/"))
                    if area is not None:
                        return area
    return None


_HOME_TAIL_REGEX = re.compile(r"(?:^|/)\.alpi(?:/profiles/[^/]+)?/(.+)$", re.IGNORECASE)
_NO_ACCESS_AREAS = frozenset({"secrets", "host"})
_NO_WRITE_AREAS = frozenset({"schedule", "memories", "logs", "runs", "sessions", "recipes"})
_AREA_OWNER = {"memories": "memory", "schedule": "schedule"}


def _home_parts(path: Path | str) -> list[list[str]]:
    text = str(path)
    found: list[list[str]] = []
    m = _HOME_TAIL_REGEX.search(text)
    if m:
        found.append([part for part in m.group(1).lower().split("/") if part])
    lowered = text.lower()
    for home in _profile_homes():
        if lowered.startswith(home + "/"):
            parts = [part for part in lowered[len(home) + 1:].split("/") if part]
            if parts[:1] == ["profiles"] and len(parts) >= 3:
                parts = parts[2:]
            found.append(parts)
    return found


def _always_private_area(typed: Path | str, resolved: Path | str, *, for_write: bool) -> str | None:
    for form in (typed, resolved):
        for parts in _home_parts(form):
            if not parts:
                continue
            head = parts[0]
            if head == "host":
                if not for_write and parts[1:2] == ["attachments"]:
                    continue
                return head
            if head in _NO_ACCESS_AREAS or parts[:2] == ["alp", "secrets"]:
                return head if head != "alp" else "alp/secrets"
            if head == "browser" and len(parts) == 2 and "state.json" in parts[1]:
                return "browser/state.json"
            if for_write and (head in _NO_WRITE_AREAS or parts[:2] == ["alp", "peers.yaml"]):
                return head if head != "alp" else "alp/peers.yaml"
    return None


def _always_private_error(area: str, path: str, *, for_write: bool) -> str:
    owner = _AREA_OWNER.get(area)
    if owner:
        return (
            f"cannot write {path}: {area}/ is owned by the `{owner}` tool; "
            f"use `{owner}` instead of the file tools"
        )
    verb = "write to" if for_write else "read"
    return f"cannot {verb} {path}: {area} is a daemon-owned area that file tools never touch"


def private_areas_fenced() -> bool:
    from alpi.host.connection_context import current
    from alpi.tools import _policy
    return current().role != "admin" or _policy.fences_private_areas()


def _member_denied_area(p: Path | str, resolved: Path, *, for_write: bool) -> str | None:
    area = _member_home_area(p, resolved)
    if area is None:
        return None
    # Members may READ alp/ (peer mentions, workgroup transcripts) — never the keypair, never on write.
    if area == "alp" and not for_write:
        if not (_ALP_SECRETS_RE.search(str(p)) or _ALP_SECRETS_RE.search(str(resolved))):
            return None
    if area == "out" and _own_out_path(resolved, for_write):
        return None
    if area == "host" and not for_write and _own_upload_path(resolved):
        return None
    return area


def _own_upload_path(resolved: Path) -> bool:
    from alpi.home import get_home
    from alpi.host.attachments_rpc import caller_owns_upload
    from alpi.host.connection_context import current
    from alpi.tools import _state
    # Only a remote device's attachments were checked against their owner when the turn was sent.
    if current().source != "remote" or resolved not in _state.turn_attachment_paths():
        return False
    return caller_owns_upload(get_home().resolve(), resolved)


def _own_out_path(resolved: Path, for_write: bool) -> bool:
    from alpi.home import get_home
    from alpi.tools import _state
    if _member_home_area(resolved) != "out":
        return False
    if _state.is_turn_output(resolved):
        return True
    if not for_write or resolved.exists() or not resolved.is_relative_to(get_home().resolve() / "out"):
        return False
    _state.note_turn_output(resolved)
    return True


def _configured_workspace() -> Path | None:
    from alpi.home import get_home
    from alpi import config as cfg_mod
    try:
        return cfg_mod.load(get_home().resolve()).workspace_path
    except Exception as exc:  # noqa: BLE001
        # A broken config must not silently downgrade the root to cwd.
        raise ValueError(
            f"config failed to load; refusing to resolve the workspace root: {exc}"
        ) from exc


def _workspace_root() -> Path:
    wp = _configured_workspace()
    return wp if wp is not None else Path.cwd().resolve()


DISPATCH_FILE_MUTATION_TOOLS = frozenset({
    "delete_file", "edit_file", "pdf", "write_file",
})

PIPELINE_SIDE_CHANNEL_TOOLS = frozenset({"peer"})

SESSION_HISTORY_TOOLS = frozenset({
    "session_search",
    "session_read",
    "recall_sessions",
    "index_sessions",
})

PEER_HISTORY_TOOLS = SESSION_HISTORY_TOOLS | {"workgroup_search", "index_workgroups"}

PIPELINE_HISTORY_TOOLS = frozenset({
    "memory",
    "session_search",
    "session_read",
    "recall_sessions",
    "index_sessions",
    "workgroup_search",
    "index_workgroups",
})


def docker_scoped_terminal(home: Path | None = None, *, runs: bool = False) -> bool:
    try:
        from alpi import config as cfg_mod
        from alpi.home import get_home
        cfg = cfg_mod.load(home or get_home())
    except Exception:  # noqa: BLE001
        return False
    if cfg.tools.terminal.docker_scoped is not True:
        return False
    if not runs:
        return True
    from alpi.tools._policy import denied_actions, is_denied
    deny = cfg.tools.deny or []
    return not (cfg.tools.terminal.sandbox or is_denied("terminal", deny) or denied_actions("terminal", deny) & {"run", "*"})


def dispatch_tool_denies() -> frozenset[str]:
    raw = os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE")
    denied: set[str] = (
        set(PIPELINE_HISTORY_TOOLS) | set(PIPELINE_SIDE_CHANNEL_TOOLS)
        if os.environ.get("ALPI_WORKGROUP_PIPELINE")
        else set(SESSION_HISTORY_TOOLS) if os.environ.get("ALPI_WORKGROUP_DISPATCH")
        else set()
    )
    if raw is None:
        return frozenset(denied)
    from alpi.runtime import is_docker
    docker = is_docker()
    try:
        scope = json.loads(raw)
        paths = scope.get("paths")
    except (AttributeError, TypeError, json.JSONDecodeError):
        return frozenset(denied | set(DISPATCH_FILE_MUTATION_TOOLS) | ({"terminal"} if docker else set()))
    if not isinstance(paths, list) or not paths:
        denied.update(DISPATCH_FILE_MUTATION_TOOLS)
    elif docker and all(isinstance(p, str) and p for p in paths) and docker_scoped_terminal(runs=True):
        docker = False
    if docker:
        denied.add("terminal")
    return frozenset(denied)


def dispatch_tool_deny_reasons(
    profile_denies: frozenset[str] | set[str] | None = None,
) -> dict[str, str]:
    denied = dispatch_tool_denies()
    if not denied:
        return {}
    raw = os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE")
    try:
        scope = json.loads(raw or "")
        phase = str(scope.get("phase") or "the active phase")
        owner = str(scope.get("owner") or "")
        readable = scope.get("paths") == []
    except (AttributeError, TypeError, json.JSONDecodeError):
        phase, owner, readable = "the active phase", "", False
    profile_denies = frozenset(profile_denies or ())
    terminal_opted_in = readable and "terminal" in denied and docker_scoped_terminal()
    reasons: dict[str, str] = {}
    if not os.environ.get("ALPI_WORKGROUP_PIPELINE"):
        for name in denied & SESSION_HISTORY_TOOLS:
            reasons[name] = (
                "session history is unavailable in workgroup turns: other members' posts steer "
                "this turn, so this profile's other conversations stay out of it. This is a "
                "workgroup boundary, not tools.deny in config.yaml"
            )
        denied = denied - SESSION_HISTORY_TOOLS
    for name in denied:
        if name in PIPELINE_HISTORY_TOOLS:
            phase_reason = (
                "historical profile context is unavailable during pipeline turns; "
                "use only the active workgroup context and declared project inputs"
            )
        elif name in PIPELINE_SIDE_CHANNEL_TOOLS:
            phase_reason = (
                "direct peer messaging is unavailable during pipeline turns; "
                "deliver through workgroup_post on the active workgroup"
            )
        elif name == "terminal" and terminal_opted_in:
            ownership = f"; its declared owner is @{owner}" if owner else ""
            phase_reason = (
                f"terminal in scoped workgroup phase #{phase} in Docker runs only for the "
                f"profile that owns the phase{ownership}; use native file and search tools"
            )
        elif name == "terminal":
            phase_reason = (
                f"terminal is unavailable during scoped workgroup phase #{phase} "
                "in Docker; use native file and search tools. Daemon gates still run"
            )
        else:
            ownership = f"; its declared owner is @{owner}" if owner else ""
            phase_reason = (
                f"tool unavailable in this workgroup turn: #{phase} does not grant "
                f"this profile file authorship{ownership}"
            )
        reasons[name] = (
            f"tool denied for this profile by tools.deny in config.yaml; {phase_reason}. "
            "The phase boundary is an additional restriction"
            if name in profile_denies else
            f"{phase_reason}. This is a temporary pipeline boundary, not tools.deny in config.yaml"
        )
    return reasons


def _is_sensitive(*paths: Path | str) -> str | None:
    # Check both the typed path and the resolved path.
    for p in paths:
        s = str(p)
        if s in _SENSITIVE_EXACT_PATHS:
            return s
        for prefix in _SENSITIVE_PATH_PREFIXES:
            if s.startswith(prefix):
                return prefix
        for rx in _SENSITIVE_PATH_REGEX:
            if rx.search(s):
                return rx.pattern
    return None


def is_sensitive_path(path: Path | str) -> bool:
    """Return whether a typed or resolved path matches the file-tool denylist."""
    typed = Path(path).expanduser()
    try:
        resolved = typed.resolve()
    except OSError:
        resolved = typed
    return _is_sensitive(typed, resolved) is not None


def is_read_denied(path: Path | str) -> bool:
    typed = Path(path).expanduser()
    try:
        resolved = typed.resolve()
    except OSError:
        resolved = typed
    if _is_sensitive(typed, resolved) is not None:
        return True
    if _always_private_area(typed, resolved, for_write=False) is not None:
        return True
    return private_areas_fenced() and _member_denied_area(typed, resolved, for_write=False) is not None


def resolve_path(path: str, *, for_write: bool = False) -> Path:
    """Expand + resolve a path and refuse sensitive system locations.

    Relative paths root at the active workspace (matches the path rule
    in the system prompt). No workspace sandbox — reads and writes can
    reach anywhere on disk except the entries in the sensitive lists.
    Member file tools are also fenced out of the home private area, except
    read-only alp/ transcripts.
    """
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = _workspace_root() / p
    resolved = p.resolve()
    hit = _is_sensitive(p, resolved)
    if hit is not None:
        raise ValueError(f"refusing to touch sensitive path: {path}")
    from alpi.tools import _state
    claimed = _state.is_turn_output(resolved)
    try:
        return _checked(p, resolved, path, for_write)
    except ValueError:
        if for_write and not claimed:
            _state.forget_turn_output(resolved)
        raise


def _checked(p: Path, resolved: Path, path: str, for_write: bool) -> Path:
    if private_areas_fenced():
        area = _member_denied_area(p, resolved, for_write=for_write)
        if area is not None:
            verb = "write to" if for_write else "read"
            if area == "out":
                raise ValueError(
                    f"cannot {verb} {path}: member devices and peers without a tool policy use only the files "
                    "this turn created in out/, and an existing file is not theirs, so choose a new file name"
                )
            raise ValueError(
                f"member devices and peers without a tool policy cannot {verb} the profile "
                f"{area}/ area; this requires an admin device: {path}"
            )
    area = _always_private_area(p, resolved, for_write=for_write)
    if area is not None:
        raise ValueError(_always_private_error(area, path, for_write=for_write))
    if for_write:
        enforce_write_paths(resolved, path)
        _enforce_dispatch_write_scope(resolved, path)
    from alpi.core.execution_world import current as current_world
    world = current_world()
    return world.filesystem_path(resolved) if world is not None else resolved


def _profile_write_roots() -> list[Path]:
    from alpi.home import get_home
    from alpi import config as cfg_mod
    home = get_home().resolve()
    try:
        tools_cfg = cfg_mod.load(home).tools
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"config failed to load; refusing to write: {exc}") from exc
    if tools_cfg.write_paths is None:
        raise ValueError(
            "tools.write_paths in config.yaml is invalid: it must be a list of folder names; "
            "every write is refused until it is fixed"
        )
    roots = []
    for entry in tools_cfg.write_paths:
        try:
            root = Path(entry).expanduser()
            roots.append((root if root.is_absolute() else home / root).resolve())
        except (OSError, RuntimeError, ValueError) as exc:
            raise ValueError(
                f"tools.write_paths entry {entry!r} cannot be resolved ({exc}); every write is refused until it is fixed"
            ) from exc
    return roots


def enforce_write_paths(resolved: Path, original: str) -> None:
    roots = _profile_write_roots()
    if not roots or any(resolved.is_relative_to(root) for root in roots):
        return
    raise ValueError(
        f"cannot write {original}: this profile writes only inside {', '.join(str(r) for r in roots)} "
        "(tools.write_paths in config.yaml); write the file there, with its absolute path"
    )


def _enforce_dispatch_write_scope(resolved: Path, original: str) -> None:
    raw = os.environ.get("ALPI_WORKGROUP_WRITE_SCOPE")
    if raw is None:
        return
    # cwd is not a boundary: an unset workspace must never anchor the phase root.
    if _configured_workspace() is None:
        raise ValueError(f"path is outside the active phase boundary: {original}")
    try:
        scope = json.loads(raw)
        workspace = _workspace_root().resolve()
        root = (workspace / str(scope.get("root") or "")).resolve()
        root.relative_to(workspace)
        patterns = tuple(str(item) for item in scope.get("paths") or ())
        rel = resolved.relative_to(root).as_posix()
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"path is outside the active phase boundary: {original}") from exc
    if not any(fnmatch.fnmatchcase(rel, pattern) for pattern in patterns):
        raise ValueError(f"path is outside the active phase boundary: {original}")


def release_unused_claim(resolved: Path) -> None:
    from alpi.tools import _state
    if not resolved.exists():
        _state.forget_turn_output(resolved)


def resolve_workspace_path(path: str, *, for_write: bool = False) -> Path:
    """Resolve a path that must remain inside the active workspace."""
    typed = Path(path).expanduser()
    root = _workspace_root().resolve()
    if not typed.is_absolute():
        typed = root / typed
    if typed.is_symlink():
        raise ValueError(f"refusing workspace symlink: {path}")
    resolved = resolve_path(str(typed), for_write=for_write)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        if for_write:
            release_unused_claim(resolved)
        raise ValueError(f"path must stay inside the active workspace: {path}") from exc
    return resolved


def suggest_similar_paths(target: Path, limit: int = 5) -> list[str]:
    """List entries in the target's parent that fuzzy-match its basename."""
    parent = target.parent
    if not parent.exists() or not parent.is_dir():
        return []
    needle = target.name.lower()
    if not needle:
        return []
    scored: list[tuple[int, str]] = []
    try:
        for child in parent.iterdir():
            name = child.name
            nl = name.lower()
            if nl == needle:
                continue
            if needle in nl:
                scored.append((0, str(child)))
            elif nl.startswith(needle[: max(3, len(needle) // 2)]):
                scored.append((1, str(child)))
            elif needle in nl or nl in needle:
                scored.append((2, str(child)))
    except OSError:
        return []
    scored.sort(key=lambda t: (t[0], t[1]))
    return [s for _, s in scored[:limit]]
