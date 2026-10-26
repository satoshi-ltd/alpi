import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ answer: false, confirm: null, save: null, reload: null, toast: null }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', null, children);
  const Text = ({ children }) => React.createElement('span', null, children);
  const Pressable = ({ children, onPress, accessibilityLabel }) => React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, children);
  const TextInput = () => React.createElement('textarea');
  return { View, Text, Pressable, ScrollView: View, TextInput, StyleSheet: { create: (x) => x } };
});
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', null, children) }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({ colors: { bg: '#fff', ink: '#000', ink2: '#333', ink3: '#666', dangerText: '#b00' }, fonts: { sans: { regular: 'r', semibold: 's' }, mono: 'm' }, fontSizes: { xs: 11, sm: 12, md: 14, xl: 18 } }),
}));
vi.mock('../../components/AlertBanner', () => ({ AlertBanner: () => null }));
vi.mock('../../hooks/useAttention', () => ({ useAttention: () => ({ att: {} }) }));
vi.mock('../../components/Icon', () => ({ Icon: () => null }));
vi.mock('../../components/KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('div', null, children) }));
vi.mock('../../components/RichText', () => ({ RichText: ({ children }) => React.createElement('span', null, children) }));
vi.mock('../../components/ReaderSkeleton', () => ({ ReaderSkeleton: () => null }));
vi.mock('../profile/PanelHeader', () => ({ PanelHeader: ({ right }) => React.createElement('div', null, right) }));
vi.mock('../../hooks/useDirtyBack', () => ({ useDirtyBack: () => () => {} }));
vi.mock('../../components/Toast', () => ({ useToast: () => (h.toast ??= vi.fn()) }));
vi.mock('../../components/ConfirmProvider', () => ({ useConfirm: () => (h.confirm ??= vi.fn(async () => h.answer)) }));
vi.mock('../../hooks/useMemoryEditor', () => ({
  useMemoryEditor: () => ({
    editing: true, loading: false, loadError: null, dirty: true, draft: 'x', raw: 'x', canEdit: true,
    setDraft: () => {}, startEdit: () => {}, cancel: () => {},
    save: (opts) => h.save(opts), reload: () => h.reload(),
  }),
}));

import { MemoryDetail } from './MemoryDetail';

function press() {
  h.save = vi.fn(async (opts) => (opts?.force ? { ok: true } : { ok: false, conflict: true }));
  h.reload = vi.fn();
  h.confirm = vi.fn(async () => h.answer);
  const onSaved = vi.fn();
  render(<MemoryDetail profile="doc" name="MEMORY.md" onSaved={onSaved} />);
  fireEvent.click(screen.getByLabelText('Save'));
  return onSaved;
}

describe('memory save conflict', () => {
  it('offers overwrite, reload and keep editing', async () => {
    h.answer = false;
    press();
    await waitFor(() => expect(h.confirm).toHaveBeenCalled());
    const opts = h.confirm.mock.calls[0][0];
    expect([opts.confirmLabel, opts.alternateLabel, opts.cancelLabel]).toEqual(['Overwrite', 'Reload (discard)', 'Keep editing']);
  });

  it('reloads the file and discards the edits on the alternate answer', async () => {
    h.answer = 'alternate';
    const onSaved = press();
    await waitFor(() => expect(h.reload).toHaveBeenCalledTimes(1));
    expect(h.save).toHaveBeenCalledTimes(1);
    expect(onSaved).not.toHaveBeenCalled();
  });

  it('overwrites on the primary answer', async () => {
    h.answer = true;
    const onSaved = press();
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    expect(h.save).toHaveBeenLastCalledWith({ force: true });
    expect(h.reload).not.toHaveBeenCalled();
  });

  it('keeps editing and changes nothing when cancelled', async () => {
    h.answer = false;
    const onSaved = press();
    await waitFor(() => expect(h.confirm).toHaveBeenCalled());
    await Promise.resolve();
    expect(h.save).toHaveBeenCalledTimes(1);
    expect(h.reload).not.toHaveBeenCalled();
    expect(onSaved).not.toHaveBeenCalled();
  });
});
