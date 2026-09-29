import * as SecureStore from 'expo-secure-store';

const KEY = 'alpi.sidebarOpen';

export async function loadSidebarPref() {
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    if (raw === 'open') return true;
    if (raw === 'closed') return false;
  } catch {
    return null;
  }
  return null;
}

export async function saveSidebarPref(open) {
  try {
    await SecureStore.setItemAsync(KEY, open ? 'open' : 'closed');
  } catch {
    return;
  }
}
