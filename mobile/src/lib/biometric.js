// expo-local-authentication wrapper + SecureStore-backed pref for whether the app should lock at cold start.

import * as LocalAuthentication from 'expo-local-authentication';
import * as SecureStore from 'expo-secure-store';

const KEY = 'alpi.biometric';

export async function biometricCapabilities() {
  try {
    const hasHardware = await LocalAuthentication.hasHardwareAsync();
    const enrolled = await LocalAuthentication.isEnrolledAsync();
    const types = await LocalAuthentication.supportedAuthenticationTypesAsync();
    let label = 'Biometric';
    if (types.includes(LocalAuthentication.AuthenticationType.FACIAL_RECOGNITION)) label = 'Face ID';
    else if (types.includes(LocalAuthentication.AuthenticationType.FINGERPRINT)) label = 'Fingerprint';
    else if (types.includes(LocalAuthentication.AuthenticationType.IRIS)) label = 'Iris';
    return { hasHardware, enrolled, label };
  } catch {
    return { hasHardware: false, enrolled: false, label: 'Biometric' };
  }
}

export async function getBiometricPref() {
  try {
    const raw = await SecureStore.getItemAsync(KEY);
    return raw === '1';
  } catch {
    return false;
  }
}

export async function setBiometricPref(on) {
  try {
    if (on) await SecureStore.setItemAsync(KEY, '1');
    else await SecureStore.deleteItemAsync(KEY);
  } catch {}
}

export async function authenticate(reason = 'Unlock alpi') {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: reason,
      cancelLabel: 'Cancel',
      disableDeviceFallback: false,
    });
    return result.success === true;
  } catch {
    return false;
  }
}
