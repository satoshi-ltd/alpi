import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  listeners: {},
  haptics: [],
  flat: (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean)),
}));

vi.mock('react-native', () => {
  const resolve = (style) => h.flat(style instanceof Function ? style({ pressed: false }) : style);
  const View = ({ children, style }) => React.createElement('div', { 'data-style': JSON.stringify(resolve(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-size': resolve(style).fontSize, 'data-shrink': resolve(style).flexShrink }, children);
  const Pressable = ({ children, style, hitSlop, accessibilityLabel, onPress, disabled, onFocus, onBlur, testID }) =>
    React.createElement(
      'button',
      { type: 'button', 'data-testid': testID, 'aria-label': accessibilityLabel, 'data-hitslop': JSON.stringify(hitSlop ?? null), 'data-style': JSON.stringify(resolve(style)), disabled: !!disabled, onClick: onPress, onFocus, onBlur },
      children instanceof Function ? children({ pressed: false }) : children,
    );
  const TextInput = ({ value, onChangeText, onFocus, onBlur, submitBehavior, onSubmitEditing, returnKeyType, style, placeholderTextColor }) =>
    React.createElement('textarea', {
      value,
      'data-submit': submitBehavior,
      'data-return': returnKeyType ?? '',
      'data-placeholder-color': placeholderTextColor,
      'data-size': resolve(style).fontSize,
      onChange: (e) => onChangeText(e.target.value),
      onFocus,
      onBlur,
      onKeyDown: (e) => { if (e.key === 'Enter') onSubmitEditing?.(); },
    });
  const Modal = ({ children, visible, onRequestClose }) => (visible ? React.createElement('div', { 'data-modal': '', onKeyDown: (e) => { if (e.key === 'Escape') onRequestClose?.(); } }, children) : null);
  return {
    View,
    Text,
    Pressable,
    TextInput,
    Modal,
    useWindowDimensions: () => ({ height: 852, width: 393 }),
    AppState: { addEventListener: () => ({ remove: () => {} }), currentState: 'active' },
    Platform: { OS: 'ios', select: (s) => s?.ios ?? s?.default },
    Dimensions: { get: () => ({ height: 852, width: 393 }), addEventListener: () => ({ remove: () => {} }) },
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
vi.mock('../../components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', 'data-resume': title, onClick: onPress }, title) }));
vi.mock('./AttachmentCards', () => ({ AttachmentCards: () => null }));
vi.mock('../../components/EdgeFade', () => ({ EdgeFade: ({ side }) => React.createElement('span', { 'data-fade': side }) }));
vi.mock('./MentionPopover', () => ({ MentionPopover: ({ candidates, token }) => React.createElement('div', { 'data-mention': token, 'data-count': candidates.length }) }));
vi.mock('../../theme/ThemeContext', async () => {
  const tokens = await import('../../theme/tokens');
  return { useTheme: () => ({ colors: tokens.palettes.light, fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});

import { state as keyboard } from '../../../tests/mocks/reanimated.js';
import { COMPOSER_PAD_Y } from '../../lib/panes';
import { fontSizes, mobile, palettes, radii, typography } from '../../theme/tokens';
import { COMPOSER_BTN, COMPOSER_H, Composer } from './Composer';

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

describe('stop while the composer is disabled', () => {
  it('still stops a running turn when the profile is paused or the daemon is unreachable, and stays dimmed', () => {
    const onStop = vi.fn();
    render(<Composer onSend={() => {}} busy onStop={onStop} disabled offline />);
    const stop = screen.getByLabelText('Stop');
    fireEvent.click(stop);
    expect(onStop).toHaveBeenCalledTimes(1);
    expect(JSON.parse(stop.getAttribute('data-style')).opacity).toBeLessThan(1);
  });

  it('keeps Send inert when disabled', () => {
    const onSend = vi.fn();
    const { rerender } = render(<Composer onSend={onSend} />);
    type('hi');
    rerender(<Composer onSend={onSend} disabled />);
    fireEvent.click(screen.getByLabelText('Send'));
    expect(onSend).not.toHaveBeenCalled();
  });
});

describe('model chip', () => {
  it('moves model · effort into the + menu on the phone and opens its picker from there', () => {
    const onPress = vi.fn();
    render(<Composer onSend={() => {}} onPickAttachment={() => {}} modelChip={{ label: 'sonnet-4 · medium', onPress }} />);
    expect(screen.queryByLabelText(/Model and effort/)).toBeNull();
    fireEvent.click(screen.getByLabelText('Add'));
    fireEvent.click(screen.getByLabelText('Model and effort: sonnet-4 · medium'));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('closes the + menu on a tap outside it, and floats it in a modal layer above the stream', () => {
    render(<Composer onSend={() => {}} onPickAttachment={() => {}} modelChip={{ label: 'sonnet-4 · medium', onPress: () => {} }} />);
    fireEvent.click(screen.getByLabelText('Add'));
    expect(screen.getByLabelText('Model and effort: sonnet-4 · medium').closest('[data-modal]')).not.toBeNull();
    fireEvent.click(screen.getByTestId('composer-menu-backdrop'));
    expect(screen.queryByLabelText(/Model and effort/)).toBeNull();
    fireEvent.click(screen.getByLabelText('Add'));
    fireEvent.click(screen.getByLabelText('Add'));
    expect(screen.queryByLabelText(/Model and effort/)).toBeNull();
  });

  it('is absent without the admin gate', () => {
    render(<Composer onSend={() => {}} onPickAttachment={() => {}} />);
    expect(screen.queryByLabelText('Add')).toBeNull();
    expect(screen.queryByLabelText(/Model and effort/)).toBeNull();
  });
});

describe('composer anatomy', () => {
  const box = (label) => JSON.parse(screen.getByLabelText(label).getAttribute('data-style'));
  const pill = () => [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style'))).find((st) => st.minHeight === COMPOSER_H);

  it('is one 56 pt fill pill: +, a 16 pt input and a round send, at the sheet corner', () => {
    render(<Composer onSend={() => {}} onPickAttachment={() => {}} mentionSource={() => []} />);
    expect(COMPOSER_H).toBe(56);
    expect(pill()).toMatchObject({ minHeight: 56, borderRadius: radii.sheet, backgroundColor: palettes.light.fill });
    expect(pill().borderWidth).toBeUndefined();
    for (const label of ['Add', 'Send']) {
      expect(box(label)).toMatchObject({ width: COMPOSER_BTN, height: COMPOSER_BTN, borderRadius: radii.pill });
    }
    expect(Number(field().getAttribute('data-size'))).toBe(16);
  });

  it('attaches straight from + when attaching is the only extra', () => {
    const onPick = vi.fn();
    render(<Composer onSend={() => {}} onPickAttachment={onPick} />);
    fireEvent.click(screen.getByLabelText('Attach file'));
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it('keeps mention, attach and model behind + with every action intact', () => {
    const onPick = vi.fn();
    render(<Composer onSend={() => {}} onPickAttachment={onPick} mentionSource={() => []} modelChip={{ label: 'm', onPress: () => {} }} />);
    fireEvent.click(screen.getByLabelText('Add'));
    fireEvent.click(screen.getByLabelText('Mention a peer'));
    expect(field().value).toBe('@');
    fireEvent.click(screen.getByLabelText('Add'));
    fireEvent.click(screen.getByLabelText('Attach file'));
    expect(onPick).toHaveBeenCalledTimes(1);
  });

  it('gives each round control a 44 pt target', () => {
    render(<Composer onSend={() => {}} onPickAttachment={() => {}} mentionSource={() => []} />);
    for (const label of ['Add', 'Send']) {
      const slop = Number(JSON.parse(screen.getByLabelText(label).getAttribute('data-hitslop')));
      expect(box(label).height + slop * 2).toBeGreaterThanOrEqual(mobile.tap);
    }
  });
});

describe('composer states', () => {
  it('dims only the controls by the shared 0.45 when disabled and keeps the pill on the fill', () => {
    render(<Composer onSend={() => {}} disabled onPickAttachment={() => {}} mentionSource={() => []} />);
    const styles = [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style')));
    expect(styles.some((st) => st.opacity != null && st.opacity < 1)).toBe(false);
    for (const label of ['Add', 'Send']) {
      expect(JSON.parse(screen.getByLabelText(label).getAttribute('data-style')).opacity).toBe(0.45);
    }
    expect(styles.find((st) => st.minHeight === COMPOSER_H).backgroundColor).toBe(palettes.light.fill);
    expect(field().getAttribute('data-placeholder-color')).toBe(palettes.light.ink2);
  });

  it('shows no focus ring and no edge when the input takes focus: the caret is its focus', () => {
    render(<Composer onSend={() => {}} />);
    const pillStyle = () => [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style'))).find((st) => st.minHeight === COMPOSER_H);
    fireEvent.focus(field());
    expect(pillStyle().borderWidth).toBeUndefined();
    expect(pillStyle().outlineWidth).toBeUndefined();
  });

  it('fades the stream into the composer instead of a rule above it', () => {
    render(<Composer onSend={() => {}} />);
    const styles = [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style')));
    expect(styles.some((st) => st.borderTopWidth)).toBe(false);
    expect(document.querySelector('[data-fade="bottom"]')).toBeTruthy();
    expect(styles.some((st) => st.backgroundColor === palettes.light.bg)).toBe(true);
  });

  it('sends with alpi ink when the profile has no accent', () => {
    render(<Composer onSend={() => {}} />);
    fireEvent.change(field(), { target: { value: 'hi' } });
    expect(JSON.parse(screen.getByLabelText('Send').getAttribute('data-style')).backgroundColor).toBe(palettes.light.accent);
  });

  it('shows no Resume action under a disabled composer', () => {
    const { rerender } = render(<Composer onSend={() => {}} disabled />);
    expect(screen.queryByText('Resume profile')).toBeNull();
    expect(screen.queryByText('Resume')).toBeNull();
    rerender(<Composer onSend={() => {}} disabled offline />);
    expect(screen.queryByText('Resume profile')).toBeNull();
  });

  it('hands every match and the token to the popover, even when nothing matches', () => {
    render(<Composer onSend={() => {}} mentionSource={() => []} />);
    type('hello @zz');
    expect(document.querySelector('[data-mention]').getAttribute('data-mention')).toBe('zz');
    expect(document.querySelector('[data-mention]').getAttribute('data-count')).toBe('0');
  });

  it('rings the send button for a keyboard focus only', () => {
    render(<Composer onSend={() => {}} />);
    expect(JSON.parse(screen.getByLabelText('Send').getAttribute('data-style')).outlineWidth).toBeUndefined();
    fireEvent.focus(screen.getByLabelText('Send'));
    expect(JSON.parse(screen.getByLabelText('Send').getAttribute('data-style')).outlineWidth).toBe(2);
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

describe('keyboard that moved without animating', () => {
  it('sits on the home indicator again when the keyboard hides without an animation', () => {
    const bottomPad = () =>
      [...document.querySelectorAll('div[data-style]')].map((d) => JSON.parse(d.getAttribute('data-style'))).find((st) => st.paddingTop === COMPOSER_PAD_Y).paddingBottom;
    keyboard.keyboardHeight = 300;
    keyboard.keyboardState = 2;
    const { rerender } = render(<Composer onSend={() => {}} />);
    expect(bottomPad()).toBe(COMPOSER_PAD_Y);
    act(() => h.listeners.keyboardDidHide());
    rerender(<Composer onSend={() => {}} />);
    expect(bottomPad()).toBe(34);
    keyboard.keyboardState = 0;
  });
});

describe('initial text', () => {
  it('starts with the text a reply hands it', () => {
    render(<Composer onSend={() => {}} initialText={'> **Digest**\n\n'} />);
    expect(document.querySelector('textarea').value).toBe('> **Digest**\n\n');
  });
});

