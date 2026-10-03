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
      colors: { accent: '#accent', ink2: '#ink2', warningText: '#warn', dangerText: '#danger' },
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
    ['working', 'working', '#ink2'],
  ])('%s reads "%s" in its own colour', (state, text, color) => {
    render(<RowState state={state} />);
    expect(screen.getByText(text).getAttribute('data-color')).toBe(color);
    expect(Number(screen.getByText(text).getAttribute('data-size'))).toBe(fontSizes.xs);
  });

  it('paints a working row in its profile colour when the row knows it', () => {
    render(<RowState state="working" color="#3ac9f3" />);
    expect(screen.getByText('working').getAttribute('data-color')).toBe('#3ac9f3');
  });

  it('keeps needs-you and failed in their status colours whatever the profile colour', () => {
    render(<RowState state="needs-you" color="#3ac9f3" />);
    expect(screen.getByText('needs you').getAttribute('data-color')).toBe('#warn');
  });

  it('says working with the word alone, leaving the motion to the object', async () => {
    render(<RowState state="working" />);
    await act(async () => {});
    expect(screen.queryByTestId('state-pulse')).toBeNull();
    expect(screen.queryByTestId('state-dot')).toBeNull();
    expect(h.loops).toBe(0);
    cleanup();
    render(<RowState state="needs-you" />);
    expect(screen.getByTestId('state-dot')).toBeTruthy();
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
