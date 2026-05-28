// Tauri's unlisten fn can throw sync OR reject async (during HMR / StrictMode unmount races); swallow both.
export function safeUnlisten(fn) {
  if (!fn) return;
  try {
    const r = fn();
    if (r && typeof r.then === "function") r.catch(() => {});
  } catch { /* tauri race */ }
}
