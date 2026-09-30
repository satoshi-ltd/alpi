from __future__ import annotations

import asyncio
import itertools
import json
from pathlib import Path
from typing import Any

from alpi import home

METHOD_NOT_FOUND = -32601
READ_LIMIT = 16 * 1024 * 1024
INVALID_RESPONSE = "invalid response from the daemon"

_ids = itertools.count(1)


class HostUnavailable(Exception):
    pass


class HostError(Exception):
    def __init__(self, code: int | None, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    @property
    def missing_verb(self) -> bool:
        return self.code == METHOD_NOT_FOUND or "method-not-found" in self.message or "unknown method" in self.message


def socket_path() -> Path:
    return home.alpi_root() / "host" / "host.sock"


def daemon_present() -> bool:
    return socket_path().exists()


async def _open(path: Path):
    return await asyncio.open_unix_connection(str(path), limit=READ_LIMIT)


async def acall(method: str, params: dict[str, Any] | None = None, *, timeout: float = 5.0) -> Any:
    path = socket_path()
    if not path.exists():
        raise HostUnavailable("daemon not running")
    try:
        reader, writer = await asyncio.wait_for(_open(path), timeout)
    except (OSError, asyncio.TimeoutError) as e:
        raise HostUnavailable(str(e) or "daemon not running") from None
    request_id = f"tui-{next(_ids)}"
    try:
        writer.write((json.dumps({"id": request_id, "method": method, "params": params or {}}) + "\n").encode())
        await writer.drain()
        while True:
            raw = await asyncio.wait_for(reader.readline(), timeout)
            if not raw:
                raise HostUnavailable("daemon closed the connection")
            try:
                body = json.loads(raw.decode())
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(body, dict) or body.get("id") != request_id:
                continue
            if body.get("error"):
                err = body["error"] if isinstance(body["error"], dict) else {"message": str(body["error"])}
                raise HostError(err.get("code"), str(err.get("message") or "error"))
            return body.get("result")
    except (OSError, asyncio.TimeoutError) as e:
        raise HostUnavailable(str(e) or "daemon did not answer") from None
    except ValueError:
        raise HostError(None, INVALID_RESPONSE) from None
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
