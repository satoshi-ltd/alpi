import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ reduce: false, repeats: 0 }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-pad': style?.paddingHorizontal ?? '' }, children);
  const Text = ({ children, style, selectable, numberOfLines, accessibilityLiveRegion, ...p }) =>
    React.createElement('span', { ...p, 'data-size': style?.fontSize, 'data-font': style?.fontFamily }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, accessibilityRole, style, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-min-h': style?.minHeight, ...p }, children);
  const ScrollView = ({ children, nestedScrollEnabled, onContentSizeChange, contentContainerStyle, style }) =>
    React.createElement('div', { 'data-scroll': 'true', 'data-max-h': style?.maxHeight }, children);
  return { View, Text, Pressable, ScrollView, useWindowDimensions: () => ({ height: 800 }) };
});

vi.mock('react-native-reanimated', async () => {
  const base = await import('../../../tests/mocks/reanimated.js');
  return { ...base, withRepeat: (v) => { h.repeats += 1; return v; } };
});

vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => h.reduce }));

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink2: '#333', ink3: '#666', ink4: '#999', line: '#eee', bg: '#fff' },
      fonts: tokens.fonts,
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

import { fonts, fontSizes, mobile } from '../../theme/tokens';
import { Reasoning } from './Reasoning';

describe('Reasoning', () => {
  it('collapses to one “Thought for Xs” row and opens to readable sans', () => {
    render(<Reasoning text={'line one\nline two'} seconds={7} flat />);
    const row = screen.getByText('Thought for 7s');
    expect(screen.queryByText('line one')).toBeNull();
    expect(Number(row.closest('button').getAttribute('data-min-h'))).toBe(mobile.tap);
    fireEvent.click(row.closest('button'));
    const body = screen.getByText('line one');
    expect(body.getAttribute('data-font')).toBe(fonts.sans.regular);
    expect(Number(body.getAttribute('data-size'))).toBeGreaterThanOrEqual(13);
    expect(document.querySelector('[data-scroll]')).toBeTruthy();
  });

  it('shows a shimmering Thinking label while it streams, with the latest line as a hint', () => {
    h.repeats = 0;
    render(<Reasoning text={'first\nreading the deploy log'} streaming flat />);
    expect(screen.getByText('Thinking…')).toBeTruthy();
    expect(screen.getByText('reading the deploy log')).toBeTruthy();
    expect(h.repeats).toBe(1);
  });

  it('keeps the Thinking label still under reduced motion', () => {
    h.repeats = 0;
    h.reduce = true;
    render(<Reasoning text="" streaming flat />);
    expect(screen.getByText('Thinking…')).toBeTruthy();
    expect(h.repeats).toBe(0);
    h.reduce = false;
  });

  it('collapses on its own when the answer lands', () => {
    const { rerender } = render(<Reasoning text={'step one'} streaming flat />);
    fireEvent.click(screen.getByText('Thinking…').closest('button'));
    expect(screen.getByText('step one')).toBeTruthy();
    rerender(<Reasoning text={'step one'} seconds={4} flat />);
    expect(screen.getByText('step one')).toBeTruthy();
    rerender(<Reasoning text={'step one'} seconds={4} answered flat />);
    expect(screen.queryByText('step one')).toBeNull();
    expect(screen.getByText('Thought for 4s')).toBeTruthy();
  });

  it('says a bare “Thought” when an old session has no seconds', () => {
    render(<Reasoning text="x" flat />);
    expect(screen.getByText('Thought')).toBeTruthy();
  });

  it('renders nothing when finished with no text', () => {
    const { container } = render(<Reasoning text="" seconds={0} flat />);
    expect(container.textContent).toBe('');
  });

  it('indents to the same gutter as its sibling turn rows', () => {
    const { container } = render(<Reasoning text={'line one'} seconds={3} flat />);
    const pads = [...container.querySelectorAll('div')]
      .map((node) => node.getAttribute('data-pad'))
      .filter((pad) => pad !== '');
    expect(pads).toContain('16');
  });

  it('never drops below the 12 pt chat floor', () => {
    render(<Reasoning text={'hint line'} streaming flat />);
    for (const el of document.querySelectorAll('[data-size]')) {
      expect(Number(el.getAttribute('data-size'))).toBeGreaterThanOrEqual(12);
    }
  });
});
