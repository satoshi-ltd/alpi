import React from 'react';
import { vi } from 'vitest';

import { buttonHeights } from '../../../common/button.mjs';
import { fonts, lineHeights, mobile, palettes } from '../../src/theme/tokens';
import { scaleFontSizes } from '../../src/theme/textScale';

export const state = { width: 390, height: 844, scale: 1, mode: 'light', keyboard: {}, appState: [] };

export const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
const resolve = (style) => flat(typeof style === 'function' ? style({ pressed: false }) : style);
const dataOf = (p) => Object.fromEntries(Object.entries(p).filter(([k]) => k.startsWith('data-')));
const styled = (style) => JSON.stringify(resolve(style));

export const reset = () => {
  state.width = 390;
  state.height = 844;
  state.scale = 1;
  state.mode = 'light';
  state.keyboard = {};
  state.appState = [];
  Linking.openSettings.mockClear();
  Keyboard.dismiss.mockClear();
};

export const emit = (name) => (state.keyboard[name] ?? []).forEach((fn) => fn({ endCoordinates: { height: 336 } }));
export const flip = (next) => state.appState.forEach((fn) => fn(next));

export const View = ({ children, style, accessibilityRole, accessibilityLabel, testID, ...p }) =>
  React.createElement('div', { ...dataOf(p), 'data-style': styled(style), role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-testid': testID }, children);
export const Text = ({ children, style, accessibilityRole, ...p }) =>
  React.createElement('span', { 'data-style': styled(style), role: accessibilityRole }, children);
export const Pressable = ({ children, onPress, style, accessibilityRole, accessibilityLabel, disabled }) =>
  React.createElement('button', { type: 'button', onClick: onPress, disabled, role: accessibilityRole, 'aria-label': accessibilityLabel, 'data-style': styled(style) }, typeof children === 'function' ? children({ pressed: false }) : children);
export const ScrollView = ({ children, style, contentContainerStyle }) =>
  React.createElement('div', { 'data-scroll': '', 'data-style': styled(style), 'data-content': styled(contentContainerStyle) }, children);
export const TextInput = ({ value, onChangeText, editable = true, accessibilityLabel, placeholder, ref }) =>
  React.createElement('input', { ref, 'data-pair-input': '1', value: value ?? '', disabled: !editable, 'aria-label': accessibilityLabel, placeholder, onChange: (e) => onChangeText?.(e.target.value) });
export const Platform = { OS: 'ios', constants: { Model: 'iPhone' }, select: (sel) => sel?.ios ?? sel?.default };
export const StyleSheet = { create: (s) => s, absoluteFillObject: {} };
export const Linking = { openSettings: vi.fn(async () => {}), openURL: vi.fn(async () => true) };
export const Keyboard = {
  dismiss: vi.fn(),
  addListener: (name, fn) => {
    (state.keyboard[name] ??= []).push(fn);
    return { remove: () => { state.keyboard[name] = state.keyboard[name].filter((l) => l !== fn); } };
  },
};
export const AppState = {
  addEventListener: (_type, fn) => {
    state.appState.push(fn);
    return { remove: () => { state.appState = state.appState.filter((l) => l !== fn); } };
  },
  currentState: 'active',
};
export const useWindowDimensions = () => ({ width: state.width, height: state.height, fontScale: 1 });

export const ThemeContext = React.createContext(null);
export const useTheme = () => React.useContext(ThemeContext) ?? ({
  mode: state.mode,
  colors: palettes[state.mode],
  fonts,
  fontSizes: scaleFontSizes(state.scale),
  lineHeights,
  mobile,
  hydrated: true,
});

export const Button = ({ title, onPress, variant = 'primary', size = 'lg', fullWidth, loading, disabled }) =>
  React.createElement('button', {
    type: 'button',
    onClick: onPress,
    disabled: disabled || loading,
    'data-variant': variant,
    'data-size': size,
    'data-height': buttonHeights[size].mobile,
    'data-full': String(!!fullWidth),
    'data-loading': String(!!loading),
    'data-dark': String(useTheme().mode === 'dark'),
  }, title);
export const Fold = ({ size }) => React.createElement('span', { 'data-fold': 'alpaca', 'data-size': size });
export const Busy = ({ size, visible, style }) =>
  visible === false ? null : React.createElement('span', { role: 'progressbar', 'data-busy': '', 'data-size': size, 'data-style': styled(style) });
export const Icon = ({ name }) => React.createElement('i', { 'data-icon': name });
export const Toggle = ({ on, onChange, label }) =>
  React.createElement('input', { type: 'checkbox', role: 'switch', 'aria-label': label, checked: !!on, onChange: (e) => onChange?.(e.target.checked) });
export const KeyboardPane = ({ children }) => React.createElement('div', { 'data-keyboard-pane': '' }, children);
