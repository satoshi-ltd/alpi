import React from 'react';
import { afterEach, describe, it, expect, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';

afterEach(cleanup);

vi.mock('react-native', () => {
  const View = ({ children, ...props }) => React.createElement('div', props, children);
  const Text = ({ children, ...props }) => React.createElement('span', props, children);
  const Pressable = ({ children, onPress, ...props }) =>
    React.createElement('button', { type: 'button', onClick: onPress, ...props },
      children instanceof Function ? children({ pressed: false }) : children);
  return {
    View,
    Text,
    Pressable,
    ScrollView: View,
    TextInput: (props) => React.createElement('input', props),
    useColorScheme: () => 'light',
    Alert: { alert: vi.fn() },
  };
});
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, children }) => (open ? <section><h1>{title}</h1>{children}</section> : null),
}));
vi.mock('../../components/PickerRow', () => ({
  PickerRow: ({ label, helper, meta, onPress, selected }) => (
    <button type="button" data-selected={String(!!selected)} onClick={onPress}>
      <span>{label}</span>
      {helper ? <small>{helper}</small> : null}
      {meta}
    </button>
  ),
}));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => <em>{children}</em> }));
vi.mock('../../components/Row', () => ({ RowSeparator: () => <hr />, SectionHeader: ({ children }) => <h2>{children}</h2> }));
vi.mock('../../components/ConfirmProvider', () => ({ useConfirm: () => async () => false }));
vi.mock('../../components/Field', () => ({ Field: () => null }));
const toast = vi.hoisted(() => vi.fn());
vi.mock('../../components/Toast', () => ({ useToast: () => toast }));
vi.mock('../../components/ConfirmProvider', () => ({ useConfirm: () => async () => false }));
vi.mock('../../hooks/useDaemonData', () => ({ useOllamaModels: () => ({ data: null, loading: false }) }));
vi.mock('../../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn() }) }));
vi.mock('../../lib/curatedModels', () => ({ noteFor: () => null }));
vi.mock('../../lib/voices', () => ({ VOICE_SHORTLIST: [] }));
vi.mock('../../lib/voicePreview', () => ({
  currentlyPlayingVoice: () => null,
  playVoicePreview: vi.fn(),
  stopVoicePreview: vi.fn(),
  subscribeVoicePreview: () => () => {},
}));
vi.mock('../../lib/sheet-value', () => ({ nextSheetValue: ({ newInitial }) => newInitial }));
vi.mock('../../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink3: '#666', ink4: '#999', danger: '#c00' },
    fonts: { sans: { regular: 'x', semibold: 'x' }, mono: 'x', monoMedium: 'x' },
    fontSizes: { xs: 10, sm: 12, lg: 16 },
  }),
}));

import { ReasoningEffortSheet } from './ProfileFieldSheets.jsx';

describe('ReasoningEffortSheet', () => {
  it('applies the tapped effort and closes with no Save button', async () => {
    const onSave = vi.fn(async () => {});
    const onClose = vi.fn();
    render(<ReasoningEffortSheet open onClose={onClose} initialValue="medium" onSave={onSave} />);
    expect(screen.queryByText('Save')).toBeNull();
    fireEvent.click(screen.getByText('High'));
    await waitFor(() => expect(onClose).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith('high');
  });

  it('stays open and reports when the save fails', async () => {
    const onClose = vi.fn();
    toast.mockClear();
    render(<ReasoningEffortSheet open onClose={onClose} initialValue="" onSave={async () => { throw new Error('nope'); }} />);
    fireEvent.click(screen.getByText('Low'));
    await waitFor(() => expect(toast).toHaveBeenCalled());
    expect(onClose).not.toHaveBeenCalled();
  });

  it('puts the previous effort back when the save fails', async () => {
    toast.mockClear();
    render(<ReasoningEffortSheet open onClose={() => {}} initialValue="medium" onSave={async () => { throw new Error('nope'); }} />);
    fireEvent.click(screen.getByText('Low').closest('button'));
    await waitFor(() => expect(toast).toHaveBeenCalled());
    expect(screen.getByText('Medium').closest('button').getAttribute('data-selected')).toBe('true');
    expect(screen.getByText('Low').closest('button').getAttribute('data-selected')).toBe('false');
  });

  it('closes without saving when the current effort is tapped again', () => {
    const onSave = vi.fn();
    const onClose = vi.fn();
    render(<ReasoningEffortSheet open onClose={onClose} initialValue="medium" onSave={onSave} />);
    fireEvent.click(screen.getByText('Medium'));
    expect(onSave).not.toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('offers the model list as a row only when asked', () => {
    const onPress = vi.fn();
    const { rerender } = render(<ReasoningEffortSheet open onClose={() => {}} initialValue="" modelRow={{ label: 'opus-5', onPress }} />);
    fireEvent.click(screen.getByText('Change model…'));
    expect(onPress).toHaveBeenCalledTimes(1);
    rerender(<ReasoningEffortSheet open onClose={() => {}} initialValue="" />);
    expect(screen.queryByText('Change model…')).toBeNull();
  });
});
