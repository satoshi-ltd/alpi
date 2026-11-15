import { buttonHeights, buttonLabelWeight, buttonPressed, buttonStates, buttonVariants } from '../../../common/button.mjs';
import { alpha } from '../../../common/tokens.mjs';
import { mixHex } from '../../../common/color.mjs';
import { buttonStateCases } from '../../../common/button.fixtures.mjs';
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({
  Pressable: ({ children, onPress, disabled, accessibilityLabel, accessibilityRole, accessibilityState, style, onFocus, onBlur }) =>
    <button onClick={onPress} onFocus={onFocus} onBlur={onBlur} disabled={disabled} aria-label={accessibilityLabel} role={accessibilityRole}
      data-style={JSON.stringify(Object.assign({}, ...style({ pressed: false })))} data-pressed-style={JSON.stringify(Object.assign({}, ...style({ pressed: true })))} aria-busy={accessibilityState?.busy} aria-disabled={accessibilityState?.disabled}>{children}</button>,
  Text: ({ children, style }) => <span data-label-style={JSON.stringify(Object.assign({}, ...style.filter(Boolean)))}>{children}</span>,
  View: ({ children }) => <div>{children}</div>,
  StyleSheet: { create: (styles) => styles, absoluteFillObject: { position: 'absolute', inset: 0 } },
}));
vi.mock('./Spinner', () => ({ Spinner: ({ color, size }) => <span data-testid="spinner" data-color={color} data-size={size ?? ''} /> }));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({
  colors: { accent: '#14110c', ink: '#111', ink2: '#333', ink4: '#aaa', bgPane: '#fff', field: '#eee', danger: '#c14545', dangerText: '#b73737', onDanger: '#ffffff', hover: '#ddd', selected: '#ccc', pressed: '#e0e0e0', fill: '#f2f2f2', line: '#ddd', line2: '#bbb' },
  fonts: { sans: { medium: 'medium', semibold: 'semibold' } }, fontSizes: { sm: 12, md: 14, lg: 15, xl: 18 },
}) }));
import { Button } from './Button';
import { radii, space } from '../theme/tokens';
afterEach(cleanup);

describe('Button accessibility', () => {
  it('keeps its accessible name and announces busy state during loading', () => {
    const onPress = vi.fn();
    const { rerender } = render(<Button title="Save" loading onPress={onPress} />);
    const button = screen.getByRole('button', { name: 'Save' });
    expect(button.getAttribute('aria-busy')).toBe('true');
    expect(button.disabled).toBe(true);
    fireEvent.click(button);
    expect(onPress).not.toHaveBeenCalled();
    rerender(<Button title="Save" onPress={onPress} />);
    expect(button.getAttribute('aria-busy')).toBe('false');
    fireEvent.click(button);
    expect(onPress).toHaveBeenCalledTimes(1);
  });
});


describe('Button shared contract', () => {
  it.each(buttonStateCases)('respects disabled=$disabled loading=$loading', ({ disabled, loading, blocked }) => {
    const press = vi.fn();
    render(<Button title="Continue" disabled={disabled} loading={loading} onPress={press} />);
    const button = screen.getByRole('button', { name: 'Continue' });
    expect(button.disabled).toBe(blocked);
    expect(button.getAttribute('aria-busy') === 'true').toBe(loading);
    fireEvent.click(button);
    expect(press).toHaveBeenCalledTimes(blocked ? 0 : 1);
  });

  it.each(buttonVariants)('supports the %s variant', (variant) => {
    render(<Button title="Continue" variant={variant} />);
    const button = screen.getByRole('button', { name: 'Continue' });
    const style = JSON.parse(button.dataset.style);
    const backgrounds = { primary: '#14110c', secondary: '#f2f2f2', ghost: 'transparent', danger: '#c14545', 'danger-ghost': 'transparent' };
    expect(style.backgroundColor).toBe(backgrounds[variant]);
  });

  it.each(Object.keys(buttonHeights))('uses the mobile touch height for %s', (size) => {
    render(<Button title="Continue" size={size} />);
    const style = JSON.parse(screen.getByRole('button').dataset.style);
    expect(style.minHeight).toBe(buttonHeights[size].mobile);
    expect(style.minHeight).toBeGreaterThanOrEqual(44);
  });

  it('pins the phone heights: sm at the 44 pt target, md and lg at the 48 pt control, hero 56', () => {
    expect(['sm', 'md', 'lg', 'hero'].map((size) => Button.touchHeight(size))).toEqual([44, 48, 48, 56]);
    expect(Button.touchHeight('bogus')).toBe(buttonHeights.lg.mobile);
  });

  it('keeps its label visible beside the spinner while loading, as on desktop', () => {
    const { rerender } = render(<Button title="Save connection" fullWidth />);
    const before = screen.getByRole('button').dataset.style;
    rerender(<Button title="Save connection" fullWidth loading />);
    expect(screen.getByRole('button').dataset.style).toBe(before);
    expect(JSON.parse(screen.getByText('Save connection').dataset.labelStyle).opacity).toBeUndefined();
    expect(screen.getByTestId('spinner')).toBeTruthy();
  });

  it.each(buttonVariants)('presses the %s variant one step along the state ladder', (variant) => {
    const palette = { accent: '#14110c', ink: '#111', danger: '#c14545', bgPane: '#fff', line: '#ddd', selected: '#ccc', hover: '#ddd', pressed: '#e0e0e0' };
    const recipe = buttonPressed[variant];
    const expected = recipe.token ? palette[recipe.token] : mixHex(palette[recipe.from], recipe.amount, recipe.toward === 'black' ? '#000000' : palette.bgPane);
    render(<Button title="Go" variant={variant} />);
    expect(JSON.parse(screen.getByRole('button').dataset.pressedStyle).backgroundColor).toBe(expected);
  });

  it.each([[false], [true]])('does not fade a loading button (disabled=%s), as desktop does', (disabled) => {
    render(<Button title="Go" loading disabled={disabled} />);
    expect(JSON.parse(screen.getByRole('button').dataset.style).opacity).toBeUndefined();
    expect(buttonStates.loadingFades).toBe(false);
  });

  it('fades a disabled button by the shared alpha and keeps its colours', () => {
    render(<Button title="Go" variant="primary" disabled />);
    const style = JSON.parse(screen.getByRole('button').dataset.style);
    expect(style.opacity).toBe(alpha.disabled);
    expect(style.backgroundColor).toBe('#14110c');
    expect(JSON.parse(screen.getByText('Go').dataset.labelStyle).color).toBe('#fff');
  });

  it.each(buttonVariants)('labels the %s variant with the shared weight', (variant) => {
    render(<Button title="Go" variant={variant} />);
    expect(JSON.parse(screen.getByText('Go').dataset.labelStyle).fontFamily).toBe(buttonLabelWeight[variant]);
  });

  it('waits with the shared ink arc in the label colour at its own size', () => {
    render(<Button title="Save" variant="primary" loading />);
    const arc = screen.getByTestId('spinner');
    expect(arc.dataset.color).toBe(JSON.parse(screen.getByText('Save').dataset.labelStyle).color);
    expect(arc.dataset.size).toBe('');
  });
});


it('separates destructive text from a filled destructive foreground', () => {
  const { rerender } = render(<Button title="Delete" variant="danger" />);
  const color = () => JSON.parse(screen.getByText('Delete').dataset.labelStyle).color;
  expect(color()).toBe('#ffffff');
  rerender(<Button title="Delete" variant="danger-ghost" />);
  expect(color()).toBe('#b73737');
});

it('uses dark text on a light custom accent', () => {
  render(<Button title="Save" accent="#f0b447" />);
  expect(JSON.parse(screen.getByText('Save').dataset.labelStyle).color).toBe('#000000');
});

describe('Button as a pill', () => {
  it.each(['sm', 'md', 'lg', 'hero'])('cuts the %s button as a pill, the shape of everything you press', (size) => {
    render(<Button title="Go" size={size} />);
    expect(JSON.parse(screen.getByRole('button').dataset.style).borderRadius).toBe(radii.pill);
  });

  it('fills the primary with alpi ink, presses it 78 % toward the pane, and presses secondary and ghost on the pressed state fill', () => {
    expect(buttonPressed).toMatchObject({ primary: { from: 'accent', amount: 0.78, toward: 'pane' }, secondary: { token: 'pressed' }, ghost: { token: 'pressed' } });
    const pressedOf = (variant) => {
      cleanup();
      render(<Button title="Go" variant={variant} />);
      return JSON.parse(screen.getByRole('button').dataset.pressedStyle).backgroundColor;
    };
    expect(pressedOf('primary')).toBe(mixHex('#14110c', 0.78, '#fff'));
    expect(pressedOf('secondary')).toBe('#e0e0e0');
    expect(pressedOf('ghost')).toBe('#e0e0e0');
  });

  it.each(buttonVariants.filter((v) => !v.includes('ghost')))('presses the %s button by a darker tone, never by fading', (variant) => {
    render(<Button title="Go" variant={variant} />);
    const button = screen.getByRole('button');
    const idle = JSON.parse(button.dataset.style);
    const pressed = JSON.parse(button.dataset.pressedStyle);
    expect(pressed.backgroundColor).not.toBe(idle.backgroundColor);
    expect(pressed.opacity).toBeUndefined();
  });

  it('darkens a pressed danger or custom-accent button instead of lightening it', () => {
    render(<Button title="Go" variant="danger" />);
    expect(JSON.parse(screen.getByRole('button').dataset.pressedStyle).backgroundColor).toBe(mixHex('#c14545', buttonPressed.danger.amount, '#000000'));
    cleanup();
    render(<Button title="Go" accent="#f0b447" />);
    expect(JSON.parse(screen.getByRole('button').dataset.pressedStyle).backgroundColor).toBe(mixHex('#f0b447', 0.82, '#000000'));
  });
});

describe('Button horizontal padding', () => {
  it.each([['sm', 16], ['md', 24], ['lg', 24], ['hero', 24]])('pads %s by the %i pt step of the one space grid', (size, padX) => {
    render(<Button title="Go" size={size} />);
    const style = JSON.parse(screen.getByRole('button', { name: 'Go' }).getAttribute('data-style'));
    expect(style.paddingHorizontal).toBe(padX);
    expect([4, 8, 12, 16, 24, 32, 48]).toContain(padX);
  });
});

describe('Button keyboard focus', () => {
  it('draws no ring at rest or under touch, and the 2 pt ring at 60 % ink 2 pt out on keyboard focus', () => {
    render(<Button title="Go" />);
    const button = screen.getByRole('button');
    expect(JSON.parse(button.dataset.style).outlineWidth).toBeUndefined();
    fireEvent.focus(button);
    const focused = JSON.parse(screen.getByRole('button').dataset.style);
    expect(focused).toMatchObject({ outlineStyle: 'solid', outlineWidth: 2, outlineOffset: 2, outlineColor: '#11199' });
    fireEvent.blur(screen.getByRole('button'));
    expect(JSON.parse(screen.getByRole('button').dataset.style).outlineWidth).toBeUndefined();
  });
});
