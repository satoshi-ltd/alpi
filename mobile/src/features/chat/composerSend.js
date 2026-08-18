export function canComposerSend({ hasText, hasAttachments, taskOk, disabled, busy }) {
  return !disabled && !busy && (hasText || hasAttachments) && Boolean(taskOk);
}
