import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children, style, accessibilityRole }) =>
    React.createElement('div', { role: accessibilityRole, 'data-style': JSON.stringify(flat(style)) }, children);
  const Text = ({ children, style }) => React.createElement('span', { 'data-style': JSON.stringify(flat(style)) }, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-style': JSON.stringify(flat(style)) }, children);
  return { View, Text, Pressable, StyleSheet: { hairlineWidth: 0.5 } };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { danger: '#f00', dangerText: '#a00', warning: '#fa0', warningText: '#a60', ink3: '#666', ink2: '#333', ink: '#000', success: '#0a0', successText: '#060' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' } },
    fontSizes: { sm: 12, md: 14 },
  }),
}));
vi.mock('./Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('./Dot', () => ({ Dot: () => React.createElement('b', { 'data-dot': 'true' }) }));

const style = (node) => JSON.parse(node.getAttribute('data-style'));

import { Banner } from './Banner';
import { DaemonBanner } from './DaemonBanner';

describe('Banner', () => {
  it('announces a danger banner as an alert and leaves the others quiet', () => {
    const { rerender } = render(<Banner kind="danger">down</Banner>);
    expect(screen.getByRole('alert')).toBeTruthy();
    rerender(<Banner kind="warning">paused</Banner>);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('wears the shared triangle for danger and warning and a dot otherwise', () => {
    const { container, rerender } = render(<Banner kind="warning">x</Banner>);
    expect(container.querySelector('[data-icon="triangle-alert"]')).not.toBeNull();
    rerender(<Banner kind="info">x</Banner>);
    expect(container.querySelector('[data-icon]')).toBeNull();
    expect(container.querySelector('[data-dot]')).not.toBeNull();
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
