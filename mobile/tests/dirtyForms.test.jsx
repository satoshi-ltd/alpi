import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ params: {}, dirty: [], back: vi.fn() }));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel }) => React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, children);
  return { View, Text, Pressable, ScrollView: View };
});
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => h.params,
  usePathname: () => '/profile/doc',
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
}));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return { useTheme: () => ({ colors: new Proxy({}, { get: () => '#000' }), fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});
vi.mock('../src/components/KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/Field', () => ({
  Field: ({ value, onChangeText, label, placeholder }) =>
    React.createElement('input', { 'aria-label': label || placeholder || 'field', value: value ?? '', onChange: (e) => onChangeText?.(e.target.value) }),
}));
vi.mock('../src/components/ScreenHeader', () => ({
  ScreenHeader: ({ title, onBack }) => React.createElement('header', {}, React.createElement('button', { type: 'button', onClick: onBack }, 'Back'), title),
}));
vi.mock('../src/components/Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../src/components/Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../src/components/Eyebrow', () => ({ Eyebrow: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/Icon', () => ({ Icon: () => null }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/DeadEnd', () => ({ DeadEnd: () => null }));
vi.mock('../src/components/SkeletonBar', () => ({ SkeletonBar: () => null }));
vi.mock('../src/components/ListSkeleton', () => ({ ListSkeleton: () => null }));
vi.mock('../src/components/ConfirmDialog', () => ({ ConfirmDialog: () => null, Bold: ({ children }) => children, Code: ({ children }) => children }));
vi.mock('../src/components/Row', () => ({
  Row: ({ label }) => React.createElement('div', {}, label),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../src/features/peers/ScopeToggles', () => ({
  ScopeToggles: ({ onToggle }) => React.createElement('button', { type: 'button', onClick: () => onToggle('link.cancel') }, 'Toggle cancel'),
}));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => h.back }));
vi.mock('../src/hooks/useDaemonData', () => ({ useOllamaModels: () => ({ data: null }) }));
vi.mock('../src/hooks/useSubject', () => ({ useProfile: () => ({ profile: { name: 'doc', provider_keys: [], provider_ollama: [] }, refresh: async () => {} }) }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn(async () => ({})) }) }));
vi.mock('../src/hooks/useDirtyBack', () => ({
  useDirtyBack: (dirty, back) => {
    h.dirty.push(dirty);
    return Object.assign(() => (dirty ? 'asked' : back()), { leave: back });
  },
}));

import ProviderKey from '../app/profile/[id]/providers/[key].jsx';
import NewMcp from '../app/profile/[id]/mcp/new.jsx';
import NewEmail from '../app/profile/[id]/email/new.jsx';
import NewPeer from '../app/profile/[id]/peers/new.jsx';
import AcceptPeer from '../app/profile/[id]/peers/accept.jsx';

const FORMS = [
  ['a provider API key', ProviderKey, { id: 'doc', key: 'openrouter' }],
  ['a new Ollama instance', ProviderKey, { id: 'doc', key: 'ollama-new' }],
  ['a new MCP server', NewMcp, { id: 'doc' }],
  ['a new email account', NewEmail, { id: 'doc' }],
  ['a new peer', NewPeer, { id: 'doc' }],
  ['accepting a peer', AcceptPeer, { id: 'doc', handle: 'mira', pubkey: 'AAAA', address: 'tcp://x:1' }],
];

describe('phone forms warn before back drops what was typed', () => {
  it.each(FORMS)('%s starts clean and turns dirty once something is typed', (_name, Screen, params) => {
    h.params = params;
    h.dirty = [];
    render(<Screen />);
    expect(h.dirty.at(-1)).toBe(false);
    fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: 'typed-x' } });
    expect(h.dirty.at(-1)).toBe(true);
  });

  it.each(FORMS)('%s sends the header back through the guard', (_name, Screen, params) => {
    h.params = params;
    h.back.mockClear();
    render(<Screen />);
    fireEvent.change(screen.getAllByRole('textbox')[0], { target: { value: 'typed-x' } });
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(h.back).not.toHaveBeenCalled();
  });
});

describe('a new peer counts its permissions as pending', () => {
  it('turns dirty when only a permission changes and asks before going back', () => {
    h.params = { id: 'doc' };
    h.dirty = [];
    h.back.mockClear();
    render(<NewPeer />);
    expect(h.dirty.at(-1)).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: 'Toggle cancel' }));
    expect(h.dirty.at(-1)).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(h.back).not.toHaveBeenCalled();
  });

  it('goes back without asking when nothing changed', () => {
    h.params = { id: 'doc' };
    h.back.mockClear();
    render(<NewPeer />);
    fireEvent.click(screen.getByRole('button', { name: 'Back' }));
    expect(h.back).toHaveBeenCalledTimes(1);
  });
});
