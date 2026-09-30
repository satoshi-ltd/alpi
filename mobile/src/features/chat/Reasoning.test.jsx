import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ reduce: false, repeats: 0 }));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-pad': style?.paddingHorizontal ?? '' }, children);
  const Text = ({ children, style, selectable, numberOfLines, accessibilityLiveRegion, ...p }) =>
    React.createElement('span', { ...p, 'data-size': style?.fontSize, 'data-font': style?.fontFamily, 'data-lh': style?.lineHeight }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, accessibilityRole, accessibilityLiveRegion, style, hitSlop, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-expanded': accessibilityState?.expanded, 'data-live': accessibilityLiveRegion, 'data-min-h': style?.minHeight, 'data-slop': (hitSlop?.top ?? 0) + (hitSlop?.bottom ?? 0), ...p }, children);
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

import { fonts, fontSizes, lineHeights, mobile } from '../../theme/tokens';
import { PROCESS_GAP, PROCESS_ROW_H } from './processRow';
import { Reasoning } from './Reasoning';

describe('Reasoning', () => {
  it('collapses to one compact “Thought for Xs” row whose slop only meets its neighbours', () => {
    render(<Reasoning text={'line one\nline two'} seconds={7} />);
    const row = screen.getByText('Thought for 7s');
    expect(screen.queryByText('line one')).toBeNull();
    const button = row.closest('button');
    expect(Number(button.getAttribute('data-min-h'))).toBe(PROCESS_ROW_H);
    expect(Number(button.getAttribute('data-slop'))).toBe(PROCESS_GAP);
    expect(row.getAttribute('data-font')).toBe(fonts.mono);
  });

  it('opens to a mono, relaxed, scrollable body', () => {
    render(<Reasoning text={'line one\nline two'} seconds={7} />);
    fireEvent.click(screen.getByText('Thought for 7s').closest('button'));
    const body = screen.getByText('line one');
    expect(body.getAttribute('data-font')).toBe(fonts.mono);
    expect(Number(body.getAttribute('data-size'))).toBe(fontSizes.sm);
    expect(Number(body.getAttribute('data-lh'))).toBe(fontSizes.sm * lineHeights.relaxed);
    expect(document.querySelector('[data-scroll]')).toBeTruthy();
  });

  it('marks the tool calls between reasoning spans in the opened body', () => {
    const timeline = [
      { kind: 'text', text: 'read the log' },
      { kind: 'tools', names: ['read_file', 'grep'] },
      { kind: 'text', text: 'wrap up' },
    ];
    render(<Reasoning text={'read the log\n\nwrap up'} seconds={3} timeline={timeline} />);
    fireEvent.click(screen.getByText('Thought for 3s').closest('button'));
    const spans = [...document.querySelectorAll('[data-scroll] span')].map((n) => n.textContent);
    expect(spans).toEqual(['read the log', '→ read_file, grep', 'wrap up']);
  });

  it('sets every label in the same mono face and size', () => {
    render(<Reasoning text={'first\nreading the deploy log'} streaming />);
    for (const label of [screen.getByText('Thinking…'), screen.getByText('reading the deploy log')]) {
      expect(label.getAttribute('data-font')).toBe(fonts.mono);
      expect(Number(label.getAttribute('data-size'))).toBe(fontSizes.sm);
    }
  });

  it('shows a shimmering Thinking label while it streams, with the latest line as a hint', () => {
    h.repeats = 0;
    render(<Reasoning text={'first\nreading the deploy log'} streaming />);
    expect(screen.getByText('Thinking…')).toBeTruthy();
    expect(screen.getByText('reading the deploy log')).toBeTruthy();
    expect(h.repeats).toBe(1);
  });

  it('keeps the Thinking label still under reduced motion', () => {
    h.repeats = 0;
    h.reduce = true;
    render(<Reasoning text="" streaming />);
    expect(screen.getByText('Thinking…')).toBeTruthy();
    expect(h.repeats).toBe(0);
    h.reduce = false;
  });

  it('collapses on its own when the answer lands', () => {
    const { rerender } = render(<Reasoning text={'step one'} streaming />);
    fireEvent.click(screen.getByText('Thinking…').closest('button'));
    expect(screen.getByText('step one')).toBeTruthy();
    rerender(<Reasoning text={'step one'} seconds={4} />);
    expect(screen.getByText('step one')).toBeTruthy();
    rerender(<Reasoning text={'step one'} seconds={4} answered />);
    expect(screen.queryByText('step one')).toBeNull();
    expect(screen.getByText('Thought for 4s')).toBeTruthy();
  });

  it('says a bare “Thought” when an old session has no seconds', () => {
    render(<Reasoning text="x" />);
    expect(screen.getByText('Thought')).toBeTruthy();
  });

  it('renders nothing when finished with no text', () => {
    const { container } = render(<Reasoning text="" seconds={0} />);
    expect(container.textContent).toBe('');
  });

  it('never drops below the 12 pt chat floor', () => {
    render(<Reasoning text={'hint line'} streaming />);
    for (const el of document.querySelectorAll('[data-size]')) {
      expect(Number(el.getAttribute('data-size'))).toBeGreaterThanOrEqual(12);
    }
  });

  it('shows a span with nothing to open as a static row with no chevron', () => {
    render(<Reasoning text="" seconds={4} />);
    expect(screen.getByText('Thought for 4s')).toBeTruthy();
    expect(screen.getByText('Thought for 4s').closest('button')).toBeNull();
    expect(document.querySelector('[data-icon="chevron-right"]')).toBeNull();
  });

  it('lets the visible label name the row and exposes the expanded state', () => {
    render(<Reasoning text={'line one'} seconds={7} />);
    const button = screen.getByText('Thought for 7s').closest('button');
    expect(button.getAttribute('aria-label')).toBeNull();
    expect(screen.getByRole('button', { name: 'Thought for 7s' })).toBe(button);
    expect(button.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(button);
    expect(button.getAttribute('aria-expanded')).toBe('true');
    expect(button.getAttribute('data-live')).toBe('none');
  });

  it('announces Thinking… politely before any text arrives', () => {
    render(<Reasoning text="" streaming />);
    const button = screen.getByText('Thinking…').closest('button');
    expect(button.getAttribute('aria-label')).toBeNull();
    expect(button.getAttribute('data-live')).toBe('polite');
  });
});
