import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';
import { fontSizes, space } from '../../theme/tokens';

afterEach(cleanup);

const { flatStyle } = vi.hoisted(() => ({
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-style': JSON.stringify(flatStyle(style)) }, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, style, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', ...p, 'data-style': JSON.stringify(flatStyle(typeof style === 'function' ? style({ pressed: false }) : style)) },
      children,
    );
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#0b1117', ink3: '#7c8896', bgPane: '#ffffff' },
      fonts: { sans: { regular: 'Inter_400Regular' }, monoMedium: 'JetBrainsMono_500Medium' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../components/Diamond', () => ({ Diamond: () => React.createElement('span', { 'data-diamond': 'true' }) }));
vi.mock('./AttachmentCards', () => ({ AttachmentCards: () => React.createElement('span', { 'data-cards': 'true' }) }));
vi.mock('../../components/RichText', () => ({
  RichText: ({ children, size }) => React.createElement('span', { 'data-size': String(size) }, children),
}));

import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { PaneContext } from '../../nav/PaneContext';
import { ProfileAssistantMessage, ProfileUserMessage, WorkgroupMessage } from './Bubble';

function bodySize(container) {
  return Number(container.querySelector('[data-size]').getAttribute('data-size'));
}

function rowStyle(container) {
  return JSON.parse(container.firstChild.getAttribute('data-style'));
}

const VARIANTS = [
  ['user', () => <ProfileUserMessage text="ship it" ts="now" accent="#b8954a" />],
  ['assistant', () => <ProfileAssistantMessage text="shipped" />],
  ['workgroup', () => <WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" seq={7} />],
];

describe('transcript body type scale', () => {
  it.each(VARIANTS)('sizes the %s body from the token scale', (_name, Variant) => {
    const { container } = render(Variant());
    const size = bodySize(container);
    expect(size).toBe(fontSizes.lg);
    expect(Object.values(fontSizes)).toContain(size);
  });

  it('resolves every transcript body variant to one token', () => {
    const sizes = VARIANTS.map(([, Variant]) => {
      const { container } = render(Variant());
      const size = bodySize(container);
      cleanup();
      return size;
    });
    expect(new Set(sizes).size).toBe(1);
  });
});

describe('transcript row gutter', () => {
  it.each(VARIANTS)('keeps the %s row on the phone gutter token', (_name, Variant) => {
    const { container } = render(Variant());
    expect(rowStyle(container).paddingHorizontal).toBe(space.s7);
  });
});

const CAPPED = [
  ['profile user', () => <ProfileUserMessage text="ship it" ts="now" accent="#b8954a" />, '82%'],
  ['workgroup', () => <WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" seq={7} />, '90%'],
];

function bubbleCap(container) {
  return JSON.parse(container.querySelector('button').getAttribute('data-style')).maxWidth;
}

function inTwoPane(node) {
  return render(<PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>{node}</PaneContext.Provider>);
}

describe('bubble cap by pane mode', () => {
  it.each(CAPPED)('keeps the %s phone cap outside a pane provider', (_name, Variant, pct) => {
    const { container } = render(Variant());
    expect(bubbleCap(container)).toBe(pct);
  });

  it.each(CAPPED)('narrows the %s bubble to the desktop cap in two-pane mode', (_name, Variant, pct) => {
    const { container } = inTwoPane(Variant());
    expect(bubbleCap(container)).toBe(BUBBLE_MAX_PANE);
    expect(bubbleCap(container)).not.toBe(pct);
  });
});
