import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  theme.mode = 'light';
});

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole, ...p }) =>
    React.createElement('div', { ...p, role: accessibilityRole, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  return { View, Text, Pressable, StyleSheet: { hairlineWidth: 0.5 } };
});
const theme = vi.hoisted(() => ({ mode: 'light' }));
vi.mock('../theme/ThemeContext', async () => {
  const { palettes } = await vi.importActual('../theme/tokens');
  return {
    useTheme: () => ({
      mode: theme.mode,
      colors: palettes[theme.mode],
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' } },
      fontSizes: { sm: 12, md: 14 },
    }),
  };
});
vi.mock('./Icon', () => ({ Icon: ({ name, color }) => React.createElement('i', { 'data-icon': name, 'data-color': color }) }));

import { AlertBanner } from './AlertBanner';
import { palettes } from '../theme/tokens';
import { mixHex } from '../../../common/color.mjs';
import { contrastRatio } from '../../../common/name.mjs';

const style = (node) => JSON.parse(node.getAttribute('data-style'));
const hex = (rgb) => '#' + rgb.match(/\d+/g).map((v) => Number(v).toString(16).padStart(2, '0')).join('');

describe('AlertBanner', () => {
  it('draws one flat square danger tint with no border, outline, shadow or radius, no side stripe', () => {
    for (const mode of ['light', 'dark']) {
      theme.mode = mode;
      const p = palettes[mode];
      const { container, unmount } = render(<AlertBanner lead="Does not pass lint" detail="line 4" />);
      const root = style(screen.getByRole('alert'));
      expect(root.backgroundColor).toBe(mixHex(p.danger, mode === 'light' ? 0.1 : 0.14, p.bg));
      for (const key of Object.keys(root)) expect(key).not.toMatch(/border|outline|shadow|elevation|radius/i);
      expect([...container.querySelectorAll('div')].some((n) => style(n).width === 2)).toBe(false);
      unmount();
    }
  });

  it('leads with the alert glyph in dangerText, a bold ink lead and an ink2 detail', () => {
    const { container } = render(<AlertBanner lead="Does not pass lint" detail="line 4" />);
    expect(container.querySelector('[data-icon="triangle-alert"]').getAttribute('data-color')).toBe(palettes.light.dangerText);
    expect(style(screen.getByText('Does not pass lint')).fontFamily).toBe('s');
    expect(style(screen.getByText('Does not pass lint')).color).toBe(palettes.light.ink);
    expect(style(screen.getByText('line 4')).color).toBe(palettes.light.ink2);
    expect(screen.queryByRole('button')).toBeNull();
  });

  it('keeps the lead, detail and action at 4.5:1 on the tint in light and dark', () => {
    for (const mode of ['light', 'dark']) {
      const p = palettes[mode];
      const surface = hex(mixHex(p.danger, mode === 'light' ? 0.1 : 0.14, p.bg));
      for (const ink of [p.ink, p.ink2, p.dangerText]) {
        expect(contrastRatio(ink, surface), `${mode} ${ink}`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });

  it('offers an action as a 44 pt target', () => {
    const onAction = vi.fn();
    render(<AlertBanner lead="x" action="Open" onAction={onAction} />);
    const btn = screen.getByRole('button', { name: 'Open' });
    expect(style(btn).minHeight).toBeGreaterThanOrEqual(44);
    expect(style(btn).minWidth).toBeGreaterThanOrEqual(44);
    expect(style(screen.getByText('Open')).color).toBe(palettes.light.dangerText);
    fireEvent.click(btn);
    expect(onAction).toHaveBeenCalled();
  });
});
