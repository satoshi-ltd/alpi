export function modelLabel(model) {
  if (typeof model !== 'string') return '';
  const segments = model.trim().split('/').filter(Boolean);
  return segments.length ? segments[segments.length - 1] : '';
}
