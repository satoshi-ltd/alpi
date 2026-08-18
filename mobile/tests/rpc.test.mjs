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
}
globalThis.WebSocket = FakeWs;

const { call, dropEndpointPool, setAuthFailedHandler, _resetPoolForTests } = await import('../src/lib/rpc.js');

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

if (failed > 0) {
  console.error(`\n${failed} failed, ${passed} passed`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
