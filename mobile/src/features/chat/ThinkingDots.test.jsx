import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ reduce: false, loops: 0 }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Animated = {
    View,
    Value: class { constructor(v) { this.v = v; } setValue(v) { this.v = v; } },
    timing: () => ({}),
    delay: () => ({}),
    sequence: () => ({}),
    loop: () => ({ start() { h.loops += 1; }, stop() {} }),
  };
  return { View, Animated };
});
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));
vi.mock('../../theme/ThemeContext', () => ({ useTheme: () => ({ colors: { ink3: '#666' } }) }));

import { ThinkingDots } from './ThinkingDots';

describe('ThinkingDots', () => {
  it('pulses by default and holds still under reduced motion', () => {
    h.loops = 0;
    render(<ThinkingDots />);
    expect(h.loops).toBe(3);
    cleanup();
    h.loops = 0;
    h.reduce = true;
    render(<ThinkingDots />);
    expect(h.loops).toBe(0);
  });
});
