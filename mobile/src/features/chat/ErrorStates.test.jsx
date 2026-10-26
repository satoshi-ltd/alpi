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
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { danger: '#f00', dangerText: '#a00', warning: '#fa0', warningText: '#a60', ink3: '#666', ink2: '#333', ink: '#000', success: '#0a0', successText: '#060', line: '#ddd', hover: '#eee' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' } },
    fontSizes: { sm: 12, md: 14 },
    mobile: { tap: 44 },
  }),
}));
vi.mock('../../components/Icon', () => ({ Icon: ({ name }) => React.createElement('i', { 'data-icon': name }) }));
vi.mock('../../components/Dot', () => ({ Dot: () => React.createElement('b', { 'data-dot': 'true' }) }));

const style = (node) => JSON.parse(node.getAttribute('data-style'));

import { FailedSend, FailedToolCall, FailedVoice, TimeoutBanner } from './ErrorStates';

describe('inline failures share one row', () => {
  const cases = [
    ['FailedSend', () => <FailedSend onRetry={() => {}} />, /send/i],
    ['TimeoutBanner', () => <TimeoutBanner profileId="doc" onRetry={() => {}} />, /@doc/],
    ['FailedVoice', () => <FailedVoice duration={4} onRetry={() => {}} />, /voice/i],
  ];

  it.each(cases)('%s is the triangle, one sentence and a 44 pt Retry', (_name, make, sentence) => {
    const { container } = render(make());
    expect(container.querySelector('[data-icon="triangle-alert"]')).not.toBeNull();
    expect(container.textContent).toMatch(sentence);
    const retry = screen.getByLabelText('Retry');
    expect(style(retry).minHeight).toBeGreaterThanOrEqual(44);
  });

  it('retries on tap', () => {
    const onRetry = vi.fn();
    render(<FailedSend onRetry={onRetry} />);
    fireEvent.click(screen.getByLabelText('Retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('a failed tool call has the same row without a Retry', () => {
    const { container } = render(<FailedToolCall name="fetch" reason="timed out" />);
    expect(container.querySelector('[data-icon="triangle-alert"]')).not.toBeNull();
    expect(container.textContent).toContain('fetch · timed out');
    expect(screen.queryByLabelText('Retry')).toBeNull();
  });
});
