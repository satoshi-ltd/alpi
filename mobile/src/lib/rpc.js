// auth_token injected into every request; daemon: alpi/host/server.py::_check_token.

export class RpcError extends Error {
  constructor(code, message, data) {
    super(message);
    this.code = code;
    this.data = data;
  }
}

export const AUTH_FAILED = -32000;

let _authFailedHandler = null;
export function setAuthFailedHandler(cb) {
  _authFailedHandler = cb;
}
// Handler scopes recovery to the failing endpoint — never unpair globally.
function maybeAuthFailed(err, endpoint, method) {
  if (err?.code === AUTH_FAILED && err?.message === 'auth-failed') {
    try {
      _authFailedHandler?.({ endpoint, method, reason: err?.data?.reason ?? null });
    } catch { /* */ }
  }
}

const REQUEST_TIMEOUT_MS = 10000;

function buildParams(endpoint, params) {
  const out = { ...(params || {}) };
  if (endpoint?.token) out.auth_token = endpoint.token;
  return out;
}

function endpointKey(endpoint) {
  return `${endpoint?.ip || ''}:${endpoint?.port || ''}|${endpoint?.token || ''}`;
}

function nextId() {
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Persistent WS pool per (ip, port, token), multiplexed by request id — saves the ~2 RTT handshake on every Tailscale RPC. Stream calls open their own socket.
const _pool = new Map();  // key -> Entry

function dropEntry(key, reason) {
  const entry = _pool.get(key);
  if (!entry) return;
  _pool.delete(key);
  entry.closed = true;
  for (const p of entry.pending.values()) {
    clearTimeout(p.timer);
    p.reject(reason || new RpcError(-32002, 'connection closed before response'));
  }
  entry.pending.clear();
  try { entry.ws.close(); } catch { /* */ }
}

function ensureEntry(endpoint) {
  const key = endpointKey(endpoint);
  let entry = _pool.get(key);
  if (entry && !entry.closed) return entry;

  const url = `ws://${endpoint.ip}:${endpoint.port}`;
  const ws = new WebSocket(url);
  entry = {
    key,
    ws,
    url,
    opened: false,
    closed: false,
    pending: new Map(),  // id -> { resolve, reject, timer, method, endpoint }
    sendQueue: [],
  };
  _pool.set(key, entry);

  ws.onopen = () => {
    entry.opened = true;
    for (const { id, payload } of entry.sendQueue) {
      // Skip queued payloads whose call already gave up (timeout/drop) — prevents late LATE-fire mutations.
      if (!entry.pending.has(id)) continue;
      try { ws.send(payload); } catch { /* surfaces via onclose */ }
    }
    entry.sendQueue = [];
  };

  ws.onmessage = (event) => {
    if (entry.closed) return;
    let body;
    try {
      body = JSON.parse(typeof event.data === 'string' ? event.data : '');
    } catch {
      // Malformed frame = server bug; drop the whole entry so callers reconnect cleanly.
      dropEntry(key, new RpcError(-32700, 'invalid JSON in response'));
      return;
    }
    const id = body.id;
    if (!id) return;
    const slot = entry.pending.get(id);
    if (!slot) return;  // late frame after timeout — discard
    if (body.error) {
      const err = new RpcError(body.error.code, body.error.message, body.error.data);
      maybeAuthFailed(err, slot.endpoint, slot.method);
      if (err.code === AUTH_FAILED) {
        dropEntry(key, err);
        return;
      }
      entry.pending.delete(id);
      clearTimeout(slot.timer);
      slot.reject(err);
      return;
    }
    entry.pending.delete(id);
    clearTimeout(slot.timer);
    slot.resolve(body.result);
  };

  ws.onerror = () => {
    dropEntry(key, new RpcError(-32001, `connection failed to ${url}`));
  };

  ws.onclose = () => {
    dropEntry(key, new RpcError(-32002, 'connection closed before response'));
  };

  return entry;
}

export async function call(endpoint, method, params = {}, options = {}) {
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const id = nextId();
  const payload = JSON.stringify({
    id, method, params: buildParams(endpoint, params),
  });

  return new Promise((resolve, reject) => {
    const entry = ensureEntry(endpoint);
    const timer = setTimeout(() => {
      const slot = entry.pending.get(id);
      if (!slot) return;
      entry.pending.delete(id);
      // A single timeout doesn't condemn the socket — only the call.
      reject(new RpcError(-32000, `request timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    entry.pending.set(id, { resolve, reject, timer, method, endpoint });

    if (entry.closed) {
      entry.pending.delete(id);
      clearTimeout(timer);
      reject(new RpcError(-32002, 'connection closed before response'));
      return;
    }
    if (entry.opened) {
      try {
        entry.ws.send(payload);
      } catch (e) {
        entry.pending.delete(id);
        clearTimeout(timer);
        reject(new RpcError(-32001, `send failed: ${e?.message || e}`));
      }
    } else {
      entry.sendQueue.push({ id, payload });
    }
  });
}

const STREAM_OPEN_TIMEOUT_MS = 8000;

// Stream sockets NOT pooled — chat is long-lived, must not contend with unary RPCs. `cancelMethod` opt-in (chat: 'host.chat.cancel').
export function callStream(endpoint, method, params, handlers) {
  const url = `ws://${endpoint.ip}:${endpoint.port}`;
  const ws = new WebSocket(url);
  const id = nextId();
  let closed = false;
  let opened = false;

  const close = () => {
    if (closed) return;
    closed = true;
    try { ws.close(); } catch {}
  };

  const openTimer = setTimeout(() => {
    if (opened || closed) return;
    closed = true;
    try { ws.close(); } catch {}
    handlers?.onError?.(new RpcError(-32001, `stream open timed out after ${STREAM_OPEN_TIMEOUT_MS}ms`));
  }, STREAM_OPEN_TIMEOUT_MS);

  ws.onopen = () => {
    opened = true;
    clearTimeout(openTimer);
    ws.send(JSON.stringify({
      id,
      method,
      params: buildParams(endpoint, { ...(params || {}), request_id: id }),
    }));
  };

  ws.onmessage = (event) => {
    if (closed) return;
    let body;
    try {
      body = JSON.parse(typeof event.data === 'string' ? event.data : '');
    } catch {
      handlers.onError?.(new RpcError(-32700, 'invalid JSON in frame'));
      close();
      return;
    }
    if (body.id !== id) return;
    if (body.error) {
      const err = new RpcError(body.error.code, body.error.message, body.error.data);
      maybeAuthFailed(err, endpoint, method);
      handlers.onError?.(err);
      close();
      return;
    }
    const ev = body.event;
    // Trap event:"error" BEFORE onFrame so consumers never see it as a regular frame.
    if (ev === 'error') {
      close();
      handlers.onError?.(new RpcError(-32003, body.text || 'stream error', body));
      return;
    }
    handlers.onFrame?.(body);
    if (ev === 'done' || ev === 'interrupted') {
      close();
      handlers.onDone?.(body);
    }
  };

  ws.onerror = () => {
    clearTimeout(openTimer);
    handlers.onError?.(new RpcError(-32001, `connection failed to ${url}`));
    close();
  };

  ws.onclose = () => {
    clearTimeout(openTimer);
    if (!closed) handlers.onError?.(new RpcError(-32002, 'connection closed before done'));
    closed = true;
  };

  return {
    requestId: id,
    cancel: () => {
      if (handlers?.cancelMethod) {
        call(endpoint, handlers.cancelMethod, { request_id: id }).catch(() => {});
      }
      close();
    },
    // Closes the WS without firing cancelMethod — use on unmount; cancel() only on explicit user action.
    detach: () => {
      close();
    },
  };
}

// Public: drop the pooled socket for one endpoint (call on unpair / endpoint change). Pending RPCs reject with "connection closed"; subsequent calls reconnect lazily.
export function dropEndpointPool(endpoint) {
  if (!endpoint) return;
  dropEntry(endpointKey(endpoint), new RpcError(-32002, 'endpoint dropped'));
}

// Test-only: drop all pool entries (callers should NOT depend on this in app code).
export function _resetPoolForTests() {
  for (const key of Array.from(_pool.keys())) {
    dropEntry(key, new RpcError(-32099, 'pool reset'));
  }
}
