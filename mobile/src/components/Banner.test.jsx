import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(() => {
  cleanup();
  theme.mode = 'light';
});

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole }) =>
    React.createElement('div', { role: accessibilityRole, 'data-style': JSON.stringify(flat(style)) }, children);
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
vi.mock('./Dot', () => ({ Dot: ({ color }) => React.createElement('b', { 'data-dot': 'true', 'data-color': color }) }));

const style = (node) => JSON.parse(node.getAttribute('data-style'));
const KINDS = ['info', 'success', 'warning', 'danger'];
const hex = (rgb) => '#' + rgb.match(/\d+/g).map((v) => Number(v).toString(16).padStart(2, '0')).join('');

import { Banner } from './Banner';
import { BANNER_TINT, bannerTones } from './bannerTones';
import * as sharedTokens from '../../../common/tokens.mjs';
import { palettes } from '../theme/tokens';
import { mixHex } from '../../../common/color.mjs';
import { contrastRatio } from '../../../common/name.mjs';
import { DaemonBanner } from './DaemonBanner';

describe('Banner', () => {
  it('announces a danger banner as an alert and leaves the others quiet', () => {
    const { rerender } = render(<Banner kind="danger">down</Banner>);
    expect(screen.getByRole('alert')).toBeTruthy();
    rerender(<Banner kind="warning">paused</Banner>);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('leads warning and danger with the alert glyph in the kind text colour, info with the ink3 dot', () => {
    for (const kind of ['warning', 'danger']) {
      const { container, unmount } = render(<Banner kind={kind}>x</Banner>);
      expect(container.querySelector('[data-icon="triangle-alert"]').getAttribute('data-color')).toBe(palettes.light[`${kind}Text`]);
      expect(container.querySelector('[data-dot]')).toBeNull();
      unmount();
    }
    const { container } = render(<Banner kind="info">x</Banner>);
    expect(container.querySelector('[data-icon]')).toBeNull();
    expect(container.querySelector('[data-dot]').getAttribute('data-color')).toBe(palettes.light.ink3);
  });

  it('is one flat square surface: no border, outline, shadow or radius', () => {
    for (const kind of KINDS) {
      const { container, unmount } = render(<Banner kind={kind} action="Go">x</Banner>);
      const root = style(container.firstChild);
      for (const key of Object.keys(root)) expect(key).not.toMatch(/border|outline|shadow|elevation|radius/i);
      unmount();
    }
  });

  it('mixes the kind hue into the pane: 10 % / 14 % for status kinds, a 5 % / 6 % ink for info', () => {
    expect(BANNER_TINT).toEqual({ light: { tint: 0.1, quiet: 0.05 }, dark: { tint: 0.14, quiet: 0.06 } });
    expect(BANNER_TINT).toBe(sharedTokens.bannerTint);
    for (const mode of ['light', 'dark']) {
      theme.mode = mode;
      const p = palettes[mode];
      const { container, unmount } = render(<Banner kind="warning">x</Banner>);
      expect(style(container.firstChild).backgroundColor).toBe(mixHex(p.warning, mode === 'light' ? 0.1 : 0.14, p.bg));
      unmount();
      expect(bannerTones('danger', p, mode).surface).toBe(mixHex(p.danger, mode === 'light' ? 0.1 : 0.14, p.bg));
      expect(bannerTones('success', p, mode).surface).toBe(mixHex(p.success, mode === 'light' ? 0.1 : 0.14, p.bg));
      expect(bannerTones('info', p, mode).surface).toBe(mixHex(p.ink, mode === 'light' ? 0.05 : 0.06, p.bg));
    }
  });

  it('sets the action as text in the kind text colour', () => {
    for (const kind of KINDS) {
      const { unmount } = render(<Banner kind={kind} action="Resume">x</Banner>);
      const label = screen.getByText('Resume');
      expect(style(label).color).toBe(bannerTones(kind, palettes.light, 'light').text);
      expect(style(screen.getByLabelText('Resume')).backgroundColor).toBeUndefined();
      unmount();
    }
    expect(bannerTones('warning', palettes.light, 'light').text).toBe(palettes.light.warningText);
    expect(bannerTones('info', palettes.light, 'light').text).toBe(palettes.light.ink2);
  });

  it('keeps every text at 4.5:1 on its surface in light and dark', () => {
    for (const mode of ['light', 'dark']) {
      const p = palettes[mode];
      for (const kind of KINDS) {
        const { surface, text } = bannerTones(kind, p, mode);
        for (const ink of [p.ink, p.ink2, text]) {
          expect(contrastRatio(ink, hex(surface)), `${mode} ${kind} ${ink}`).toBeGreaterThanOrEqual(4.5);
        }
      }
    }
  });

  it('gives each action a 44 pt target', () => {
    const onAction = vi.fn();
    const onSecondary = vi.fn();
    render(<Banner kind="danger" action="Retry" onAction={onAction} secondaryAction="Manage" onSecondaryAction={onSecondary}>x</Banner>);
    for (const label of ['Retry', 'Manage']) {
      const target = style(screen.getByLabelText(label));
      expect(target.minHeight).toBeGreaterThanOrEqual(44);
      expect(target.minWidth).toBeGreaterThanOrEqual(44);
    }
    fireEvent.click(screen.getByLabelText('Retry'));
    fireEvent.click(screen.getByLabelText('Manage'));
    expect(onAction).toHaveBeenCalledTimes(1);
    expect(onSecondary).toHaveBeenCalledTimes(1);
  });
});

describe('DaemonBanner', () => {
  it('offers Retry and Manage when the daemon is unreachable', () => {
    const onRetry = vi.fn();
    const onManage = vi.fn();
    render(<DaemonBanner status="offline" onRetry={onRetry} onManage={onManage} />);
    fireEvent.click(screen.getByLabelText('Manage'));
    fireEvent.click(screen.getByLabelText('Retry'));
    expect(onManage).toHaveBeenCalledTimes(1);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('shows no Manage where the screen cannot open the connection', () => {
    render(<DaemonBanner status="offline" onRetry={() => {}} />);
    expect(screen.queryByLabelText('Manage')).toBeNull();
  });

  it('stays silent when online or unpaired', () => {
    const { container, rerender } = render(<DaemonBanner status="online" />);
    expect(container.firstChild).toBeNull();
    rerender(<DaemonBanner status="offline" paired={false} />);
    expect(container.firstChild).toBeNull();
  });
});
