// Theme preference persistence — one of 'light' | 'dark' | 'system'.
// Stored in SecureStore alongside other tiny prefs.

import * as SecureStore from 'expo-secure-store';

const KEY = 'alpi.themePref';
const VALID = new Set(['light', 'dark', 'system']);

export async function loadThemePref() {
  const raw = await SecureStore.getItemAsync(KEY);
  return VALID.has(raw) ? raw : 'light';
}

export async function saveThemePref(value) {
  if (!VALID.has(value)) return;
  await SecureStore.setItemAsync(KEY, value);
}
