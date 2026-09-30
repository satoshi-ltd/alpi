import { modelLabel } from '../../lib/modelLabel';

export function modelChipLabel(model, effort) {
  const name = modelLabel(model);
  if (!name) return '';
  const e = String(effort ?? '').trim();
  return e ? `${name} · ${e}` : name;
}
