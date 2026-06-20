import http.server
import ssl
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpcore
import httpx
import pytest

from alpi.tools import _pinned_dns


class _Recorder(httpcore.NetworkBackend):
    def __init__(self):
        self.calls: list[tuple[str, int]] = []

    def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        self.calls.append((host, port))
        raise httpcore.ConnectError("recorder — not actually connecting")

    def connect_unix_socket(self, *a, **k):
        raise NotImplementedError

    def sleep(self, seconds):
        return None


def test_pinned_backend_uses_pinned_ip_not_host():
    rec = _Recorder()
    backend = _pinned_dns._PinnedBackend({"example.com": ["93.184.216.34"]}, inner=rec)
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("example.com", 443)
    assert rec.calls == [("93.184.216.34", 443)]


def test_pinned_backend_refuses_unpinned_host():
    backend = _pinned_dns._PinnedBackend(
        {"example.com": ["93.184.216.34"]}, inner=_Recorder(),
    )
    with pytest.raises(httpcore.ConnectError, match="not in pinned DNS map"):
        backend.connect_tcp("evil.attacker.com", 443)


def test_pinned_backend_falls_back_to_second_ip_on_first_failure():
    state = {"calls": []}

    class _FailFirst(httpcore.NetworkBackend):
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            state["calls"].append(host)
            if host == "203.0.113.1":
                raise httpcore.ConnectError("simulated: IPv4-only network, AAAA unreachable")
            return f"connected:{host}:{port}"

        def connect_unix_socket(self, *a, **k): pass

        def sleep(self, s): pass

    backend = _pinned_dns._PinnedBackend(
        {"example.com": ["203.0.113.1", "198.51.100.7"]}, inner=_FailFirst(),
    )
    result = backend.connect_tcp("example.com", 443)
    assert result == "connected:198.51.100.7:443"
    assert state["calls"] == ["203.0.113.1", "198.51.100.7"]


def test_pinned_backend_shares_deadline_across_ip_attempts(monkeypatch):
    fake_now = [1000.0]
    monkeypatch.setattr(_pinned_dns.time, "monotonic", lambda: fake_now[0])

    state = {"calls": []}

    class _FakeClock(httpcore.NetworkBackend):
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            state["calls"].append((host, timeout))
            fake_now[0] += 0.4
            raise httpcore.ConnectError(f"down:{host}")

        def connect_unix_socket(self, *a, **k): pass

        def sleep(self, s): pass

    backend = _pinned_dns._PinnedBackend(
        {"example.com": ["1.1.1.1", "2.2.2.2", "3.3.3.3", "4.4.4.4"]},
        inner=_FakeClock(),
    )
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("example.com", 443, timeout=1.0)

    timeouts = [t for _h, t in state["calls"]]
    assert timeouts == pytest.approx([1.0, 0.6, 0.2])
    assert len(state["calls"]) == 3


def test_pinned_backend_no_timeout_passes_none_to_inner():
    state = {"calls": []}

    class _Recorder(httpcore.NetworkBackend):
        def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
            state["calls"].append((host, timeout))
            raise httpcore.ConnectError(f"down:{host}")

        def connect_unix_socket(self, *a, **k): pass

        def sleep(self, s): pass

    backend = _pinned_dns._PinnedBackend(
        {"example.com": ["1.1.1.1", "2.2.2.2"]},
        inner=_Recorder(),
    )
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp("example.com", 443, timeout=None)
    assert [t for _h, t in state["calls"]] == [None, None]


def test_pinned_backend_raises_when_all_ips_fail():
    class _AllFail(httpcore.NetworkBackend):
        def connect_tcp(self, host, port, **kw):
            raise httpcore.ConnectError(f"down:{host}")

        def connect_unix_socket(self, *a, **k): pass

        def sleep(self, s): pass

    backend = _pinned_dns._PinnedBackend(
        {"example.com": ["203.0.113.1", "198.51.100.7"]}, inner=_AllFail(),
    )
    with pytest.raises(httpcore.ConnectError, match="down:198.51.100.7"):
        backend.connect_tcp("example.com", 443)


def test_resolve_and_pin_accepts_literal_public_ip():
    ok, reason, host, ips = _pinned_dns.resolve_and_pin("https://93.184.216.34/x")
    assert ok, reason
    assert host == "93.184.216.34"
    assert ips == ["93.184.216.34"]


def test_resolve_and_pin_refuses_private_literal_ip():
    ok, reason, _h, _ips = _pinned_dns.resolve_and_pin("http://10.0.0.1/")
    assert not ok
    assert "private" in reason or "blocked" in reason


def test_resolve_and_pin_refuses_metadata_host():
    ok, reason, _h, _ips = _pinned_dns.resolve_and_pin("http://metadata.google.internal/")
    assert not ok
    assert "metadata" in reason


def test_resolve_and_pin_refuses_unsupported_scheme():
    ok, reason, _h, _ips = _pinned_dns.resolve_and_pin("file:///etc/passwd")
    assert not ok
    assert "scheme" in reason


def test_resolve_and_pin_returns_all_validated_public_ips(monkeypatch):
    def fake_getaddrinfo(host, port):
        assert host == "example.com"
        return [
            (0, 0, 0, "", ("203.0.113.5", 0)),
            (0, 0, 0, "", ("198.51.100.7", 0)),
        ]
    monkeypatch.setattr(_pinned_dns.socket, "getaddrinfo", fake_getaddrinfo)
    ok, reason, host, ips = _pinned_dns.resolve_and_pin("https://example.com/")
    assert ok, reason
    assert host == "example.com"
    assert ips == ["203.0.113.5", "198.51.100.7"]


def test_resolve_and_pin_refuses_if_any_resolved_ip_is_private(monkeypatch):
    def fake_getaddrinfo(host, port):
        return [
            (0, 0, 0, "", ("203.0.113.5", 0)),
            (0, 0, 0, "", ("10.0.0.5", 0)),
        ]
    monkeypatch.setattr(_pinned_dns.socket, "getaddrinfo", fake_getaddrinfo)
    ok, reason, _h, _ips = _pinned_dns.resolve_and_pin("https://rebind.example.com/")
    assert not ok
    assert "10.0.0.5" in reason or "private" in reason


def test_dns_rebinding_after_validation_cannot_reach_private_ip(monkeypatch):
    state = {"call": 0}

    def fake_getaddrinfo(host, port):
        state["call"] += 1
        if state["call"] == 1:
            return [(0, 0, 0, "", ("203.0.113.5", 0))]
        return [(0, 0, 0, "", ("10.0.0.99", 0))]

    monkeypatch.setattr(_pinned_dns.socket, "getaddrinfo", fake_getaddrinfo)
    ok, _reason, host, ips = _pinned_dns.resolve_and_pin("https://rebind.example.com/")
    assert ok and host == "rebind.example.com" and ips == ["203.0.113.5"]

    rec = _Recorder()
    backend = _pinned_dns._PinnedBackend({host: ips}, inner=rec)
    with pytest.raises(httpcore.ConnectError):
        backend.connect_tcp(host, 443)
    assert rec.calls == [("203.0.113.5", 443)]


def test_safe_client_end_to_end_against_loopback_server():
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"pinned ok")

        def log_message(self, *a, **k):
            pass

    httpd = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{port}/"
        ok, reason, client = _pinned_dns.safe_client(url, allow_loopback=True, timeout=5)
        assert ok, reason
        with client:
            r = client.get(url)
        assert r.status_code == 200
        assert r.text == "pinned ok"
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_safe_client_returns_none_for_blocked_url():
    ok, reason, client = _pinned_dns.safe_client("http://192.168.1.1/")
    assert not ok
    assert client is None
    assert reason


def _selfsigned_cert(hostname: str, tmp_path: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, hostname)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=365))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(hostname)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path


def test_pinned_https_uses_hostname_for_sni_and_cert(tmp_path):
    hostname = "example.test"
    cert_path, key_path = _selfsigned_cert(hostname, tmp_path)

    received_sni: dict[str, str] = {}

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"https ok")

        def log_message(self, *a, **k):
            pass

    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))

    def _sni_cb(sock, name, _ctx):
        if name:
            received_sni["value"] = name

    ssl_ctx.set_servername_callback(_sni_cb)

    httpd = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    httpd.socket = ssl_ctx.wrap_socket(httpd.socket, server_side=True)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        client_ssl_ctx = ssl.create_default_context(cafile=str(cert_path))
        transport = _pinned_dns.make_pinned_transport(
            {hostname: ["127.0.0.1"]},
            verify=client_ssl_ctx,
        )
        client = httpx.Client(transport=transport, timeout=5)
        with client:
            r = client.get(f"https://{hostname}:{port}/")
        assert r.status_code == 200
        assert r.text == "https ok"
        assert received_sni.get("value") == hostname, (
            f"SNI was {received_sni.get('value')!r}, expected {hostname!r} — pinning leaked the IP to SNI"
        )
    finally:
        httpd.shutdown()
        httpd.server_close()
