import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';

const h = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn(), dismissAll: vi.fn(), sheet: null, tools: null }));

vi.mock('react-native', () => {
  const View = ({ children, accessibilityRole }) => React.createElement('div', { role: accessibilityRole }, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress }) =>
    React.createElement('button', { type: 'button', onClick: onPress }, typeof children === 'function' ? children({ pressed: false }) : children);
  return { View, Text, Pressable, ScrollView: ({ children }) => React.createElement('div', {}, children) };
});
vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace, back: vi.fn(), canDismiss: () => true, dismissAll: h.dismissAll }),
  useLocalSearchParams: () => ({ id: 'doc', key: 'not-a-provider' }),
}));
vi.mock('./Button', () => ({ Button: ({ title, onPress }) => React.createElement('button', { type: 'button', onClick: onPress }, title) }));
vi.mock('../features/sheets/ConnectionSheet', () => ({
  ConnectionSheet: ({ open }) => (open ? React.createElement('div', { 'data-sheet': 'connection' }) : null),
}));
vi.mock('../theme/ThemeContext', () => ({
  useTheme: () => ({
    colors: { ink: '#000', ink2: '#333', ink3: '#666', bg: '#fff' },
    fonts: { sans: { regular: 'r', medium: 'm', semibold: 's' }, mono: 'mono' },
    fontSizes: { xs: 11, sm: 12, base: 14, lg: 15, xl: 18, xxl: 22 },
  }),
}));
vi.mock('../hooks/useDaemonData', () => ({ useTools: () => h.tools, useOllamaModels: () => ({ data: null }) }));
vi.mock('../hooks/useBusyVisible', () => ({ useBusyVisible: () => false }));
vi.mock('./ScreenHeader', () => ({ ScreenHeader: ({ subtitle }) => React.createElement('header', {}, subtitle) }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('./KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('./Toast', () => ({ useToast: () => vi.fn() }));
vi.mock('../hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../hooks/useSubject', () => ({ useProfile: () => ({ profile: null, refresh: vi.fn() }) }));
vi.mock('../lib/EndpointContext', () => ({ useEndpoint: () => ({ call: vi.fn() }) }));

import { EMPTY } from '../../../common/emptyCopy.mjs';
import { DeadEnd } from './DeadEnd';
import { ToolDetail } from '../features/brain/ToolDetail';
import ProviderKey from '../../app/profile/[id]/providers/[key].jsx';

afterEach(cleanup);

describe('DeadEnd', () => {
  it('renders an alert with the shared copy and takes the phone back to the inbox', () => {
    render(<DeadEnd copy="missingWorkgroup" />);
    expect(screen.getByRole('alert')).toBeTruthy();
    expect(screen.getByText(EMPTY.missingWorkgroup.title)).toBeTruthy();
    h.dismissAll.mockClear();
    h.replace.mockClear();
    fireEvent.click(screen.getByText('Back to inbox'));
    expect(h.dismissAll).toHaveBeenCalledTimes(1);
    expect(h.replace).toHaveBeenCalledWith('/');
    expect(h.dismissAll.mock.invocationCallOrder[0]).toBeLessThan(h.replace.mock.invocationCallOrder[0]);
  });

  it('offers Retry instead of claiming the row is gone when the read failed', () => {
    const onRetry = vi.fn();
    render(<DeadEnd copy="missingProfile" error={{ message: 'request timed out after 15000ms' }} onRetry={onRetry} label="this profile" />);
    expect(screen.queryByText(EMPTY.missingProfile.title)).toBeNull();
    expect(screen.getByText("Couldn't load this profile")).toBeTruthy();
    fireEvent.click(screen.getByText('Retry'));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('sends an unpaired phone to pairing', () => {
    render(<DeadEnd copy="unpaired" action="pair" />);
    fireEvent.click(screen.getByText('Pair this phone'));
    expect(h.push).toHaveBeenCalledWith('/pair');
  });

  it('opens the connection sheet only when asked', async () => {
    render(<DeadEnd copy="foreignConnection" action="connection" />);
    expect(document.querySelector('[data-sheet]')).toBeNull();
    await act(async () => { fireEvent.click(screen.getByText('Switch connection')); });
    expect(await screen.findByText((_, el) => el?.getAttribute?.('data-sheet') === 'connection')).toBeTruthy();
  });
});

describe('a tool that is no longer exposed', () => {
  it('shows the dead end with its way back', () => {
    h.tools = { data: { tools: [] }, loading: false, error: null, refresh: vi.fn() };
    render(<ToolDetail profile="doc" name="ghost" />);
    expect(screen.getByText(EMPTY.missingTool.title)).toBeTruthy();
    expect(screen.getByText('Back to inbox')).toBeTruthy();
  });
});

describe('a provider link this phone does not know', () => {
  it('shows the dead end with its way back', () => {
    render(<ProviderKey />);
    expect(screen.getByText(EMPTY.missingProvider.title)).toBeTruthy();
    fireEvent.click(screen.getByText('Back to inbox'));
    expect(h.replace).toHaveBeenCalledWith('/');
  });
});
