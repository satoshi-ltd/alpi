import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';

import { _resetSessionMarksForTests, DONE_MS, headerState, sessionMarkKey, sharedSessionMark, useSessionMark, useSharedSessionMark } from './sessionMark';

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  _resetSessionMarksForTests();
});

const mount = (initial) => renderHook((props) => useSessionMark(props), { initialProps: { key: sessionMarkKey('doc'), ...initial } });

describe('headerState', () => {
  it('ranks offline over paused over needs over working over failed over done', () => {
    expect(headerState({})).toBe('idle');
    expect(headerState({ done: true })).toBe('done');
    expect(headerState({ done: true, failed: true })).toBe('failed');
    expect(headerState({ failed: true, working: true })).toBe('working');
    expect(headerState({ working: true, needs: true })).toBe('needs');
    expect(headerState({ needs: true, paused: true })).toBe('paused');
    expect(headerState({ paused: true, offline: true })).toBe('offline');
  });
});

describe('useSessionMark', () => {
  it('works from send until the turn ends, shows done for a moment, then rests', () => {
    const { result, rerender } = mount({ working: false });
    expect(result.current).toBe('idle');
    rerender({ key: 'profile:doc', working: true });
    expect(result.current).toBe('working');
    rerender({ key: 'profile:doc', working: false });
    expect(result.current).toBe('done');
    act(() => vi.advanceTimersByTime(DONE_MS - 1));
    expect(result.current).toBe('done');
    act(() => vi.advanceTimersByTime(1));
    expect(result.current).toBe('idle');
  });

  it('rests, without a done, when the user cancels the turn', () => {
    const { result, rerender } = mount({ working: true });
    rerender({ key: 'profile:doc', working: false, cancelled: true });
    expect(result.current).toBe('idle');
    rerender({ key: 'profile:doc', working: false, cancelled: false });
    expect(result.current).toBe('idle');
    rerender({ key: 'profile:doc', working: true });
    rerender({ key: 'profile:doc', working: false });
    expect(result.current).toBe('done');
  });

  it('rests when the cancel lands a render before the turn stops', () => {
    const { result, rerender } = mount({ working: true });
    rerender({ key: 'profile:doc', working: true, cancelled: true });
    rerender({ key: 'profile:doc', working: false, cancelled: false });
    expect(result.current).toBe('idle');
  });

  it('needs you while a question or a permission is pending', () => {
    const { result, rerender } = mount({ working: true });
    rerender({ key: 'profile:doc', working: true, needs: true });
    expect(result.current).toBe('needs');
    rerender({ key: 'profile:doc', working: true, needs: false });
    expect(result.current).toBe('working');
  });

  it('fails when the turn ends in an error and stays failed until the next send', () => {
    const { result, rerender } = mount({ working: true });
    rerender({ key: 'profile:doc', working: false, error: true });
    expect(result.current).toBe('failed');
    act(() => vi.advanceTimersByTime(DONE_MS * 4));
    expect(result.current).toBe('failed');
    rerender({ key: 'profile:doc', working: true, error: false });
    expect(result.current).toBe('working');
    rerender({ key: 'profile:doc', working: false, error: false });
    expect(result.current).toBe('done');
  });

  it('reads paused while the profile is paused', () => {
    const { result, rerender } = mount({ paused: true });
    expect(result.current).toBe('paused');
    rerender({ key: 'profile:doc', paused: false });
    expect(result.current).toBe('idle');
  });

  it('shares its state with the selected roster row and forgets it on unmount', () => {
    const { rerender, unmount } = mount({ working: true });
    const row = renderHook(() => useSharedSessionMark(sessionMarkKey('doc')));
    expect(row.result.current).toBe('working');
    rerender({ key: 'profile:doc', working: false });
    expect(row.result.current).toBe('done');
    expect(sharedSessionMark(sessionMarkKey('other'))).toBeNull();
    unmount();
    expect(row.result.current).toBeNull();
  });

  it('forgets done and failed when the connection, the profile or the session changes', () => {
    const { result, rerender } = mount({ scope: 'c:doc', session: 's_a', working: true });
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_a', working: false, error: true });
    expect(result.current).toBe('failed');
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_b', working: false, error: true });
    expect(result.current).toBe('idle');
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_b', working: true });
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_b', working: false });
    expect(result.current).toBe('done');
    rerender({ key: 'profile:abby', scope: 'c:abby', session: 's_c', working: false });
    expect(result.current).toBe('idle');
    act(() => vi.advanceTimersByTime(DONE_MS * 2));
    expect(result.current).toBe('idle');
  });

  it('shows no false done when the chat moves to another session mid-turn', () => {
    const { result, rerender } = mount({ scope: 'c:doc', session: 's_a', working: true });
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_b', working: false });
    expect(result.current).toBe('idle');
  });

  it('keeps the done of a new thread when the turn names its session', () => {
    const { result, rerender } = mount({ scope: 'c:doc', session: null, working: true });
    rerender({ key: 'profile:doc', scope: 'c:doc', session: null, working: false });
    expect(result.current).toBe('done');
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_new', working: false });
    expect(result.current).toBe('done');
    rerender({ key: 'profile:doc', scope: 'c:doc', session: 's_other', working: false });
    expect(result.current).toBe('idle');
  });
});

describe('the shared store across stacked chats', () => {
  it('keeps the lower chat of a profile published when the top one of the same profile unmounts', () => {
    const lowerA = renderHook(() => useSessionMark({ key: sessionMarkKey('doc'), working: true }));
    const b = renderHook(() => useSessionMark({ key: sessionMarkKey('abby') }));
    const topA = renderHook(() => useSessionMark({ key: sessionMarkKey('doc'), paused: true }));
    const row = renderHook(() => useSharedSessionMark(sessionMarkKey('doc')));
    expect(row.result.current).toBe('paused');
    topA.unmount();
    expect(row.result.current).toBe('working');
    b.unmount();
    expect(sharedSessionMark(sessionMarkKey('abby'))).toBeNull();
    expect(row.result.current).toBe('working');
    lowerA.unmount();
    expect(row.result.current).toBeNull();
  });

  it('lets the top chat speak for the profile even when the lower one changes state', () => {
    const lower = renderHook((props) => useSessionMark(props), { initialProps: { key: sessionMarkKey('doc'), working: false } });
    const top = renderHook(() => useSessionMark({ key: sessionMarkKey('doc'), needs: true }));
    lower.rerender({ key: sessionMarkKey('doc'), working: true });
    expect(sharedSessionMark(sessionMarkKey('doc'))).toBe('needs');
    top.unmount();
    expect(sharedSessionMark(sessionMarkKey('doc'))).toBe('working');
    lower.unmount();
  });
});
