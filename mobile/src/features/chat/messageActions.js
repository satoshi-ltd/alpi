export function buildMessageActions(target, { onCopy, onEdit, onRetry }) {
  if (!target) return [];
  const isAgent = target.kind === 'agent';
  const out = [];
  if (onCopy) out.push({ id: 'copy', label: 'Copy', onPress: () => onCopy(target) });
  if (!isAgent && onEdit) {
    out.push({ id: 'edit', label: 'Edit', onPress: () => onEdit(target) });
  }
  if (!isAgent && onRetry) {
    out.push({ id: 'retry', label: 'Retry', onPress: () => onRetry(target) });
  }
  if (isAgent && onRetry && target.retryText) {
    out.push({ id: 'retry-agent', label: 'Ask again', onPress: () => onRetry(target) });
  }
  return out;
}

export function retryTextFor(target) {
  if (!target) return null;
  if (target.kind === 'agent') return target.retryText ?? null;
  return target.text ?? null;
}
