import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

const { flat } = vi.hoisted(() => ({ flat: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)) }));

vi.mock('react-native', () => {
  const View = ({ children, style, testID }) => React.createElement('div', { 'data-testid': testID, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style, numberOfLines }) =>
    React.createElement('span', { 'data-lines': numberOfLines, 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, style, accessibilityLabel }) =>
    React.createElement('button', { type: 'button', 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(typeof style === 'function' ? style({ pressed: false }) : style)) }, children);
  return { View, Text, Pressable };
});
vi.mock('react-native-gesture-handler/ReanimatedSwipeable', () => ({
  default: ({ children }) => React.createElement('div', {}, children),
}));
vi.mock('../../lib/haptics', () => ({ tap: vi.fn() }));
vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => false }));
vi.mock('../../components/Fold', () => ({ Fold: () => React.createElement('i') }));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => React.createElement('b', { 'data-pill': '1' }, children) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', line: '#ddd', selected: '#eee', bgPane: '#fff' },
    fonts: { mono: 'mono', sans: { regular: 'r', semibold: 's', medium: 'm' } },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15 },
  }),
}));

import { FOLD_SIZE, FOLD_TOP, NotificationRow } from './NotificationRow';
import { dotScale } from '../../theme/tokens';

const ROW = {
  profile: 'sentinel',
  connectionName: 'mirai-dev',
  type: 'warning',
  title: 'PR #482 is waiting on you',
  body: 'Two blocking findings.',
  created_at: Date.now() / 1000 - 120,
};

const styleOf = (node) => JSON.parse(node.getAttribute('data-style'));

describe('NotificationRow header', () => {
  it('never wraps and keeps the time in a fixed trailing column', () => {
    const { container } = render(<NotificationRow row={ROW} unread multi />);
    const meta = container.querySelector('[data-testid="notification-meta"]');
    expect(styleOf(meta).flexWrap).toBeUndefined();
    const time = meta.lastChild;
    expect(styleOf(time).flexShrink).toBe(0);
    expect(time.getAttribute('data-lines')).toBe('1');
    expect(styleOf(meta.firstChild)).toMatchObject({ flex: 1, minWidth: 0 });
  });

  it('lets the name and the connection truncate instead of the time', () => {
    const { container } = render(<NotificationRow row={ROW} unread multi />);
    const [name, conn] = container.querySelector('[data-testid="notification-meta"]').firstChild.children;
    for (const node of [name, conn]) {
      expect(styleOf(node).flexShrink).toBe(1);
      expect(node.getAttribute('data-lines')).toBe('1');
    }
  });

  it('puts the level pill before the headline on the title line', () => {
    const { container } = render(<NotificationRow row={ROW} unread multi />);
    const title = container.querySelector('[data-testid="notification-title"]');
    expect(title.children[0].getAttribute('data-pill')).toBe('1');
    expect(title.children[0].textContent).toBe('warning');
    expect(title.children[1].textContent).toBe('PR #482 is waiting on you');
    expect(container.querySelector('[data-testid="notification-meta"] [data-pill]')).toBeNull();
  });

  it('holds the same title line height with and without a level', () => {
    const { container, rerender } = render(<NotificationRow row={ROW} unread multi />);
    const withLevel = styleOf(container.querySelector('[data-testid="notification-title"]')).minHeight;
    rerender(<NotificationRow row={{ ...ROW, type: 'info' }} unread multi />);
    expect(styleOf(container.querySelector('[data-testid="notification-title"]')).minHeight).toBe(withLevel);
    expect(withLevel).toBe(22);
  });
});

describe('NotificationRow unread dot', () => {
  it('shares its vertical centre with the fold beside it', () => {
    const { container } = render(<NotificationRow row={ROW} unread />);
    const [lane, foldBox] = container.querySelector('button').children;
    const dotCentre = styleOf(lane).paddingTop + dotScale.sm / 2;
    const foldCentre = styleOf(foldBox).paddingTop + FOLD_SIZE / 2;
    expect(styleOf(foldBox).paddingTop).toBe(FOLD_TOP);
    expect(dotCentre).toBe(foldCentre);
  });
});
