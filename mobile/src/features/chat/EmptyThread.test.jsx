import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style }) =>
    React.createElement('div', { 'data-style': JSON.stringify(style) }, children),
  Text: ({ children, style, testID, numberOfLines }) =>
    React.createElement('span', { 'data-style': JSON.stringify(style), testid: testID, 'data-lines': numberOfLines }, children),
  Pressable: ({ children, onPress, testID, accessibilityLabel, accessibilityRole, style }) =>
    React.createElement('button', { onClick: onPress, testid: testID, 'aria-label': accessibilityLabel, role: accessibilityRole, 'data-style': JSON.stringify(typeof style === 'function' ? style({ pressed: false }) : style) }, children),
  ScrollView: ({ children, testID, contentContainerStyle }) =>
    React.createElement('div', { testid: testID, 'data-content': JSON.stringify(contentContainerStyle) }, children),
  Keyboard: { addListener: () => ({ remove: () => {} }), dismiss: () => {} },
  StyleSheet: { create: (s) => s },
}));
vi.mock('../../components/Button', () => ({ Button: () => null }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../../components/Fold', () => ({
  Fold: ({ shape, color, size }) => React.createElement('span', { 'data-mark': color, 'data-shape': String(shape), 'data-size': String(size) }),
}));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', fill: '#f2f2f2', pressed: '#ddd' },
      fonts: { sans: { semibold: 'semibold', regular: 'regular', medium: 'medium' }, mono: 'mono' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

import { EmptyThread } from './EmptyThread';
import { CONTENT_MAX_W } from '../../lib/panes';
import { fontSizes } from '../../theme/tokens';

function styles() {
  return [...document.querySelectorAll('[data-style]')].map((el) => el.getAttribute('data-style'));
}

describe('EmptyThread', () => {
  it('caps its column so a wide two-pane detail view keeps the hero centred', () => {
    render(<EmptyThread heading="start a thread with doc" detail="anthropic/claude-opus-5" accent="#abc123" />);
    expect(styles().some((s) => s.includes(`"maxWidth":${CONTENT_MAX_W}`))).toBe(true);
  });

  it('draws the heading at the display token and the profile fold in the accent', () => {
    render(<EmptyThread heading="start a thread with doc" detail="anthropic/claude-opus-5" accent="#abc123" shape="shield" />);
    expect(styles().some((s) => s.includes(`"fontSize":${fontSizes.xxl}`))).toBe(true);
    const mark = document.querySelector('[data-mark]');
    expect(mark.getAttribute('data-mark')).toBe('#abc123');
    expect(mark.getAttribute('data-size')).toBe('72');
    expect(mark.getAttribute('data-shape')).toBe('shield');
  });

  it('drops the detail line when the subject has no model', () => {
    render(<EmptyThread heading="no posts yet" accent="#abc123" />);
    expect([...document.querySelectorAll('span')].filter((el) => el.textContent).length).toBe(1);
  });

  it('introduces the profile with its bio, cut at five lines', () => {
    const bio = 'Migration assistant for MINT: inventories legacy bots, jobs and data, classifies reuse/repair/replace/retire, runs parallel comparisons and prepares staff-device authorization handoffs.';
    render(<EmptyThread heading="Start a new thread" detail="deepseek" accent="#abc123" bio={bio} />);
    const line = document.querySelector('[testid="thread-bio"]');
    expect(line.textContent).toBe(bio);
    expect(line.getAttribute('data-lines')).toBe('5');
  });

  it('offers to continue the latest session at a 44 pt target and opens it', () => {
    const onContinue = vi.fn();
    const ts = Math.floor(Date.now() / 1000) - 8 * 86400;
    render(<EmptyThread heading="Start a new thread" accent="#abc123" session={{ id: 's-1', title: 'Can we modify a booking?', ts }} onContinue={onContinue} />);
    const button = document.querySelector('[testid="thread-continue"]');
    expect(button.getAttribute('role')).toBe('button');
    expect(button.getAttribute('aria-label')).toBe('Continue “Can we modify a booking?”, 1w');
    expect(JSON.parse(button.getAttribute('data-style')).minHeight).toBe(44);
    expect(button.querySelector('[data-icon="history"]')).not.toBeNull();
    fireEvent.click(button);
    expect(onContinue).toHaveBeenCalledWith('s-1');
  });

  it('shows neither bio nor Continue when there is nothing to show', () => {
    render(<EmptyThread heading="Start a new thread" accent="#abc123" session={{ id: 's-1', title: 'x', ts: 0 }} />);
    expect(document.querySelector('[testid="thread-bio"]')).toBeNull();
    expect(document.querySelector('[testid="thread-continue"]')).toBeNull();
  });

  it('scrolls instead of spilling when a long bio and the keyboard leave no room', () => {
    render(<EmptyThread heading="Start a new thread" accent="#abc123" bio="x" session={{ id: 's', title: 't', ts: 1 }} onContinue={() => {}} />);
    const scroller = document.querySelector('[testid="thread-intro"]');
    expect(JSON.parse(scroller.getAttribute('data-content'))).toEqual({ flexGrow: 1 });
    expect(scroller.querySelector('[testid="thread-continue"]')).not.toBeNull();
  });
});
