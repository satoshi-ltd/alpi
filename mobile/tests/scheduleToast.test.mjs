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

test('schedule.done success is NEVER toasted — schedule success is not an interrupt; jobs that want to notify call notify explicitly', () => {
  assert.equal(buildScheduleToast('schedule.done', {
    profile: 'abby', job_id: 'ab12',
    message: 'silent run ok: ⏰ comprar pan',
    reply: '⏰ comprar pan',
  }), null);
  assert.equal(buildScheduleToast('schedule.done', {
    profile: 'mirai', message: 'silent run ok', silent: true,
  }), null);
  assert.equal(buildScheduleToast('schedule.done', {
    profile: 'mirai', job_id: 'standup',
    message: 'agent delivered via notify',
    delivered_to: 'external',
  }), null);
});

test('schedule.failed always toasts — errors always need attention', () => {
  const t = buildScheduleToast('schedule.failed', {
    profile: 'doc', job_id: 'weekly', message: 'rc=1',
  });
  assert.notEqual(t, null);
  assert.equal(t.title, 'doc · schedule failed');
  assert.equal(t.message, 'weekly: rc=1');
});

test('schedule.failed with no message falls back to job_id only', () => {
  const t = buildScheduleToast('schedule.failed', {
    profile: 'doc', job_id: 'weekly',
  });
  assert.notEqual(t, null);
  assert.equal(t.message, 'weekly');
});

test('schedule.failed prefers the human title and enriched body, flattening newlines', () => {
  const t = buildScheduleToast('schedule.failed', {
    profile: 'mirai', job_id: '6b7ad5d5',
    title: 'Monthly Lobby improvement backlog',
    body: 'agent timed out\ntimeout: timeout_1800s',
    message: 'agent timed out',
  });
  assert.equal(t.title, 'mirai · schedule failed');
  assert.equal(t.message, 'Monthly Lobby improvement backlog: agent timed out · timeout: timeout_1800s');
});

test('unknown event → null', () => {
  assert.equal(buildScheduleToast('wg.done', {}), null);
  assert.equal(buildScheduleToast('session_changed', {}), null);
  assert.equal(buildScheduleToast('agent.message', {}), null);
});

test('null/missing fields on failure tolerated', () => {
  const t = buildScheduleToast('schedule.failed', {});
  assert.notEqual(t, null);
  assert.equal(t.title, ' · schedule failed');
});

test('schedule.failed with a reason but no title/job_id has no leading colon', () => {
  const t = buildScheduleToast('schedule.failed', { profile: 'doc', message: 'boom' });
  assert.equal(t.message, 'boom');
});

test('duration is set (default 5000ms — readable for a sentence)', () => {
  const t = buildScheduleToast('schedule.failed', {
    profile: 'abby', job_id: 'x', message: 'boom',
  });
  assert.equal(typeof t.duration, 'number');
  assert.ok(t.duration >= 3000);
});

if (failed > 0) {
  console.error(`\n${failed} failed, ${passed} passed`);
  process.exit(1);
}
console.log(`\n${passed} passed`);
