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

function restingHeight(row) {
  const style = styleOf(row);
  const tallest = Math.max(...[...row.children].map((el) => {
    const child = styleOf(el);
    return child.height ?? child.minHeight ?? 0;
  }));
  return style.paddingTop + tallest + style.paddingBottom;
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
    expect(composer).toBe(COMPOSER_PAD_Y * 2 + COMPOSER_CTRL + bottom);
    expect(composer).toBeGreaterThan(footerHeight() + bottom);
    h.bottom = 0;
  });

  it('keeps the composer field a full tap target instead of squeezing it to match the footer', () => {
    expect(COMPOSER_CTRL).toBe(44);
    expect(COMPOSER_CTRL).toBeGreaterThan(CHROME_H - COMPOSER_PAD_Y * 2);
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
    expect(composer).toMatch(/COMPOSER_PAD_Y \+ \(keyboardUp \? 0 : insets\.bottom\)/);
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
    expect(box.width + slop.left + slop.right).toBeGreaterThanOrEqual(mobile.tap);
    expect(box.height + slop.top + slop.bottom).toBeGreaterThanOrEqual(mobile.tap);

    const send = screen.getByLabelText('Send');
    const sendSlop = Number(JSON.parse(send.getAttribute('data-hitslop')));
    expect(styleOf(send).height + sendSlop * 2).toBeGreaterThanOrEqual(mobile.tap);
    expect(sendSlop).toBe(tapSlop(COMPOSER_CTRL));
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
    expect(attach.querySelector('[data-icon="paperclip"]').getAttribute('data-size')).toBe('md');
  });

  it('spends less room between the pane gutter and the placeholder', () => {
    const { container } = render(<Composer placeholder="Message @doc…" onPickAttachment={() => {}} />);
    const row = [...container.querySelectorAll('div')].find((el) => styleOf(el).paddingTop === COMPOSER_PAD_Y);
    const input = styleOf(container.querySelector('[data-input]'));
    const attach = styleOf(screen.getByLabelText('Attach file'));
    const textStart = styleOf(row).paddingHorizontal + attach.width + styleOf(row).gap + input.paddingHorizontal;
    expect(styleOf(row).paddingHorizontal).toBe(PANE_PAD_X);
    expect(input.paddingHorizontal).toBeLessThan(PANE_PAD_X);
    expect(textStart).toBeLessThan(PANE_PAD_X + mobile.tap + space.s3 + PANE_PAD_X);
  });
});
