export async function copyText(text) {
  try {
    const Clipboard = await import('expo-clipboard');
    await Clipboard.setStringAsync(String(text ?? ''));
    return true;
  } catch {
    return false;
  }
}
