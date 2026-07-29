import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, ...p }) => React.createElement('div', p, children);
  const Text = ({ children, ...p }) => React.createElement('span', p, children);
  const Pressable = ({ children, onPress, accessibilityLabel, accessibilityState, ...p }) =>
    React.createElement(
      'button',
      { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, 'aria-expanded': accessibilityState?.expanded, ...p },
      children,
    );
  const Animated = {
    View,
    Value: class { constructor(v) { this.v = v; } },
    timing: () => ({ start() {}, stop() {} }),
    loop: () => ({ start() {}, stop() {} }),
    sequence: () => ({ start() {}, stop() {} }),
  };
  return { View, Text, Pressable, Animated };
});

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', danger: '#f00' },
    fonts: { mono: 'm', monoMedium: 'mm' },
  }),
}));

vi.mock('../../components/Icon', () => ({
  Icon: ({ name }) => React.createElement('span', { 'data-icon': name }),
}));

import { ToolModule } from './ToolCallRow';

describe('ToolModule', () => {
  it('a single tool renders inline, no bucket', () => {
    render(<ToolModule tools={[{ name: 'read', args: { path: 'a' }, ok: true }]} accent="#0af" />);
    expect(screen.getByText('read')).toBeTruthy();
    expect(screen.queryByText(/tool calls?$/)).toBeNull();
  });

  it('finished tools collapse into the bucket and expand on tap', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: true, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('2 tool calls')).toBeTruthy();
    expect(screen.queryByText('aaa')).toBeNull();
    fireEvent.click(screen.getByText('2 tool calls').closest('button'));
    expect(screen.getByText('aaa')).toBeTruthy();
    expect(screen.getByText('bbb')).toBeTruthy();
  });

  it('a running tool stays out of the previous bucket', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: null, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('+1 previous tool call')).toBeTruthy();
    expect(screen.getByText('bbb')).toBeTruthy();
    expect(screen.queryByText('aaa')).toBeNull();
  });

  it('shows the failed count on the collapsed bucket', () => {
    render(<ToolModule tools={[
      { name: 'aaa', ok: true, tool_id: 't1' },
      { name: 'bbb', ok: false, tool_id: 't2' },
    ]} accent="#0af" />);
    expect(screen.getByText('1 failed')).toBeTruthy();
  });
});
