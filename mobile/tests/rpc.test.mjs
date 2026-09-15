// Node-runnable test for src/lib/rpc.js — pool + multiplex + cleanup.
//   $ node mobile/tests/rpc.test.mjs
import assert from 'node:assert/strict';

// React Native ships its own WebSocket; in Node we stub a minimal one before importing the module under test so the pool sees our shim.
let nextWs = null;
class FakeWs {
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.readyState = 0;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    this.onclose = null;
    nextWs = this;
  }
  send(data) {
    this.sent.push(data);
  }
  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }
  // Test helpers — drive the lifecycle from outside.
  open() {
    this.readyState = 1;
    if (this.onopen) this.onopen();
  }
  message(payload) {
    if (this.onmessage) this.onmessage({ data: JSON.stringify(payload) });
  }
  closeWith(code, reason) {
    this.readyState = 3;
    if (this.onclose) this.onclose({ code, reason });
  }
}
globalThis.WebSocket = FakeWs;

const { call, callStream, dropEndpointPool, hasLiveSocket, setAuthFailedHandler, setRateLimitedHandler, RATE_LIMITED, RATE_LIMITED_MESSAGE, _resetPoolForTests } = await import('../src/lib/rpc.js');
const { RATE_LIMITED_HOLD_MS, CLOSE_AFTER_ERROR_GRACE_MS } = await import('../src/lib/rateLimit.js');

const realNow = Date.now;
async function atTime(ms, fn) {
  Date.now = () => ms;
  try { return await fn(); } finally { Date.now = realNow; }
}
const settle = (ms = CLOSE_AFTER_ERROR_GRACE_MS + 20) => new Promise((r) => setTimeout(r, ms));

let passed = 0;
let failed = 0;
function test(name, fn) {
  return Promise.resolve()
    .then(fn)
    .then(() => {
      console.log(`ok   ${name}`);
      passed++;
    })
    .catch((err) => {
      console.error(`FAIL ${name}\n     ${err.message}`);
      failed++;
    });
}

const endpoint = { ip: '127.0.0.1', port: 9999, token: 't' };

await test('wss endpoints are passed to the native WebSocket unchanged', async () => {
  _resetPoolForTests();
  nextWs = null;
  const secure = { url: 'wss://client.example.com', token: 'secure' };
  const pending = call(secure, 'host.echo', {});
  const ws = nextWs;
  assert.strictEqual(ws.url, 'wss://client.example.com');
  ws.open();
  ws.message({ id: JSON.parse(ws.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await pending, { ok: true });
});

await test('two concurrent calls share one ws and resolve by id', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p1 = call(endpoint, 'host.echo', { x: 1 });
  // First call creates the ws; second must reuse it (no new instance).
  const ws = nextWs;
  assert.ok(ws);
  const wsBefore = ws;
  const p2 = call(endpoint, 'host.echo', { x: 2 });
  assert.strictEqual(nextWs, wsBefore, 'second call must reuse pooled ws');
  ws.open();
  // After open both queued payloads should have been flushed.
  assert.strictEqual(ws.sent.length, 2);
  const ids = ws.sent.map((s) => JSON.parse(s).id);
  ws.message({ id: ids[1], result: { got: 2 } });
  ws.message({ id: ids[0], result: { got: 1 } });
  const [r1, r2] = await Promise.all([p1, p2]);
  assert.deepStrictEqual(r1, { got: 1 });
  assert.deepStrictEqual(r2, { got: 2 });
});

await test('per-request timeout rejects only that call', async () => {
  _resetPoolForTests();
  nextWs = null;
  const slow = call(endpoint, 'host.slow', {}, { timeoutMs: 50 });
  const fast = call(endpoint, 'host.fast', {});
  nextWs.open();
  const fastId = JSON.parse(nextWs.sent[1]).id;
  // Resolve fast immediately.
  nextWs.message({ id: fastId, result: { ok: true } });
  assert.deepStrictEqual(await fast, { ok: true });
  // slow should reject after timeout, but the pool/ws stays alive.
  await assert.rejects(slow, /timed out/);
  // Pool entry should still be reusable.
  const next = call(endpoint, 'host.again', {});
  nextWs.message({ id: JSON.parse(nextWs.sent[2]).id, result: { again: true } });
  assert.deepStrictEqual(await next, { again: true });
});

await test('pre-open timeout does NOT fire the queued payload when ws opens late', async () => {
  // P0: a mutation timing out before the WS handshake completes could still
  // ship if the queued payload survived in sendQueue. Verify the queue skips
  // it now (entry.pending.delete on timeout is the gate).
  _resetPoolForTests();
  nextWs = null;
  const slow = call(endpoint, 'host.workgroup.post', { wg_id: 'x', text: 'mutation' }, { timeoutMs: 30 });
  const ws = nextWs;
  assert.ok(ws);
  assert.strictEqual(ws.sent.length, 0);  // socket still opening
  await assert.rejects(slow, /timed out/);
  ws.open();
  // The queued payload must have been skipped — nothing should reach the server.
  assert.strictEqual(ws.sent.length, 0,
    `expected no sends after pre-open timeout; got ${ws.sent.length}`);
  // Pool entry stays usable for the next call.
  const ok = call(endpoint, 'host.echo', {});
  ws.message({ id: JSON.parse(ws.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await ok, { ok: true });
});

await test('close rejects all pending and clears pool', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p = call(endpoint, 'host.never', {});
  nextWs.open();
  nextWs.close();
  await assert.rejects(p, /closed before response/);
  // Subsequent call must create a NEW ws (pool entry was dropped).
  const wsBefore = nextWs;
  const p2 = call(endpoint, 'host.again', {});
  assert.notStrictEqual(nextWs, wsBefore);
  nextWs.open();
  nextWs.message({ id: JSON.parse(nextWs.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await p2, { ok: true });
});

await test('dropEndpointPool rejects pending + drops socket', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p = call(endpoint, 'host.never', {});
  nextWs.open();
  const wsBefore = nextWs;
  dropEndpointPool(endpoint);
  await assert.rejects(p, /endpoint dropped/);
  // Next call must create a fresh ws.
  const p2 = call(endpoint, 'host.again', {});
  assert.notStrictEqual(nextWs, wsBefore);
  nextWs.open();
  nextWs.message({ id: JSON.parse(nextWs.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await p2, { ok: true });
});

await test('auth-failed drops pool so next call reconnects', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p = call(endpoint, 'host.protected', {});
  nextWs.open();
  const id = JSON.parse(nextWs.sent[0]).id;
  nextWs.message({ id, error: { code: -32000, message: 'auth-failed' } });
  await assert.rejects(p, /auth-failed/);
  const wsBefore = nextWs;
  const p2 = call(endpoint, 'host.again', {});
  assert.notStrictEqual(nextWs, wsBefore, 'auth-failed must invalidate the pooled ws');
  nextWs.open();
  nextWs.message({ id: JSON.parse(nextWs.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await p2, { ok: true });
});

await test('a socket unseen past the staleness window is replaced for new calls', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const first = call(endpoint, 'host.echo', {});
    const ws = nextWs;
    ws.open();
    ws.message({ id: JSON.parse(ws.sent[0]).id, result: { ok: true } });
    assert.deepStrictEqual(await first, { ok: true });
    Date.now = () => realNow() + 31000;
    const fresh = call(endpoint, 'host.list', {});
    assert.notStrictEqual(nextWs, ws, 'stale ws must be replaced, not reused');
    assert.strictEqual(ws.readyState, 3, 'a stale socket with nothing in flight must be closed');
    nextWs.open();
    nextWs.message({ id: JSON.parse(nextWs.sent[0]).id, result: { ok: true } });
    assert.deepStrictEqual(await fresh, { ok: true });
  } finally {
    Date.now = realNow;
  }
});

await test('the staleness sweep does not kill a request that is still in flight', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const upload = call(endpoint, 'host.upload', { photo: 'x' }, { timeoutMs: 60000 });
    const wsBefore = nextWs;
    wsBefore.open();
    const uploadId = JSON.parse(wsBefore.sent[0]).id;
    Date.now = () => realNow() + 31000;
    const other = call(endpoint, 'host.list', {});
    assert.notStrictEqual(nextWs, wsBefore, 'the new call still gets a fresh socket');
    nextWs.open();
    nextWs.message({ id: JSON.parse(nextWs.sent[0]).id, result: { listed: true } });
    assert.deepStrictEqual(await other, { listed: true });
    wsBefore.message({ id: uploadId, result: { uploaded: true } });
    assert.deepStrictEqual(await upload, { uploaded: true });
  } finally {
    Date.now = realNow;
  }
});

await test('a retired socket closes once its last in-flight call settles', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const upload = call(endpoint, 'host.upload', {}, { timeoutMs: 60000 });
    const wsBefore = nextWs;
    wsBefore.open();
    const uploadId = JSON.parse(wsBefore.sent[0]).id;
    Date.now = () => realNow() + 31000;
    call(endpoint, 'host.list', {}).catch(() => {});
    assert.strictEqual(wsBefore.readyState, 1, 'retired socket stays open while it owes a response');
    wsBefore.message({ id: uploadId, result: { uploaded: true } });
    await upload;
    assert.strictEqual(wsBefore.readyState, 3, 'retired socket must not leak past its last call');
  } finally {
    Date.now = realNow;
  }
});

await test('a retired socket that really is dead still rejects the call it was carrying', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const upload = call(endpoint, 'host.upload', {}, { timeoutMs: 60000 });
    const wsBefore = nextWs;
    wsBefore.open();
    Date.now = () => realNow() + 31000;
    const other = call(endpoint, 'host.list', {});
    const wsAfter = nextWs;
    wsBefore.close();
    await assert.rejects(upload, /closed before response/);
    wsAfter.open();
    wsAfter.message({ id: JSON.parse(wsAfter.sent[0]).id, result: { listed: true } });
    assert.deepStrictEqual(await other, { listed: true });
  } finally {
    Date.now = realNow;
  }
});

await test('a retired socket that never answers rejects on its own budget, not the sweep', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const upload = call(endpoint, 'host.upload', {}, { timeoutMs: 40 });
    const wsBefore = nextWs;
    wsBefore.open();
    Date.now = () => realNow() + 31000;
    call(endpoint, 'host.list', {}).catch(() => {});
    await assert.rejects(upload, /timed out/);
    assert.strictEqual(wsBefore.readyState, 3, 'a timed-out retired socket must still be closed');
  } finally {
    Date.now = realNow;
  }
});

await test('inbound frames keep a live socket out of the staleness sweep', async () => {
  _resetPoolForTests();
  nextWs = null;
  const realNow = Date.now;
  try {
    const first = call(endpoint, 'host.echo', {});
    const ws = nextWs;
    ws.open();
    Date.now = () => realNow() + 25000;
    ws.message({ id: JSON.parse(ws.sent[0]).id, result: { ok: true } });
    assert.deepStrictEqual(await first, { ok: true });
    Date.now = () => realNow() + 50000;
    const second = call(endpoint, 'host.echo', {});
    assert.strictEqual(nextWs, ws, 'a socket seen alive inside the window must be reused');
    ws.message({ id: JSON.parse(ws.sent[1]).id, result: { again: true } });
    assert.deepStrictEqual(await second, { again: true });
  } finally {
    Date.now = realNow;
  }
});

await test('connection-disabled reports its reason without masquerading as rejection', async () => {
  _resetPoolForTests();
  nextWs = null;
  const failures = [];
  setAuthFailedHandler((failure) => { failures.push(failure); });
  const p = call(endpoint, 'host.protected', {});
  nextWs.open();
  const id = JSON.parse(nextWs.sent[0]).id;
  nextWs.message({
    id,
    error: {
      code: -32000,
      message: 'auth-failed',
      data: { reason: 'connection-disabled' },
    },
  });
  await assert.rejects(p, /auth-failed/);
  assert.strictEqual(failures.length, 1);
  assert.strictEqual(failures[0].reason, 'connection-disabled');
  setAuthFailedHandler(null);
});

await test('a 1013 auth-rate-limited close rejects with the rate-limited error and notifies the handler', async () => {
  _resetPoolForTests();
  nextWs = null;
  const seen = [];
  setRateLimitedHandler((info) => { seen.push(info); });
  const ep = { id: 'ep-1', ip: '127.0.0.1', port: 9999, token: 't' };
  const p = call(ep, 'host.ping', {});
  nextWs.closeWith(1013, 'auth-rate-limited');
  await assert.rejects(p, (err) => (
    err.code === RATE_LIMITED
    && err.message === RATE_LIMITED_MESSAGE
    && err.data.reason === 'auth-rate-limited'
    && err.data.close_code === 1013
  ));
  assert.strictEqual(seen.length, 1);
  assert.strictEqual(seen[0].endpoint.id, 'ep-1');
  setRateLimitedHandler(null);
});

await test('any other 1013 close stays a generic connection-closed error', async () => {
  _resetPoolForTests();
  nextWs = null;
  const seen = [];
  setRateLimitedHandler((info) => { seen.push(info); });
  const p = call(endpoint, 'host.ping', {});
  nextWs.closeWith(1013, 'Device connection limit reached');
  await assert.rejects(p, (err) => err.code === -32002 && /connection closed/.test(err.message));
  assert.strictEqual(seen.length, 0);
  setRateLimitedHandler(null);
});

await test('a later generic transport error does not overwrite the rate-limited rejection', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p = call(endpoint, 'host.ping', {});
  const ws = nextWs;
  ws.closeWith(1013, 'auth-rate-limited');
  if (ws.onerror) ws.onerror();
  ws.closeWith(1006, '');
  await assert.rejects(p, (err) => err.code === RATE_LIMITED && err.message === RATE_LIMITED_MESSAGE);
});

await test('stream sockets surface the throttle once through onError', async () => {
  _resetPoolForTests();
  nextWs = null;
  const errors = [];
  callStream(endpoint, 'host.chat.send', { text: 'hi' }, { onError: (e) => errors.push(e), onFrame: () => {}, onDone: () => {} });
  const ws = nextWs;
  ws.closeWith(1013, 'auth-rate-limited');
  if (ws.onerror) ws.onerror();
  ws.closeWith(1006, '');
  assert.strictEqual(errors.length, 1);
  assert.strictEqual(errors[0].code, RATE_LIMITED);
  assert.strictEqual(errors[0].message, RATE_LIMITED_MESSAGE);
});

await test('a generic onerror before the close frame does not lose the daemon reason, and settles once', async () => {
  _resetPoolForTests();
  nextWs = null;
  const rejections = [];
  const p = call(endpoint, 'host.ping', {}).catch((e) => { rejections.push(e); });
  const ws = nextWs;
  ws.onerror();
  ws.closeWith(1013, 'auth-rate-limited');
  ws.closeWith(1006, '');
  await p;
  await settle();
  assert.strictEqual(rejections.length, 1);
  assert.strictEqual(rejections[0].code, RATE_LIMITED);
  assert.strictEqual(rejections[0].message, RATE_LIMITED_MESSAGE);
});

await test('an onerror with no close following still settles the call from the transport', async () => {
  _resetPoolForTests();
  nextWs = null;
  const p = call(endpoint, 'host.ping', {});
  nextWs.onerror();
  await assert.rejects(p, (err) => err.code === -32001);
});

await test('a stream keeps the daemon reason when onerror precedes the close, and fires onError once', async () => {
  _resetPoolForTests();
  nextWs = null;
  const errors = [];
  callStream(endpoint, 'host.chat.send', { text: 'hi' }, { onError: (e) => errors.push(e), onFrame: () => {}, onDone: () => {} });
  const ws = nextWs;
  ws.onerror();
  ws.closeWith(1013, 'auth-rate-limited');
  ws.closeWith(1006, '');
  await settle();
  assert.strictEqual(errors.length, 1);
  assert.strictEqual(errors[0].code, RATE_LIMITED);
});

await test('every layer waits out the hold: no socket is opened, then one attempt is allowed', async () => {
  _resetPoolForTests();
  nextWs = null;
  const ep = { id: 'ep-hold', ip: '127.0.0.1', port: 9999, token: 't' };

  await atTime(1000, async () => {
    const first = call(ep, 'host.ping', {});
    nextWs.closeWith(1013, 'auth-rate-limited');
    await assert.rejects(first, (e) => e.code === RATE_LIMITED);
  });

  await atTime(1000 + RATE_LIMITED_HOLD_MS - 1, async () => {
    nextWs = null;
    await assert.rejects(call(ep, 'host.ping', {}), (e) => e.code === RATE_LIMITED);
    await assert.rejects(call(ep, 'host.other', {}), (e) => e.code === RATE_LIMITED);
    const streamErrors = [];
    callStream(ep, 'host.chat.send', {}, { onError: (e) => streamErrors.push(e) });
    assert.strictEqual(streamErrors.length, 1);
    assert.strictEqual(streamErrors[0].code, RATE_LIMITED);
    assert.strictEqual(nextWs, null, 'no socket may be opened while the hold stands');
  });

  let live = null;
  await atTime(1000 + RATE_LIMITED_HOLD_MS + 1, async () => {
    nextWs = null;
    const retry = call(ep, 'host.ping', {});
    assert.ok(nextWs, 'the hold must expire into exactly one new attempt');
    live = nextWs;
    live.open();
    const id = JSON.parse(live.sent[0]).id;
    live.message({ id, result: { ok: true } });
    assert.deepStrictEqual(await retry, { ok: true });
  });

  await atTime(1000 + RATE_LIMITED_HOLD_MS + 2, async () => {
    const after = call(ep, 'host.ping', {});
    const id = JSON.parse(live.sent[live.sent.length - 1]).id;
    live.message({ id, result: { ok: true } });
    assert.deepStrictEqual(await after, { ok: true }, 'the expired hold leaves nothing behind');
  });
});

await test('only an authenticated socket counts as live, and a refused one never vouches for itself', async () => {
  _resetPoolForTests();
  nextWs = null;
  const ep = { id: 'ep-live', ip: '127.0.0.1', port: 9999, token: 't' };
  callStream(ep, 'host.chat.send', { text: 'hi' }, { onError: () => {}, onFrame: () => {}, onDone: () => {} });
  const stream = nextWs;
  stream.open();
  assert.strictEqual(hasLiveSocket(ep), false, 'a socket that only shook hands proves nothing about the token');
  stream.message({ id: JSON.parse(stream.sent[0]).id, event: 'assistant_delta', text: 'hi' });
  assert.strictEqual(hasLiveSocket(ep), true);

  const pooled = call(ep, 'host.ping', {});
  nextWs.closeWith(1013, 'auth-rate-limited');
  await assert.rejects(pooled, (e) => e.code === RATE_LIMITED);
  assert.strictEqual(hasLiveSocket(ep), true, 'the working stream still proves the host is reachable');

  stream.closeWith(1000, '');
  assert.strictEqual(hasLiveSocket(ep), false);
});

await test('the refused socket is gone before the handler is told, so the block is never hidden by its own victim', async () => {
  for (const shape of ['rpc', 'stream']) {
    _resetPoolForTests();
    nextWs = null;
    const ep = { id: `ep-self-${shape}`, ip: '127.0.0.1', port: 9999, token: 't' };
    const seen = [];
    setRateLimitedHandler(({ endpoint }) => { seen.push(hasLiveSocket(endpoint)); });

    if (shape === 'rpc') {
      const p = call(ep, 'host.ping', {});
      nextWs.closeWith(1013, 'auth-rate-limited');
      await assert.rejects(p, (e) => e.code === RATE_LIMITED);
    } else {
      callStream(ep, 'host.chat.send', {}, { onError: () => {} });
      nextWs.closeWith(1013, 'auth-rate-limited');
    }

    assert.deepStrictEqual(seen, [false], `${shape}: the dying socket must not report itself as live`);
    setRateLimitedHandler(null);
  }
});

await test('the hold stops new sockets but never an authenticated one already in the pool', async () => {
  _resetPoolForTests();
  nextWs = null;
  const ep = { id: 'ep-healthy', ip: '127.0.0.1', port: 9999, token: 't' };

  const first = call(ep, 'host.ping', {});
  const healthy = nextWs;
  healthy.open();
  healthy.message({ id: JSON.parse(healthy.sent[0]).id, result: { ok: true } });
  assert.deepStrictEqual(await first, { ok: true });

  nextWs = null;
  const streamErrors = [];
  callStream(ep, 'host.chat.send', {}, { onError: (e) => streamErrors.push(e) });
  nextWs.closeWith(1013, 'auth-rate-limited');
  assert.strictEqual(streamErrors[0].code, RATE_LIMITED);

  nextWs = null;
  const cancel = call(ep, 'host.chat.cancel', { request_id: 'r-1' });
  assert.strictEqual(nextWs, null, 'the healthy socket is reused, no new socket is opened');
  healthy.message({ id: JSON.parse(healthy.sent[healthy.sent.length - 1]).id, result: { cancelled: true } });
  assert.deepStrictEqual(await cancel, { cancelled: true }, 'a held endpoint must still answer over its authenticated socket');

  healthy.closeWith(1000, '');
  nextWs = null;
  await assert.rejects(call(ep, 'host.ping', {}), (e) => e.code === RATE_LIMITED);
  assert.strictEqual(nextWs, null, 'with no authenticated socket left, the hold applies again');
  assert.strictEqual(hasLiveSocket(ep), false);
});

await test('a stream that times out opening leaves no phantom live socket behind', async () => {
  _resetPoolForTests();
  nextWs = null;
  const ep = { id: 'ep-phantom', ip: '127.0.0.1', port: 9999, token: 't' };
  const errors = [];
  const handle = callStream(ep, 'host.chat.send', {}, { onError: (e) => errors.push(e) });
  const ws = nextWs;
  ws.open();
  ws.message({ id: JSON.parse(ws.sent[0]).id, event: 'assistant_delta', text: 'hi' });
  assert.strictEqual(hasLiveSocket(ep), true);
  handle.detach();
  assert.strictEqual(hasLiveSocket(ep), false, 'detach must release the count');

  // Fire the 8s open timeout immediately instead of waiting it out; nothing else about the stream changes.
  const realSetTimeout = globalThis.setTimeout;
  globalThis.setTimeout = (fn, ms, ...rest) => realSetTimeout(fn, ms === 8000 ? 0 : ms, ...rest);
  nextWs = null;
  const timedOut = [];
  try {
    callStream(ep, 'host.chat.send', {}, { onError: (e) => timedOut.push(e) });
    await new Promise((r) => realSetTimeout(r, 20));
  } finally {
    globalThis.setTimeout = realSetTimeout;
  }
  assert.strictEqual(timedOut.length, 1);
  assert.match(timedOut[0].message, /stream open timed out/);
  assert.strictEqual(hasLiveSocket(ep), false, 'an open timeout may not leave the endpoint counted as live');
  assert.strictEqual(errors.length, 0);
});

await test('dropping an endpoint clears its hold and its late close cannot touch another endpoint', async () => {
  _resetPoolForTests();
  nextWs = null;
  const epA = { id: 'ep-a', ip: '127.0.0.1', port: 9999, token: 'a' };
  const epB = { id: 'ep-b', ip: '127.0.0.2', port: 9999, token: 'b' };
  const marked = [];
  setRateLimitedHandler(({ endpoint }) => marked.push(endpoint.id));

  const a = call(epA, 'host.ping', {});
  const wsA = nextWs;
  dropEndpointPool(epA);
  await assert.rejects(a, (e) => e.code === -32002);

  nextWs = null;
  const b = call(epB, 'host.ping', {});
  wsA.closeWith(1013, 'auth-rate-limited');
  assert.deepStrictEqual(marked, [], 'a late close from a dropped socket marks nothing');
  nextWs.open();
  const idB = JSON.parse(nextWs.sent[0]).id;
  nextWs.message({ id: idB, result: { ok: true } });
  assert.deepStrictEqual(await b, { ok: true });

  nextWs = null;
  const again = call(epA, 'host.ping', {});
  assert.ok(nextWs, 'dropping the endpoint released its hold');
  nextWs.closeWith(1006, '');
  await assert.rejects(again, (e) => e.code === -32002);
  setRateLimitedHandler(null);
});

if (failed > 0) {
  console.error(`\n${failed} failed, ${passed} passed`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
