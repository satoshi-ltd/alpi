import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, renderHook } from '@testing-library/react';

const h = vi.hoisted(() => ({ activity: { running: [] }, supported: true }));

vi.mock('../../hooks/useActivity', async (importOriginal) => ({
  ...(await importOriginal()),
  useActivity: () => ({ activity: h.activity, supported: h.supported }),
}));

import { elapsedLabel, useRunningJob } from './useRunningJob';

const JOB = { id: 'j1', run_timeout: 900 };
const rowFor = (startedAgo) => ({ kind: 'turn', profile: 'scout', job_id: 'j1', source: 'schedule', started_at: Date.now() / 1000 - startedAgo });

beforeEach(() => {
  vi.useFakeTimers();
  h.activity = { running: [] };
  h.supported = true;
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe('elapsed label', () => {
  it('counts minutes and seconds', () => {
    expect(elapsedLabel(0)).toBe('0:00');
    expect(elapsedLabel(42)).toBe('0:42');
    expect(elapsedLabel(605)).toBe('10:05');
    expect(elapsedLabel(-3)).toBe('0:00');
  });
});

describe('running job', () => {
  const mount = () => renderHook(() => useRunningJob('scout', JOB));

  it('is running while an activity row carries the job, with the time since it started', () => {
    h.activity = { running: [rowFor(90)] };
    const { result } = mount();
    expect(result.current.running).toBe(true);
    expect(result.current.elapsed).toMatch(/^1:3\d$/);
  });

  it('ignores a row of another profile or another job', () => {
    h.activity = { running: [{ ...rowFor(5), profile: 'other' }, { ...rowFor(5), job_id: 'j2' }] };
    expect(mount().result.current.running).toBe(false);
  });

  it('shows running at once after a fire and stops when the event says so', () => {
    const { result } = mount();
    act(() => result.current.started());
    expect(result.current.running).toBe(true);
    act(() => result.current.finished());
    expect(result.current.running).toBe(false);
  });

  it('lets go when the run never shows up in Activity within a few seconds', () => {
    const { result } = mount();
    act(() => result.current.started());
    act(() => { vi.advanceTimersByTime(9000); });
    expect(result.current.running).toBe(true);
    act(() => { vi.advanceTimersByTime(2000); });
    expect(result.current.running).toBe(false);
  });

  it('lets go when the run showed up and then left Activity without an event', () => {
    const { result, rerender } = mount();
    act(() => result.current.started());
    h.activity = { running: [rowFor(3)] };
    rerender();
    expect(result.current.running).toBe(true);
    h.activity = { running: [] };
    rerender();
    expect(result.current.running).toBe(true);
    act(() => { vi.advanceTimersByTime(2100); });
    expect(result.current.running).toBe(false);
  });

  it('keeps the event first: a row that leaves just before schedule.done does not end the run early', () => {
    const { result, rerender } = mount();
    act(() => result.current.started());
    h.activity = { running: [rowFor(3)] };
    rerender();
    h.activity = { running: [] };
    rerender();
    act(() => { vi.advanceTimersByTime(1500); });
    expect(result.current.wasRunning()).toBe(true);
    act(() => result.current.finished());
    expect(result.current.running).toBe(false);
  });

  it('waits for the event or the run timeout on a daemon without Activity', () => {
    h.supported = false;
    const { result } = mount();
    act(() => result.current.started());
    act(() => { vi.advanceTimersByTime(60_000); });
    expect(result.current.running).toBe(true);
    act(() => { vi.advanceTimersByTime(900_000); });
    expect(result.current.running).toBe(false);
  });
});
