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

const { call, dropEndpointPool, _resetPoolForTests } = await import('../src/lib/rpc.js');

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

if (failed > 0) {
  console.error(`\n${failed} failed, ${passed} passed`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
