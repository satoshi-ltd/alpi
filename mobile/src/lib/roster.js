import { splitDefaultProfile } from '../../../common/rosterOrder.mjs';

const MATCH_FIELDS = ['label', 'name', 'id', 'preview'];
const CREATABLE_SECTIONS = ['profiles', 'workgroups'];

export const SECTION_LABELS = { front: '', pinned: 'PINNED', profiles: 'PROFILES', workgroups: 'WORKGROUPS' };

const profileOf = (item) => (item?.kind === 'profile' ? item.raw ?? item : null);

function needle(query) {
  return String(query ?? '').replace(/^[@#]/, '').trim().toLowerCase();
}

export function matchesQuery(item, query) {
  const q = needle(query);
  if (!q) return true;
  return MATCH_FIELDS.some((field) => String(item?.[field] ?? '').toLowerCase().includes(q));
}

export function rosterSections(items, query, options) {
  const { front, rest: others } = splitDefaultProfile(items ?? [], profileOf);
  const hits = others.filter((item) => matchesQuery(item, query));
  const rest = hits.filter((item) => !item.pinned);
  const kept = needle(query)
    ? []
    : (options?.keepEmpty ?? []).filter((key) => CREATABLE_SECTIONS.includes(key));
  return [
    { key: 'front', label: SECTION_LABELS.front, data: front && matchesQuery(front, query) ? [front] : [] },
    { key: 'pinned', label: SECTION_LABELS.pinned, data: hits.filter((item) => item.pinned) },
    { key: 'profiles', label: SECTION_LABELS.profiles, data: rest.filter((item) => item.kind === 'profile') },
    { key: 'workgroups', label: SECTION_LABELS.workgroups, data: rest.filter((item) => item.kind === 'workgroup') },
  ].filter((section) => section.data.length > 0 || kept.includes(section.key));
}

export function rosterIsEmpty(sections) {
  return (sections ?? []).every((section) => (section.data?.length ?? 0) === 0);
}
