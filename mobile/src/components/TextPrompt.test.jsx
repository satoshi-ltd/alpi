import React from 'react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

vi.mock('react-native', () => {
  const R = require('react');
  const host = (tag) => ({ children, onPress, onChangeText, onSubmitEditing, value, ...rest }) =>
    R.createElement(tag, {
      ...rest,
      value,
      onClick: onPress ? (e) => { e.stopPropagation(); onPress(e); } : undefined,
      onChange: onChangeText ? (e) => onChangeText(e.target.value) : undefined,
      onKeyDown: onSubmitEditing ? (e) => { if (e.key === 'Enter') onSubmitEditing(); } : undefined,
    }, children);
  return {
    Modal: ({ visible, children }) => (visible ? R.createElement('div', { 'data-modal': 'true' }, children) : null),
    Pressable: host('div'),
    Text: host('span'),
    TextInput: host('input'),
    View: host('div'),
  };
});
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bgPane: '#fff', ink: '#000', ink3: '#333', ink4: '#444', bgInput: '#eee', line2: '#ddd' },
    fonts: { mono: 'mono', sans: { semibold: 'sans-semibold' } },
    fontSizes: { xs: 11, md: 15, lg: 18 },
  }),
}));
vi.mock('../theme/tokens', () => ({
  radii: { sheet: 16, xl: 12 },
  space: { s1: 4, s3: 8, s5: 12, s7: 16, s9: 24 },
  tracking: { snug: -0.005 },
  typography: { dialogTitle: { size: 'lg' } },
}));
vi.mock('./Button', () => ({
  Button: ({ title, onPress, disabled }) =>
    React.createElement('button', { onClick: disabled ? undefined : onPress, disabled }, title),
}));

import { TextPrompt } from './TextPrompt';

afterEach(cleanup);

describe('TextPrompt', () => {
  it('submits the trimmed value and stays disabled while the name is empty or unchanged', () => {
    const onSubmit = vi.fn();
    render(<TextPrompt open title="Rename" initialValue="casa" onSubmit={onSubmit} onClose={() => {}} />);
    const save = screen.getByText('Save');
    expect(save.disabled).toBe(true);
    const input = screen.getByDisplayValue('casa');
    fireEvent.change(input, { target: { value: '   ' } });
    expect(screen.getByText('Save').disabled).toBe(true);
    fireEvent.change(input, { target: { value: '  macbook-pro  ' } });
    expect(screen.getByText('Save').disabled).toBe(false);
    fireEvent.click(screen.getByText('Save'));
    expect(onSubmit).toHaveBeenCalledWith('macbook-pro');
  });

  it('renders nothing while closed and cancels through onClose', () => {
    const onClose = vi.fn();
    const { rerender } = render(<TextPrompt open={false} title="Rename" initialValue="casa" onClose={onClose} />);
    expect(screen.queryByText('Rename')).toBeNull();
    rerender(<TextPrompt open title="Rename" initialValue="casa" onClose={onClose} />);
    fireEvent.click(screen.getByText('Cancel'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});
