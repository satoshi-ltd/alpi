import * as SecureStore from 'expo-secure-store';

const STORAGE_KEY = 'alpi.spent-pairings.v1';
const KEEP = 10;

let spent = null;

async function load() {
  if (spent) return spent;
  let list = [];
  try {
    const raw = await SecureStore.getItemAsync(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (Array.isArray(parsed)) list = parsed.filter((t) => typeof t === 'string');
  } catch {
    list = [];
  }
  if (!spent) spent = new Set(list);
  return spent;
}

export async function rememberSpentPairing(token) {
  if (typeof token !== 'string' || !token) return;
  const known = await load();
  known.add(token);
  const recent = [...known].slice(-KEEP);
  spent = new Set(recent);
  try {
    await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(recent));
  } catch {
    return;
  }
}

export async function isSpentPairing(token) {
  if (typeof token !== 'string' || !token) return false;
  return (await load()).has(token);
}

export function _resetSpentPairingsForTests() {
  spent = null;
}
