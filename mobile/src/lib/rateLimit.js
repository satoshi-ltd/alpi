// The daemon closes a throttled socket with 1013 and this exact reason (alpi >= 0.14.41); any other 1013 is capacity.
export const RATE_LIMITED = -32013;
export const RATE_LIMITED_CLOSE_CODE = 1013;
export const RATE_LIMITED_CLOSE_REASON = 'auth-rate-limited';
export const RATE_LIMITED_STATUS = 'rate-limited';
export const RATE_LIMITED_MESSAGE = 'Too many authentication attempts from this IP. Wait a minute and try again.';
export const RATE_LIMITED_REPROBE_MS = 60000;
// One attempt per window from every layer: the transport refuses to open a socket while the hold stands, so probes and data hooks cannot hammer the daemon and extend its window.
export const RATE_LIMITED_HOLD_MS = 60000;
// A close event is spec-guaranteed after an error; this only bounds the wait if a platform ever skips it.
export const CLOSE_AFTER_ERROR_GRACE_MS = 60;

export function isRateLimitedClose(event) {
  return event?.code === RATE_LIMITED_CLOSE_CODE && event?.reason === RATE_LIMITED_CLOSE_REASON;
}
