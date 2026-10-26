import { modelLabel } from '../../lib/modelLabel';

export function modelChipParts(model, effort) {
  const name = modelLabel(model);
  if (!name) return null;
  return { model: name, effort: String(effort ?? '').trim() };
}

export function modelChipLabel(model, effort) {
  const parts = modelChipParts(model, effort);
  if (!parts) return '';
  return parts.effort ? `${parts.model} · ${parts.effort}` : parts.model;
}
