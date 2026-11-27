import { describe, expect, it } from 'vitest';

import { chatgptRow, failureMessage, isSignInUrl, looksLikeCallback, signedInMessage, signedOutMessage } from './chatgptPlan';

describe('looksLikeCallback', () => {
  it('accepts the address the browser ends on', () => {
    expect(looksLikeCallback(' http://127.0.0.1:1455/auth/callback?code=c&state=s&client_id=x ')).toBe(true);
    expect(looksLikeCallback('http://localhost:1455/auth/callback?state=s&code=c')).toBe(true);
  });

  it.each([
    '', null, 'https://auth.openai.com/api/accounts/authorize?state=s', 'http://127.0.0.1:1455/auth/callback',
    'http://127.0.0.1:1455/auth/callback?code=c', 'http://127.0.0.1:1455/other?state=s', 'state=s&code=c',
  ])('refuses %s', (text) => expect(looksLikeCallback(text)).toBe(false));
});

describe('isSignInUrl', () => {
  it('accepts only OpenAI\'s sign-in address', () => {
    expect(isSignInUrl('https://auth.openai.com/api/accounts/authorize?state=s')).toBe(true);
  });

  it.each([
    '', null, 'https://auth.openai.com/', 'http://auth.openai.com/x', 'https://auth.openai.com.evil.test/x', 'file:///x',
    'intent://x#Intent;end', 'https://auth.openai.com/a b', 'https://auth.openai.com/a\nb', 'tel:123',
  ])('refuses %s', (url) => expect(isSignInUrl(url)).toBe(false));
});

describe('chatgptRow', () => {
  it('is absent on a daemon that predates the sign-in', () => {
    expect(chatgptRow(undefined)).toBeNull();
    expect(chatgptRow(null)).toBeNull();
  });

  it('names the account once signed in and says nothing twice before', () => {
    expect(chatgptRow({ signed_in: true, email: 'a@example.com' })).toEqual({ helper: 'a@example.com', pill: 'signed in', on: true });
    expect(chatgptRow({ signed_in: true, email: '' })).toEqual({ helper: undefined, pill: 'signed in', on: true });
    expect(chatgptRow({ signed_in: false, plan_declined: true })).toEqual({ helper: 'plan use declined', pill: 'not signed in', on: false });
    expect(chatgptRow({ signed_in: false })).toEqual({ helper: undefined, pill: 'not signed in', on: false });
  });
});

describe('messages', () => {
  it('confirms plan use the first time and only names the account afterwards', () => {
    expect(signedInMessage({ email: 'a@example.com', first_sign_in: true })).toEqual({ title: "You're using your ChatGPT plan", message: 'a@example.com' });
    expect(signedInMessage({ email: 'a@example.com' })).toEqual({ title: 'Signed in', message: 'a@example.com' });
  });

  it('says when signing out left the profile without a model or was not confirmed', () => {
    expect(signedOutMessage({ revoked: true }, 'doc')).toEqual({ title: 'Signed out' });
    expect(signedOutMessage({ revoked: true, model_cleared: true }, 'doc')).toEqual({ title: 'Signed out', message: '@doc has no model.' });
    expect(signedOutMessage({ revoked: false, model_cleared: true }, 'doc')).toEqual({
      title: 'Signed out here only', message: 'Remove alpi in ChatGPT settings. @doc has no model.',
    });
  });

  it('turns an older daemon into an instruction and keeps the daemon\'s own sentence otherwise', () => {
    expect(failureMessage(new Error('host.providers.chatgpt_begin: method-not-found'))).toBe('Update alpi on this daemon to sign in with ChatGPT.');
    expect(failureMessage({ data: { detail: 'that address belongs to another sign-in attempt' } })).toBe('that address belongs to another sign-in attempt');
  });
});
