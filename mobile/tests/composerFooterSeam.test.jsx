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
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Keyboard: { addListener: () => ({ remove: () => {} }) },
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

import { CHROME_BTN, CHROME_H, COMPOSER_CTRL, COMPOSER_PAD_Y, PANE_PAD_X, tapSlop } from '../src/lib/panes';
import * as tokens from '../src/theme/tokens';
import { mobile, space } from '../src/theme/tokens';
import { Composer } from '../src/features/chat/Composer';
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
  return [...container.querySelectorAll('div')].find((el) => styleOf(el).borderRadius !== undefined);
}

function restingHeight(row) {
  const outer = styleOf(row);
  const c = styleOf(card(row.ownerDocument.body));
  const ctrl = Math.max(...[...row.querySelectorAll('button')].map((b) => styleOf(b).height ?? 0), 0);
  const line = Math.round(15 * 1.5);
  return outer.paddingTop + c.paddingTop + line + c.gap + ctrl + c.paddingBottom + outer.paddingBottom;
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

  it('stacks the controls under the text like desktop, so the field owns the full card width', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const c = card(container);
    expect(styleOf(c).flexDirection).toBeUndefined();
    const input = container.querySelector('[data-input]');
    expect(styleOf(input).flex).toBeUndefined();
    const row = [...c.querySelectorAll('div')].find((el) => styleOf(el).flexDirection === 'row');
    expect(row.contains(screen.getByLabelText('Attach file'))).toBe(true);
    expect(row.contains(screen.getByLabelText('Send'))).toBe(true);
  });

  it('drops the footer rule in two-pane, so nothing invites the eye to compare the two heights', () => {
    const inPane = (twoPane) => {
      const { container } = render(
        <PaneContext.Provider value={{ twoPane, side: 'list' }}>
          <ShellFooter onSettingsPress={() => {}} />
        </PaneContext.Provider>,
      );
      const width = styleOf(container.firstChild).borderTopWidth;
      cleanup();
      return width;
    };
    expect(inPane(true)).toBe(0);
    expect(inPane(false)).toBeGreaterThan(0);
  });

  it('reads one constant instead of two hand-tuned numbers', () => {
    const composer = source('src/features/chat/Composer.jsx');
    expect(composer).toMatch(/Math\.max\(COMPOSER_PAD_Y, insets\.bottom\)/);
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
  it('keeps 44pt of touch on every shrunken control', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const attach = screen.getByLabelText('Attach file');
    const slop = JSON.parse(attach.getAttribute('data-hitslop'));
    const box = styleOf(attach);
    const pad = typeof slop === 'number' ? { left: slop, right: slop, top: slop, bottom: slop } : slop;
    expect(box.width + pad.left + pad.right).toBeGreaterThanOrEqual(mobile.tap);
    expect(box.height + pad.top + pad.bottom).toBeGreaterThanOrEqual(mobile.tap);

    const send = screen.getByLabelText('Send');
    const sendSlop = Number(JSON.parse(send.getAttribute('data-hitslop')));
    expect(styleOf(send).height + sendSlop * 2).toBeGreaterThanOrEqual(mobile.tap);
    expect(sendSlop).toBe(tapSlop(styleOf(send).height));
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
    expect(button.querySelector('[data-icon="send"]')).not.toBeNull();
  });

  it('shrinks the attach box and its glyph so the field is not shoved over', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const attach = screen.getByLabelText('Attach file');
    expect(styleOf(attach).width).toBe(CHROME_BTN);
    expect(styleOf(attach).width).toBeLessThan(mobile.tap);
    expect(attach.querySelector('[data-icon="paperclip"]').getAttribute('data-size')).toBe('lg');
  });

  it('spends less room between the pane gutter and the placeholder', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const row = [...container.querySelectorAll('div')].find((el) => styleOf(el).paddingTop === COMPOSER_PAD_Y);
    const textStart = styleOf(row).paddingHorizontal + styleOf(card(container)).paddingHorizontal;
    expect(styleOf(row).paddingHorizontal).toBe(PANE_PAD_X);
    expect(textStart).toBeLessThan(PANE_PAD_X + mobile.tap + space.s3);
  });
});

describe('composer matches the desktop card', () => {
  it('fills the card white and rules it off from the transcript, as desktop does', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const c = styleOf(card(container));
    expect(c.backgroundColor).toBe(tokens.palettes.light.bgElev);
    expect(c.backgroundColor).not.toBe(tokens.palettes.light.bgInput);
    expect(styleOf(container.firstChild).borderTopWidth).toBeGreaterThan(0);
  });

  it('draws send as a rounded square of desktop\'s size, not a circle', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const send = styleOf(screen.getByLabelText('Send'));
    expect(send.width).toBe(30);
    expect(send.height).toBe(30);
    expect(send.borderRadius).toBe(tokens.radii.lg);
    expect(send.borderRadius).not.toBe(tokens.radii.pill);
  });

  it('gives send more weight than attach, since only one is the primary action', () => {
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const send = styleOf(screen.getByLabelText('Send'));
    const attach = styleOf(screen.getByLabelText('Attach file'));
    expect(send.backgroundColor).toBeTruthy();
    expect(attach.backgroundColor).toBeUndefined();
  });

  it('offers a tappable mention affordance only where mentions exist', () => {
    const plain = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    expect(plain.container.textContent).not.toMatch(/mention/i);
    cleanup();
    render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} mentionSource={() => []} />);
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
});
