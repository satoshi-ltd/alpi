import React from 'react';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  bottom: 0,
  flat: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const resolve = (style) => h.flat(style instanceof Function ? style({ pressed: false }) : style);
  const View = ({ children, style }) =>
    React.createElement('div', { 'data-style': JSON.stringify(resolve(style)) }, children);
  const Text = ({ children, style }) =>
    React.createElement('span', { 'data-style': JSON.stringify(resolve(style)) }, children);
  const Pressable = ({ children, style, hitSlop, accessibilityLabel, onPress, disabled }) =>
    React.createElement(
      'button',
      {
        type: 'button',
        'aria-label': accessibilityLabel,
        'data-hitslop': JSON.stringify(hitSlop ?? null),
        'data-style': JSON.stringify(resolve(style)),
        disabled: !!disabled,
        onClick: onPress,
      },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const TextInput = ({ style }) =>
    React.createElement('input', { readOnly: true, 'data-input': 'true', 'data-style': JSON.stringify(resolve(style)) });
  return {
    View,
    Text,
    Pressable,
    TextInput,
    Modal: ({ children, visible }) => (visible ? React.createElement('div', { 'data-modal': '' }, children) : null),
    useWindowDimensions: () => ({ height: 852, width: 393 }),
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    AppState: { addEventListener: () => ({ remove: () => {} }), currentState: 'active' },
    Dimensions: { get: () => ({ height: 852, width: 393 }), addEventListener: () => ({ remove: () => {} }) },
    Keyboard: { addListener: () => ({ remove: () => {} }), dismiss: () => {} },
    StyleSheet: { create: (s) => s },
  };
});

vi.mock('react-native-safe-area-context', () => ({
  useSafeAreaInsets: () => ({ top: 0, bottom: h.bottom, left: 0, right: 0 }),
}));

vi.mock('expo-constants', () => ({ default: { expoConfig: { version: '0.3.1' } } }));

vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      colors: tokens.palettes.light,
      fonts: tokens.fonts,
      fontSizes: tokens.fontSizes,
      lineHeights: tokens.lineHeights,
      mobile: tokens.mobile,
    }),
  };
});

vi.mock('../src/components/Icon', () => ({
  Icon: ({ name, size }) => React.createElement('span', { 'data-icon': name, 'data-size': size }),
}));
vi.mock('../src/features/chat/AttachmentCards', () => ({ AttachmentCards: () => React.createElement('span', {}) }));
vi.mock('../src/features/chat/MentionPopover', () => ({ MentionPopover: () => null }));

import { CHROME_H, COMPOSER_CTRL, COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../src/lib/panes';
import * as tokens from '../src/theme/tokens';
import { mobile, space } from '../src/theme/tokens';
import { COMPOSER_BTN, COMPOSER_H, Composer, composerPlaceholder } from '../src/features/chat/Composer';
import { ShellFooter } from '../src/features/shell/ShellFooter';
import { PaneContext } from '../src/nav/PaneContext';

const ROOT = join(import.meta.dirname, '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');
const styleOf = (el) => JSON.parse(el.getAttribute('data-style') || '{}');

function composerRow() {
  const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
  return [...container.querySelectorAll('div')].find((el) => styleOf(el).paddingTop === COMPOSER_PAD_Y);
}

function card(container) {
  return [...container.querySelectorAll('div')].find((el) => styleOf(el).minHeight === COMPOSER_H);
}

function restingHeight(row) {
  const outer = styleOf(row);
  return outer.paddingTop + COMPOSER_H + outer.paddingBottom;
}

function footerHeight() {
  const { container } = render(<ShellFooter onSettingsPress={() => {}} />);
  return styleOf(container.firstChild).height;
}

describe('composer and sidebar footer seam', () => {
  it.each([0, 20, 34])('gives the composer room to breathe above the footer line at a %ipt inset', (bottom) => {
    h.bottom = bottom;
    const composer = restingHeight(composerRow());
    cleanup();
    expect(composer).toBeGreaterThan(footerHeight() + bottom);
    expect(composer).toBeGreaterThan(COMPOSER_PAD_Y * 2 + COMPOSER_CTRL + bottom);
    h.bottom = 0;
  });

  it('lays +, the input and send in one row inside the pill, the input taking the rest', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const c = card(container);
    expect(styleOf(c).flexDirection).toBe('row');
    expect(styleOf(container.querySelector('[data-input]')).flex).toBe(1);
    expect(c.contains(screen.getByLabelText('Attach file'))).toBe(true);
    expect(c.contains(screen.getByLabelText('Send'))).toBe(true);
  });

  it('draws no footer rule in either pane mode: the phone draws no hairlines', () => {
    for (const twoPane of [true, false]) {
      const { container } = render(
        <PaneContext.Provider value={{ twoPane, side: 'list' }}>
          <ShellFooter onSettingsPress={() => {}} />
        </PaneContext.Provider>,
      );
      expect(styleOf(container.firstChild).borderTopWidth).toBeUndefined();
      cleanup();
    }
  });

  it('reads one constant instead of two hand-tuned numbers', () => {
    const composer = source('src/features/chat/Composer.jsx');
    expect(composer).toMatch(/Math\.max\(COMPOSER_PAD_Y, insets\.bottom\)/);
    expect(composer).toMatch(/Math\.max\(COMPOSER_PAD_Y, bottomInset - keyboard\.value\)/);
    expect(composer).not.toMatch(/Math\.max\(10/);
    expect(composer).not.toMatch(/: 44,/);
    expect(source('src/features/shell/ShellFooter.jsx')).toMatch(/height: CHROME_H/);
  });

  it('leaves the footer the bottom inset the composer takes on itself', () => {
    expect(source('src/features/shell/SidebarPane.jsx')).toMatch(/edges=\{\['top', 'left', 'bottom'\]\}/);
    expect(source('app/chat/[id].jsx')).not.toMatch(/edges=\{\[[^\]]*'bottom'/);
    expect(source('app/wg/[id].jsx')).not.toMatch(/edges=\{\[[^\]]*'bottom'/);
  });
});

describe('composer controls', () => {
  it('keeps 44pt of touch on both round controls', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    for (const label of ['Attach file', 'Send']) {
      const el = screen.getByLabelText(label);
      const slop = Number(JSON.parse(el.getAttribute('data-hitslop')));
      expect(styleOf(el).height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
      expect(slop).toBe(tapSlop(COMPOSER_BTN));
    }
    expect(screen.queryByLabelText('Voice message')).toBeNull();
  });

  it('offers stop instead of send while a turn is streaming', () => {
    const onStop = vi.fn();
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} busy onStop={onStop} />);
    expect(screen.queryByLabelText('Send')).toBeNull();
    const button = screen.getByLabelText('Stop');
    expect(button.disabled).toBe(false);
    expect(button.querySelector('[data-icon="square"]')).not.toBeNull();
    fireEvent.click(button);
    expect(onStop).toHaveBeenCalledTimes(1);
  });

  it('keeps the send button when nothing is streaming, and it stays disabled on an empty composer', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} onStop={() => {}} />);
    const button = screen.getByLabelText('Send');
    expect(button.disabled).toBe(true);
    expect(button.querySelector('[data-icon="arrow-up"]')).not.toBeNull();
  });

  it('starts the placeholder close to the pane gutter', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const row = [...container.querySelectorAll('div')].find((el) => styleOf(el).paddingTop === COMPOSER_PAD_Y);
    expect(styleOf(row).paddingHorizontal).toBe(PANE_PAD_X);
    expect(styleOf(card(container)).padding + COMPOSER_BTN).toBeLessThan(mobile.tap + space.s3);
  });
});

describe('composer matches the board', () => {
  it('draws the composer as one fill pill at the sheet corner, on the ground with no rule above it', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const c = styleOf(card(container));
    expect(c.backgroundColor).toBe(tokens.palettes.light.fill);
    expect(c.borderRadius).toBe(tokens.radii.sheet);
    expect(c.borderWidth).toBeUndefined();
    expect(styleOf(container.firstChild).borderTopWidth).toBeUndefined();
    expect(styleOf(container.firstChild).backgroundColor).toBe(tokens.palettes.light.bg);
  });

  it('draws send and + as 40 pt circles', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    for (const label of ['Send', 'Attach file']) {
      const st = styleOf(screen.getByLabelText(label));
      expect(st.width).toBe(40);
      expect(st.height).toBe(40);
      expect(st.borderRadius).toBe(tokens.radii.pill);
    }
  });

  it('gives send more weight than +, since only one is the primary action', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    expect(styleOf(screen.getByLabelText('Send')).backgroundColor).toBeTruthy();
    expect(styleOf(screen.getByLabelText('Attach file')).backgroundColor).toBe('transparent');
  });

  it('offers mention only where mentions exist, behind +', () => {
    const plain = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    expect(plain.container.textContent).not.toMatch(/mention/i);
    cleanup();
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} mentionSource={() => []} />);
    fireEvent.click(screen.getByLabelText('Add'));
    expect(screen.getByLabelText('Mention a peer').textContent).toMatch(/mention/i);
  });

  it('shows no keyboard shortcut — there is no modifier key on a phone', () => {
    const { container } = render(<Composer placeholder="Message @doc…" mentionSource={() => []} />);
    expect(container.textContent).not.toMatch(/⌘|↵/);
  });
});

describe('composer bottom clearance', () => {
  it('rides the system inset instead of stacking its own padding on top of it', () => {
    h.bottom = 34;
    const row = composerRow();
    expect(styleOf(row).paddingBottom).toBe(34);
    cleanup();
    h.bottom = 0;
    expect(styleOf(composerRow()).paddingBottom).toBe(COMPOSER_PAD_Y);
  });

  it('names the daemon outage in the placeholder instead of calling the profile paused', () => {
    expect(composerPlaceholder({ offline: true, disabled: true, placeholder: 'Message @doc…' })).toBe('Daemon unreachable — sending paused');
    expect(composerPlaceholder({ disabled: true, placeholder: 'Message @doc…' })).toBe('Paused — resume to chat');
    expect(composerPlaceholder({ placeholder: 'Message @doc…' })).toBe('Message @doc…');
  });
});
