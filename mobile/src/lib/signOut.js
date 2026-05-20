import * as SecureStore from 'expo-secure-store';

import { resetReadState } from './readState';

const KEYS = [
  'alpi.connections',
  'alpi.endpoint',
  'alpi.pinned',
  'alpi.biometric',
  'alpi.themePref',
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
