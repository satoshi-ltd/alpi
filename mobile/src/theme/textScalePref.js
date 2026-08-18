import * as SecureStore from 'expo-secure-store';

import { clampTextScale, DEFAULT_TEXT_SCALE } from './textScale';

const KEY = 'alpi.textScale';

export async function loadTextScale() {
  const raw = await SecureStore.getItemAsync(KEY);
  return raw == null ? DEFAULT_TEXT_SCALE : clampTextScale(raw);
}

export async function saveTextScale(value) {
  await SecureStore.setItemAsync(KEY, String(clampTextScale(value)));
}
