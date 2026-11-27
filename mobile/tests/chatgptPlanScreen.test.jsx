import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({
  profile: null, call: null, toast: null, openURL: null, refresh: null, push: null, clip: '',
}));

vi.mock('react-native', () => {
  const View = ({ children }) => React.createElement('div', {}, children);
  const Text = ({ children }) => React.createElement('span', {}, children);
  const Pressable = ({ children, onPress, accessibilityLabel }) => React.createElement('button', { type: 'button', onClick: onPress, 'aria-label': accessibilityLabel }, children);
  return { View, Text, Pressable, ScrollView: View, Linking: { openURL: (...args) => h.openURL(...args) } };
});
vi.mock('expo-router', () => ({
  useLocalSearchParams: () => ({ id: 'doc' }),
  useRouter: () => ({ push: (...args) => h.push(...args) }),
}));
vi.mock('expo-clipboard', () => ({ getStringAsync: async () => h.clip }));
vi.mock('react-native-safe-area-context', () => ({ SafeAreaView: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/theme/ThemeContext', async () => {
  const tokens = await import('../src/theme/tokens');
  return { useTheme: () => ({ colors: new Proxy({}, { get: () => '#000' }), fonts: tokens.fonts, fontSizes: tokens.fontSizes }) };
});
vi.mock('../src/components/KeyboardPane', () => ({ KeyboardPane: ({ children }) => React.createElement('div', {}, children) }));
vi.mock('../src/components/Field', () => ({
  Field: ({ value, onChangeText, label, helper, rightSlot }) => React.createElement('div', {},
    React.createElement('input', { 'aria-label': label, value: value ?? '', onChange: (e) => onChangeText?.(e.target.value) }),
    rightSlot, helper ? React.createElement('em', {}, helper) : null),
}));
vi.mock('../src/components/ScreenHeader', () => ({ ScreenHeader: ({ title, subtitle }) => React.createElement('header', {}, title, ' ', subtitle) }));
vi.mock('../src/components/Button', () => ({
  Button: ({ title, onPress, disabled }) => React.createElement('button', { type: 'button', onClick: onPress, disabled: !!disabled }, title),
}));
vi.mock('../src/components/Toast', () => ({ useToast: () => h.toast }));
vi.mock('../src/components/DeadEnd', () => ({ DeadEnd: () => React.createElement('p', {}, 'dead end') }));
vi.mock('../src/components/Pill', () => ({ Pill: ({ children }) => React.createElement('span', {}, children) }));
vi.mock('../src/components/SkeletonBar', () => ({ SkeletonBar: () => null }));
vi.mock('../src/components/ConfirmDialog', () => ({
  ConfirmDialog: ({ open, onConfirm, confirmLabel, title, body }) => (open
    ? React.createElement('div', {}, title, ' ', body, React.createElement('button', { type: 'button', onClick: onConfirm }, `confirm ${confirmLabel}`))
    : null),
}));
vi.mock('../src/components/Row', () => ({
  Row: ({ label, helper, value, onPress }) => React.createElement('div', { role: onPress ? 'button' : undefined, onClick: onPress }, label, ' ', helper, ' ', value),
  RowGroup: ({ children }) => React.createElement('div', {}, children),
  RowSeparator: () => null,
  SectionHeader: ({ children }) => React.createElement('h3', {}, children),
}));
vi.mock('../src/hooks/useBack', () => ({ useBack: () => vi.fn() }));
vi.mock('../src/hooks/useDirtyBack', () => ({ useDirtyBack: (_dirty, back) => back }));
vi.mock('../src/hooks/useDaemonData', () => ({ useOllamaModels: () => ({ data: null }) }));
vi.mock('../src/hooks/useSubject', () => ({ useProfile: () => ({ profile: h.profile, refresh: h.refresh }) }));
vi.mock('../src/lib/EndpointContext', () => ({ useEndpoint: () => ({ call: (...args) => h.call(...args) }) }));

import ChatGPTPlan from '../app/profile/[id]/providers/chatgpt.jsx';
import ProvidersList from '../app/profile/[id]/providers/index.jsx';

const ADDRESS = 'http://127.0.0.1:1455/auth/callback?code=c&state=s&client_id=oaiapp_1';

beforeEach(() => {
  h.profile = { name: 'doc', provider_keys: [], provider_ollama: [], provider_chatgpt: { signed_in: false, email: '', plan_declined: false, models: 0 } };
  h.toast = vi.fn();
  h.openURL = vi.fn(async () => true);
  h.refresh = vi.fn(async () => {});
  h.push = vi.fn();
  h.clip = '';
  h.call = vi.fn(async (method) => {
    if (method === 'host.providers.chatgpt_begin') return { url: 'https://auth.openai.com/api/accounts/authorize?state=s', redirect_uri: 'http://127.0.0.1:1455/auth/callback' };
    if (method === 'host.providers.chatgpt_finish') return { signed_in: true, email: 'a@example.com', first_sign_in: true };
    return { ok: true, revoked: true };
  });
});

describe('ChatGPT plan on the phone', () => {
  it('shows what will happen before the browser opens, with one way in', () => {
    render(<ChatGPTPlan />);

    expect(screen.getByText('1. Sign in in the browser.')).toBeTruthy();
    expect(screen.getByText('2. The last page will not load. Copy its whole address.')).toBeTruthy();
    expect(screen.getByText('3. Come back and paste it here.')).toBeTruthy();
    expect(screen.getByLabelText('Address')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Finish' }).disabled).toBe(true);
    expect(screen.queryByRole('button', { name: 'Open browser again' })).toBeNull();
  });

  it('opens the browser, then finishes with the address the person carries back', async () => {
    render(<ChatGPTPlan />);

    fireEvent.click(screen.getByRole('button', { name: 'Continue with ChatGPT' }));
    await waitFor(() => expect(h.openURL).toHaveBeenCalledWith('https://auth.openai.com/api/accounts/authorize?state=s'));
    expect(h.call).toHaveBeenCalledWith('host.providers.chatgpt_begin', { profile: 'doc', port: 1455 });
    await waitFor(() => screen.getByRole('button', { name: 'Open browser again' }));
    expect(screen.queryByRole('button', { name: 'Continue with ChatGPT' })).toBeNull();

    fireEvent.change(screen.getByLabelText('Address'), { target: { value: 'https://chatgpt.com/' } });
    expect(screen.getByText('must start with http://127.0.0.1:1455/auth/callback')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Finish' }).disabled).toBe(true);

    h.clip = `  ${ADDRESS}\n`;
    fireEvent.click(screen.getByRole('button', { name: 'Paste address' }));
    await waitFor(() => expect(screen.getByLabelText('Address').value).toBe(ADDRESS));
    fireEvent.click(screen.getByRole('button', { name: 'Finish' }));

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: "You're using your ChatGPT plan", message: 'a@example.com' }));
    expect(h.call).toHaveBeenCalledWith('host.providers.chatgpt_finish', { profile: 'doc', callback: ADDRESS }, { timeoutMs: 120000 });
    expect(h.refresh).toHaveBeenCalled();
  });

  it('takes from the clipboard only a sign-in address', async () => {
    render(<ChatGPTPlan />);
    h.clip = 'my bank password';
    fireEvent.click(screen.getByRole('button', { name: 'Paste address' }));

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: 'Clipboard has no sign-in address' }));
    expect(screen.getByLabelText('Address').value).toBe('');
  });

  it('keeps the way in when the browser cannot be opened', async () => {
    h.openURL = vi.fn(async () => { throw new Error('no browser'); });
    render(<ChatGPTPlan />);
    fireEvent.click(screen.getByRole('button', { name: 'Continue with ChatGPT' }));

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: 'Sign-in failed', message: 'no browser' }));
    expect(screen.getByRole('button', { name: 'Continue with ChatGPT' })).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Open browser again' })).toBeNull();
  });

  it('shows the daemon\'s own reason when the answer is refused and keeps what was pasted', async () => {
    h.call = vi.fn(async (method) => {
      if (method === 'host.providers.chatgpt_begin') return { url: 'https://auth.openai.com/x?state=s' };
      throw Object.assign(new Error('chatgpt-sign-in'), { data: { detail: 'that address belongs to another sign-in attempt' } });
    });
    render(<ChatGPTPlan />);
    fireEvent.change(screen.getByLabelText('Address'), { target: { value: ADDRESS } });
    fireEvent.click(screen.getByRole('button', { name: 'Finish' }));

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: 'Sign-in failed', message: 'that address belongs to another sign-in attempt' }));
    expect(screen.getByLabelText('Address').value).toBe(ADDRESS);
  });

  it('once signed in shows the account, the usage link and a sign out that says what it costs', async () => {
    h.profile.provider_chatgpt = { signed_in: true, email: 'a@example.com', plan_declined: false, models: 4 };
    h.profile.model = 'chatgpt-plan/gpt-6.2-sol';
    h.call = vi.fn(async () => ({ ok: true, revoked: true, model_cleared: true }));
    render(<ChatGPTPlan />);

    expect(screen.getByText(/a@example.com/)).toBeTruthy();
    expect(screen.queryByText(/model/)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Continue with ChatGPT' })).toBeNull();
    fireEvent.click(screen.getByText(/Manage usage/));
    expect(h.openURL).toHaveBeenCalledWith('https://chatgpt.com/settings/usage');

    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(h.call).not.toHaveBeenCalled();
    expect(screen.getByText(/@doc is left without a model\./)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'confirm Sign out' }));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.providers.chatgpt_logout', { profile: 'doc', forget: true }, { timeoutMs: 120000 }));
    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: 'Signed out', message: '@doc has no model.' }));
  });

  it('never opens an address that is not OpenAI\'s sign-in', async () => {
    h.call = vi.fn(async () => ({ url: 'file:///Applications/Calculator.app' }));
    render(<ChatGPTPlan />);
    fireEvent.click(screen.getByRole('button', { name: 'Continue with ChatGPT' }));

    await waitFor(() => expect(h.toast).toHaveBeenCalledWith({ title: 'Sign-in failed', message: "The daemon returned an address that is not OpenAI's sign-in." }));
    expect(h.openURL).not.toHaveBeenCalled();
  });

  it('says plan use was declined and lets the person end that session', async () => {
    h.profile.provider_chatgpt = { signed_in: false, email: 'a@example.com', plan_declined: true, models: 0 };
    render(<ChatGPTPlan />);

    expect(screen.getByText('Plan use was declined. Sign in again to allow it.')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Sign out' }));
    expect(screen.getByText(/@doc can no longer use plan models\./)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'confirm Sign out' }));
    await waitFor(() => expect(h.call).toHaveBeenCalledWith('host.providers.chatgpt_logout', { profile: 'doc', forget: true }, { timeoutMs: 120000 }));
  });

  it('offers Sign out when a registration is saved but its session ended', () => {
    h.profile.provider_chatgpt = { signed_in: false, email: 'a@example.com', plan_declined: false, registered: true, models: 0 };
    render(<ChatGPTPlan />);

    expect(screen.getByRole('button', { name: 'Sign out' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Continue with ChatGPT' })).toBeTruthy();
  });

  it('tells the owner of an older daemon what to do', () => {
    delete h.profile.provider_chatgpt;
    render(<ChatGPTPlan />);

    expect(screen.getByText('Update alpi on this daemon to sign in with ChatGPT.')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Continue with ChatGPT' })).toBeNull();
  });
});

describe('Providers list', () => {
  it('lists the ChatGPT plan with the cloud providers, after OpenAI, and opens its screen', () => {
    render(<ProvidersList />);
    const html = document.body.innerHTML;
    expect(html.indexOf('OPENAI_API_KEY')).toBeLessThan(html.indexOf('ChatGPT plan'));
    expect(html.indexOf('ChatGPT plan')).toBeLessThan(html.indexOf('OPENROUTER_API_KEY'));
    expect(html.match(/ChatGPT plan/g)).toHaveLength(1);
    expect(screen.getByText('not signed in')).toBeTruthy();

    fireEvent.click(screen.getByText(/ChatGPT plan/));
    expect(h.push).toHaveBeenCalledWith('/profile/doc/providers/chatgpt');
  });

  it('leaves it out on a daemon that predates the sign-in, and lists Groq with the other keys', () => {
    delete h.profile.provider_chatgpt;
    render(<ProvidersList />);

    expect(screen.queryByText(/ChatGPT plan/)).toBeNull();
    expect(screen.getByText(/GROQ_API_KEY/)).toBeTruthy();
  });
});
