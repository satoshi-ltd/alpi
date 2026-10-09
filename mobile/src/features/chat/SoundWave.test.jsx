import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ reduce: false, loops: 0, listener: null }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Animated = {
    View,
    Value: class { constructor(v) { this.v = v; } setValue(v) { this.v = v; } },
    timing: () => ({}),
    sequence: () => ({}),
    loop: () => ({ start() { h.loops += 1; }, stop() {} }),
  };
  const Pressable = ({ children, hitSlop, accessibilityLabel }) => React.createElement('button', { type: 'button', 'aria-label': accessibilityLabel, 'data-hitslop': JSON.stringify(hitSlop ?? null) }, children);
  return { Animated, Pressable, StyleSheet: { create: (s) => s } };
});
vi.mock('../../lib/readAloud', () => ({
  subscribeReadAloud: (fn) => { h.listener = fn; return () => {}; },
  clearReadAloud: () => {},
}));
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

import { SoundWave } from './SoundWave';

describe('SoundWave', () => {
  it('animates while reading aloud and holds still under reduced motion', () => {
    h.loops = 0;
    render(<SoundWave accent="#abc" />);
    act(() => h.listener({ kind: 'playing' }));
    expect(h.loops).toBe(3);
    cleanup();
    h.loops = 0;
    h.reduce = true;
    render(<SoundWave accent="#abc" />);
    act(() => h.listener({ kind: 'playing' }));
    expect(h.loops).toBe(0);
  });

  it('is a named control with a 44 pt touch height around its 18 pt bars', () => {
    const { getByLabelText } = render(<SoundWave accent="#abc" />);
    act(() => h.listener({ kind: 'playing' }));
    const button = getByLabelText('Silence read-aloud');
    const slop = JSON.parse(button.getAttribute('data-hitslop'));
    expect(slop.top + slop.bottom + 18).toBeGreaterThanOrEqual(44);
  });
});
