import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const flat = (style) => Object.assign({}, ...[style].flat(Infinity).filter(Boolean));
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel, style, hitSlop }) => {
    const resolved = flat(typeof style === 'function' ? style({ pressed: false }) : style);
    return React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'data-minheight': String(resolved.minHeight ?? 0), 'data-minwidth': String(resolved.minWidth ?? 0), 'data-slop': String(typeof hitSlop === 'number' ? hitSlop : 0) },
      typeof children === 'function' ? children({ pressed: false }) : children,
    );
  };
  return { View, Text, Pressable };
});
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Banner', () => ({ Banner: () => null }));
vi.mock('../src/components/Button', () => ({ Button: () => null }));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return {
    useTheme: () => ({
      colors: { ink: '#000', ink2: '#333', ink3: '#666', danger: '#f00', dangerText: '#a00', line2: '#ddd', selected: '#eee', bgPane: '#fff' },
      fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'm', monoMedium: 'mm' },
      fontSizes: tokens.fontSizes,
      mobile: tokens.mobile,
    }),
  };
});

import { LoadFailed } from '../src/components/LoadFailed';
import { FailedSend, FailedVoice } from '../src/features/chat/ErrorStates';
import { PendingPeerActions } from '../src/features/peers/PendingPeerActions';
import { mobile } from '../src/theme/tokens';

function reach(button) {
  const slop = Number(button.getAttribute('data-slop'));
  return {
    height: Number(button.getAttribute('data-minheight')) + 2 * slop,
    width: Number(button.getAttribute('data-minwidth')) + 2 * slop,
  };
}

describe('retry and pending-peer controls', () => {
  it('gives the send Retry the touch floor in both directions', () => {
    render(<FailedSend onRetry={() => {}} />);
    const { height, width } = reach(screen.getByRole('button'));
    expect(height).toBeGreaterThanOrEqual(mobile.tap);
    expect(width).toBeGreaterThanOrEqual(mobile.tap);
  });

  it('gives the voice Retry the touch floor without growing its pill', () => {
    render(<FailedVoice duration={4} onRetry={() => {}} />);
    const { height, width } = reach(screen.getByRole('button'));
    expect(height).toBeGreaterThanOrEqual(mobile.tap);
    expect(width).toBeGreaterThanOrEqual(mobile.tap);
  });

  it('gives the inline Retry of a failed load the touch floor', () => {
    render(<LoadFailed inline label="the schedule" error="daemon unreachable" onRetry={() => {}} />);
    const { height, width } = reach(screen.getByLabelText('Retry'));
    expect(height).toBeGreaterThanOrEqual(mobile.tap);
    expect(width).toBeGreaterThanOrEqual(mobile.tap);
  });

  it('gives Accept and Discard of a pending peer the touch floor and keeps their calls', () => {
    const onDiscard = vi.fn();
    const onAccept = vi.fn();
    render(<PendingPeerActions onDiscard={onDiscard} onAccept={onAccept} />);
    for (const name of ['Accept', 'Discard']) {
      const { height, width } = reach(screen.getByLabelText(name));
      expect(height).toBeGreaterThanOrEqual(mobile.tap);
      expect(width).toBeGreaterThanOrEqual(mobile.tap);
    }
    screen.getByLabelText('Accept').click();
    screen.getByLabelText('Discard').click();
    expect(onAccept).toHaveBeenCalledTimes(1);
    expect(onDiscard).toHaveBeenCalledTimes(1);
  });
});
