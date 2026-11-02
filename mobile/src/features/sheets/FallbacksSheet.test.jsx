import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, style, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, style, ...props }) => React.createElement('span', props, children);
  const Pressable = ({ children, onPress, style, accessibilityLabel, accessibilityState, accessibilityRole, disabled, ...props }) =>
    React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel, disabled, ...props },
      children instanceof Function ? children({ pressed: false }) : children);
  return { View, Text, Pressable };
});
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, subtitle, primaryAction, children }) => (open ? (
    <section>
      <h1>{title}</h1>
      <p>{subtitle}</p>
      {children}
      <button type="button" onClick={primaryAction.onPress}>{primaryAction.label}</button>
    </section>
  ) : null),
}));
vi.mock('../../components/PickerRow', () => ({
  PickerRow: ({ label, helper, onPress }) => (
    <button type="button" onClick={onPress}><span>{label}</span><small>{helper}</small></button>
  ),
}));
vi.mock('../../components/Row', () => ({ RowSeparator: () => <hr /> }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('../../components/Toast', () => ({ useToast: () => toast }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', selected: '#eee' },
    fonts: { sans: { regular: 'x', medium: 'x' }, mono: 'x' },
    fontSizes: { xs: 10, sm: 12, md: 14 },
  }),
}));

import { FallbacksSheet } from './FallbacksSheet';

const LIST = ['anthropic/sonnet', 'openai/gpt-x'];

beforeEach(() => toast.mockReset());

function renderSheet(props = {}) {
  const onSave = vi.fn(async () => {});
  const onAdd = vi.fn();
  const onClose = vi.fn();
  render(<FallbacksSheet open profileName="doc" list={LIST} onSave={onSave} onAdd={onAdd} onClose={onClose} {...props} />);
  return { onSave, onAdd, onClose };
}

describe('FallbacksSheet', () => {
  it('lists the fallbacks in order and says when they are used', () => {
    renderSheet();
    expect(screen.getByText('1 · sonnet')).toBeTruthy();
    expect(screen.getByText('2 · gpt-x')).toBeTruthy();
    expect(screen.getByText("@doc · tried in order when the main model's provider fails")).toBeTruthy();
  });

  it('moves and removes entries, never past either end', async () => {
    const { onSave } = renderSheet();
    expect(screen.getByLabelText('Move sonnet up').disabled).toBe(true);
    expect(screen.getByLabelText('Move gpt-x down').disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('Move sonnet down'));
    await waitFor(() => expect(onSave).toHaveBeenCalledWith(['openai/gpt-x', 'anthropic/sonnet']));
    fireEvent.click(screen.getByLabelText('Remove gpt-x'));
    await waitFor(() => expect(onSave).toHaveBeenLastCalledWith(['anthropic/sonnet']));
  });

  it('opens the model picker from Add and closes on Done', () => {
    const { onAdd, onClose } = renderSheet({ list: [] });
    expect(screen.getByText('No fallbacks: a provider outage stops the agent.')).toBeTruthy();
    fireEvent.click(screen.getByText('Add model…'));
    expect(onAdd).toHaveBeenCalled();
    fireEvent.click(screen.getByText('Done'));
    expect(onClose).toHaveBeenCalled();
  });

  it('stops offering Add at the cap and when nothing is left to add', () => {
    const full = Array.from({ length: 16 }, (_, i) => `p/m${i}`);
    renderSheet({ list: full });
    expect(screen.queryByText('Add model…')).toBeNull();
    expect(screen.getByText('16 is the most a profile can list.')).toBeTruthy();
    cleanup();
    renderSheet({ canAdd: false });
    expect(screen.queryByText('Add model…')).toBeNull();
  });

  it('toasts a refused save', async () => {
    const onSave = vi.fn(async () => { throw new Error('too many fallback models'); });
    renderSheet({ onSave });
    fireEvent.click(screen.getByLabelText('Remove sonnet'));
    await waitFor(() => expect(toast).toHaveBeenCalledWith({ title: 'Save failed', message: 'Error: too many fallback models' }));
  });
});
