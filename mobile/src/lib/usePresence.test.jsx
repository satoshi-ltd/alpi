import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render, renderHook, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ reduce: false }));
vi.mock('./reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('react-native', async () => {
  const R = await import('react');
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  return {
    View: ({ children, testID, style }) =>
      R.createElement('div', { 'data-testid': testID, 'data-style': JSON.stringify(flat(style)) }, children),
    Text: ({ children }) => R.createElement('span', {}, children),
    Pressable: ({ children, accessibilityLabel }) =>
      R.createElement('button', { type: 'button', 'aria-label': accessibilityLabel }, typeof children === 'function' ? children({ pressed: false }) : children),
  };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: {}, fonts: { sans: {} }, fontSizes: { sm: 12 }, shadow: { base: {} }, chromeScale: 1 }),
}));
vi.mock('../components/Icon', () => ({ Icon: () => null }));

import { finishTimings, state } from '../../tests/mocks/reanimated.js';
import { Expand } from '../components/Expand';
import { JumpToLatest } from '../features/chat/JumpToLatest';
import { motionMs } from '../theme/tokens';
import { usePresence } from './usePresence';

const styleOf = (id) => JSON.parse(screen.getByTestId(id).getAttribute('data-style'));

beforeEach(() => {
  h.reduce = false;
  state.hold = true;
  state.pending.length = 0;
  state.timings.length = 0;
});
afterEach(() => {
  state.hold = false;
  state.pending.length = 0;
});

describe('usePresence', () => {
  it('stays mounted through an in-flight exit and unmounts when it finishes', () => {
    const { result, rerender } = renderHook(({ v }) => usePresence(v, 180), { initialProps: { v: true } });
    expect(state.timings).toEqual([]);
    rerender({ v: false });
    expect(state.timings.at(-1)).toEqual({ to: 0, duration: 180 });
    expect(result.current.mounted).toBe(true);
    expect(result.current.moving.value).toBe(true);
    act(() => finishTimings());
    expect(result.current.mounted).toBe(false);
    expect(result.current.moving.value).toBe(false);
  });

  it('ignores a stale exit that lands after a reopen', () => {
    const { result, rerender } = renderHook(({ v }) => usePresence(v, 180), { initialProps: { v: true } });
    rerender({ v: false });
    const staleExit = state.pending.splice(0);
    rerender({ v: true });
    act(() => staleExit.forEach((done) => done(true)));
    expect(result.current.mounted).toBe(true);
    rerender({ v: false });
    expect(result.current.mounted).toBe(true);
    act(() => finishTimings());
    expect(result.current.mounted).toBe(false);
  });

  it('snaps with no timing under reduced motion or when asked to', () => {
    h.reduce = true;
    const a = renderHook(({ v }) => usePresence(v, 180), { initialProps: { v: true } });
    a.rerender({ v: false });
    expect(a.result.current.mounted).toBe(false);
    h.reduce = false;
    const b = renderHook(({ v }) => usePresence(v, 180, { snap: true }), { initialProps: { v: true } });
    b.rerender({ v: false });
    expect(b.result.current.mounted).toBe(false);
    expect(state.timings).toEqual([]);
  });
});

describe('Expand', () => {
  it('renders a mount-open body at full height on the first frame, unclipped', () => {
    render(<Expand open><span>body</span></Expand>);
    const style = styleOf('expand');
    expect(style.overflow).toBe('visible');
    expect(style.maxHeight).toBeGreaterThan(10000);
    expect(state.timings).toEqual([]);
  });

  it('clips only while the 180 ms expansion is in flight', () => {
    const { rerender } = render(<Expand open={false}><span>body</span></Expand>);
    rerender(<Expand open><span>body</span></Expand>);
    expect(state.timings.at(-1)).toEqual({ to: 1, duration: motionMs.expand });
    expect(styleOf('expand').overflow).toBe('hidden');
    act(() => finishTimings());
    rerender(<Expand open><span>body</span></Expand>);
    expect(styleOf('expand').overflow).toBe('visible');
    rerender(<Expand open={false}><span>body</span></Expand>);
    rerender(<Expand open={false}><span>body</span></Expand>);
    expect(styleOf('expand').overflow).toBe('hidden');
    expect(screen.getByText('body')).toBeTruthy();
    act(() => finishTimings());
    expect(screen.queryByText('body')).toBeNull();
  });
});

describe('JumpToLatest', () => {
  it('fades out over 150 ms and stays tappable-free until gone', () => {
    const { rerender } = render(<JumpToLatest visible onPress={() => {}} />);
    rerender(<JumpToLatest visible={false} onPress={() => {}} />);
    expect(state.timings.at(-1)).toEqual({ to: 0, duration: motionMs.jump });
    expect(screen.getByLabelText('Jump to latest')).toBeTruthy();
    act(() => finishTimings());
    expect(screen.queryByLabelText('Jump to latest')).toBeNull();
  });

  it('names the durations the motion board lists', () => {
    expect(motionMs).toEqual({ sidebar: 200, expand: 180, jump: 150 });
  });
});
