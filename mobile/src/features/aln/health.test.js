import { describe, expect, it } from 'vitest';

import { describeHealth } from './health';

const NOW = 1_700_000_000_000;
const OK = { permission: 'granted', registration: 'registered' };
const healthy = (name, minsAgo) => ({ name, lastSuccessMs: NOW - minsAgo * 60000, lastError: '' });

describe('describeHealth global gates', () => {
  it('calls out a denied permission before anything else', () => {
    const h = describeHealth({ ...OK, permission: 'denied', daemons: [healthy('home', 1)] }, NOW);
    expect(h.ok).toBe(false);
    expect(h.detail).toMatch(/denied/i);
  });

  it('calls out an undetermined permission', () => {
    const h = describeHealth({ permission: 'undetermined' }, NOW);
    expect(h.ok).toBe(false);
    expect(h.detail).toMatch(/not granted/i);
  });

  it('surfaces an OS-restricted background task distinctly from a missing permission', () => {
    const h = describeHealth({ ...OK, registration: 'restricted', daemons: [healthy('home', 1)] }, NOW);
    expect(h.ok).toBe(false);
    expect(h.detail).toMatch(/restricted/i);
  });

  it('flags an unregistered task', () => {
    const h = describeHealth({ ...OK, registration: 'unregistered', daemons: [] }, NOW);
    expect(h.ok).toBe(false);
    expect(h.detail).toMatch(/not registered/i);
  });

  it('says so when nothing is paired', () => {
    expect(describeHealth({ ...OK, daemons: [] }, NOW).ok).toBe(false);
  });

  it('treats a missing health object as not granted rather than throwing', () => {
    expect(describeHealth(null, NOW).ok).toBe(false);
  });
});

describe('describeHealth single daemon', () => {
  it('reports minutes for a recent success', () => {
    const h = describeHealth({ ...OK, daemons: [healthy('home', 5)] }, NOW);
    expect(h.ok).toBe(true);
    expect(h.detail).toContain('5 min ago');
  });

  it('reports hours once the gap is long enough — the honest signal that the OS is not waking the app', () => {
    const h = describeHealth({ ...OK, daemons: [healthy('home', 180)] }, NOW);
    expect(h.ok).toBe(true);
    expect(h.detail).toContain('3 h ago');
  });

  it('says just now for a sub-minute gap', () => {
    const h = describeHealth({ ...OK, daemons: [{ name: 'home', lastSuccessMs: NOW - 1000, lastError: '' }] }, NOW);
    expect(h.detail).toContain('just now');
  });

  it('is not ok when the only daemon has never succeeded', () => {
    const h = describeHealth({ ...OK, daemons: [{ name: 'home', lastSuccessMs: 0, lastError: '' }] }, NOW);
    expect(h.ok).toBe(false);
    expect(h.detail).toContain('no successful check yet');
  });

  it('surfaces the error text when the only daemon is failing', () => {
    const h = describeHealth(
      { ...OK, daemons: [{ name: 'home', lastSuccessMs: NOW - 60000, lastError: 'timeout' }] },
      NOW,
    );
    expect(h.ok).toBe(false);
    expect(h.detail).toContain('timeout');
  });
});

describe('describeHealth reports the worst daemon, not the newest', () => {
  it('one healthy daemon cannot paint over two that never answered', () => {
    const h = describeHealth({
      ...OK,
      daemons: [
        healthy('home', 1),
        { name: 'work', lastSuccessMs: 0, lastError: '' },
        { name: 'nas', lastSuccessMs: 0, lastError: '' },
      ],
    }, NOW);

    expect(h.ok).toBe(false);
    expect(h.detail).toContain('1 of 3 daemons checking in');
    expect(h.detail).toContain('work');
    expect(h.detail).toContain('no successful check yet');
  });

  it('a daemon with a current error counts as unhealthy even though it succeeded before', () => {
    const h = describeHealth({
      ...OK,
      daemons: [healthy('home', 1), { name: 'work', lastSuccessMs: NOW - 120000, lastError: 'unreachable' }],
    }, NOW);

    expect(h.ok).toBe(false);
    expect(h.detail).toContain('1 of 2 daemons checking in');
    expect(h.detail).toContain('work: last error: unreachable');
  });

  it('reports the OLDEST check when every daemon is healthy', () => {
    const h = describeHealth({ ...OK, daemons: [healthy('home', 2), healthy('work', 45)] }, NOW);

    expect(h.ok).toBe(true);
    expect(h.detail).toContain('All 2 daemons checking in');
    expect(h.detail).toContain('45 min ago');
  });

  it('falls back to a positional label when a daemon has no name', () => {
    const h = describeHealth({
      ...OK,
      daemons: [healthy('home', 1), { name: '', lastSuccessMs: 0, lastError: '' }],
    }, NOW);

    expect(h.detail).toContain('daemon 2');
  });
});

describe('describeHealth degraded routes', () => {
  it('a daemon reachable only as a member is not green — admin-only alerts cannot arrive', () => {
    const h = describeHealth({
      ...OK,
      daemons: [{ ...healthy('home', 1), degraded: true }],
    }, NOW);

    expect(h.ok).toBe(false);
    expect(h.detail).toContain('only as a member');
  });

  it('a plain healthy daemon stays green', () => {
    const h = describeHealth({ ...OK, daemons: [{ ...healthy('home', 1), degraded: false }] }, NOW);
    expect(h.ok).toBe(true);
  });

  it('an outright failure outranks a degraded sibling', () => {
    const h = describeHealth({
      ...OK,
      daemons: [
        { ...healthy('home', 1), degraded: true },
        { name: 'work', lastSuccessMs: 0, lastError: '' },
      ],
    }, NOW);

    expect(h.ok).toBe(false);
    expect(h.detail).toContain('work');
  });
});
