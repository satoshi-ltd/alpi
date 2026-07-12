import React from 'react';
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

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
    ActivityIndicator: () => React.createElement('span', { 'data-testid': 'spinner' }),
    TextInput: (props) => React.createElement('input', props),
    useColorScheme: () => 'light',
    Alert: { alert: vi.fn() },
  };
});
vi.mock('../../components/Sheet', () => ({
  Sheet: ({ open, title, children }) => (open ? <section><h1>{title}</h1>{children}</section> : null),
}));
vi.mock('../../components/PickerRow', () => ({
  PickerRow: ({ label, helper, meta, onPress }) => (
    <button type="button" onClick={onPress}>
      <span>{label}</span>
      {helper ? <small>{helper}</small> : null}
      {meta}
    </button>
  ),
}));
vi.mock('../../components/Pill', () => ({ Pill: ({ children }) => <em>{children}</em> }));
vi.mock('../../components/Row', () => ({ RowSeparator: () => <hr />, SectionHeader: ({ children }) => <h2>{children}</h2> }));
vi.mock('../../components/Field', () => ({ Field: () => null }));
vi.mock('../../components/Toast', () => ({ useToast: () => () => {} }));
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

import { CleanupSheet } from './ProfileFieldSheets.jsx';

const PLAN = [
  { key: 'tts', label: 'TTS cache', desc: 'mp3s', size: 2_000_000, count: 3, action: 'unlink', destructive: false },
  { key: 'sessions', label: 'Old sessions', desc: 'transcripts older than 30 days', size: 512, count: 2, action: 'unlink', destructive: true },
  { key: 'logs', label: 'Subsystem logs', desc: 'logs', size: 0, count: 0, action: 'unlink', destructive: false },
];

describe('CleanupSheet', () => {
  it('fetches the plan, lists reclaimable categories, applies on tap', async () => {
    const call = vi.fn(async (verb) => {
      if (verb === 'host.cleanup.plan') return { categories: PLAN };
      if (verb === 'host.cleanup.apply') return { results: [{ key: 'tts', ok: true, removed: 3, freed_bytes: 2_000_000 }] };
      throw new Error(`unexpected ${verb}`);
    });
    const onCleaned = vi.fn();
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="agora" call={call} onCleaned={onCleaned} />,
    );
    const scope = within(container);
    await waitFor(() => expect(scope.getByText('TTS cache')).toBeTruthy());
    expect(scope.getByText('1.9 MB')).toBeTruthy();
    expect(scope.queryByText('Subsystem logs')).toBeNull();
    fireEvent.click(scope.getByText('TTS cache'));
    await waitFor(() =>
      expect(call).toHaveBeenCalledWith('host.cleanup.apply', { profile: 'agora', keys: ['tts'] }),
    );
    await waitFor(() => expect(onCleaned).toHaveBeenCalled());
  });

  it('shows the tidy state when nothing is reclaimable', async () => {
    const call = vi.fn(async () => ({ categories: [{ ...PLAN[2] }] }));
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="doc" call={call} />,
    );
    await waitFor(() =>
      expect(within(container).getByText(/Nothing to clean/)).toBeTruthy(),
    );
  });

  it('destructive categories go through a native confirm before applying', async () => {
    const { Alert } = await import('react-native');
    Alert.alert.mockClear();
    const call = vi.fn(async (verb) => {
      if (verb === 'host.cleanup.plan') return { categories: PLAN };
      return { results: [{ key: 'sessions', ok: true, freed_bytes: 512 }] };
    });
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="agora" call={call} />,
    );
    const scope = within(container);
    await waitFor(() => expect(scope.getByText('Old sessions')).toBeTruthy());
    fireEvent.click(scope.getByText('Old sessions'));
    expect(call.mock.calls.filter(([v]) => v === 'host.cleanup.apply')).toHaveLength(0);
    expect(Alert.alert).toHaveBeenCalled();
    const buttons = Alert.alert.mock.calls[0][2];
    buttons.find((b) => b.style === 'destructive').onPress();
    await waitFor(() =>
      expect(call).toHaveBeenCalledWith('host.cleanup.apply', { profile: 'agora', keys: ['sessions'] }),
    );
  });

  it('a pure failure never fires onCleaned; a partial one refreshes anyway', async () => {
    const cleaned = [];
    let applyResult = { results: [{ key: 'tts', ok: false, removed: 0, errors: ['a.mp3: permission denied'] }] };
    const call = vi.fn(async (verb) => {
      if (verb === 'host.cleanup.plan') return { categories: PLAN };
      return applyResult;
    });
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="agora" call={call} onCleaned={() => cleaned.push(1)} />,
    );
    const scope = within(container);
    await waitFor(() => expect(scope.getByText('TTS cache')).toBeTruthy());
    fireEvent.click(scope.getByText('TTS cache'));
    await waitFor(() =>
      expect(call.mock.calls.filter(([v]) => v === 'host.cleanup.apply')).toHaveLength(1),
    );
    expect(cleaned).toHaveLength(0);

    applyResult = { results: [{ key: 'tts', ok: false, removed: 2, freed_bytes: 128, errors: ['b.mp3: busy'] }] };
    const planCallsBefore = call.mock.calls.filter(([v]) => v === 'host.cleanup.plan').length;
    fireEvent.click(scope.getByText('TTS cache'));
    await waitFor(() => expect(cleaned).toHaveLength(1));
    expect(call.mock.calls.filter(([v]) => v === 'host.cleanup.plan').length)
      .toBeGreaterThan(planCallsBefore);
  });

  it('small categories show real byte sizes, not 0.0 MB', async () => {
    const call = vi.fn(async () => ({ categories: [PLAN[1]] }));
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="agora" call={call} />,
    );
    await waitFor(() => expect(within(container).getByText('512 B')).toBeTruthy());
  });

  it('shows the unavailable state when the daemon lacks the verb', async () => {
    const call = vi.fn(async () => { throw new Error('unknown method'); });
    const { container } = render(
      <CleanupSheet open onClose={() => {}} profileName="old" call={call} />,
    );
    await waitFor(() =>
      expect(within(container).getByText(/Cleanup unavailable/)).toBeTruthy(),
    );
  });
});
