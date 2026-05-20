// Node-runnable test for src/lib/scheduleToast.js.
//   $ node mobile/tests/scheduleToast.test.mjs
import assert from 'node:assert/strict';

import { buildScheduleToast } from '../src/lib/scheduleToast.js';

let passed = 0;
let failed = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`ok   ${name}`);
    passed++;
  } catch (err) {
    console.error(`FAIL ${name}\n     ${err.message}`);
    failed++;
  }
}

test('reply present → profile as title, reply as message', () => {
  const t = buildScheduleToast('schedule.done', {
    profile: 'abby',
    job_id: 'ab12',
    message: 'silent run ok: ⏰ comprar pan',
    reply: '⏰ comprar pan',
    silent: false,
  });
  assert.equal(t.title, 'abby');
  assert.equal(t.message, '⏰ comprar pan');
});

test('silent=true on success → suppressed', () => {
  const t = buildScheduleToast('schedule.done', {
    profile: 'mirai',
    message: 'silent run ok',
    reply: '',
    silent: true,
  });
  assert.equal(t, null);
});

test('silent on failure is ignored — errors always surface', () => {
  const t = buildScheduleToast('schedule.failed', {
    profile: 'doc',
    job_id: 'weekly',
    message: 'rc=1',
    reply: '',
    silent: true,
  });
  assert.notEqual(t, null);
  assert.equal(t.title, 'doc · schedule failed');
});

test('send_message self-delivered → toast with fallback message', () => {
  const t = buildScheduleToast('schedule.done', {
    profile: 'mirai',
    job_id: 'standup',
    message: 'agent delivered via send_message; no duplicate reply pushed',
    reply: '',
    delivered_to: 'external',
  });
  assert.equal(t.title, 'mirai · schedule ran');
  assert.ok(t.message.startsWith('standup:'));
});

test('unknown event → null', () => {
  assert.equal(buildScheduleToast('wg.done', {}), null);
  assert.equal(buildScheduleToast('session_changed', {}), null);
});

test('null/missing fields tolerated', () => {
  const t = buildScheduleToast('schedule.done', { reply: undefined });
  assert.equal(t.title, ' · schedule ran');
  assert.equal(t.message, '');
});

test('duration is set (default 5000ms — readable for a sentence)', () => {
  const t = buildScheduleToast('schedule.done', {
    profile: 'abby', reply: 'go drink water',
  });
  assert.equal(typeof t.duration, 'number');
  assert.ok(t.duration >= 3000);
});

if (failed > 0) {
  console.error(`\n${failed} failed, ${passed} passed`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
