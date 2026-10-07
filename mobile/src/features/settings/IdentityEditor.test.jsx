import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ toast: vi.fn() }));

vi.mock('react-native', () => ({
  View: ({ children, style, ...p }) => React.createElement('div', p, children),
  Text: ({ children, style, ...p }) => React.createElement('span', p, children),
  TextInput: ({ value, onChangeText, placeholder, style, editable, ...p }) =>
    React.createElement('textarea', { value, placeholder, readOnly: editable === false, onChange: (e) => onChangeText?.(e.target.value) }),
  Pressable: ({ children, onPress, style, disabled, accessibilityLabel, ...p }) =>
    React.createElement('button', { type: 'button', onClick: onPress, disabled, 'aria-label': accessibilityLabel }, children),
  StyleSheet: { create: (s) => s, absoluteFillObject: {} },
}));

vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { bg: '#fff', bgPane: '#fff', bgInput: '#f1f3f5', line: '#eee', line2: '#ddd', hover: '#f4f4f4', selected: '#eee', ink: '#000', ink2: '#333', ink3: '#666', ink4: '#999', accent: '#c90', warning: '#e08a3c', warningText: '#8a5a0a', success: '#3fb37a', successText: '#217a45', danger: '#c14545', dangerText: '#b73737', onDanger: '#fff' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono', monoMedium: 'monoMedium' },
    fontSizes: { xs: 11, sm: 12, md: 14, lg: 15, xl: 18 },
    mobile: { tap: 44, inputH: 44, btnH: 48 },
  }),
}));

vi.mock('../../components/Spinner', () => ({ Spinner: () => null }));
vi.mock('../../components/Toast', () => ({ useToast: () => h.toast }));

import { IdentityEditor } from './IdentityEditor';

const profile = { name: 'doc', bio: 'Personal doctor', model: 'openrouter/example' };

beforeEach(() => {
  h.toast.mockClear();
});

describe('IdentityEditor', () => {
  it('shows the bio, saves an edit as public_bio and reports it', async () => {
    const call = vi.fn(async () => ({}));
    const onSaved = vi.fn(async () => {});
    render(<IdentityEditor profileId="doc" profile={profile} call={call} onSaved={onSaved} />);
    expect(screen.queryByText('Save')).toBeNull();
    fireEvent.change(screen.getByPlaceholderText('public identity — visible to peers'), { target: { value: 'Village doctor' } });
    expect(screen.getByText('draft')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('Save'));
    await waitFor(() => expect(call).toHaveBeenCalledWith('host.config.set_field', { profile: 'doc', key: 'public_bio', value: 'Village doctor' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Identity saved' }));
  });

  it('discards an edit back to the saved bio', () => {
    render(<IdentityEditor profileId="doc" profile={profile} call={vi.fn()} />);
    const box = screen.getByPlaceholderText('public identity — visible to peers');
    fireEvent.change(box, { target: { value: 'typo' } });
    fireEvent.click(screen.getByLabelText('Discard'));
    expect(box.value).toBe('Personal doctor');
    expect(screen.queryByText('draft')).toBeNull();
  });

  it('drafts from AGENT.md into the box without saving', async () => {
    const call = vi.fn(async (method) => (method === 'host.identity.draft' ? { bio: 'Lab-savvy doctor' } : {}));
    render(<IdentityEditor profileId="doc" profile={profile} call={call} />);
    fireEvent.click(screen.getByLabelText('Draft'));
    await waitFor(() => expect(screen.getByPlaceholderText('public identity — visible to peers').value).toBe('Lab-savvy doctor'));
    expect(call).toHaveBeenCalledWith('host.identity.draft', { profile: 'doc' });
    expect(call).not.toHaveBeenCalledWith('host.config.set_field', expect.anything());
    expect(screen.getByText('draft')).toBeTruthy();
  });

  it('refuses to draft without a model instead of letting the daemon fail', () => {
    const call = vi.fn();
    render(<IdentityEditor profileId="doc" profile={{ ...profile, model: '' }} call={call} />);
    fireEvent.click(screen.getByLabelText('Draft'));
    expect(call).not.toHaveBeenCalled();
    expect(h.toast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Set a model first' }));
  });
});
