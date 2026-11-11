import * as SecureStore from 'expo-secure-store';

// Tokens and notification cursors must not travel in an encrypted backup to another phone; background polls still read them after the first unlock.
export function deviceOnlyOpts() {
  try {
    if (SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY !== undefined) {
      return { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY };
    }
    if (SecureStore.AFTER_FIRST_UNLOCK !== undefined) {
      return { keychainAccessible: SecureStore.AFTER_FIRST_UNLOCK };
    }
  } catch { /* */ }
  return {};
}

// expo-secure-store updates only the value of an existing item, never its class, so an item moves to a new key once.
export async function readMovedItem(key, legacyKey) {
  const current = await SecureStore.getItemAsync(key);
  if (current != null) return current;
  // Concurrent first reads share one move, so a late copy of the legacy value never lands over a newer write.
  let move = moves.get(key);
  if (!move) {
    move = moveItem(key, legacyKey).finally(() => moves.delete(key));
    moves.set(key, move);
  }
  return move;
}

const moves = new Map();

async function moveItem(key, legacyKey) {
  const current = await SecureStore.getItemAsync(key);
  if (current != null) return current;
  const legacy = await SecureStore.getItemAsync(legacyKey);
  if (legacy == null) return null;
  await SecureStore.setItemAsync(key, legacy, deviceOnlyOpts());
  await SecureStore.deleteItemAsync(legacyKey);
  return legacy;
}
