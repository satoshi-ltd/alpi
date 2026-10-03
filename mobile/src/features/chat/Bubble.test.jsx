import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { fontSizes, space, palettes } from '../../theme/tokens';

const themeState = vi.hoisted(() => ({ mode: 'light', reduce: false, ticks: [] }));
afterEach(() => { cleanup(); themeState.mode = 'light'; themeState.reduce = false; themeState.ticks.length = 0; });

const { flatStyle } = vi.hoisted(() => ({
  flatStyle: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const View = ({ children, style, ...p }) =>
    React.createElement('div', { ...p, 'data-style': JSON.stringify(flatStyle(style)) }, children);
  const Text = ({ children, style, ...p }) => React.createElement('span', { ...p, 'data-text-size': style?.fontSize, 'data-text-color': style?.color }, children);
  const Pressable = ({ children, style, onLongPress, delayLongPress, ...p }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        ...p,
        onContextMenu: onLongPress,
        'data-style': JSON.stringify(flatStyle(typeof style === 'function' ? style({ pressed: false }) : style)),
        'data-pressed-style': JSON.stringify(flatStyle(typeof style === 'function' ? style({ pressed: true }) : style)),
      },
      children,
    );
  return { View, Text, Pressable, StyleSheet: { create: (s) => s } };
});

vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return {
    useTheme: () => ({
      colors: tokens.palettes[themeState.mode],
      fonts: { sans: { regular: 'Geist_400Regular' }, monoMedium: 'GeistMono_500Medium' },
      fontSizes: tokens.fontSizes,
    }),
  };
});

vi.mock('../../lib/reduceMotion', () => ({ useReduceMotion: () => themeState.reduce }));
vi.mock('../../lib/haptics', () => ({ selection: () => themeState.ticks.push('selection'), tap: () => themeState.ticks.push('tap') }));
vi.mock('../../components/Fold', () => ({ Fold: ({ fold, color, size, outlined }) => React.createElement('span', { 'data-fold': fold ?? 'diamond', 'data-color': color, 'data-size': size, 'data-outlined': String(!!outlined) }) }));
vi.mock('./AttachmentCards', () => ({ AttachmentCards: () => React.createElement('span', { 'data-cards': 'true' }) }));
vi.mock('../../components/RichText', () => ({
  RichText: ({ children, size, color }) => React.createElement('span', { 'data-size': String(size), 'data-color': color }, children),
}));

import { BUBBLE_MAX_PANE } from '../../lib/panes';
import { PaneContext } from '../../nav/PaneContext';
import { state as motion } from '../../../tests/mocks/reanimated.js';
import { LONG_PRESS_MS, PULSE_FROM, PULSE_MS, ProfileAssistantMessage, ProfileUserMessage, WorkgroupMessage } from './Bubble';

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
    expect(size).toBe(fontSizes.chat);
    expect(size).toBe(16);
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

describe('workgroup speaker fold', () => {
  it('marks the speaker with their fold in their accent', () => {
    const { container } = render(<WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" speakerFold="shield" seq={7} />);
    const fold = container.querySelector('[data-fold]');
    expect(fold.getAttribute('data-fold')).toBe('shield');
    expect(fold.getAttribute('data-color')).toBe('#0af0af');
  });

  it('marks the hub on the right with the same fold', () => {
    const { container } = render(<WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" speakerFold="tree" isFromHub seq={7} />);
    expect(container.querySelectorAll('[data-fold="tree"]')).toHaveLength(1);
  });

  it('falls back to the diamond for a speaker with no fold', () => {
    const { container } = render(<WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" seq={7} />);
    expect(container.querySelector('[data-fold]').getAttribute('data-fold')).toBe('diamond');
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


describe('user bubble palette', () => {
  it.each(['light', 'dark'])('draws your message as a neutral 4 pt sheet with no profile tint in %s', (mode) => {
    themeState.mode = mode;
    const { container } = render(<ProfileUserMessage text="Readable message" accent="#f0b447" />);
    const style = JSON.parse(container.querySelector('button').getAttribute('data-style'));
    expect(style.backgroundColor).toBe(palettes[mode].selected);
    expect(style.borderTopRightRadius).toBe(4);
    expect(style.borderBottomLeftRadius).toBe(4);
    expect(screen.getByText('Readable message').getAttribute('data-color')).toBe(palettes[mode].ink);
    expect(style.paddingHorizontal).toBe(space.s7);
  });
});

describe('message footer and long press', () => {
  it('gives agent messages the same faint time as user messages', () => {
    render(<ProfileAssistantMessage text="shipped" ts="2m" />);
    const stamp = screen.getByText('2m');
    expect(Number(stamp.getAttribute('data-text-size'))).toBe(fontSizes.sm);
    expect(Number(stamp.getAttribute('data-text-size'))).toBeGreaterThanOrEqual(12);
    expect(stamp.getAttribute('data-text-color')).toBe(palettes.light.ink3);
    cleanup();
    render(<ProfileUserMessage text="ship it" ts="2m" accent="#b8954a" />);
    expect(screen.getByText('2m').getAttribute('data-text-size')).toBe(String(fontSizes.sm));
  });

  it('ticks and opens the menu on long press', () => {
    const onLongPress = vi.fn();
    render(<ProfileAssistantMessage text="shipped" onLongPress={onLongPress} />);
    fireEvent.contextMenu(screen.getByText('shipped').closest('button'));
    expect(onLongPress).toHaveBeenCalledTimes(1);
    expect(themeState.ticks).toEqual(['selection']);
  });

  it.each(VARIANTS)('does not move the %s bubble on press-in or a short tap', (_name, Variant) => {
    const { container } = render(Variant());
    const button = container.querySelector('button');
    expect(button.getAttribute('data-pressed-style')).toBe(button.getAttribute('data-style'));
    expect(JSON.parse(button.getAttribute('data-style')).transform).toEqual([{ scale: 1 }]);
  });

  it('pulses 0.985 → 1 over 160 ms with the haptic only once the long press lands', () => {
    motion.timings.length = 0;
    render(<ProfileUserMessage text="ship it" accent="#b8954a" onLongPress={() => {}} />);
    expect(motion.timings).toEqual([]);
    fireEvent.contextMenu(screen.getByText('ship it').closest('button'));
    expect(motion.timings).toEqual([{ to: PULSE_FROM, duration: 0 }, { to: 1, duration: PULSE_MS }]);
    expect(themeState.ticks).toEqual(['selection']);
    expect([PULSE_FROM, PULSE_MS, LONG_PRESS_MS]).toEqual([0.985, 160, 350]);
  });

  it('keeps the haptic but drops the pulse under reduced motion', () => {
    themeState.reduce = true;
    motion.timings.length = 0;
    const { container } = render(<WorkgroupMessage body="status?" speakerName="scout" speakerAccent="#0af0af" onLongPress={() => {}} />);
    expect(JSON.parse(container.querySelector('button').getAttribute('data-style')).transform).toBeUndefined();
    fireEvent.contextMenu(screen.getByText('status?').closest('button'));
    expect(motion.timings).toEqual([]);
    expect(themeState.ticks).toEqual(['selection']);
  });

});
