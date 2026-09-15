// auth_token injected into every request; daemon: alpi/host/server.py::_check_token.
import { endpointUrl } from './endpoint.js';
import {
  CLOSE_AFTER_ERROR_GRACE_MS,
  RATE_LIMITED,
  RATE_LIMITED_CLOSE_CODE,
  RATE_LIMITED_CLOSE_REASON,
  RATE_LIMITED_HOLD_MS,
  RATE_LIMITED_MESSAGE,
  isRateLimitedClose,
} from './rateLimit.js';

export { RATE_LIMITED, RATE_LIMITED_MESSAGE };

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

let _rateLimitedHandler = null;
export function setRateLimitedHandler(cb) {
  _rateLimitedHandler = cb;
}
function maybeRateLimited(err, endpoint) {
  if (err?.code !== RATE_LIMITED) return;
  try {
    _rateLimitedHandler?.({ endpoint });
  } catch { /* */ }
}

// Only 1013 + the daemon's reason means throttling; every other close keeps the generic transport error.
function closeError(event, fallback) {
  if (!isRateLimitedClose(event)) return fallback;
  return rateLimitedError(event.code);
}

function rateLimitedError(closeCode = RATE_LIMITED_CLOSE_CODE) {
  return new RpcError(RATE_LIMITED, RATE_LIMITED_MESSAGE, {
    close_code: closeCode,
    reason: RATE_LIMITED_CLOSE_REASON,
  });
}

const _heldUntil = new Map();  // endpointKey -> ms timestamp

function holdRateLimited(key) {
  _heldUntil.set(key, Date.now() + RATE_LIMITED_HOLD_MS);
}

function isHeld(key) {
  const until = _heldUntil.get(key);
  if (!until) return false;
  if (Date.now() >= until) {
    _heldUntil.delete(key);
    return false;
  }
  return true;
}

// Only time or dropping the endpoint lifts the hold: an answer on a socket opened before the block says nothing about whether new ones are accepted.
function releaseRateLimited(key) {
  _heldUntil.delete(key);
}

const _openStreams = new Map();  // endpointKey -> count of authenticated stream sockets

function reusableEntry(key) {
  const entry = _pool.get(key);
  if (!entry || entry.closed) return null;
  return Date.now() - entry.lastSeen < STALE_SOCKET_MS ? entry : null;
}

// True while another socket for this endpoint is authenticated and carrying traffic: one rejected new socket is not a dead host. A socket that only completed its handshake proves nothing about the token.
export function hasLiveSocket(endpoint) {
  const key = endpointKey(endpoint);
  if ((_openStreams.get(key) ?? 0) > 0) return true;
  const entry = reusableEntry(key);
  return !!entry && entry.authenticated === true;
}

const REQUEST_TIMEOUT_MS = 10000;
// Only inbound frames refresh lastSeen — a send succeeds on a silently broken path (NAT/DERP drop) and would mask the death.
const STALE_SOCKET_MS = 30000;

function buildParams(endpoint, params) {
  const out = { ...(params || {}) };
  if (endpoint?.token) out.auth_token = endpoint.token;
  return out;
}

function endpointKey(endpoint) {
  return `${endpointUrl(endpoint)}|${endpoint?.token || ''}`;
}

function nextId() {
  return `m-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

// Persistent WS pool per (ip, port, token), multiplexed by request id — saves the ~2 RTT handshake on every Tailscale RPC. Stream calls open their own socket.
const _pool = new Map();  // key -> Entry

function settleEntry(entry, reason) {
  if (entry.closed) return;
  entry.closed = true;
  for (const p of entry.pending.values()) {
    clearTimeout(p.timer);
    p.reject(reason || new RpcError(-32002, 'connection closed before response'));
  }
  entry.pending.clear();
  try { entry.ws.close(); } catch { /* */ }
}

function dropEntry(key, reason) {
  const entry = _pool.get(key);
  if (!entry) return;
  _pool.delete(key);
  settleEntry(entry, reason);
}

function closeIfDrained(entry) {
  if (entry.retired && entry.pending.size === 0) settleEntry(entry, null);
}

function ensureEntry(endpoint) {
  const key = endpointKey(endpoint);
  const reusable = reusableEntry(key);
  if (reusable) return reusable;
  let entry = _pool.get(key);
  if (entry && !entry.closed) {
    _pool.delete(key);
    if (entry.pending.size > 0) entry.retired = true;
    else settleEntry(entry, new RpcError(-32002, `connection to ${entry.url} went stale`));
  }

  const url = endpointUrl(endpoint);
  const ws = new WebSocket(url);
  entry = {
    key,
    ws,
    url,
    endpoint,
    opened: false,
    closed: false,
    retired: false,
    authenticated: false,
    lastSeen: Date.now(),
    pending: new Map(),  // id -> { resolve, reject, timer, method, endpoint }
    sendQueue: [],
  };
  _pool.set(key, entry);

  // A discarded entry's late events must never evict its replacement under the same key.
  const dropSocket = (reason) => {
    if (_pool.get(key) === entry) _pool.delete(key);
    settleEntry(entry, reason);
  };

  ws.onopen = () => {
    entry.opened = true;
    entry.lastSeen = Date.now();
    for (const { id, payload } of entry.sendQueue) {
      // Skip queued payloads whose call already gave up (timeout/drop) — prevents late LATE-fire mutations.
      if (!entry.pending.has(id)) continue;
      try { ws.send(payload); } catch { /* surfaces via onclose */ }
    }
    entry.sendQueue = [];
  };

  ws.onmessage = (event) => {
    if (entry.closed) return;
    entry.lastSeen = Date.now();
    let body;
    try {
      body = JSON.parse(typeof event.data === 'string' ? event.data : '');
    } catch {
      // Malformed frame = server bug; drop the whole entry so callers reconnect cleanly.
      dropSocket(new RpcError(-32700, 'invalid JSON in response'));
      return;
    }
    const id = body.id;
    if (!id) return;
    const slot = entry.pending.get(id);
    if (!slot) return;  // late frame after timeout — discard
    if (body.error) {
      const err = new RpcError(body.error.code, body.error.message, body.error.data);
      // Any answer the daemon routed to a handler proves this socket is past authentication.
      if (err.code !== AUTH_FAILED && err.code !== RATE_LIMITED) entry.authenticated = true;
      maybeAuthFailed(err, slot.endpoint, slot.method);
      if (err.code === AUTH_FAILED) {
        dropSocket(err);
        return;
      }
      entry.pending.delete(id);
      clearTimeout(slot.timer);
      slot.reject(err);
      closeIfDrained(entry);
      return;
    }
    entry.pending.delete(id);
    clearTimeout(slot.timer);
    entry.authenticated = true;
    slot.resolve(body.result);
    closeIfDrained(entry);
  };

  // onerror arrives before the close frame is parsed; settling here would drop the daemon's close reason, so it only arms a fallback.
  ws.onerror = () => {
    if (entry.closed) return;
    entry.pendingError = new RpcError(-32001, `connection failed to ${url}`);
    entry.graceTimer = setTimeout(() => finish(entry.pendingError), CLOSE_AFTER_ERROR_GRACE_MS);
  };

  const finish = (err) => {
    if (entry.closed) return;
    clearTimeout(entry.graceTimer);
    if (err?.code === RATE_LIMITED) holdRateLimited(key);
    // Retire the socket first: a handler asking whether the endpoint still has a live socket must not be answered by the one that just died.
    dropSocket(err);
    maybeRateLimited(err, entry.endpoint);
  };

  ws.onclose = (event) => {
    finish(closeError(event, entry.pendingError ?? new RpcError(-32002, 'connection closed before response')));
  };

  return entry;
}

export async function call(endpoint, method, params = {}, options = {}) {
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const id = nextId();
  const payload = JSON.stringify({
    id, method, params: buildParams(endpoint, params),
  });

  // The hold exists to stop new sockets, not to cut an authenticated one — cancelling a turn must still get through.
  const poolKey = endpointKey(endpoint);
  if (!reusableEntry(poolKey) && isHeld(poolKey)) {
    return Promise.reject(rateLimitedError());
  }

  return new Promise((resolve, reject) => {
    const entry = ensureEntry(endpoint);
    const timer = setTimeout(() => {
      const slot = entry.pending.get(id);
      if (!slot) return;
      entry.pending.delete(id);
      closeIfDrained(entry);
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
  const url = endpointUrl(endpoint);
  const key = endpointKey(endpoint);
  if (isHeld(key)) {
    handlers?.onError?.(rateLimitedError());
    return { requestId: null, cancel: () => {}, detach: () => {} };
  }
  const ws = new WebSocket(url);
  const id = nextId();
  let closed = false;
  let opened = false;
  let live = false;
  let pendingError = null;
  let graceTimer = null;
  let openTimer = null;

  // A stream counts as live only once the daemon answers it: a socket waiting on its handshake proves nothing about the token.
  const markLive = () => {
    if (live || closed) return;
    live = true;
    _openStreams.set(key, (_openStreams.get(key) ?? 0) + 1);
  };

  // Every exit runs through here, so a timeout can never leave the endpoint counted as live.
  const close = () => {
    if (closed) return;
    closed = true;
    clearTimeout(graceTimer);
    clearTimeout(openTimer);
    if (live) {
      live = false;
      const left = (_openStreams.get(key) ?? 1) - 1;
      if (left > 0) _openStreams.set(key, left);
      else _openStreams.delete(key);
    }
    try { ws.close(); } catch {}
  };

  // One terminal outcome per stream, whatever order error/close events arrive in.
  const fail = (err) => {
    if (closed) return;
    if (err?.code === RATE_LIMITED) holdRateLimited(key);
    close();
    maybeRateLimited(err, endpoint);
    handlers?.onError?.(err);
  };

  openTimer = setTimeout(() => {
    if (opened || closed) return;
    fail(new RpcError(-32001, `stream open timed out after ${STREAM_OPEN_TIMEOUT_MS}ms`));
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
      fail(new RpcError(-32700, 'invalid JSON in frame'));
      return;
    }
    if (body.id !== id) return;
    if (body.error) {
      const err = new RpcError(body.error.code, body.error.message, body.error.data);
      if (err.code !== AUTH_FAILED && err.code !== RATE_LIMITED) markLive();
      maybeAuthFailed(err, endpoint, method);
      fail(err);
      return;
    }
    markLive();
    const ev = body.event;
    // Trap event:"error" BEFORE onFrame so consumers never see it as a regular frame.
    if (ev === 'error') {
      fail(new RpcError(-32003, body.text || 'stream error', body));
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
    if (closed) return;
    pendingError = new RpcError(-32001, `connection failed to ${url}`);
    graceTimer = setTimeout(() => fail(pendingError), CLOSE_AFTER_ERROR_GRACE_MS);
  };

  ws.onclose = (event) => {
    clearTimeout(openTimer);
    fail(closeError(event, pendingError ?? new RpcError(-32002, 'connection closed before done')));
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
  const key = endpointKey(endpoint);
  releaseRateLimited(key);
  _openStreams.delete(key);
  dropEntry(key, new RpcError(-32002, 'endpoint dropped'));
}

// Test-only: drop all pool entries (callers should NOT depend on this in app code).
export function _resetPoolForTests() {
  _heldUntil.clear();
  _openStreams.clear();
  for (const key of Array.from(_pool.keys())) {
    dropEntry(key, new RpcError(-32099, 'pool reset'));
  }
}
