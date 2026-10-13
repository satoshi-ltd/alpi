import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style }) => React.createElement('div', { 'data-bg': style?.backgroundColor, 'data-w': style?.width }, children),
  Text: ({ children, style }) => React.createElement('span', { 'data-fg': style?.color }, children),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { hover: 'HOVER', ink: 'INK', ink2: 'INK2', ink3: 'INK3', success: '#00aa00', successText: 'GREEN', danger: '#aa0000', dangerText: 'RED', warning: '#ff8800', warningText: 'ORANGE' },
    fonts: { monoMedium: 'm' },
    fontSizes: { sm: 12 },
  }),
}));
vi.mock('./groupTone', () => ({ useGroundTone: () => '#ffffff' }));

import { Pill } from './Pill';

const parts = (container) => {
  const [pill, ...rest] = container.querySelectorAll('div');
  const dot = rest.find((el) => el.getAttribute('data-w'));
  return { bg: pill.getAttribute('data-bg'), dot: dot?.getAttribute('data-bg') ?? null, fg: container.querySelector('span').getAttribute('data-fg') };
};

describe('Pill', () => {
  it('draws warn like the desktop Chip: neutral ground, ink text, a warning dot', () => {
    const { container } = render(<Pill tone="warn">warning</Pill>);
    expect(parts(container)).toEqual({ bg: 'HOVER', fg: 'INK', dot: '#ff8800' });
  });

  it('tints the ground for on and err and puts their colour in the dot', () => {
    const on = parts(render(<Pill tone="on">on</Pill>).container);
    expect(on.fg).toBe('GREEN');
    expect(on.dot).toBe('#00aa00');
    expect(on.bg).not.toBe('HOVER');
    cleanup();
    const err = parts(render(<Pill tone="err">error</Pill>).container);
    expect(err.fg).toBe('RED');
    expect(err.dot).toBe('#aa0000');
  });

  it('gives off a grey dot and a plain pill none', () => {
    expect(parts(render(<Pill off>off</Pill>).container).dot).toBe('INK3');
    cleanup();
    expect(parts(render(<Pill>12 KB</Pill>).container)).toEqual({ bg: 'HOVER', fg: 'INK2', dot: null });
  });
});
