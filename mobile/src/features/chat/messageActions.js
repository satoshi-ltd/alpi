export function buildMessageActions(target, { onCopy, onSelectText, onDownload, onExportPdf, onEdit, onRetry }) {
  if (!target) return [];
  const isAgent = target.kind === 'agent';
  const out = [];
  if (onCopy) out.push({ id: 'copy', label: 'Copy', onPress: () => onCopy(target) });
  if (onSelectText && target.text) out.push({ id: 'select', label: 'Select text', onPress: () => onSelectText(target) });
  if (isAgent && target.text && onDownload) out.push({ id: 'download', label: 'Download .md', onPress: () => onDownload(target) });
  if (isAgent && target.text && onExportPdf) out.push({ id: 'pdf', label: 'Export PDF…', onPress: () => onExportPdf(target) });
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

export function agentTurnTarget(turn, { profileName, accent, turnIndex, exportBody }) {
  return {
    kind: 'agent',
    text: turn.assistant,
    exportBody,
    retryText: turn.user,
    turnIndex,
    exportProfile: profileName,
    exportAt: turn.ended_at || turn.at,
    exportAccent: accent,
  };
}

export function showsMoreButton({ last, turn }) {
  return !!last && !turn.pending && !!turn.assistant;
}

export function workgroupTarget({ isOwn, body, text, speakerName, speakerAccent, at }) {
  const shown = text ?? body;
  return isOwn
    ? { kind: 'user', text: shown }
    : { kind: 'agent', text: shown, exportProfile: speakerName, exportAt: at, exportAccent: speakerAccent };
}
