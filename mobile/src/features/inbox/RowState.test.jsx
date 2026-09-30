import React from 'react';
import { act, cleanup, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ reduce: false, loops: 0 }));

vi.mock('react-native', () => {
  const View = ({ children, testID, style }) =>
    React.createElement('div', { 'data-testid': testID, 'data-bg': style?.backgroundColor }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-color': style?.color, 'data-size': style?.fontSize }, children);
  class Value {
    constructor(v) { this.v = v; }
    setValue(v) { this.v = v; }
  }
  const Animated = {
    View,
    Value,
    timing: () => ({}),
    sequence: () => ({}),
    loop: () => ({ start: () => { h.loops += 1; }, stop: () => {} }),
  };
  return { Animated, Text, View };
});

vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { accent: '#accent', warningText: '#warn', dangerText: '#danger' },
      fonts: { sans: { medium: 'sans-medium' }, monoMedium: 'mono-medium' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { fontSizes } from '../../theme/tokens';
import { RowState } from './RowState';

beforeEach(() => {
  h.reduce = false;
  h.loops = 0;
});
afterEach(cleanup);

describe('RowState', () => {
  it.each([
    ['needs-you', 'needs you', '#warn'],
    ['failed', 'failed', '#danger'],
    ['working', 'working', '#accent'],
  ])('%s reads "%s" in its own colour', (state, text, color) => {
    render(<RowState state={state} />);
    expect(screen.getByText(text).getAttribute('data-color')).toBe(color);
    expect(Number(screen.getByText(text).getAttribute('data-size'))).toBe(fontSizes.xs);
  });

  it('pulses only a working row', async () => {
    render(<RowState state="working" />);
    await act(async () => {});
    expect(screen.getByTestId('state-pulse')).toBeTruthy();
    expect(h.loops).toBe(1);
    cleanup();
    render(<RowState state="needs-you" />);
    expect(screen.getByTestId('state-dot')).toBeTruthy();
  });

  it('holds the working dot still under reduced motion', async () => {
    h.reduce = true;
    render(<RowState state="working" />);
    await act(async () => {});
    expect(screen.getByTestId('state-dot')).toBeTruthy();
    expect(h.loops).toBe(0);
  });

  it('shows the phase count of a running pipeline in place of the word', () => {
    render(<RowState state="working" phases="2/4" />);
    expect(screen.getByText('2/4')).toBeTruthy();
    expect(screen.queryByText('working')).toBeNull();
  });

  it('renders nothing for an idle row', () => {
    const { container } = render(<RowState state={null} />);
    expect(container.innerHTML).toBe('');
  });
});
