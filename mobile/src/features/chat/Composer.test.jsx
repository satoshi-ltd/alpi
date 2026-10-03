import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  listeners: {},
  haptics: [],
  flat: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const resolve = (style) => h.flat(style instanceof Function ? style({ pressed: false }) : style);
  const View = ({ children, style }) => React.createElement('div', { 'data-style': JSON.stringify(resolve(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-size': resolve(style).fontSize }, children);
  const Pressable = ({ children, style, hitSlop, accessibilityLabel, onPress, disabled }) =>
    React.createElement(
      'button',
      { type: 'button', 'aria-label': accessibilityLabel, 'data-hitslop': JSON.stringify(hitSlop ?? null), 'data-style': JSON.stringify(resolve(style)), disabled: !!disabled, onClick: onPress },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, onFocus, onBlur, submitBehavior, onSubmitEditing, returnKeyType, style }) =>
    React.createElement('textarea', {
      value,
      'data-submit': submitBehavior,
      'data-return': returnKeyType ?? '',
      'data-size': resolve(style).fontSize,
      onChange: (e) => onChangeText(e.target.value),
      onFocus,
      onBlur,
      onKeyDown: (e) => { if (e.key === 'Enter') onSubmitEditing?.(); },
    });
  return {
    View,
    Text,
    Pressable,
    TextInput,
    Keyboard: {
      addListener: (event, fn) => {
        h.listeners[event] = fn;
        return { remove: () => { delete h.listeners[event]; } };
      },
    },
  };
});

vi.mock('react-native-safe-area-context', () => ({ useSafeAreaInsets: () => ({ top: 0, bottom: 34, left: 0, right: 0 }) }));
vi.mock('../../lib/haptics', () => ({ tap: () => h.haptics.push('tap'), selection: () => h.haptics.push('selection') }));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('span', { 'data-icon': name }) }));
vi.mock('./AttachmentCards', () => ({ AttachmentCards: () => null }));
vi.mock('./MentionPopover', () => ({ MentionPopover: () => null }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return { useTheme: () => ({ colors: tokens.palettes.light, fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});

import { state as keyboard } from '../../../tests/mocks/reanimated.js';
import { COMPOSER_PAD_Y } from '../../lib/panes';
import { fontSizes, mobile, typography } from '../../theme/tokens';
import { Composer } from './Composer';

beforeEach(() => {
  h.haptics.length = 0;
  keyboard.keyboardHeight = 0;
});

function field() {
  return document.querySelector('textarea');
}

function type(text) {
  fireEvent.change(field(), { target: { value: text } });
}

describe('Return in the composer', () => {
  it.each([336, 69, 0])('adds a line and never sends, whatever keyboard is up (%i pt)', (height) => {
    const onSend = vi.fn();
    render(<Composer onSend={onSend} />);
    fireEvent.focus(field());
    h.listeners.keyboardDidShow?.({ endCoordinates: { height } });
    type('first line');
    expect(field().getAttribute('data-submit')).toBe('newline');
    fireEvent.keyDown(field(), { key: 'Enter' });
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('Send'));
    expect(onSend).toHaveBeenCalledWith('first line', []);
  });

  it('never labels the soft return key as send', () => {
    render(<Composer onSend={() => {}} />);
    expect(field().getAttribute('data-return')).toBe('');
  });
});

describe('send and stop', () => {
  it('give a light haptic', () => {
    const onStop = vi.fn();
    const { rerender } = render(<Composer onSend={() => {}} />);
    type('hi');
    fireEvent.click(screen.getByLabelText('Send'));
    rerender(<Composer onSend={() => {}} busy onStop={onStop} />);
    fireEvent.click(screen.getByLabelText('Stop'));
    expect(onStop).toHaveBeenCalledTimes(1);
    expect(h.haptics).toEqual(['tap', 'tap']);
  });
});

describe('model chip', () => {
  it('shows model · effort in the bottom row and opens on tap', () => {
    const onPress = vi.fn();
    render(<Composer onSend={() => {}} modelChip={{ label: 'sonnet-4 · medium', onPress }} />);
    const chip = screen.getByLabelText('Model and effort: sonnet-4 · medium');
    expect(chip.textContent).toContain('sonnet-4 · medium');
    const box = JSON.parse(chip.getAttribute('data-style'));
    const slop = Number(JSON.parse(chip.getAttribute('data-hitslop')));
    expect(box.height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    fireEvent.click(chip);
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('is absent without the admin gate', () => {
    render(<Composer onSend={() => {}} />);
    expect(screen.queryByLabelText(/Model and effort/)).toBeNull();
  });
});

describe('composer text and keyboard', () => {
  it('types at the chat body size', () => {
    render(<Composer onSend={() => {}} />);
    expect(Number(field().getAttribute('data-size'))).toBe(fontSizes[typography.chat.size]);
  });

  it('hands the home-indicator inset to the keyboard as it rises', () => {
    const bottomPad = () =>
      [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style'))).find((st) => st.paddingTop === COMPOSER_PAD_Y).paddingBottom;
    render(<Composer onSend={() => {}} />);
    expect(bottomPad()).toBe(34);
    cleanup();
    keyboard.keyboardHeight = 20;
    render(<Composer onSend={() => {}} />);
    expect(bottomPad()).toBe(14);
    cleanup();
    keyboard.keyboardHeight = 300;
    render(<Composer onSend={() => {}} />);
    expect(bottomPad()).toBe(COMPOSER_PAD_Y);
  });
});

describe('initial text', () => {
  it('starts with the text a reply hands it', () => {
    render(<Composer onSend={() => {}} initialText={'> **Digest**\n\n'} />);
    expect(document.querySelector('textarea').value).toBe('> **Digest**\n\n');
  });
});
