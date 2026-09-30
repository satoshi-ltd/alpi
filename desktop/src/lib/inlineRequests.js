export function belongsToChat(req, scope) {
  if (!req || !scope?.profile || req.profile !== scope.profile) return false;
  const ids = (scope.sessionIds ?? []).filter(Boolean);
  if (req.session_id) return ids.includes(req.session_id);
  return !!scope.live;
}

export function splitInline(queue, scope) {
  const inline = [];
  const modal = [];
  for (const req of queue ?? []) (belongsToChat(req, scope) ? inline : modal).push(req);
  return { inline, modal };
}
