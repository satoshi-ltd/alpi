"""Bounded, sanitised evidence from the interactive browser context."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import time
import uuid
import tempfile
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from alpi.tools._paths import resolve_workspace_path

_LIMIT = 2000
_BODY_LIMIT = 256 * 1024


def safe_url(url: str) -> dict:
    parsed = urlsplit(url)
    segments = [s if not s or re.fullmatch(r"[A-Za-z_-]{1,40}(?:\.[A-Za-z]{1,8})?", s) else ":value" for s in parsed.path.split("/")]
    return {"origin": f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else ""),
            "path": "/".join(segments)[:512],
            "query_names": sorted({k for k, _ in parse_qsl(parsed.query) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", k)})[:40]}


def body_evidence(raw: bytes, secret: bytes) -> dict:
    if len(raw) > _BODY_LIMIT:
        return {"omitted": "body exceeds 256 KiB"}
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return {"omitted": "not JSON"}
    remaining = 500
    truncated = False
    def scrub(item, key="", depth=0):
        nonlocal remaining, truncated
        remaining -= 1
        if remaining < 0 or depth > 8:
            truncated = True
            return "[truncated]"
        if re.search(r"password|secret|token|authorization|cookie|card|cvv|cvc|email|phone|address|firstname|lastname|fullname", key, re.I):
            return "[redacted]"
        if isinstance(item, dict):
            truncated = truncated or len(item) > 80
            return {(k if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]{0,63}", k) else "[key]"): scrub(v, k, depth + 1) for k, v in list(item.items())[:80]}
        if isinstance(item, list):
            truncated = truncated or len(item) > 40
            return [scrub(v, key, depth + 1) for v in item[:40]]
        if item is None or isinstance(item, bool):
            return item
        if isinstance(item, (int, float)) and key.lower() in {"amount", "amountraw", "total", "totalprice", "price", "tax", "taxes", "nights", "quantity", "adults", "children", "count"}:
            return item
        if isinstance(item, str) and ((key.lower() == "currency" and re.fullmatch(r"[A-Z]{3}", item)) or (key.lower() in {"status", "state"} and item.lower() in {"ok", "success", "failed", "pending", "confirmed", "cancelled", "available", "unavailable", "prereserved"})):
            return item
        return "ref:" + hmac.new(secret, str(item).encode(), hashlib.sha256).hexdigest()[:16]
    return {"json": scrub(value), "truncated": truncated}


class BrowserTrace:
    def __init__(self, context):
        self.context = context
        self.secret = secrets.token_bytes(32)
        self.path = resolve_workspace_path(f".browser-traces/{uuid.uuid4().hex}.json", for_write=True)
        self.started = time.time()
        self.rows = []
        self.steps = []
        self.pending = {}
        self.truncated = False
        self.confirmed = False
        self.closed = False
        self.error = False
        self.body_bytes = 0
        self.listeners = [("request", self.request), ("requestfinished", self.finished), ("requestfailed", self.failed)]
        self.save()
        for event, listener in self.listeners:
            context.on(event, listener)

    def body(self, raw):
        evidence = body_evidence(raw, self.secret)
        size = len(json.dumps(evidence).encode())
        if self.body_bytes + size > 4 * 1024 * 1024:
            return {"omitted": "trace body budget exhausted"}
        self.body_bytes += size
        return evidence

    def request(self, request):
        if len(self.rows) >= _LIMIT:
            self.truncated = True
            return
        row = {"id": len(self.rows) + 1, "step": len(self.steps), "ms": round((time.time() - self.started) * 1000),
               "method": request.method, **safe_url(request.url), "type": request.resource_type}
        try:
            raw = request.post_data_buffer
            if raw:
                row["request_body"] = self.body(raw)
        except Exception:
            row["request_body"] = {"omitted": "unavailable"}
        self.rows.append(row)
        self.pending[request] = row

    def finished(self, request):
        row = self.pending.pop(request, None)
        if row is None:
            return
        try:
            response = request.response()
            row["status"] = response.status
            headers = response.headers
            row["security_headers"] = sorted(k for k in headers if k in {"content-security-policy", "strict-transport-security", "x-frame-options", "x-content-type-options", "referrer-policy"})
            if request.resource_type in {"xhr", "fetch"} and "json" in headers.get("content-type", ""):
                length = headers.get("content-length")
                if length and length.isdigit() and int(length) <= _BODY_LIMIT:
                    row["response_body"] = self.body(response.body())
                else:
                    row["response_body"] = {"omitted": "unknown or excessive content length"}
        except Exception:
            row["response_body"] = {"omitted": "unavailable"}

    def failed(self, request):
        row = self.pending.pop(request, None)
        if row is not None:
            row["failed"] = True

    def step(self, action: str, ok: bool):
        if len(self.steps) >= 500:
            self.truncated = True
        else:
            self.steps.append({"action": action, "ok": ok, "ms": round((time.time() - self.started) * 1000)})
        try:
            self.save()
        except Exception:
            self.error = True

    def report(self):
        navigated = any(s["action"] == "navigate" and s["ok"] for s in self.steps)
        return {"schema": "alpi.browser.trace.v1", "started_at": self.started, "closed": self.closed,
                "requests": self.rows, "steps": self.steps, "truncated": self.truncated,
                "confirmation_observed": self.confirmed, "pending_requests": len(self.pending),
                "flow_complete": self.closed and self.confirmed and navigated and not self.truncated and not self.error and not any(r.get("type") in {"document", "xhr", "fetch"} for r in self.pending.values()) and not any(r.get("type") in {"document", "xhr", "fetch"} and (r.get("failed") or r.get("status", 0) >= 400) for r in self.rows) and all(s["ok"] for s in self.steps)}

    def save(self):
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as f:
                temporary = Path(f.name)
                os.chmod(temporary, 0o600)
                json.dump(self.report(), f)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def close(self, confirmed=False):
        for event, listener in self.listeners:
            self.context.remove_listener(event, listener)
        self.confirmed = confirmed
        self.closed = True
        self.save()
        return {"path": str(self.path), "requests": len(self.rows), "flow_complete": self.report()["flow_complete"], "confirmation_observed": confirmed}
