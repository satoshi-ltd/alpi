from __future__ import annotations

import shutil
import threading
from pathlib import Path

from alpi import _log
from alpi._log import get_subsystem_logger, log_path


def _lines(home: Path, subsystem: str) -> list[str]:
    path = log_path(home, subsystem)
    return [line.rsplit(" ", 1)[-1] for line in path.read_text().splitlines()] if path.exists() else []


def test_two_homes_in_one_process_keep_their_own_lines(tmp_path: Path) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    for subsystem in ("llm", "agent", "approval"):
        get_subsystem_logger(first, subsystem).info("from-first")
        get_subsystem_logger(second, subsystem).info("from-second")
        get_subsystem_logger(first, subsystem).info("first-again")
    for subsystem in ("llm", "agent", "approval"):
        assert _lines(first, subsystem) == ["from-first", "first-again"]
        assert _lines(second, subsystem) == ["from-second"]


def test_the_line_format_still_names_the_subsystem(tmp_path: Path) -> None:
    get_subsystem_logger(tmp_path, "agent").info("hello")
    assert " INFO alpi.agent hello" in log_path(tmp_path, "agent").read_text()


def test_a_home_removed_and_created_again_gets_its_lines(tmp_path: Path) -> None:
    home = tmp_path / "profile"
    logger = get_subsystem_logger(home, "agent")
    logger.info("before")
    shutil.rmtree(home)
    again = get_subsystem_logger(home, "agent")
    again.info("after")
    assert again is logger
    assert _lines(home, "agent") == ["after"]


def test_a_log_rotated_by_another_process_is_followed(tmp_path: Path) -> None:
    logger = get_subsystem_logger(tmp_path, "agent")
    logger.info("old")
    path = log_path(tmp_path, "agent")
    path.rename(path.with_name("agent.log.1"))
    path.write_text("")
    get_subsystem_logger(tmp_path, "agent").info("new")
    assert _lines(tmp_path, "agent") == ["new"]


def test_a_home_whose_log_cannot_be_opened_does_not_raise_and_recovers(tmp_path: Path) -> None:
    blocker = tmp_path / "home"
    blocker.write_text("a file where the home should be")
    get_subsystem_logger(blocker, "agent").warning("dropped")
    blocker.unlink()
    get_subsystem_logger(blocker, "agent").info("kept")
    assert _lines(blocker, "agent") == ["kept"]


def test_many_threads_asking_for_one_log_share_one_handler(tmp_path: Path) -> None:
    seen: list[object] = []

    def ask() -> None:
        logger = get_subsystem_logger(tmp_path, "llm")
        logger.info("line")
        seen.append(logger)

    threads = [threading.Thread(target=ask) for _ in range(16)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len({id(logger) for logger in seen}) == 1
    assert len(seen[0].handlers) == 1
    assert len(_lines(tmp_path, "llm")) == 16


def _open_log_files() -> int:
    return sum(isinstance(logger.handlers[0], _log.RotatingFileHandler) for logger in _log._loggers.values())


def test_a_process_that_sees_many_homes_keeps_a_bounded_number_of_logs_open(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(_log, "MAX_OPEN", 4)
    first = get_subsystem_logger(tmp_path / "home-0", "agent")
    first.info("early")
    for index in range(1, 12):
        get_subsystem_logger(tmp_path / f"home-{index}", "agent").info("line")
        assert len(_log._loggers) <= 4

    assert _open_log_files() <= 4
    assert isinstance(first.handlers[0], _log.logging.NullHandler)
    first.warning("dropped quietly by a logger that was put aside")
    get_subsystem_logger(tmp_path / "home-0", "agent").info("back")
    assert _lines(tmp_path / "home-0", "agent") == ["early", "back"]
    for index in range(1, 12):
        assert _lines(tmp_path / f"home-{index}", "agent") == ["line"]
