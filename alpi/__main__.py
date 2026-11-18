import os
import sys


def main() -> None:
    # PID 1 forks before alpi.cli is imported: a thread a dependency starts at import is absent from the daemon while the locks it held stay taken.
    if os.getpid() == 1 and _starts_daemon(sys.argv[1:]):
        from alpi import pid1

        pid1.run(_cli)
        return
    _cli()


def _starts_daemon(args: list[str]) -> bool:
    rest = list(args)
    while rest and rest[0].startswith("-") and rest[0] != "--":
        head = rest.pop(0)
        if head in ("--continue",) or head.startswith("--profile="):
            continue
        if head == "--profile":
            if not rest:
                return False
            rest.pop(0)
            continue
        if head.startswith("--"):
            return False
        flags = head[1:]
        while flags:
            flag, flags = flags[0], flags[1:]
            if flag == "c":
                continue
            if flag != "p":
                return False
            if not flags:
                if not rest:
                    return False
                rest.pop(0)
            flags = ""
    if rest[:1] == ["--"]:
        rest.pop(0)
    if rest[:1] != ["daemon"]:
        return False
    rest.pop(0)
    if rest[:1] == ["--"]:
        rest.pop(0)
    return rest[:1] == ["start"]


def _cli() -> None:
    from alpi.cli import main as cli_main

    cli_main()


if __name__ == "__main__":
    main()
