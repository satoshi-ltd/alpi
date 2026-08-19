import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => ({
  View: ({ children, style }) =>
    React.createElement('div', { 'data-style': JSON.stringify(style) }, children),
  Text: ({ children, style }) =>
    React.createElement('span', { 'data-style': JSON.stringify(style) }, children),
  Keyboard: { addListener: () => ({ remove: () => {} }) },
  StyleSheet: { create: (s) => s },
}));
vi.mock('../../components/AlpiMark', () => ({
  AlpiMark: ({ color, size }) => React.createElement('span', { 'data-mark': color, 'data-size': String(size) }),
}));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink3: '#666' },
      fonts: { sans: { semibold: 'semibold' }, mono: 'mono' },
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

  it('draws the heading at the display token and tints the silhouette with the accent', () => {
    render(<EmptyThread heading="start a thread with doc" detail="anthropic/claude-opus-5" accent="#abc123" />);
    expect(styles().some((s) => s.includes(`"fontSize":${fontSizes.xxl}`))).toBe(true);
    expect(document.querySelector('[data-mark]').getAttribute('data-mark')).toBe('#abc123');
  });

  it('drops the detail line when the subject has no model', () => {
    render(<EmptyThread heading="no posts yet" accent="#abc123" />);
    expect([...document.querySelectorAll('span')].filter((el) => el.textContent).length).toBe(1);
  });
});
