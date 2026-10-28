from __future__ import annotations

import os
import re
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


_EXEC_BUILTINS = frozenset({"eval", "source", "."})
_MARK = "\x00SUB\x00"
_MARK_AT_COMMAND_RE = re.compile(r"(?:^|[;&|(]\s*)\x00SUB\x00")
_DOWNLOAD_WORD_RE = re.compile(r"(?:^|[\s;&|(`/])(?<!git )(?:curl|wget|fetch)(?=\s|$)")
_ASSIGNMENT_RE = re.compile(r"([A-Za-z_]\w*)=")
_VALUE_LETTER = {"curl": "o", "wget": "O", "fetch": "o"}
_VALUE_LONG = {
    "curl": frozenset({"--output"}),
    "wget": frozenset({"--output-document"}),
    "fetch": frozenset({"--output"}),
}
_PREFIX_FLAGS = frozenset({"-P", "--directory-prefix"})
_NO_RUN_FLAGS = frozenset({"-n", "--check"})
_VALUE_FLAGS = frozenset({"-o", "-W", "-X", "-r", "--require"})
_WRAPPER_NAMES = frozenset(_WRAPPER_SPECS) | {"exec"}
_KEYWORDS = frozenset({"if", "then", "do", "else", "elif", "while", "until", "!", "exec", "time"})


def command_segments(command: str) -> list[list[str]] | None:
    tokens = _tokenize(command)
    if tokens is None:
        return None
    return [seg for chain in _split_by_separators(tokens) for seg in _split_by_pipe(chain)]


def segment_executable(segment: list[str]) -> str:
    return _segment_executable(segment)


def _substitution_spans(text: str) -> list[tuple[int, int, str]]:
    spans: list[tuple[int, int, str]] = []
    n = len(text)
    i = 0
    while i < n:
        if text[i] == "`":
            j = text.find("`", i + 1)
            if j < 0:
                break
            spans.append((i, j + 1, text[i + 1:j]))
            i = j + 1
            continue
        if text.startswith(("$(", "<("), i):
            depth = 0
            j = i + 1
            while j < n:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                    if depth == 0:
                        break
                j += 1
            if j >= n:
                break
            spans.append((i, j + 1, text[i + 2:j]))
            i = j + 1
            continue
        i += 1
    return spans


def _head_index(segment: list[str]) -> int:
    toks = _strip_redirs_and_groups(segment)
    for i, tok in enumerate(toks):
        if _ASSIGNMENT_RE.match(tok) or tok in _KEYWORDS:
            continue
        return i
    return -1


def _head_token(segment: list[str]) -> str:
    toks = _strip_redirs_and_groups(segment)
    i = _head_index(segment)
    return toks[i] if i >= 0 else ""


def _first_positional(rest: list[str]) -> str:
    skip = False
    prev = ""
    for tok in rest:
        if skip:
            skip = False
            prev = tok
            continue
        if tok in _VALUE_FLAGS:
            skip = True
        elif tok.startswith("-") or tok in _REDIR_OPS:
            pass
        elif prev not in _REDIR_OPS:
            return tok
        prev = tok
    return ""


def _is_command_word(segment: list[str], tok: str) -> bool:
    return tok != "." or _head_token(segment) == "."


def _segment_runs_substitution(segment: list[str], marks: tuple[str, ...]) -> bool:
    def has_mark(tok: str) -> bool:
        return any(m in tok for m in marks)

    def code_mark(tok: str) -> bool:
        return tok in marks or bool(_MARK_AT_COMMAND_RE.search(tok)) or any(
            re.search(r"(?:^|[;&|(]\s*)" + re.escape(m), tok) for m in marks
        )

    head = _head_token(segment)
    if head == _MARK or head in marks:
        return True
    for i, tok in enumerate(segment):
        exe = _normalize_exe(tok)
        if exe in _WRAPPER_NAMES and i + 1 < len(segment) and segment[i + 1] == _MARK:
            return True
        is_builtin = exe in _EXEC_BUILTINS
        if not is_builtin and exe not in _INTERPRETERS:
            continue
        if not _is_command_word(segment, tok):
            continue
        rest = segment[i + 1:]
        if is_builtin and any(has_mark(t) for t in rest):
            return True
        positional = _first_positional(rest)
        for j, t in enumerate(rest):
            prev = rest[j - 1] if j else ""
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", prev) and code_mark(t):
                return True
            if prev in _REDIR_OPS and has_mark(t) and (not positional or has_mark(positional)):
                return True
        if positional and has_mark(positional) and code_mark(positional):
            return True
    return False


def _norm(token: str, work: str) -> str:
    return os.path.normpath(os.path.join(work, os.path.expanduser(token)))


def _download_outputs(segment: list[str], exe: str, work: str) -> set[str]:
    letter = _VALUE_LETTER.get(exe, "")
    longs = _VALUE_LONG.get(exe, frozenset())
    out: set[str] = set()
    urls = [t for t in segment if "://" in t]
    remote_name = False
    explicit = False
    prefix = work
    for i, tok in enumerate(segment):
        value = ""
        nxt = segment[i + 1] if i + 1 < len(segment) else ""
        if exe == "wget" and tok in _PREFIX_FLAGS and nxt:
            prefix = _norm(nxt, work)
        elif exe == "wget" and tok.startswith(("-P", "--directory-prefix=")) and tok not in _PREFIX_FLAGS:
            prefix = _norm(tok.split("=", 1)[1] if tok.startswith("--") else tok[2:], work)
        if tok in longs or tok in (">", ">>"):
            value = nxt
        elif "=" in tok and tok.split("=", 1)[0] in longs:
            value = tok.split("=", 1)[1]
        elif re.fullmatch(r"-[A-Za-z]+", tok) and letter and tok[-1] == letter:
            value = nxt
        elif letter and tok.startswith("-" + letter) and len(tok) > 2:
            value = tok[2:]
        if value:
            explicit = True
            out.add(_norm(value, work))
        if tok in ("--remote-name", "--remote-name-all") or (
            exe == "curl" and re.fullmatch(r"-[A-Za-z]*O[A-Za-z]*", tok)
        ):
            remote_name = True
    if remote_name or (exe == "wget" and not explicit):
        for url in urls:
            name = url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
            if name and "://" not in name:
                out.add(_norm(name, prefix))
    return out


def _downloaded_file_executed(segments: list[list[str]]) -> bool:
    outputs: set[str] = set()
    downloaded = False
    work = ""
    for seg in segments:
        exe = _segment_executable(seg)
        if exe in _DOWNLOADERS:
            downloaded = True
            outputs |= _download_outputs(seg, exe, work)
            continue
        if exe in ("cd", "pushd"):
            args = [t for t in _strip_redirs_and_groups(seg)[1:] if not t.startswith("-")]
            if args:
                work = _norm(args[0], work)
            continue
        if downloaded and exe == "tee":
            outputs |= {_norm(t, work) for t in seg[1:] if not t.startswith("-") and t != "tee"}
            continue
        if not outputs:
            continue
        if exe in ("cp", "mv"):
            args = [t for t in _strip_redirs_and_groups(seg)[1:] if not t.startswith("-")]
            if len(args) >= 2 and _norm(args[0], work) in outputs:
                outputs.add(_norm(args[-1], work))
            continue
        for i, tok in enumerate(seg):
            name = _normalize_exe(tok)
            if name not in _INTERPRETERS and name not in _EXEC_BUILTINS:
                continue
            if not _is_command_word(seg, tok):
                continue
            rest = seg[i + 1:]
            if any(t in _NO_RUN_FLAGS for t in rest):
                continue
            operand = _first_positional(rest)
            if operand and _norm(operand, work) in outputs:
                return True
            if name in _INTERPRETERS and (not operand or operand.isdigit() or "-s" in rest) and any(
                prev == "<" and _norm(t, work) in outputs for prev, t in zip(rest, rest[1:])
            ):
                return True
        head = _head_token(seg)
        if head and _norm(head, work) in outputs:
            return True
    return False


def runs_remote_code(command: str) -> bool:
    if not command or not command.strip():
        return False
    text = _normalize_command(command)
    parts: list[str] = []
    last = 0
    for start, end, body in _substitution_spans(text):
        if _DOWNLOAD_WORD_RE.search(body):
            parts.append(text[last:start])
            parts.append(_MARK)
            last = end
    if parts:
        parts.append(text[last:])
        masked = command_segments("".join(parts))
        if masked:
            marks = [_MARK]
            for seg in masked:
                for tok in seg:
                    match = _ASSIGNMENT_RE.match(tok)
                    if match and _MARK in tok:
                        marks += [f"${match.group(1)}", f"${{{match.group(1)}}}"]
            if any(_segment_runs_substitution(seg, tuple(marks)) for seg in masked):
                return True
    segments = command_segments(text)
    return bool(segments) and _downloaded_file_executed(segments)
