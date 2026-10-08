import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  _resetNotificationStoreForTests,
  freeze,
  notificationState,
  scheduleDelete,
  setTrail,
  trailPosition,
  undoAllDeletes,
} from './notificationStore';

const e = (id) => ({ key: `c:p:${id}`, profile: 'p', id, connectionId: 'c', pinned: id === 'a', unread: true });

beforeEach(() => {
  _resetNotificationStoreForTests();
  vi.useFakeTimers();
});
afterEach(() => vi.useRealTimers());

describe('trailPosition', () => {
  it('places a key in the order the list showed, with its neighbours', () => {
    setTrail([e('a'), e('b'), e('c')]);
    expect(trailPosition('c:p:b')).toEqual({ index: 1, total: 3, prev: e('a'), next: e('c') });
    expect(trailPosition('c:p:zz')).toBeNull();
  });

  it('skips rows waiting to be deleted but keeps the current one', () => {
    setTrail([e('a'), e('b'), e('c')]);
    scheduleDelete('c:p:b', async () => {});
    expect(trailPosition('c:p:a')).toMatchObject({ total: 2, next: e('c') });
    expect(trailPosition('c:p:b')).toMatchObject({ index: 1, total: 3 });
  });

  it('answers nothing without a trail, as on a deep link', () => {
    expect(trailPosition('c:p:a')).toBeNull();
  });
});

describe('freeze', () => {
  it('keeps only the key and the flags the row had in the list', () => {
    freeze(e('a'));
    expect(notificationState().frozen).toEqual({ key: 'c:p:a', pinned: true, unread: true });
    freeze(null);
    expect(notificationState().frozen).toBeNull();
  });
});

describe('scheduleDelete', () => {
  it('hides at once and runs only after the undo window', async () => {
    const run = vi.fn(async () => {});
    scheduleDelete('k', run, { delayMs: 5000 });
    expect(notificationState().hidden.has('k')).toBe(true);
    await vi.advanceTimersByTimeAsync(4999);
    expect(run).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);
    expect(run).toHaveBeenCalledTimes(1);
    expect(notificationState().hidden.has('k')).toBe(true);
  });

  it('never runs once undone, and shows the row again', async () => {
    const run = vi.fn(async () => {});
    scheduleDelete('k', run, { delayMs: 5000 });
    expect(undoAllDeletes()).toBe(true);
    expect(notificationState().hidden.has('k')).toBe(false);
    await vi.advanceTimersByTimeAsync(10000);
    expect(run).not.toHaveBeenCalled();
    expect(undoAllDeletes()).toBe(false);
  });

  it('counts the batch and gives every pending row one window', async () => {
    const first = vi.fn(async () => {});
    const second = vi.fn(async () => {});
    expect(scheduleDelete('a', first, { delayMs: 5000 })).toBe(1);
    await vi.advanceTimersByTimeAsync(4000);
    expect(scheduleDelete('b', second, { delayMs: 5000 })).toBe(2);
    await vi.advanceTimersByTimeAsync(4000);
    expect(first).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1000);
    expect(first).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenCalledTimes(1);
  });

  it('one undo brings back every row of the batch', async () => {
    const run = vi.fn(async () => {});
    scheduleDelete('a', run, { delayMs: 5000 });
    scheduleDelete('b', run, { delayMs: 5000 });
    scheduleDelete('c', run, { delayMs: 5000 });
    expect(undoAllDeletes()).toBe(true);
    for (const key of ['a', 'b', 'c']) expect(notificationState().hidden.has(key)).toBe(false);
    await vi.advanceTimersByTimeAsync(10000);
    expect(run).not.toHaveBeenCalled();
  });

  it('shows back only the row the daemon refused', async () => {
    scheduleDelete('a', async () => { throw new Error('boom'); }, { delayMs: 10 });
    scheduleDelete('b', async () => {}, { delayMs: 10 });
    await vi.advanceTimersByTimeAsync(10);
    expect(notificationState().hidden.has('a')).toBe(false);
    expect(notificationState().hidden.has('b')).toBe(true);
  });

  it('shows the row again when the daemon refuses the delete', async () => {
    scheduleDelete('k', async () => { throw new Error('boom'); }, { delayMs: 10 });
    await vi.advanceTimersByTimeAsync(10);
    expect(notificationState().hidden.has('k')).toBe(false);
  });
});
