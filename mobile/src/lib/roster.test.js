import { describe, expect, it } from 'vitest';

import { ALL_WORKGROUPS_KEY, matchesQuery, ROSTER_WORKGROUP_CAP, rosterIsEmpty, rosterSections, withActivity, workgroupSections } from './roster';

const alpi = { kind: 'profile', id: 'alpi', name: 'alpi', label: 'alpi', preview: 'ready', pinned: true };
const pixel = { kind: 'profile', id: 'pixel', name: 'pixel', label: 'pixel', preview: 'MODEL_OK' };
const mira = { kind: 'profile', id: 'mira', name: 'mira', label: 'mira', preview: 'orden lista' };
const abad = { kind: 'workgroup', id: 'wg1', label: 'site-hotel-abad-v23', preview: "Workgroup for hotel 'hotel-abad'" };
const roma = { kind: 'workgroup', id: 'wg2', label: 'site-roma-nueve-dos', preview: 'Workgroup for hotel', pinned: true };

const all = [alpi, pixel, mira, abad, roma];

describe('rosterSections', () => {
  it('groups pinned first, then profiles, then workgroups', () => {
    const sections = rosterSections(all, '');
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(sections[0].data).toEqual([alpi, roma]);
    expect(sections[1].data).toEqual([pixel, mira]);
    expect(sections[2].data).toEqual([abad]);
  });

  it('never lists a pinned item twice', () => {
    const ids = rosterSections(all, '').flatMap((s) => s.data.map((i) => i.id));
    expect(ids).toEqual([...new Set(ids)]);
  });

  it('drops empty sections instead of rendering a bare label', () => {
    expect(rosterSections([pixel, mira], '').map((s) => s.key)).toEqual(['profiles']);
    expect(rosterSections([], '')).toEqual([]);
    expect(rosterIsEmpty(rosterSections([], ''))).toBe(true);
  });

  it('filters every section by the query and keeps the surviving order', () => {
    const sections = rosterSections(all, 'hotel');
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'workgroups']);
    expect(sections[0].data).toEqual([roma]);
    expect(sections[1].data).toEqual([abad]);
  });

  it('matches on preview text, not just the name', () => {
    expect(rosterSections(all, 'MODEL_OK').map((s) => s.data.map((i) => i.id))).toEqual([['pixel']]);
  });
});

describe('rosterSections creation reachability', () => {
  const CREATABLE = { keepEmpty: ['profiles', 'workgroups'] };

  it('keeps an empty creatable section, so a daemon with no workgroups still has a heading to create from', () => {
    const sections = rosterSections([pixel, mira], '', CREATABLE);
    expect(sections.map((s) => s.key)).toEqual(['profiles', 'workgroups']);
    expect(sections[1].data).toEqual([]);
  });

  it('keeps both creatable headings when the daemon holds nothing at all', () => {
    expect(rosterSections([], '', CREATABLE).map((s) => s.key)).toEqual(['profiles', 'workgroups']);
  });

  it('keeps both creatable headings when every item is pinned', () => {
    const sections = rosterSections([alpi, roma], '', CREATABLE);
    expect(sections.map((s) => s.key)).toEqual(['pinned', 'profiles', 'workgroups']);
    expect(sections[0].data).toEqual([alpi, roma]);
    expect(sections[1].data).toEqual([]);
    expect(sections[2].data).toEqual([]);
  });

  it('never keeps an empty pinned section — a pin is not something you create', () => {
    const sections = rosterSections([pixel], '', { keepEmpty: ['pinned', 'profiles', 'workgroups'] });
    expect(sections.map((s) => s.key)).toEqual(['profiles', 'workgroups']);
  });

  it('drops the kept headings while a query is filtering, so a miss still reads as a miss', () => {
    expect(rosterSections(all, 'zzz', CREATABLE)).toEqual([]);
    expect(rosterSections(all, '#site-roma', CREATABLE).map((s) => s.key)).toEqual(['pinned']);
  });

  it('still calls a roster of bare headings empty', () => {
    expect(rosterIsEmpty(rosterSections([], '', CREATABLE))).toBe(true);
    expect(rosterIsEmpty(rosterSections([alpi, roma], '', CREATABLE))).toBe(false);
  });
});

describe('rosterSections front door', () => {
  const host = { kind: 'profile', id: 'default', name: 'default', label: 'alpi', preview: 'quiet week', paused: true, raw: { name: 'default', is_default: true } };
  const wgDefault = { kind: 'workgroup', id: 'default', name: 'default', label: 'default', preview: 'brief' };

  it('leads with an unlabelled section holding only the default profile, above pinned', () => {
    const sections = rosterSections([pixel, host, alpi, roma, abad], '');
    expect(sections.map((s) => s.key)).toEqual(['front', 'pinned', 'profiles', 'workgroups']);
    expect(sections[0]).toEqual({ key: 'front', label: '', data: [host] });
    expect(sections[1].data).toEqual([alpi, roma]);
  });

  it('ignores a stale pin on the default profile', () => {
    const sections = rosterSections([{ ...host, pinned: true }, pixel], '');
    expect(sections.map((s) => s.key)).toEqual(['front', 'profiles']);
  });

  it('keeps it under a filter only when it matches its name or its label', () => {
    expect(rosterSections([host, pixel], 'alp').map((s) => s.key)).toEqual(['front']);
    expect(rosterSections([host, pixel], 'defa').map((s) => s.key)).toEqual(['front']);
    expect(rosterSections([host, pixel], 'pixel').map((s) => s.key)).toEqual(['profiles']);
  });

  it('never takes a workgroup named default for the front door', () => {
    expect(rosterSections([wgDefault, pixel], '').map((s) => s.key)).toEqual(['profiles', 'workgroups']);
  });

  it('has no front section on a connection without the default profile', () => {
    expect(rosterSections([pixel, mira], '').map((s) => s.key)).toEqual(['profiles']);
  });
});

describe('matchesQuery', () => {
  it('is case-insensitive and ignores surrounding blanks', () => {
    expect(matchesQuery(pixel, '  PIXEL ')).toBe(true);
    expect(matchesQuery(pixel, 'PiXeL')).toBe(true);
  });

  it('treats an empty query as match-all', () => {
    for (const q of ['', '   ', null, undefined]) expect(matchesQuery(pixel, q)).toBe(true);
  });

  it('does not match an unrelated needle', () => {
    expect(matchesQuery(pixel, 'zzz')).toBe(false);
  });

  it('ignores a leading @ or # so a typed mention still matches', () => {
    expect(matchesQuery(pixel, '@pixel')).toBe(true);
    expect(matchesQuery(abad, '#site-hotel')).toBe(true);
    expect(rosterSections(all, '#site-roma').map((s) => s.data.map((i) => i.id))).toEqual([['wg2']]);
  });

  it('strips only the leading marker, not one inside the needle', () => {
    expect(matchesQuery({ label: 'a#b' }, '#a#b')).toBe(true);
    expect(matchesQuery({ label: 'ab' }, 'a#b')).toBe(false);
  });
});

describe('roster workgroup cap', () => {
  const wg = (id, stateId, sortKey) => ({ kind: 'workgroup', id, label: id, preview: stateId, stateId, sortKey });
  const many = [
    wg('i1', 'idle', 9), wg('i2', 'idle', 8), wg('q', 'queued', 7), wg('i3', 'idle', 6),
    wg('w', 'active', 5), wg('i4', 'idle', 4), wg('n', 'needs', 3), wg('i5', 'idle', 2),
  ];

  it('keeps what moves, fills up to five rows with the most recent idle ones and ends in All workgroups', () => {
    const section = rosterSections(many, '', { workgroupCap: ROSTER_WORKGROUP_CAP }).find((s) => s.key === 'workgroups');
    expect(section.data.map((i) => i.id)).toEqual(['w', 'n', 'q', 'i1', 'i2', ALL_WORKGROUPS_KEY]);
    expect(section.data.at(-1)).toMatchObject({ kind: ALL_WORKGROUPS_KEY, count: 8 });
  });

  it('counts pinned workgroups in All workgroups and lists every workgroup while searching or uncapped', () => {
    const pinned = { ...wg('p', 'idle', 10), pinned: true };
    const capped = rosterSections([...many, pinned], '', { workgroupCap: ROSTER_WORKGROUP_CAP }).find((s) => s.key === 'workgroups');
    expect(capped.data.at(-1).count).toBe(9);
    expect(rosterSections(many, 'i', { workgroupCap: ROSTER_WORKGROUP_CAP }).find((s) => s.key === 'workgroups').data.some((i) => i.kind === ALL_WORKGROUPS_KEY)).toBe(false);
    expect(rosterSections(many, '').find((s) => s.key === 'workgroups').data).toHaveLength(8);
  });

  it('adds no All workgroups row when every workgroup already fits', () => {
    const section = rosterSections(many.slice(0, 5), '', { workgroupCap: ROSTER_WORKGROUP_CAP }).find((s) => s.key === 'workgroups');
    expect(section.data.map((i) => i.id)).toEqual(['i1', 'i2', 'q', 'i3', 'w']);
  });
});

describe('workgroupSections', () => {
  const wg = (id, stateId, sortKey, raw = {}) => ({ kind: 'workgroup', id, label: id, preview: id, stateId, sortKey, raw });
  const items = [wg('idle-old', 'idle', 1), wg('idle-new', 'idle', 5), wg('q2', 'queued', 9, { queue_position: 2 }), wg('q1', 'queued', 3, { queue_position: 1 }),
    wg('broken', 'error', 2), wg('run', 'active', 4), wg('rest', 'paused', 8), { kind: 'profile', id: 'doc', label: 'doc' }];

  it('groups All under Needs you, Working, Queued, Idle and Paused in the order the desktop table sorts', () => {
    const sections = workgroupSections(items, 'all', '');
    expect(sections.map((s) => [s.label, s.data.map((i) => i.id)])).toEqual([
      ['Needs you', ['broken']], ['Working', ['run']], ['Queued', ['q1', 'q2']], ['Idle', ['idle-new', 'idle-old']], ['Paused', ['rest']],
    ]);
  });

  it('shows one unlabelled list for a filter, narrows by the query and returns nothing when nothing is left', () => {
    expect(workgroupSections(items, 'active', '')).toEqual([{ key: 'active', label: null, data: [items[5], items[4]] }]);
    expect(workgroupSections(items, 'all', 'idle-n').flatMap((s) => s.data.map((i) => i.id))).toEqual(['idle-new']);
    expect(workgroupSections(items, 'paused', 'zzz')).toEqual([]);
  });
});

describe('withActivity', () => {
  const idle = { kind: 'workgroup', id: 'w', stateId: 'idle', preview: 'last run done', previewTone: null };

  it('files an idle workgroup the activity feed sees working under Working, named by its phase and owner', () => {
    expect(withActivity(idle, { state: 'working' })).toMatchObject({ stateId: 'active', preview: 'Working', previewTone: null, activity: { state: 'working' } });
    const owned = { ...idle, raw: { id: 'w', phase_map: { build: { owner: '@pixel' } } } };
    expect(withActivity(owned, { state: 'working', phase: 'build' })).toMatchObject({ stateId: 'active', preview: 'Working · build · @pixel' });
  });

  it('keeps what the pipeline already says and leaves profiles and quiet workgroups alone', () => {
    const queued = { ...idle, stateId: 'queued', preview: 'Queued · #2' };
    expect(withActivity(queued, { state: 'working' })).toMatchObject({ stateId: 'queued', preview: 'Queued · #2' });
    expect(withActivity(idle, null)).toEqual({ ...idle, activity: null });
    expect(withActivity({ kind: 'profile', id: 'doc' }, { state: 'working' })).toEqual({ kind: 'profile', id: 'doc', activity: { state: 'working' } });
  });

  it('keeps a workgroup the feed sees working in a capped roster', () => {
    const rows = [1, 2, 3, 4, 5, 6].map((n) => ({ kind: 'workgroup', id: `i${n}`, label: `i${n}`, preview: '', stateId: 'idle', sortKey: 10 - n }));
    const long = withActivity({ kind: 'workgroup', id: 'long', label: 'long', preview: '', stateId: 'idle', sortKey: 0 }, { state: 'working' });
    const section = rosterSections([...rows, long], '', { workgroupCap: ROSTER_WORKGROUP_CAP }).find((s) => s.key === 'workgroups');
    expect(section.data[0].id).toBe('long');
  });
});
