from __future__ import annotations

import shlex

_DOWNLOADERS = frozenset({"curl", "wget", "fetch"})

_INTERPRETERS = frozenset({
    "sh", "bash", "zsh", "ash", "dash", "ksh", "fish",
    "python", "python2", "python3", "perl", "ruby", "node",
    "pwsh", "powershell",
})

_PIPE_TOKENS = frozenset({"|", "|&"})
_SEPARATOR_TOKENS = frozenset({";", "&&", "||", "&"})

_GROUP_OPEN = frozenset({"(", "{"})
_GROUP_CLOSE = frozenset({")", "}"})
_GROUP_TOKENS = _GROUP_OPEN | _GROUP_CLOSE

_REDIR_OPS = frozenset({">", ">>", "<", "<<", "<<<", "<>", ">&", "&>", "<&"})

_WRAPPER_SPECS: dict[str, dict] = {
    "sudo": {
        "value_flags": frozenset({
            "-u", "-g", "-h", "-p", "-r", "-t", "-T", "-C", "-D",
            "--user", "--group", "--host", "--prompt", "--chdir", "--chroot", "--type",
        }),
        "positional_after_flags": 0,
        "query_flags": frozenset(),
        "shell_flags": frozenset({"-s", "--shell", "-i", "--login"}),
    },
    "nice": {
        "value_flags": frozenset({"-n", "--adjustment"}),
        "positional_after_flags": 0,
        "query_flags": frozenset(),
    },
    "ionice": {
        "value_flags": frozenset({
            "-c", "-n", "-p", "-P", "-u",
            "--class", "--classdata", "--pid", "--uid",
        }),
        "positional_after_flags": 0,
        "query_flags": frozenset(),
    },
    "nohup": {"value_flags": frozenset(), "positional_after_flags": 0, "query_flags": frozenset()},
    "stdbuf": {
        "value_flags": frozenset({"-i", "-o", "-e", "--input", "--output", "--error"}),
        "positional_after_flags": 0,
        "query_flags": frozenset(),
    },
    "timeout": {
        "value_flags": frozenset({"-k", "-s", "--kill-after", "--signal"}),
        "positional_after_flags": 1,
        "query_flags": frozenset(),
    },
    "command": {
        "value_flags": frozenset(),
        "positional_after_flags": 0,
        "query_flags": frozenset({"-v", "-V"}),
    },
    "exec": {
        "value_flags": frozenset({"-a"}),
        "positional_after_flags": 0,
        "query_flags": frozenset(),
    },
}


def _normalize_exe(token: str) -> str:
    if not token:
        return ""
    sep = max(token.rfind("/"), token.rfind("\\"))
    name = token[sep + 1:] if sep >= 0 else token
    name = name.casefold()
    if name.endswith(".exe"):
        name = name[:-4]
    return name


def _normalize_command(cmd: str) -> str:
    cmd = cmd.replace("\\\n", " ")
    out: list[str] = []
    i = 0
    quote: str | None = None
    while i < len(cmd):
        c = cmd[i]
        if quote is None:
            if c in ('"', "'"):
                quote = c
                out.append(c)
                i += 1
                continue
            if c == "\\" and i + 1 < len(cmd):
                out.append(c)
                out.append(cmd[i + 1])
                i += 2
                continue
            if c == "\n":
                j = i + 1
                while j < len(cmd) and cmd[j] in " \t":
                    j += 1
                next_is_op = j < len(cmd) and cmd[j] in "|&;"
                k = len(out) - 1
                while k >= 0 and out[k] in " \t":
                    k -= 1
                prev_is_op = k >= 0 and out[k] in "|&;"
                if next_is_op or prev_is_op:
                    out.append(" ")
                else:
                    out.append(" ; ")
                i += 1
                continue
            out.append(c)
            i += 1
            continue
        out.append(c)
        if c == quote:
            quote = None
            i += 1
            continue
        if c == "\\" and i + 1 < len(cmd) and quote == '"':
            out.append(cmd[i + 1])
            i += 2
            continue
        i += 1
    return "".join(out)


def _tokenize(command: str) -> list[str] | None:
    normalized = _normalize_command(command)
    lex = shlex.shlex(normalized, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    try:
        return list(lex)
    except ValueError:
        return None


def _split_by_separators(tokens: list[str]) -> list[list[str]]:
    chains: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for tok in tokens:
        if tok in _GROUP_OPEN:
            depth += 1
            current.append(tok)
            continue
        if tok in _GROUP_CLOSE:
            depth = max(0, depth - 1)
            current.append(tok)
            continue
        if depth == 0 and tok in _SEPARATOR_TOKENS:
            if current:
                chains.append(current)
                current = []
            continue
        current.append(tok)
    if current:
        chains.append(current)
    return chains


def _split_by_pipe(tokens: list[str]) -> list[list[str]]:
    segments: list[list[str]] = []
    current: list[str] = []
    depth = 0
    for tok in tokens:
        if tok in _GROUP_OPEN:
            depth += 1
            current.append(tok)
            continue
        if tok in _GROUP_CLOSE:
            depth = max(0, depth - 1)
            current.append(tok)
            continue
        if depth == 0 and tok in _PIPE_TOKENS:
            segments.append(current)
            current = []
            continue
        current.append(tok)
    segments.append(current)
    return segments


def _strip_redirs_and_groups(segment: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    n = len(segment)
    while i < n:
        tok = segment[i]
        if tok in _GROUP_TOKENS:
            i += 1
            continue
        if tok.isdigit() and i + 1 < n and segment[i + 1] in _REDIR_OPS:
            i += 3 if i + 2 < n else 2
            continue
        if tok in _REDIR_OPS:
            i += 2 if i + 1 < n else 1
            continue
        out.append(tok)
        i += 1
    return out


def _resolve_executable_flat(toks: list[str]) -> str:
    i = 0
    while i < len(toks):
        tok = toks[i]
        if not tok:
            i += 1
            continue
        if "=" in tok and not tok.startswith("-"):
            head = tok.split("=", 1)[0]
            if head and (head[0].isalpha() or head[0] == "_") and head.replace("_", "").isalnum():
                i += 1
                continue

        base = _normalize_exe(tok)

        if base == "env":
            i += 1
            while i < len(toks) and toks[i].startswith("-"):
                flag = toks[i]
                i += 1
                if flag.startswith("--split-string="):
                    inner = flag.split("=", 1)[1]
                    exe = _resolve_in_split_string(inner)
                    if exe:
                        return exe
                    continue
                if flag in {"-S", "--split-string"} and i < len(toks):
                    inner = toks[i]
                    i += 1
                    exe = _resolve_in_split_string(inner)
                    if exe:
                        return exe
                    continue
                if flag in {"-u", "--unset"} and i < len(toks):
                    i += 1
            while i < len(toks) and "=" in toks[i] and not toks[i].startswith("-"):
                h = toks[i].split("=", 1)[0]
                if h and (h[0].isalpha() or h[0] == "_"):
                    i += 1
                else:
                    break
            continue

        if base in _WRAPPER_SPECS:
            spec = _WRAPPER_SPECS[base]
            i += 1
            saw_query = False
            saw_shell = False
            while i < len(toks) and toks[i].startswith("-"):
                flag = toks[i]
                i += 1
                if flag in spec["query_flags"]:
                    saw_query = True
                if flag in spec.get("shell_flags", frozenset()):
                    saw_shell = True
                if flag in spec["value_flags"] and i < len(toks):
                    i += 1
            if saw_query:
                return ""
            if saw_shell:
                return "sh"
            i += spec["positional_after_flags"]
            continue

        return base
    return ""


def _resolve_in_split_string(value: str) -> str:
    if not value or not value.strip():
        return ""
    try:
        lex = shlex.shlex(value, posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        lex.commenters = ""
        inner_tokens = list(lex)
    except ValueError:
        return ""
    return _resolve_executable_flat(inner_tokens)


def _segment_executable(segment: list[str]) -> str:
    toks = _strip_redirs_and_groups(segment)
    return _resolve_executable_flat(toks)


def _segment_contains(segment: list[str], target: frozenset[str]) -> bool:
    if not segment:
        return False
    is_group = segment[0] in _GROUP_OPEN
    if not is_group:
        return _segment_executable(segment) in target

    toks = _strip_redirs_and_groups(segment)
    current: list[str] = []
    subs: list[list[str]] = []
    for tok in toks:
        if tok in _SEPARATOR_TOKENS or tok in _PIPE_TOKENS:
            if current:
                subs.append(current)
                current = []
        else:
            current.append(tok)
    if current:
        subs.append(current)
    return any(_resolve_executable_flat(sub) in target for sub in subs)


def is_pipe_to_interpreter(command: str) -> bool:
    if not command or not command.strip():
        return False
    tokens = _tokenize(command)
    if not tokens:
        return False

    for chain in _split_by_separators(tokens):
        segments = _split_by_pipe(chain)
        if len(segments) < 2:
            continue
        for idx, seg in enumerate(segments[:-1]):
            if not _segment_contains(seg, _DOWNLOADERS):
                continue
            for later in segments[idx + 1:]:
                if _segment_contains(later, _INTERPRETERS):
                    return True
    return False
