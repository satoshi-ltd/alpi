from __future__ import annotations

import fnmatch
import glob
import itertools
import os
import re
import time

from alpi.tools._pipe_to_interpreter import (
    command_segments,
    segment_executable,
)

_MAX_TOKEN_CHARS = 4096
_MAX_GLOB_TOKENS = 8
_MAX_GLOB_DEPTH = 3
_MAX_GLOB_RESULTS = 64
_MAX_BRACE_RESULTS = 32
_MAX_NESTED_COMMANDS = 3
_BUDGET_SECONDS = 2.0
_SYNTHETIC_NAMES = (
    ".env", "config.yaml", "secrets",
    "id_rsa", "id_ed25519", "id_ecdsa", "authorized_keys",
)

_CREDENTIAL_RES = (
    re.compile(r"(?:^|/)\.ssh/(?:id_(?!.*\.pub$)[^/]*|[^/]*_key|authorized_keys)$", re.I),
    re.compile(r"(?:^|/)\.aws/credentials$", re.I),
    re.compile(r"(?:^|/)\.gnupg(?:/|$)", re.I),
    re.compile(r"(?:^|/)\.config/gh/hosts\.yml$", re.I),
    re.compile(r"(?:^|/)\.config/gcloud/(?:credentials\.db|access_tokens\.db|application_default_credentials\.json)$", re.I),
)
_HOME_FILES = (".netrc", ".npmrc", ".pypirc", ".pgpass", ".sentryclirc")
_PRIVATE_REL_RE = re.compile(
    r"(?:profiles/[^/]+/)?(?:"
    r"\.env(?:\.(?!(?:example|sample|template|dist)(?:/|$))[^/]*)?"
    r"|config\.yaml|secrets|alp/secrets|host/connections\.yaml|skills/[^/]+/[^/]+/secrets"
    r")(?:/|$)",
    re.I,
)
_ANCESTOR_REL_RE = re.compile(
    r"(?:profiles(?:/[^/]+)?|(?:profiles/[^/]+/)?(?:skills(?:/[^/]+){0,2}|alp|host))?", re.I,
)
_CREDENTIAL_DIR_RE = re.compile(r"(?:^|/)\.(?:ssh|aws|gnupg)$|(?:^|/)\.config(?:/(?:gh|gcloud))?$", re.I)
_INPUT_SUB_RE = re.compile(r"\$\(\s*<\s*([^()\s]+)\s*\)|`\s*<\s*([^`\s]+)\s*`")

_ASSIGNMENT_RE = re.compile(r"([A-Za-z_]\w*)=(.*)", re.S)
_VAR_RE = re.compile(r"\$(?:\{(\w+)\}|(\w+))")
_GLOB_RE = re.compile(r"[*?\[]")
_OPERATOR_RE = re.compile(r"[|&;<>()]+")
_BRACE_RE = re.compile(r"\{([^{}]*,[^{}]*)\}")

_ALWAYS_RECURSIVE = frozenset({
    "tar", "bsdtar", "zip", "7z", "7za", "rsync", "scp", "rg", "ag", "ack", "ditto", "pax", "rclone",
})
_METADATA_EXES = frozenset({"ls", "du", "stat", "readlink", "realpath", "test", "[", "[["})
_PATTERN_FIRST = frozenset({"rg", "ag", "ack", "grep", "egrep", "fgrep", "zgrep"})
_RECURSIVE_FLAG_LETTERS = {
    "cp": "rRa", "grep": "rR", "egrep": "rR", "fgrep": "rR", "zgrep": "rR",
}
_FIND_EXEC = frozenset({"-exec", "-execdir", "-ok", "-okdir"})
_IDENTITY_USERS = frozenset({"ssh", "sftp"})
_KEYGEN_SAFE_FLAGS = frozenset({"-l", "-y", "-t"})
_SHELLS = frozenset({"sh", "bash", "zsh", "dash", "ash", "ksh"})
_CHDIR_FLAGS = frozenset({"-C", "--directory", "--chdir"})
_CHDIR_EXES = frozenset({"tar", "bsdtar", "git", "make", "env"})
_GROUP_TOKENS = frozenset({"(", ")", "{", "}"})
_SEPARATORS = frozenset({";", "&&", "||", "&", "|", "|&"})


class _Budget:
    def __init__(self) -> None:
        self.deadline = time.monotonic() + _BUDGET_SECONDS
        self.globs = 0

    def spent(self) -> bool:
        return time.monotonic() > self.deadline


def _roots() -> list[str]:
    from alpi.home import alpi_root, get_home

    found: list[str] = []
    for base in (alpi_root, get_home):
        try:
            path = base()
        except Exception:  # noqa: BLE001
            continue
        for cand in (str(path), os.path.realpath(path)):
            if cand not in found:
                found.append(cand)
    return found


def _base_env() -> dict[str, str]:
    from alpi.home import get_home

    env = dict(os.environ)
    env["HOME"] = os.path.expanduser("~")
    try:
        env["ALPI_HOME"] = str(get_home())
    except Exception:  # noqa: BLE001
        pass
    return env


def _expand(raw: str, env: dict[str, str]) -> str | None:
    missing = False

    def sub(match: re.Match[str]) -> str:
        nonlocal missing
        value = env.get(match.group(1) or match.group(2))
        if value is None:
            missing = True
            return ""
        return value

    out = _VAR_RE.sub(sub, raw)
    return None if missing else out


def _braces(token: str) -> list[str]:
    results = [token]
    for _ in range(4):
        grown: list[str] = []
        changed = False
        for item in results:
            match = _BRACE_RE.search(item)
            if not match:
                grown.append(item)
                continue
            changed = True
            for part in match.group(1).split(","):
                grown.append(item[:match.start()] + part + item[match.end():])
        results = grown[:_MAX_BRACE_RESULTS]
        if not changed:
            break
    return results


def _relative_to(path: str, root: str) -> str | None:
    path, root = path.casefold(), root.rstrip(os.sep).casefold()
    if path == root:
        return ""
    if path.startswith(root + os.sep):
        return path[len(root) + 1:]
    return None


def _is_credential(path: str, roots: list[str]) -> bool:
    if any(rx.search(path) for rx in _CREDENTIAL_RES):
        return True
    home = os.path.expanduser("~")
    if any(_relative_to(path, os.path.join(home, name)) == "" for name in _HOME_FILES):
        return True
    for root in roots:
        rel = _relative_to(path, root)
        if rel and _PRIVATE_REL_RE.match(rel):
            return True
    return False


def _is_credential_ancestor(path: str, roots: list[str]) -> bool:
    if _CREDENTIAL_DIR_RE.search(path):
        return True
    for root in roots:
        rel = _relative_to(path, root)
        if rel is not None and _ANCESTOR_REL_RE.fullmatch(rel):
            return True
    return False


def _flag_letters(segment: list[str]) -> str:
    return "".join(t[1:] for t in segment if re.fullmatch(r"-[A-Za-z]+", t))


def _is_recursive(exe: str, segment: list[str]) -> bool:
    if exe in _ALWAYS_RECURSIVE:
        return True
    if exe == "find":
        return any(t in _FIND_EXEC for t in segment)
    if exe == "aws":
        return "sync" in segment or "--recursive" in segment
    letters = _RECURSIVE_FLAG_LETTERS.get(exe)
    if letters is None:
        return False
    if any(t in ("--recursive", "--archive", "--dereference-recursive") for t in segment):
        return True
    return any(ch in letters for ch in _flag_letters(segment))


def _glob_candidates(path: str, budget: _Budget) -> list[str]:
    parent, base = os.path.split(path)
    found: list[str] = []
    depth = sum(1 for part in path.split("/") if _GLOB_RE.search(part))
    if budget.globs < _MAX_GLOB_TOKENS and depth <= _MAX_GLOB_DEPTH:
        budget.globs += 1
        found = list(itertools.islice(glob.iglob(path, recursive=True), _MAX_GLOB_RESULTS))
    if not _GLOB_RE.search(parent):
        found += [
            os.path.join(parent, name)
            for name in _SYNTHETIC_NAMES
            if _part_matches(name, base)
        ]
    return found


def _credential_samples(roots: list[str]) -> list[str]:
    home = os.path.expanduser("~")
    samples = [
        os.path.join(home, rel)
        for rel in (
            ".ssh/id_rsa", ".ssh/id_ed25519", ".ssh/id_ecdsa", ".ssh/authorized_keys",
            ".aws/credentials", ".netrc", ".npmrc", ".pypirc", ".pgpass", ".sentryclirc",
            ".config/gh/hosts.yml", ".config/gcloud/credentials.db",
            ".gnupg/private-keys-v1.d", ".gnupg/pubring.kbx",
        )
    ]
    for root in roots:
        samples += [
            os.path.join(root, rel)
            for rel in (".env", "config.yaml", "secrets", "alp/secrets", "host/connections.yaml")
        ]
    return samples


def _part_matches(name: str, pattern: str) -> bool:
    if name.startswith(".") and not pattern.startswith("."):
        return False
    return fnmatch.fnmatchcase(name.casefold(), pattern.casefold())


def _parts_match(names: list[str], patterns: list[str]) -> bool:
    if not patterns:
        return not names
    if patterns[0] == "**":
        return _parts_match(names, patterns[1:]) or (
            bool(names) and not names[0].startswith(".") and _parts_match(names[1:], patterns)
        )
    return bool(names) and _part_matches(names[0], patterns[0]) and _parts_match(names[1:], patterns[1:])


def _pattern_may_match(pattern: str, roots: list[str]) -> bool:
    parts = pattern.split("/")
    return any(_parts_match(sample.split("/"), parts) for sample in _credential_samples(roots))


def _forms(path: str) -> tuple[str, ...]:
    return (path, os.path.realpath(path))


def _set_work(env: dict[str, str], old: str, new: str) -> str:
    env["OLDPWD"], env["PWD"] = old, new
    return new


def _hits(
    raw: str, env: dict[str, str], work: str, roots: list[str], recursive: bool, budget: _Budget,
) -> bool:
    if raw.startswith("@"):
        raw = raw[1:].split(";", 1)[0]
    if not raw or raw.startswith("-") or len(raw) > _MAX_TOKEN_CHARS or _OPERATOR_RE.fullmatch(raw):
        return False
    for variant in _braces(raw):
        expanded = _expand(variant, env)
        if expanded is None:
            continue
        path = os.path.expanduser(expanded)
        if not os.path.isabs(path):
            path = os.path.join(work, path)
        path = os.path.normpath(path)
        has_glob = bool(_GLOB_RE.search(path))
        if has_glob and _pattern_may_match(path, roots):
            return True
        for cand in _glob_candidates(path, budget) if has_glob else [path]:
            for form in _forms(cand):
                if _is_credential(form, roots):
                    return True
                if recursive and _is_credential_ancestor(form, roots):
                    return True
    return False


def _flatten(segments: list[list[str]]) -> list[list[str]]:
    out: list[list[str]] = []
    for seg in segments:
        current: list[str] = []
        for tok in seg:
            if tok in _GROUP_TOKENS:
                continue
            if tok in _SEPARATORS:
                out.append(current)
                current = []
                continue
            current.append(tok)
        out.append(current)
    return [seg for seg in out if seg]


def _names_key_to_use(exe: str, tokens: list[str], i: int) -> bool:
    tok = tokens[i]
    prev = tokens[i - 1] if i else ""
    if exe == "ssh-add":
        return not tok.startswith("-")
    if exe in _IDENTITY_USERS:
        return (
            prev == "-i"
            or tok.startswith("-i")
            or (prev == "-o" and tok.lower().startswith("identityfile="))
            or tok.lower().startswith("-oidentityfile=")
        )
    if exe == "ssh-keygen":
        return (prev == "-f" or tok.startswith("-f")) and any(t in _KEYGEN_SAFE_FLAGS for t in tokens)
    return False


def _positional(tokens: list[str]) -> list[str]:
    return [t for t in tokens[1:] if not t.startswith("-") and not _OPERATOR_RE.fullmatch(t)]


def _chdir_target(exe: str, tokens: list[str], i: int) -> str | None:
    if exe not in _CHDIR_EXES and os.path.basename(tokens[0]) not in _CHDIR_EXES:
        return None
    tok = tokens[i]
    if tok in _CHDIR_FLAGS:
        return tokens[i + 1] if i + 1 < len(tokens) else None
    if tok.startswith(("--directory=", "--chdir=")):
        return tok.split("=", 1)[1]
    if tok.startswith("-C") and len(tok) > 2:
        return tok[2:]
    return None


def _candidates(tok: str) -> list[str]:
    found: list[str] = []
    head, eq, value = tok.partition("=")
    if eq and re.search(r"\s", value):
        return found
    found.append(tok)
    if eq:
        found.append(value)
    if re.fullmatch(r"-[A-Za-z].+", tok):
        found.append(tok[2:])
    return found


def touches_credential_path(
    command: str, cwd: str | None = None, _depth: int = 0, _env: dict[str, str] | None = None,
) -> bool:
    try:
        return _touches(command, cwd, _depth, _env)
    except (ValueError, OSError):
        return True


def _input_substitutions(command: str) -> list[str]:
    return [(m.group(1) or m.group(2)).strip("'\"") for m in _INPUT_SUB_RE.finditer(command)]


def _touches(command: str, cwd: str | None, depth: int, outer_env: dict[str, str] | None) -> bool:
    segments = command_segments(command)
    if segments is None:
        segments = [command.split()]
    roots = _roots()
    env = dict(outer_env) if outer_env else _base_env()
    if outer_env is None:
        env.pop("OLDPWD", None)
    work = os.path.normpath(cwd or os.getcwd())
    env["PWD"] = work
    budget = _Budget()
    for path in _input_substitutions(command):
        if _hits(path, env, work, roots, False, budget):
            return True
    stack: list[str] = []
    for seg in _flatten(segments):
        exe = segment_executable(seg)
        tokens = seg
        recursive = _is_recursive(exe, tokens)
        seg_work = work
        skip_next = False
        for i, tok in enumerate(tokens):
            if budget.spent():
                return True
            if skip_next:
                skip_next = False
                continue
            target = _chdir_target(exe, tokens, i)
            if target is not None:
                expanded = _expand(target, env)
                if expanded:
                    seg_work = os.path.normpath(os.path.join(seg_work, os.path.expanduser(expanded)))
                    env["PWD"] = seg_work
                skip_next = tok in _CHDIR_FLAGS
                continue
            if _names_key_to_use(exe, tokens, i):
                continue
            match = _ASSIGNMENT_RE.fullmatch(tok)
            if match and not tok.startswith("-"):
                expanded = _expand(match.group(2), env)
                if expanded is not None:
                    env[match.group(1)] = expanded
            cands = _candidates(tok)
            if exe in _METADATA_EXES and i and _GLOB_RE.search(tok):
                cands = []
            for cand in cands:
                if _hits(cand, env, seg_work, roots, recursive, budget):
                    return True
        env["PWD"] = work
        if recursive and exe in _PATTERN_FIRST and len(_positional(tokens)) <= 1:
            if any(
                _is_credential_ancestor(form, roots) or _is_credential(form, roots)
                for form in _forms(seg_work)
            ):
                return True
        if exe in ("cd", "pushd"):
            args = _positional(tokens)
            if tokens[1:2] == ["-"]:
                target = env.get("OLDPWD")
            elif args:
                target = _expand(args[0], env)
            else:
                target = env.get("HOME")
            if exe == "pushd":
                stack.append(work)
            if target:
                work = _set_work(env, work, os.path.normpath(os.path.join(work, os.path.expanduser(target))))
        elif exe == "popd":
            if not stack:
                return True
            work = _set_work(env, work, stack.pop())
        if depth < _MAX_NESTED_COMMANDS:
            for nested in _nested_commands(tokens) + _assigned_commands(tokens):
                if touches_credential_path(nested, work, depth + 1, env):
                    return True
    return False


def _assigned_commands(tokens: list[str]) -> list[str]:
    return [
        value for _, eq, value in (tok.partition("=") for tok in tokens)
        if eq and re.search(r"\s", value)
    ]


def _nested_commands(tokens: list[str]) -> list[str]:
    found: list[str] = []
    for i, tok in enumerate(tokens):
        name = os.path.basename(tok).casefold()
        if name == "eval":
            found.append(" ".join(tokens[i + 1:]))
        elif name in _SHELLS:
            for j in range(i + 1, len(tokens) - 1):
                if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", tokens[j]):
                    found.append(tokens[j + 1])
                    break
    return found
