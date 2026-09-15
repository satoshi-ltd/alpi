export const RATE_LIMITED = "rate-limited";
export const RATE_LIMITED_CLOSE = "1013 auth-rate-limited";
export const RATE_LIMITED_MESSAGE =
  "Too many authentication attempts from this IP. Wait a minute and try again.";
export const RATE_LIMITED_RETRY_MS = 60000;

export function isRateLimitedError(text) {
  return String(text ?? "").includes(RATE_LIMITED_CLOSE);
}

export function describeConnectionError(text) {
  return isRateLimitedError(text) ? RATE_LIMITED_MESSAGE : String(text ?? "");
}
