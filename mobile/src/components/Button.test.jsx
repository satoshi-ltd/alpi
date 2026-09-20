import { buttonHeights, buttonVariants } from '../../../common/button.mjs';
import { buttonStateCases } from '../../../common/button.fixtures.mjs';
import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

vi.mock('react-native', () => ({
  Pressable: ({ children, onPress, disabled, accessibilityLabel, accessibilityRole, accessibilityState, style }) =>
    <button onClick={onPress} disabled={disabled} aria-label={accessibilityLabel} role={accessibilityRole}
      data-style={JSON.stringify(Object.assign({}, ...style({ pressed: false })))} aria-busy={accessibilityState?.busy} aria-disabled={accessibilityState?.disabled}>{children}</button>,
  Text: ({ children, style }) => <span data-label-style={JSON.stringify(Object.assign({}, ...style.filter(Boolean)))}>{children}</span>,
  View: ({ children }) => <div>{children}</div>,
  StyleSheet: { create: (styles) => styles, absoluteFillObject: { position: 'absolute', inset: 0 } },
  ActivityIndicator: () => <span data-testid="spinner" />,
}));
vi.mock('../theme/ThemeContext', () => ({ useTheme: () => ({
  colors: { ink: '#111', ink2: '#333', ink4: '#aaa', bgPane: '#fff', bgInput: '#eee', danger: '#c14545', dangerText: '#b73737', onDanger: '#ffffff', hover: '#ddd' },
  fonts: { sans: { medium: 'medium', semibold: 'semibold' } }, fontSizes: { sm: 12, md: 14, lg: 15, xl: 18 },
}) }));
import { Button } from './Button';
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
    const backgrounds = { primary: '#111', secondary: '#ddd', ghost: 'transparent', danger: '#c14545', 'danger-ghost': 'transparent' };
    expect(style.backgroundColor).toBe(backgrounds[variant]);
  });

  it.each(Object.keys(buttonHeights))('uses the mobile touch height for %s', (size) => {
    render(<Button title="Continue" size={size} />);
    const style = JSON.parse(screen.getByRole('button').dataset.style);
    expect(style.minHeight).toBe(buttonHeights[size].mobile);
    expect(style.minHeight).toBeGreaterThanOrEqual(40);
  });

  it('retains label layout while loading so the button does not shrink', () => {
    const { rerender } = render(<Button title="Save connection" fullWidth />);
    const before = screen.getByRole('button').dataset.style;
    rerender(<Button title="Save connection" fullWidth loading />);
    expect(screen.getByRole('button').dataset.style).toBe(before);
    expect(JSON.parse(screen.getByText('Save connection').dataset.labelStyle).opacity).toBe(0);
    expect(screen.getByTestId('spinner')).toBeTruthy();
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
