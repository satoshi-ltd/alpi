import * as SecureStore from 'expo-secure-store';

import { resetReadState } from './readState';

// alpi.endpoint is the legacy single-endpoint key; loadConnections no longer migrates it, but signOut still wipes it so an old build's leftover token does not linger in SecureStore.
const KEYS = [
  'alpi.connections',
  'alpi.endpoint',
  'alpi.pinned',
  'alpi.biometric',
  'alpi.themePref',
  'alpi.textScale',
  'alpi.read-state.v1',
];

export async function signOut() {
  await Promise.all(
    KEYS.map((key) =>
      SecureStore.deleteItemAsync(key).catch(() => {}),
    ),
  );
  resetReadState();
}
