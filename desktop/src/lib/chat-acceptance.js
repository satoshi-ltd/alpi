import { listen } from "@tauri-apps/api/event";

export const ACCEPTANCE_TIMEOUT_MS = 8000;

export function watchAcceptance(requestId, { timeoutMs = ACCEPTANCE_TIMEOUT_MS } = {}) {
  let done = false;
  let unlisten = null;
  let timer = null;
  let settle = () => {};
  const promise = new Promise((resolve) => {
    settle = (verdict) => {
      if (done) return;
      done = true;
      clearTimeout(timer);
      try { unlisten?.(); } catch { /* */ }
      resolve(verdict);
    };
  });
  timer = setTimeout(() => settle({ accepted: true }), timeoutMs);
  const ready = listen("chat-event", (event) => {
    const payload = event?.payload;
    if (payload?.request_id !== requestId) return;
    if (payload.kind === "heartbeat") return;
    if (payload.kind === "error") settle({ accepted: false, text: String(payload.text ?? "") });
    else settle({ accepted: true });
  })
    .then((fn) => {
      if (done) fn?.();
      else unlisten = fn;
    })
    .catch(() => settle({ accepted: true }));
  return { ready, promise, cancel: () => settle({ accepted: true }) };
}
