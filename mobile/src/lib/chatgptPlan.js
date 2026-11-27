export const CHATGPT_USAGE_URL = 'https://chatgpt.com/settings/usage';
export const CHATGPT_CALLBACK_PORT = 1455;
export const CALLBACK_START = `http://127.0.0.1:${CHATGPT_CALLBACK_PORT}/auth/callback`;
export const PLAN_DECLINED = 'Plan use was declined. Sign in again to allow it.';
export const SIGN_IN_STEPS = [
  'Sign in in the browser.',
  'The last page will not load. Copy its whole address.',
  'Come back and paste it here.',
];

export function looksLikeCallback(text) {
  const value = String(text ?? '').trim();
  return /^https?:\/\/(127\.0\.0\.1|localhost)(:\d+)?\/auth\/callback\?/.test(value) && /[?&]state=[^&]+/.test(value);
}

// The daemon names the address and the phone opens it: only OpenAI's sign-in may be opened on its word.
export function isSignInUrl(url) {
  const value = String(url ?? '');
  return /^https:\/\/auth\.openai\.com\/\S+$/.test(value) && !/[\u0000-\u001f\u007f]/.test(value);
}

// The daemon talks to OpenAI inside these calls; the default timeout would give up while it is still signing in.
export const CHATGPT_CALL = { timeoutMs: 120000 };

export function chatgptRow(state) {
  if (!state) return null;
  if (state.signed_in) return { helper: state.email || undefined, pill: 'signed in', on: true };
  if (state.plan_declined) return { helper: 'plan use declined', pill: 'not signed in', on: false };
  return { helper: undefined, pill: 'not signed in', on: false };
}

export function signedInMessage(result) {
  const who = result?.email || 'your account';
  return result?.first_sign_in
    ? { title: "You're using your ChatGPT plan", message: who }
    : { title: 'Signed in', message: who };
}

export function signedOutMessage(result, profile) {
  const left = result?.model_cleared ? `@${profile} has no model.` : undefined;
  if (result?.revoked === false) {
    return { title: 'Signed out here only', message: ['Remove alpi in ChatGPT settings.', left].filter(Boolean).join(' ') };
  }
  return left ? { title: 'Signed out', message: left } : { title: 'Signed out' };
}

export function failureMessage(error) {
  const text = String(error?.data?.detail || error?.message || error || '');
  if (/method[- ]not[- ]found|-32601/i.test(text)) return 'Update alpi on this daemon to sign in with ChatGPT.';
  return text.replace(/^Error:\s*/, '');
}
