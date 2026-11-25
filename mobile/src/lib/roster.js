import { useRef } from 'react';

import { splitDefaultProfile } from '../../../common/rosterOrder.mjs';
import { groupWorkgroupRows, inFilter, rosterWorkgroups, stateRank } from '../../../common/workgroupList.mjs';
import { workgroupMark, workgroupStatusLine } from '../../../common/workgroupMarkState.mjs';

export const ROSTER_WORKGROUP_CAP = 5;

const MATCH_FIELDS = ['label', 'name', 'id', 'preview'];
const CREATABLE_SECTIONS = ['profiles', 'workgroups'];

export const SECTION_LABELS = { front: '', pinned: 'Pinned', profiles: 'Profiles', workgroups: 'Workgroups' };

const profileOf = (item) => (item?.kind === 'profile' ? item.raw ?? item : null);

function needle(query) {
  return String(query ?? '').replace(/^[@#]/, '').trim().toLowerCase();
}

export function matchesQuery(item, query) {
  const q = needle(query);
  if (!q) return true;
  return MATCH_FIELDS.some((field) => String(item?.[field] ?? '').toLowerCase().includes(q));
}

export const ALL_WORKGROUPS_KEY = 'all-workgroups';

function capWorkgroups(rows, total, cap) {
  if (!cap || rows.length <= cap) return rows;
  return [...rosterWorkgroups(rows, cap), { kind: ALL_WORKGROUPS_KEY, id: ALL_WORKGROUPS_KEY, count: total }];
}

export function rosterSections(items, query, options) {
  const { front, rest: others } = splitDefaultProfile(items ?? [], profileOf);
  const hits = others.filter((item) => matchesQuery(item, query));
  const rest = hits.filter((item) => !item.pinned);
  const searching = !!needle(query);
  const kept = searching
    ? []
    : (options?.keepEmpty ?? []).filter((key) => CREATABLE_SECTIONS.includes(key));
  const workgroups = rest.filter((item) => item.kind === 'workgroup');
  const total = others.filter((item) => item.kind === 'workgroup').length;
  return [
    { key: 'front', label: SECTION_LABELS.front, data: front && matchesQuery(front, query) ? [front] : [] },
    { key: 'pinned', label: SECTION_LABELS.pinned, data: hits.filter((item) => item.pinned) },
    { key: 'profiles', label: SECTION_LABELS.profiles, data: rest.filter((item) => item.kind === 'profile') },
    { key: 'workgroups', label: SECTION_LABELS.workgroups, data: searching ? workgroups : capWorkgroups(workgroups, total, options?.workgroupCap) },
  ].filter((section) => section.data.length > 0 || kept.includes(section.key));
}

export function withActivity(item, rowState) {
  const next = { ...item, activity: rowState };
  if (item?.kind !== 'workgroup' || item.stateId !== 'idle' || rowState?.state !== 'working') return next;
  const mark = workgroupMark({ workgroup: item.raw ?? {}, run: rowState.phase ? { phase: rowState.phase } : null, busy: true });
  return { ...next, stateId: 'active', preview: workgroupStatusLine(mark) ?? 'Working', previewTone: null };
}

export function workgroupSections(items, filter, query) {
  const rows = (items ?? [])
    .filter((item) => item.kind === 'workgroup' && inFilter(item.stateId, filter) && matchesQuery(item, query))
    .sort((a, b) => stateRank(a.stateId) - stateRank(b.stateId)
      || Number(a.raw?.queue_position || 0) - Number(b.raw?.queue_position || 0)
      || b.sortKey - a.sortKey);
  if (filter !== 'all') return rows.length ? [{ key: filter, label: null, data: rows }] : [];
  return groupWorkgroupRows(rows.map((item) => ({ ...item, state: { id: item.stateId } })))
    .map((group) => ({ key: group.id, label: group.label, data: group.rows }));
}

export function rosterIsEmpty(sections) {
  return (sections ?? []).every((section) => (section.data?.length ?? 0) === 0);
}

export function isFirstProfile({ empty, initialLoading = false, paired = true, query = '', daemonDown = false, error = null }) {
  return !!empty && !initialLoading && !!paired && !String(query ?? '').trim() && !daemonDown && !error;
}

export function useSettledOnce(loading, key) {
  const seen = useRef({ key, settled: false });
  if (seen.current.key !== key) seen.current = { key, settled: false };
  if (!loading) seen.current.settled = true;
  return loading && !seen.current.settled;
}

export const TILES_KEY = 'tiles';

export function tileSections(sections) {
  const front = sections.find((section) => section.key === 'front')?.data ?? [];
  const pinned = sections.find((section) => section.key === 'pinned')?.data ?? [];
  const tiles = [...front, ...pinned];
  const rest = sections.filter((section) => section.key !== 'front' && section.key !== 'pinned');
  if (tiles.length === 0) return rest;
  return [{ key: TILES_KEY, label: '', data: [{ kind: TILES_KEY, id: TILES_KEY, items: tiles }] }, ...rest];
}
