from __future__ import annotations

import contextvars
import shutil
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from alpi.core.run_context import RunContext


@dataclass(frozen=True)
class ExecutionWorld:
    context: RunContext
    backend: str = "local"

    def filesystem_path(self, path: Path) -> Path:
        return path

    def command(
        self,
        command: str,
        cwd: Path,
        env_keys: tuple[str, ...],
        *,
        container_name: str | None = None,
    ) -> list[str] | str:
        return command


@dataclass(frozen=True)
class DockerExecutionWorld(ExecutionWorld):
    image: str = "python:3.12-slim"
    allow_network: bool = False
    backend: str = "docker"

    def command(
        self,
        command: str,
        cwd: Path,
        env_keys: tuple[str, ...],
        *,
        container_name: str | None = None,
    ) -> list[str]:
        if shutil.which("docker") is None:
            raise RuntimeError("Docker execution requested but the docker CLI is unavailable")
        if not self.image or self.image.startswith("-") or any(char.isspace() for char in self.image):
            raise RuntimeError("Docker execution image must be one non-option image reference")
        if not cwd.is_dir():
            raise RuntimeError(f"Docker execution cwd is not a directory: {cwd}")
        if not self.context.workspace.is_dir() or not self.context.home.is_dir():
            raise RuntimeError("Docker execution workspace and profile home must be directories")
        mounts = {self.context.workspace.resolve(), self.context.home.resolve(), cwd.resolve()}
        args = ["docker", "run", "--rm", "-i", "--network", "bridge" if self.allow_network else "none"]
        if container_name is not None:
            args.extend(["--name", container_name])
        for path in sorted(mounts, key=str):
            args.extend(["--volume", f"{path}:{path}"])
        args.extend(["--workdir", str(cwd)])
        for key in env_keys:
            args.extend(["--env", key])
        args.extend(["--env", "HOME=/tmp"])
        args.extend([self.image, "/bin/sh", "-lc", command])
        return args


def build(context: RunContext, cfg) -> ExecutionWorld:  # noqa: ANN001
    execution = cfg.tools.execution
    if execution.backend == "docker":
        return DockerExecutionWorld(
            context=context, image=execution.docker_image,
            allow_network=cfg.tools.terminal.allow_network,
        )
    return ExecutionWorld(context=context)


_current: contextvars.ContextVar[ExecutionWorld | None] = contextvars.ContextVar(
    "alpi_execution_world", default=None,
)


def current() -> ExecutionWorld | None:
    return _current.get()


@contextmanager
def use(world: ExecutionWorld) -> Iterator[ExecutionWorld]:
    token = _current.set(world)
    try:
        yield world
    finally:
        _current.reset(token)


__all__ = ["DockerExecutionWorld", "ExecutionWorld", "build", "current", "use"]
