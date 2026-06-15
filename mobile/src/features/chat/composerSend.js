export function canComposerSend({ hasText, hasAttachments, taskOk, disabled }) {
  return !disabled && (hasText || hasAttachments) && Boolean(taskOk);
}
